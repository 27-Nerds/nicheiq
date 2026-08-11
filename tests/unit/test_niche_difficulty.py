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


def test_recommendation_audience_drift_uses_requested_primary_and_recommended_only():
    from nicheiq.utils.niche_difficulty import detect_recommendation_audience_drift

    notice = detect_recommendation_audience_drift(
        "independent veterinary clinics across multiple locations",
        "Independent Single-Location General Practices with Manual Drug Logs",
        [SimpleNamespace(
            source_segment=(
                "Specialty, Emergency, and Referral Hospitals with High-Volume "
                "Controlled-Drug Workflows"
            )
        )],
    )

    assert notice is not None
    assert notice.recommended_source_segments == [
        "Specialty, Emergency, and Referral Hospitals with High-Volume Controlled-Drug Workflows"
    ]
    assert notice.message == (
        "You asked to reach “independent veterinary clinics across multiple locations”. "
        "The dossier centers “Independent Single-Location General Practices with Manual "
        "Drug Logs”, while the recommendation is built for “Specialty, Emergency, and "
        "Referral Hospitals with High-Volume Controlled-Drug Workflows”. Validate that "
        "buyer shift before funding or building the recommendation."
    )


def test_recommendation_audience_drift_renders_nothing_when_all_three_agree():
    from nicheiq.utils.niche_difficulty import detect_recommendation_audience_drift

    assert detect_recommendation_audience_drift(
        "independent veterinary clinics",
        "Independent veterinary clinics",
        [SimpleNamespace(source_segment="Independent veterinary clinics")],
    ) is None


def test_recommendation_audience_drift_ignores_mild_wording_differences():
    from nicheiq.utils.niche_difficulty import detect_recommendation_audience_drift

    assert detect_recommendation_audience_drift(
        "independent veterinary clinics managing medication inventory",
        "Independent vet practices managing medicine inventory",
        [SimpleNamespace(source_segment="Independent veterinary practices managing drug inventory")],
    ) is None


def test_fact_pack_drift_never_falls_back_to_the_whole_pool():
    requested = _nc("segment_of_niche", "independent veterinary clinics")
    segments = [_seg("Independent veterinary clinics")]
    pool = [_idea(audience_fit=False)]
    pool[0].source_segment = "Corporate emergency hospital groups"

    unscoped = assess_niche_difficulty([_pain("full")] * 3, pool, requested, segments=segments)
    scoped = assess_niche_difficulty(
        [_pain("full")] * 3,
        pool,
        requested,
        segments=segments,
        recommended_candidates=pool,
    )

    assert unscoped.audience_drift_notice is None
    assert "audience_drift" not in unscoped.flags
    assert scoped.audience_drift_notice is not None
    assert "audience_drift" in scoped.flags


def test_fact_pack_ignores_divergent_non_recommended_candidates():
    requested = _nc("segment_of_niche", "independent veterinary clinics")
    segments = [_seg("Independent veterinary clinics")]
    recommended = _idea(audience_fit=True)
    recommended.source_segment = "Independent veterinary practices"
    unrelated = _idea(audience_fit=False)
    unrelated.source_segment = "Corporate emergency hospital groups"

    fp = assess_niche_difficulty(
        [_pain("full")] * 3,
        [recommended, unrelated],
        requested,
        segments=segments,
        recommended_candidates=[recommended],
    )

    assert fp.audience_drift_notice is None
    assert "audience_drift" not in fp.flags


def test_recommendation_drift_reads_dict_candidates_and_deduplicates_segments():
    from nicheiq.utils.niche_difficulty import detect_recommendation_audience_drift

    notice = detect_recommendation_audience_drift(
        "Independent multi-location veterinary clinics",
        "Independent single-location general veterinary practices",
        [
            {"source_segment": "Specialty emergency veterinary hospitals"},
            {"source_segment": "Specialty emergency veterinary hospitals"},
        ],
    )

    assert notice is not None
    assert notice.recommended_source_segments == ["Specialty emergency veterinary hospitals"]


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
    assert v.headline == "Software Fit: Hard. Software can only sit beside the problem"


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
    from nicheiq.utils.niche_difficulty import (
        _WEAK_WTP_CHALLENGE, _wtp_judgment, has_zero_price_prescription)
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=ci)
             for ci in (0.55, 0.4, 0.3)]
    fp = assess_niche_difficulty(pains, [_idea(novelty=0.6)] * 4, _nc())
    assert fp.commercial_intent_max == 0.55
    assert fp.high_commercial_share == 0.0
    assert _WEAK_WTP_CHALLENGE in fp.key_points          # surfaced even on a strong-fit niche
    # judgment bands
    assert _wtp_judgment(None, None) == "n/a"
    assert _wtp_judgment(0.55, 0.0) == _WEAK_WTP_CHALLENGE
    # A FACT about the corpus, not a commercial shape to adopt (D1 round 15, Priority 1).
    assert "corpus evidence gap" in _wtp_judgment(0.55, 0.0)
    assert not has_zero_price_prescription(_wtp_judgment(0.55, 0.0))
    assert _wtp_judgment(0.8, 0.3).startswith("Strong corpus")
    assert _wtp_judgment(0.7, 0.1).startswith("Moderate corpus")


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
    assert "No pain in this run crosses the buying-signal bar" in captured["prompt"]


def test_final_visible_narrative_is_wallet_consistent_for_weak_corpus(monkeypatch):
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd
    from nicheiq.utils.niche_difficulty import (
        _PAYING_WALLET_CORPUS_CHALLENGE,
        _WEAK_WTP_CHALLENGE,
    )

    forbidden = (
        "Avoid subscription pricing because willingness to pay is weak across the board. "
        "Build only a free lead-generation tool."
    )
    responses = iter([
        SimpleNamespace(headline="", narrative_summary=forbidden, buyer_class=""),
        SimpleNamespace(
            headline="", narrative_summary=_PAYING_WALLET_CORPUS_CHALLENGE, buyer_class=""
        ),
        SimpleNamespace(headline="", narrative_summary=_WEAK_WTP_CHALLENGE, buyer_class=""),
        SimpleNamespace(headline="", narrative_summary=_WEAK_WTP_CHALLENGE, buyer_class=""),
    ])
    call_count = 0

    def _cap(**kw):
        nonlocal call_count
        call_count += 1
        return next(responses), None

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    inspected_wallets = []
    real_invariant = nd._commercial_copy_violations

    def _inspect(verdict, fp):
        inspected_wallets.append(fp.wallet_class)
        return real_invariant(verdict, fp)

    monkeypatch.setattr(nd, "_commercial_copy_violations", _inspect)
    evidence = "$99-399/mo DaySmart Vet, $299/mo single-vet, $290/mo IDEXX Neo, $300/mo VetSnap"
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=ci)
             for ci in (0.48, 0.55, 0.52, 0.42)]
    ideas = [_idea(novelty=0.6)] * 4

    paying_fp = assess_niche_difficulty(
        pains,
        ideas,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": evidence},
    )
    paying_verdict, _ = generate_niche_difficulty_verdict(
        paying_fp, "veterinary clinics", _nc())
    free_fp = assess_niche_difficulty(
        pains,
        ideas,
        _nc(),
        niche_wallet_brief={"wallet_class": "free-culture", "evidence": "most tools are free"},
    )
    free_verdict, _ = generate_niche_difficulty_verdict(free_fp, "veterinary clinics", _nc())
    unknown_fp = assess_niche_difficulty(pains, ideas, _nc())
    unknown_verdict, _ = generate_niche_difficulty_verdict(
        unknown_fp, "veterinary clinics", _nc())

    assert paying_verdict.narrative_summary == (
        "This niche is a strong fit for software: the pains are workflow or data problems a tool "
        "can directly own. There's room for a real product rather than a thin reference."
    )
    assert paying_verdict.key_challenges == [_PAYING_WALLET_CORPUS_CHALLENGE]
    assert _PAYING_WALLET_CORPUS_CHALLENGE not in paying_verdict.narrative_summary
    assert free_verdict.narrative_summary == _WEAK_WTP_CHALLENGE
    assert unknown_verdict.narrative_summary == _WEAK_WTP_CHALLENGE
    assert call_count == 4
    assert {"paying", "free-culture", None}.issubset(inspected_wallets)


def test_final_visible_narrative_reconciles_paying_consumer_bypass(monkeypatch):
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd
    from nicheiq.utils.niche_difficulty import _commercial_copy_violations

    forbidden = (
        "Avoid subscription pricing because willingness to pay is weak across the board. "
        "Build only a free lead-generation tool."
    )
    call_count = 0

    def _cap(**kw):
        nonlocal call_count
        call_count += 1
        return SimpleNamespace(
            headline="",
            narrative_summary=forbidden,
            buyer_class="consumer",
        ), None

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    evidence = "$99-399/mo DaySmart Vet, $299/mo single-vet, $290/mo IDEXX Neo, $300/mo VetSnap"
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=ci)
             for ci in (0.48, 0.55, 0.52, 0.42)]
    fp = assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": evidence},
    )

    warnings = []
    sink_id = nd.logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        verdict, _ = generate_niche_difficulty_verdict(fp, "veterinary clinics", _nc())
    finally:
        nd.logger.remove(sink_id)

    assert verdict.narrative_summary.startswith(
        "This niche is a strong fit for software"
    )
    assert "corpus evidence gap, not proof of weak market willingness to pay" not in (
        verdict.narrative_summary
    )
    assert verdict.key_challenges == [
        nd._PAYING_WALLET_CORPUS_CHALLENGE,
        nd._paying_wallet_buyer_note("consumer"),
    ]
    assert "subscription pricing remains viable" in verdict.key_challenges[0]
    assert forbidden not in verdict.narrative_summary
    assert verdict.buyer_class == "consumer"
    assert verdict.buyer_class_note == (
        "The end user may be a consumer, but verified niche pricing shows that buyers already "
        "fund tooling. Validate whether the paying customer is the user, an organization, or "
        "an adjacent sponsor before choosing the pricing model."
    )
    assert _commercial_copy_violations(verdict, fp) == []
    assert call_count == 2
    assert any("commercial invariant rejected" in warning for warning in warnings)


@pytest.mark.parametrize(
    "field,expected_path",
    [
        ("headline", "verdict.headline"),
        ("narrative_summary", "verdict.narrative_summary"),
        ("key_strengths", "verdict.key_strengths[0]"),
        ("key_challenges", "verdict.key_challenges[0]"),
        ("buyer_class_note", "verdict.buyer_class_note"),
    ],
)
def test_paying_wallet_invariant_scans_every_visible_commercial_string(field, expected_path):
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils.niche_difficulty import _commercial_copy_violations

    forbidden = "Avoid subscription pricing and build only a free tool."
    values = {
        "difficulty_level": "low",
        "software_addressability": 1.0,
        "headline": "Software Fit: Strong",
        "narrative_summary": "Paid pricing remains viable.",
        "key_strengths": ["Buyers already pay for tooling."],
        "key_challenges": ["Validate the paid wedge."],
        "buyer_class_note": "The paying customer has budget authority.",
    }
    values[field] = [forbidden] if field in {"key_strengths", "key_challenges"} else forbidden
    verdict = NicheDifficultyVerdict(**values)
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": "$99/mo incumbent"},
    )

    assert expected_path in {path for path, _ in _commercial_copy_violations(verdict, fp)}


def test_positive_contract_replaces_recurring_billing_paraphrase(monkeypatch):
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd

    paraphrase = (
        "Monthly recurring billing will not work here; give it away and monetise referrals."
    )
    # "give it away and monetise referrals" IS a zero-price prescription; the general rule now
    # names it. What this test still pins is the OTHER half — "recurring billing will not work
    # here" is caught by the negative-paraphrase regex, not by any named prescription.
    assert nd._paying_wallet_copy_rule_labels(paraphrase) == [
        "zero-price shape prescribed for a paying niche"
    ]
    assert nd._PAYING_WALLET_VERDICT_NEGATIVE_PARAPHRASE.search(paraphrase)

    monkeypatch.setattr(
        llm_service.LLMService,
        "invoke_structured",
        staticmethod(lambda **kw: (
            SimpleNamespace(
                headline="",
                narrative_summary=paraphrase,
                buyer_class="consumer",
            ),
            None,
        )),
    )
    evidence = "$99/mo incumbent"
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": evidence},
    )

    warnings = []
    sink_id = nd.logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        verdict, _ = generate_niche_difficulty_verdict(fp, "veterinary clinics", _nc())
    finally:
        nd.logger.remove(sink_id)

    assert verdict.narrative_summary == (
        "This niche is a strong fit for software: the pains are workflow or data problems a tool "
        "can directly own. There's room for a real product rather than a thin reference."
    )
    assert verdict.key_challenges == [
        nd._PAYING_WALLET_CORPUS_CHALLENGE,
        "The end user may be a consumer, but verified niche pricing shows that buyers already "
        "fund tooling. Validate whether the paying customer is the user, an organization, or "
        "an adjacent sponsor before choosing the pricing model.",
    ]
    assert paraphrase not in " ".join(
        copy for _, copy in nd._iter_verdict_strings(verdict.model_dump())
    )
    assert nd._commercial_copy_violations(verdict, fp) == []
    assert any("recurring paid model declared non-viable" in warning for warning in warnings)


@pytest.mark.parametrize(
    "buyer_class,expected_note",
    [
        (
            "budgeted-business",
            "Buyers here are businesses with real budget authority — direct paid pricing is viable.",
        ),
        (
            "smb-operator",
            "Buyers here are small-business operators — price-aware but used to paying for tools "
            "that save time or win customers.",
        ),
        (
            "prosumer",
            "Buyers here are prosumers paying out of pocket — expect low price ceilings and high "
            "churn on subscriptions.",
        ),
        (
            "indie-hobbyist",
            "The end user may be an indie or hobbyist buyer, while verified niche pricing shows "
            "that paid tooling already exists. Validate whether the paid customer is the user, a "
            "team, or an adjacent buyer.",
        ),
        (
            "consumer",
            "The end user may be a consumer, but verified niche pricing shows that buyers already "
            "fund tooling. Validate whether the paying customer is the user, an organization, or "
            "an adjacent sponsor before choosing the pricing model.",
        ),
        (
            "mixed",
            "Buyers here span several wallet types — pick the segment with budget authority and "
            "price for it.",
        ),
    ],
)
def test_positive_contract_final_visible_strings_for_every_buyer_class(
    monkeypatch, buyer_class, expected_note
):
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd

    monkeypatch.setattr(
        llm_service.LLMService,
        "invoke_structured",
        staticmethod(lambda **kw: (
            SimpleNamespace(
                headline=(
                    "Software Fit: Strong — automating inventory and controlled substance "
                    "compliance"
                ),
                narrative_summary=(
                    "Inventory controls and audit preparation are concrete workflows this run "
                    "can automate."
                ),
                buyer_class=buyer_class,
            ),
            None,
        )),
    )
    evidence = "$99/mo incumbent"
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": evidence},
    )

    verdict, _ = generate_niche_difficulty_verdict(fp, "veterinary clinics", _nc())

    assert verdict.headline == (
        "Software Fit: Strong — automating inventory and controlled substance compliance"
    )
    assert verdict.narrative_summary == (
        "Inventory controls and audit preparation are concrete workflows this run can automate."
    )
    assert verdict.key_strengths == [
        "Most pains are workflow or data problems a tool can directly own.",
        "There's room for a genuinely novel angle, not just a clone.",
        "Usable data is reachable without a heavy cold-start lift.",
        "Buyers in this niche demonstrably pay for tooling ($99/mo incumbent): willingness to pay "
        "is not the primary risk. Thin early signal; Deep Research validates.",
    ]
    expected_challenges = [nd._PAYING_WALLET_CORPUS_CHALLENGE]
    if buyer_class in {"prosumer", "indie-hobbyist", "consumer"}:
        expected_challenges.append(expected_note)
    assert verdict.key_challenges == expected_challenges
    assert verdict.buyer_class_note == expected_note
    assert nd._commercial_copy_violations(verdict, fp) == []
    assert "Software Fit: Strong:" not in verdict.headline


def test_compliant_run_specific_prose_is_not_replaced_by_contract_template():
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    evidence = "$99/mo incumbent"
    safe_wallet_copy = nd.paying_wallet_commercial_contract_copy("paying", evidence)
    verdict = NicheDifficultyVerdict(
        difficulty_level="medium",
        software_addressability=0.72,
        headline=(
            "Software Fit: Strong — automating inventory and controlled substance compliance"
        ),
        narrative_summary=(
            "Inventory controls and audit preparation are concrete workflows this run can automate."
        ),
        key_strengths=[
            "Controlled-substance reconciliation is a concrete workflow this product can own.",
            safe_wallet_copy,
        ],
        key_challenges=[nd._PAYING_WALLET_CORPUS_CHALLENGE],
        monetization_guidance=nd.monetization_guidance(
            {"wallet_class": "paying", "evidence": evidence}
        ),
    )
    fp = nd.NicheDifficultyFactPack(
        n_pains=4,
        n_ideas=4,
        none_share=0.0,
        partial_share=0.28,
        full_share=0.72,
        commercial_intent_max=0.4,
        difficulty_level="medium",
        software_addressability=0.72,
        wallet_class="paying",
        wallet_evidence=evidence,
    )

    reconciled = nd.reconcile_persisted_niche_difficulty_verdict(
        verdict,
        wallet_class="paying",
        wallet_evidence=evidence,
        fact_pack=fp,
        niche="independent veterinary clinics managing medication",
    )

    assert reconciled == verdict
    assert reconciled.headline != nd._FIT_HEADLINES["strong"]


def test_only_contract_violating_headline_uses_narrow_fallback():
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    evidence = "$99/mo incumbent"
    verdict = NicheDifficultyVerdict(
        difficulty_level="medium",
        software_addressability=0.72,
        headline="Software Fit: Strong: avoid subscription pricing",
        narrative_summary="Inventory controls are concrete workflows this run can automate.",
        key_strengths=[
            "Controlled-substance reconciliation is a concrete workflow this product can own.",
            nd.paying_wallet_commercial_contract_copy("paying", evidence),
        ],
        key_challenges=[nd._PAYING_WALLET_CORPUS_CHALLENGE],
        monetization_guidance=nd.monetization_guidance(
            {"wallet_class": "paying", "evidence": evidence}
        ),
    )
    fp = nd.NicheDifficultyFactPack(
        n_pains=4,
        n_ideas=4,
        none_share=0.0,
        partial_share=0.28,
        full_share=0.72,
        commercial_intent_max=0.4,
        difficulty_level="medium",
        software_addressability=0.72,
        wallet_class="paying",
        wallet_evidence=evidence,
    )

    reconciled = nd.reconcile_persisted_niche_difficulty_verdict(
        verdict,
        wallet_class="paying",
        wallet_evidence=evidence,
        fact_pack=fp,
        niche="independent veterinary clinics managing medication",
    )

    before = verdict.model_dump()
    after = reconciled.model_dump()
    changed_fields = {key for key in before if before[key] != after[key]}
    assert changed_fields == {"headline"}
    assert reconciled.headline == "Software Fit: Strong. A tool can directly own these pains"
    assert "Software Fit: Strong:" not in reconciled.headline


def test_paying_wallet_monetization_directive_uses_positive_contract():
    from nicheiq.utils.niche_difficulty import derive_monetization_directive

    pains = [SimpleNamespace(commercial_intent=0.2)]
    segments = [SimpleNamespace(payability_score=0.1)]
    legacy = derive_monetization_directive(pains, segments)
    paying = derive_monetization_directive(
        pains,
        segments,
        niche_wallet_brief={"wallet_class": "paying", "evidence": "$99/mo incumbent"},
    )
    priced_mixed = derive_monetization_directive(
        pains,
        segments,
        niche_wallet_brief={"wallet_class": "mixed", "evidence": "Truckstop $42-159/mo"},
    )

    from nicheiq.utils.niche_difficulty import (
        _MONETIZATION_WTP_LADDER, _PAYING_WALLET_MONETIZATION_DIRECTIVE,
        has_zero_price_prescription)

    # Even with no wallet brief at all, the corpus-derived branch states evidence and never
    # nominates a commercial shape (D1 round 15, Priority 1).
    assert "weak-wallet niche" in legacy
    assert not has_zero_price_prescription(legacy)
    assert paying == f"{_PAYING_WALLET_MONETIZATION_DIRECTIVE} {_MONETIZATION_WTP_LADDER}"
    # A `mixed` wallet whose evidence carries literal prices is the same contradiction as
    # `paying`; the classifier's bucket is not what makes it one (D1 round 15, Priority 2).
    assert priced_mixed == paying


def test_positive_contract_construction_failure_is_fail_soft(monkeypatch):
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd

    monkeypatch.setattr(
        llm_service.LLMService,
        "invoke_structured",
        staticmethod(lambda **kw: (
            SimpleNamespace(headline="", narrative_summary="Model prose.", buyer_class="consumer"),
            None,
        )),
    )
    monkeypatch.setattr(
        nd,
        "_build_paying_wallet_contract_verdict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad copy")),
    )
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": "$99/mo incumbent"},
    )

    verdict, _ = generate_niche_difficulty_verdict(fp, "veterinary clinics", _nc())

    assert verdict.narrative_summary == (
        "This niche has verified paying buyers. Validate which pain and paid wedge will convert."
    )
    assert verdict.key_challenges == [
        nd._PAYING_WALLET_CORPUS_CHALLENGE,
        "The end user may be a consumer, but verified niche pricing shows that buyers already "
        "fund tooling. Validate whether the paying customer is the user, an organization, or "
        "an adjacent sponsor before choosing the pricing model.",
    ]


@pytest.mark.parametrize("wallet_class,evidence,expects_weak_wtp_note,expects_paying_strength", [
    ("paying", "$99/mo incumbent", False, True),
    ("paying", "", True, False),
    ("free-culture", "most tools are free", True, False),
    ("mixed", "some pay, some do not", True, False),
    (None, "", True, False),
])
def test_wallet_strengths_and_challenges_never_prescribe_opposites(
    wallet_class, evidence, expects_weak_wtp_note, expects_paying_strength
):
    from nicheiq.utils import niche_difficulty as nd

    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    brief = ({"wallet_class": wallet_class, "evidence": evidence, "free_density": "unknown"}
             if wallet_class else None)

    fp = assess_niche_difficulty(
        pains, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    strengths = " ".join(fp.key_strengths)

    assert ("demonstrably pay for tooling" in strengths) is expects_paying_strength
    assert (nd._WEAK_WTP_CHALLENGE in fp.key_points) is expects_weak_wtp_note
    assert not (expects_paying_strength and nd._WEAK_WTP_CHALLENGE in fp.key_points)
    # The two used to be able to contradict each other because the weak-WTP point PRESCRIBED a
    # non-paying shape. It no longer prescribes anything, and neither may any other key point.
    assert not any(nd.has_zero_price_prescription(point) for point in fp.key_points)
    assert not any(nd.has_zero_price_prescription(point) for point in fp.key_strengths)


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


# --- niche wallet probe (2026-07-09) ----------------------------------------------

def test_wallet_brief_none_is_backward_compatible():
    # Omitting niche_wallet_brief entirely must behave identically to today.
    fp_default = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    fp_explicit_none = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=None)
    assert fp_default.key_points == fp_explicit_none.key_points
    assert fp_default.wallet_class is None
    assert fp_explicit_none.wallet_class is None


def test_free_culture_wallet_appends_keypoint():
    from nicheiq.utils.niche_difficulty import _wallet_challenge
    brief = {"wallet_class": "free-culture", "evidence": "$0-25/mo total, start free",
              "free_density": "high"}
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    assert fp.wallet_class == "free-culture"
    assert _wallet_challenge("$0-25/mo total, start free") in fp.key_points


def test_paying_wallet_no_keypoint():
    brief = {"wallet_class": "paying", "evidence": "tools run $19-59/mo", "free_density": "low"}
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    assert fp.wallet_class == "paying"
    assert not any("free-tool culture" in k for k in fp.key_points)


def test_free_culture_wallet_deduped_against_substitute_challenge():
    from nicheiq.utils.niche_difficulty import _SUBSTITUTE_CHALLENGE
    ideas = [_cidea(parity="substitute (x): y") for _ in range(4)]
    brief = {"wallet_class": "free-culture", "evidence": "start free", "free_density": "high"}
    fp = assess_niche_difficulty([_pain()] * 4, ideas, _nc(), niche_wallet_brief=brief)
    assert _SUBSTITUTE_CHALLENGE in fp.key_points
    assert not any("free-tool culture" in k for k in fp.key_points)


def test_free_culture_wallet_deduped_against_weak_wtp_challenge():
    from nicheiq.utils.niche_difficulty import _WEAK_WTP_CHALLENGE
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.3) for _ in range(4)]
    brief = {"wallet_class": "free-culture", "evidence": "start free", "free_density": "high"}
    fp = assess_niche_difficulty(pains, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    assert _WEAK_WTP_CHALLENGE in fp.key_points
    assert not any("free-tool culture" in k for k in fp.key_points)


def test_strengths_never_leak_into_key_challenges(monkeypatch):
    """A strong-fit niche accrues frictions too, and both used to share one list surfaced as
    `key_challenges` — so ReportBrief printed "There's room for a genuinely novel angle" as
    the run's primary concern. The two polarities must stay separated."""
    _patch_llm_headline(monkeypatch, "")
    pains = [_pain("full")] * 6
    ideas = [_idea(novelty=0.6)] * 4
    fp = assess_niche_difficulty(pains, ideas, _nc())
    v, _ = generate_niche_difficulty_verdict(fp, "x", _nc())

    assert v.key_strengths, "a fully-addressable niche should report strengths"
    encouragements = [p for p in v.key_challenges if "room for a genuinely novel angle" in p
                      or "can directly own" in p or "without a heavy cold-start" in p]
    assert not encouragements, f"strengths leaked into key_challenges: {encouragements}"


def test_paying_wallet_positive_keypoint():
    from nicheiq.utils.niche_difficulty import _wallet_positive_note
    brief = {"wallet_class": "paying", "evidence": "tools run $19-59/mo", "free_density": "low"}
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    assert fp.wallet_class == "paying"
    # A positive signal belongs in key_strengths; key_points is frictions-only.
    assert _wallet_positive_note("tools run $19-59/mo") in fp.key_strengths
    assert _wallet_positive_note("tools run $19-59/mo") not in fp.key_points


def test_mixed_wallet_no_keypoint():
    brief = {"wallet_class": "mixed", "evidence": "some pay, some don't", "free_density": "medium"}
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)
    assert fp.wallet_class == "mixed"
    assert not any("demonstrably pay" in k for k in fp.key_points)
    assert not any("free-tool culture" in k for k in fp.key_points)


# --- incumbent map probe (2026-07-10) -----------------------------------------------

def _row(name, pricing="", focus="", gap="", source=""):
    return {"name": name, "pricing": pricing, "focus": focus, "gap": gap, "source": source}


def test_incumbent_map_none_is_backward_compatible():
    fp_default = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    fp_explicit_none = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), incumbent_map=None)
    assert fp_default.key_points == fp_explicit_none.key_points
    assert fp_default.incumbent_count is None and fp_default.priced_count is None
    assert fp_explicit_none.incumbent_count is None and fp_explicit_none.priced_count is None


def test_incumbent_map_dense_fires_keypoint_and_counts():
    rows = [_row(f"Tool {i}", pricing="$19/mo") for i in range(6)] + \
        [_row("Tool 6", pricing="unknown"), _row("Tool 7", pricing="")]
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), incumbent_map=rows)
    assert fp.incumbent_count == 8
    assert fp.priced_count == 6
    assert any("dense tool ecosystem" in k and "8 tools web-verified, 6 with published pricing" in k
               for k in fp.key_points)
    assert any(k.endswith("Thin early signal; Deep Research validates.") for k in fp.key_points)


def test_incumbent_map_below_threshold_no_keypoint():
    rows = [_row(f"Tool {i}", pricing="$19/mo") for i in range(7)]
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), incumbent_map=rows)
    assert fp.incumbent_count == 7
    assert not any("dense tool ecosystem" in k for k in fp.key_points)


def test_incumbent_map_priced_count_detects_digits_and_dollar_sign():
    rows = [_row("A", pricing="Free"), _row("B", pricing="$0"), _row("C", pricing="Contact us"),
            _row("D", pricing="From 10 EUR")]
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), incumbent_map=rows)
    assert fp.incumbent_count == 4
    assert fp.priced_count == 2  # "$0" and "From 10 EUR" carry a digit/$; "Free"/"Contact us" don't


# --- SERP-owned probe (2026-07-10) ----------------------------------------------------

def test_serp_owned_share_none_is_backward_compatible():
    fp_default = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    fp_explicit_none = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), serp_owned_share=None)
    assert fp_default.key_points == fp_explicit_none.key_points
    assert fp_default.serp_owned_share is None
    assert fp_explicit_none.serp_owned_share is None


def test_serp_owned_heavy_fires_keypoint():
    from nicheiq.utils.niche_difficulty import _SERP_OWNED_CHALLENGE
    fp = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), serp_owned_share=0.5)
    assert fp.serp_owned_share == 0.5
    assert _SERP_OWNED_CHALLENGE in fp.key_points

    fp_below = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(), serp_owned_share=0.49)
    assert _SERP_OWNED_CHALLENGE not in fp_below.key_points


# --- all-None regression across every new kwarg simultaneously ------------------------

def test_all_new_inputs_none_together_is_byte_identical_to_legacy():
    baseline = assess_niche_difficulty([_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc())
    with_defaults = assess_niche_difficulty(
        [_pain()] * 4, [_idea(novelty=0.6)] * 4, _nc(),
        incumbent_map=None, serp_owned_share=None, niche_wallet_brief=None)
    assert baseline == with_defaults


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


# --- adversarial commercial paraphrase corpus ------------------------------------------
#
# The paying-wallet contract is defeated by paraphrase whenever "allowed" means "mentions
# money positively-sounding words". Each entry below is a NOVEL sentence — none of them
# contains a phrase any forbidden-copy rule names — that takes a commercial stance the
# codebase never authored. A1-A8 are the reproduction set a blind critic used to defeat the
# permissive allowlist (A2 was published end-to-end on a `paying` card). N1-N6 were written
# afterwards, against the tightened contract, and had never been seen by it.

PAYING_WALLET_COMMERCIAL_ATTACKS = {
    "A1": (
        "Buyers here treat every purchase as discretionary, so recurring plans churn out "
        "fast; ship it free and earn from partner placements."
    ),
    "A2": (
        "Customers fund tools only when a crisis hits, so a monthly plan will sit unused and "
        "cancel; price per incident instead."
    ),
    "A3": (
        "Willingness to pay among these buyers is thin outside a one-off transaction, so "
        "recurring revenue is the wrong bet here."
    ),
    "A4": (
        "The realistic model is a no-charge utility with sponsor placements, because buyers "
        "already pay incumbents and won't add another line item."
    ),
    "A5": (
        "Customers purchase once and never renew, so build the seat licence as a perpetual "
        "key rather than a recurring plan."
    ),
    "A6": (
        "These buyers pay their vendors on net-60 and keep software wallets shallow, so any "
        "repeating charge is a losing wedge."
    ),
    "A7": "Expect these customers to sign one contract and never renew; bill per incident.",
    "A8": "Nobody in this space keeps a tool on a card month after month.",
    "N1": (
        "Treat this as a tip-jar category: leave the core open to everyone and let a sponsor "
        "underwrite the hosting bill."
    ),
    "N2": (
        "Dispatchers here already run three tools they resent paying for, so a fourth line "
        "item is a hard no; monetise the data instead."
    ),
    "N3": (
        "The wedge that survives here is a one-and-done export you sell for a flat fee at tax "
        "season, not something billed every quarter."
    ),
    "N4": (
        "Renewal conversations in this trade end at 'we only needed it once', so anchor the "
        "model on credits that expire."
    ),
    "N5": (
        "Owners here guard their card details closely and treat any repeating debit as an "
        "expense to cut first."
    ),
    "N6": (
        "Reaching for a per-user tier would stall adoption; the durable shape is a shared "
        "community utility supported by vendor sponsorships."
    ),
}

_ATTACK_CASES = sorted(PAYING_WALLET_COMMERCIAL_ATTACKS.items())
_PAYING_EVIDENCE = "$99/mo incumbent"


def _paying_fact_pack():
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    return assess_niche_difficulty(
        pains,
        [_idea(novelty=0.6)] * 4,
        _nc(),
        niche_wallet_brief={"wallet_class": "paying", "evidence": _PAYING_EVIDENCE},
    )


def _paying_verdict(**overrides):
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    values = {
        "difficulty_level": "medium",
        "software_addressability": 0.72,
        "headline": "Software Fit: Strong — automating controlled substance compliance",
        "narrative_summary": (
            "Inventory controls and audit preparation are concrete workflows this run can "
            "automate."
        ),
        "key_strengths": [
            "Controlled-substance reconciliation is a concrete workflow this product can own.",
            nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE),
        ],
        "key_challenges": [nd._PAYING_WALLET_CORPUS_CHALLENGE],
        "buyer_class": "smb-operator",
        "buyer_class_note": nd._BUYER_CLASS_NOTES["smb-operator"],
    }
    values.update(overrides)
    return NicheDifficultyVerdict(**values)


def test_no_bespoke_phrase_carve_out_hides_inside_the_topic_boundary():
    """The topic boundary is a vocabulary, not a rebuilt phrase list.

    An earlier round made the only adversarial test pass by appending a literal
    "give it away" alternative to the topic regex — a phrase list inside the boundary that
    was supposed to replace phrase lists.
    """
    from nicheiq.utils import niche_difficulty as nd

    assert "give" not in nd._COMMERCIAL_COPY_TOPIC_RE.pattern
    assert "away" not in nd._COMMERCIAL_COPY_TOPIC_RE.pattern
    assert nd.has_unsanctioned_commercial_claim(
        "Monthly recurring billing will not work here; give it away and monetise referrals."
    )


@pytest.mark.parametrize("label,attack", _ATTACK_CASES)
@pytest.mark.parametrize(
    "field,expected_path",
    [
        ("headline", "verdict.headline"),
        ("narrative_summary", "verdict.narrative_summary"),
        ("key_strengths", "verdict.key_strengths[0]"),
        ("key_challenges", "verdict.key_challenges[0]"),
        ("buyer_class_note", "verdict.buyer_class_note"),
    ],
)
def test_commercial_paraphrase_is_rejected_on_the_verdict_path(
    field, expected_path, label, attack
):
    from nicheiq.utils import niche_difficulty as nd

    value = [attack] if field in {"key_strengths", "key_challenges"} else attack
    verdict = _paying_verdict(**{field: value})

    violations = nd._commercial_copy_violations(verdict, _paying_fact_pack())

    assert expected_path in {path for path, _ in violations}, label


@pytest.mark.parametrize("label,attack", _ATTACK_CASES)
def test_commercial_paraphrase_never_survives_verdict_reconciliation(label, attack):
    from nicheiq.utils import niche_difficulty as nd

    fp = _paying_fact_pack()
    verdict = _paying_verdict(narrative_summary=attack, key_strengths=[attack])

    reconciled = nd.reconcile_persisted_niche_difficulty_verdict(
        verdict,
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        fact_pack=fp,
        niche="independent veterinary clinics managing medication",
    )

    published = " ".join(copy for _, copy in nd._iter_verdict_strings(reconciled.model_dump()))
    assert attack not in published, label
    assert nd._commercial_copy_violations(reconciled, fp) == []


@pytest.mark.parametrize("label,attack", _ATTACK_CASES)
def test_commercial_paraphrase_is_rejected_on_the_portfolio_summary_path(label, attack):
    from nicheiq.utils.niche_difficulty import (
        paying_wallet_commercial_contract_copy,
        paying_wallet_commercial_copy_violations,
        reconcile_persisted_paying_wallet_summary,
    )

    contract_copy = paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)
    # The hardest shape: the sanctioned statement IS present, so only the surrounding claim
    # can give the paraphrase away.
    summary = f"{contract_copy} {attack}"

    violations = paying_wallet_commercial_copy_violations(
        summary,
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        expected_copy=contract_copy,
        allow_surrounding_copy=True,
    )

    assert "commercial copy outside sanctioned paying-wallet statement" in violations, label
    assert reconcile_persisted_paying_wallet_summary(
        summary, wallet_class="paying", wallet_evidence=_PAYING_EVIDENCE
    ) == contract_copy


def test_sanctioned_commercial_copy_is_still_publishable():
    """The tightened boundary must not reject the statements this codebase authors."""
    from nicheiq.utils import niche_difficulty as nd

    publishable = [
        nd._wallet_positive_note(""),
        nd._wallet_positive_note("$99-399/mo DaySmart Vet"),
        # The em-dash generation still on disk in older checkpoints.
        nd._wallet_positive_note("Truckstop $42-159/mo").replace(": willingness", " — willingness"),
        nd._PAYING_WALLET_CORPUS_CHALLENGE,
        nd._PAYING_WALLET_MONETIZATION_DIRECTIVE,
        nd._PAYING_WALLET_CONSUMER_BUYER_NOTE,
        nd._PAYING_WALLET_INDIE_BUYER_NOTE,
        nd._incumbent_density_challenge(8, 2),
        nd._BUYER_CLASS_NOTES["budgeted-business"],
        nd._BUYER_CLASS_NOTES["smb-operator"],
        nd._BUYER_CLASS_NOTES["mixed"],
        nd._BUYER_CLASS_NOTES["prosumer"],
        "Paid pricing remains viable.",
        # Real run prose that is not about money at all.
        "Most ideas need a data corpus that doesn't exist yet — plan a cold-start play "
        "(seed it, scrape it, or partner) before the product is useful.",
        "Software Fit: Moderate — Focus on advice, not automation, for marketplace sellers",
        "Inventory controls and audit preparation are concrete workflows this run can automate.",
    ]

    rejected = [copy for copy in publishable if nd.has_unsanctioned_commercial_claim(copy)]
    assert rejected == []


def test_generic_low_payability_buyer_notes_stay_rejected_on_a_paying_wallet():
    """The consumer/indie generics assert weak willingness to pay: never sanctioned here."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_unsanctioned_commercial_claim(nd._BUYER_CLASS_NOTES["consumer"])
    assert nd.has_unsanctioned_commercial_claim(nd._BUYER_CLASS_NOTES["indie-hobbyist"])
    # `_WEAK_WTP_CHALLENGE` used to belong here because it asserted a commercial shape. Rewritten
    # as a fact (D1 round 15, Priority 1) it says nothing about money at all, so there is nothing
    # left for the boundary to reject — see test_niche_difficulty_constants_are_facts.py, which
    # enforces that it stays that way.
    assert not nd.has_unsanctioned_commercial_claim(nd._WEAK_WTP_CHALLENGE)
    # `_EPISODIC_CHALLENGE` is the deliberate other case (D1 round 16, Priority 3). Its
    # "subscriptions churn in that shape; favor one-time purchases, credits, or usage-based
    # pricing" names only PAID shapes, so it prescribes no zero-price shape and stays a legal
    # fact-pack point in general. It still ARGUES about subscriptions, which is precisely what a
    # verified paying wallet has evidence against — so this wallet-scoped, deny-by-default
    # boundary keeps rejecting it, and the verdict card drops it there rather than everywhere.
    assert nd.has_unsanctioned_commercial_claim(nd._EPISODIC_CHALLENGE)
    assert not nd.has_zero_price_prescription(nd._EPISODIC_CHALLENGE)


def test_short_sanctioned_phrases_do_not_license_a_fresh_commercial_sentence():
    """A fragment never sanctions the sentence it was dropped into."""
    from nicheiq.utils import niche_difficulty as nd

    assert not nd.has_unsanctioned_commercial_claim(
        nd._BUYER_CLASS_NOTES["budgeted-business"]
    )
    # "buyer" is an audience noun, so the fragment plus an audience fact is not a money claim.
    # Adding a novel money claim beside the same fragment still is.
    assert not nd.has_unsanctioned_commercial_claim(
        "The buyer with budget authority is the clinic owner, not the vet tech."
    )
    assert nd.has_unsanctioned_commercial_claim(
        "The buyer holds budget authority and renews a monthly plan without prompting."
    )
    assert nd.has_unsanctioned_commercial_claim(
        "Budget authority is absent here, so nothing recurring will clear procurement."
    )
    assert nd.has_unsanctioned_commercial_claim(
        "Published pricing exists, but these buyers never renew past the first invoice."
    )


# ---------------------------------------------------------------------------
# Round 12: scope the deny-by-default boundary, and close what it never covered.
# ---------------------------------------------------------------------------

# Registers a paying-wallet contradiction reaches for once the obvious money nouns are watched.
# Every one of these survived all three publication paths before this round.
NOVEL_REGISTER_ATTACKS = {
    "N1-checkbook": "Nobody in this niche opens a checkbook for tooling like this.",
    "N2-no-money": "There is simply no money in this audience for a tool of this kind.",
    "N3-invoice": (
        "Send an invoice here and it goes unsigned; a retainer arrangement is the wrong shape."
    ),
    "N4-split-sentence": (
        "Ask what these operators do when a vendor comes asking for money. "
        "They walk away every time."
    ),
    "N5-quotation": (
        'One operator said it plainly: "I would never open my checkbook for something like this."'
    ),
    "N6-list-item": (
        "- Commercial reality: treat this as a handout; the audience does not reach for a "
        "checkbook."
    ),
    "N7-litotes": "Commercial appetite here is anything but robust, so keep the ask at zero.",
    "N8-euphemism": (
        "Expect procurement conversations here to stall permanently; plan for an unpaid "
        "distribution motion."
    ),
}

_NOVEL_CASES = sorted(NOVEL_REGISTER_ATTACKS.items())


@pytest.mark.parametrize("label,attack", _NOVEL_CASES)
def test_novel_register_attack_is_rejected_on_the_verdict_path(label, attack):
    from nicheiq.utils import niche_difficulty as nd

    verdict = _paying_verdict(narrative_summary=attack)
    violations = nd._commercial_copy_violations(verdict, _paying_fact_pack())

    assert "verdict.narrative_summary" in {path for path, _ in violations}, label


@pytest.mark.parametrize("label,attack", _NOVEL_CASES)
def test_novel_register_attack_never_survives_verdict_reconciliation(label, attack):
    from nicheiq.utils import niche_difficulty as nd

    fp = _paying_fact_pack()
    reconciled = nd.reconcile_persisted_niche_difficulty_verdict(
        _paying_verdict(narrative_summary=attack, key_strengths=[attack]),
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        fact_pack=fp,
        niche="independent veterinary clinics managing medication",
    )

    published = " ".join(copy for _, copy in nd._iter_verdict_strings(reconciled.model_dump()))
    assert attack not in published, label


@pytest.mark.parametrize("label,attack", _NOVEL_CASES)
def test_novel_register_attack_is_rejected_on_the_portfolio_summary_path(label, attack):
    from nicheiq.utils import niche_difficulty as nd

    contract_copy = nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)

    violations = nd.paying_wallet_summary_copy_violations(
        f"{contract_copy} {attack}",
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        expected_copy=contract_copy,
    )

    assert violations, label


@pytest.mark.parametrize(
    "negation",
    [
        "Budget authority is far from established.",
        "Verified niche pricing stops short of proving anything.",
        "Budget authority here is anything but real.",
        "Published pricing is illusory for this segment.",
    ],
)
def test_understated_negation_does_not_sanction_itself(negation):
    """A sanctioned FRAGMENT inside a sentence that denies it is not sanctioned copy."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_unsanctioned_commercial_claim(negation)


@pytest.mark.parametrize(
    "compliant",
    [
        # The negation belongs to a different clause; it says nothing about "budget authority".
        "The buyer with budget authority is the clinic owner, not the vet tech.",
        "Published pricing exists for three tools; none of the rest are relevant to this workflow.",
        # "plan" here is a verb, not a pricing tier.
        "The team plans a cold-start play.",
        # Audience descriptors, not stances about money.
        "Home bakers selling cakes from a domestic kitchen are the audience.",
        "Marketplace sellers are the operators this run is about.",
    ],
)
def test_unrelated_negation_does_not_disarm_compliant_copy(compliant):
    from nicheiq.utils import niche_difficulty as nd

    assert not nd.has_unsanctioned_commercial_claim(compliant)


def test_pricing_sense_of_plan_is_still_a_commercial_claim():
    """Dropping "team"/"pro" from the plans qualifier must not drop the pricing sense."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_unsanctioned_commercial_claim("Nobody upgrades past the entry plan.")
    assert nd.has_unsanctioned_commercial_claim("The starter plan is the only one that sells.")


def test_wallet_evidence_slot_cannot_smuggle_a_contradiction():
    """The parenthetical is model-produced web text inside the contract's own statement."""
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    evidence = (
        "Truckstop $42/mo, but most dispatchers refuse monthly fees and stay on free spreadsheets"
    )
    # 1. It never gets interpolated in the first place.
    authored = nd._wallet_positive_note(evidence)
    assert "refuse monthly fees" not in authored
    assert authored == nd._wallet_positive_note("")

    # 2. And a copy already persisted with it is caught rather than swallowed.
    persisted = (
        f"Buyers in this niche demonstrably pay for tooling ({evidence}): willingness to pay "
        "is not the primary risk. Thin early signal; Deep Research validates."
    )
    assert evidence in nd._unsanctioned_commercial_residue(persisted)
    assert nd.has_unsanctioned_commercial_claim(persisted)

    reconciled = nd.reconcile_persisted_niche_difficulty_verdict(
        NicheDifficultyVerdict(
            difficulty_level="medium",
            software_addressability=0.6,
            headline="Software Fit: Moderate",
            narrative_summary="Inventory reconciliation is a concrete workflow to own.",
            key_challenges=[],
            key_strengths=[persisted],
            low_confidence=False,
        ),
        wallet_class="paying",
        wallet_evidence=evidence,
    )
    published = " ".join(copy for _, copy in nd._iter_verdict_strings(reconciled.model_dump()))
    assert "refuse monthly fees" not in published

    # A genuine price list is still published.
    assert "$99-399/mo DaySmart Vet" in nd._wallet_positive_note("$99-399/mo DaySmart Vet")


def test_compliant_narrative_sentences_filters_rather_than_truncates():
    """A violation in sentence 1 must not delete compliant sentences 2 and 3."""
    from nicheiq.utils import niche_difficulty as nd

    narrative = (
        "Buyers here will not pay for another tool. "
        "Inventory controls and audit preparation are concrete workflows this run can automate. "
        "Most ideas still need a data corpus that does not exist yet."
    )

    kept = nd._compliant_narrative_sentences(narrative)

    assert kept == (
        "Inventory controls and audit preparation are concrete workflows this run can automate. "
        "Most ideas still need a data corpus that does not exist yet."
    )


def test_compliant_narrative_sentences_keeps_a_lone_survivor():
    """The old >=2 floor threw away the last compliant sentence in the document."""
    from nicheiq.utils import niche_difficulty as nd

    narrative = (
        "Willingness to pay is weak across the board. "
        "Inventory controls are a concrete workflow this run can automate."
    )

    assert nd._compliant_narrative_sentences(narrative) == (
        "Inventory controls are a concrete workflow this run can automate."
    )


def test_compliant_narrative_sentences_drops_a_middle_violator_only():
    from nicheiq.utils import niche_difficulty as nd

    narrative = (
        "The corpus drifts from the stated audience. "
        "Buyers here will not pay for another subscription. "
        "Usable data is reachable without a heavy cold-start lift."
    )

    assert nd._compliant_narrative_sentences(narrative) == (
        "The corpus drifts from the stated audience. "
        "Usable data is reachable without a heavy cold-start lift."
    )


def test_compliant_narrative_sentences_returns_nothing_when_all_violate():
    from nicheiq.utils import niche_difficulty as nd

    assert nd._compliant_narrative_sentences(
        "Buyers here will not pay. Willingness to pay is weak."
    ) == ""


def test_audience_descriptor_does_not_destroy_a_whole_narrative():
    """A real narrative was replaced by the generic template over the word "selling"."""
    from nicheiq.utils import niche_difficulty as nd

    narrative = (
        "Home bakers selling cakes from a domestic kitchen face licensing and labelling work "
        "a tool can own. Most ideas still need a data corpus that does not exist yet."
    )

    assert nd._compliant_narrative_sentences(narrative) == narrative


def test_per_idea_payability_commentary_is_publishable_in_a_summary():
    """The summary's job includes per-idea payability; that is not a niche wallet claim.

    Measured over the persisted corpus, the verdict card's polarity-blind boundary rejected the
    portfolio summary essentially always, because commercial vocabulary IS its subject matter.
    """
    from nicheiq.utils import niche_difficulty as nd

    contract_copy = nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)
    summary = (
        "AutoBondClaim has limited market fit and weak buyer payability, with a pricing model "
        "that might lead to churn. LoadLedger targets personal wallets rather than business "
        "budgets, while BondClaim Coach has good buyer payability and SEO scalability. "
        f"{contract_copy}"
    )

    assert nd.paying_wallet_summary_copy_violations(
        summary,
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        expected_copy=contract_copy,
    ) == []
    # The verdict card is a different contract and still refuses all of it.
    assert nd.has_unsanctioned_commercial_claim(summary)


def test_niche_level_wallet_contradiction_is_still_rejected_in_a_summary():
    from nicheiq.utils import niche_difficulty as nd

    contract_copy = nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)
    for contradiction in (
        "The entire pool reflects a market where willingness-to-pay is consistently weak.",
        "This niche is heavily influenced by a free-culture mentality, with no established "
        "paid software market.",
        "The target audience lacks the budget to support a dedicated subscription.",
    ):
        assert nd.paying_wallet_summary_copy_violations(
            f"{contract_copy} {contradiction}",
            wallet_class="paying",
            wallet_evidence=_PAYING_EVIDENCE,
            expected_copy=contract_copy,
        ), contradiction


def test_persisted_summary_reconciliation_keeps_the_analysis():
    """D1: remove the contradiction, not the paid deliverable."""
    from nicheiq.utils import niche_difficulty as nd

    contract_copy = nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)
    summary = (
        "The current idea pool is constrained by incumbents like VetSnap. "
        "DEAAuditChecklistGen and NDCShiftVet both suffer from limited market fit.\n\n"
        "The entire pool reflects a market where willingness-to-pay is consistently weak. "
        "DispenseSpeedBench and Fallback Ledger most deserve deep validation next."
    )

    reconciled = nd.reconcile_persisted_paying_wallet_summary(
        summary, wallet_class="paying", wallet_evidence=_PAYING_EVIDENCE
    )

    assert "willingness-to-pay is consistently weak" not in reconciled
    assert "DEAAuditChecklistGen and NDCShiftVet" in reconciled
    assert "DispenseSpeedBench and Fallback Ledger" in reconciled
    assert reconciled.startswith("The current idea pool is constrained by incumbents")
    assert reconciled.count(contract_copy) == 1
    assert nd.paying_wallet_summary_copy_violations(
        reconciled,
        wallet_class="paying",
        wallet_evidence=_PAYING_EVIDENCE,
        expected_copy=contract_copy,
    ) == []


# =============================================================================================
# D1 (round 13): zero-price / alternative-funding PRESCRIPTIONS.
#
# A prescription is a negative conclusion with no valence word in it. Rounds 1-3, 10, 11 and 12
# all keyed on negative vocabulary and were structurally blind to this whole register, which is
# where D1 actually lives: on the round-12 code every one of the thirteen paraphrases below
# published verbatim on the summary path, alongside "Buyers in this niche demonstrably pay for
# tooling".
#
# X*/Y* are the critic's thirteen. Z* are six more written afterwards, against the finished
# rule, to check it generalises past the set it was built from.
# =============================================================================================

_CRITIC_PRESCRIPTIONS = {
    "X1": "Treat this as a marketing asset for the agency rather than something the shops buy.",
    "X2": "Keep the tool complimentary for the whole trade and let a vendor cover the hosting.",
    "X3": "Take payment once at install and let the licence run forever for these shops.",
    "X4": "Position it as a giveaway that earns goodwill with these operators.",
    "X5": "Budgets here get approved long after the quarter you needed the cash in.",
    "X6": "Hand the finished tool to the community as a gift and fund it from consulting "
          "elsewhere.",
    "Y1": "The realistic route for this trade is a no-charge utility that feeds a services "
          "pipeline.",
    "Y2": "Make it a lead magnet for the audience instead of a product they purchase.",
    "Y4": "A one-time licence fits this audience better than a monthly plan.",
    "Y6": "Open-source the whole thing and let the community run it themselves.",
    "Y7": "Lifetime deals are the right instrument for this community.",
    "Y8": "Fund it with donations from the shops that get value out of it.",
    "Y9": "Perpetual licences suit these operators better than recurring billing.",
}

_NOVEL_PRESCRIPTIONS = {
    "Z1": "The sensible course here is a community-maintained utility funded by the trade "
          "association.",
    "Z2": "Ship it as a free companion to the consultancy work and bill the engagements "
          "separately.",
    "Z3": "For this trade the natural shape is a grant-funded public utility.",
    "Z4": "Consider handing the tool to the industry body and letting them host it for "
          "everyone.",
    "Z5": "The obvious play for these shops is a perpetual seat licence bought once at rollout.",
    "Z6": "Best to launch it as a loss leader that pulls audit work into the practice.",
}

_ALL_PRESCRIPTIONS = {**_CRITIC_PRESCRIPTIONS, **_NOVEL_PRESCRIPTIONS}

# The live D1 artifact's own sentence, quoted from
# output/checkpoints/checkpoint_independent_veterinary_clinics_managing_medication_51a491dc…
_D1_LIVE_SENTENCE = (
    "Given the market reality that subscription models are poorly received, the most promising "
    "path forward is to pivot toward a free, lead-generation-focused tool rather than a "
    "standalone product."
)

# Prose that NAMES the same shapes without recommending them. These must stay publishable: a
# rule that refuses them is a closed gate, which is how round 11 failed (55/55 rejected).
_REPORTS_NOT_PRESCRIPTIONS = {
    "R1": "Concepts such as DEAAuditChecklistGen suffer from limited market fit because they "
          "attempt to solve problems already addressed by free, integrated tools within the "
          "PIMS ecosystem.",
    "R2": "ReviewRequestTimingBench faces direct competition from free, bundled features "
          "already offered by major industry players like Toast.",
    "R3": "QuickBooksSyncFixer could be viable if you pivot to a usage-based pricing model "
          "rather than a traditional subscription.",
    "R4": "SurveyScoreAttributionFilter and ReviewComplianceGuard are the only two ideas that "
          "deserve further validation.",
    "R5": "Open-source alternatives already cover half of this workflow.",
    "R6": "Incumbents in this space are ad-funded and give the basic tier away.",
}


def _prescription_paths(copy: str) -> dict:
    """Run one string through every publication path that can carry a commercial claim."""
    from nicheiq.utils import niche_difficulty as nd

    contract = nd.paying_wallet_commercial_contract_copy("paying", _PAYING_EVIDENCE)
    slot_evidence = f"{_PAYING_EVIDENCE}. {copy}"
    slot_note = nd._wallet_positive_note(slot_evidence)
    return {
        "summary": bool(nd.paying_wallet_summary_copy_violations(
            f"{copy}\n\n{contract}",
            wallet_class="paying",
            wallet_evidence=_PAYING_EVIDENCE,
            expected_copy=contract,
        )),
        "verdict": bool(nd.paying_wallet_commercial_copy_violations(
            f"{copy} {contract}",
            wallet_class="paying",
            wallet_evidence=_PAYING_EVIDENCE,
            expected_copy=contract,
            allow_surrounding_copy=True,
        )),
        # The slot is the free text the contract's own sentence interpolates. "Refused" here
        # means the prescription never reaches the published statement at all.
        "slot": copy.rstrip(".") not in slot_note,
    }


@pytest.mark.parametrize("label", sorted(_ALL_PRESCRIPTIONS))
@pytest.mark.parametrize("path", ["summary", "verdict", "slot"])
def test_zero_price_prescription_is_refused_on_every_path(label, path):
    assert _prescription_paths(_ALL_PRESCRIPTIONS[label])[path], (
        f"{label} published on the {path} path: {_ALL_PRESCRIPTIONS[label]!r}"
    )


def test_live_d1_sentence_is_refused_on_every_path():
    assert all(_prescription_paths(_D1_LIVE_SENTENCE).values())


@pytest.mark.parametrize("label", sorted(_REPORTS_NOT_PRESCRIPTIONS))
def test_reporting_a_zero_price_shape_stays_publishable(label):
    """CLOSED-GATE GUARD: naming a free/ad-funded/one-time shape is not recommending it.

    The mood conjunct is the only thing separating this rule from round 11's permanently-closed
    gate. Deleting it makes every one of these fail.
    """
    from nicheiq.utils import niche_difficulty as nd

    copy = _REPORTS_NOT_PRESCRIPTIONS[label]
    assert not nd.has_zero_price_prescription(copy), copy


def test_prescription_detector_needs_mood_and_object_in_one_sentence():
    """Mood in one sentence and object in the next is not a prescription."""
    from nicheiq.utils import niche_difficulty as nd

    assert not nd.has_zero_price_prescription(
        "The best route here is a paid audit workflow. Free spreadsheets are what they use now."
    )


def test_medical_prescribing_is_not_a_recommendation_mood():
    """R14.1: `prescrib\\w*` read a medical participle as a deontic.

    The corpus sentence below REPORTS free Reddit alternatives and names prescribing physicians
    as a market fact; it recommends nothing. Widening the deontic back to `prescrib\\w*` makes
    the first assertion fail, and dropping the alternative entirely makes the second fail.
    """
    from nicheiq.utils import niche_difficulty as nd

    corpus_sentence = (
        "GLP-1 Off-Ramp Navigator, while scalable, is weakened by the existence of free "
        "alternatives on platforms like Reddit and the inherent role of prescribing physicians "
        "in managing dose adjustments."
    )
    assert not nd.has_zero_price_prescription(corpus_sentence)
    # The recommendation sense takes a nominal object, and still bites.
    assert nd.has_zero_price_prescription(
        "For this trade I would prescribe a free companion tool, not a paid one."
    )
    assert nd.has_zero_price_prescription(
        "The reviewers prescribed a donation-funded utility for these clinics."
    )


# ---------------------------------------------------------------------------
# ROUND 14 — the measured ceiling of the surface-text backstop.
#
# A blind critic published these through the real entry point next to "Buyers in this niche
# demonstrably pay for tooling". They are recorded here so the ceiling is a fact in the suite
# rather than a claim in a report: the backstop is a BACKSTOP, and the actual fix is that the
# generators are no longer licensed to select a commercial shape at all
# (see test_generator_prompts_withdraw_the_commercial_shape_license).
#
# OBJECT — 13 of 14 name a shape in which this audience does not pay, in vocabulary no list
# anticipated. MOOD — 6 of 14 recommend a plainly-covered zero-price object in a register the
# mood conjunct does not recognise.
# ---------------------------------------------------------------------------
_R14_OBJECT_ATTACKS = {
    "revenue-share": "Take a revenue share of every prescription the clinic fills instead of "
                     "charging them a subscription.",
    "equity-for-access": "Trade access to the ledger for a small equity stake in each practice "
                         "rather than invoicing them.",
    "barter": "Barter the tool for the clinic's anonymised dispensing data instead of billing "
              "for it.",
    "membership-dues": "Fold the tool into the state association's membership dues so no clinic "
                       "ever sees an invoice.",
    "freemium-no-paid-tier": "Ship it as a permanently free tier with no paid plan behind it.",
    "cost-recovery": "Run it at cost recovery so the clinics only ever cover hosting.",
    "insurer-reimbursed": "Have the pet insurers reimburse the tool so the clinic never pays "
                          "for it.",
    "bill-the-wholesaler": "Bill the drug wholesaler for the integration and hand the clinics "
                           "the tool for nothing.",
    "platform-credits": "Settle in platform credits rather than cash so the practices never "
                        "open their wallets.",
    "data-exhaust": "Monetise the dispensing exhaust downstream and leave the front-end unpriced "
                    "for the clinics.",
    "white-label": "White-label it to the PIMS vendors and let them absorb the cost instead of "
                   "selling to clinics.",
    "regulator-covered": "Get the state board to cover the cost so compliance stays free at the "
                         "point of use.",
    "employer-paid": "Have the corporate parent pay for it so individual clinics never do.",
    "association-funded": "The tool is best funded by the trade association rather than sold to "
                          "the clinics.",
}

_R14_MOOD_ATTACKS = {
    "imperative": "Give the clinics the tool for free.",
    "deontic-should": "The product should be free for clinics.",
    "evaluative-path": "The most viable path forward is a free tool.",
    "pivot": "Pivot toward a free, lead-generation tool.",
    "recommend": "I recommend a free tool for these clinics.",
    "best-fit": "A free tool fits better here.",
    "right-answer": "A free tool is the right answer here.",
    "consider": "Consider a free tool instead.",
    "gerund-subject": "Giving the clinics a free tool is the sane move here.",
    "passive": "A free tool is preferred over a paid one in this niche.",
    "question": "Why not make the tool free for the clinics?",
    "counterfactual": "If this were my money, the tool would be free for the clinics.",
    "hedged-deontic": "It might arguably be worthwhile to keep the tool free for clinics.",
    "two-sentence-split": "There is one shape left for this product. Free, with distribution "
                          "monetisation.",
}

# What the backstop caught when the ruling was made. Assertions below are MONOTONE: these must
# keep failing to publish, and nothing outside the recorded uncaught set may start publishing.
# A future rule that catches MORE passes unchanged; one that catches less fails.
_R14_BACKSTOP_CATCHES = {"freemium-no-paid-tier"} | {
    "imperative", "deontic-should", "evaluative-path", "pivot", "recommend", "best-fit",
    "right-answer", "consider",
}
_R14_KNOWN_UNCAUGHT = (set(_R14_OBJECT_ATTACKS) | set(_R14_MOOD_ATTACKS)) - _R14_BACKSTOP_CATCHES


def _r14_attacks() -> dict:
    return {**_R14_OBJECT_ATTACKS, **_R14_MOOD_ATTACKS}


@pytest.mark.parametrize("label", sorted(_R14_BACKSTOP_CATCHES))
@pytest.mark.parametrize("path", ["summary", "verdict", "slot"])
def test_r14_attacks_the_backstop_does_catch_stay_refused(label, path):
    attack = _r14_attacks()[label]
    assert _prescription_paths(attack)[path], f"{label} published on {path}: {attack!r}"


def test_r14_ceiling_is_recorded_and_may_only_shrink():
    """The measured ceiling, asserted as an upper bound rather than a target.

    Round 14's ruling — "there is no closed structural property in surface text" — is why the
    license was withdrawn at generation instead of a seventh filter being written. This test
    fails if an attack the backstop used to catch starts publishing, and passes unchanged if a
    later rule legitimately catches more.
    """
    from nicheiq.utils import niche_difficulty as nd

    uncaught = {
        label for label, attack in _r14_attacks().items()
        if not nd.has_zero_price_prescription(attack)
    }
    assert uncaught <= _R14_KNOWN_UNCAUGHT, (
        f"regression: {sorted(uncaught - _R14_KNOWN_UNCAUGHT)} used to be refused"
    )


def test_generator_prompts_withdraw_the_commercial_shape_license():
    """THE round-14 fix: neither prose generator is allowed to pick a commercial shape.

    Deleting the remit paragraph from either prompt fails this. The prescriptive licenses the
    prompts used to carry are asserted absent by their own former wording — those sentences are
    what produced the live D1 contradiction.
    """
    from nicheiq.utils.idea_portfolio_summary import build_idea_portfolio_digest
    from nicheiq.utils.prompts import load_prompt

    verdict_prompt = " ".join(load_prompt("niche_difficulty_verdict").split())
    assert "OUT OF YOUR REMIT" in verdict_prompt
    assert "Reporting is not prescribing" in verdict_prompt
    assert "MUST NOT recommend, select, rule out, or pivot" in verdict_prompt
    # The withdrawn licenses, verbatim.
    assert "should be built as free tools with built-in distribution" not in verdict_prompt
    assert "one-time/usage pricing fits the shape better" not in verdict_prompt

    digest = " ".join(build_idea_portfolio_digest(
        [SimpleNamespace(solution_name="AlphaTool", visibility_state="visible")],
        niche_wallet_brief={"wallet_class": "paying", "evidence": _PAYING_EVIDENCE},
    ).split())
    assert "MONETIZATION GUIDANCE" in digest
    assert "not something to restate" in digest


# ---------------------------------------------------------------------------
# ROUND 14 scope gap — a `mixed` wallet whose evidence quotes real prices.
# ---------------------------------------------------------------------------
_MIXED_PRICED_WALLET = {
    "wallet_class": "mixed",
    "evidence": "DaySmart Vet $116–$565/mo; quote-based pricing common",
    "free_density": "VetSoftwareHub free comparison tools",
}
# The live sentence from output/checkpoints/…0c9b6f29…, published beside that evidence.
_D1_MIXED_LIVE_SENTENCE = (
    "Given these constraints, the most logical path forward is to pivot away from subscription "
    "SaaS and toward free, lead-generation tools that seed a data corpus."
)


def test_priced_mixed_wallet_refuses_the_live_0c9b6f29_prescription():
    from nicheiq.utils import niche_difficulty as nd

    assert nd.wallet_evidence_shows_real_prices("mixed", _MIXED_PRICED_WALLET["evidence"])
    assert nd.priced_wallet_prescription_violations(
        _D1_MIXED_LIVE_SENTENCE,
        wallet_class="mixed",
        wallet_evidence=_MIXED_PRICED_WALLET["evidence"],
    ) == [nd.PRICED_WALLET_PRESCRIPTION_LABEL]


# The same sentence with the run's OWN EVIDENCE in front of it, which is how it was actually
# published. This is the monotone sibling of the pin above and the tripwire this round was missing:
# hardening round 2 excused any sentence whose recommended side carried an explicit price, and
# since the gate only arms when prices are VERIFIED, the copy quotes them — the exemption was
# defeated by the very condition that enables the check. Adding evidence to a prescription may
# never turn a violation into a pass.
_D1_MIXED_LIVE_SENTENCE_WITH_ITS_OWN_EVIDENCE = (
    "Given DaySmart Vet's $116-$565/mo pricing, the most logical path forward is to pivot away "
    "from subscription SaaS and toward free, lead-generation tools that seed a data corpus."
)


def test_quoting_the_verified_prices_does_not_silence_the_prescription():
    from nicheiq.utils import niche_difficulty as nd

    assert nd.priced_wallet_prescription_violations(
        _D1_MIXED_LIVE_SENTENCE_WITH_ITS_OWN_EVIDENCE,
        wallet_class="mixed",
        wallet_evidence=_MIXED_PRICED_WALLET["evidence"],
    ) == [nd.PRICED_WALLET_PRESCRIPTION_LABEL]


@pytest.mark.parametrize(
    "wallet_class,evidence",
    [
        ("mixed", "some buyers pay and some do not"),   # no price literal
        ("free-culture", "the paid incumbent charges $99/mo but nobody here buys it"),
        ("paying", "$99/mo incumbent"),                  # has its own, stronger contract
        (None, "$99/mo incumbent"),
    ],
)
def test_priced_mixed_contract_does_not_reach_other_wallets(wallet_class, evidence):
    from nicheiq.utils import niche_difficulty as nd

    assert nd.priced_wallet_prescription_violations(
        _D1_MIXED_LIVE_SENTENCE, wallet_class=wallet_class, wallet_evidence=evidence
    ) == []


def test_priced_mixed_wallet_keeps_its_own_negative_analysis():
    """A mixed niche may still say half its buyers will not pay — it just may not PRESCRIBE."""
    from nicheiq.utils import niche_difficulty as nd

    honest = (
        "These market realities suggest that the willingness to pay for new, standalone tools "
        "in these categories is quite low, and the competitive landscape is already "
        "well-defended by existing software."
    )
    assert nd.priced_wallet_prescription_violations(
        honest, wallet_class="mixed", wallet_evidence=_MIXED_PRICED_WALLET["evidence"]
    ) == []


def test_persisted_priced_mixed_summary_loses_only_the_prescription():
    from nicheiq.utils import niche_difficulty as nd

    summary = (
        "NarcVault Vet and ControlledSignal face significant competitive pressure from "
        "VetSnap.\n\n"
        f"{_D1_MIXED_LIVE_SENTENCE} The VetUnitEconomics Validator and RxNormPIMSMismatch are "
        "the most deserving of further validation."
    )
    published = nd.reconcile_persisted_paying_wallet_summary(
        summary,
        wallet_class="mixed",
        wallet_evidence=_MIXED_PRICED_WALLET["evidence"],
    )
    assert _D1_MIXED_LIVE_SENTENCE not in published
    assert "VetSnap" in published
    assert "most deserving of further validation" in published
    assert not nd.has_zero_price_prescription(published)


def test_persisted_priced_mixed_summary_is_never_emptied():
    """No sanctioned statement exists for a mixed wallet, so the filter must not publish ''."""
    from nicheiq.utils import niche_difficulty as nd

    published = nd.reconcile_persisted_paying_wallet_summary(
        _D1_MIXED_LIVE_SENTENCE,
        wallet_class="mixed",
        wallet_evidence=_MIXED_PRICED_WALLET["evidence"],
    )
    assert published == _D1_MIXED_LIVE_SENTENCE


def test_score_grade_survives_only_where_the_clause_is_about_the_niche():
    """R13.3: stripping the per-idea grade erased the only negation in a niche-level claim."""
    from nicheiq.utils import niche_difficulty as nd

    niche_level = (
        "The overall market verdict suggests that building a subscription-based product here "
        "is likely to fail due to weak buyer payability and high cold-start data requirements."
    )
    per_idea = (
        "AggregatorAccessMatcher has limited market fit and SEO scalability, with weak "
        "payability for its target segment."
    )
    adjacent_cue = (
        "WeatherCancelAlert and CallUp Now are hampered by weak payability, as they target "
        "individual coaches rather than the corporate budgets that sustain this niche."
    )
    # The grade is the ONLY negation in this one; stripping it unconditionally publishes it.
    grade_is_the_claim = "Across this market the buyer payability is weak."
    assert nd.has_negative_niche_wallet_claim(niche_level)
    assert nd.has_negative_niche_wallet_claim(grade_is_the_claim)
    # Both of these are grades on named ideas. The niche noun in the second sits in a different
    # clause than the grade, and reading them together turned a per-idea score into a wallet
    # denial across 23 of the 26 summaries the contract had been publishing.
    assert not nd.has_negative_niche_wallet_claim(per_idea)
    assert not nd.has_negative_niche_wallet_claim(adjacent_cue)


def test_low_and_failure_grades_count_as_wallet_negations():
    """R13.2: the vocabulary had no word for "quite low" or "likely to fail"."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_negative_niche_wallet_claim(
        "These market realities suggest that the willingness to pay for new, standalone tools "
        "in these categories is quite low."
    )
    assert nd.has_negative_niche_wallet_claim(
        "Subscription pricing struggles in this trade and every launch here is uphill."
    )


def test_bare_price_list_with_a_refusal_never_reaches_the_evidence_slot():
    """R13.4: a price list carries no money NOUN, so the refusal had nothing to pair with."""
    from nicheiq.utils import niche_difficulty as nd

    smuggled = "$29-$99/mo; nobody upgrades"
    note = nd._wallet_positive_note(smuggled)
    assert "nobody upgrades" not in note
    assert nd.has_negative_commercial_stance(smuggled)
    # A price list on its own is exactly what the slot is FOR and must still publish.
    clean = "$99-399/mo DaySmart Vet, $299/mo single-vet"
    assert clean in nd._wallet_positive_note(clean)
    assert not nd.has_unsanctioned_commercial_claim(nd._wallet_positive_note(clean))


def test_slot_contradiction_is_caught_wherever_the_statement_is_quoted():
    """A statement persisted with a poisoned slot is refused on re-validation, not just at build."""
    from nicheiq.utils import niche_difficulty as nd

    poisoned = (
        "Buyers in this niche demonstrably pay for tooling ($29-$99/mo; nobody upgrades): "
        "willingness to pay is not the primary risk."
    )
    assert nd._paying_wallet_copy_rule_labels(poisoned) == [
        "contradiction inside the sanctioned statement's evidence slot"
    ]


# ---------------------------------------------------------------------------
# Round 15, Priority 5: the deterministic fallbacks validate their own output,
# and the monetization line the prompts defer to actually reaches the reader.
# ---------------------------------------------------------------------------


def _paying_fp(**overrides):
    from nicheiq.utils import niche_difficulty as nd

    fields = dict(
        n_pains=4,
        n_ideas=4,
        none_share=0.0,
        partial_share=0.28,
        full_share=0.72,
        software_addressability=0.72,
        difficulty_level="medium",
        commercial_intent_max=0.4,
        wallet_class="paying",
        wallet_evidence="$99-399/mo DaySmart Vet",
    )
    fields.update(overrides)
    return nd.NicheDifficultyFactPack(**fields)


def test_contract_baseline_revalidates_the_points_it_carries_over():
    """The baseline used to copy `fp.key_points` through untouched.

    The fact pack's own points were never validated against the contract, so the RECONCILED
    verdict — the deterministic one, built precisely because the model's prose was rejected —
    could come back with a `key_challenges[0]` that still failed `_commercial_copy_violations`.
    """
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    prescription = (
        "Ship it as a free tool funded by sponsorship rather than something the clinics buy."
    )
    assert nd.has_zero_price_prescription(prescription)
    fp = _paying_fp(
        key_points=[prescription, "Most ideas need a data corpus that doesn't exist yet."],
        key_strengths=[prescription, "Usable data is reachable without a heavy cold-start lift."],
    )
    verdict = NicheDifficultyVerdict(
        difficulty_level="medium",
        software_addressability=0.72,
        headline="Software Fit: Strong. A tool can directly own these pains",
        narrative_summary="Inventory controls are concrete workflows this run can automate.",
        key_challenges=[prescription],
        key_strengths=[],
    )

    baseline = nd._paying_wallet_contract_baseline(verdict, fp, "veterinary clinics")

    assert nd._commercial_copy_violations(baseline, fp) == []
    assert prescription not in baseline.key_challenges
    assert prescription not in baseline.key_strengths
    # Filtering is surgical: the run's other deterministic findings survive.
    assert any("data corpus" in point for point in baseline.key_challenges)


def test_minimal_fallback_revalidates_before_returning(monkeypatch):
    """The last stop on every failure path is the one place a violation cannot be caught later."""
    from nicheiq.models.research_state import NicheDifficultyVerdict
    from nicheiq.utils import niche_difficulty as nd

    monkeypatch.setattr(
        nd,
        "_build_paying_wallet_contract_verdict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")),
    )
    fp = _paying_fp()
    verdict = NicheDifficultyVerdict(
        difficulty_level="medium",
        software_addressability=0.72,
        headline="Software Fit: Strong: avoid subscription pricing",
        narrative_summary="Buyers here will not pay.",
        buyer_class="consumer",
    )

    out = nd._deterministic_paying_wallet_fallback(verdict, fp, "veterinary clinics")

    assert nd._commercial_copy_violations(out, fp) == []
    assert out.key_challenges  # never empties itself to satisfy the invariant


@pytest.mark.parametrize("wallet_class,evidence", [
    ("paying", "$99-399/mo DaySmart Vet"),
    ("mixed", "Truckstop $42-159/mo"),
    ("mixed", "quote-based only"),
    ("free-culture", "every route here is free"),
    (None, ""),
])
def test_monetization_guidance_is_persisted_on_the_verdict(monkeypatch, wallet_class, evidence):
    """`monetization_guidance()` had NO reader while three prompts told the model the report
    rendered it. It is now carried on the verdict card, so the claim is true."""
    from types import SimpleNamespace as NS
    from nicheiq.utils import llm_service
    from nicheiq.utils import niche_difficulty as nd

    captured = {}

    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return (NS(headline="", narrative_summary="", buyer_class=""), None)

    monkeypatch.setattr(llm_service.LLMService, "invoke_structured", staticmethod(_cap))
    brief = ({"wallet_class": wallet_class, "evidence": evidence, "free_density": "unknown"}
             if wallet_class else None)
    pains = [SimpleNamespace(tool_addressable="full", commercial_intent=0.4) for _ in range(4)]
    fp = assess_niche_difficulty(
        pains, [_idea(novelty=0.6)] * 4, _nc(), niche_wallet_brief=brief)

    verdict, _ = generate_niche_difficulty_verdict(fp, "veterinary clinics", _nc())

    expected = nd.monetization_guidance(brief)
    assert verdict.monetization_guidance == expected
    # The prompt that tells the model to defer to this line also shows it the line.
    assert expected in captured["prompt"]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# D1 round 16, Priority 3 — the detector was OBJECT-BLIND: deontic mood plus the token `free`
# anywhere in the sentence. So pro-PAID guidance ("a paid product here must beat the free route")
# was read as a zero-price prescription and deleted. The free thing there is the COMPETITOR.
# ═════════════════════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("reports_a_rival", [
    "A paid product here must beat that free route on convenience and completeness.",
    "A paid tool must compete with the free official portal on completeness.",
    "The product has to win against the free spreadsheet template these buyers already use.",
    "Any paid version should be worth more than the free DIY routine it replaces.",
    "You should price it above free and charge monthly.",
    "The free/DIY route is the real competitor here, not another startup.",
    "Open-source alternatives are the benchmark this has to clear, so the bar is completeness.",
])
def test_naming_the_free_route_as_the_thing_to_BEAT_is_not_a_prescription(reports_a_rival):
    """Every one of these RECOMMENDS the paid product. Deleting them cost the reader real guidance."""
    from nicheiq.utils import niche_difficulty as nd

    assert not nd.has_zero_price_prescription(reports_a_rival), reports_a_rival
    assert nd._paying_wallet_copy_rule_labels(reports_a_rival) == [], reports_a_rival


@pytest.mark.parametrize("still_a_prescription", [
    # The rival framing must not become a cloak: the second half of each of these recommends a
    # zero-price shape in its own right.
    "You should beat the free route by giving it away.",
    "You should beat the free route by giving the first month away.",
    "You should compete with the free portal and then open-source the whole thing.",
    "Price it above free, and fund the rest from donations.",
    # ...and the plain prescriptions the object rule must never reach.
    "Pivot toward a free, lead-generation tool.",
    "The realistic path here is to hand the whole thing over to the trade association.",
    "Ship it as a free, affiliate-and-lead-gen-supported tool rather than something the shops buy.",
    "Default to a free tool with distribution monetization.",
    "Consider funding it from donations.",
])
def test_the_rival_object_rule_does_not_become_a_cloak(still_a_prescription):
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_zero_price_prescription(still_a_prescription), still_a_prescription


def test_the_restored_guidance_r15_removed_is_back_and_clean():
    """Round 15 deleted four pieces of guidance on an object-blind read. Three name PAID shapes
    and one names the bar a paid product has to clear; none contradicts any wallet reading."""
    from nicheiq.utils import niche_difficulty as nd

    restored = {
        "_SUBSTITUTE_CHALLENGE": "must beat that free route on convenience and completeness",
        "_EPISODIC_CHALLENGE": "favor one-time purchases, credits, or usage-based pricing",
        "_ADJACENT_MONEY_CHALLENGE": "may be the better business",
    }
    for name, fragment in restored.items():
        copy = getattr(nd, name)
        assert fragment in copy, f"{name} lost the guidance restored in round 16"
        assert not nd.has_zero_price_prescription(copy), copy
        assert nd._paying_wallet_copy_rule_labels(copy) == [], copy

    indie = nd._BUYER_CLASS_NOTES["indie-hobbyist"]
    assert "one-time pricing" in indie
    assert "an adjacent buyer with budget" in indie
    # ...but the zero-price half of the original note stays deleted.
    assert "free-tool distribution" not in indie
    assert not nd.has_zero_price_prescription(indie)


def test_a_longer_give_away_object_no_longer_escapes_the_shape_vocabulary():
    """`give the <one word> away` missed "giving the first month away" — the same prescription on
    a three-word object, and the hand-over pattern beside it had already been widened for this."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd._ZERO_PRICE_SHAPE_RE.search("giving the first month away")
    assert nd._ZERO_PRICE_SHAPE_RE.search("give the entire starter tier away")
    assert nd.has_zero_price_prescription("You should give the first three months away.")


@pytest.mark.parametrize("leak", [
    # Bare prepositional object: the imperative branch required a determiner or pronoun.
    "Monetize through affiliate links instead of asking the shops for money.",
    "Fund through sponsorships from the trade bodies.",
    # Fronted subordinate clause: the imperative branch was anchored at the start of the sentence.
    "Rather than selling seats, run it as an ad-supported comparison site.",
    "Instead of charging the clinics, give it to them and sell the data.",
])
def test_two_known_backstop_leaks_in_the_imperative_branch_are_closed(leak):
    """The MOOD conjunct's imperative branch missed these registers entirely (round 16, optional)."""
    from nicheiq.utils import niche_difficulty as nd

    assert nd.has_zero_price_prescription(leak), leak


@pytest.mark.parametrize("still_a_report", [
    "Open-source alternatives already cover most of this.",
    "Problems already addressed by free, integrated tools.",
    "Buyers favor free tools in this market.",
    "Communities here run on donations from their members.",
])
def test_widening_the_imperative_branch_did_not_swallow_reports(still_a_report):
    """The MOOD conjunct is the whole reason this is a contract and not another closed gate."""
    from nicheiq.utils import niche_difficulty as nd

    assert not nd.has_zero_price_prescription(still_a_report), still_a_report
