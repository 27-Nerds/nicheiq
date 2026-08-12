from pathlib import Path
from types import SimpleNamespace

from nicheiq.config.settings import Settings, settings
from nicheiq.crews.unified_solution_crew import (
    _COMMERCIAL_ROUTE_GENERATION_DIRECTIVE,
    UnifiedSolutionCrew,
    _auto_tournament_seed,
    _is_credible_distribution_lane,
)
from nicheiq.models.solution_idea import BaseSolutionIdea, CommercialRouteContract, RawConcept
from nicheiq.utils.score_helpers import demand_with_beachhead_magnitude, ranking_seo


def _concept(**overrides):
    data = dict(
        concept_name="Permit pages", one_liner="Enumerates permits", ideation_technique="data_source_inversion",
        project_type="directory", target_keywords=["city permits", "county permits"],
        data_route="public county permit index", data_access_model="public", obviousness_score=0.25,
        commercial_route={
            "access_model": "free", "value_capture_mode": "advertising", "payer": "advertisers",
            "source_user_payment_required": False,
            "corpus_origin": "public_dataset", "enumerable_dimensions": ["city", "permit type"],
        },
    )
    data.update(overrides)
    return RawConcept.model_validate(data)


def _idea(**overrides):
    base = dict(market_fit_score=0.8, source_segment_payability=0.1,
                source_segment_payability_class="personal-wallet", incumbent_parity=None,
                commercial_route=None, serp_competition=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_commercial_contract_degrades_each_bad_field_without_rejecting_raw_concept():
    concept = _concept(commercial_route={
        "access_model": "sponsor-paid", "value_capture_mode": "advertising", "payer": "  ",
        "source_user_payment_required": "sometimes"})
    assert concept.commercial_route.access_model is None
    assert concept.commercial_route.value_capture_mode == "advertising"
    assert concept.commercial_route.payer is None
    assert concept.commercial_route.source_user_payment_required is None
    assert _concept(commercial_route="advertising").commercial_route is None

    idea = BaseSolutionIdea(
        solution_name="Tolerant idea",
        description="A concrete product description.",
        value_proposition="A concrete outcome.",
        pain_points_addressed=["Recurring pain"],
        core_features=["workflow"],
        target_personas=["operator"],
        commercial_route={
            "access_model": "sponsor-paid",
            "value_capture_mode": "affiliate",
            "payer": "merchant",
            "source_user_payment_required": "no",
            "corpus_origin": "public-ish",
            "enumerable_dimensions": "city/category",
        },
    )
    assert idea.commercial_route.access_model is None
    assert idea.commercial_route.value_capture_mode == "affiliate"
    assert idea.commercial_route.source_user_payment_required is None
    assert idea.commercial_route.corpus_origin is None
    assert idea.commercial_route.enumerable_dimensions is None


def test_commercial_contract_survives_raw_serialization_and_code_owned_stamp():
    concept = RawConcept.model_validate(_concept().model_dump())
    idea = SimpleNamespace(commercial_route=CommercialRouteContract(
        access_model="paid", value_capture_mode="direct_user_payment", payer="fabricated buyer"))
    UnifiedSolutionCrew._stamp_commercial_route_from_source(idea, concept)
    assert idea.commercial_route == concept.commercial_route
    assert idea.commercial_route is not concept.commercial_route


def test_late_tags_align_only_when_vocabulary_has_exact_route_value():
    advertising = _idea(
        commercial_route=CommercialRouteContract(
            access_model="free", value_capture_mode="advertising", payer="advertiser",
            source_user_payment_required=False),
        tags=SimpleNamespace(monetization="subscription"),
    )
    sponsorship = _idea(
        commercial_route=CommercialRouteContract(
            access_model="free", value_capture_mode="sponsorship", payer="sponsor",
            source_user_payment_required=False),
        tags=SimpleNamespace(monetization="subscription"),
    )
    UnifiedSolutionCrew._align_tags_with_commercial_route(advertising)
    UnifiedSolutionCrew._align_tags_with_commercial_route(sponsorship)
    assert advertising.tags.monetization == "advertising"
    assert sponsorship.tags.monetization == "subscription"  # contract remains authoritative


def test_auto_tournament_reserves_only_verified_enumerable_on_band_lane_and_allows_zero():
    direct = _concept(concept_name="Novel direct", obviousness_score=0.2,
                      commercial_route={"access_model": "paid", "value_capture_mode": "direct_user_payment", "payer": "user"})
    lane = _concept(obviousness_score=0.28)
    assert _auto_tournament_seed([direct, lane]) is lane
    assert _auto_tournament_seed([direct, _concept(obviousness_score=0.31)]) is direct
    assert _auto_tournament_seed([_concept(critic_no_route=True), _concept(data_access_model="blocked")]) is None
    assert not _is_credible_distribution_lane(_concept(data_access_model="unverified"))
    assert not _is_credible_distribution_lane(_concept(data_route="NO-BULK"))


def test_payability_cap_applies_to_direct_and_legacy_but_not_non_direct_route(monkeypatch):
    monkeypatch.setattr(settings, "payability_market_fit_cap", 0.4)
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    direct = _idea(commercial_route=CommercialRouteContract(
        access_model="paid", value_capture_mode="direct_user_payment", payer="user"))
    non_direct = _idea(commercial_route=CommercialRouteContract(
        access_model="free", value_capture_mode="advertising", payer="advertiser",
        source_user_payment_required=False))
    legacy = _idea()
    crew._validate_idea_caps(direct)
    crew._validate_idea_caps(non_direct)
    crew._validate_idea_caps(legacy)
    assert direct.market_fit_score == 0.4
    assert legacy.market_fit_score == 0.4
    assert non_direct.market_fit_score == 0.8


def test_paid_upgrade_funnel_is_non_direct_for_problem_fit_payability(monkeypatch):
    monkeypatch.setattr(settings, "payability_market_fit_cap", 0.4)
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    funnel = _idea(commercial_route=CommercialRouteContract(
        access_model="free", value_capture_mode="paid_upgrade_funnel", payer="vendor",
        source_user_payment_required=False))
    crew._validate_idea_caps(funnel)
    assert funnel.market_fit_score == 0.8


def test_vendor_joins_and_malformed_corpus_fields_never_create_a_reserve():
    joins = _concept(commercial_route={
        "access_model": "free", "value_capture_mode": "lead_generation", "payer": "vendor",
        "source_user_payment_required": False,
        "corpus_origin": "user_generated", "enumerable_dimensions": ["city", "category"],
    })
    malformed = _concept(commercial_route={
        "access_model": "free", "value_capture_mode": "advertising", "payer": "advertiser",
        "source_user_payment_required": False,
        "corpus_origin": "public-ish", "enumerable_dimensions": "city/category",
    })
    assert not _is_credible_distribution_lane(joins)
    assert not _is_credible_distribution_lane(malformed)
    assert malformed.commercial_route.value_capture_mode == "advertising"
    assert malformed.commercial_route.corpus_origin is None
    assert malformed.commercial_route.enumerable_dimensions is None


def test_verified_no_bulk_or_refuted_route_vetoes_optimistic_typed_corpus():
    assert not _is_credible_distribution_lane(_concept(data_route="NO-BULK"))
    assert not _is_credible_distribution_lane(_concept(critic_no_route=True))
    assert not _is_credible_distribution_lane(_concept(data_access_model="blocked"))


def test_incomplete_or_contradictory_non_direct_tuple_is_conservative(monkeypatch):
    from nicheiq.utils.commercial_route import CommercialLane, assess_commercial_lane

    complete = CommercialRouteContract(
        access_model="freemium", value_capture_mode="paid_upgrade_funnel", payer="vendor",
        source_user_payment_required=False)
    incomplete = [
        CommercialRouteContract(
            access_model=None, value_capture_mode="advertising", payer="advertiser",
            source_user_payment_required=False),
        CommercialRouteContract(
            access_model="free", value_capture_mode="advertising", payer=None,
            source_user_payment_required=False),
        CommercialRouteContract(
            access_model="free", value_capture_mode="advertising", payer="advertiser",
            source_user_payment_required=None),
        CommercialRouteContract(
            access_model="paid", value_capture_mode="advertising", payer="advertiser",
            source_user_payment_required=False),
    ]
    assert assess_commercial_lane(_idea(commercial_route=complete)) is CommercialLane.NON_DIRECT
    assert all(
        assess_commercial_lane(_idea(commercial_route=route)) is CommercialLane.UNKNOWN
        for route in incomplete
    )
    assert assess_commercial_lane(_idea(commercial_route=CommercialRouteContract(
        access_model="free", value_capture_mode="advertising", payer="advertiser",
        source_user_payment_required=True))) is CommercialLane.DIRECT

    monkeypatch.setattr(settings, "payability_market_fit_cap", 0.4)
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    capped = _idea(commercial_route=incomplete[2])
    crew._validate_idea_caps(capped)
    assert capped.market_fit_score == 0.4


def test_parity_is_direct_product_damage_but_only_explicit_open_serp_bypasses(monkeypatch):
    monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.55)
    monkeypatch.setattr(settings, "parity_partial_market_fit_cap", 0.65)
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    route = CommercialRouteContract(
        access_model="free", value_capture_mode="affiliate", payer="vendor",
        source_user_payment_required=False)
    direct = _idea(incumbent_parity="shipped: same feature")
    open_route = _idea(incumbent_parity="shipped: same feature", commercial_route=route, serp_competition="open")
    owned_route = _idea(incumbent_parity="shipped: same feature", commercial_route=route, serp_competition="owned")
    unknown_route = _idea(incumbent_parity="shipped: same feature", commercial_route=route, serp_competition="unknown")
    absent_route = _idea(incumbent_parity="shipped: same feature", commercial_route=route, serp_competition=None)
    partial_unknown = _idea(
        incumbent_parity="partial: same core workflow", commercial_route=route,
        serp_competition="unknown")
    for idea in (direct, open_route, owned_route, unknown_route, absent_route, partial_unknown):
        crew._validate_idea_caps(idea)
    assert direct.market_fit_score == 0.55
    assert open_route.market_fit_score == 0.8
    assert owned_route.market_fit_score == 0.55
    assert unknown_route.market_fit_score == 0.55
    assert absent_route.market_fit_score == 0.55
    assert partial_unknown.market_fit_score == 0.65


def test_distribution_route_still_takes_public_substitute_competition(monkeypatch):
    monkeypatch.setattr(settings, "parity_substitute_market_fit_cap", 0.6)
    monkeypatch.setattr(settings, "parity_substitute_weak_wallet_cap", 0.3)
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    route = CommercialRouteContract(
        access_model="free", value_capture_mode="affiliate", payer="vendor",
        source_user_payment_required=False)
    idea = _idea(incumbent_parity="substitute: official public directory",
                 commercial_route=route, serp_competition="open")
    crew._validate_idea_caps(idea)
    assert idea.market_fit_score == 0.6  # ordinary public-substitute cap; never weak-user-wallet cap


def test_typed_serp_ownership_caps_headless_ranking_and_refined_bypasses():
    assert ranking_seo(0.9, {"serp_competition": "owned"}) <= settings.serp_owned_seo_ceiling
    assert ranking_seo(0.9, {"serp_competition": "open"}) == settings.provisional_seo_rank_ceiling
    assert ranking_seo(0.9, {"serp_competition": "owned", "seo_scalability_score_refined": 0.9}) == 0.9


def test_irrelevant_graded_head_term_is_zero_demand_evidence():
    assert demand_with_beachhead_magnitude(0.98, 0, 1_600_000) == 0.0
    assert demand_with_beachhead_magnitude(0.8, None, 10_000) > 0


def test_direction_aware_default_is_on():
    assert Settings().enable_direction_aware_eval is True
    env_example = Path(__file__).parents[2] / ".env.example"
    assert "ENABLE_DIRECTION_AWARE_EVAL=true" in env_example.read_text()


def test_serp_probe_is_bounded_and_persists_three_state(monkeypatch):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    eligible = SimpleNamespace(
        commercial_route=CommercialRouteContract(
            access_model="free", value_capture_mode="advertising", payer="advertiser",
            source_user_payment_required=False,
            corpus_origin="public_dataset", enumerable_dimensions=["city", "permit type"]),
        data_access_model="public", project_type="directory", candidate_status="active",
        market_fit_score=0.7, technical_feasibility_score=0.7,
        novelty_score=0.6, seo_scalability_score=0.8,
        winning_angle=None, seo_scalability_score_refined=None, serp_competition=None,
        programmatic_seo_opportunity="city permit directory", mechanism_tag="permits",
        solution_name="Permit pages",
    )
    classified = SimpleNamespace(
        commercial_route=None, winning_angle="distribution_seo", seo_scalability_score_refined=None,
        candidate_status="active", market_fit_score=0.7, technical_feasibility_score=0.7,
        novelty_score=0.6, seo_scalability_score=0.8,
        serp_competition=None, programmatic_seo_opportunity="venue cost pages",
        mechanism_tag="venues", solution_name="Venue pages",
    )
    unrelated = SimpleNamespace(
        commercial_route=None, winning_angle="vertical_workflow", seo_scalability_score_refined=None,
        serp_competition=None, programmatic_seo_opportunity="workflow", mechanism_tag="workflow",
        solution_name="Workflow",
    )
    calls = []

    def _batch(queries, **_kwargs):
        calls.extend(queries)
        return {q: "https://reddit.com/r/example https://smallsite.example/page" for q in queries}

    crew._ma_search_batch = _batch
    monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
    crew._probe_serp_composition([eligible, classified, unrelated])
    assert len(calls) == 4
    assert eligible.serp_competition == "open"
    assert classified.serp_competition == "open"
    assert unrelated.serp_competition is None


def test_cell_scorer_never_spends_serp_budget(monkeypatch):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.idea_focus = "auto"
    order = []
    winner = SimpleNamespace(
        winning_angle=None, project_type="directory", seo_scalability_score=0.8,
        commercial_route=None, serp_competition=None,
    )
    crew._finalize_feasibility = lambda _ideas: order.append("feasibility")
    crew._classify_batch = lambda **_kwargs: (order.append("classify") or 1, None)
    crew._reconcile_angle_after_classify = lambda *_args: order.append("reconcile")
    crew._probe_serp_composition = lambda _ideas: order.append("serp")
    crew._validate_idea_caps = lambda _idea: order.append("caps")
    crew._novelty_enhance = lambda idea, **_kwargs: idea
    monkeypatch.setattr(settings, "enable_score_calibration", False)
    crew._score_cell_winner(winner, skip_selection=False, usages=[])
    assert "serp" not in order
    assert "caps" in order


def test_global_serp_selector_is_hard_bounded_for_twelve_ideas(monkeypatch):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    ideas = [SimpleNamespace(
        solution_name=f"Idea {index}", candidate_status="active",
        winning_angle="distribution_seo", commercial_route=None,
        seo_scalability_score_refined=None, serp_competition=None,
        market_fit_score=0.7, technical_feasibility_score=0.7,
        novelty_score=0.6, seo_scalability_score=0.8,
        programmatic_seo_opportunity=f"venue axis {index}", mechanism_tag=f"venue-{index}",
    ) for index in range(12)]
    calls = []
    crew._ma_search_batch = lambda queries, **_kwargs: (
        calls.extend(queries) or {query: "https://reddit.com/r/x" for query in queries}
    )
    monkeypatch.setattr(settings, "serp_probe_queries_per_idea", 2)
    monkeypatch.setattr(settings, "serp_probe_distribution_candidate_cap", 2)
    crew._probe_serp_composition(ideas)
    assert len(calls) == 4
    assert sum(idea.serp_competition is not None for idea in ideas) == 2


def test_broad_generation_prompt_always_requests_structured_corpus_contract():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.tasks_config = {"divergent_exploration": {"description": "{partitioned_mode_block}"}}
    prompt = crew._render_divergent_prompt({}, "", partitioned_mode_block="")
    assert _COMMERCIAL_ROUTE_GENERATION_DIRECTIVE in prompt
    assert "corpus_origin" in prompt
    assert "enumerable_dimensions" in prompt
    assert "source_user_payment_required" in prompt


def test_late_wave_stamps_unknown_without_search_and_caps_shipped_parity(monkeypatch):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    route = CommercialRouteContract(
        access_model="free", value_capture_mode="affiliate", payer="vendor",
        source_user_payment_required=False)
    idea = _idea(
        solution_name="Late affiliate pages", commercial_route=route,
        winning_angle="distribution_seo", candidate_status="active",
        seo_scalability_score_refined=None, serp_competition=None,
        incumbent_parity="shipped: same feature", market_fit_score=0.8,
    )
    calls = []
    crew._finalize_idea_pool = lambda _wave: None
    crew._verify_pool_routes = lambda _wave: None
    crew._finalize_feasibility = lambda _wave: None
    crew._filter_pain_relevance = lambda _wave: None
    crew._stamp_payability = lambda _idea: None
    crew._finalize_dev_time = lambda _wave: None
    crew._probe_mechanism_parity = lambda _wave: None
    crew._calibrate_idea_scores = lambda _wave: None
    crew._classify_idea_angles = lambda _wave: None
    crew._ma_search_batch = lambda *_args, **_kwargs: calls.append("search")
    monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.55)

    crew._score_wave([idea])

    assert calls == []
    assert idea.serp_competition == "unknown"
    assert idea.market_fit_score == 0.55


def test_guarded_broad_fallback_receives_structured_corpus_contract(monkeypatch):
    import nicheiq.crews.unified_solution_crew as module

    captured = {}

    class FakeCrew:
        def __init__(self, **_kwargs):
            pass

        def kickoff(self, *, inputs):
            captured.update(inputs)
            return SimpleNamespace(tasks_output=[])

    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.solution_ideator = lambda: object()
    crew.divergent_exploration_task = lambda: object()
    monkeypatch.setattr(module, "Crew", FakeCrew)

    assert crew._divergent_fallback({}) == []
    assert _COMMERCIAL_ROUTE_GENERATION_DIRECTIVE in captured["partitioned_mode_block"]


def test_paid_probe_settings_reject_unbounded_values():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(top_solutions_for_validation=1000)
    with pytest.raises(ValidationError):
        Settings(keyword_pivot_max_attempts=1000)
    with pytest.raises(ValidationError):
        Settings(serp_probe_distribution_candidate_cap=1000)
    with pytest.raises(ValidationError):
        Settings(serp_probe_queries_per_idea=1000)
    with pytest.raises(ValidationError):
        Settings(serp_probe_queries_per_idea=3)
    with pytest.raises(ValidationError):
        Settings(keyword_probe_candidate_cap=1000)
