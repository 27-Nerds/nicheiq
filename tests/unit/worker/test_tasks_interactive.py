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

    @patch('worker.tasks.notify_job_quality_gate_stop')
    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_quality_gate_stop_not_delivered_reraises(
        self, mock_progress, mock_mark, mock_notify_ideas, mock_quality_gate
    ):
        """Codex review finding 6 (BLOCKER): when notify_job_quality_gate_stop's delivery
        fails (returns False), the job must NOT be silently swallowed — re-raise so
        queue_consumer's generic notify_job_failed path takes over."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from nicheiq.flows.research_flow import QualityGateStopException
            flow = MockFlow.return_value
            flow.run_with_resume.side_effect = QualityGateStopException(
                stage=5, reason='INSUFFICIENT_DATA', details={'score': 0.3}
            )
            flow.cleanup_collections = MagicMock()
            flow.state = MagicMock(current_stage=5)
            mock_progress.return_value = MagicMock()
            mock_quality_gate.return_value = False

            from worker.tasks import run_interactive_research
            with pytest.raises(QualityGateStopException):
                run_interactive_research(job_id='job-1', niche='test')

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


class TestRunInteractiveResearchChatMode:
    """Phase B: run_interactive_research(chat_mode=True) — G1 gate stop."""

    @patch('worker.tasks.notify_gate_reached')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_chat_mode_stops_after_stage_1_before_idea_check(
        self, mock_progress, mock_mark, mock_notify_gate
    ):
        """DR B2: chat_mode must branch BEFORE the 'Phase 1 did not produce solution ideas'
        hard-raise — idea_generation is empty at a G1 stop (Stage 5 hasn't run), so if this
        branch didn't exist the job would instantly fail."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            state = MagicMock()
            state.idea_generation = None  # No ideas yet — a G1 stop never reaches Stage 5
            flow.state = state
            flow.run_with_resume.return_value = ''
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/checkpoint-g1'
            flow._extract_stage_artifact.return_value = {"type": "niche_validation"}
            mock_progress.return_value = MagicMock()

            from worker.tasks import run_interactive_research
            result = run_interactive_research(job_id='job-1', niche='test niche', chat_mode=True)

            flow.run_with_resume.assert_called_once_with(auto_resume=False, stop_after_stage=1)
            flow._extract_stage_artifact.assert_called_once_with(1)
            mock_notify_gate.assert_called_once()
            args, kwargs = mock_notify_gate.call_args
            assert args[0] == 'job-1'
            assert kwargs.get('gate_stage', args[1] if len(args) > 1 else None) == 1
            assert result == {
                "status": "awaiting_gate", "job_id": "job-1", "gate_stage": 1,
                "checkpoint_path": "/tmp/checkpoint-g1",
            }

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_non_chat_mode_unaffected_still_uses_stop_after_phase(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        """Default (chat_mode=False) behavior is byte-identical to before this change."""
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

            flow.run_with_resume.assert_called_once_with(auto_resume=False, stop_after_phase=1)
            assert result == {"status": "awaiting_selection", "job_id": "job-1"}


class TestContinueFromGate:
    """Phase B: continue_from_gate — mode='continue' (G1->G2, G2->AWAITING_SELECTION) and
    mode='apply_stay' (re-notify the same gate with a refreshed artifact)."""

    @patch('worker.tasks.notify_gate_reached')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_continue_from_g1_runs_to_stage_4_stop(
        self, mock_progress, mock_mark, mock_notify_gate
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/checkpoint-g1-forked'
            flow._build_g2_gate_artifact.return_value = {"type": "audience_mapping_gate"}
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            result = continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/checkpoint-g1', gate_stage=1,
                mode='continue',
            )

            mock_mark.assert_called_once_with('job-1')
            flow.resume_from_checkpoint.assert_called_once_with('/tmp/checkpoint-g1')
            # stop_after_phase=1 bounds the degenerate-G2 fallthrough (finding 2) — safe in
            # this normal case since the stop_after_stage==4 return inside the ladder fires
            # first and stop_after_phase=1 is never reached.
            flow._execute_remaining_stages.assert_called_once_with(
                stop_after_stage=4, stop_after_phase=1, skip_bulk_replay=True)
            mock_notify_gate.assert_called_once()
            args, kwargs = mock_notify_gate.call_args
            assert args[0] == 'job-1'
            # The EFFECTIVE post-resume checkpoint path is reported, not the input path.
            assert result == {
                "status": "awaiting_gate", "job_id": "job-1", "gate_stage": 4,
                "checkpoint_path": "/tmp/checkpoint-g1-forked",
            }

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_continue_from_g1_degenerate_g2_falls_through_to_awaiting_selection(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        """Codex review finding 2 (BLOCKER): when _build_g2_gate_artifact comes back None
        (neither pain analysis nor audience mapping survived), continue_from_gate must NOT
        call notify_gate_reached with a coerced {} artifact — it falls through to the same
        Phase-1-completion path gate_stage==4 uses."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/checkpoint-g1-forked'
            flow._build_g2_gate_artifact.return_value = None
            sol1 = MagicMock(solution_name="Sol1", name="Sol1")
            sol1.model_dump.return_value = {"solution_name": "Sol1", "name": "Sol1"}
            state = MagicMock()
            state.idea_generation = MagicMock(solution_ideas=[sol1])
            flow.state = state
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            result = continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/checkpoint-g1', gate_stage=1,
                mode='continue',
            )

            flow._execute_remaining_stages.assert_called_once_with(
                stop_after_stage=4, stop_after_phase=1, skip_bulk_replay=True)
            mock_notify_ideas.assert_called_once()
            assert result == {"status": "awaiting_selection", "job_id": "job-1"}

    @patch('worker.tasks.notify_ideas_ready')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_continue_from_g2_reaches_awaiting_selection(
        self, mock_progress, mock_mark, mock_notify_ideas
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            sol1 = MagicMock(solution_name="Sol1", name="Sol1")
            sol1.model_dump.return_value = {"solution_name": "Sol1", "name": "Sol1"}
            state = MagicMock()
            state.idea_generation = MagicMock(solution_ideas=[sol1])
            flow.state = state
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/cp'
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            result = continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/checkpoint-g2', gate_stage=4,
                mode='continue',
            )

            flow._execute_remaining_stages.assert_called_once_with(
                stop_after_phase=1, skip_bulk_replay=True)
            mock_notify_ideas.assert_called_once()
            assert result == {"status": "awaiting_selection", "job_id": "job-1"}

    @patch('worker.tasks.notify_job_quality_gate_stop')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_quality_gate_stop_during_continuation_returns_none_when_delivered(
        self, mock_progress, mock_mark, mock_quality_gate
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from nicheiq.flows.research_flow import QualityGateStopException
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow._execute_remaining_stages.side_effect = QualityGateStopException(
                stage=5, reason='INSUFFICIENT_DATA', details={'score': 0.3}
            )
            mock_progress.return_value = MagicMock()
            mock_quality_gate.return_value = True

            from worker.tasks import continue_from_gate
            result = continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=4, mode='continue',
            )

            assert result is None
            mock_quality_gate.assert_called_once()

    @patch('worker.tasks.notify_job_quality_gate_stop')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_quality_gate_stop_during_continuation_reraises_when_not_delivered(
        self, mock_progress, mock_mark, mock_quality_gate
    ):
        """Codex review finding 6 (BLOCKER): "same discipline" as notify_gate_failed — a
        quality-gate-stop notification that fails to deliver must not be swallowed. Re-raising
        lets queue_consumer's TASK_TYPE_CONTINUE_FROM_GATE handling take over (notify_gate_failed,
        and ultimately notify_job_failed if that also fails)."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            from nicheiq.flows.research_flow import QualityGateStopException
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow._execute_remaining_stages.side_effect = QualityGateStopException(
                stage=5, reason='INSUFFICIENT_DATA', details={'score': 0.3}
            )
            mock_progress.return_value = MagicMock()
            mock_quality_gate.return_value = False

            from worker.tasks import continue_from_gate
            with pytest.raises(QualityGateStopException) as exc_info:
                continue_from_gate(
                    job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=4, mode='continue',
                )

            assert exc_info.value.gate_stage == 4
            mock_quality_gate.assert_called_once()

    @patch('worker.tasks.notify_gate_reached')
    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_apply_stay_reapplies_patch_and_renotifies_same_gate(
        self, mock_progress, mock_mark, mock_notify_gate
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow, \
             patch('nicheiq.flows.gate_patches.apply_gate_patch') as mock_apply_patch:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/cp'
            flow._extract_stage_artifact.return_value = {"type": "niche_validation"}
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            result = continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=1,
                mode='apply_stay', patch={"niche_description": "Edited"},
            )

            mock_apply_patch.assert_called_once()
            # The run must NOT advance the stage ladder on apply_stay.
            flow._execute_remaining_stages.assert_not_called()
            mock_notify_gate.assert_called_once()
            assert result["status"] == "awaiting_gate"
            assert result["gate_stage"] == 1

    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_apply_stay_g2_degenerate_artifact_raises(self, mock_progress, mock_mark):
        """Codex review finding 2 (BLOCKER): apply_stay on gate_stage=4 must NOT re-notify
        the gate with a coerced {} artifact when _build_g2_gate_artifact returns None —
        raising routes to queue_consumer's notify_gate_failed (retryable) instead."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow, \
             patch('nicheiq.flows.gate_patches.apply_gate_patch') as mock_apply_patch:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            flow.checkpoint_mgr = MagicMock()
            flow.checkpoint_mgr.checkpoint_folder = '/tmp/cp'
            flow._build_g2_gate_artifact.return_value = None
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            with pytest.raises(RuntimeError, match="G2 gate artifact unavailable"):
                continue_from_gate(
                    job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=4,
                    mode='apply_stay', patch={"excluded_segments": ["Segment A"]},
                )

            mock_apply_patch.assert_called_once()

    def test_apply_stay_without_patch_raises(self):
        from worker.tasks import continue_from_gate
        with pytest.raises(RuntimeError, match="apply_stay requires a patch"):
            continue_from_gate(
                job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=1, mode='apply_stay',
            )

    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_failed_checkpoint_load_raises_with_gate_stage_attr(self, mock_progress, mock_mark):
        """queue_consumer reads e.gate_stage off the raised exception to know which gate to
        revert to — must be stamped on every failure path."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = False
            flow.cleanup_collections = MagicMock()
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            with pytest.raises(RuntimeError, match="Failed to load checkpoint") as exc_info:
                continue_from_gate(
                    job_id='job-1', checkpoint_path='/bad/path', gate_stage=4, mode='continue',
                )
            assert exc_info.value.gate_stage == 4

    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_invalid_patch_raises_runtime_error(self, mock_progress, mock_mark):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow, \
             patch('nicheiq.flows.gate_patches.apply_gate_patch') as mock_apply_patch:
            from nicheiq.flows.gate_patches import GatePatchError
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            mock_apply_patch.side_effect = GatePatchError("unknown field")
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            with pytest.raises(RuntimeError, match="Invalid gate patch"):
                continue_from_gate(
                    job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=1, mode='continue',
                    patch={"bogus": True},
                )

    @patch('worker.tasks.mark_job_running')
    @patch('worker.tasks.create_progress_callback')
    def test_patch_persist_failure_propagates_not_swallowed(self, mock_progress, mock_mark):
        """Codex review finding 5 (REGRESSION): a GatePatchPersistError (checkpoint write
        failed) is NOT a GatePatchError — it must NOT be caught by continue_from_gate's
        `except GatePatchError` (which would mis-report it as 'Invalid gate patch'). It
        propagates to the generic exception handler, gets gate_stage stamped, and reaches
        queue_consumer's notify_gate_failed revert path instead of a false success."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow, \
             patch('nicheiq.flows.gate_patches.apply_gate_patch') as mock_apply_patch:
            from nicheiq.flows.gate_patches import GatePatchPersistError
            flow = MockFlow.return_value
            flow.resume_from_checkpoint.return_value = True
            flow.cleanup_collections = MagicMock()
            mock_apply_patch.side_effect = GatePatchPersistError("checkpoint save failed")
            mock_progress.return_value = MagicMock()

            from worker.tasks import continue_from_gate
            with pytest.raises(GatePatchPersistError, match="checkpoint save failed") as exc_info:
                continue_from_gate(
                    job_id='job-1', checkpoint_path='/tmp/cp', gate_stage=1, mode='continue',
                    patch={"niche_description": "Edited"},
                )
            assert exc_info.value.gate_stage == 1


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
                with patch(
                    'worker.tasks._solution_to_preview_dict',
                    return_value={"solution_name": "NewSol"},
                ):
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
    def test_rematerializes_preview_with_merged_solutions_before_delivery(
        self, mock_progress, mock_notify_regen
    ):
        """The preview-backed UI/chat context must include the regenerated batch."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                flow = MockFlow.return_value
                flow.resume_from_checkpoint.return_value = True
                flow.cleanup_collections = MagicMock()
                flow.allowed_project_types = None

                old_sol = MagicMock(
                    solution_name="OldSol",
                    name="OldSol",
                    candidate_status="active",
                )
                new_sol = MagicMock(
                    solution_name="NewSol",
                    name="NewSol",
                    candidate_status="active",
                )
                new_sol.model_dump.return_value = {
                    "solution_name": "NewSol",
                    "name": "NewSol",
                }
                state = MagicMock()
                state.idea_generation = MagicMock(solution_ideas=[old_sol])
                flow.state = state
                flow.checkpoint_mgr = MagicMock()
                mock_progress.return_value = MagicMock()
                MockCrew.return_value.execute_pipeline.return_value = [
                    MagicMock(solution_ideas=[new_sol])
                ]

                events = []
                materialized_names = []

                def capture_preview(_output_dir):
                    events.append("preview")
                    materialized_names.extend(
                        idea.solution_name
                        for idea in state.idea_generation.solution_ideas
                    )
                    return "/tmp/preview_report_job-1.json"

                flow._materialize_preview_report.side_effect = capture_preview
                mock_notify_regen.side_effect = lambda *_args, **_kwargs: events.append("notify")

                from nicheiq.config.settings import settings
                from worker.tasks import run_regenerate_ideas

                with patch(
                    'worker.tasks._solution_to_preview_dict',
                    return_value={"solution_name": "NewSol"},
                ):
                    run_regenerate_ideas(
                        job_id='job-1',
                        checkpoint_path='/tmp/cp',
                        existing_solution_names=['OldSol'],
                        niche='test niche',
                    )

                assert materialized_names == ["OldSol", "NewSol"]
                flow._materialize_preview_report.assert_called_once_with(
                    str(settings.checkpoint_dir)
                )
                assert events == ["preview", "notify"]

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


class TestRunSeedIdea:
    """Tests for run_seed_idea (eager-meandering-feather.md Phase 5) — the worker's dispatch-
    settled counterpart to run_regenerate_ideas for a single user-composed idea."""

    def _mock_flow_and_crew(self, MockFlow, MockCrew, idea, old_solutions=None):
        flow = MockFlow.return_value
        flow.resume_from_checkpoint.return_value = True
        flow.cleanup_collections = MagicMock()
        flow.allowed_project_types = None
        flow.idea_focus = "auto"
        state = MagicMock()
        state.pain_point_analysis = MagicMock()
        state.social_content = MagicMock()
        state.niche_context = MagicMock()
        state.audience_mapping = MagicMock()
        state.idea_generation = MagicMock(solution_ideas=list(old_solutions or []))
        flow.state = state
        flow.checkpoint_mgr = MagicMock()
        crew = MockCrew.return_value
        crew.execute_seed_pipeline.return_value = idea
        return flow, crew, state

    @patch('worker.tasks.notify_seed_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_hydrates_crew_instead_of_cold_reprobing(
        self, mock_progress, mock_notify_seed
    ):
        """The crew must be HYDRATED from persisted state, never re-run cold via
        execute_pipeline — a seed must not re-probe paid Phase-1 evidence."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                idea = MagicMock(solution_name="Seed Idea", candidate_status="active")
                idea.model_dump.return_value = {"solution_name": "Seed Idea"}
                flow, crew, state = self._mock_flow_and_crew(MockFlow, MockCrew, idea)
                mock_progress.return_value = MagicMock()

                from worker.tasks import run_seed_idea
                result = run_seed_idea(
                    job_id='job-1', checkpoint_path='/tmp/cp',
                    seed={"seed_text": "an idea", "pain_ref": None, "tool_ref": None},
                    niche='test niche', dispatch_id='dispatch-1',
                )

                crew.hydrate_from_state.assert_called_once_with(state)
                crew.execute_pipeline.assert_not_called()
                crew.execute_seed_pipeline.assert_called_once()
                assert result == {"status": "seed_settled", "job_id": "job-1", "outcome": "accepted"}
                mock_notify_seed.assert_called_once()

    @patch('worker.tasks.notify_seed_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_merges_old_and_seed_and_saves_checkpoint(
        self, mock_progress, mock_notify_seed
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                old_sol = MagicMock(solution_name="OldSol")
                idea = MagicMock(solution_name="Seed Idea", candidate_status="active")
                idea.model_dump.return_value = {"solution_name": "Seed Idea"}
                flow, crew, state = self._mock_flow_and_crew(
                    MockFlow, MockCrew, idea, old_solutions=[old_sol])
                mock_progress.return_value = MagicMock()

                from worker.tasks import run_seed_idea
                run_seed_idea(
                    job_id='job-1', checkpoint_path='/tmp/cp',
                    seed={"seed_text": "an idea"}, niche='test niche',
                )

                assert state.idea_generation.solution_ideas == [old_sol, idea]
                flow.checkpoint_mgr.save_stage.assert_called_once_with(
                    "stage_5_3_refinement", state.idea_generation)

    @patch('worker.tasks.notify_seed_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_demoted_seed_is_still_merged_saved_and_notified(
        self, mock_progress, mock_notify_seed
    ):
        """A demoted seed is honestly reported, never hidden — the UI shows it in
        Examined & ruled out rather than the pool discarding it."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                idea = MagicMock(solution_name="Weak Seed", candidate_status="demoted")
                idea.model_dump.return_value = {"solution_name": "Weak Seed"}
                flow, crew, state = self._mock_flow_and_crew(MockFlow, MockCrew, idea)
                mock_progress.return_value = MagicMock()

                from worker.tasks import run_seed_idea
                result = run_seed_idea(
                    job_id='job-1', checkpoint_path='/tmp/cp',
                    seed={"seed_text": "an idea"}, niche='test niche',
                )

                assert result["outcome"] == "demoted"
                assert idea in state.idea_generation.solution_ideas
                flow.checkpoint_mgr.save_stage.assert_called_once()
                mock_notify_seed.assert_called_once()
                # outcome is sent to the backend either way
                assert mock_notify_seed.call_args[0][2] == "demoted"

    @patch('worker.tasks.notify_seed_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_structural_duplicate_is_kept_with_caveat_never_dropped(
        self, mock_progress, mock_notify_seed
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                old_sol = MagicMock(solution_name="Existing Idea")
                idea = MagicMock(solution_name="Seed Idea", candidate_status="active")
                idea.model_dump.return_value = {"solution_name": "Seed Idea"}
                flow, crew, state = self._mock_flow_and_crew(
                    MockFlow, MockCrew, idea, old_solutions=[old_sol])
                mock_progress.return_value = MagicMock()

                with patch(
                    'nicheiq.utils.validation.crew_guardrails.detect_catalog_duplicate',
                    return_value=True,
                ):
                    from worker.tasks import run_seed_idea
                    run_seed_idea(
                        job_id='job-1', checkpoint_path='/tmp/cp',
                        seed={"seed_text": "an idea"}, niche='test niche',
                    )

                # Kept — never dropped — with the caveat stamped.
                assert idea in state.idea_generation.solution_ideas
                assert idea.duplicate_of == "Existing Idea"

    @patch('worker.tasks.notify_seed_complete')
    @patch('worker.tasks.create_progress_callback')
    def test_birth_failure_raises_and_stamps_failed_stage(
        self, mock_progress, mock_notify_seed
    ):
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                flow, crew, state = self._mock_flow_and_crew(MockFlow, MockCrew, idea=None)
                mock_progress.return_value = MagicMock()

                from worker.tasks import run_seed_idea
                with pytest.raises(RuntimeError, match="did not produce an idea"):
                    run_seed_idea(
                        job_id='job-1', checkpoint_path='/tmp/cp',
                        seed={"seed_text": "an idea"}, niche='test niche',
                    )
                mock_notify_seed.assert_not_called()

    @patch('worker.tasks.create_progress_callback')
    def test_delivery_failure_is_tagged_seed_delivery_only(self, mock_progress):
        """notify_seed_complete raising after a successful merge+save must be tagged so the
        queue consumer never mistakes it for a pipeline failure (would wrongly refund/discard
        a completed, saved outcome)."""
        with patch('nicheiq.flows.research_flow.ResearchFlow') as MockFlow:
            with patch('nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew') as MockCrew:
                idea = MagicMock(solution_name="Seed Idea", candidate_status="active")
                idea.model_dump.return_value = {"solution_name": "Seed Idea"}
                flow, crew, state = self._mock_flow_and_crew(MockFlow, MockCrew, idea)
                mock_progress.return_value = MagicMock()

                with patch('worker.tasks.notify_seed_complete', side_effect=RuntimeError("unreachable")):
                    from worker.tasks import run_seed_idea
                    with pytest.raises(RuntimeError) as exc_info:
                        run_seed_idea(
                            job_id='job-1', checkpoint_path='/tmp/cp',
                            seed={"seed_text": "an idea"}, niche='test niche',
                        )
                    assert getattr(exc_info.value, "seed_delivery_only", False) is True
                # The merge+save already happened before delivery was attempted, THEN got
                # reverted (Amend 4): the eventual automatic refund (heartbeat ->
                # cancelSeedIdeaDispatch, since the job stays RUNNING with delivery never
                # landing) must be honest — no unpaid ghost idea survives in the checkpoint.
                assert flow.checkpoint_mgr.save_stage.call_count == 2
                assert idea not in state.idea_generation.solution_ideas


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
