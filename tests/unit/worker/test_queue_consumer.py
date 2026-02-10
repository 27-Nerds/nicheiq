"""Tests for queue_consumer job routing and completion handling."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import patch, MagicMock


class TestProcessJobRouting:
    """Tests for process_job task routing logic."""

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_research_phase2_routes_correctly(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_research_phase2') as mock_task:
            mock_task.return_value = {"status": "completed"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research_phase2",
                "checkpoint_path": "/tmp/cp",
                "selected_solutions": ["Sol1", "Sol2"],
            })
            mock_task.assert_called_once()
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["selected_solutions"] == ["Sol1", "Sol2"]

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_research_phase2_backward_compat_selected_solution(
        self, mock_started, mock_set_job, mock_completed
    ):
        """When only selected_solution (string) is provided, it is wrapped in a list."""
        with patch('worker.tasks.run_research_phase2') as mock_task:
            mock_task.return_value = {"status": "completed"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research_phase2",
                "checkpoint_path": "/tmp/cp",
                "selected_solution": "Sol1",
            })
            mock_task.assert_called_once()
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["selected_solutions"] == ["Sol1"]

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_regenerate_ideas_routes_correctly(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_regenerate_ideas') as mock_task:
            mock_task.return_value = {"status": "regenerated"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "regenerate_ideas",
                "checkpoint_path": "/tmp/cp",
                "niche": "test",
            })
            mock_task.assert_called_once()

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_interactive_mode_routes_to_interactive_research(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_interactive_research') as mock_task:
            mock_task.return_value = {"status": "awaiting_selection"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research",
                "niche": "test niche",
                "job_mode": "interactive",
            })
            mock_task.assert_called_once()

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_interactive_resume_routes_to_interactive_research(
        self, mock_started, mock_set_job, mock_completed
    ):
        """resume=true with job_mode=interactive -> run_interactive_research with resume=True."""
        with patch('worker.tasks.run_interactive_research') as mock_task:
            mock_task.return_value = {"status": "awaiting_selection"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "niche": "test niche",
                "job_mode": "interactive",
                "resume": True,
            })
            mock_task.assert_called_once()
            # Verify resume=True is passed
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["resume"] is True

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_default_research_routes_correctly(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_research_job') as mock_task:
            mock_task.return_value = {"status": "completed"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research",
                "niche": "test niche",
            })
            mock_task.assert_called_once()

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_landing_page_routes_correctly(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_landing_page_only') as mock_task:
            mock_task.return_value = {"status": "completed"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "landing_page",
                "report_path": "/tmp/report.json",
            })
            mock_task.assert_called_once()


class TestCompletionHandling:
    """Tests for completion notification logic."""

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_awaiting_selection_skips_completion_notification(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_interactive_research') as mock_task:
            mock_task.return_value = {"status": "awaiting_selection"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research",
                "niche": "test",
                "job_mode": "interactive",
            })
            mock_completed.assert_not_called()

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_regenerate_ideas_calls_completion(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_regenerate_ideas') as mock_task:
            mock_task.return_value = {"status": "regenerated"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "regenerate_ideas",
                "checkpoint_path": "/tmp/cp",
                "niche": "test",
            })
            mock_completed.assert_called_once_with("job-1")

    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_normal_completion_calls_notification(
        self, mock_started, mock_set_job, mock_completed
    ):
        with patch('worker.tasks.run_research_job') as mock_task:
            mock_task.return_value = {"status": "completed"}
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research",
                "niche": "test",
            })
            mock_completed.assert_called_once_with("job-1")


class TestRegenerationFailureHandling:
    """Tests for regeneration failure revert logic in queue consumer."""

    @patch('worker.heartbeat.notify_job_failed')
    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_regeneration_failure_calls_notify_regeneration_failed(
        self, mock_started, mock_set_job, mock_completed, mock_job_failed
    ):
        """When regenerate_ideas fails, notify_regeneration_failed is called instead of notify_job_failed."""
        with patch('worker.tasks.run_regenerate_ideas') as mock_task:
            mock_task.side_effect = RuntimeError("LLM rate limit exceeded")
            with patch('worker.progress.notify_regeneration_failed') as mock_regen_failed:
                from worker.queue_consumer import process_job
                process_job({
                    "job_id": "job-1",
                    "task_type": "regenerate_ideas",
                    "checkpoint_path": "/tmp/cp",
                    "niche": "test",
                })
                mock_regen_failed.assert_called_once_with("job-1", "LLM rate limit exceeded")
                mock_job_failed.assert_not_called()

    @patch('worker.heartbeat.notify_job_failed')
    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_regeneration_failure_falls_through_to_job_failed_on_revert_error(
        self, mock_started, mock_set_job, mock_completed, mock_job_failed
    ):
        """When both regeneration and revert notification fail, falls through to notify_job_failed."""
        with patch('worker.tasks.run_regenerate_ideas') as mock_task:
            mock_task.side_effect = RuntimeError("LLM error")
            with patch('worker.progress.notify_regeneration_failed') as mock_regen_failed:
                mock_regen_failed.side_effect = Exception("Backend unreachable")
                from worker.queue_consumer import process_job
                process_job({
                    "job_id": "job-1",
                    "task_type": "regenerate_ideas",
                    "checkpoint_path": "/tmp/cp",
                    "niche": "test",
                })
                mock_regen_failed.assert_called_once()
                mock_job_failed.assert_called_once_with("job-1", "LLM error", None)

    @patch('worker.heartbeat.notify_job_failed')
    @patch('worker.heartbeat.notify_job_completed')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_started', return_value=True)
    def test_non_regeneration_failure_uses_normal_job_failed(
        self, mock_started, mock_set_job, mock_completed, mock_job_failed
    ):
        """Non-regeneration task failures use the standard notify_job_failed path."""
        with patch('worker.tasks.run_research_job') as mock_task:
            mock_task.side_effect = RuntimeError("Pipeline crashed")
            from worker.queue_consumer import process_job
            process_job({
                "job_id": "job-1",
                "task_type": "research",
                "niche": "test",
            })
            mock_job_failed.assert_called_once()
