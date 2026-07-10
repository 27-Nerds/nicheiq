"""ReportGenerator._generate_alternative_solutions must carry candidate_status/merged_from/
incumbent_parity/adjacent_market_parity/source_frame through onto AlternativeSolution (closes a
known residual: these fields exist on BaseSolutionIdea but were dropped when alternatives were
assembled)."""

from nicheiq.models.research_state import ResearchState
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult
from nicheiq.models.solution_selection import SolutionSelection
from nicheiq.report.report_generator import ReportGenerator


def _idea(name, **over):
    base = dict(
        solution_name=name, description="d" * 30, value_proposition="v",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        market_fit_score=0.6, technical_feasibility_score=0.7, novelty_score=0.4,
        seo_scalability_score=0.5, project_type="saas",
    )
    base.update(over)
    return BaseSolutionIdea(**base)


def _generator():
    state = ResearchState()
    state.idea_generation = IdeaGenerationResult(
        solution_ideas=[
            _idea("Selected"),
            _idea(
                "RunnerUp",
                candidate_status="restored",
                merged_from=["Absorbed A", "Absorbed B"],
                incumbent_parity="Aftershoot ships partial parity — depth/pricing/roadmap",
                adjacent_market_parity="none found",
                source_frame="gap",
            ),
            _idea("Third"),
        ]
    )
    state.solution_selection = SolutionSelection(
        selected_solution_name="Selected",
        selection_rationale="x" * 120,
        runner_up_solutions=["RunnerUp"],
        recommended_focus="x",
    )
    return ReportGenerator(state)


def test_candidate_status_and_merged_from_populated():
    gen = _generator()
    alts = gen._generate_alternative_solutions()
    assert alts and len(alts) == 1
    alt = alts[0]
    assert alt.solution_name == "RunnerUp"
    assert alt.candidate_status == "restored"
    assert alt.merged_from == ["Absorbed A", "Absorbed B"]


def test_parity_fields_pass_through():
    gen = _generator()
    alt = gen._generate_alternative_solutions()[0]
    assert alt.incumbent_parity == "Aftershoot ships partial parity — depth/pricing/roadmap"
    assert alt.adjacent_market_parity == "none found"


def test_defaults_when_source_idea_omits_lineage_fields():
    """A legacy/plain idea (no candidate_status/merged_from set explicitly) still gets the
    BaseSolutionIdea default ('active' / None), not a crash or None candidate_status."""
    state = ResearchState()
    state.idea_generation = IdeaGenerationResult(
        solution_ideas=[_idea("Selected"), _idea("RunnerUp"), _idea("Third")]
    )
    state.solution_selection = SolutionSelection(
        selected_solution_name="Selected",
        selection_rationale="x" * 120,
        runner_up_solutions=["RunnerUp"],
        recommended_focus="x",
    )
    alt = ReportGenerator(state)._generate_alternative_solutions()[0]
    assert alt.candidate_status == "active"
    assert alt.merged_from is None


def test_source_frame_passes_through():
    """Multi-Frame Idea Generation Portfolio: source_frame is code-filled on BaseSolutionIdea
    and must carry through onto AlternativeSolution unchanged."""
    gen = _generator()
    alt = gen._generate_alternative_solutions()[0]
    assert alt.source_frame == "gap"


def test_source_frame_defaults_to_pain_when_not_overridden():
    """BaseSolutionIdea.source_frame defaults to 'pain' (legacy/default generation path), and
    that default carries through onto AlternativeSolution unchanged."""
    state = ResearchState()
    state.idea_generation = IdeaGenerationResult(
        solution_ideas=[_idea("Selected"), _idea("RunnerUp"), _idea("Third")]
    )
    state.solution_selection = SolutionSelection(
        selected_solution_name="Selected",
        selection_rationale="x" * 120,
        runner_up_solutions=["RunnerUp"],
        recommended_focus="x",
    )
    alt = ReportGenerator(state)._generate_alternative_solutions()[0]
    assert alt.source_frame == "pain"
