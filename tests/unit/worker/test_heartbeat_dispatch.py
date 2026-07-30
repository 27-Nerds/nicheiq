import json
import re
from unittest.mock import patch

import requests
import responses


@responses.activate
@patch("worker.heartbeat._current_job_id", "job-1")
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_periodic_heartbeat_carries_active_dispatch():
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/heartbeat$"),
        json={"status": "ok", "shouldCancel": False},
        status=200,
    )
    from worker.heartbeat import _send_heartbeat
    from worker.progress import clear_active_dispatch, set_active_dispatch

    set_active_dispatch("job-1", "dispatch-1")
    try:
        assert _send_heartbeat() is True
    finally:
        clear_active_dispatch("job-1")

    payload = json.loads(responses.calls[0].request.body)
    assert payload["job_id"] == "job-1"
    assert payload["dispatch_id"] == "dispatch-1"


@responses.activate
@patch("worker.heartbeat._current_job_id", "job-legacy")
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_periodic_heartbeat_omits_dispatch_only_for_legacy_delivery():
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/heartbeat$"),
        json={"status": "ok", "shouldCancel": False},
        status=200,
    )
    from worker.heartbeat import _send_heartbeat
    from worker.progress import clear_active_dispatch

    clear_active_dispatch("job-legacy")
    assert _send_heartbeat() is True

    payload = json.loads(responses.calls[0].request.body)
    assert payload["job_id"] == "job-legacy"
    assert "dispatch_id" not in payload


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


@responses.activate
@patch("worker.heartbeat._current_job_id", "job-1")
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_shutdown_carries_active_dispatch():
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/shutdown$"),
        json={"status": "ok"},
        status=200,
    )
    from worker.heartbeat import notify_shutdown
    from worker.progress import clear_active_dispatch, set_active_dispatch

    set_active_dispatch("job-1", "dispatch-1")
    try:
        assert notify_shutdown("SIGTERM") is True
    finally:
        clear_active_dispatch("job-1")

    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "worker-test",
        "job_id": "job-1",
        "reason": "SIGTERM",
        "dispatch_id": "dispatch-1",
    }


@responses.activate
@patch("worker.heartbeat._current_job_id", "job-legacy")
@patch("worker.heartbeat.WORKER_ID", "worker-test")
def test_shutdown_omits_dispatch_for_legacy_job_without_one():
    responses.add(
        responses.POST,
        re.compile(r".+/api/workers/shutdown$"),
        json={"status": "ok"},
        status=200,
    )
    from worker.heartbeat import notify_shutdown
    from worker.progress import clear_active_dispatch

    clear_active_dispatch("job-legacy")
    assert notify_shutdown("SIGINT") is True
    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "worker-test",
        "job_id": "job-legacy",
        "reason": "SIGINT",
    }


@patch(
    "worker.heartbeat.requests.post",
    side_effect=requests.exceptions.ConnectionError("backend offline"),
)
def test_modern_job_does_not_run_when_dispatch_claim_is_network_ambiguous(_post):
    from worker.heartbeat import notify_job_started
    from worker.progress import clear_active_dispatch, set_active_dispatch

    set_active_dispatch("job-1", "dispatch-1")
    try:
        assert notify_job_started("job-1") is False
    finally:
        clear_active_dispatch("job-1")


@patch(
    "worker.heartbeat.requests.post",
    side_effect=requests.exceptions.ConnectionError("backend offline"),
)
def test_legacy_job_retains_start_compatibility_when_backend_is_unreachable(_post):
    from worker.heartbeat import notify_job_started
    from worker.progress import clear_active_dispatch

    clear_active_dispatch("job-legacy")
    assert notify_job_started("job-legacy") is True
