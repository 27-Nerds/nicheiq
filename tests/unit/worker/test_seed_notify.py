"""Retry/idempotency behavior of notify_seed_complete / notify_seed_failed
(eager-meandering-feather.md Phase 5).

notify_seed_complete mirrors notify_gate_reached's contract exactly (it is likewise the seed
op's ONLY transition out of QUEUED/RUNNING): transient failures retry; a 409 with
state=CANCELLED returns quietly; any other 404/409 raises (a saved-but-undelivered outcome is a
real loss); exhausted transient retries raise so the caller (run_seed_idea) can tag the
exception `seed_delivery_only` and the task's failure path never mistakes it for a pipeline
failure.

notify_seed_failed mirrors notify_gate_failed: never raises (it is itself called from an
exception handler) but RETURNS success/failure so the caller (queue_consumer) can tell a
delivered revert from an undelivered one — and, for a seed op, must NEVER fall through to the
generic notify_job_failed path either way (that would refund the wrong charge).
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

_SEED_COMPLETE = re.compile(r".+/api/workers/seed-complete$")
_SEED_FAILED = re.compile(r".+/api/workers/seed-failed$")


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_success_first_attempt_posts_once(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE, json={}, status=200)
    from worker.progress import notify_seed_complete

    notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()
    body = responses.calls[0].request.body
    assert b'"outcome": "accepted"' in body or b'"outcome":"accepted"' in body


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_idempotent_200_treated_as_delivered(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE, json={"idempotent": True}, status=200)
    from worker.progress import notify_seed_complete

    notify_seed_complete("job-1", {"solution_name": "S"}, "demoted")
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_409_cancelled_returns_quietly(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE,
                  json={"error": "Job cancelled", "state": "CANCELLED"}, status=409)
    from worker.progress import notify_seed_complete

    notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")  # must not raise
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_409_other_state_raises_without_retry(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE,
                  json={"error": "Job not in expected state", "state": "FAILED"}, status=409)
    from worker.progress import notify_seed_complete

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_404_raises_without_retry(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE, json={"error": "Job not found"}, status=404)
    from worker.progress import notify_seed_complete

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_transient_failure_retries_then_succeeds(mock_sleep, _wid):
    responses.add(responses.POST, _SEED_COMPLETE, body=requests.exceptions.ConnectionError("down"))
    responses.add(responses.POST, _SEED_COMPLETE, json={}, status=200)
    from worker.progress import notify_seed_complete

    notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")
    assert len(responses.calls) == 2
    assert mock_sleep.call_count == 1


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_seed_complete_exhausted_retries_raise(mock_sleep, _wid):
    """This is the exact scenario run_seed_idea tags `seed_delivery_only` — the merge is
    already saved by the time this is called, so exhausting retries must raise (not swallow)
    so the caller can distinguish it from a genuine pipeline failure."""
    for _ in range(4):
        responses.add(responses.POST, _SEED_COMPLETE, body=requests.exceptions.ConnectionError("down"))
    from worker.progress import notify_seed_complete

    with pytest.raises(requests.exceptions.RequestException):
        notify_seed_complete("job-1", {"solution_name": "S"}, "accepted")
    assert len(responses.calls) == 4
    assert mock_sleep.call_count == 3


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
def test_seed_failed_posts_and_returns_true_on_success(_wid):
    responses.add(responses.POST, _SEED_FAILED, json={}, status=200)
    from worker.progress import notify_seed_failed

    delivered = notify_seed_failed("job-1", "boom")
    assert delivered is True
    assert len(responses.calls) == 1


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
def test_seed_failed_swallows_request_errors_but_reports_false(_wid):
    """Called from an exception handler (queue_consumer) — must never raise a NEW exception
    that would mask the original failure, but MUST report the delivery failure via its return
    value so the caller knows the revert did not land."""
    responses.add(responses.POST, _SEED_FAILED, body=requests.exceptions.ConnectionError("down"))
    from worker.progress import notify_seed_failed

    delivered = notify_seed_failed("job-1", "boom")  # must not raise
    assert delivered is False
    assert len(responses.calls) == 1
