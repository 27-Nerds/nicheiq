"""Code-owned identities for idea candidates and ruled-out findings.

The backend mirrors the idea-id algorithm in ``backend/src/utils/ideaIdentity.ts``.
Keep the byte-level seed stable: legacy checkpoints hydrated in Python must resolve to
the same IDs as their existing backend projections.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_solution_name(value: Any) -> str:
    """Normalize display-name whitespace without changing user-visible casing."""
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def normalized_solution_name_key(value: Any) -> str:
    """Case-insensitive key used only for matching and ambiguity checks."""
    return normalize_solution_name(value).lower()


def deterministic_idea_id(
    job_id: str,
    origin: str,
    operation_key: str,
    index: int,
) -> str:
    """Return the stable ID shared with the backend's TypeScript implementation."""
    seed = f"nicheiq:idea:v1\0{job_id}\0{origin}\0{operation_key}\0{index}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return f"idea_{digest}"


def deterministic_finding_id(job_id: str, operation_key: str, index: int) -> str:
    """Return a stable identity for a ruled-out finding."""
    seed = f"nicheiq:finding:v1\0{job_id}\0{operation_key}\0{index}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    return f"finding_{digest}"


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(key, default)
    return getattr(record, key, default)


def _set(record: Any, key: str, value: Any) -> None:
    if isinstance(record, MutableMapping):
        record[key] = value
    else:
        setattr(record, key, value)


def _valid_identity(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_revision(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def stamp_new_idea_identities(
    job_id: str,
    ideas: Iterable[Any],
    *,
    origin: str,
    operation_key: str,
    force: bool = False,
    only_unowned: bool = False,
) -> list[Any]:
    """Stamp missing identities in original sequence order and return the same records."""
    stamped = list(ideas)
    for index, idea in enumerate(stamped):
        if only_unowned and _get(idea, "identity_origin"):
            continue
        if force or not _valid_identity(_get(idea, "idea_id")):
            _set(
                idea,
                "idea_id",
                deterministic_idea_id(job_id, origin, operation_key, index),
            )
        if force or not _valid_revision(_get(idea, "idea_revision")):
            _set(idea, "idea_revision", 1)
        _set(idea, "identity_origin", origin)
        _set(idea, "identity_operation_id", operation_key)
    return stamped


def apply_pool_identities(
    ideas: Iterable[Any],
    identity_map: Iterable[Any],
) -> int:
    """Stamp backend identities onto selectable checkpoint candidates by name.

    Identities are assigned by the BACKEND at /api/workers/ideas-ready, seeded from the
    Phase-1 dispatch id, and persisted only in Postgres — the checkpoint on disk carries no
    idea_id at all. `ensure_legacy_idea_identities` below therefore cannot reproduce them
    (it does not know the dispatch id), and its `legacy_backfill` ids never match the refs
    the backend later sends for Phase 2. The backend closes the gap by shipping its stamped
    pool in the work payload; this applies it. Hidden ``demoted`` and ``absorbed``
    records are historical checkpoint state, not members of that backend pool, so they
    must never capture a same-name selectable candidate's identity.

    Keyed by normalized name rather than position: the checkpoint pool and the backend's
    stored pool need not be the same length (a batch can land in one before the other), and
    a positional assignment that silently slips by one would research an idea the user never
    bought. Ambiguous names are skipped rather than guessed, leaving them to the legacy
    backfill — a candidate with no usable identity must fail the lookup loudly. Native
    checkpoint identities are never rewritten: exact matches already carry stronger
    provenance, while a mismatch means the two pools disagree and must fail. The synthetic
    `legacy_backfill` identity created during old-checkpoint reconstruction is only a
    compatibility placeholder, so the backend map may replace it.
    """
    by_name: dict[str, tuple[str, int]] = {}
    ambiguous: set[str] = set()
    for entry in identity_map or []:
        key = normalized_solution_name_key(_get(entry, "solution_name"))
        idea_id = str(_get(entry, "idea_id") or "").strip()
        revision = _get(entry, "idea_revision")
        if not key or not _valid_identity(idea_id) or not _valid_revision(revision):
            continue
        if key in by_name:
            ambiguous.add(key)
            continue
        by_name[key] = (idea_id, revision)
    for key in ambiguous:
        by_name.pop(key, None)

    # Use the canonical visibility projection rather than re-declaring lifecycle statuses
    # here. A synthesized winner can legitimately retain an absorbed same-name source record;
    # only the selectable winner participates in the backend pool identity contract.
    from nicheiq.models.solution_idea import visible_ideas

    applied = 0
    for idea in visible_ideas(list(ideas)):
        identity = by_name.get(
            normalized_solution_name_key(_get(idea, "solution_name"))
        )
        if identity is None:
            continue
        existing_id = str(_get(idea, "idea_id") or "").strip()
        existing_revision = _get(idea, "idea_revision")
        if (
            _valid_identity(existing_id)
            and _valid_revision(existing_revision)
            and (existing_id, existing_revision) == identity
        ):
            continue
        identity_origin = _get(idea, "identity_origin")
        is_legacy_placeholder = identity_origin == "legacy_backfill"
        has_owner = (
            not is_legacy_placeholder
            and (
                _valid_identity(existing_id)
                or bool(identity_origin)
                or bool(_get(idea, "identity_operation_id"))
            )
        )
        if has_owner:
            name = normalize_solution_name(_get(idea, "solution_name"))
            raise RuntimeError(
                "Checkpoint candidate identity conflicts with backend pool "
                f"for {name!r}: {existing_id or '<missing>'}:"
                f"{existing_revision!r} != {identity[0]}:{identity[1]}"
            )
        _set(idea, "idea_id", identity[0])
        _set(idea, "idea_revision", identity[1])
        _set(idea, "identity_origin", "backend_pool")
        _set(idea, "identity_operation_id", None)
        applied += 1
    return applied


def ensure_legacy_idea_identities(job_id: str, ideas: Iterable[Any]) -> list[Any]:
    """Hydrate pre-identity checkpoints using the backend's old visible-pool ordering."""
    records = list(ideas)
    visible = [
        idea for idea in records
        if _get(idea, "candidate_status", "active") not in {"demoted", "absorbed"}
    ]
    hidden = [
        idea for idea in records
        if _get(idea, "candidate_status", "active") in {"demoted", "absorbed"}
    ]
    stamp_new_idea_identities(
        job_id,
        visible,
        origin="legacy_backfill",
        operation_key="pool",
        only_unowned=True,
    )
    stamp_new_idea_identities(
        job_id,
        hidden,
        origin="legacy_hidden",
        operation_key="pool",
        only_unowned=True,
    )
    return records


def stamp_ruled_out_findings(
    job_id: str,
    findings: Iterable[dict[str, Any]],
    *,
    operation_key: str,
) -> list[dict[str, Any]]:
    """Stamp finding and underlying idea identities without relying on display names.

    If the finding already embeds its full idea, that nested record is authoritative and
    receives a deterministic candidate identity. The same identity is copied to the finding
    envelope so consumers can address the demoted result without opening the nested payload.
    """
    stamped = list(findings)
    for index, finding in enumerate(stamped):
        if not _valid_identity(finding.get("finding_id")):
            finding["finding_id"] = deterministic_finding_id(
                job_id, operation_key, index,
            )
        if not _valid_revision(finding.get("finding_revision")):
            finding["finding_revision"] = 1

        nested = finding.get("idea")
        if isinstance(nested, MutableMapping):
            if not _valid_identity(nested.get("idea_id")):
                nested["idea_id"] = deterministic_idea_id(
                    job_id, "ruled_out", operation_key, index,
                )
            if not _valid_revision(nested.get("idea_revision")):
                nested["idea_revision"] = 1
            nested.setdefault("identity_origin", "ruled_out")
            nested.setdefault("identity_operation_id", operation_key)
            finding["idea_id"] = nested["idea_id"]
            finding["idea_revision"] = nested["idea_revision"]
            finding["identity_origin"] = nested["identity_origin"]
            finding["identity_operation_id"] = nested["identity_operation_id"]
        else:
            if not _valid_identity(finding.get("idea_id")):
                finding["idea_id"] = deterministic_idea_id(
                    job_id, "ruled_out", operation_key, index,
                )
            if not _valid_revision(finding.get("idea_revision")):
                finding["idea_revision"] = 1
            finding.setdefault("identity_origin", "ruled_out")
            finding.setdefault("identity_operation_id", operation_key)
    return stamped


def link_legacy_findings_to_ideas(
    findings: Iterable[dict[str, Any]],
    ideas: Iterable[Any],
) -> list[dict[str, Any]]:
    """Recover a legacy finding's candidate ref only when its old name join is unique."""
    by_name: dict[str, list[Any]] = {}
    for idea in ideas:
        key = normalized_solution_name_key(
            _get(idea, "solution_name") or _get(idea, "name")
        )
        if key:
            by_name.setdefault(key, []).append(idea)

    linked = list(findings)
    for finding in linked:
        if _valid_identity(finding.get("idea_id")):
            continue
        matches = by_name.get(
            normalized_solution_name_key(finding.get("idea_name")),
            [],
        )
        if len(matches) != 1:
            continue
        idea = matches[0]
        idea_id = _get(idea, "idea_id")
        idea_revision = _get(idea, "idea_revision")
        if not _valid_identity(idea_id) or not _valid_revision(idea_revision):
            continue
        finding["idea_id"] = idea_id
        finding["idea_revision"] = idea_revision
        finding["identity_origin"] = _get(idea, "identity_origin")
        finding["identity_operation_id"] = _get(idea, "identity_operation_id")
        nested = finding.get("idea")
        if isinstance(nested, MutableMapping):
            nested["idea_id"] = idea_id
            nested["idea_revision"] = idea_revision
            nested["identity_origin"] = _get(idea, "identity_origin")
            nested["identity_operation_id"] = _get(
                idea, "identity_operation_id",
            )
    return linked


def selection_fingerprint(refs: Iterable[Mapping[str, Any]]) -> str:
    """Hash normalized exact refs in input order; snapshots are deliberately excluded."""
    normalized = [
        {
            "idea_id": str(ref.get("idea_id") or "").strip(),
            "idea_revision": int(ref.get("idea_revision") or 0),
            "solution_name": normalize_solution_name(ref.get("solution_name")),
        }
        for ref in refs
    ]
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
