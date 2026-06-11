"""Retry behavior of notify_ideas_ready.

This delivery is the only transition out of RUNNING for interactive /
pain-research jobs: transient failures must retry, a 409 means the transition
already happened (or the job was cancelled), and exhausted retries must raise
so the task's failure path (FAILED + refund) replaces a zombie RUNNING job.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
@patch("worker.progress.requests.post")
def test_success_first_attempt_posts_once(mock_post, mock_sleep, _wid):
    mock_post.return_value = _response(200)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [{"solution_name": "S"}], "/cp", 1, skip_validation=True)
    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()


@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
@patch("worker.progress.requests.post")
def test_409_treated_as_delivered_no_retry_no_raise(mock_post, mock_sleep, _wid):
    mock_post.return_value = _response(409)
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [], "/cp", 0)  # must not raise
    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()


@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
@patch("worker.progress.requests.post")
def test_transient_failure_retries_then_succeeds(mock_post, mock_sleep, _wid):
    mock_post.side_effect = [
        requests.exceptions.ConnectionError("backend down"),
        _response(200),
    ]
    from worker.progress import notify_ideas_ready

    notify_ideas_ready("job-1", [], "/cp", 0)
    assert mock_post.call_count == 2
    assert mock_sleep.call_count == 1


@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
@patch("worker.progress.requests.post")
def test_exhausted_retries_raise(mock_post, mock_sleep, _wid):
    mock_post.side_effect = requests.exceptions.ConnectionError("backend down")
    from worker.progress import notify_ideas_ready

    with pytest.raises(requests.exceptions.RequestException):
        notify_ideas_ready("job-1", [], "/cp", 0)
    # 1 initial + 3 retries; sleeps between attempts only
    assert mock_post.call_count == 4
    assert mock_sleep.call_count == 3
