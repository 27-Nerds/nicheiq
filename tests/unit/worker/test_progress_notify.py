"""Retry behavior of notify_ideas_ready.

This delivery is the only transition out of RUNNING for interactive /
pain-research jobs: transient failures must retry; the backend answers
lost-response retries with 200 {idempotent:true}; a 409 with state CANCELLED
has nothing to deliver to (quiet return); any OTHER 409/404 means a completed
run's ideas would be silently discarded — it must RAISE (2026-07-02 infra-review
fix: previously every 409 was swallowed as 'delivered'). Exhausted transient
retries must raise so the task's failure path replaces a zombie RUNNING job.
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

# Matched by URL suffix so the test doesn't depend on the resolved backend host.
_IDEAS_READY = re.compile(r".+/api/workers/ideas-ready$")


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_success_first_attempt_posts_once(mock_sleep, _wid):
    responses.add(responses.POST, _IDEAS_READY, json={}, status=200)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [{"solution_name": "S"}], "/cp", 1, skip_validation=True)
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_idempotent_200_treated_as_delivered(mock_sleep, _wid):
    responses.add(responses.POST, _IDEAS_READY, json={"status": "ok", "idempotent": True}, status=200)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [], "/cp", 0)  # must not raise
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_409_cancelled_returns_quietly(mock_sleep, _wid):
    responses.add(responses.POST, _IDEAS_READY,
                  json={"error": "Job cancelled", "state": "CANCELLED"}, status=409)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [], "/cp", 0)  # nothing to deliver to — must not raise
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_409_failed_state_raises_without_retry(mock_sleep, _wid):
    # the exact silent-loss scenario: job marked FAILED (e.g. heartbeat timeout) while the
    # worker finished anyway — swallowing this 409 discards a completed run's ideas
    responses.add(responses.POST, _IDEAS_READY,
                  json={"error": "Job not in RUNNING state (current: FAILED)", "state": "FAILED"},
                  status=409)
    from worker.progress import notify_ideas_ready

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_ideas_ready("job-1", [], "/cp", 0)
    assert len(responses.calls) == 1   # deterministic conflict — no retry
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_404_raises_without_retry(mock_sleep, _wid):
    responses.add(responses.POST, _IDEAS_READY, json={"error": "Job not found"}, status=404)
    from worker.progress import notify_ideas_ready

    with pytest.raises(RuntimeError, match="could not be delivered"):
        notify_ideas_ready("job-1", [], "/cp", 0)
    assert len(responses.calls) == 1
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_transient_failure_retries_then_succeeds(mock_sleep, _wid):
    responses.add(responses.POST, _IDEAS_READY, body=requests.exceptions.ConnectionError("backend down"))
    responses.add(responses.POST, _IDEAS_READY, json={}, status=200)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [], "/cp", 0)
    assert len(responses.calls) == 2
    assert mock_sleep.call_count == 1


@responses.activate
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_exhausted_retries_raise(mock_sleep, _wid):
    for _ in range(4):
        responses.add(responses.POST, _IDEAS_READY, body=requests.exceptions.ConnectionError("backend down"))
    from worker.progress import notify_ideas_ready

    with pytest.raises(requests.exceptions.RequestException):
        notify_ideas_ready("job-1", [], "/cp", 0)
    # 1 initial + 3 retries; sleeps between attempts only
    assert len(responses.calls) == 4
    assert mock_sleep.call_count == 3
