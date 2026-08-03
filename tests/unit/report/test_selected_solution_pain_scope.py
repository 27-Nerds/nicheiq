"""Regression coverage for selected-solution pain integrity in Stage 14."""

from types import SimpleNamespace

from nicheiq.models.marketing_blueprint import First30DaysPlaybook, IdealCustomerProfile
from nicheiq.report.report_generator import ReportGenerator
from nicheiq.utils.llm_service import LLMService

PREMIERE = "Premiere Pro panel integration broken in Frame.io V4"
SCOPE = "No upfront revision limit leads to scope creep and unpaid work"
PRICING = "Undercharging per finished minute reduces profitability"
BRIEF = "Vague client briefs cause multiple revision rounds"


def _pain(title: str, severity: float, intent: float, category: str):
    return SimpleNamespace(
        title=title,
        description=f"Validated description for {title}",
        severity_score=severity,
        commercial_intent=intent,
        mention_count=12,
        categories=[category],
        representative_quotes=[f"Quote about {title}"],
        source_platforms=["Reddit"],
        source_post_ids=[],
        solution_approach="stale unrelated bridge",
    )


def _fixture():
    pains = [
        _pain(PREMIERE, 0.9, 0.8, "Tool Integration"),
        _pain(SCOPE, 0.8, 0.6, "Scope Creep"),
        _pain(PRICING, 0.45, 0.35, "Pricing"),
        _pain(BRIEF, 0.6, 0.4, "Client Communication"),
    ]
    solution = SimpleNamespace(
        solution_name="ScopeShield Post Kit",
        pain_points_addressed=[
            SCOPE,
            PRICING,
            "Vague client briefs like 'cut the boring parts' cause multiple revision rounds",
        ],
        source_pain=None,
        description="Track revision limits, clarify vague briefs, and protect project margins.",
        value_proposition="Protect margins without awkward scope conversations.",
        target_personas=["Freelance video editors"],
        core_features=["Revision limit tracker", "Pricing calculator", "Brief clarifier"],
        key_features=[],
        project_type="saas",
        estimated_development_time="4-6 weeks",
        technical_approach="Rules and a project ledger",
        pricing_strategy="Freemium",
        requires_data_aggregation=False,
        estimated_indexable_pages=40,
        estimated_cac_organic=25,
        seo_scalability_score=0.4,
    )
    categorization = SimpleNamespace(
        user_segments=[SimpleNamespace(
            segment_name="Freelance video editors",
            primary_concerns=[SCOPE],
            mention_frequency="High",
        )],
    )
    state = SimpleNamespace(
        pain_point_analysis=SimpleNamespace(
            pain_points=pains,
            content_categorization=categorization,
        ),
        solution_selection=None,
        social_content=None,
        audience_mapping=None,
        seeded_from_catalog=False,
        niche_context=SimpleNamespace(
            niche_description="Freelance video editing",
            market_segments=["Freelance video editors"],
        ),
    )
    generator = ReportGenerator(state)
    generator.accessor.get_selected_solution_details = lambda: solution
    return generator, solution, pains


def test_shared_resolver_never_falls_back_to_the_global_top_pain():
    generator, solution, _ = _fixture()

    resolved = generator.accessor.get_solution_pain_points(solution)

    assert [pain.title for pain in resolved] == [SCOPE, BRIEF, PRICING]
    assert PREMIERE not in [pain.title for pain in resolved]

    unmatched = SimpleNamespace(
        pain_points_addressed=["A completely unrelated problem"],
        source_pain=None,
    )
    assert generator.accessor.get_solution_pain_points(unmatched) == []


def test_executive_core_pain_is_selected_solution_specific():
    generator, solution, _ = _fixture()

    core = generator._extract_core_pain_point(solution)

    assert core is not None
    assert core.title == SCOPE
    assert core.title != PREMIERE


def test_market_narrative_and_next_steps_prompts_exclude_unaddressed_pains(monkeypatch):
    generator, solution, pains = _fixture()
    prompts: list[str] = []

    def fake_invoke(*args, **kwargs):
        prompts.append(kwargs["prompt"])
        if kwargs["output_model"].__name__ == "MarketNarrative":
            return SimpleNamespace(
                executive_summary="Scoped summary.",
                acquisition_strategy_summary="Scoped acquisition.",
            ), None
        return SimpleNamespace(next_steps=["Validate revision-limit demand."]), None

    monkeypatch.setattr(LLMService, "invoke_structured", fake_invoke)
    report = SimpleNamespace(
        selected_solution_details=solution,
        detailed_pain_points=pains,
        niche="Freelance video editing",
        selected_solution_name=solution.solution_name,
        market_validation="Moderate market validation.",
        selection_rationale="Best fit for scope and pricing pains.",
        executive_summary="",
        acquisition_strategy_summary="",
        next_steps=[],
    )

    generator._llm_market_narrative(report)
    generator._llm_next_steps(report)

    assert len(prompts) == 2
    assert "SEO Scalability: 4.0/10" in prompts[0]
    for prompt in prompts:
        assert SCOPE in prompt
        assert BRIEF in prompt
        assert PREMIERE not in prompt
        assert "Frame.io" not in prompt


def test_icp_and_playbook_use_only_selected_solution_pains(monkeypatch):
    generator, solution, _ = _fixture()
    prompts: list[str] = []

    def fake_invoke(*args, **kwargs):
        prompts.append(kwargs["prompt"])
        if kwargs["output_model"] is IdealCustomerProfile:
            return IdealCustomerProfile(
                persona_name="Freelance Editor Erin",
                demographics="Freelance video editor",
                psychographics="Protects client relationships and margins.",
                pain_points=[SCOPE, PREMIERE],
                goals=["Protect project margins"],
                buying_triggers="An unpaid revision round.",
                decision_criteria="Clear limits and simple exports.",
            ), None
        return First30DaysPlaybook(
            week_1_actions=[f"Interview editors about {SCOPE}"],
            week_2_actions=["Test a revision-limit prototype"],
            week_3_actions=["Review usage"],
            week_4_actions=["Decide whether to proceed"],
            success_metrics=["Five qualified interviews"],
        ), None

    monkeypatch.setattr(LLMService, "invoke_structured", fake_invoke)
    generator.accessor.get_tier_keyword_counts = lambda: {
        "total": 10,
        "tier_0": 2,
        "tier_1": 3,
    }
    generator.accessor.get_competitor_count = lambda: 4

    icp = generator._extract_ideal_customer_profile()
    assert icp is not None
    assert icp.pain_points == [SCOPE]

    generator._generate_first_30_days_playbook([], icp, solution)

    assert len(prompts) == 2
    for prompt in prompts:
        assert SCOPE in prompt
        assert PREMIERE not in prompt
        assert "Frame.io" not in prompt


def test_pain_mapping_rejects_titles_that_were_not_supplied(monkeypatch):
    generator, solution, _ = _fixture()
    scoped = generator.accessor.get_solution_pain_points(solution)
    captured = {}

    def fake_invoke(*args, **kwargs):
        captured["prompt"] = kwargs["prompt"]
        return SimpleNamespace(mappings=[
            SimpleNamespace(pain_point_title=SCOPE, solution_approach="Tracks revision limits."),
            SimpleNamespace(pain_point_title=PREMIERE, solution_approach="Invented integration."),
        ]), None

    monkeypatch.setattr(LLMService, "invoke_structured", fake_invoke)

    mappings = generator._generate_pain_solution_mappings(scoped, solution)

    assert mappings == {SCOPE: "Tracks revision limits."}
    assert PREMIERE not in captured["prompt"]
    assert "Frame.io" not in captured["prompt"]
