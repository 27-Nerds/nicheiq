"""Buyer-job family partition over validated pain points (docs/DIVERSITY_DECISION_2026-08.md).

WHY: idea pools collapse into ~3 buyer-job families because cell allocation has no family key —
themes and pains are the only spreading keys, and several themes routinely describe *the same
buyer doing the same job*. Raising the generator budget bought more themes and zero new families
(9 generators / 6 pain cells still produced 3 families), which is what makes an explicit family
key load-bearing rather than optional.

CONTRACT (deliberate, from the decision doc):
  - The partition is over **stable pain ids** (the pain TITLE, which the DB already enforces
    unique per job) — free-text family labels are NEVER used as equality keys.
  - Every pain lands in exactly one family: this is a validated PARTITION, not a tagging pass.
    Pains the labeler forgot become their own family (`inferred=True`) rather than vanishing.
  - ONE structured LLM call per run. Fail-soft: on any failure we fall back to the theme key
    that allocation uses today AND record the degradation (`degraded=True`) so telemetry can
    never present a degraded run as if families were computed.

The grouping wording is anchored on the phrasing already proven in
`unified_solution_crew._group_variant_overlaps` ("same buyer, same job, overlapping value;
different mechanisms do NOT make them different products").
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from .slugify import slugify

logger = logging.getLogger(__name__)

# Cap on the number of families the labeler may emit. The allocator spends a fixed cell budget
# (~6-9); beyond that a family can never receive a cell, so more families would only inflate the
# "uncovered" ledger. Overflow is MERGED (never dropped) so the partition stays complete.
MAX_FAMILIES = 6

_UNASSIGNED_LABEL = "Other buyer jobs"


def content_id(label: str, member_pain_ids) -> str:
    """A family id derived only from CONTENT — never from position in a list.

    `family_id` outlives the call that minted it: it is persisted, reused by later regenerate/
    seed batches (`partition_from_dict`) and used as the thesis identity in the UI. A positional
    id ("family_3") would silently rebind to a different buyer job the moment a batch produced a
    different number of families, merging unrelated ideas under one thesis. Label slug first
    (readable); the member-pain digest is the fallback when there is no usable label.
    """
    base = slugify(label or "")[:40]
    if base:
        return base
    digest = hashlib.sha256(
        "\n".join(sorted((p or "").strip() for p in member_pain_ids or [])).encode("utf-8")
    ).hexdigest()[:10]
    return f"job-{digest}"


def pain_id(pain) -> str:
    """Stable per-run identity of a pain point: its title.

    `CatalogPainPoint` is `@@unique([sourceJobId, title])` and Task-3 scoring already matches by
    title, so the title is the identity the whole pipeline agrees on. Normalized (stripped) only
    — never lowercased, because callers round-trip it back to `PainPoint.title`.
    """
    return (getattr(pain, "title", "") or "").strip()


@dataclass(frozen=True)
class BuyerJobFamily:
    """One buyer-job family: who buys, what job triggers the purchase, whose budget it comes out
    of, and which validated pains belong to it."""

    family_id: str
    buyer: str
    triggering_job: str
    economic_outcome: str
    member_pain_ids: tuple[str, ...]
    display_label: str
    inferred: bool = False  # not produced by the labeler (leftover/overflow repair)

    def to_dict(self) -> dict:
        return {
            "family_id": self.family_id,
            "buyer": self.buyer,
            "triggering_job": self.triggering_job,
            "economic_outcome": self.economic_outcome,
            "display_label": self.display_label,
            "member_pain_ids": list(self.member_pain_ids),
            "inferred": self.inferred,
        }


@dataclass(frozen=True)
class BuyerJobPartition:
    """A complete, validated partition of the run's validated pains into buyer-job families."""

    families: tuple[BuyerJobFamily, ...]
    by_pain: dict = field(default_factory=dict)  # pain_id -> family_id
    source: str = "llm"                          # "llm" | "theme_fallback"
    degraded: bool = False
    degradation_reason: str | None = None

    def family_for(self, pid: str) -> str | None:
        return self.by_pain.get((pid or "").strip())

    def family_for_pain(self, pain) -> str | None:
        return self.family_for(pain_id(pain))

    def label_for(self, family_id: str) -> str:
        for f in self.families:
            if f.family_id == family_id:
                return f.display_label
        return family_id

    @property
    def family_ids(self) -> list[str]:
        return [f.family_id for f in self.families]

    def to_telemetry(self) -> dict:
        return {
            "source": self.source,
            "degraded": self.degraded,
            "degradation_reason": self.degradation_reason,
            "families": [f.to_dict() for f in self.families],
        }


# ---------------------------------------------------------------------------
# Fallback (no LLM): today's key
# ---------------------------------------------------------------------------

def theme_fallback_partition(pains: list, *, reason: str | None = None) -> BuyerJobPartition:
    """The key allocation uses TODAY — `parent_theme_id`, with theme-less pains standing alone.

    Returned whenever the labeler is unavailable or fails. Always `degraded=True`: a theme is not
    a buyer job, and a run that silently substituted one for the other would misreport coverage.
    """
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    themes: dict[str, str] = {}
    for p in pains or []:
        pid = pain_id(p)
        if not pid:
            continue
        theme = getattr(p, "parent_theme_id", None) or ""
        key = f"theme:{theme}" if theme else f"pain:{slugify(pid) or pid}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
            themes[key] = theme
        buckets[key].append(pid)

    families: list[BuyerJobFamily] = []
    by_pain: dict[str, str] = {}
    for key in order:
        members = tuple(buckets[key])
        # Content-derived, never positional — see `content_id`. The theme id IS the bucket's
        # identity here, so it is the readable label to slug.
        fid = content_id(themes.get(key) or "", members)
        families.append(BuyerJobFamily(
            family_id=fid, buyer="", triggering_job="", economic_outcome="",
            member_pain_ids=members, display_label=members[0][:70], inferred=True))
        for pid in members:
            by_pain[pid] = fid
    return BuyerJobPartition(
        families=tuple(families), by_pain=by_pain, source="theme_fallback",
        degraded=True, degradation_reason=reason or "buyer-job labeler unavailable")


# ---------------------------------------------------------------------------
# Validation / repair
# ---------------------------------------------------------------------------

def _validate_partition(raw_families: list[dict], pains: list) -> tuple[list[BuyerJobFamily], dict]:
    """Turn the labeler's raw groups into a complete partition over the run's pain ids.

    Repairs, in order: unknown ids dropped · duplicate ids keep their FIRST family · empty
    families dropped · pains the labeler never mentioned become their own `inferred` family ·
    overflow past `MAX_FAMILIES` merged into one `inferred` residual family (merged, never
    dropped — a dropped pain would leave the "partition" incomplete and silently un-allocatable).
    """
    valid_ids = [pain_id(p) for p in pains if pain_id(p)]
    valid_set = set(valid_ids)
    claimed: set[str] = set()
    families: list[BuyerJobFamily] = []
    used_slugs: set[str] = set()

    for raw in raw_families:
        members = []
        for pid in raw.get("member_pain_ids") or []:
            pid = (pid or "").strip()
            if pid in valid_set and pid not in claimed:
                members.append(pid)
                claimed.add(pid)
        if not members:
            continue
        label = (raw.get("display_label") or raw.get("triggering_job") or "").strip()
        base = content_id(label, members)
        fid = base
        n = 2
        while fid in used_slugs:
            fid = f"{base}-{n}"
            n += 1
        used_slugs.add(fid)
        families.append(BuyerJobFamily(
            family_id=fid,
            buyer=(raw.get("buyer") or "").strip(),
            triggering_job=(raw.get("triggering_job") or "").strip(),
            economic_outcome=(raw.get("economic_outcome") or "").strip(),
            member_pain_ids=tuple(members),
            display_label=label or members[0][:70],
        ))

    repairs = {"labeler_families": len(families), "unassigned_pains": 0, "overflow_merged": 0}

    leftovers = [pid for pid in valid_ids if pid not in claimed]
    for pid in leftovers:
        base = content_id(pid, (pid,))
        fid = base
        n = 2
        while fid in used_slugs:
            fid = f"{base}-{n}"
            n += 1
        used_slugs.add(fid)
        families.append(BuyerJobFamily(
            family_id=fid, buyer="", triggering_job="", economic_outcome="",
            member_pain_ids=(pid,), display_label=pid[:70], inferred=True))
    repairs["unassigned_pains"] = len(leftovers)

    if len(families) > MAX_FAMILIES:
        # Keep the biggest families intact; fold the tail into ONE residual family so every pain
        # still has a home. This can only LOWER the measured family count — never inflate it.
        families.sort(key=lambda f: (-len(f.member_pain_ids), f.family_id))
        keep, tail = families[: MAX_FAMILIES - 1], families[MAX_FAMILIES - 1:]
        merged_ids = tuple(pid for f in tail for pid in f.member_pain_ids)
        keep.append(BuyerJobFamily(
            family_id="other-buyer-jobs", buyer="", triggering_job="", economic_outcome="",
            member_pain_ids=merged_ids, display_label=_UNASSIGNED_LABEL, inferred=True))
        repairs["overflow_merged"] = len(tail)
        families = keep

    return families, repairs


def _build_partition(families: list[BuyerJobFamily], source: str) -> BuyerJobPartition:
    by_pain = {pid: f.family_id for f in families for pid in f.member_pain_ids}
    return BuyerJobPartition(families=tuple(families), by_pain=by_pain, source=source)


# ---------------------------------------------------------------------------
# Reuse across batches (regenerate / seed / resume) — NEVER re-partition
# ---------------------------------------------------------------------------

def partition_from_dict(data) -> BuyerJobPartition | None:
    """Rehydrate a persisted partition (`to_telemetry()` output). None when there is none.

    WHY this exists: `run_regenerate_ideas` / `run_seed_idea` build a FRESH crew whose
    `_buyer_job_partition` starts as None, so without rehydration each batch would compute its
    OWN partition and stamp its ideas with family ids from a different labeling of the same
    pains — one buyer job splitting into two theses, or two jobs colliding on one id. The
    partition is a per-JOB fact, not a per-batch one: compute once, reuse forever.

    A DEGRADED persisted partition is not rehydrated — it was the theme fallback, and a later
    batch deserves a real labeler attempt rather than inheriting the degradation.
    """
    if not isinstance(data, dict):
        return None
    if data.get("degraded"):
        return None
    families: list[BuyerJobFamily] = []
    for raw in data.get("families") or []:
        members = tuple((p or "").strip() for p in (raw.get("member_pain_ids") or []) if (p or "").strip())
        fid = (raw.get("family_id") or "").strip()
        if not fid or not members:
            continue
        families.append(BuyerJobFamily(
            family_id=fid,
            buyer=raw.get("buyer") or "",
            triggering_job=raw.get("triggering_job") or "",
            economic_outcome=raw.get("economic_outcome") or "",
            member_pain_ids=members,
            display_label=raw.get("display_label") or members[0][:70],
            inferred=bool(raw.get("inferred")),
        ))
    if not families:
        return None
    return _build_partition(families, source=data.get("source") or "llm")


def extend_partition(partition: BuyerJobPartition, pains: list) -> BuyerJobPartition:
    """Incrementally admit pains the persisted partition has never seen — no LLM, no re-labeling.

    Every existing family keeps its id and members verbatim; a genuinely new pain becomes its own
    `inferred` family. This is what keeps a later batch's ideas addressable at all without
    re-partitioning (which would move existing pains between families and break thesis identity).
    """
    known = set(partition.by_pain)
    used = {f.family_id for f in partition.families}
    added: list[BuyerJobFamily] = []
    for p in pains or []:
        pid = pain_id(p)
        if not pid or pid in known:
            continue
        known.add(pid)
        fid = content_id(pid, (pid,))
        n = 2
        while fid in used:
            fid = f"{content_id(pid, (pid,))}-{n}"
            n += 1
        used.add(fid)
        added.append(BuyerJobFamily(
            family_id=fid, buyer="", triggering_job="", economic_outcome="",
            member_pain_ids=(pid,), display_label=pid[:70], inferred=True))
    if not added:
        return partition
    logger.info(f"[BuyerJobs] extended persisted partition with {len(added)} new-pain families")
    return _build_partition(list(partition.families) + added, source=partition.source)


# ---------------------------------------------------------------------------
# The one structured call
# ---------------------------------------------------------------------------

_PROMPT_HEAD = (
    "You are partitioning a niche's validated pain points into BUYER-JOB FAMILIES.\n\n"
    "Two pains belong to the SAME family when the same buyer, doing the same job, would pay "
    "one vendor to make both go away — same buyer, same triggering job, overlapping value. "
    "Different mechanisms do NOT make them different families. Different job, different budget "
    "owner, or a different person signing off => different family.\n\n"
)

_PROMPT_TAIL = (
    "\nReturn at most {max_families} families. Every pain id listed above must appear in exactly "
    "one family — never invent an id, never repeat one. For each family give:\n"
    "  buyer            — the role who pays (not a demographic)\n"
    "  triggering_job    — the job that makes them go looking, <=15 words\n"
    "  economic_outcome — whose budget it comes out of and what it buys, <=15 words\n"
    "  display_label     — <=6 words, human-readable\n"
    "  member_pain_ids   — the exact pain id strings from the list above\n"
    "Return JSON."
)


def classify_buyer_job_families(
    pains: list,
    *,
    theme_categories: list | None = None,
    niche: str = "",
    model_name: str | None = None,
    cost_tracker=None,
    cost_label: str = "Stage 5 - Buyer Job Families",
    timeout: int = 120,
) -> BuyerJobPartition:
    """ONE structured call partitioning `pains` into buyer-job families.

    Never raises: any failure (too few pains, LLM error, empty result) returns
    `theme_fallback_partition(...)` with `degraded=True` and a reason string.
    """
    usable = [p for p in (pains or []) if pain_id(p)]
    if len(usable) < 2:
        return theme_fallback_partition(usable, reason="fewer than 2 identifiable pains")

    try:
        from pydantic import BaseModel, Field as _F

        from ..config.settings import settings
        from .llm_service import LLMService

        class _Family(BaseModel):
            buyer: str = _F("", description="the role who pays")
            triggering_job: str = _F("", description="the job that triggers the purchase, <=15 words")
            economic_outcome: str = _F("", description="whose budget, buying what, <=15 words")
            display_label: str = _F("", description="<=6 words")
            member_pain_ids: list[str] = _F(default_factory=list,
                                            description="exact pain id strings from the list")

        class _Families(BaseModel):
            families: list[_Family] = _F(default_factory=list)

        lines = "\n".join(
            f"- id: {pain_id(p)}\n  detail: {(getattr(p, 'description', '') or '')[:180]}"
            for p in usable
        )
        theme_block = ""
        themes = [t for t in (theme_categories or []) if getattr(t, "category_name", None)]
        if themes:
            theme_block = (
                "\nThe research themes these pains were extracted under (context only — themes "
                "are NOT buyer jobs; several themes often describe one buyer doing one job):\n"
                + "\n".join(f"- {getattr(t, 'category_name', '')}: "
                            f"{(getattr(t, 'definition', '') or '')[:120]}" for t in themes[:12])
            )
        prompt = (
            _PROMPT_HEAD
            + (f"NICHE: {niche}\n\n" if niche else "")
            + f"VALIDATED PAIN POINTS:\n{lines}\n{theme_block}\n"
            + _PROMPT_TAIL.format(max_families=MAX_FAMILIES)
        )

        result, usage = LLMService.invoke_structured(
            prompt=prompt, output_model=_Families, temperature=0, timeout=timeout,
            model_name=model_name or settings.report_structured_llm,
            reasoning_effort="none")
        if cost_tracker is not None and usage is not None:
            try:
                cost_tracker.record_llm_usage(cost_label, usage.to_dict())
            except Exception as e:  # noqa: BLE001 — accounting must never break the run
                logger.warning(f"[BuyerJobs] cost record skipped: {str(e)[:80]}")

        raw = [{
            "buyer": f.buyer, "triggering_job": f.triggering_job,
            "economic_outcome": f.economic_outcome, "display_label": f.display_label,
            "member_pain_ids": f.member_pain_ids,
        } for f in (result.families or [])]
        if not raw:
            return theme_fallback_partition(usable, reason="labeler returned no families")

        families, repairs = _validate_partition(raw, usable)
        if not families:
            return theme_fallback_partition(usable, reason="no family survived validation")
        partition = _build_partition(families, source="llm")
        logger.info(
            f"[BuyerJobs] {len(families)} families over {len(usable)} pains "
            f"(labeler={repairs['labeler_families']}, unassigned_repaired="
            f"{repairs['unassigned_pains']}, overflow_merged={repairs['overflow_merged']}): "
            + "; ".join(f"{f.display_label}[{len(f.member_pain_ids)}]" for f in families))
        return partition
    except Exception as e:  # noqa: BLE001 — fail-soft by contract
        logger.warning(f"[BuyerJobs] classification failed, falling back to theme key: {str(e)[:160]}")
        return theme_fallback_partition(usable, reason=f"labeler error: {str(e)[:120]}")
