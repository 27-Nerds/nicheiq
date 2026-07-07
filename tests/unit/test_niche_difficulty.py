"""Hermetic tests for the Research Reality Check difficulty classifier.

Targets the pure `assess_niche_difficulty` (no LLM/IO) plus the deterministic
fallback path of `generate_niche_difficulty_verdict` (LLM monkeypatched to raise).
"""

from types import SimpleNamespace

import pytest

from nicheiq.utils.niche_difficulty import (
    assess_niche_difficulty,
    generate_niche_difficulty_verdict,
)


def _pain(tool="full"):
    return SimpleNamespace(tool_addressable=tool)


def _idea(
    novelty=0.5,
    novelty_raw=None,
    project_type="saas",
    mechanism_tag="workflow-automation",
    audience_fit=None,
    requires_data_aggregation=False,
    data_access_model="public",
):
    return SimpleNamespace(
        novelty_score=novelty,
        novelty_score_raw=novelty_raw,
        project_type=project_type,
        mechanism_tag=mechanism_tag,
        audience_fit=audience_fit,
        requires_data_aggregation=requires_data_aggregation,
        data_access_model=data_access_model,
    )


def _nc(scope=None, audience="founders"):
    return SimpleNamespace(audience_scope=scope, user_target_audience=audience)


def test_empty_returns_none():
    assert assess_niche_difficulty([], [], _nc()) is None


def test_all_none_tool_addressable_is_very_high():
    fp = assess_niche_difficulty([_pain("none")] * 6, [_idea()] * 4, _nc())
    assert fp.difficulty_level == "very_high"
    assert fp.software_addressability == 0.0
    assert "tool_addressability" in fp.flags


def test_all_full_high_novelty_is_low():
    ideas = [
        _idea(novelty=0.6, novelty_raw=0.62, project_type=pt, mechanism_tag="workflow")
        for pt in ("saas", "marketplace", "saas", "comparison-tool")
    ]
    fp = assess_niche_difficulty([_pain("full")] * 6, ideas, _nc())
    assert fp.difficulty_level == "low"
    assert fp.software_addressability == 1.0
    assert fp.flags == []  # no friction


def test_missing_raw_means_no_calibration_gap():
    fp = assess_niche_difficulty(
        [_pain("partial")] * 4,
        [_idea(novelty=0.5, novelty_raw=None)] * 3,
        _nc(),
    )
    assert fp.novelty_calibration_gap is None
    assert "calibration" not in fp.flags


def test_audience_fit_ratio_only_for_segment_scope():
    ideas = [_idea(audience_fit=True), _idea(audience_fit=False)]
    fp_other = assess_niche_difficulty([_pain("full")] * 3, ideas, _nc(scope="niche"))
    assert fp_other.audience_fit_ratio is None

    fp_seg = assess_niche_difficulty(
        [_pain("full")] * 3, ideas, _nc(scope="segment_of_niche")
    )
    assert fp_seg.audience_fit_ratio == 0.5


def test_low_confidence_on_tiny_sample():
    fp = assess_niche_difficulty([_pain("partial")], [_idea()], _nc())
    assert fp.low_confidence is True


def test_concentrated_derivative_low_novelty_escalates():
    # 4 aggregator/lookup ideas, low novelty -> derivative flag; combined with the
    # tool-addressability flag (partial pains) this should escalate past 'medium'.
    ideas = [
        _idea(novelty=0.3, project_type="aggregator", mechanism_tag="lookup-database")
        for _ in range(4)
    ]
    fp = assess_niche_difficulty([_pain("partial")] * 4, ideas, _nc())
    assert "derivative" in fp.flags
    assert fp.difficulty_level in ("high", "very_high")
    assert fp.derivative_mechanism_share == 1.0


def test_saturation_surfaces_even_on_strong_fit_niche():
    # Strong fit (addressable pains, public data, room for novelty) BUT a high share of brainstormed
    # concepts were flagged already-existing → "great data, clear pains, mature tool ecosystem".
    pains = [_pain("full")] * 6 + [_pain("partial")] * 2
    ideas = [_idea(novelty=0.5) for _ in range(4)]
    fp = assess_niche_difficulty(pains, ideas, _nc("segment_of_niche"), concept_duplication_rate=0.44)
    assert fp.difficulty_level == "low"                       # software fits
    assert fp.concept_duplication_rate == 0.44
    assert "saturated_tooling" in fp.flags
    assert any("tool ecosystem looks mature" in k for k in fp.key_points)  # surfaced despite strong fit


def test_no_saturation_when_duplication_low():
    pains = [_pain("full")] * 6 + [_pain("partial")] * 2
    ideas = [_idea(novelty=0.5) for _ in range(4)]
    fp = assess_niche_difficulty(pains, ideas, _nc("segment_of_niche"), concept_duplication_rate=0.1)
    assert "saturated_tooling" not in fp.flags


def test_saturation_skipped_when_fit_is_the_problem():
    # When addressability is low, the fit verdict leads — don't also cry "saturated".
    pains = [_pain("none")] * 6 + [_pain("partial")] * 2
    ideas = [_idea(novelty=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(pains, ideas, _nc("segment_of_niche"), concept_duplication_rate=0.5)
    assert "saturated_tooling" not in fp.flags


def test_blocked_data_access_counts_as_cold_start():
    ideas = [_idea(requires_data_aggregation=False, data_access_model="blocked")] * 3
    fp = assess_niche_difficulty([_pain("partial")] * 3, ideas, _nc())
    assert fp.cold_start_share == 1.0


def _patch_llm_headline(monkeypatch, headline):
    from types import SimpleNamespace
    from nicheiq.utils import llm_service
    monkeypatch.setattr(
        llm_service.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (SimpleNamespace(headline=headline, narrative_summary="ok"), None)),
    )


def test_verdict_rejects_headline_with_wrong_rating(monkeypatch):
    # very_high band -> rating word "Hard". An LLM headline that says "Limited" contradicts the band,
    # so the guard rejects it and the deterministic headline stands.
    _patch_llm_headline(monkeypatch, "Software Fit: Limited — differentiation is the real bottleneck")
    fp = assess_niche_difficulty([_pain("none")] * 5, [_idea(novelty=0.3)] * 3, _nc())
    assert fp.difficulty_level == "very_high"
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert v.headline == "Software Fit: Hard — software can only sit beside the problem"


def test_verdict_keeps_tailored_headline_when_rating_matches(monkeypatch):
    # medium band -> "Moderate"; a matching tailored headline is kept verbatim.
    _patch_llm_headline(monkeypatch, "Software Fit: Moderate — pick the wedge carefully")
    fp = assess_niche_difficulty([_pain("full")] * 2 + [_pain("partial")] * 3, [_idea(novelty=0.45)] * 3, _nc())
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert fp.difficulty_level == "medium"
    assert v.headline == "Software Fit: Moderate — pick the wedge carefully"


def test_verdict_falls_back_when_llm_raises(monkeypatch):
    from nicheiq.utils import llm_service

    def _boom(*args, **kwargs):
        raise RuntimeError("no live llm in tests")

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_boom))

    fp = assess_niche_difficulty([_pain("none")] * 5, [_idea(novelty=0.3)] * 3, _nc())
    verdict, usage = generate_niche_difficulty_verdict(fp, "peptide research", _nc())

    assert usage is None
    assert verdict.difficulty_level == "very_high"
    assert verdict.headline  # deterministic fallback populated
    assert verdict.narrative_summary
    assert verdict.software_addressability == fp.software_addressability


# ── 2026-07-02 words-only narrative contract ─────────────────────────────────

def test_share_word_bands():
    from nicheiq.utils.niche_difficulty import _share_word
    assert _share_word(None) == "n/a"
    assert _share_word(0.0) == "none"
    assert _share_word(0.06) == "a small minority"
    assert _share_word(0.20) == "about a quarter"
    assert _share_word(0.49) == "about half"
    assert _share_word(0.85) == "nearly all"


def test_saturation_judgment_low_is_good_news():
    from nicheiq.utils.niche_difficulty import _saturation_judgment
    # a bare "6%" read as a warning in prose — the judgment phrase carries the meaning
    assert "NOT already built" in _saturation_judgment(0.06)
    assert "differentiation" not in _saturation_judgment(0.06)
    assert _saturation_judgment(0.5).startswith("high")
    assert _saturation_judgment(None) == "n/a"


def test_shape_concentration_words():
    from nicheiq.utils.niche_difficulty import _shape_concentration_word
    assert "dominates" in _shape_concentration_word(0.6)
    assert "no single shape dominates" in _shape_concentration_word(0.15)


def test_prompt_receives_no_percentages(monkeypatch):
    # the words-only contract at the source: no digit-percent tokens in the rendered prompt
    from types import SimpleNamespace
    from nicheiq.utils import llm_service
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return (SimpleNamespace(headline="", narrative_summary=""), None)

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    fp = assess_niche_difficulty(
        [_pain("none")] * 3 + [_pain("partial")] * 2, [_idea(novelty=0.3)] * 4, _nc())
    generate_niche_difficulty_verdict(fp, "x", _nc())
    import re
    assert captured["prompt"]
    assert not re.search(r"\d+%", captured["prompt"])
    assert "about" in captured["prompt"] or "minority" in captured["prompt"] or "nearly all" in captured["prompt"] or "none" in captured["prompt"]


def test_strong_fit_with_frictions_keeps_strong_headline(monkeypatch):
    """Codex-review fix (2026-07-02): the ≥2-friction escalation can band a strong-fit niche
    'high', but FIT language must come from addressability — 'Software Fit: Limited' next to
    an 88% addressability meter was a printed contradiction."""
    _patch_llm_headline(monkeypatch, "")   # empty LLM headline -> deterministic fit headline stands
    # all pains fully tool-addressable → addressability 1.0 (strong)
    pains = [_pain("full")] * 6
    # frictions: notable calibration gap + cold-start ideas → ≥2 flags → escalation
    ideas = [_idea(novelty=0.4, novelty_raw=0.8, data_access_model="unverified",
                   requires_data_aggregation=True) for _ in range(4)]
    fp = assess_niche_difficulty(pains, ideas, _nc())
    assert fp.software_addressability >= 0.7
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert v.headline.startswith("Software Fit: Strong")
    if fp.difficulty_level in ("high", "very_high"):
        # frictions still surfaced, just not as a fit problem
        assert v.key_challenges


def test_moderate_fit_high_difficulty_narrative_reconciles():
    """Wedding-photographers run (2026-07-07): 'Software Fit: Moderate' next to a 'high'
    difficulty band read as a contradiction — the fallback narrative must attribute the
    difficulty to frictions, not a worse fit (same reconciliation the strong branch has)."""
    from nicheiq.utils.niche_difficulty import _fallback_narrative
    fp = SimpleNamespace(
        software_addressability=0.6, difficulty_level="high", n_pains=6,
        full_share=0.4, key_points=[], low_confidence=False,
        dominant_project_type="saas", shape_concentration=0.5,
    )
    headline, lead = _fallback_narrative(fp, "x")
    assert headline.startswith("Software Fit: Moderate")
    assert "frictions" in lead and "not a worse fit" in lead
    # medium difficulty: no friction clause needed
    fp.difficulty_level = "medium"
    _, lead2 = _fallback_narrative(fp, "x")
    assert "frictions" not in lead2


def test_wtp_signals_computed_and_weak_wtp_keypoint():
    from nicheiq.utils.niche_difficulty import _WEAK_WTP_CHALLENGE, _wtp_judgment
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=ci)
             for ci in (0.55, 0.4, 0.3)]
    fp = assess_niche_difficulty(pains, [_idea(novelty=0.6)] * 4, _nc())
    assert fp.commercial_intent_max == 0.55
    assert fp.high_commercial_share == 0.0
    assert _WEAK_WTP_CHALLENGE in fp.key_points          # surfaced even on a strong-fit niche
    # judgment bands
    assert _wtp_judgment(None, None) == "n/a"
    assert _wtp_judgment(0.55, 0.0).startswith("weak")
    assert "NOT subscription" in _wtp_judgment(0.55, 0.0)
    assert _wtp_judgment(0.8, 0.3).startswith("strong")
    assert _wtp_judgment(0.7, 0.1).startswith("moderate")


def test_strong_wtp_no_keypoint():
    from nicheiq.utils.niche_difficulty import _WEAK_WTP_CHALLENGE
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.75) for _ in range(4)]
    fp = assess_niche_difficulty(pains, [_idea(novelty=0.6)] * 4, _nc())
    assert _WEAK_WTP_CHALLENGE not in fp.key_points


def test_wtp_reaches_prompt(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return (NS(headline="", narrative_summary=""), None)
    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(pains, [_idea(novelty=0.6)] * 4, _nc())
    generate_niche_difficulty_verdict(fp, "x", _nc())
    assert "Willingness to pay" in captured["prompt"]
    assert "weak — no pain crosses" in captured["prompt"]


# --- buyer class (who pays here) --------------------------------------------------

def _seg(name, budget="High"):
    return SimpleNamespace(segment_name=name, budget_sensitivity=budget)


def test_segment_budget_brief_computed_and_reaches_prompt(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return (NS(headline="", narrative_summary=""), None)
    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(),
        segments=[_seg("Bootstrapped Solo Founder"), _seg("Technical Founder", "Medium")])
    assert fp.segment_budget_brief == (
        "Bootstrapped Solo Founder (budget sensitivity: High); "
        "Technical Founder (budget sensitivity: Medium)")
    generate_niche_difficulty_verdict(fp, "x", _nc())
    assert "Buyer segments" in captured["prompt"]
    assert "Bootstrapped Solo Founder" in captured["prompt"]


def test_buyer_class_validated_and_low_class_adds_challenge(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    monkeypatch.setattr(
        llm_service.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (NS(headline="", narrative_summary="n",
                                      buyer_class="indie-hobbyist"), None)))
    fp = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(),
                                 segments=[_seg("Indie Builders")])
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert v.buyer_class == "indie-hobbyist"
    assert "personal money" in v.buyer_class_note
    assert v.buyer_class_note in v.key_challenges   # low payability surfaces as a challenge


def test_buyer_class_off_vocab_dropped(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    monkeypatch.setattr(
        llm_service.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (NS(headline="", narrative_summary="n",
                                      buyer_class="rich-people"), None)))
    fp = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert v.buyer_class is None and v.buyer_class_note is None


def test_buyer_class_none_on_llm_failure():
    # LLM path raises inside generate_ (no llm_service available in hermetic env is fine —
    # monkeypatch it to raise to be explicit)
    import pytest as _p
    from nicheiq.utils import llm_service

    class _Boom:
        @staticmethod
        def invoke_structured(**kw):
            raise RuntimeError("down")
    fp = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    _orig = llm_service.LLMService.invoke_structured
    llm_service.LLMService.invoke_structured = _Boom.invoke_structured
    try:
        v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    finally:
        llm_service.LLMService.invoke_structured = _orig
    assert v.buyer_class is None
    assert v.headline  # deterministic fallback intact


def test_high_payability_class_no_extra_challenge(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    monkeypatch.setattr(
        llm_service.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (NS(headline="", narrative_summary="n",
                                      buyer_class="budgeted-business"), None)))
    fp = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())
    assert v.buyer_class == "budgeted-business"
    assert v.buyer_class_note and "budget authority" in v.buyer_class_note
    assert v.buyer_class_note not in v.key_challenges  # only LOW classes become challenges


# --- web-verified competition + usage-shape signals (2026-07-06) -------------------

def _cidea(parity=None, adjacent=None, cadence=None, novelty=0.6):
    i = _idea(novelty=novelty)
    i.incumbent_parity = parity
    i.adjacent_market_parity = adjacent
    i.tags = SimpleNamespace(usage_cadence=cadence)
    return i


def test_competition_and_cadence_aggregates():
    ideas = [
        _cidea(parity="substitute (census.gov): free", cadence="episodic"),
        _cidea(parity="shipped by X: y", cadence="one-shot"),
        _cidea(parity="partial by X: y", adjacent="V (cat): e", cadence="continuous"),
        _cidea(parity="none found", adjacent="V (cat): e", cadence="periodic"),
    ]
    fp = assess_niche_difficulty([_pain()] * 4, ideas, _nc())
    assert fp.substitute_share == 0.25
    assert fp.verified_incumbent_share == 0.5
    assert fp.adjacent_incumbent_share == 0.5
    assert fp.episodic_usage_share == 0.5


def test_substitute_and_incumbent_challenges_fire():
    from nicheiq.utils.niche_difficulty import (_INCUMBENT_DENSE_CHALLENGE,
                                                _SUBSTITUTE_CHALLENGE)
    ideas = [_cidea(parity="substitute (x): y"), _cidea(parity="shipped by A: b"),
             _cidea(parity="shipped by A: b"), _cidea(parity="partial by A: b")]
    fp = assess_niche_difficulty([_pain()] * 4, ideas, _nc())
    assert _SUBSTITUTE_CHALLENGE in fp.key_points
    assert _INCUMBENT_DENSE_CHALLENGE in fp.key_points


def test_adjacent_money_challenge_needs_weak_wallets():
    from nicheiq.utils.niche_difficulty import _ADJACENT_MONEY_CHALLENGE
    ideas = [_cidea(adjacent="V (cat): e") for _ in range(4)]
    weak = [_seg("Indie", "High")]
    for s in weak:
        s.payability_score, s.payability_class = 0.2, "personal-wallet"
    fp = assess_niche_difficulty([_pain()] * 4, ideas, _nc(), segments=weak)
    assert fp.segment_payability_mean == 0.2
    assert _ADJACENT_MONEY_CHALLENGE in fp.key_points
    # healthy wallets -> adjacent presence alone is not the "sell elsewhere" story
    rich = [_seg("Agency", "Low")]
    for s in rich:
        s.payability_score, s.payability_class = 0.7, "smb-budget"
    fp2 = assess_niche_difficulty([_pain()] * 4, ideas, _nc(), segments=rich)
    assert _ADJACENT_MONEY_CHALLENGE not in fp2.key_points


def test_episodic_challenge_defers_to_wtp_challenge():
    from nicheiq.utils.niche_difficulty import (_EPISODIC_CHALLENGE, _WEAK_WTP_CHALLENGE)
    ideas = [_cidea(cadence="episodic") for _ in range(4)]
    # strong buying signals -> WTP challenge absent -> episodic note fires
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.8) for _ in range(4)]
    fp = assess_niche_difficulty(pains, ideas, _nc())
    assert _EPISODIC_CHALLENGE in fp.key_points
    # weak buying signals -> WTP challenge already carries the pricing-shape advice
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.3) for _ in range(4)]
    fp2 = assess_niche_difficulty(pains, ideas, _nc())
    assert _WEAK_WTP_CHALLENGE in fp2.key_points
    assert _EPISODIC_CHALLENGE not in fp2.key_points


def test_segment_brief_carries_wallet_class_and_prompt_gets_new_words(monkeypatch):
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return (NS(headline="", narrative_summary=""), None)
    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    seg = _seg("Indie Builders", "High")
    seg.payability_score, seg.payability_class = 0.15, "personal-wallet"
    ideas = [_cidea(parity="substitute (x): y", cadence="episodic") for _ in range(4)]
    fp = assess_niche_difficulty([_pain()] * 4, ideas, _nc(), segments=[seg])
    assert "wallet: personal-wallet" in fp.segment_budget_brief
    generate_niche_difficulty_verdict(fp, "x", _nc())
    p = captured["prompt"]
    assert "already free/DIY" in p and "ADJACENT commercial market" in p
    assert "episodically" in p
