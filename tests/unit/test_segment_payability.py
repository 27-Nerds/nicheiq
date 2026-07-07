"""Segment payability (permanent since the 2026-07-06 gate pass): evidence-grounded wallet scoring for
audience segments, stamped onto ideas via source_segment, read by the critic line + cap (d).

Hermetic: LLM mocked; the deterministic blend/caps and the crew wiring are the units under test.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.segment_payability import (
    SegmentPayability, blend_payability, norm_segment_name, score_segment_payability,
)

_INVOKE_UTIL = "nicheiq.utils.llm_service.LLMService.invoke_structured"


def _seg(name, budget="Medium"):
    return SimpleNamespace(segment_name=name, budget_sensitivity=budget,
                           expertise_level="Intermediate",
                           payability_score=None, payability_class=None,
                           payability_rationale=None)


def _pain(title, ci, segments, quotes=()):
    return SimpleNamespace(title=title, commercial_intent=ci, affected_segments=list(segments),
                           representative_quotes=list(quotes))


def _llm_item(name, cls="personal-wallet", score=0.7, rationale="r"):
    return SegmentPayability(segment_name=name, payability_class=cls,
                             payability_score=score, rationale=rationale)


# --- deterministic blend ----------------------------------------------------------

def test_blend_prior_averages_and_clamps():
    # personal-wallet prior 0.25; LLM 0.7 -> (0.25+0.7)/2 = 0.475 -> 0.47 (float repr rounds down)
    assert blend_payability(0.7, "personal-wallet", "Medium") == 0.47
    # corporate prior 0.85; LLM 1.5 clamps to 1.0 -> 0.93
    assert blend_payability(1.5, "corporate-budget", "Low") == 0.93


def test_blend_high_budget_sensitivity_caps_at_prior_minus_margin():
    # High sensitivity: personal-wallet capped at 0.25 - 0.1 = 0.15 even with LLM 0.9
    assert blend_payability(0.9, "personal-wallet", "High") == 0.15
    assert blend_payability(0.9, "smb-budget", "high") == 0.5   # case-insensitive


# --- scoring util -----------------------------------------------------------------

def test_score_segments_allow_list_and_blend():
    segs = [_seg("Bootstrapped Solo Founder", budget="High"), _seg("Agency Owner", budget="Low")]
    pains = [_pain("P", 0.7, ["Agency Owner"], quotes=["we pay $200/mo for tools"])]
    fake = SimpleNamespace(segments=[
        _llm_item("Bootstrapped Solo Founder", "personal-wallet", 0.6),
        _llm_item("Agency Owner", "smb-budget", 0.8),
        _llm_item("Hallucinated Segment", "corporate-budget", 0.9),   # not an input -> dropped
        SegmentPayability(segment_name="Agency Owner", payability_class="rich-people"),  # off-vocab
    ])
    with patch(_INVOKE_UTIL, return_value=(fake, None)):
        out, _ = score_segment_payability(segs, pains, [{"name": "ToolX", "pricing": "$50/mo",
                                                         "focus": "agency ops"}], "niche")
    assert set(out) == {norm_segment_name("Bootstrapped Solo Founder"),
                        norm_segment_name("Agency Owner")}
    # High budget sensitivity capped the founder at prior-0.1
    assert out[norm_segment_name("Bootstrapped Solo Founder")].payability_score == 0.15
    assert out[norm_segment_name("Agency Owner")].payability_score == 0.7  # (0.6+0.8)/2


def test_score_segments_prompt_carries_evidence():
    segs = [_seg("Agency Owner", budget="Low")]
    pains = [_pain("P", 0.7, ["Agency Owner"], quotes=["we pay $200/mo for tools", "no money talk"])]
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return SimpleNamespace(segments=[_llm_item("Agency Owner", "smb-budget", 0.8)]), None
    with patch(_INVOKE_UTIL, side_effect=_cap):
        score_segment_payability(segs, pains, [{"name": "ToolX", "pricing": "$50/mo", "focus": "f"}],
                                 "my niche")
    p = captured["prompt"]
    assert "budget sensitivity: Low" in p
    assert "max 0.70" in p                       # joined-pain commercial intent
    assert 'we pay $200/mo for tools' in p       # money-language quote
    assert "ToolX: $50/mo" in p                  # incumbent existing-spend proof
    assert "pain without a wallet" in p.lower()  # downgrade framing


def test_score_segments_fail_soft():
    with patch(_INVOKE_UTIL, side_effect=RuntimeError("down")):
        out, usage = score_segment_payability([_seg("A")], [], [], "n")
    assert out == {} and usage is None
    assert score_segment_payability([], [], [], "n") == ({}, None)   # no segments, no call


# --- crew wiring ------------------------------------------------------------------

def _crew(pay_map=None):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew._payability_map = pay_map  # pre-cache: bypass the LLM path
    return crew


def _idea(name, segment):
    return SimpleNamespace(solution_name=name, source_segment=segment,
                           source_segment_payability=None, source_segment_payability_class=None)


def test_stamp_from_matching_segment():
    pay = {norm_segment_name("Agency Owner"): _llm_item("Agency Owner", "smb-budget", 0.7)}
    idea = _idea("X", "Agency Owner")
    _crew(pay)._stamp_payability(idea)
    assert idea.source_segment_payability == 0.7
    assert idea.source_segment_payability_class == "smb-budget"


def test_stamp_unmatched_falls_back_to_mean():
    # Uniform-coverage guard: a join failure gets the niche mean, never a silent None.
    pay = {norm_segment_name("A"): _llm_item("A", "smb-budget", 0.6),
           norm_segment_name("B"): _llm_item("B", "personal-wallet", 0.2)}
    idea = _idea("X", "Renamed Segment Nobody Knows")
    _crew(pay)._stamp_payability(idea)
    assert idea.source_segment_payability == 0.4          # mean(0.6, 0.2)
    assert idea.source_segment_payability_class == "mixed"


def test_stamp_noop_when_map_empty():
    idea = _idea("X", "Agency Owner")
    _crew({})._stamp_payability(idea)                      # empty map -> uniform none
    assert idea.source_segment_payability is None


# --- cap (d) ----------------------------------------------------------------------

def _cap_idea(mf, pay, cls="personal-wallet"):
    return SimpleNamespace(
        solution_name="X", market_fit_score=mf, novelty_score=None, obviousness_score=None,
        winning_angle=None, data_access_model="public", build_feasibility_score=0.8,
        solo_dev_feasibility=None, source_segment_payability=pay,
        source_segment_payability_class=cls)


def test_cap_d_fires_below_threshold():
    idea = _cap_idea(mf=0.75, pay=0.2)
    flags = _crew()._validate_idea_caps(idea)
    assert idea.market_fit_score == settings.payability_market_fit_cap
    assert any("segment payability" in f for f in flags)
    # idempotent
    flags2 = _crew()._validate_idea_caps(idea)
    assert idea.market_fit_score == settings.payability_market_fit_cap
    assert not any("segment payability" in f for f in flags2)


def test_cap_d_noop_none_payability_or_low_mf():
    idea = _cap_idea(mf=0.75, pay=None)
    _crew()._validate_idea_caps(idea)
    assert idea.market_fit_score == 0.75                   # unscored -> fail-open
    idea = _cap_idea(mf=0.5, pay=0.2)
    _crew()._validate_idea_caps(idea)
    assert idea.market_fit_score == 0.5                    # already under the cap


# --- critic line ------------------------------------------------------------------

def test_fenced_row_carries_payability_line_only_when_stamped(monkeypatch):
    import nicheiq.crews.unified_solution_crew as usc
    crew = _crew()
    crew._format_competitor_mentions = lambda: ""
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    idea = SimpleNamespace(
        solution_name="X", source_segment="Agency Owner", source_segment_payability=0.15,
        source_segment_payability_class="personal-wallet", pain_points_addressed=[],
        source_pain="", value_proposition="v", conventional_approach="c",
        innovation_angle="i", why_it_works="w", technical_approach="t",
        requires_data_aggregation=False, data_access_model="public",
        build_feasibility_score=0.8, data_feasibility_score=0.8,
        programmatic_seo_opportunity="", content_generation_model="", winning_angle=None)
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return SimpleNamespace(calibrations=[]), None
    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_cap))

    crew._calibrate_batch(batch=[idea])
    assert "buyer payability: personal-wallet (0.15)" in captured["prompt"]
    assert "BUYER PAYABILITY" in captured["prompt"]        # rubric paragraph

    idea.source_segment_payability = None                  # unstamped -> no line (rubric stays)
    crew._calibrate_batch(batch=[idea])
    assert "buyer payability:" not in captured["prompt"]


def test_stamp_resets_llm_fabricated_values():
    # BaseSolutionIdea is also the generators' structured-output model — the LLM can fabricate
    # payability values (observed live 2026-07-06). Reset-first must clear them even when the
    # map is empty.
    idea = _idea("X", "Agency Owner")
    idea.source_segment_payability = 0.9          # fabricated by the generator LLM
    idea.source_segment_payability_class = "corporate-budget"
    _crew({})._stamp_payability(idea)
    assert idea.source_segment_payability is None
    assert idea.source_segment_payability_class is None
