"""Tests for closed-vocabulary tag facet derivation (utils.idea_tags)."""

from typing import get_args

from nicheiq.models.solution_idea import (
    BuildComplexityTag,
    DataAccessTag,
    GrowthChannelTag,
    IdeaTags,
    MonetizationTag,
    NoveltyLevelTag,
    ProjectTypeTag,
    RiskFlagTag,
    StrengthTag,
    TargetMarketTag,
    UsageCadenceTag,
)
from nicheiq.utils.idea_tags import STRENGTH_CUTOFFS, derive_tag_facets


def _idea(**scores):
    """Minimal BaseSolutionIdea with overridable scores/fields."""
    from nicheiq.models.solution_idea import BaseSolutionIdea

    base = dict(
        solution_name="Test",
        description="A test idea.",
        value_proposition="Value.",
        pain_points_addressed=["pain"],
        core_features=["feature"],
        target_personas=["persona"],
    )
    base.update(scores)
    return BaseSolutionIdea(**base)


# --- strengths: multi-award + primary by margin ---------------------------------

def test_strengths_multi_award_and_primary_by_margin():
    idea = _idea(
        market_fit_score=0.83,        # +0.01 over 0.82
        seo_scalability_score=0.95,   # +0.10 over 0.85  -> biggest margin
        novelty_score=0.60,           # below 0.70
        technical_feasibility_score=0.80,  # below 0.85
        solo_dev_feasibility=0.79,    # +0.01 over 0.78
    )
    tags = derive_tag_facets(idea)
    assert set(tags.strengths) == {"market-fit", "seo-power", "solo-friendly"}
    assert tags.primary_strength == "seo-power"  # max margin wins, not raw max


def test_no_strengths_when_below_all_cutoffs():
    idea = _idea(
        market_fit_score=0.70,
        seo_scalability_score=0.70,
        novelty_score=0.50,
        technical_feasibility_score=0.70,
        solo_dev_feasibility=0.70,
    )
    tags = derive_tag_facets(idea)
    assert tags.strengths == []
    assert tags.primary_strength is None


def test_strengths_ignore_missing_scores():
    idea = _idea(novelty_score=0.75)  # only innovator present
    tags = derive_tag_facets(idea)
    assert tags.strengths == ["innovator"]
    assert tags.primary_strength == "innovator"


# --- build_complexity recalibrated buckets --------------------------------------

def test_build_complexity_buckets_from_solo_dev():
    # PRIMARY driver is solo_dev_feasibility (the visible "Solo" score).
    assert derive_tag_facets(_idea(solo_dev_feasibility=0.95)).build_complexity == "low"
    assert derive_tag_facets(_idea(solo_dev_feasibility=0.70)).build_complexity == "medium"
    assert derive_tag_facets(_idea(solo_dev_feasibility=0.55)).build_complexity == "high"


def test_build_complexity_low_cut_locked_to_solo_friendly():
    """The 'low' cut must equal the solo-friendly strength cutoff so Easy-to-build and Solo-friendly
    stay consistent — pins the single-source-of-truth invariant (review SHOULD-FIX 1)."""
    from nicheiq.utils.idea_tags import STRENGTH_CUTOFFS, _SOLO_FRIENDLY_CUTOFF

    solo_cut = dict((k, c) for k, _f, c in STRENGTH_CUTOFFS)["solo-friendly"]
    assert _SOLO_FRIENDLY_CUTOFF == solo_cut
    # 0.76 is below the 0.78 cut -> medium (would have been "low" under the old 0.75 cut).
    assert derive_tag_facets(_idea(solo_dev_feasibility=0.76)).build_complexity == "medium"


def test_hard_to_build_and_solo_friendly_never_co_occur():
    # solo<0.65 -> "high" (Hard to build); solo>=0.78 -> "solo-friendly". Non-overlapping by design.
    hard = _idea(solo_dev_feasibility=0.55)
    assert derive_tag_facets(hard).build_complexity == "high"
    assert "solo-friendly" not in derive_tag_facets(hard).strengths

    easy = _idea(solo_dev_feasibility=0.95)
    assert derive_tag_facets(easy).build_complexity != "high"
    assert "solo-friendly" in derive_tag_facets(easy).strengths


def test_build_complexity_falls_back_when_solo_absent():
    # No solo_dev -> fall back to build_feasibility, then technical.
    assert derive_tag_facets(_idea(build_feasibility_score=0.90)).build_complexity == "low"
    assert derive_tag_facets(_idea(technical_feasibility_score=0.55)).build_complexity == "high"


# --- novelty_level --------------------------------------------------------------

def test_novelty_level_matches_originality():
    # obviousness LOWER = MORE original (Originality = 1 - obviousness).
    assert derive_tag_facets(_idea(obviousness_score=0.2)).novelty_level == "novel"        # Orig 80
    assert derive_tag_facets(_idea(obviousness_score=0.35)).novelty_level == "moderate"     # Orig 65
    assert derive_tag_facets(_idea(obviousness_score=0.5)).novelty_level == "moderate"      # Orig 50
    assert derive_tag_facets(_idea(obviousness_score=0.65)).novelty_level == "conventional" # Orig 35
    assert derive_tag_facets(_idea(obviousness_score=0.85)).novelty_level == "conventional" # Orig 15
    # novelty_score fallback (higher = more original) when obviousness is absent
    assert derive_tag_facets(_idea(novelty_score=0.75)).novelty_level == "novel"
    assert derive_tag_facets(_idea(novelty_score=0.3)).novelty_level == "conventional"
    assert derive_tag_facets(_idea()).novelty_level is None


# --- pSEO force-add + tos-risk derivation ---------------------------------------

def test_pseo_force_added_to_growth_channels():
    idea = _idea(estimated_indexable_pages=800)
    tags = derive_tag_facets(idea, {"growth_channels": ["content"]})
    assert "programmatic-seo" in tags.growth_channels
    assert "content" in tags.growth_channels


def test_pseo_not_added_when_below_threshold():
    idea = _idea(estimated_indexable_pages=100, seo_scalability_score=0.5)
    tags = derive_tag_facets(idea, {"growth_channels": ["content"]})
    assert "programmatic-seo" not in tags.growth_channels


def test_tos_risk_derived_only_from_unofficial_access():
    # `unofficial` = ToS-gray route → derived tos-risk
    assert "tos-risk" in derive_tag_facets(_idea(data_access_model="unofficial")).risk_flags


def test_restricted_and_blocked_are_not_tos_risk():
    # `restricted` / `blocked` describe obtainability (hard to get), NOT a ToS violation.
    for access in ("restricted", "blocked", "public", "freemium", "paywalled"):
        tags = derive_tag_facets(_idea(data_access_model=access))
        assert "tos-risk" not in tags.risk_flags, access


def test_llm_tos_risk_still_respected():
    # The LLM can still assign tos-risk even when access doesn't auto-derive it.
    tags = derive_tag_facets(_idea(data_access_model="public"), {"risk_flags": ["tos-risk"]})
    assert "tos-risk" in tags.risk_flags


# --- vocabulary validation / coercion -------------------------------------------

def test_invalid_llm_values_dropped():
    idea = _idea()
    tags = derive_tag_facets(idea, {
        "target_market": "nonsense",
        "monetization": "bitcoin",
        "growth_channels": ["content", "made-up-channel"],
        "risk_flags": ["regulatory", "fake-risk"],
    })
    assert tags.target_market is None
    assert tags.monetization is None
    assert tags.growth_channels == ["content"]
    assert tags.risk_flags == ["regulatory"]


def test_reused_facets_copied_and_coerced():
    tags = derive_tag_facets(_idea(project_type="saas", data_access_model="freemium"))
    assert tags.project_type == "saas"
    assert tags.data_access == "freemium"
    # unknown project_type coerced to None (stays parseable)
    assert derive_tag_facets(_idea(project_type="weird")).project_type is None


def test_failsoft_without_llm_facets():
    """No LLM facets → derived + reused still attach, semantic facets None."""
    idea = _idea(project_type="saas", novelty_score=0.8, build_feasibility_score=0.9)
    tags = derive_tag_facets(idea, None)
    assert isinstance(tags, IdeaTags)
    assert tags.project_type == "saas"
    assert tags.novelty_level == "novel"
    assert tags.build_complexity == "low"
    assert tags.target_market is None and tags.monetization is None


# --- mutual-exclusivity invariant -----------------------------------------------

def test_facet_vocabularies_are_mutually_exclusive():
    """No value string appears in two facet vocabularies (faceted-classification rule)."""
    facets = {
        "project_type": get_args(ProjectTypeTag),
        "target_market": get_args(TargetMarketTag),
        "monetization": get_args(MonetizationTag),
        "growth_channels": get_args(GrowthChannelTag),
        "risk_flags": get_args(RiskFlagTag),
        "data_access": get_args(DataAccessTag),
        "build_complexity": get_args(BuildComplexityTag),
        "novelty_level": get_args(NoveltyLevelTag),
        "strengths": get_args(StrengthTag),
        "usage_cadence": get_args(UsageCadenceTag),
    }
    seen: dict[str, str] = {}
    for facet, values in facets.items():
        for v in values:
            assert v not in seen, f"value {v!r} in both {seen.get(v)} and {facet}"
            seen[v] = facet


def test_strength_cutoff_table_covers_all_strength_values():
    cutoff_keys = {k for k, _, _ in STRENGTH_CUTOFFS}
    assert cutoff_keys == set(get_args(StrengthTag))


# --- usage_cadence + pricing-shape mismatch --------------------------------------

def test_usage_cadence_accepted_and_out_of_vocab_dropped():
    tags = derive_tag_facets(_idea(), {"usage_cadence": "episodic"})
    assert tags.usage_cadence == "episodic"
    tags = derive_tag_facets(_idea(), {"usage_cadence": "sometimes"})
    assert tags.usage_cadence is None
    assert derive_tag_facets(_idea()).usage_cadence is None  # no LLM facets at all


def test_pricing_shape_mismatch_matrix():
    # episodic + subscription -> mismatch with the recommended shape in the note
    tags = derive_tag_facets(_idea(), {"monetization": "subscription", "usage_cadence": "episodic"})
    assert tags.pricing_shape_mismatch is True
    assert "churn between events" in tags.pricing_shape_note
    assert "usage-based pricing or credit packs" in tags.pricing_shape_note
    # one-shot + subscription -> mismatch, one-time recommendation
    tags = derive_tag_facets(_idea(), {"monetization": "subscription", "usage_cadence": "one-shot"})
    assert tags.pricing_shape_mismatch is True
    assert "one-time purchase" in tags.pricing_shape_note
    # continuous + subscription -> fine
    tags = derive_tag_facets(_idea(), {"monetization": "subscription", "usage_cadence": "continuous"})
    assert tags.pricing_shape_mismatch is False and tags.pricing_shape_note is None
    # episodic + one-time -> fine (shape already matches)
    tags = derive_tag_facets(_idea(), {"monetization": "one-time", "usage_cadence": "episodic"})
    assert tags.pricing_shape_mismatch is False and tags.pricing_shape_note is None
    # missing cadence -> never a mismatch
    tags = derive_tag_facets(_idea(), {"monetization": "subscription"})
    assert tags.pricing_shape_mismatch is False and tags.pricing_shape_note is None
