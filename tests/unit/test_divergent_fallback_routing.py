"""Regression coverage for Stage-5's guarded divergent fallback.

The guarded CrewAI fallback is a broad generator: unlike the normal partitioned fanout,
its concepts have no ``source_pain``/``source_segment`` cell provenance.  A valid broad
fallback pool must therefore use the pooled convergent refiner, not schedule zero cell
tournaments.
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
import nicheiq.utils.llm_service as llm_service
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import (
    BaseSolutionIdea,
    IdeaGenerationResult,
    RawConcept,
)
from nicheiq.utils.llm_service import LLMService, LLMSystemicError


@pytest.fixture(autouse=True)
def _clean_systemic_breaker():
    LLMService.reset_systemic()
    yield
    LLMService.reset_systemic()


def _provider_402() -> RuntimeError:
    error = RuntimeError("OpenRouter HTTP 402: insufficient provider credits")
    error.status_code = 402
    return error


def _concept(name: str, *, source_pain: str | None = None) -> RawConcept:
    return RawConcept(
        concept_name=name,
        one_liner=f"A useful, specific workflow for {name}.",
        ideation_technique="atomic_feature",
        project_type="saas",
        target_keywords=[f"{name} software", f"{name} workflow"],
        why_non_obvious=f"{name} uses an uncommon but obtainable workflow signal.",
        source_pain=source_pain,
    )


def _idea(name: str) -> BaseSolutionIdea:
    return BaseSolutionIdea(
        solution_name=name,
        description=f"{name} gives operators a concrete workflow with auditable outcomes.",
        value_proposition=f"Resolve {name} work faster.",
        pain_points_addressed=["Test pain"],
        core_features=["Workflow", "Audit trail"],
        target_personas=["Operator"],
        technical_approach="A conventional web application backed by a relational database.",
        differentiation_factors=["Narrow workflow focus"],
        requires_data_aggregation=False,
        data_sources=[],
        estimated_development_time="4-6 weeks",
        pricing_strategy="$29 per month",
        market_fit_score=0.65,
        technical_feasibility_score=0.8,
        project_type="saas",
        programmatic_seo_opportunity="Several workflow-specific landing pages.",
        content_generation_model="Template-driven pages",
        organic_discovery_queries=[f"{name} workflow", f"{name} software"],
        estimated_cac_organic="$10-20",
        estimated_cac_paid="$40-60",
        seo_scalability_score=0.55,
        novelty_score=0.5,
        conventional_approach="Teams usually coordinate this work in generic spreadsheets.",
        innovation_angle="The product owns one decision and records its supporting evidence.",
        why_it_works="The workflow is repeated often enough to support a focused product.",
        solo_dev_feasibility=0.8,
    )


def _wire_minimal_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    partition_pool: list[RawConcept],
    fallback_pool: list[RawConcept],
) -> tuple[UnifiedSolutionCrew, list[dict]]:
    pain = SimpleNamespace(
        title="Test pain",
        description="A repeated operational pain.",
        representative_quotes=["This process wastes hours every week."],
        opportunity_level=SimpleNamespace(value="high"),
        severity_score=0.8,
    )
    cells = [
        {"frame": "pain", "pain": SimpleNamespace(**{**pain.__dict__, "title": f"Pain {i}"}), "segment": None}
        for i in range(3)
    ]
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.pain_point_analysis = SimpleNamespace(
        pain_points=[pain],
        content_categorization=None,
        analysis_summary="Test analysis",
        top_categories=[],
        total_mentions=10,
    )
    crew.niche_context = None
    crew.audience_mapping = None
    crew.allowed_project_types = None
    crew.existing_ideas = []
    crew.idea_focus = "auto"
    crew.search_tool = None
    crew.checkpoint_mgr = None
    crew.competitor_mentions_text = ""
    crew.cost_tracker = None
    crew.user_audience_scope = None
    crew.coverage_caveats = []

    import nicheiq.utils.niche_difficulty as niche_difficulty
    import nicheiq.utils.pain_point_formatters as pain_formatters
    import nicheiq.utils.validation.crew_guardrails as crew_guardrails

    monkeypatch.setattr(
        pain_formatters,
        "extract_pain_points_by_priority",
        lambda analysis: ([pain], [], []),
    )
    monkeypatch.setattr(pain_formatters, "select_diverse_pain_points", lambda pains: pains)
    monkeypatch.setattr(pain_formatters, "format_pain_points_for_agents", lambda **kwargs: "pain")
    monkeypatch.setattr(niche_difficulty, "derive_monetization_directive", lambda *args: "")
    monkeypatch.setattr(crew_guardrails, "enforce_pain_coverage", lambda *args, **kwargs: [])

    monkeypatch.setattr(UnifiedSolutionCrew, "_build_partition_cells", lambda self, *args: cells)
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_audience_context", lambda self: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_regeneration_directive", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_segment_payability_map", lambda self: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_wallet_prompt_line", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_competitor_mentions", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_ensure_tool_glosses", lambda self: None)
    monkeypatch.setattr(
        UnifiedSolutionCrew,
        "_generate_divergent_pool",
        lambda self, inputs, partition_cells=None: (list(partition_pool), []),
    )
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage", lambda self, usages: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_critic_pool", lambda self, concepts: concepts)
    monkeypatch.setattr(
        UnifiedSolutionCrew,
        "_pool_and_dedup_raw_concepts",
        lambda self, concepts, keep_fraction=None: list(concepts[:6]),
    )
    monkeypatch.setattr(UnifiedSolutionCrew, "_divergent_fallback", lambda self, inputs: list(fallback_pool))

    for name in (
        "_carry_provenance",
        "_finalize_idea_pool",
        "_enforce_diversity_caps",
        "_finalize_feasibility",
        "_verify_pool_routes",
        "_filter_pain_relevance",
        "_finalize_dev_time",
        "_stamp_payability",
        "_probe_mechanism_parity",
        "_classify_idea_angles",
        "_validate_idea_scores",
        "_backfill_and_demote",
    ):
        monkeypatch.setattr(UnifiedSolutionCrew, name, lambda self, *args, **kwargs: None)
    monkeypatch.setattr(usc.settings, "enable_per_cell_tournament", True)
    monkeypatch.setattr(usc.settings, "enable_score_calibration", False)
    return crew, cells


def test_successful_broad_fallback_uses_convergent_refiner_and_returns_ideas(monkeypatch):
    fallback = [_concept(f"Fallback {i}") for i in range(10)]
    crew, _ = _wire_minimal_pipeline(
        monkeypatch,
        partition_pool=[],
        fallback_pool=fallback,
    )
    refined = IdeaGenerationResult(solution_ideas=[_idea(f"Idea {i}") for i in range(3)])
    convergent_calls: list[dict] = []

    class _ConvergentCrew:
        usage_metrics = None

        def kickoff(self, inputs):
            convergent_calls.append(inputs)
            return SimpleNamespace(
                tasks_output=[SimpleNamespace(pydantic=refined)],
                pydantic=None,
            )

    monkeypatch.setattr(UnifiedSolutionCrew, "_convergent_crew", lambda self, skip: _ConvergentCrew())
    monkeypatch.setattr(
        UnifiedSolutionCrew,
        "_run_parallel",
        lambda *args, **kwargs: pytest.fail("broad fallback must not schedule cell tournaments"),
    )
    monkeypatch.setattr(
        UnifiedSolutionCrew,
        "_finalize_evaluator_passes",
        lambda self, *args, **kwargs: LLMService.raise_if_systemic(),
    )
    llm_service._detect_systemic(_provider_402())

    result, selection = crew.execute_pipeline(skip_selection=True)

    assert [idea.solution_name for idea in result.solution_ideas] == ["Idea 0", "Idea 1", "Idea 2"]
    assert selection is None
    assert len(convergent_calls) == 1
    LLMService.raise_if_systemic()


def test_normal_partitioned_pool_still_runs_per_cell_tournaments(monkeypatch):
    partitioned = [_concept(f"Cell {i}", source_pain=f"Pain {i % 3}") for i in range(6)]
    crew, cells = _wire_minimal_pipeline(
        monkeypatch,
        partition_pool=partitioned,
        fallback_pool=[],
    )
    winners = [_idea(f"Winner {i}") for i in range(3)]
    tournament_jobs: list[dict] = []

    def _run_parallel(self, fn, jobs, deadline, max_workers, label="Parallel"):
        tournament_jobs.extend(jobs)
        return winners

    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel", _run_parallel)
    monkeypatch.setattr(
        UnifiedSolutionCrew,
        "_convergent_crew",
        lambda *args, **kwargs: pytest.fail("provenance-bearing pool must keep tournament mode"),
    )
    monkeypatch.setattr(UnifiedSolutionCrew, "_salvage_cell_losers", lambda self, groups, ideas: [])
    monkeypatch.setattr(UnifiedSolutionCrew, "_synthesize_bundles", lambda self, ideas: [])
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_evaluator_passes", lambda *args, **kwargs: None)

    result, selection = crew.execute_pipeline(skip_selection=True)

    assert len(tournament_jobs) == len(cells) == 3
    assert [idea.solution_name for idea in result.solution_ideas] == [
        "Winner 0",
        "Winner 1",
        "Winner 2",
    ]
    assert selection is None


def test_exhausted_fallback_surfaces_provider_billing_error(monkeypatch):
    crew, _ = _wire_minimal_pipeline(
        monkeypatch,
        partition_pool=[],
        fallback_pool=[],
    )
    llm_service._detect_systemic(_provider_402())

    with pytest.raises(LLMSystemicError, match="HTTP 402"):
        crew.execute_pipeline(skip_selection=True)
