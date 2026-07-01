"""Selection-integrity invariants: name-bearing fields stay ⊆ the final idea set (Bug 2 + Minor A),
and a Stage-6-pivoted winner is never dropped from the Stage 7/8 working set (Bug 5)."""

from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.solution_selection import SolutionScores, SolutionSelection


def _score(name, composite=0.7, rank=0):
    return SolutionScores(
        solution_name=name,
        market_fit_score=0.7,
        technical_feasibility_score=0.7,
        competitive_advantage_score=0.5,
        seo_growth_potential_score=0.6,
        composite_score=composite,
        rank=rank,
    )


def _ideas(*names):
    return [SimpleNamespace(solution_name=n) for n in names]


class TestPruneSelectionToIdeas:
    def test_drops_phantom_scores_and_runner_ups(self):
        sel = SolutionSelection(
            selected_solution_name="Keep1",
            selection_rationale="x" * 120,
            recommended_focus="Focus on the selected solution as the primary MVP.",
            all_solution_scores=[_score("Keep1", 0.9, 1), _score("Ghost", 0.8, 2), _score("Keep2", 0.7, 3)],
            runner_up_solutions=["Ghost", "Keep2"],
        )
        UnifiedSolutionCrew._prune_selection_to_ideas(sel, _ideas("Keep1", "Keep2"))

        names = {s.solution_name for s in sel.all_solution_scores}
        assert names == {"Keep1", "Keep2"}          # phantom dropped
        assert [s.rank for s in sel.all_solution_scores] == [1, 2]  # ranks re-contiguous
        assert sel.runner_up_solutions == ["Keep2"]  # phantom runner-up dropped
        assert sel.selected_solution_name == "Keep1"  # unchanged (survives)

    def test_promotes_when_selected_was_dropped(self):
        sel = SolutionSelection(
            selected_solution_name="Dropped",
            selection_rationale="x" * 120,
            recommended_focus="Focus on the selected solution as the primary MVP.",
            all_solution_scores=[_score("Dropped", 0.9, 1), _score("Survivor", 0.8, 2)],
            runner_up_solutions=["Survivor"],
        )
        UnifiedSolutionCrew._prune_selection_to_ideas(sel, _ideas("Survivor"))
        assert sel.selected_solution_name == "Survivor"  # promoted top survivor
        assert {s.solution_name for s in sel.all_solution_scores} == {"Survivor"}


class TestEnsureSelectedInTopN:
    def _flow(self, selected_name):
        flow = ResearchFlow(niche_description="test niche", job_id="job-topn")
        flow.state.solution_selection = SolutionSelection(
            selected_solution_name=selected_name,
            selection_rationale="x" * 120,
            recommended_focus="Focus on the selected solution as the primary MVP.",
            all_solution_scores=[
                _score("AlphaTool", 0.9), _score("BetaTool", 0.8),
                _score("GammaTool", 0.7), _score("PivotedTool", 0.5),
            ],
        )
        return flow

    def test_appends_pivoted_winner_when_missing(self):
        flow = self._flow("PivotedTool")
        all_scores = flow.state.solution_selection.all_solution_scores
        top_n = [s for s in all_scores if s.solution_name in {"AlphaTool", "BetaTool"}]  # excludes Pivoted
        out = flow._ensure_selected_in_topn(top_n, all_scores)
        assert any(s.solution_name == "PivotedTool" for s in out)  # winner kept for pricing/traffic
        assert len(out) == len(top_n) + 1

    def test_noop_when_selected_already_present(self):
        flow = self._flow("AlphaTool")
        all_scores = flow.state.solution_selection.all_solution_scores
        top_n = [s for s in all_scores if s.solution_name in {"AlphaTool", "BetaTool"}]
        out = flow._ensure_selected_in_topn(top_n, all_scores)
        assert out == top_n  # no change
