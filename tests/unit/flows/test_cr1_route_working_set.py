"""CR-1: one route-aware validation set and candidate-scoped Stage-8 evidence."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import nicheiq.flows.research_flow as flow_module
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.keyword_data import CrewKeywordValidationResult
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.models.solution_selection import SolutionScores, SolutionSelection


def _idea(name: str, *, project_type: str = "saas", seo: float = 0.3, **extra):
    data = {
        "solution_name": name,
        "description": "A concrete workflow product with a defined buyer and delivery path.",
        "value_proposition": "Turn a recurring workflow into a measurable result.",
        "pain_points_addressed": ["Recurring workflow failure"],
        "core_features": ["workflow"],
        "target_personas": ["operator"],
        "project_type": project_type,
        "market_fit_score": 0.7,
        "technical_feasibility_score": 0.8,
        "novelty_score": 0.5,
        "seo_scalability_score": seo,
        "data_access_model": "public" if seo >= 0.5 else None,
        "data_route": "public venue registry bulk index" if seo >= 0.5 else None,
        "content_generation_model": (
            "Public venue records generate one benchmark page per venue and city."
            if seo >= 0.5 else None
        ),
        "organic_discovery_queries": (
            ["venue cost benchmark", "venue settlement calculator"] if seo >= 0.5 else None
        ),
        "commercial_route": ({
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "lead buyer",
            "source_user_payment_required": False,
            "corpus_origin": "public_dataset",
            "enumerable_dimensions": ["city", "venue type"],
        } if seo >= 0.5 else None),
    }
    upstream = {"access_model", "value_capture_mode", "payer"}
    if upstream.intersection(extra) and not upstream.issubset(BaseSolutionIdea.model_fields):
        pytest.skip("typed route contract has not landed in BaseSolutionIdea yet")
    data.update(extra)
    return BaseSolutionIdea(**data)


def _score(name: str, composite: float, rank: int) -> SolutionScores:
    return SolutionScores(
        solution_name=name,
        market_fit_score=0.7,
        technical_feasibility_score=0.8,
        competitive_advantage_score=0.5,
        seo_growth_potential_score=0.6,
        composite_score=composite,
        rank=rank,
    )


def _selection(scores, selected="TopDirect"):
    return SolutionSelection(
        selected_solution_name=selected,
        selection_rationale="The selected idea currently leads the measured ranking. " * 3,
        recommended_focus="Validate the selected workflow before expanding scope.",
        all_solution_scores=scores,
    )


def _state(ideas, scores, selected="TopDirect"):
    return SimpleNamespace(
        solution_selection=_selection(scores, selected),
        idea_generation=SimpleNamespace(solution_ideas=ideas),
        keyword_validation_results=None,
        pricing_strategies=None,
        traffic_monetization_results=None,
        pain_point_analysis=SimpleNamespace(pain_points=[]),
        competitive_analysis=SimpleNamespace(solution_landscapes=[]),
        audience_mapping=None,
        seo_strategy_report=SimpleNamespace(total_monthly_volume=1000),
        current_stage=6,
    )


class _Harness:
    _NON_DIRECT_VALUE_CAPTURE = frozenset({
        "advertising", "affiliate", "lead_generation", "sponsorship", "paid_upgrade_funnel",
    })
    _TRAFFIC_PROJECT_TYPES = frozenset({"directory", "aggregator", "comparison-tool"})
    def _route_has_structural_evidence(self, *args, **kwargs):
        return ResearchFlow._route_has_structural_evidence(*args, **kwargs)

    def _commercial_route_value(self, *args, **kwargs):
        return ResearchFlow._commercial_route_value(*args, **kwargs)

    def _credible_non_direct_candidate(self, *args, **kwargs):
        return ResearchFlow._credible_non_direct_candidate(self, *args, **kwargs)

    def _traffic_monetization_eligible(self, *args, **kwargs):
        return ResearchFlow._traffic_monetization_eligible(self, *args, **kwargs)

    def _validation_working_set(self, *args, **kwargs):
        return ResearchFlow._validation_working_set(self, *args, **kwargs)

    def _keyword_probe_working_set(self, *args, **kwargs):
        return ResearchFlow._keyword_probe_working_set(self, *args, **kwargs)

    def _ensure_selected_in_topn(self, *args, **kwargs):
        return ResearchFlow._ensure_selected_in_topn(self, *args, **kwargs)

    def _seo_report_matches_solution(self, *args, **kwargs):
        return ResearchFlow._seo_report_matches_solution(*args, **kwargs)

    _run_integrated_keyword_validation = ResearchFlow._run_integrated_keyword_validation
    stage_7_pricing_validation = ResearchFlow.stage_7_pricing_validation
    stage_8_traffic_monetization = ResearchFlow.stage_8_traffic_monetization
    _analyze_traffic_monetization = ResearchFlow._analyze_traffic_monetization

    def __init__(self, state):
        self.state = state
        self.niche_description = "independent live music venues"
        self.checkpoint_mgr = MagicMock()
        self.cost_tracker = MagicMock()
        self._emit_progress = MagicMock()
        self._skip_stage = MagicMock()
        self._mark_stage_complete = MagicMock()


def _portfolio(*, selected="TopDirect"):
    ideas = [
        _idea("TopDirect", seo=0.2),
        _idea("SecondDirect", seo=0.2),
        _idea("LeadReserve", project_type="directory", seo=0.75),
        _idea("WeakDirectory", project_type="directory", seo=0.2),
    ]
    scores = [
        _score("TopDirect", 0.95, 1),
        _score("SecondDirect", 0.85, 2),
        _score("LeadReserve", 0.70, 3),
        _score("WeakDirectory", 0.60, 4),
    ]
    return _Harness(_state(ideas, scores, selected)), scores


def test_working_set_adds_exactly_one_credible_reserve(monkeypatch):
    flow, scores = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)

    result = flow._validation_working_set(scores)

    assert [row.solution_name for row in result] == [
        "TopDirect", "SecondDirect", "LeadReserve"
    ]


def test_working_set_has_no_duplicate_when_selected_is_already_present(monkeypatch):
    flow, scores = _portfolio(selected="LeadReserve")
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)

    result = flow._validation_working_set(scores)

    names = [row.solution_name for row in result]
    assert names.count("LeadReserve") == 1
    assert names == ["TopDirect", "SecondDirect", "LeadReserve"]


def test_credible_candidate_already_in_topn_is_the_single_paid_reserve_lane(monkeypatch):
    flow, scores = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 3)

    working = flow._validation_working_set(scores)
    probes = flow._keyword_probe_working_set(working)

    assert [row.solution_name for row in working] == [
        "TopDirect", "SecondDirect", "LeadReserve"
    ]
    assert [row.solution_name for row in probes] == ["TopDirect", "LeadReserve"]


def test_working_set_adds_no_weak_quota_filler(monkeypatch):
    ideas = [_idea("TopDirect"), _idea("WeakDirectory", project_type="directory", seo=0.2)]
    scores = [_score("TopDirect", 0.9, 1), _score("WeakDirectory", 0.7, 2)]
    flow = _Harness(_state(ideas, scores))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 1)

    result = flow._validation_working_set(scores)

    assert [row.solution_name for row in result] == ["TopDirect"]


def test_recruited_customer_pages_are_not_an_enumerable_reserve(monkeypatch):
    recruited = _idea("RecruitDirectory", project_type="directory", seo=0.8)
    recruited.commercial_route.corpus_origin = "user_generated"
    recruited.content_generation_model = (
        "Pages are created only after recruiting and manually onboarding each customer."
    )
    scores = [_score("TopDirect", 0.9, 1), _score("RecruitDirectory", 0.7, 2)]
    flow = _Harness(_state([_idea("TopDirect"), recruited], scores))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 1)

    result = flow._validation_working_set(scores)

    assert [row.solution_name for row in result] == ["TopDirect"]


def test_corpus_authority_never_inferrs_origin_from_euphemistic_prose():
    from nicheiq.utils.commercial_route import has_credible_public_corpus

    customer_owned = _idea("CustomerOwned", project_type="directory", seo=0.8)
    customer_owned.commercial_route.corpus_origin = "user_generated"
    customer_owned.content_generation_model = "Our public directory covers every city and category."
    assert not has_credible_public_corpus(customer_owned)

    public_owned = _idea("PublicOwned", project_type="directory", seo=0.8)
    public_owned.content_generation_model = "Vendors join and customers contribute profiles."
    assert has_credible_public_corpus(public_owned)


def test_working_set_preserves_selected_outside_top_n(monkeypatch):
    ideas = [_idea("TopDirect"), _idea("UserSelected")]
    scores = [_score("TopDirect", 0.9, 1), _score("UserSelected", 0.5, 2)]
    flow = _Harness(_state(ideas, scores, selected="UserSelected"))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 1)

    result = flow._validation_working_set(scores)

    assert [row.solution_name for row in result] == ["TopDirect", "UserSelected"]


def test_project_type_alone_never_creates_a_reserve(monkeypatch):
    flow, scores = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)

    result = flow._validation_working_set(scores)

    assert result[-1].solution_name == "LeadReserve"
    assert "WeakDirectory" not in {row.solution_name for row in result}


def test_reserve_below_explicit_quality_floor_is_not_added(monkeypatch):
    ideas = [_idea("TopDirect"), _idea("TinyReserve", project_type="directory", seo=0.8)]
    scores = [_score("TopDirect", 0.9, 1), _score("TinyReserve", 0.01, 2)]
    flow = _Harness(_state(ideas, scores))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 1)
    monkeypatch.setattr(flow_module.settings, "commercial_reserve_quality_floor", 0.55)

    assert [row.solution_name for row in flow._validation_working_set(scores)] == ["TopDirect"]


def test_non_active_public_corpus_is_not_reserved(monkeypatch):
    retired = _idea("RetiredReserve", project_type="directory", seo=0.8)
    retired.candidate_status = "restored"
    scores = [_score("TopDirect", 0.9, 1), _score("RetiredReserve", 0.7, 2)]
    flow = _Harness(_state([_idea("TopDirect"), retired], scores))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 1)

    assert [row.solution_name for row in flow._validation_working_set(scores)] == ["TopDirect"]


def test_clearly_direct_directory_is_not_traffic_eligible():
    idea = _idea(
        "PaidDirectory",
        project_type="directory",
        seo=0.8,
        commercial_route={
            "access_model": "paid",
            "value_capture_mode": "direct_user_payment",
            "payer": "end user",
        },
    )
    flow = _Harness(_state([idea], [_score("PaidDirectory", 0.9, 1)], "PaidDirectory"))

    assert flow._traffic_monetization_eligible(idea) is False


def test_typed_non_direct_route_is_traffic_eligible_without_legacy_project_type():
    idea = _idea(
        "LeadTool",
        project_type="saas",
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "lead buyer",
            "source_user_payment_required": False,
        },
    )
    flow = _Harness(_state([idea], [_score("LeadTool", 0.9, 1)], "LeadTool"))

    assert flow._traffic_monetization_eligible(idea) is True


def test_paid_upgrade_funnel_is_non_direct_for_stage_8_eligibility():
    idea = _idea(
        "UpgradeFunnel",
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "paid_upgrade_funnel",
            "payer": "downstream professional buyer",
            "source_user_payment_required": False,
        },
    )
    flow = _Harness(_state([idea], [_score("UpgradeFunnel", 0.9, 1)], "UpgradeFunnel"))

    assert flow._traffic_monetization_eligible(idea) is True


def test_unknown_legacy_route_preserves_project_fallback_only():
    directory = _idea("LegacyDirectory", project_type="directory", seo=0.2)
    saas = _idea("LegacySaaS", project_type="saas", seo=0.2)
    flow = _Harness(_state(
        [directory, saas],
        [_score("LegacyDirectory", 0.9, 1), _score("LegacySaaS", 0.8, 2)],
        "LegacyDirectory",
    ))

    assert flow._traffic_monetization_eligible(directory) is True
    assert flow._traffic_monetization_eligible(saas) is False


def test_nested_commercial_route_wins_over_flat_legacy_fields():
    persisted = _idea(
        "PersistedRoute",
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "venue operator",
            "source_user_payment_required": False,
        },
    )
    restored = BaseSolutionIdea.model_validate(persisted.model_dump(mode="json"))
    assert restored.commercial_route.value_capture_mode == "lead_generation"

    idea = SimpleNamespace(
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "venue operator",
            "source_user_payment_required": False,
        },
        access_model="paid",
        value_capture_mode="direct_user_payment",
        payer="end user",
    )

    assert ResearchFlow._commercial_route_value(idea, "access_model") == "free"
    assert ResearchFlow._commercial_route_value(idea, "value_capture_mode") == "lead_generation"


def test_missing_commercial_contract_remains_unknown():
    idea = SimpleNamespace(commercial_route=None)

    assert ResearchFlow._commercial_route_value(idea, "value_capture_mode") == ""


class _CapturedWorkingSet(RuntimeError):
    def __init__(self, names):
        self.names = names


def test_stage_6_real_wiring_probes_selected_and_reserve_but_not_generic_direct_topn(monkeypatch):
    flow, _ = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)
    flow._batched_attempt_one_validation = lambda names, _vocab: (_ for _ in ()).throw(
        _CapturedWorkingSet(list(names))
    )

    with pytest.raises(_CapturedWorkingSet) as exc:
        flow._run_integrated_keyword_validation()

    assert exc.value.names == ["TopDirect", "LeadReserve"]


def test_stage_6_also_probes_working_set_idea_already_classified_distribution_seo(monkeypatch):
    ideas = [
        _idea("TopDirect", seo=0.2),
        _idea("SeoClassified", seo=0.2, winning_angle="distribution_seo"),
        _idea("GenericDirect", seo=0.2),
        _idea("LeadReserve", project_type="directory", seo=0.8),
    ]
    scores = [
        _score("TopDirect", 0.95, 1),
        _score("SeoClassified", 0.90, 2),
        _score("GenericDirect", 0.85, 3),
        _score("LeadReserve", 0.70, 4),
    ]
    flow = _Harness(_state(ideas, scores))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 3)
    flow._batched_attempt_one_validation = lambda names, _vocab: (_ for _ in ()).throw(
        _CapturedWorkingSet(list(names))
    )

    with pytest.raises(_CapturedWorkingSet) as exc:
        flow._run_integrated_keyword_validation()

    assert exc.value.names == ["TopDirect", "LeadReserve", "SeoClassified"]


def test_stage_6_keyword_probe_candidates_have_one_hard_total_cap(monkeypatch):
    ideas = [_idea("Selected", seo=0.2)] + [
        _idea(f"SEO {index}", seo=0.2, winning_angle="distribution_seo")
        for index in range(12)
    ] + [_idea("Reserve", project_type="directory", seo=0.8)]
    scores = [_score(idea.solution_name, 0.99 - index * 0.01, index + 1)
              for index, idea in enumerate(ideas)]
    flow = _Harness(_state(ideas, scores, "Selected"))
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 7)
    monkeypatch.setattr(flow_module.settings, "keyword_probe_candidate_cap", 4)
    batch_calls = []

    def capture_batch(names, _vocab):
        batch_calls.append(list(names))
        raise _CapturedWorkingSet(list(names))

    flow._batched_attempt_one_validation = capture_batch

    with pytest.raises(_CapturedWorkingSet) as exc:
        flow._run_integrated_keyword_validation()

    assert exc.value.names[0] == "Selected"
    assert "Reserve" in exc.value.names
    assert len(exc.value.names) == 4
    assert batch_calls == [exc.value.names]


def test_stage_7_real_wiring_uses_same_working_set(monkeypatch):
    flow, _ = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)
    captured = []

    def fake_pricing(name):
        captured.append(name)
        return {"solution_name": name, "result": None, "usage_metrics": None}

    flow._validate_solution_pricing = fake_pricing
    flow.stage_7_pricing_validation()

    assert set(captured) == {"TopDirect", "SecondDirect", "LeadReserve"}


def test_stage_8_real_wiring_reaches_the_reserved_traffic_candidate(monkeypatch):
    flow, _ = _portfolio()
    monkeypatch.setattr(flow_module.settings, "top_solutions_for_validation", 2)
    captured = []

    def fake_traffic(name):
        captured.append(name)
        return {"solution_name": name, "result": None, "usage_metrics": None}

    flow._analyze_traffic_monetization = fake_traffic
    flow.stage_8_traffic_monetization()

    assert captured == ["LeadReserve"]


def _keyword_result(name: str, volume: int) -> CrewKeywordValidationResult:
    return CrewKeywordValidationResult(
        solution_name=name,
        validated_count=1,
        total_volume=volume,
        avg_competition=20,
        keyword_demand_score=0.7,
        top_keywords=[{"keyword": f"{name} keyword", "volume": volume}],
        top_geographic_keywords=[],
        demand_signal="moderate",
        validation_signals={"has_search_demand": True},
        attempts_made=1,
        best_relevance_score=0.8,
        niche_relevant_volume=volume,
        validated_keywords=[{
            "keyword": f"{name} keyword",
            "search_volume": volume,
            "idea_intent_grade": 2,
        }],
    )


def test_runner_up_gets_own_keywords_and_never_selected_seo(monkeypatch):
    selected = _idea("Selected", project_type="directory", seo=0.8)
    runner = _idea("Runner", project_type="directory", seo=0.8)
    scores = [_score("Selected", 0.9, 1), _score("Runner", 0.8, 2)]
    state = _state([selected, runner], scores, "Selected")
    selected_kv = _keyword_result("Selected", 9000)
    runner_kv = _keyword_result("Runner", 700)
    state.keyword_validation_results = [selected_kv, runner_kv]
    selected_seo = state.seo_strategy_report
    captured = {}

    class FakeTrafficCrew:
        usage_metrics = None

        def analyze(self, **kwargs):
            captured.update(kwargs)
            return None

    monkeypatch.setattr(flow_module, "TrafficMonetizationCrew", FakeTrafficCrew)
    flow = _Harness(state)

    flow._analyze_traffic_monetization("Runner")

    assert captured["keyword_validation_results"] == [runner_kv]
    assert captured["seo_strategy_report"] is None
    assert selected_seo is state.seo_strategy_report


def test_runner_up_without_own_evidence_stays_unknown_and_never_inherits_selected_seo(monkeypatch):
    selected = _idea("Selected", project_type="directory", seo=0.8)
    runner = _idea("Runner", project_type="directory", seo=0.8)
    scores = [_score("Selected", 0.9, 1), _score("Runner", 0.8, 2)]
    state = _state([selected, runner], scores, "Selected")
    state.keyword_validation_results = [_keyword_result("Selected", 9000)]
    called = MagicMock()

    class FakeTrafficCrew:
        usage_metrics = None
        analyze = called

    monkeypatch.setattr(flow_module, "TrafficMonetizationCrew", FakeTrafficCrew)
    flow = _Harness(state)

    result = flow._analyze_traffic_monetization("Runner")

    assert result["result"] is None
    called.assert_not_called()


def test_selected_candidate_rejects_stale_named_seo_report(monkeypatch):
    selected = _idea("Current", project_type="directory", seo=0.8)
    scores = [_score("Current", 0.9, 1)]
    state = _state([selected], scores, "Current")
    own_keywords = _keyword_result("Current", 700)
    state.keyword_validation_results = [own_keywords]
    state.seo_strategy_report = SimpleNamespace(
        solution_name="Previous",
        candidate_idea_id=None,
        candidate_idea_revision=None,
        idea_intent_monthly_volume=250_000,
    )
    captured = {}

    class FakeTrafficCrew:
        usage_metrics = None

        def analyze(self, **kwargs):
            captured.update(kwargs)
            return None

    monkeypatch.setattr(flow_module, "TrafficMonetizationCrew", FakeTrafficCrew)
    result = _Harness(state)._analyze_traffic_monetization("Current")

    assert result["result"] is None
    assert captured["keyword_validation_results"] == [own_keywords]
    assert captured["seo_strategy_report"] is None


def test_new_seo_report_identity_is_code_stamped_and_exact():
    selected = _idea("Current", project_type="directory", seo=0.8)
    selected.idea_id = "idea-current"
    selected.idea_revision = 3
    report = SimpleNamespace(
        solution_name=None, candidate_idea_id=None, candidate_idea_revision=None,
    )

    ResearchFlow._stamp_seo_report_identity(report, selected)

    assert report.solution_name == "Current"
    assert report.candidate_idea_id == "idea-current"
    assert report.candidate_idea_revision == 3
    assert ResearchFlow._seo_report_matches_solution(report, selected)


def test_seo_report_identity_match_is_exact_and_legacy_missing_is_allowed():
    selected = _idea("Current", project_type="directory", seo=0.8)
    selected.idea_id = "idea-current"
    selected.idea_revision = 3

    assert ResearchFlow._seo_report_matches_solution(SimpleNamespace(
        solution_name="Current", candidate_idea_id="idea-current",
        candidate_idea_revision=3), selected)
    assert not ResearchFlow._seo_report_matches_solution(SimpleNamespace(
        solution_name="Other", candidate_idea_id="idea-current",
        candidate_idea_revision=3), selected)
    assert not ResearchFlow._seo_report_matches_solution(SimpleNamespace(
        solution_name="Current", candidate_idea_id="idea-stale",
        candidate_idea_revision=3), selected)
    assert not ResearchFlow._seo_report_matches_solution(SimpleNamespace(
        solution_name="Current", candidate_idea_id="idea-current",
        candidate_idea_revision=2), selected)
    assert ResearchFlow._seo_report_matches_solution(SimpleNamespace(
        solution_name=None, candidate_idea_id=None, candidate_idea_revision=None), selected)
