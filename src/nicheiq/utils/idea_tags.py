"""Assemble an idea's closed-vocabulary tag facets (see docs/IDEA_TAGS.md).

`derive_tag_facets` merges three sources into a single `IdeaTags`:
  - LLM-generated semantic facets (target_market, monetization, growth_channels, risk_flags)
    passed in as a dict from the crew tagging step;
  - code-derived buckets from the idea's scores (build_complexity, novelty_level, strengths,
    primary_strength) plus force-added derived signals (pSEO growth channel, tos-risk flag);
  - facets reused verbatim from existing idea fields (project_type, data_access).

All values are validated against the closed vocabularies; unknown values are dropped so the
resulting IdeaTags always parses. The strength cutoff table here is the single source of truth.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, get_args

from nicheiq.models.solution_idea import (
    DataAccessTag,
    GrowthChannelTag,
    IdeaTags,
    MonetizationTag,
    ProjectTypeTag,
    RiskFlagTag,
    TargetMarketTag,
    UsageCadenceTag,
)

if TYPE_CHECKING:
    from nicheiq.models.solution_idea import BaseSolutionIdea

logger = logging.getLogger(__name__)

# Closed vocabularies (derived from the Literal aliases — single source of truth)
PROJECT_TYPES = frozenset(get_args(ProjectTypeTag))
DATA_ACCESS = frozenset(get_args(DataAccessTag))
TARGET_MARKETS = frozenset(get_args(TargetMarketTag))
MONETIZATION = frozenset(get_args(MonetizationTag))
GROWTH_CHANNELS = frozenset(get_args(GrowthChannelTag))
RISK_FLAGS = frozenset(get_args(RiskFlagTag))
USAGE_CADENCE = frozenset(get_args(UsageCadenceTag))

# Pricing-shape check: usage cadences that clash with subscription billing (buyers churn
# between events), mapped to the shape to suggest instead. Informational — never a score.
_CADENCE_SHAPE_FIX = {
    "episodic": "usage-based pricing or credit packs",
    "one-shot": "a one-time purchase or paid report",
}

# Standardized per-dimension cutoffs for strength badges (calibrated to ~top-third on a
# 60-idea sample; tunable — see docs/IDEA_TAGS.md). Order also breaks primary-strength ties.
STRENGTH_CUTOFFS: list[tuple[str, str, float]] = [
    ("market-fit", "market_fit_score", 0.82),
    ("seo-power", "seo_scalability_score", 0.85),
    ("innovator", "novelty_score", 0.70),
    ("quick-build", "technical_feasibility_score", 0.85),
    ("solo-friendly", "solo_dev_feasibility", 0.78),
]

# "Easy to build" shares the solo-friendly cutoff so the two tags stay locked together (the table
# above is the single source of truth — never hardcode this elsewhere).
_SOLO_FRIENDLY_CUTOFF: float = dict((key, cut) for key, _field, cut in STRENGTH_CUTOFFS)["solo-friendly"]

# data_access_model values that genuinely imply a Terms-of-Service-gray acquisition route →
# derived tos-risk. Only `unofficial` qualifies: it denotes a ToS-gray route (unofficial API /
# scraping a site against its terms). `restricted` / `blocked` describe OBTAINABILITY (per-ID
# lookup, login-gated, no bulk route) — that's "hard to get", NOT "violates terms" — so they do
# NOT imply tos-risk. The LLM still owns tos-risk for everything else.
_TOS_RISK_ACCESS = frozenset({"unofficial"})


def _build_complexity(idea: "BaseSolutionIdea") -> Optional[str]:
    """Bucket solo operating load from solo_dev_feasibility — the SAME field shown as the "Solo" chip and
    used by the "solo-friendly" strength — so "Hard to run solo" cannot contradict a high Solo score
    (they read the same number). Falls back to build_feasibility/technical only when solo is absent.
    The "low" cut is locked to the solo-friendly cutoff so the positive and warning labels stay
    mutually consistent."""
    s = idea.solo_dev_feasibility
    if s is None:
        s = idea.build_feasibility_score
    if s is None:
        s = idea.technical_feasibility_score
    if s is None:
        return None
    if s >= _SOLO_FRIENDLY_CUTOFF:
        return "low"
    if s >= 0.65:
        return "medium"
    return "high"


def _novelty_level(idea: "BaseSolutionIdea") -> Optional[str]:
    """Bucket distinctiveness, matching the UI's inverse-obviousness presentation.
    Obviousness is the primary signal: LOWER = MORE distinct. novelty_score (higher = more
    distinct) is the fallback when obviousness is absent."""
    o = idea.obviousness_score
    n = idea.novelty_score
    if o is not None:
        if o <= 0.30:        # very original (Orig ≥ 70)
            return "novel"
        if o >= 0.60:        # obvious / unoriginal (Orig ≤ 40)
            return "conventional"
        return "moderate"
    if n is not None:
        if n >= 0.70:
            return "novel"
        if n <= 0.40:
            return "conventional"
        return "moderate"
    return None


def _strengths(idea: "BaseSolutionIdea") -> tuple[list[str], Optional[str]]:
    """All strengths clearing their cutoff, plus the single most exceptional (max margin)."""
    earned: list[str] = []
    margins: dict[str, float] = {}
    for key, field, cutoff in STRENGTH_CUTOFFS:
        v = getattr(idea, field, None)
        if isinstance(v, (int, float)) and v >= cutoff:
            earned.append(key)
            margins[key] = v - cutoff
    primary = max(margins, key=margins.get) if margins else None
    return earned, primary


def _has_pseo(idea: "BaseSolutionIdea") -> bool:
    pages = idea.estimated_indexable_pages or 0
    seo = idea.seo_scalability_score or 0
    return pages >= 500 or seo >= 0.7


def _norm_name(name: str) -> str:
    return "".join((name or "").lower().split())


def validate_solution_tags(
    tag_items: list, expected_names: list[str]
) -> tuple[bool, Optional[str]]:
    """Coverage check for the LLM tagging batch: every expected solution must be tagged.
    Returns (ok, error). Vocab correctness is NOT enforced here — derive_tag_facets coerces /
    drops out-of-vocab values, so one bad token never fails the batch."""
    tagged = {_norm_name(getattr(t, "solution_name", "")) for t in tag_items}
    missing = [n for n in expected_names if _norm_name(n) not in tagged]
    if missing:
        return False, f"missing tags for {len(missing)} solution(s): {missing[:5]}"
    return True, None


def derive_tag_facets(
    idea: "BaseSolutionIdea", llm_facets: Optional[dict] = None
) -> IdeaTags:
    """Build the complete IdeaTags for one idea. `llm_facets` carries the semantic facets from
    the tagging step (or None on failure — derived + reused facets still attach)."""
    llm = llm_facets or {}

    # growth channels: keep valid LLM values (dedup, order-preserving) + force-add pSEO
    growth = [g for g in dict.fromkeys(llm.get("growth_channels") or []) if g in GROWTH_CHANNELS]
    if _has_pseo(idea) and "programmatic-seo" not in growth:
        growth.append("programmatic-seo")

    # risk flags: valid LLM values + derived tos-risk from non-public data access
    risks = [r for r in dict.fromkeys(llm.get("risk_flags") or []) if r in RISK_FLAGS]
    if (idea.data_access_model or "") in _TOS_RISK_ACCESS and "tos-risk" not in risks:
        risks.append("tos-risk")

    strengths, primary = _strengths(idea)

    def _valid(value, vocab):
        return value if value in vocab else None

    rationale = (llm.get("rationale") or "").strip() or None
    if rationale:
        rationale = rationale[:200]

    monetization = _valid(llm.get("monetization"), MONETIZATION)
    usage_cadence = _valid(llm.get("usage_cadence"), USAGE_CADENCE)

    # Pricing-shape mismatch: episodic/one-shot usage sold as a subscription churns between
    # events (a validation tool used at project start, a price-raise kit used yearly).
    mismatch = monetization == "subscription" and usage_cadence in _CADENCE_SHAPE_FIX
    shape_note = (
        f"{usage_cadence} usage but subscription pricing — buyers churn between events; "
        f"consider {_CADENCE_SHAPE_FIX[usage_cadence]}"
    ) if mismatch else None

    return IdeaTags(
        project_type=_valid(idea.project_type, PROJECT_TYPES),
        data_access=_valid(idea.data_access_model, DATA_ACCESS),
        target_market=_valid(llm.get("target_market"), TARGET_MARKETS),
        monetization=monetization,
        monetization_secondary=_valid(llm.get("monetization_secondary"), MONETIZATION),
        growth_channels=growth,
        risk_flags=risks,
        usage_cadence=usage_cadence,
        pricing_shape_mismatch=mismatch,
        pricing_shape_note=shape_note,
        build_complexity=_build_complexity(idea),
        novelty_level=_novelty_level(idea),
        strengths=strengths,
        primary_strength=primary,
        rationale=rationale,
    )


def refresh_tag_facets(idea: "BaseSolutionIdea") -> IdeaTags:
    """Refresh an idea's tags from its current fields and scores.

    Semantic facets already attached by the tagging step are preserved. Reused and
    code-derived facets are rebuilt by :func:`derive_tag_facets`, so stale strength,
    complexity, and novelty buckets cannot outlive a later score adjustment. Ideas
    from legacy checkpoints without tags still receive every derivable facet.
    """
    existing = getattr(idea, "tags", None)
    if isinstance(existing, IdeaTags):
        semantic_facets = existing.model_dump()
    elif isinstance(existing, dict):
        semantic_facets = dict(existing)
    else:
        semantic_facets = None
    return derive_tag_facets(idea, semantic_facets)
