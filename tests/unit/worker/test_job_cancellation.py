"""Tests for job cancellation handling in worker."""

import sys
from pathlib import Path

# Add project root to path so worker module can be imported
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import patch, MagicMock


class TestNotifyJobStarted:
    """Tests for notify_job_started cancellation handling."""

    @patch('worker.heartbeat.requests.post')
    def test_returns_false_when_should_cancel_true(self, mock_post):
        """notify_job_started returns False when backend signals cancellation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok', 'shouldCancel': True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        from worker.heartbeat import notify_job_started
        result = notify_job_started('job-123')

        assert result is False

    @patch('worker.heartbeat.requests.post')
    def test_returns_true_when_should_cancel_false(self, mock_post):
        """notify_job_started returns True when job should proceed."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok', 'shouldCancel': False}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        from worker.heartbeat import notify_job_started
        result = notify_job_started('job-123')

        assert result is True

    @patch('worker.heartbeat.requests.post')
    def test_returns_true_when_should_cancel_not_in_response(self, mock_post):
        """notify_job_started returns True when shouldCancel is not in response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        from worker.heartbeat import notify_job_started
        result = notify_job_started('job-123')

        assert result is True

    @patch('worker.heartbeat.requests.post')
    def test_returns_true_on_network_error(self, mock_post):
        """notify_job_started returns True (proceed) on network failure."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        from worker.heartbeat import notify_job_started
        result = notify_job_started('job-123')

        assert result is True  # Proceed anyway if backend unreachable

    @patch('worker.heartbeat.requests.post')
    def test_returns_true_on_timeout(self, mock_post):
        """notify_job_started returns True (proceed) on timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        from worker.heartbeat import notify_job_started
        result = notify_job_started('job-123')

        assert result is True  # Proceed anyway if backend unreachable


class TestProcessJobCancellation:
    """Tests for queue_consumer skipping cancelled jobs."""

    @patch('worker.heartbeat.notify_job_started')
    @patch('worker.heartbeat.set_current_job')
    def test_skips_processing_when_job_cancelled(
        self, mock_set_job, mock_notify
    ):
        """process_job returns early when job is cancelled."""
        mock_notify.return_value = False  # Job was cancelled

        from worker.queue_consumer import process_job
        job_data = {'job_id': 'job-123', 'niche': 'test', 'task_type': 'research'}

        # Should return without running research
        with patch('worker.tasks.run_research_job') as mock_run:
            process_job(job_data)
            mock_run.assert_not_called()

        # Should set job_id initially and clear it after skipping
        # Call count is 3: set(job_id), set(None) in early return, set(None) in finally
        mock_set_job.assert_any_call('job-123')
        mock_set_job.assert_any_call(None)

    @patch('worker.heartbeat.notify_job_started')
    @patch('worker.heartbeat.set_current_job')
    @patch('worker.heartbeat.notify_job_completed')
    def test_proceeds_when_job_not_cancelled(
        self, mock_notify_completed, mock_set_job, mock_notify_started
    ):
        """process_job continues when job is not cancelled."""
        mock_notify_started.return_value = True  # Job should proceed
        mock_notify_completed.return_value = True

        from worker.queue_consumer import process_job
        job_data = {
            'job_id': 'job-123',
            'niche': 'test niche',
            'task_type': 'research',
            'user_id': 'user-1',
        }

        with patch('worker.tasks.run_research_job') as mock_run:
            mock_run.return_value = {'success': True}
            process_job(job_data)
            mock_run.assert_called_once()

    @patch('worker.heartbeat.notify_job_started')
    @patch('worker.heartbeat.set_current_job')
    def test_skips_landing_page_task_when_cancelled(
        self, mock_set_job, mock_notify
    ):
        """process_job skips landing page task when cancelled."""
        mock_notify.return_value = False  # Job was cancelled

        from worker.queue_consumer import process_job
        job_data = {
            'job_id': 'job-123',
            'task_type': 'landing_page',
            'report_path': '/some/path.json',
        }

        with patch('worker.tasks.run_landing_page_only') as mock_run:
            process_job(job_data)
            mock_run.assert_not_called()
