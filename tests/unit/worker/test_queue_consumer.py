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


# ── Reliable queue (2026-07-02 infra review): BLMOVE + processing ack + stale requeue ──

class TestReliableQueue:
    def _redis(self, entries=None, claims=None):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.lrange.return_value = list(entries or [])
        claims = claims or {}
        r.hget.side_effect = lambda h, k: claims.get(k)
        r.lrem.return_value = 1
        return r

    def test_ack_removes_entry_and_claim(self):
        from worker.queue_consumer import _ack_processing, PROCESSING_QUEUE, CLAIMS_HASH
        r = self._redis()
        _ack_processing(r, '{"job_id": "j1"}', "j1")
        r.lrem.assert_called_once_with(PROCESSING_QUEUE, 1, '{"job_id": "j1"}')
        r.hdel.assert_called_once_with(CLAIMS_HASH, "j1")

    def test_ack_fail_soft(self):
        import redis as redis_lib
        from worker.queue_consumer import _ack_processing
        r = self._redis()
        r.lrem.side_effect = redis_lib.RedisError("down")
        _ack_processing(r, "raw", "j1")   # must not raise — sweep reclaims later

    def test_sweep_requeues_stale_and_keeps_fresh(self):
        import time
        from worker.queue_consumer import (
            CLAIMS_HASH, PROCESSING_QUEUE, QUEUE_NAME, STALE_CLAIM_SECONDS,
            requeue_stale_processing,
        )
        now = time.time()
        stale = '{"job_id": "old"}'
        fresh = '{"job_id": "new"}'
        r = self._redis(entries=[stale, fresh],
                        claims={"old": f"{now - STALE_CLAIM_SECONDS - 10}:w1",
                                "new": f"{now - 30}:w2"})
        n = requeue_stale_processing(r)
        assert n == 1
        r.lpush.assert_called_once_with(QUEUE_NAME, stale)
        # fresh entry untouched on the queue side
        for call in r.lrem.call_args_list:
            assert call.args[2] != fresh

    def test_sweep_requeues_claimless_entry(self):
        from worker.queue_consumer import QUEUE_NAME, requeue_stale_processing
        r = self._redis(entries=['{"job_id": "ghost"}'], claims={})
        assert requeue_stale_processing(r) == 1
        r.lpush.assert_called_once_with(QUEUE_NAME, '{"job_id": "ghost"}')

    def test_sweep_drops_malformed_poison(self):
        from worker.queue_consumer import PROCESSING_QUEUE, requeue_stale_processing
        r = self._redis(entries=["not json at all"])
        assert requeue_stale_processing(r) == 0
        r.lrem.assert_called_once_with(PROCESSING_QUEUE, 1, "not json at all")
        r.lpush.assert_not_called()

    def test_sweep_fail_soft(self):
        import redis as redis_lib
        from worker.queue_consumer import requeue_stale_processing
        r = self._redis()
        r.lrange.side_effect = redis_lib.RedisError("down")
        assert requeue_stale_processing(r) == 0   # must not raise

    def test_consume_loop_uses_blmove_and_acks(self):
        # drive ONE loop iteration: blmove returns a job, then shutdown
        import worker.queue_consumer as qc
        from unittest.mock import MagicMock, patch

        r = self._redis()
        job = '{"job_id": "j9", "task_type": "research"}'
        r.blmove.side_effect = [job]

        def _stop(job_data):
            qc.shutdown_requested = True

        with patch.object(qc, "get_redis_connection", return_value=r), \
             patch.object(qc, "process_job", side_effect=_stop), \
             patch.object(qc, "start_heartbeat", create=True), \
             patch("worker.heartbeat.start_heartbeat"), \
             patch("worker.heartbeat.stop_heartbeat"), \
             patch("worker.heartbeat.get_worker_id", return_value="w1"), \
             patch.object(qc.signal, "signal"):
            qc.shutdown_requested = False
            qc._jobs_processed = 0
            try:
                qc.run_consumer()
            finally:
                qc.shutdown_requested = False
        r.blmove.assert_called_once_with(
            qc.QUEUE_NAME, qc.PROCESSING_QUEUE, timeout=5, src="RIGHT", dest="LEFT")
        r.lrem.assert_any_call(qc.PROCESSING_QUEUE, 1, job)   # acked after process_job
        r.hset.assert_called_once()                            # claim stamped

    def test_consume_loop_acks_even_when_process_job_raises(self):
        import worker.queue_consumer as qc
        from unittest.mock import patch

        r = self._redis()
        job = '{"job_id": "jX", "task_type": "research"}'
        r.blmove.side_effect = [job]

        def _boom(job_data):
            qc.shutdown_requested = True
            raise RuntimeError("unexpected")

        with patch.object(qc, "get_redis_connection", return_value=r), \
             patch.object(qc, "process_job", side_effect=_boom), \
             patch("worker.heartbeat.start_heartbeat"), \
             patch("worker.heartbeat.stop_heartbeat"), \
             patch("worker.heartbeat.get_worker_id", return_value="w1"), \
             patch.object(qc.signal, "signal"), \
             patch.object(qc.time, "sleep", create=True) if hasattr(qc, "time") else patch("time.sleep"):
            qc.shutdown_requested = False
            qc._jobs_processed = 0
            try:
                qc.run_consumer()
            finally:
                qc.shutdown_requested = False
        r.lrem.assert_any_call(qc.PROCESSING_QUEUE, 1, job)   # delivery attempt is DONE


class TestClaimRefresh:
    """Infra review round 2: without refresh, a job longer than STALE_CLAIM_SECONDS (2h) but
    under the backend's 4h max runtime gets sweep-requeued WHILE STILL RUNNING. The heartbeat
    thread re-stamps the claim each tick, so staleness now means 'worker actually dead'."""

    def test_heartbeat_tick_invokes_refresher_for_current_job(self):
        from unittest.mock import MagicMock, patch
        import worker.heartbeat as hb

        calls = []
        hb.set_claim_refresher(lambda job_id: calls.append(job_id))
        try:
            with patch.object(hb, "_send_heartbeat"), \
                 patch.object(hb, "_current_job_id", "j42"), \
                 patch.object(hb, "HEARTBEAT_INTERVAL_SECONDS", 0):
                hb._shutdown_event.clear()
                # run exactly one loop iteration: set shutdown from within wait
                original_wait = hb._shutdown_event.wait
                def _wait_once(timeout=None):
                    hb._shutdown_event.set()
                    return True
                with patch.object(hb._shutdown_event, "wait", side_effect=_wait_once):
                    hb._heartbeat_loop()
        finally:
            hb.set_claim_refresher(None)
            hb._shutdown_event.clear()
        assert calls == ["j42"]

    def test_refresher_exception_never_kills_thread(self):
        from unittest.mock import patch
        import worker.heartbeat as hb

        def _boom(job_id):
            raise RuntimeError("redis down")
        hb.set_claim_refresher(_boom)
        try:
            with patch.object(hb, "_send_heartbeat"), \
                 patch.object(hb, "_current_job_id", "j1"):
                def _wait_once(timeout=None):
                    hb._shutdown_event.set()
                    return True
                with patch.object(hb._shutdown_event, "wait", side_effect=_wait_once):
                    hb._heartbeat_loop()   # must not raise
        finally:
            hb.set_claim_refresher(None)
            hb._shutdown_event.clear()

    def test_consumer_registers_refresher(self):
        # source-level pin: run_consumer wires set_claim_refresher before consuming
        import inspect
        import worker.queue_consumer as qc
        src = inspect.getsource(qc.run_consumer)
        assert "set_claim_refresher(_refresh_claim)" in src
        assert src.index("set_claim_refresher") < src.index("requeue_stale_processing(redis_conn)")
