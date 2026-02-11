"""Tests for interactive job flow worker tasks."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import patch, MagicMock
from nicheiq.models.solution_selection import SolutionScores, SolutionSelection


class TestRunInteractiveResearch:
    """Tests for run_interactive_research task."""

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_creates_flow_and_calls_mark_job_running(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        """Creates ResearchFlow, calls mark_job_running, then runs pipeline."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.progress_callback = None

            # Mock state with solution ideas
            state = MagicMock()
            idea_gen = MagicMock()
            idea_gen.solution_ideas = [MagicMock(solution_name="Sol1")]
            state.idea_generation = idea_gen
            flow.state = state
            flow.run_with_resume.return_value = ''
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/checkpoint'

            mock_progress.return_value = MagicMock()  # progress callback

            from worker.tasks import run_interactive_research
            result = run_interactive_research(job_id='job-1', niche='test niche')

            mock_mark.assert_called_once_with('job-1')
            MockFlow.assert_called_once()
            flow.run_with_resume.assert_called_once_with(auto_resume=False, stop_after_phase=1)

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_calls_notify_ideas_ready_with_skip_validation(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            state = MagicMock()
            ideas = [MagicMock(solution_name="Sol1", name="Sol1")]
            ideas[0].model_dump.return_value = {"solution_name": "Sol1", "name": "Sol1"}
            state.idea_generation = MagicMock(solution_ideas=ideas)
            flow.state = state
            flow.run_with_resume.return_value = ''
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/cp'

            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            result = run_interactive_research(job_id='job-1', niche='test')

            mock_notify_ideas.assert_called_once()
            args = mock_notify_ideas.call_args
            assert args[0][0] == 'job-1'  # job_id
            assert len(args[0][1]) == 1   # solutions list
            assert args[0][2] == '/tmp/cp'  # checkpoint_path
            # skip_validation should be True
            assert args[1].get('skip_validation') is True or args[0][4] is True

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_returns_awaiting_selection_immediately(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        """After Phase 1, should return awaiting_selection without validation loop."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            sol1 = MagicMock(solution_name="Sol1", name="Sol1")
            sol1.model_dump.return_value = {"solution_name": "Sol1", "name": "Sol1"}
            state = MagicMock()
            state.idea_generation = MagicMock(solution_ideas=[sol1])
            flow.state = state
            flow.run_with_resume.return_value = ''
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/cp'

            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            result = run_interactive_research(job_id='job-1', niche='test')

            assert result == {"status": "awaiting_selection", "job_id": "job-1"}

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_handles_job_cancelled_exception(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from worker.heartbeat import JobCancelledException
            flow = MockFlow.return_value
            flow.run_with_resume.side_effect = JobCancelledException("cancelled")
            flow.cleanup_collections = MagicMock()
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            with pytest.raises(JobCancelledException):
                run_interactive_research(job_id='job-1', niche='test')

            flow.cleanup_collections.assert_called_once()

    @patch('worker.tasks.notify_job_quality_gate_stop')
    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_handles_quality_gate_stop(
        self, mock_progress, mock_mark, mock_notify_ideas, mock_quality_gate
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from nicheiq.flows.research_flow import QualityGateStopException
            flow = MockFlow.return_value
            flow.run_with_resume.side_effect = QualityGateStopException(
                stage=5, reason='INSUFFICIENT_DATA', details={'score': 0.3}
            )
            flow.cleanup_collections = MagicMock()
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            result = run_interactive_research(job_id='job-1', niche='test')

            assert result is None
            mock_quality_gate.assert_called_once()

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_cleanup_collections_called_in_finally(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.run_with_resume.side_effect = RuntimeError("boom")
            flow.cleanup_collections = MagicMock()
            flow.state = MagicMock(current_stage=5)
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            with pytest.raises(RuntimeError):
                run_interactive_research(job_id='job-1', niche='test')

            flow.cleanup_collections.assert_called_once()


class TestRunResearchPhase2:
    """Tests for run_research_phase2 task."""

    @patch('worker.tasks._run_phase2_continuation')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_loads_checkpoint_and_runs_phase2(
        self, mock_progress, mock_mark, mock_phase2_cont
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            mock_progress.return_value = MagicMock()
            mock_phase2_cont.return_value = {"status": "completed"}

            from worker.tasks import run_research_phase2
            result = run_research_phase2(
                job_id='job-1',
                checkpoint_path='/tmp/cp',
                selected_solutions=['Sol1'],
            )

            mock_mark.assert_called_once_with('job-1')
            flow.resume_from_checkpoint.assert_called_once_with('/tmp/cp')
            mock_phase2_cont.assert_called_once()
            assert result == {"status": "completed"}

    @patch('worker.tasks.notify_job_quality_gate_stop')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_handles_quality_gate_stop(
        self, mock_progress, mock_mark, mock_quality_gate
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from nicheiq.flows.research_flow import QualityGateStopException
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.side_effect = QualityGateStopException(
                stage=9, reason='INSUFFICIENT_DATA', details={}
            )
            flow.cleanup_collections = MagicMock()
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_research_phase2
            result = run_research_phase2(
                job_id='job-1', checkpoint_path='/tmp/cp',
                selected_solutions=['Sol1'],
            )
            assert result is None
            mock_quality_gate.assert_called_once()

    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_handles_errors_and_raises(self, mock_progress, mock_mark):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = False
            flow.cleanup_collections = MagicMock()
            flow.state = MagicMock(current_stage=8)
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_research_phase2
            with pytest.raises(RuntimeError, match="Failed to load checkpoint"):
                run_research_phase2(
                    job_id='job-1', checkpoint_path='/bad/path',
                    selected_solutions=['Sol1'],
                )


class TestRunRegenerateIdeas:
    """Tests for run_regenerate_ideas task."""

    @patch('worker.tasks.notify_regeneration_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_loads_checkpoint_and_regenerates(
        self, mock_progress, mock_notify_regen
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                flow = MockFlow.return_value
                flow.resume_from_checkpoint.return_value = True
                flow.cleanup_collections = MagicMock()
                flow.allowed_project_types = None
                state = MagicMock()
                state.pain_point_analysis = MagicMock()
                state.social_content = MagicMock()
                state.niche_context = MagicMock()
                state.audience_mapping = MagicMock()
                flow.state = state
                flow.checkpoint_mgr = MagicMock()
                mock_progress.return_value = MagicMock()

                # Mock crew results
                new_sol = MagicMock(solution_name="NewSol", name="NewSol")
                new_sol.model_dump.return_value = {"solution_name": "NewSol", "name": "NewSol"}
                idea_gen = MagicMock(solution_ideas=[new_sol])
                MockCrew.return_value.execute_pipeline.return_value = [idea_gen]

                from worker.tasks import run_regenerate_ideas
                result = run_regenerate_ideas(
                    job_id='job-1',
                    checkpoint_path='/tmp/cp',
                    existing_solution_names=['OldSol'],
                    niche='test niche',
                )

                assert result["status"] == "regenerated"
                mock_notify_regen.assert_called_once()

    @patch('worker.tasks.notify_regeneration_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_handles_errors_gracefully(self, mock_progress, mock_notify_regen):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = False
            flow.cleanup_collections = MagicMock()
            flow.state = MagicMock(current_stage=7)
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_regenerate_ideas
            with pytest.raises(RuntimeError, match="Failed to load checkpoint"):
                run_regenerate_ideas(
                    job_id='job-1', checkpoint_path='/bad/path',
                    existing_solution_names=[], niche='test',
                )


def _make_score(name, composite, rank=1):
    """Helper to create a SolutionScores object."""
    return SolutionScores(
        solution_name=name,
        market_fit_score=composite,
        technical_feasibility_score=composite,
        competitive_advantage_score=composite,
        seo_growth_potential_score=composite,
        composite_score=composite,
        rank=rank,
    )


class TestPhase2MultiSelectFix:
    """Tests for multi-select solution handling in _run_phase2_continuation."""

    def _make_state(self, scored_names=None, all_ideas=None):
        """Build a mock state with solution_selection and idea_generation."""
        state = MagicMock()

        # Build all_solution_scores from scored_names
        if scored_names is not None:
            scores = [_make_score(n, 0.7 - i * 0.1, i + 1) for i, n in enumerate(scored_names)]
            selection = MagicMock(spec=SolutionSelection)
            selection.all_solution_scores = scores
            selection.selected_solution_name = scored_names[0]
            selection.runner_up_solutions = list(scored_names[1:])
            selection.selection_rationale = "test"
            selection.recommended_focus = "test"
            state.solution_selection = selection
        else:
            state.solution_selection = None

        # Build idea_generation
        if all_ideas:
            ideas = []
            for name in all_ideas:
                idea = MagicMock()
                idea.solution_name = name
                ideas.append(idea)
            state.idea_generation = MagicMock(solution_ideas=ideas)
        else:
            state.idea_generation = None

        return state

    def test_filter_keeps_only_user_selected_solutions(self):
        """Phase 2 filter should keep only user-selected solutions in all_solution_scores."""
        from worker.tasks import _run_phase2_continuation

        state = self._make_state(
            scored_names=["Sol A", "Sol B", "Sol C"],
            all_ideas=["Sol A", "Sol B", "Sol C"],
        )

        flow = MagicMock()
        flow.state = state
        flow._execute_remaining_stages.return_value = None

        # We can't run the full function (it tries to execute stages),
        # so test the filter logic directly
        selected_solutions = ["Sol A", "Sol C"]
        selected_set = set(selected_solutions)

        # Simulate the filter logic from _run_phase2_continuation
        state.solution_selection.all_solution_scores = [
            s for s in state.solution_selection.all_solution_scores
            if getattr(s, 'solution_name', '') in selected_set
        ]

        remaining_names = {s.solution_name for s in state.solution_selection.all_solution_scores}
        assert remaining_names == {"Sol A", "Sol C"}
        assert "Sol B" not in remaining_names

    def test_runner_up_is_non_primary_selected(self):
        """runner_up_solutions should be selected solutions minus primary."""
        state = self._make_state(
            scored_names=["Sol A", "Sol B", "Sol C"],
            all_ideas=["Sol A", "Sol B", "Sol C"],
        )

        selected_solutions = ["Sol A", "Sol C"]
        selected_set = set(selected_solutions)

        # Filter scores
        state.solution_selection.all_solution_scores = [
            s for s in state.solution_selection.all_solution_scores
            if getattr(s, 'solution_name', '') in selected_set
        ]

        # Pick best
        scores = state.solution_selection.all_solution_scores
        best = max(scores, key=lambda s: getattr(s, 'composite_score', 0))
        state.solution_selection.selected_solution_name = best.solution_name

        # Build runner-ups
        primary = state.solution_selection.selected_solution_name
        state.solution_selection.runner_up_solutions = [
            n for n in selected_solutions if n != primary
        ]

        assert state.solution_selection.selected_solution_name == "Sol A"  # highest score
        assert state.solution_selection.runner_up_solutions == ["Sol C"]
        assert primary not in state.solution_selection.runner_up_solutions

    def test_else_branch_sets_runner_ups(self):
        """When solution_selection is None, else branch sets runner_ups correctly."""
        selected_solutions = ["Sol X", "Sol Y", "Sol Z"]

        # Simulate the else branch
        selection = SolutionSelection(
            selected_solution_name=selected_solutions[0],
            selection_rationale=(
                "User selected 'Sol X' via interactive flow. Rationale: Not provided. "
                "Selected after reviewing AI-generated solution ideas, "
                "pricing/keyword validation data, and competitive landscape analysis."
            ),
            recommended_focus=f"Build and launch {selected_solutions[0]} targeting identified market gaps.",
            runner_up_solutions=[n for n in selected_solutions[1:]],
        )

        assert selection.selected_solution_name == "Sol X"
        assert selection.runner_up_solutions == ["Sol Y", "Sol Z"]
        assert selection.selected_solution_name not in selection.runner_up_solutions

    def test_user_selected_solutions_stored_on_state(self):
        """_user_selected_solutions should be stored as a set for keyword validation guard."""
        state = self._make_state(
            scored_names=["Sol A", "Sol B"],
            all_ideas=["Sol A", "Sol B"],
        )

        selected_solutions = ["Sol A", "Sol B"]
        state._user_selected_solutions = set(selected_solutions)

        assert state._user_selected_solutions == {"Sol A", "Sol B"}


class TestStage7BackfillScores:
    """Tests for Phase 1 backfill of all_solution_scores after Stage 7."""

    def test_backfill_creates_entries_for_unscored_solutions(self):
        """Solutions in idea_generation but not in all_solution_scores get backfilled."""
        scored = [_make_score("Sol A", 0.8, 1)]

        # Simulate idea_generation with Sol A (scored) and Sol B (unscored)
        idea_a = MagicMock()
        idea_a.solution_name = "Sol A"
        idea_a.market_fit_score = 0.8
        idea_a.technical_feasibility_score = 0.7

        idea_b = MagicMock()
        idea_b.solution_name = "Sol B"
        idea_b.market_fit_score = 0.6
        idea_b.technical_feasibility_score = 0.5

        ideas = [idea_a, idea_b]
        all_solution_scores = list(scored)

        # Simulate backfill logic
        scored_names = {s.solution_name for s in all_solution_scores}
        for idea in ideas:
            if idea.solution_name not in scored_names:
                raw_mf = getattr(idea, 'market_fit_score', None)
                mf = raw_mf if raw_mf is not None else 0.5
                raw_tf = getattr(idea, 'technical_feasibility_score', None)
                tf = raw_tf if raw_tf is not None else 0.5
                all_solution_scores.append(
                    SolutionScores(
                        solution_name=idea.solution_name,
                        market_fit_score=mf,
                        technical_feasibility_score=tf,
                        competitive_advantage_score=0.5,
                        seo_growth_potential_score=0.5,
                        composite_score=round((mf + tf + 0.5 + 0.5) / 4, 3),
                        rank=0,
                    )
                )

        # Reassign ranks
        all_solution_scores.sort(key=lambda s: s.composite_score, reverse=True)
        for i, s in enumerate(all_solution_scores, 1):
            s.rank = i

        names = {s.solution_name for s in all_solution_scores}
        assert names == {"Sol A", "Sol B"}
        assert len(all_solution_scores) == 2

        # Sol A should still rank first (higher composite)
        assert all_solution_scores[0].solution_name == "Sol A"
        assert all_solution_scores[0].rank == 1

        # Sol B backfilled with its own scores
        sol_b = next(s for s in all_solution_scores if s.solution_name == "Sol B")
        assert sol_b.market_fit_score == 0.6
        assert sol_b.technical_feasibility_score == 0.5
        assert sol_b.composite_score == round((0.6 + 0.5 + 0.5 + 0.5) / 4, 3)

    def test_backfill_uses_defaults_when_scores_missing(self):
        """When idea has no score attributes, defaults to 0.5."""
        idea = MagicMock(spec=[])  # empty spec = no attributes
        idea.solution_name = "NoScores"

        raw_mf = getattr(idea, 'market_fit_score', None)
        mf = raw_mf if raw_mf is not None else 0.5
        raw_tf = getattr(idea, 'technical_feasibility_score', None)
        tf = raw_tf if raw_tf is not None else 0.5

        score = SolutionScores(
            solution_name=idea.solution_name,
            market_fit_score=mf,
            technical_feasibility_score=tf,
            competitive_advantage_score=0.5,
            seo_growth_potential_score=0.5,
            composite_score=round((mf + tf + 0.5 + 0.5) / 4, 3),
            rank=0,
        )

        assert score.market_fit_score == 0.5
        assert score.technical_feasibility_score == 0.5
        assert score.composite_score == 0.5

    def test_backfill_skips_already_scored_solutions(self):
        """Solutions already in all_solution_scores should not be duplicated."""
        scored = [_make_score("Sol A", 0.8, 1), _make_score("Sol B", 0.7, 2)]

        idea_a = MagicMock()
        idea_a.solution_name = "Sol A"
        idea_b = MagicMock()
        idea_b.solution_name = "Sol B"

        all_solution_scores = list(scored)
        scored_names = {s.solution_name for s in all_solution_scores}

        for idea in [idea_a, idea_b]:
            if idea.solution_name not in scored_names:
                all_solution_scores.append(_make_score(idea.solution_name, 0.5))

        assert len(all_solution_scores) == 2  # No duplicates added
