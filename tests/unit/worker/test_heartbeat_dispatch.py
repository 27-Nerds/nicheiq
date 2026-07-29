import json
import re
from unittest.mock import patch

import responses


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-1"})
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_job_completed_carries_active_dispatch(_dispatch):
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/job-completed$"),
        json={"status": "ok"},
        status=200,
    )
    from worker.heartbeat import notify_job_completed

    assert notify_job_completed("job-1") is True
    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "worker-test",
        "job_id": "job-1",
        "dispatch_id": "dispatch-1",
    }


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-1"})
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_job_failed_carries_active_dispatch(_dispatch):
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/job-failed$"),
        json={"status": "ok"},
        status=200,
    )
    from worker.heartbeat import notify_job_failed

    assert notify_job_failed("job-1", "boom", 8) is True
    payload = json.loads(responses.calls[0].request.body)
    assert payload["worker_id"] == "worker-test"
    assert payload["job_id"] == "job-1"
    assert payload["dispatch_id"] == "dispatch-1"
