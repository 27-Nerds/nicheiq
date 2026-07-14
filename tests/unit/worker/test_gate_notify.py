"""Retry/idempotency behavior of notify_gate_reached / notify_gate_failed (Phase B).

notify_gate_reached mirrors notify_ideas_ready's contract exactly (it is likewise the job's
ONLY transition out of RUNNING/QUEUED for a gate stop): transient failures retry; a 409 with
state=CANCELLED returns quietly; any other 404/409 raises (a reached gate silently discarded
is a real loss); exhausted transient retries raise so the task's failure path takes over.

notify_gate_failed mirrors notify_regeneration_failed: best-effort, never raises (logged only)
— it is itself called from an exception handler, so raising again would mask the original error.
Instead it RETURNS success/failure (Codex review findings 4/6) so the caller (queue_consumer)
can fall through to the generic notify_job_failed path instead of treating a swallowed delivery
failure as a recovered job.
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import responses

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

_GATE_REACHED = re.compile(r".+/api/workers/gate-reached$")
_GATE_FAILED = re.compile(r".+/api/workers/gate-failed$")


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_success_first_attempt_posts_once(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED, json={}, status=200)
    from worker.progress import notify_gate_reached

    notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={"type": "x"})
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()
    body = responses.calls[0].request.body
    assert b'"gate_stage": 1' in body or b'"gate_stage":1' in body


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_idempotent_200_treated_as_delivered(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED, json={"idempotent": True}, status=200)
    from worker.progress import notify_gate_reached

    notify_gate_reached("job-1", gate_stage=4, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_409_cancelled_returns_quietly(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED,
                  json={"error": "Job cancelled", "state": "CANCELLED"}, status=409)
    from worker.progress import notify_gate_reached

    notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_409_other_state_raises_without_retry(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED,
                  json={"error": "Job not in expected state", "state": "FAILED"}, status=409)
    from worker.progress import notify_gate_reached

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_404_raises_without_retry(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED, json={"error": "Job not found"}, status=404)
    from worker.progress import notify_gate_reached

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_transient_failure_retries_then_succeeds(mock_sleep, _wid):
    responses.add(responses.POST, _GATE_REACHED, body=requests.exceptions.ConnectionError("down"))
    responses.add(responses.POST, _GATE_REACHED, json={}, status=200)
    from worker.progress import notify_gate_reached

    notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 2
    assert mock_sleep.call_count == 1


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_gate_reached_exhausted_retries_raise(mock_sleep, _wid):
    for _ in range(4):
        responses.add(responses.POST, _GATE_REACHED, body=requests.exceptions.ConnectionError("down"))
    from worker.progress import notify_gate_reached

    with pytest.raises(requests.exceptions.RequestException):
        notify_gate_reached("job-1", gate_stage=1, checkpoint_path="/cp", gate_artifact={})
    assert len(responses.calls) == 4
    assert mock_sleep.call_count == 3


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
def test_gate_failed_posts_and_never_raises_on_success(_wid):
    responses.add(responses.POST, _GATE_FAILED, json={}, status=200)
    from worker.progress import notify_gate_failed

    delivered = notify_gate_failed("job-1", gate_stage=4, error_message="boom")  # must not raise
    assert delivered is True
    assert len(responses.calls) == 1


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
def test_gate_failed_swallows_request_errors_but_reports_false(_wid):
    """Called from an exception handler (queue_consumer) — must never raise a NEW exception
    that would mask the original failure, but MUST report the delivery failure via its return
    value (Codex review findings 4/6) so the caller doesn't treat the job as recovered."""
    responses.add(responses.POST, _GATE_FAILED, body=requests.exceptions.ConnectionError("down"))
    from worker.progress import notify_gate_failed

    delivered = notify_gate_failed("job-1", gate_stage=1, error_message="boom")  # must not raise
    assert delivered is False
    assert len(responses.calls) == 1
