"""Red-team-killed ideas are ineligible for the AUTOMATIC #1 recommendation.

Paired with the 2026-08-02 removal of the red-team -> `incumbent_parity` coupling: with the
parity cap gone a killed idea's market_fit REBOUNDS, and `apply_red_team_downgrade` only
runs at final report assembly — after selection, and it explicitly permits a killed idea to
remain selected. These tests pin the two flow-level automatic-pick derivations:
`_build_headless_selection` (tournament auto-select) and `_withhold_killed_auto_pick`
(the Task-4 strategic selector, which runs BEFORE the red team).
"""

from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.solution_selection import SolutionScores


def _idea(name, mf, verdict=None, caveats=None):
    return SimpleNamespace(
        solution_name=name,
        market_fit_score=mf,
        technical_feasibility_score=0.8,
        novelty_score=0.6,
        seo_scalability_score=0.4,
        build_feasibility_score=0.8,
        winning_angle=None,
        audience_fit=None,
        candidate_status="active",
        duplicate_of=None,
        project_type="saas",
        value_proposition=f"{name} value prop",
        core_features=["feature one"],
        pain_points_addressed=["a pain"],
        incumbent_parity=None,
        red_team_verdict=verdict,
        red_team_caveats=caveats,
    )


def _flow():
    return ResearchFlow.__new__(ResearchFlow)


class TestHeadlessAutoSelect:
    def test_killed_leader_never_becomes_the_auto_pick(self):
        flow = _flow()
        ideas = [
            _idea("Killed Leader", 0.74, "killed", ["no buyer evidence for this workflow"]),
            _idea("Runner Up", 0.60),
        ]
        selection = flow._build_headless_selection(SimpleNamespace(solution_ideas=ideas))

        assert selection.selected_solution_name == "Runner Up"
        # Visible, selectable, and still rank 1 in the list — only the pick is withheld.
        assert selection.all_solution_scores[0].solution_name == "Killed Leader"
        assert selection.all_solution_scores[0].rank == 1
        assert "Killed Leader" in selection.runner_up_solutions
        assert "no buyer evidence for this workflow" in selection.selection_rationale

    def test_surviving_leader_is_picked_with_no_note(self):
        flow = _flow()
        ideas = [_idea("Leader", 0.74), _idea("Runner Up", 0.60, "killed", ["dead"])]
        selection = flow._build_headless_selection(SimpleNamespace(solution_ideas=ideas))

        assert selection.selected_solution_name == "Leader"
        assert "withheld" not in selection.selection_rationale

    def test_all_killed_degrades_loudly(self):
        flow = _flow()
        ideas = [
            _idea("Alpha", 0.74, "killed", ["refuted"]),
            _idea("Beta", 0.60, "killed", ["also refuted"]),
        ]
        selection = flow._build_headless_selection(SimpleNamespace(solution_ideas=ideas))

        assert selection.selected_solution_name == "Alpha"
        assert "No automatic recommendation" in selection.selection_rationale


class TestWithholdKilledAutoPick:
    @staticmethod
    def _state(ideas, selected):
        return SimpleNamespace(
            idea_generation=SimpleNamespace(solution_ideas=ideas),
            solution_selection=SimpleNamespace(
                selected_solution_name=selected,
                selection_rationale="Task-4 picked this.",
                original_selection_reasoning=None,
                recommended_focus="old focus",
                runner_up_solutions=["Beta"],
                all_solution_scores=[
                    SolutionScores(solution_name="Alpha", market_fit_score=0.74,
                                   technical_feasibility_score=0.8, composite_score=0.7, rank=1),
                    SolutionScores(solution_name="Beta", market_fit_score=0.60,
                                   technical_feasibility_score=0.8, composite_score=0.6, rank=2),
                ],
            ),
        )

    def test_killed_llm_winner_is_repointed(self):
        flow = _flow()
        ideas = [_idea("Alpha", 0.74, "killed", ["premise refuted"]), _idea("Beta", 0.60)]
        flow._state = self._state(ideas, "Alpha")

        flow._withhold_killed_auto_pick()

        sel = flow.state.solution_selection
        assert sel.selected_solution_name == "Beta"
        assert sel.runner_up_solutions[0] == "Alpha"
        assert "premise refuted" in sel.selection_rationale
        assert sel.original_selection_reasoning == "Task-4 picked this."
        assert sel.recommended_focus != "old focus"

    def test_surviving_winner_is_left_alone(self):
        flow = _flow()
        ideas = [_idea("Alpha", 0.74), _idea("Beta", 0.60, "killed", ["dead"])]
        flow._state = self._state(ideas, "Alpha")

        flow._withhold_killed_auto_pick()

        assert flow.state.solution_selection.selected_solution_name == "Alpha"
        assert flow.state.solution_selection.selection_rationale == "Task-4 picked this."

    def test_user_selection_is_exempt(self):
        flow = _flow()
        ideas = [_idea("Alpha", 0.74, "killed", ["premise refuted"]), _idea("Beta", 0.60)]
        flow._state = self._state(ideas, "Alpha")
        flow.state._user_selected_solutions = {"Alpha"}

        flow._withhold_killed_auto_pick()

        assert flow.state.solution_selection.selected_solution_name == "Alpha"

    def test_all_killed_keeps_the_selection_and_states_it(self):
        flow = _flow()
        ideas = [_idea("Alpha", 0.74, "killed", ["refuted"]), _idea("Beta", 0.60, "killed", ["also"])]
        flow._state = self._state(ideas, "Alpha")

        flow._withhold_killed_auto_pick()

        sel = flow.state.solution_selection
        assert sel.selected_solution_name == "Alpha"
        assert "No automatic recommendation" in sel.selection_rationale
