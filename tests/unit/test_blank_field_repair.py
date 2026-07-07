"""_repair_blank_idea_fields — post-loop fill-in for tournament winners (live 2026-07-05:
'RFPFailWatch' shipped why_it_works/pricing_strategy/... = None because the improve loop never
back-fills surface pitch fields and the final round has no next turn to surface the blank).

Fill-ONLY contract: never overwrite non-blank fields; no blanks -> no LLM call; fail-soft.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import (
    _FULL_FIELD_SPEC, _REPAIRABLE_TEXT_FIELDS, UnifiedSolutionCrew,
)
from nicheiq.models.solution_idea import BaseSolutionIdea

_INVOKE = "nicheiq.crews.unified_solution_crew.LLMService.invoke_structured"


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="tech founders seeking ideas")
    crew._record_divergent_usage = lambda u: None
    return crew


def _full_idea(**overrides):
    """An idea with every repairable field populated (the dominant, zero-cost case)."""
    base = dict(
        solution_name="RFPFailWatch", project_type="aggregator",
        headline="Weekly failed-RFP digest for founders",
        short_description="A weekly email digest of cancelled government RFPs.",
        description="A weekly email that delivers cancelled government RFPs with the unmet need summarized.",
        value_proposition="Objective validation from failed procurements.",
        conventional_approach="Asking friends if an idea is good.",
        innovation_angle="Mines negative data instead of open opportunities.",
        why_it_works="The government tried to pay someone to solve this and they failed.",
        why_it_works_short="Failed RFPs are hard proof a problem is real.",
        technical_approach="Cron queries SAM.gov for cancelled RFPs; LLM summarizes.",
        pricing_strategy="$19/mo subscription",
        programmatic_seo_opportunity="~500 pages, one per cancelled RFP category",
        content_generation_model="template + LLM summary",
        data_acquisition_notes="SAM.gov public API",
        estimated_cac_organic="$10-20", estimated_cac_paid="$50-80",
        organic_discovery_queries=["failed government rfp list"],
        pain_points_addressed=["Biased feedback"], core_features=["digest"],
        target_personas=["founders"], market_fit_score=0.6,
        technical_feasibility_score=0.7, novelty_score=0.5,
    )
    base.update(overrides)
    return BaseSolutionIdea(**base)


def _llm_filled(**overrides):
    """What the repair LLM returns — a full spec including fields the merge must NOT copy."""
    base = dict(
        solution_name="Renamed By LLM",  # not in the repair list: must never land on the idea
        headline="LLM headline", description="LLM description " * 5,
        short_description="LLM short description.",
        value_proposition="LLM value prop",
        conventional_approach="LLM conventional", innovation_angle="LLM angle",
        why_it_works="LLM grounded reason the mechanism works for this audience.",
        why_it_works_short="LLM short reason.",
        technical_approach="LLM tech approach", pricing_strategy="$29/mo",
        programmatic_seo_opportunity="~1000 pages", content_generation_model="LLM model",
        data_acquisition_notes="LLM data notes",
        estimated_cac_organic="$5", estimated_cac_paid="$40",
        organic_discovery_queries=["q1", "q2", "q3", "q4", "q5"],
        estimated_development_time="99 weeks",       # excluded: _finalize_dev_time owns it
        estimated_indexable_pages=12345,             # excluded: Stage-12 SEO owns it
        data_access_model="paywalled",               # excluded: v4 verifier vocab
        pain_points_addressed=["fabricated pain"],   # excluded: code-owned provenance
        market_fit_score=0.99, novelty_score=0.99,   # excluded: calibration critic owns scores
        technical_feasibility_score=0.99,
        core_features=["f"], target_personas=["t"],
    )
    base.update(overrides)
    return BaseSolutionIdea(**base)


def test_no_blanks_skips_llm():
    idea = _full_idea()
    with patch(_INVOKE, side_effect=AssertionError("must not be called")):
        _crew()._repair_blank_idea_fields(idea)
    assert idea.solution_name == "RFPFailWatch"


def test_fills_only_blank_fields_never_overwrites():
    idea = _full_idea(why_it_works=None, why_it_works_short=None,
                      pricing_strategy=None, organic_discovery_queries=None)
    with patch(_INVOKE, return_value=(_llm_filled(), None)):
        _crew()._repair_blank_idea_fields(idea)
    # blanks filled from the LLM output
    assert idea.why_it_works == "LLM grounded reason the mechanism works for this audience."
    assert idea.why_it_works_short == "LLM short reason."
    assert idea.pricing_strategy == "$29/mo"
    assert idea.organic_discovery_queries == ["q1", "q2", "q3", "q4", "q5"]
    # non-blank fields untouched (fill-only: the loop's latest coherent pitch survives)
    assert idea.headline == "Weekly failed-RFP digest for founders"
    assert idea.description.startswith("A weekly email")
    assert idea.solution_name == "RFPFailWatch"


def test_short_only_blank_derived_without_llm():
    idea = _full_idea(why_it_works_short=None)
    with patch(_INVOKE, side_effect=AssertionError("must not be called")):
        _crew()._repair_blank_idea_fields(idea)
    assert idea.why_it_works_short
    assert len(idea.why_it_works_short) <= 120
    assert idea.why_it_works_short.startswith("The government tried")


def test_fail_soft_on_llm_error():
    idea = _full_idea(why_it_works_short=None, pricing_strategy=None)
    with patch(_INVOKE, side_effect=RuntimeError("model down")):
        _crew()._repair_blank_idea_fields(idea)   # must not raise
    # deterministic derivation still applied; the LLM-only blank stays blank
    assert idea.why_it_works_short
    assert idea.pricing_strategy is None


def test_prompt_pins_and_shared_spec():
    idea = _full_idea(why_it_works=None, why_it_works_short=None, pricing_strategy=None)
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return _llm_filled(), None

    with patch(_INVOKE, side_effect=_cap):
        _crew()._repair_blank_idea_fields(idea)
    p = captured["prompt"]
    assert _FULL_FIELD_SPEC in p                       # SAME spec as every other birth path
    assert "NOT a redesign" in p
    assert "keep VERBATIM" in p and "RFPFailWatch" in p
    assert "pricing_strategy" in p and "why_it_works" in p  # blank fields named


def test_excluded_fields_never_written():
    idea = _full_idea(why_it_works=None)
    before = dict(
        estimated_development_time=idea.estimated_development_time,
        estimated_indexable_pages=idea.estimated_indexable_pages,
        data_access_model=idea.data_access_model,
        pain_points_addressed=list(idea.pain_points_addressed or []),
        market_fit_score=idea.market_fit_score,
        novelty_score=idea.novelty_score,
        solution_name=idea.solution_name,
    )
    with patch(_INVOKE, return_value=(_llm_filled(), None)):
        _crew()._repair_blank_idea_fields(idea)
    for f, v in before.items():
        assert getattr(idea, f) == v, f"{f} must not be written by the repair"


def test_repair_shares_the_spec():
    # parity pin (mirrors test_synthesis_bundles): all THREE expansion consumers reference
    # the ONE field spec — adding a field to _FULL_FIELD_SPEC covers repair too.
    src = inspect.getsource(UnifiedSolutionCrew._repair_blank_idea_fields)
    assert "_FULL_FIELD_SPEC" in src


def test_repair_list_matches_model_fields():
    # every repairable field must exist on BaseSolutionIdea (guards against renames drifting)
    for f in _REPAIRABLE_TEXT_FIELDS + ("organic_discovery_queries",):
        assert f in BaseSolutionIdea.model_fields, f"unknown repair field {f}"
