#!/usr/bin/env python3
"""Reconcile paying-wallet prose in registered preview/final report assets.

With ``--database-url`` this is an authoritative, audited data migration: it enumerates
``JobAsset`` rows, writes changed JSON to immutable siblings, and compare-and-swaps the registered
path. Positional paths remain available for the repository corpus sweep and local diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from nicheiq.models.research_state import NicheDifficultyVerdict
from nicheiq.utils.niche_difficulty import (
    _FIT_HEADLINES,
    paying_wallet_commercial_contract_copy,
    paying_wallet_summary_copy_violations,
    reconcile_persisted_niche_difficulty_verdict,
    reconcile_persisted_paying_wallet_summary,
)

CONTRACT_VERSION = "paying-wallet-positive-copy-v1"
MIGRATION_LOCK_KEY = 0x4E495143435237  # "NIQCCR7"
VALID_WALLET_CLASSES = frozenset({"paying", "mixed", "free-culture"})
NON_PAYING_WALLET_CLASSES = frozenset({"mixed", "free-culture"})
_REPORT_JOB_ID_RE = re.compile(
    r"^(?:preview|final)_report_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})\.json$",
    re.IGNORECASE,
)
_CHECKPOINT_DIR_JOB_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_DOUBLE_COLON_HEADLINE_RE = re.compile(
    r"^(Software Fit:\s*(?:Strong|Moderate|Limited|Hard)):\s+(.+)$",
    re.IGNORECASE,
)
_GENERIC_HEADLINES = frozenset(
    template.casefold()
    for headline in _FIT_HEADLINES.values()
    for template in (headline, headline.replace(". ", ": ", 1))
)
_GENERIC_STRENGTHS = frozenset(
    {"Most pains are workflow or data problems a tool can directly own."}
)


@dataclass(frozen=True)
class SectionResult:
    status: str
    reason: str = ""


@dataclass(frozen=True)
class Reconciliation:
    document: Any
    changed: bool
    paying: bool
    sections: dict[str, SectionResult]
    replacements: tuple[tuple[str, str], ...] = ()
    safe_copy: str | None = None


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    raw: bytes
    sha256: str
    inode: int
    size: int
    mtime_ns: int
    mode: int


@dataclass(frozen=True)
class AssetRecord:
    id: int
    job_id: str
    asset_type: str
    file_path: str
    updated_at: datetime


@dataclass
class Result:
    path: Path
    status: str
    detail: str = ""
    asset: AssetRecord | None = None
    source_sha256: str | None = None
    result_path: Path | None = None
    registered_result_path: str | None = None
    result_sha256: str | None = None
    result_size: int | None = None
    sections: dict[str, SectionResult] = field(default_factory=dict)
    replacements: tuple[tuple[str, str], ...] = ()
    safe_copy: str | None = None
    source_snapshot: FileSnapshot | None = None


STAGE_5_VERDICT_FILENAME = "stage_5_niche_difficulty.json"

# Local corpus shapes. `stage_5_niche_difficulty.json` is not a served asset, but it IS the
# source `_preserved_source_verdict` restores prose from, so a contradiction left there can be
# copied back into a served report on a later pass.
_LOCAL_ASSET_GLOBS = (
    "preview_report_*.json",
    "final_report_*.json",
    "report.json",
    STAGE_5_VERDICT_FILENAME,
)


def _asset_paths(inputs: Iterable[Path]) -> list[Path]:
    """Legacy/local corpus discovery. Database mode never calls this function."""
    paths: set[Path] = set()
    for item in inputs:
        if item.is_file():
            paths.add(item.resolve())
        elif item.is_dir():
            for pattern in _LOCAL_ASSET_GLOBS:
                paths.update(path.resolve() for path in item.rglob(pattern))
    return sorted(paths)


def _verdict_string_replacements(before: Any, after: Any) -> list[tuple[str, str]]:
    """Map text that was published to the text that replaces it.

    These pairs are applied to historic chat messages, so a wrong pair rewrites prose that is
    still on the card. Lists must therefore be compared by MEMBERSHIP, not by index: dropping
    one violating challenge shifts every later entry, and index-wise pairing would claim the
    surviving statements had been rewritten into each other.
    """
    replacements: list[tuple[str, str]] = []
    if isinstance(before, str) and isinstance(after, str) and before != after:
        replacements.append((before, after))
    elif isinstance(before, dict) and isinstance(after, dict):
        for key in before.keys() & after.keys():
            replacements.extend(_verdict_string_replacements(before[key], after[key]))
    elif isinstance(before, list) and isinstance(after, list):
        kept = {item for item in after if isinstance(item, str)}
        introduced = [
            item for item in after if isinstance(item, str) and item not in set(
                left for left in before if isinstance(left, str)
            )
        ]
        dropped = [item for item in before if isinstance(item, str) and item not in kept]
        for left, right in zip(before, after):
            if not isinstance(left, str) and not isinstance(right, str):
                replacements.extend(_verdict_string_replacements(left, right))
        if len(dropped) == len(introduced):
            # A same-size swap is a rewrite in place.
            replacements.extend(zip(dropped, introduced))
        else:
            # Otherwise the old statement simply stopped being publishable.
            replacements.extend((item, "") for item in dropped)
    return replacements


def _repair_double_colon_headline(verdict: NicheDifficultyVerdict) -> NicheDifficultyVerdict:
    match = _DOUBLE_COLON_HEADLINE_RE.match(verdict.headline.strip())
    if not match:
        return verdict
    clause = match.group(2)
    return verdict.model_copy(
        update={"headline": f"{match.group(1)}. {clause[:1].upper()}{clause[1:]}"}
    )


def _has_generic_template_overwrite(
    verdict: NicheDifficultyVerdict,
    source_verdict: NicheDifficultyVerdict,
) -> bool:
    if (
        verdict.headline.casefold() in _GENERIC_HEADLINES
        and source_verdict.headline != verdict.headline
        and source_verdict.headline.casefold() not in _GENERIC_HEADLINES
    ):
        return True
    if not verdict.key_strengths or not source_verdict.key_strengths:
        return False
    return (
        verdict.key_strengths[0] in _GENERIC_STRENGTHS
        and source_verdict.key_strengths[0] != verdict.key_strengths[0]
        and source_verdict.key_strengths[0] not in _GENERIC_STRENGTHS
    )


def _checkpoint_root(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if candidate.name == "checkpoints":
            return candidate
        # `output/jobs/<id>/report.json` has no `checkpoints` ancestor; its run checkpoints sit
        # in the sibling `output/checkpoints` tree.
        nested = candidate / "checkpoints"
        if nested.is_dir():
            return nested
    return path.parent


def _job_checkpoint_files(path: Path, job_id: str | None, filename: str) -> list[Path]:
    """Every same-job checkpoint file of one kind, newest last."""
    candidates: list[Path] = []
    sibling = path.parent / filename
    if sibling.exists() and sibling != path:
        candidates.append(sibling)
    if job_id:
        candidates.extend(
            sorted(_checkpoint_root(path).glob(f"checkpoint_*{job_id}*/{filename}"))
        )
    return list(dict.fromkeys(candidates))


def _path_job_id(path: Path) -> str | None:
    match = _REPORT_JOB_ID_RE.match(path.name)
    if match:
        return match.group(1)
    checkpoint_match = _CHECKPOINT_DIR_JOB_ID_RE.search(path.parent.name)
    return checkpoint_match.group(1) if checkpoint_match else None


def _preserved_source_verdict(
    path: Path,
    *,
    job_id: str | None = None,
) -> NicheDifficultyVerdict | None:
    if job_id is None:
        job_id = _path_job_id(path)
    if not job_id:
        return None

    valid: list[NicheDifficultyVerdict] = []
    for candidate in _job_checkpoint_files(path, job_id, STAGE_5_VERDICT_FILENAME):
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("niche_difficulty_verdict"), dict):
                raw = raw["niche_difficulty_verdict"]
            valid.append(NicheDifficultyVerdict.model_validate(raw))
        except (OSError, ValueError, TypeError):
            continue
    # Re-runs of the same job write byte-identical stage-5 checkpoints, so agreement is the
    # test, not file count. Genuinely different verdicts cannot be attributed to the asset in
    # front of us, and restoring the wrong run's prose would be a fabrication.
    unique = {verdict.model_dump_json(): verdict for verdict in valid}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def _authoritative_wallet(path: Path, job_id: str | None = None) -> tuple[str, str | None] | None:
    """Read the run's own wallet brief, which outranks whatever an asset embedded.

    A damaged asset that never persisted `market_reality.wallet` used to be unclassifiable and
    therefore skipped forever. The run metadata that produced it still records the probe.
    """
    if job_id is None:
        job_id = _path_job_id(path)
    briefs: list[tuple[str, str | None]] = []
    for candidate in _job_checkpoint_files(path, job_id, "metadata.json"):
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        brief = raw.get("niche_wallet_brief") if isinstance(raw, dict) else None
        if not isinstance(brief, dict):
            continue
        wallet_class = brief.get("wallet_class")
        evidence = brief.get("evidence")
        if isinstance(wallet_class, str) and isinstance(evidence, (str, type(None))):
            briefs.append((wallet_class, evidence))
    unique = list(dict.fromkeys(briefs))
    return unique[0] if len(unique) == 1 else None


def _reconcile_document(
    document: Any,
    *,
    source_verdict: NicheDifficultyVerdict | None = None,
    authoritative_wallet: tuple[str, str | None] | None = None,
    verdict_key: str | None = "niche_difficulty_verdict",
) -> Reconciliation:
    """Reconcile one persisted document.

    ``verdict_key=None`` means the document IS the verdict (a stage-5 checkpoint), which has no
    embedded wallet block of its own and therefore relies on ``authoritative_wallet``.
    """
    if not isinstance(document, dict):
        return Reconciliation(
            document, False, False, {"document": SectionResult("invalid", "root is not an object")}
        )

    reconciled = dict(document)
    changed = False
    sections: dict[str, SectionResult] = {}
    replacements: list[tuple[str, str]] = []

    def read_verdict(source: dict) -> Any:
        return source if verdict_key is None else source.get(verdict_key)

    def write_verdict(raw: dict, safe: NicheDifficultyVerdict) -> dict:
        nonlocal reconciled, changed
        merged = {**raw, **safe.model_dump(mode="json")}
        if verdict_key is None:
            reconciled = merged
        else:
            reconciled[verdict_key] = merged
        replacements.extend(_verdict_string_replacements(raw, merged))
        changed = True
        sections["niche_difficulty_verdict"] = SectionResult("changed")
        return merged

    # Structural repairs run BEFORE the wallet branch. A blanket-templated or double-colon
    # verdict is damage regardless of wallet class, and gating the repair on a `paying` reading
    # left every asset with an unreadable wallet block damaged forever.
    raw_verdict = read_verdict(document)
    if isinstance(raw_verdict, dict):
        try:
            verdict = NicheDifficultyVerdict.model_validate(raw_verdict)
            repaired = verdict
            if (
                source_verdict is not None
                and source_verdict.difficulty_level == verdict.difficulty_level
                and source_verdict.software_addressability == verdict.software_addressability
                and _has_generic_template_overwrite(verdict, source_verdict)
            ):
                repaired = source_verdict
            repaired = _repair_double_colon_headline(repaired)
            if repaired != verdict:
                write_verdict(raw_verdict, repaired)
        except (ValueError, TypeError):
            pass

    def early(wallet_result: SectionResult) -> Reconciliation:
        return Reconciliation(
            reconciled,
            changed,
            False,
            {"wallet": wallet_result, **sections},
            tuple(replacements),
        )

    embedded: tuple[str, str | None] | None | SectionResult = None
    if verdict_key is not None:
        market_reality = document.get("market_reality")
        if not isinstance(market_reality, dict):
            embedded = SectionResult("unknown", "market_reality is missing")
        else:
            wallet = market_reality.get("wallet")
            if wallet is None:
                embedded = SectionResult("unknown", "wallet is missing")
            elif not isinstance(wallet, dict):
                embedded = SectionResult("invalid", "wallet is not an object")
            elif not isinstance(wallet.get("wallet_class"), str) or not isinstance(
                wallet.get("evidence"), (str, type(None))
            ):
                embedded = SectionResult(
                    "invalid", "wallet_class/evidence must be strings or null"
                )
            else:
                embedded = (wallet["wallet_class"], wallet.get("evidence"))

    if isinstance(embedded, tuple):
        wallet_class, wallet_evidence = embedded
    elif authoritative_wallet is not None:
        # The run's own probe outranks a missing or malformed embedded copy of it.
        wallet_class, wallet_evidence = authoritative_wallet
    elif isinstance(embedded, SectionResult):
        return early(embedded)
    else:
        return early(SectionResult("unknown", "no wallet brief for this run"))

    normalized_wallet_class = wallet_class.strip().lower()
    if normalized_wallet_class not in VALID_WALLET_CLASSES:
        return early(
            SectionResult("invalid", f"unrecognized wallet_class: {wallet_class!r}")
        )
    if normalized_wallet_class in NON_PAYING_WALLET_CLASSES:
        return early(SectionResult("not_paying"))
    if not (wallet_evidence or "").strip():
        return early(
            SectionResult("unknown", "paying wallet is missing evidence")
        )

    safe_copy = paying_wallet_commercial_contract_copy(
        normalized_wallet_class, wallet_evidence
    )
    if safe_copy is None:  # Defensive: the shared contract must agree with the proven schema.
        return early(
            SectionResult("invalid", "paying wallet contract could not be applied")
        )

    sections = {"wallet": SectionResult("paying"), **sections}

    # Sections are deliberately isolated: an invalid verdict is left byte-for-value alone and
    # recorded, but cannot prevent a valid portfolio summary from being made publishable.
    raw_verdict = read_verdict(reconciled)
    if raw_verdict is None:
        sections["niche_difficulty_verdict"] = SectionResult("not_present")
    elif not isinstance(raw_verdict, dict):
        sections["niche_difficulty_verdict"] = SectionResult("invalid", "verdict is not an object")
    else:
        try:
            # `raw_verdict` already carries the structural repairs applied above.
            verdict = NicheDifficultyVerdict.model_validate(raw_verdict)
            safe_verdict = reconcile_persisted_niche_difficulty_verdict(
                verdict,
                wallet_class=normalized_wallet_class,
                wallet_evidence=wallet_evidence,
                niche=document.get("niche") if isinstance(document.get("niche"), str) else None,
            )
            if safe_verdict != verdict:
                write_verdict(raw_verdict, safe_verdict)
            else:
                sections.setdefault("niche_difficulty_verdict", SectionResult("unchanged"))
        except Exception as exc:  # noqa: BLE001 - this section alone is quarantined
            sections["niche_difficulty_verdict"] = SectionResult("invalid", str(exc))

    raw_summary = document.get("idea_portfolio_summary") if verdict_key is not None else None
    if raw_summary is None:
        sections["idea_portfolio_summary"] = SectionResult("not_present")
    elif not isinstance(raw_summary, str):
        sections["idea_portfolio_summary"] = SectionResult("invalid", "summary is not a string")
    else:
        try:
            safe_summary = reconcile_persisted_paying_wallet_summary(
                raw_summary,
                wallet_class=normalized_wallet_class,
                wallet_evidence=wallet_evidence,
            )
            if safe_summary != raw_summary:
                reconciled["idea_portfolio_summary"] = safe_summary
                replacements.append((raw_summary, safe_summary or ""))
                changed = True
                sections["idea_portfolio_summary"] = SectionResult("changed")
            else:
                sections["idea_portfolio_summary"] = SectionResult("unchanged")
        except Exception as exc:  # noqa: BLE001 - this section alone is quarantined
            sections["idea_portfolio_summary"] = SectionResult("invalid", str(exc))

    return Reconciliation(
        reconciled,
        changed,
        True,
        sections,
        tuple((old, new) for old, new in replacements if old and old != new),
        safe_copy,
    )


def _reconciled_document(document: Any) -> tuple[Any, bool]:
    """Compatibility wrapper retained for callers from the earlier rounds."""
    outcome = _reconcile_document(document)
    return outcome.document, outcome.changed


def _snapshot(path: Path) -> FileSnapshot:
    with path.open("rb") as handle:
        raw = handle.read()
        file_stat = os.fstat(handle.fileno())
    return FileSnapshot(
        path=path,
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        inode=file_stat.st_ino,
        size=file_stat.st_size,
        mtime_ns=file_stat.st_mtime_ns,
        mode=stat.S_IMODE(file_stat.st_mode),
    )


def _snapshot_matches(snapshot: FileSnapshot) -> bool:
    try:
        current = _snapshot(snapshot.path)
    except OSError:
        return False
    return (
        current.sha256 == snapshot.sha256
        and current.inode == snapshot.inode
        and current.size == snapshot.size
        and current.mtime_ns == snapshot.mtime_ns
    )


def _serialized(document: Any) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_json(path: Path, document: Any, expected: FileSnapshot | None = None) -> bool:
    original = expected or _snapshot(path)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(_serialized(document))
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(original.mode)
        if not _snapshot_matches(original):
            return False
        os.replace(temp_path, path)
        temp_path = None
        _fsync_directory(path.parent)
        return True
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def backfill(path: Path, *, dry_run: bool) -> Result:
    try:
        source = _snapshot(path)
        document = json.loads(source.raw)
        bare_verdict = path.name == STAGE_5_VERDICT_FILENAME
        outcome = _reconcile_document(
            document,
            source_verdict=None if bare_verdict else _preserved_source_verdict(path),
            authoritative_wallet=_authoritative_wallet(path),
            verdict_key=None if bare_verdict else "niche_difficulty_verdict",
        )
        if not outcome.changed:
            status = (
                "skipped"
                if any(s.status in {"invalid", "unknown"} for s in outcome.sections.values())
                else "unchanged"
            )
            detail = "; ".join(
                f"{name}: {section.reason}" for name, section in outcome.sections.items() if section.reason
            )
            return Result(path, status, detail, source_sha256=source.sha256, sections=outcome.sections)
        if not dry_run and not _atomic_write_json(path, outcome.document, source):
            return Result(path, "conflict", "source changed before atomic replace")
        return Result(
            path,
            "would-change" if dry_run else "changed",
            source_sha256=source.sha256,
            sections=outcome.sections,
            replacements=outcome.replacements,
            safe_copy=outcome.safe_copy,
        )
    except Exception as exc:  # noqa: BLE001 - one odd asset must not stop the corpus backfill
        return Result(path, "skipped", str(exc))


def _resolve_registered_path(file_path: str, asset_root: Path) -> Path:
    if not file_path:
        raise ValueError("empty JobAsset.filePath")
    candidate = Path(file_path)
    if ".." in candidate.parts:
        raise ValueError("parent traversal is not allowed")
    resolved = candidate.resolve() if candidate.is_absolute() else (asset_root / candidate).resolve()
    root = asset_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path is outside asset root {root}")
    return resolved


def _registered_immutable_path(record: AssetRecord, source: Path, sha256: str) -> tuple[Path, str]:
    result = source.parent / f".commercial-copy-r7-{record.id}-{sha256[:16]}.json"
    if Path(record.file_path).is_absolute():
        registered = str(result)
    else:
        registered = str(Path(record.file_path).parent / result.name)
    if len(registered) > 500:
        raise ValueError("immutable result path exceeds JobAsset.filePath capacity")
    return result, registered


def _write_immutable(path: Path, raw: bytes, source: FileSnapshot) -> bool:
    """Create once; return whether this invocation created the immutable result."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, source.mode)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashlib.sha256(raw).hexdigest():
            raise RuntimeError(f"immutable result collision at {path}")
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        source_stat = source.path.stat()
        try:
            os.chown(path, source_stat.st_uid, source_stat.st_gid)
        except PermissionError:
            result_stat = path.stat()
            if (result_stat.st_uid, result_stat.st_gid) != (source_stat.st_uid, source_stat.st_gid):
                raise
        shutil.copystat(source.path, path, follow_symlinks=True)
        _fsync_directory(path.parent)
        return True
    except Exception:
        path.unlink(missing_ok=True)
        raise


def prepare_registered_asset(record: AssetRecord, asset_root: Path) -> Result:
    try:
        path = _resolve_registered_path(record.file_path, asset_root)
        source = _snapshot(path)
        outcome = _reconcile_document(
            json.loads(source.raw),
            source_verdict=_preserved_source_verdict(path, job_id=record.job_id),
            authoritative_wallet=_authoritative_wallet(path, job_id=record.job_id),
        )
        invalid = any(
            section.status in {"invalid", "unknown"}
            for section in outcome.sections.values()
        )
        if not outcome.paying and not outcome.changed:
            status = "skipped" if invalid else "not_paying"
            detail = "; ".join(
                f"{name}: {section.reason}" for name, section in outcome.sections.items() if section.reason
            )
            return Result(
                path, status, detail, record, source.sha256, path, record.file_path,
                source.sha256, source.size, outcome.sections, source_snapshot=source,
            )

        result_path = path
        registered_path = record.file_path
        result_raw = source.raw
        if outcome.changed:
            result_raw = _serialized(outcome.document)
            result_sha = hashlib.sha256(result_raw).hexdigest()
            result_path, registered_path = _registered_immutable_path(record, path, result_sha)
            _write_immutable(result_path, result_raw, source)
        result_sha = hashlib.sha256(result_raw).hexdigest()
        if invalid:
            status = "partial"
        elif not outcome.paying:
            status = "not_paying"
        elif outcome.changed:
            status = "changed"
        else:
            status = "unchanged"
        return Result(
            path,
            status,
            asset=record,
            source_sha256=source.sha256,
            result_path=result_path,
            registered_result_path=registered_path,
            result_sha256=result_sha,
            result_size=len(result_raw),
            sections=outcome.sections,
            replacements=outcome.replacements,
            safe_copy=outcome.safe_copy,
            source_snapshot=source,
        )
    except Exception as exc:  # noqa: BLE001 - audit and quarantine one bad authoritative row
        return Result(Path(record.file_path), "skipped", str(exc), asset=record)


def _section_json(sections: dict[str, SectionResult]) -> dict[str, dict[str, str]]:
    return {
        name: {"status": section.status, **({"reason": section.reason} if section.reason else {})}
        for name, section in sections.items()
    }


class BackfillRepository(Protocol):
    def start_run(self, contract_version: str) -> str: ...
    def enumerate_assets(self) -> list[AssetRecord]: ...
    def commit_asset(self, run_id: str, result: Result) -> Result: ...
    def reconcile_chat(
        self,
        run_id: str,
        replacements: dict[str, tuple[tuple[str, str], ...]],
        safe_copy: dict[str, str],
        eligible_job_ids: set[str],
    ) -> dict[str, int]: ...
    def complete_run(self, run_id: str, counts: dict[str, int], chat_counts: dict[str, int]) -> None: ...
    def fail_run(self, run_id: str, error: str) -> None: ...


def run_authoritative_backfill(repository: BackfillRepository, asset_root: Path) -> tuple[list[Result], dict[str, int]]:
    run_id = repository.start_run(CONTRACT_VERSION)
    results: list[Result] = []
    try:
        assets = repository.enumerate_assets()
        replacements: dict[str, list[tuple[str, str]]] = {}
        safe_copy: dict[str, str] = {}
        results_by_job: dict[str, list[Result]] = {}
        for asset in assets:
            prepared = prepare_registered_asset(asset, asset_root)
            committed = repository.commit_asset(run_id, prepared)
            results.append(committed)
            results_by_job.setdefault(asset.job_id, []).append(committed)
            if committed.asset and committed.safe_copy:
                replacements.setdefault(committed.asset.job_id, []).extend(committed.replacements)
                safe_copy[committed.asset.job_id] = committed.safe_copy

        frozen_replacements = {
            job_id: tuple(dict.fromkeys(values)) for job_id, values in replacements.items()
        }
        publishable_statuses = {"changed", "unchanged", "not_paying"}
        eligible_job_ids = {
            job_id
            for job_id, job_results in results_by_job.items()
            if job_results
            and all(result.status in publishable_statuses for result in job_results)
            and len({result.sections.get("wallet", SectionResult("unknown")).status for result in job_results}) == 1
        }
        chat_counts = repository.reconcile_chat(
            run_id, frozen_replacements, safe_copy, eligible_job_ids
        )
        if chat_counts["conflict"]:
            raise RuntimeError(
                f"historic chat reconciliation had {chat_counts['conflict']} concurrent conflict(s)"
            )
        counts = {
            status: sum(result.status == status for result in results)
            for status in ("changed", "unchanged", "not_paying", "partial", "skipped", "conflict")
        }
        counts["authoritative"] = len(assets)
        repository.complete_run(run_id, counts, chat_counts)
        return results, chat_counts
    except Exception as exc:
        repository.fail_run(run_id, str(exc))
        raise


def _reconcile_chat_content(
    content: str,
    replacements: tuple[tuple[str, str], ...],
    safe_copy: str,
) -> str:
    reconciled = content
    for old, new in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        reconciled = reconciled.replace(old, new)

    # LLM openings sometimes paraphrased the persisted fields rather than quoting them. Remove
    # only paragraphs that violate the shared publication contract; preserve every other
    # paragraph and add the sanctioned statement once.
    #
    # The caller only supplies `safe_copy` for a job whose wallet was proven paying, which is
    # what the contract gate needs; a chat paragraph is a FRAGMENT of a larger message, so it is
    # not itself required to carry the sanctioned statement, only to avoid contradicting it.
    parts = re.split(r"(\n\s*\n)", reconciled)
    changed = reconciled != content
    for index in range(0, len(parts), 2):
        paragraph = parts[index]
        if paragraph and paying_wallet_summary_copy_violations(
            paragraph,
            wallet_class="paying",
            wallet_evidence=safe_copy,
            expected_copy=safe_copy,
            allow_surrounding_copy=True,
            require_expected_copy=False,
        ):
            parts[index] = safe_copy
            changed = True
    if not changed:
        return content
    collapsed = "".join(parts)
    while collapsed.count(safe_copy) > 1:
        collapsed = collapsed.replace(safe_copy, "", 1)
    return collapsed.strip()


class PostgresBackfillRepository:
    def __init__(self, database_url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency diagnostic
            raise RuntimeError("database mode requires psycopg[binary]") from exc
        # Prisma accepts a `schema=` URL option; libpq does not. The migration tables live in the
        # connection's normal search_path, matching Prisma's migrate-deploy target.
        parsed = urlsplit(database_url)
        query_pairs = parse_qsl(parsed.query)
        schema = next((value for key, value in query_pairs if key == "schema"), None)
        libpq_pairs = [(key, value) for key, value in query_pairs if key != "schema"]
        if schema and not any(key == "options" for key, _value in libpq_pairs):
            libpq_pairs.append(("options", f"-c search_path={schema}"))
        query = urlencode(libpq_pairs)
        libpq_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
        self.connection = psycopg.connect(libpq_url, row_factory=dict_row)
        self.connection.autocommit = True
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))

    def close(self) -> None:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))
        finally:
            self.connection.close()

    def start_run(self, contract_version: str) -> str:
        run_id = str(uuid.uuid4())
        with self.connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "CommercialCopyBackfillRun" '
                '("id", "contractVersion", "status") VALUES (%s, %s, %s)',
                (run_id, contract_version, "RUNNING"),
            )
        return run_id

    def enumerate_assets(self) -> list[AssetRecord]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'SELECT "id", "jobId", "assetType"::text AS "assetType", "filePath", "updatedAt" '
                'FROM "JobAsset" WHERE "assetType" IN (\'PREVIEW_REPORT\', \'REPORT_JSON\') '
                'ORDER BY "id"'
            )
            return [
                AssetRecord(
                    id=row["id"], job_id=row["jobId"], asset_type=row["assetType"],
                    file_path=row["filePath"], updated_at=row["updatedAt"],
                )
                for row in cursor.fetchall()
            ]

    def _insert_item(self, cursor, run_id: str, result: Result, status: str) -> None:
        asset = result.asset
        assert asset is not None
        cursor.execute(
            'INSERT INTO "CommercialCopyBackfillItem" '
            '("runId", "targetKind", "targetId", "jobId", "assetType", "sourcePath", '
            '"resultPath", "sourceSha256", "resultSha256", "status", "reason", "sectionResults") '
            'VALUES (%s, \'JOB_ASSET\', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)',
            (
                run_id, str(asset.id), asset.job_id, asset.asset_type, asset.file_path,
                result.registered_result_path, result.source_sha256, result.result_sha256,
                status, result.detail or None, json.dumps(_section_json(result.sections)),
            ),
        )

    def commit_asset(self, run_id: str, result: Result) -> Result:
        asset = result.asset
        if asset is None:
            raise ValueError("authoritative result is missing its JobAsset record")

        if result.status == "skipped":
            # A previous fail-open runner may already have stamped this row NOT_APPLICABLE.
            # Unknown input must actively revoke that stale assertion; merely auditing the skip
            # would leave the old publishable status in place indefinitely.
            self.connection.autocommit = False
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(
                        'UPDATE "JobAsset" SET "commercialCopyStatus" = \'PENDING\', '
                        '"commercialCopySha256" = NULL, "commercialCopyCheckedAt" = NULL, '
                        '"updatedAt" = CURRENT_TIMESTAMP '
                        'WHERE "id" = %s AND "filePath" = %s AND "updatedAt" = %s '
                        'RETURNING "id"',
                        (asset.id, asset.file_path, asset.updated_at),
                    )
                    if cursor.fetchone() is None:
                        self.connection.rollback()
                        conflict = Result(
                            result.path,
                            "conflict",
                            "JobAsset row changed before quarantine compare-and-swap",
                            asset=asset,
                            source_sha256=result.source_sha256,
                            result_path=result.result_path,
                            registered_result_path=result.registered_result_path,
                            result_sha256=result.result_sha256,
                            sections=result.sections,
                            source_snapshot=result.source_snapshot,
                        )
                        with self.connection.cursor() as audit_cursor:
                            self._insert_item(audit_cursor, run_id, conflict, conflict.status)
                        self.connection.commit()
                        return conflict
                    self._insert_item(cursor, run_id, result, result.status)
                self.connection.commit()
                return result
            except Exception:
                self.connection.rollback()
                raise
            finally:
                self.connection.autocommit = True

        if result.source_snapshot is None or not _snapshot_matches(result.source_snapshot):
            conflict = Result(
                result.path, "conflict", "source content changed before JobAsset CAS",
                asset=asset, source_sha256=result.source_sha256, result_path=result.result_path,
                registered_result_path=result.registered_result_path,
                result_sha256=result.result_sha256, sections=result.sections,
                replacements=result.replacements, safe_copy=result.safe_copy,
            )
            with self.connection.cursor() as cursor:
                self._insert_item(cursor, run_id, conflict, conflict.status)
            return conflict

        publication_status = {
            "not_paying": "NOT_APPLICABLE",
            "partial": "PARTIAL",
            "changed": "RECONCILED",
            "unchanged": "RECONCILED",
        }[result.status]
        self.connection.autocommit = False
        try:
            with self.connection.cursor() as cursor:
                path_changed = result.registered_result_path != asset.file_path
                if path_changed:
                    # This update intentionally trips the DB trigger and resets the publication
                    # fence. The status/hash-only statement below stamps the reconciled bytes.
                    cursor.execute(
                        'UPDATE "JobAsset" SET "filePath" = %s, "fileSizeBytes" = %s '
                        'WHERE "id" = %s AND "filePath" = %s AND "updatedAt" = %s RETURNING "id"',
                        (
                            result.registered_result_path, result.result_size, asset.id,
                            asset.file_path, asset.updated_at,
                        ),
                    )
                else:
                    # Keep non-paying and already-canonical registrations stable while still
                    # taking a row lock and checking the exact enumeration token.
                    cursor.execute(
                        'SELECT "id" FROM "JobAsset" WHERE "id" = %s AND "filePath" = %s '
                        'AND "updatedAt" = %s FOR UPDATE',
                        (asset.id, asset.file_path, asset.updated_at),
                    )
                if cursor.fetchone() is None:
                    self.connection.rollback()
                    conflict = Result(
                        result.path, "conflict", "JobAsset row changed before compare-and-swap",
                        asset=asset, source_sha256=result.source_sha256,
                        result_path=result.result_path,
                        registered_result_path=result.registered_result_path,
                        result_sha256=result.result_sha256, sections=result.sections,
                        replacements=result.replacements, safe_copy=result.safe_copy,
                    )
                    with self.connection.cursor() as audit_cursor:
                        self._insert_item(audit_cursor, run_id, conflict, conflict.status)
                    self.connection.commit()
                    return conflict
                cursor.execute(
                    'UPDATE "JobAsset" SET "commercialCopyStatus" = %s, '
                    '"commercialCopySha256" = %s, "commercialCopyCheckedAt" = CURRENT_TIMESTAMP '
                    'WHERE "id" = %s',
                    (publication_status, result.result_sha256, asset.id),
                )
                self._insert_item(cursor, run_id, result, result.status)
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            raise
        finally:
            self.connection.autocommit = True

    def reconcile_chat(
        self,
        run_id: str,
        replacements: dict[str, tuple[tuple[str, str], ...]],
        safe_copy: dict[str, str],
        eligible_job_ids: set[str],
    ) -> dict[str, int]:
        counts = {"changed": 0, "unchanged": 0, "conflict": 0}
        for job_id in sorted(eligible_job_ids):
            with self.connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "id", "content" FROM "ChatMessage" '
                    'WHERE "jobId" = %s AND "role" = \'assistant\' ORDER BY "createdAt"',
                    (job_id,),
                )
                messages = cursor.fetchall()
            for message in messages:
                before = message["content"]
                safe = safe_copy.get(job_id)
                after = (
                    _reconcile_chat_content(before, replacements.get(job_id, ()), safe)
                    if safe is not None
                    else before
                )
                status = "unchanged"
                self.connection.autocommit = False
                try:
                    with self.connection.cursor() as cursor:
                        if after != before:
                            cursor.execute(
                                'UPDATE "ChatMessage" SET "content" = %s '
                                'WHERE "id" = %s AND "content" = %s RETURNING "id"',
                                (after, message["id"], before),
                            )
                            status = "changed" if cursor.fetchone() else "conflict"
                        cursor.execute(
                            'INSERT INTO "CommercialCopyBackfillItem" '
                            '("runId", "targetKind", "targetId", "jobId", "sourceSha256", '
                            '"resultSha256", "status", "reason", "sectionResults") '
                            'VALUES (%s, \'CHAT_MESSAGE\', %s, %s, %s, %s, %s, %s, %s::jsonb)',
                            (
                                run_id, message["id"], job_id,
                                hashlib.sha256(before.encode()).hexdigest(),
                                hashlib.sha256(after.encode()).hexdigest(), status,
                                "content changed before compare-and-swap" if status == "conflict" else None,
                                json.dumps({"commercial_copy": {"status": status}}),
                            ),
                        )
                    self.connection.commit()
                    counts[status] += 1
                except Exception:
                    self.connection.rollback()
                    raise
                finally:
                    self.connection.autocommit = True
        return counts

    def complete_run(self, run_id: str, counts: dict[str, int], chat_counts: dict[str, int]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'UPDATE "CommercialCopyBackfillRun" SET "status" = \'COMPLETED\', '
                '"completedAt" = CURRENT_TIMESTAMP, "authoritativeAssets" = %s, '
                '"assetsChanged" = %s, "assetsUnchanged" = %s, "assetsNotPaying" = %s, '
                '"assetsPartial" = %s, "assetsSkipped" = %s, "assetsConflicted" = %s, '
                '"chatChanged" = %s, "chatUnchanged" = %s, "chatConflicted" = %s '
                'WHERE "id" = %s',
                (
                    counts["authoritative"], counts["changed"], counts["unchanged"],
                    counts["not_paying"], counts["partial"], counts["skipped"],
                    counts["conflict"], chat_counts["changed"], chat_counts["unchanged"],
                    chat_counts["conflict"], run_id,
                ),
            )

    def fail_run(self, run_id: str, error: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'UPDATE "CommercialCopyBackfillRun" SET "status" = \'FAILED\', '
                '"completedAt" = CURRENT_TIMESTAMP, "error" = %s WHERE "id" = %s',
                (error, run_id),
            )


def _print_results(results: list[Result], *, authoritative: bool = False) -> None:
    for result in results:
        prefix = f"asset={result.asset.id} job={result.asset.job_id} " if result.asset else ""
        detail = f": {result.detail}" if result.detail else ""
        print(f"{result.status.upper()} {prefix}{result.path}{detail}")
    statuses = ("changed", "would-change", "unchanged", "not_paying", "partial", "skipped", "conflict")
    counts = {status: sum(result.status == status for result in results) for status in statuses}
    source = " authoritative=JobAsset" if authoritative else ""
    print(
        "SUMMARY "
        + " ".join(f"{status}={count}" for status, count in counts.items() if count)
        + f" scanned={len(results)}{source}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Local asset file(s) or directories")
    parser.add_argument("--dry-run", action="store_true", help="Report local changes without writing")
    parser.add_argument("--database-url", help="Run the mandatory JobAsset-backed migration")
    parser.add_argument(
        "--asset-root", type=Path,
        default=Path(os.environ.get("ASSET_ROOT") or Path(os.environ.get("OUTPUT_DIR", "output")).parent),
        help="Allowed root used to resolve relative JobAsset paths",
    )
    args = parser.parse_args()

    if args.database_url:
        if args.paths or args.dry_run:
            parser.error("database mode does not accept paths or --dry-run")
        repository = PostgresBackfillRepository(args.database_url)
        try:
            results, chat_counts = run_authoritative_backfill(repository, args.asset_root)
        finally:
            repository.close()
        _print_results(results, authoritative=True)
        print("CHAT " + " ".join(f"{key}={value}" for key, value in chat_counts.items()))
        return 0

    if not args.paths:
        parser.error("provide paths or --database-url")
    results = [backfill(path, dry_run=args.dry_run) for path in _asset_paths(args.paths)]
    _print_results(results)
    return 1 if any(result.status in {"skipped", "conflict"} for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
