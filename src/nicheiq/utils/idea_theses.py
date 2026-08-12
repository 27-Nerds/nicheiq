"""Thesis-level portfolio partition — one card per product THESIS, variants nested beneath.

WHY (docs/DIVERSITY_DECISION_2026-08.md, "Presentation: necessary, but NOT nearly free"):
the pipeline presents N ideas as N independent opportunities while the pool actually collapses
into a handful of buyer-job families (measured: 12 ideas -> 3 families). The existing
`_group_variant_overlaps` output (`idea_overlap_groups`) cannot carry that IA: it emits only
groups of 2+, runs post-refinement, has ACCEPTED merges removed from it, and its persisted
contract represents *rejected/unmerged* variants. This module builds the COMPLETE partition
instead — every visible idea lands in exactly one thesis or in an explicit `unassigned` bucket.

CONTRACT:
  - Grouping key is the run's `BuyerJobPartition` (utils/buyer_jobs.py) over stable pain ids.
    No new LLM call is made here — every field is a DETERMINISTIC rollup of signals already
    stamped on the ideas / on the allocation telemetry.
  - `uncovered_families` is the honesty half of the contract: validated buyer-job families with
    NO surviving idea, with the reason separated into "no idea was ever drafted here" vs "one
    was drafted and nothing survived" (docs: "a visible 'validated families not represented
    by a surviving concept' section"). `reason` is the enum for code; `reason_detail` is the
    sentence a user reads and carries no pipeline vocabulary.
  - No partition => `{}` (the caller persists nothing and the UI keeps the flat list). A thesis
    IA built on the theme fallback would claim buyer-job identity the run never computed.
"""

from __future__ import annotations

import logging
import re

from ..models.solution_idea import effective_red_team_state, visible_ideas
from ..validators.report_consistency import parse_stamp_vendor
from .calibration_notes import strip_markdown_emphasis

logger = logging.getLogger(__name__)

# Parity stamps whose "vendor" is not a vendor. `shipped by evidence:` / `bundled_free
# (red-team):` are ADVERSARIAL findings written by the red-team pass (utils/red_team_review.py),
# not parity claims naming a product — treating them as incumbents would invent a competitor.
_NON_VENDOR_TOKENS = frozenset({"evidence", "red-team", "red team", "redteam", "unknown", ""})

_NO_INCUMBENT = "none found"

# Data-source phrasings that mean "the customer brings the data" — i.e. the product has nothing
# until a buyer hands over their own export. That is a cold-start assumption, not a data route.
# Suffix forms generalize across niches (user-submitted / clinic-supplied / customer-provided).
_COLD_START_MARKERS = (
    "-submitted", " submitted", "-supplied", " supplied", "-provided", " provided",
    "-entered", " entered", "-maintained", " maintained", "-contributed", " contributed",
    "user-", "self-reported", "crowdsourced", "crowd-sourced", "first-party",
    "manual ", "manually",
)

# Data-access labels that mean the route was NOT confirmed by the verifier
# (crews/idea_improvement_loop_v4.py: 'unverified' = never confirmed, 'blocked' = refuted).
# Values are the USER-FACING clause; the keys stay the internal enum.
_UNVERIFIED_ROUTES = {
    "unverified": "we could not confirm the data this product needs is actually available",
    "blocked": "we checked and the data this product needs is not available on the terms it assumes",
}

# Display budget for the thesis card. Ordered by signal strength (red-team kill first), so the
# truncated tail is always the weakest evidence.
MAX_FATAL_ASSUMPTIONS = 8


def _get(obj, field, default=None):
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _norm(text) -> str:
    """Loose title key: casefolded, punctuation-stripped, whitespace-collapsed.

    Used ONLY as a second pass after exact matching — `pain_points_addressed` is LLM-written
    and routinely differs from the validated `PainPoint.title` by a hyphen or a trailing word.
    """
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").strip().casefold()).strip()


def _family_lookup(partition):
    """(exact, normalized) pain-id -> family_id maps for the run's partition."""
    exact = dict(partition.by_pain or {})
    loose: dict[str, str] = {}
    for pid, fid in exact.items():
        key = _norm(pid)
        # First writer wins: a collision means two pains normalize the same, and picking either
        # is a coin flip — keep it deterministic (partition order) rather than dict-order.
        if key and key not in loose:
            loose[key] = fid
    return exact, loose


# ---------------------------------------------------------------------------
# Assignment: visible idea -> family
# ---------------------------------------------------------------------------

def _match_family(title, exact: dict, loose: dict) -> str | None:
    t = (title or "").strip()
    if not t:
        return None
    return exact.get(t) or loose.get(_norm(t))


def _assign_family(idea, exact: dict, loose: dict, by_name: dict) -> tuple[str | None, str]:
    """Map ONE visible idea to a family id. Returns (family_id | None, how).

    Order, cheapest/most-authoritative first:
      1. `source_pain` — CODE-stamped from the generating cell; the real provenance.
      2. `merged_from` — an `idea_tier='merged'` synthesis inherits the family of the variants
         it absorbed (they carry real cell provenance; the synthesis often doesn't).
      3. `pain_points_addressed` — the fallback for frame-born (gap/data_asset/workflow),
         bundles and salvage, none of which carry a `source_pain`. Majority vote over the
         validated pains the idea claims; ties break toward the FIRST claimed pain, which is the
         generator's own ordering (bundles list their anchor pain first).
    No LLM call at any step. Unmatched => (None, reason) and the caller buckets it.
    """
    fam = _match_family(_get(idea, "source_pain"), exact, loose)
    if fam:
        return fam, "source_pain"

    merged_from = _get(idea, "merged_from") or []
    if merged_from:
        votes: dict[str, int] = {}
        for name in merged_from:
            member = by_name.get((name or "").strip())
            if member is None:
                continue
            mfam = _match_family(_get(member, "source_pain"), exact, loose)
            if not mfam:
                mfam, _ = _assign_family_from_pains(member, exact, loose)
            if mfam:
                votes[mfam] = votes.get(mfam, 0) + 1
        if votes:
            return max(votes.items(), key=lambda kv: (kv[1], -list(votes).index(kv[0])))[0], "merged_from"

    fam, how = _assign_family_from_pains(idea, exact, loose)
    if fam:
        return fam, how
    return None, "no validated pain matched (source_pain, merged_from, pain_points_addressed)"


def _assign_family_from_pains(idea, exact: dict, loose: dict) -> tuple[str | None, str]:
    votes: dict[str, int] = {}
    order: list[str] = []
    for title in _get(idea, "pain_points_addressed") or []:
        fam = _match_family(title, exact, loose)
        if not fam:
            continue
        if fam not in votes:
            order.append(fam)
        votes[fam] = votes.get(fam, 0) + 1
    if not votes:
        return None, ""
    return max(order, key=lambda f: (votes[f], -order.index(f))), "pain_points_addressed"


# ---------------------------------------------------------------------------
# Rollups (deterministic — every input is already stamped on the idea)
# ---------------------------------------------------------------------------

def _named_vendor(stamp) -> tuple[str, str] | None:
    """(class, vendor) for a parity stamp that NAMES a vendor, else None."""
    parsed = parse_stamp_vendor(stamp)
    if not parsed:
        return None
    klass, vendor = parsed
    if vendor.strip().casefold() in _NON_VENDOR_TOKENS:
        return None
    return klass, vendor.strip()


def _incumbent_rollup(members) -> tuple[str, list[str]]:
    """Thesis-level incumbent status + the vendors it rests on.

    any shipped/bundled_free WITH a named vendor -> occupied
    else any partial/substitute WITH a named vendor -> partial
    else every stamped member says 'none found' -> open
    else (vendor-less stamps, free text, or nothing probed) -> unknown
    """
    stamps = [(_get(m, "incumbent_parity") or "").strip() for m in members]
    stamps = [s for s in stamps if s]
    occupied: list[str] = []
    partial: list[str] = []
    for s in stamps:
        named = _named_vendor(s)
        if not named:
            continue
        klass, vendor = named
        bucket = occupied if klass in ("shipped", "bundled_free") else partial
        if vendor not in bucket:
            bucket.append(vendor)
    if occupied:
        return "occupied", occupied + [v for v in partial if v not in occupied]
    if partial:
        return "partial", partial
    if stamps and all(s.casefold().startswith(_NO_INCUMBENT) for s in stamps):
        return "open", []
    return "unknown", []


def _member_row(idea) -> dict:
    """One variant under a thesis.

    `winning_angle` rides at VARIANT level and is deliberately NOT rolled up: the GTM lens
    (vertical_workflow | distribution_seo | novel_differentiation) is orthogonal to the buyer job
    — two variants of the same product can be sold through different angles, so a thesis-level
    angle would be a fabricated consensus. `name` is the join key back to the full idea the
    detail overlay already renders; `idea_tier`/`source_frame` are birth provenance (single /
    salvaged / bundle / merged, pain / gap / data_asset / workflow) so the nested list can label
    a variant without a second lookup.
    """
    return {
        "name": _get(idea, "solution_name") or "",
        "winning_angle": _get(idea, "winning_angle"),
        "idea_tier": _get(idea, "idea_tier") or "single",
        "source_frame": _get(idea, "source_frame") or "pain",
    }


def _cold_start_sources(idea) -> list[str]:
    out = []
    for src in _get(idea, "data_sources") or []:
        low = (src or "").casefold()
        if any(marker in low for marker in _COLD_START_MARKERS):
            out.append(src)
    return out


def _fatal_assumptions(members) -> list[dict]:
    """DETERMINISTIC rollup of the kill-signals already stamped on this thesis's members.

    Every entry names the `source_field` it came from so the UI can attribute the claim instead
    of asserting it in NicheIQ's own voice. No LLM call — these are the run's own findings.

    `source_field` is a MACHINE key (the frontend maps it to a label); every `assumption`
    string must therefore stand on its own, naming what found the problem in plain English and
    carrying no internal enum token (live audit 2026-08).
    """
    out: list[dict] = []

    def add(idea, source_field: str, assumption: str) -> None:
        assumption = " ".join(strip_markdown_emphasis(assumption or "").split())
        if not assumption:
            return
        out.append({
            "idea_name": _get(idea, "solution_name") or "",
            "source_field": source_field,
            "assumption": assumption[:400],
        })

    for m in members:
        if effective_red_team_state(m)[0] == "killed":
            caveats = _get(m, "red_team_caveats") or []
            # User-facing string: the UI calls this state "Premise unproven"
            # (frontend/src/lib/utils/adversarialReview.ts PREMISE_UNPROVEN_LABEL).
            # "killed" is the internal verdict value and must not reach a chip.
            add(m, "red_team_verdict",
                caveats[0] if caveats
                else "The adversarial review could not find evidence for this concept's premise.")
    for m in members:
        route = (_get(m, "data_access_model") or "").strip().casefold()
        if route in _UNVERIFIED_ROUTES:
            # The raw route token ('unverified' / 'blocked') is an internal label — the
            # clause it maps to already says the same thing in English.
            add(m, "data_access_model",
                f"{_UNVERIFIED_ROUTES[route]} — the concept assumes access it has not "
                f"demonstrated.")
    for m in members:
        if _get(m, "audience_fit") is False:
            add(m, "audience_fit",
                "Serves an adjacent audience, not the stated target audience.")
    for m in members:
        # Stamped on the SolutionScores at keyword-validation time; absent (False) during Phase 1.
        if _get(m, "demand_unmeasured") is True:
            add(m, "demand_unmeasured",
                "No keyword survived validation — search demand for this concept is unmeasured, "
                "not measured-and-low.")
    for m in members:
        cold = _cold_start_sources(m)
        if cold:
            add(m, "data_sources",
                "Cold start: the product has no data until a customer supplies it — "
                + "; ".join(cold[:3]))
    for m in members:
        constraint = _get(m, "refine_binding_constraint")
        if constraint:
            add(m, "refine_binding_constraint", constraint)

    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for row in out:
        key = (row["source_field"], row["assumption"].casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped[:MAX_FATAL_ASSUMPTIONS]


# ---------------------------------------------------------------------------
# Uncovered families
# ---------------------------------------------------------------------------

#: Plain-English rendering of the allocator's own uncovered-reason enum
#: (unified_solution_crew._allocation_telemetry). The enum stays machine-readable on the
#: telemetry; only this string is read by a person, so it never names the allocator, a
#: "cell", or a raw token (live audit 2026-08: "the allocator never spent a cell here
#: (budget_exhausted)" shipped to the UI verbatim).
_NO_CELL_REASON_TEXT = {
    "budget_exhausted": "we ran out of idea budget before reaching this job",
    "frame_displacement": (
        "the idea budget went to other angles on this niche before reaching this job"),
    "no_allocatable_pain": (
        "none of this job's validated pains were concrete enough to build an idea on"),
}
_NO_CELL_REASON_FALLBACK = "this job was not reached before the idea budget ran out"


def _uncovered_reason(family_id: str, cell_allocation: dict) -> tuple[str, str]:
    """"no cell allocated" vs "cell allocated but no idea survived", per the days-3/4 telemetry.

    Returns (machine-readable `reason` enum, human sentence). The enum is the code contract;
    the sentence is shown to the user, so it carries no pipeline vocabulary.
    """
    if not cell_allocation:
        return "unknown", "we could not determine why this job has no idea in this run"
    if (cell_allocation.get("cells_by_family") or {}).get(family_id):
        return "no_surviving_idea", (
            "we drafted at least one idea for this job, but no concept survived the review bar")
    for row in cell_allocation.get("families_uncovered") or []:
        if row.get("family_id") == family_id:
            detail = _NO_CELL_REASON_TEXT.get(
                (row.get("reason") or "").strip().casefold(), _NO_CELL_REASON_FALLBACK)
            return "no_cell_allocated", f"no idea was drafted for this job — {detail}"
    return "no_cell_allocated", "no idea was drafted for this job in this run"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_idea_theses(ideas: list, *, partition, cell_allocation: dict | None = None) -> dict:
    """The run's thesis partition over the VISIBLE idea pool. Never raises, never calls an LLM.

    Returns `{}` when there is no buyer-job partition (unit tests / legacy runs / classifier
    degradation): a thesis IA keyed on the theme fallback would present theme identity as buyer-
    job identity, which is exactly the conflation the family key exists to remove.
    """
    if partition is None or not getattr(partition, "families", None):
        return {}
    if getattr(partition, "degraded", False):
        logger.info("[IdeaTheses] skipped — buyer-job partition degraded "
                    f"({partition.degradation_reason})")
        return {}

    pool = visible_ideas(ideas or [])
    exact, loose = _family_lookup(partition)
    by_name = {(_get(i, "solution_name") or "").strip(): i for i in (ideas or [])}

    members_by_family: dict[str, list] = {}
    unassigned: list[dict] = []
    for idea in pool:
        fam, how = _assign_family(idea, exact, loose, by_name)
        if fam:
            members_by_family.setdefault(fam, []).append(idea)
        else:
            unassigned.append({"idea_name": _get(idea, "solution_name") or "", "reason": how})

    # Lead idea = best member by the SAME angle-aware composite the preview grid ranks on
    # (utils/score_helpers.angle_ranked_composite), with the pool's audience-fit coverage so the
    # adjacent-audience penalty matches. Name tie-break keeps it deterministic.
    from .score_helpers import angle_ranked_composite, audience_fit_coverage
    coverage = audience_fit_coverage(pool)

    def _rank_key(idea):
        try:
            score = angle_ranked_composite(idea, coverage)
        except Exception:  # noqa: BLE001 — a malformed idea must not lose its whole thesis
            score = 0.0
        return (-score, (_get(idea, "solution_name") or "").strip().casefold())

    theses: list[dict] = []
    uncovered: list[dict] = []
    for family in partition.families:
        members = members_by_family.get(family.family_id) or []
        if not members:
            reason, detail = _uncovered_reason(family.family_id, cell_allocation or {})
            uncovered.append({
                "family_id": family.family_id,
                "display_label": family.display_label,
                "member_pain_ids": list(family.member_pain_ids),
                "reason": reason,
                "reason_detail": detail,
            })
            continue
        members = sorted(members, key=_rank_key)
        status, vendors = _incumbent_rollup(members)
        theses.append({
            "family_id": family.family_id,
            "display_label": family.display_label,
            "buyer": family.buyer,
            "triggering_job": family.triggering_job,
            "economic_outcome": family.economic_outcome,
            "members": [_member_row(m) for m in members],
            "lead_idea_name": _get(members[0], "solution_name") or "",
            "incumbent_status": status,
            "incumbent_vendors": vendors,
            "fatal_assumptions": _fatal_assumptions(members),
        })

    logger.info(
        f"[IdeaTheses] {len(theses)} theses over {len(pool)} visible ideas "
        f"({len(uncovered)} uncovered families, {len(unassigned)} unassigned): "
        + "; ".join(f"{t['display_label']}[{len(t['members'])}/{t['incumbent_status']}]"
                    for t in theses))
    return {
        "family_source": getattr(partition, "source", "llm"),
        "theses": theses,
        "uncovered_families": uncovered,
        "unassigned": unassigned,
    }
