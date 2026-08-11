"""Retry behavior of notify_ideas_ready.

This delivery is the only transition out of RUNNING for interactive /
pain-research jobs: transient failures must retry; the backend answers
lost-response retries with 200 {idempotent:true}; a 409 with state CANCELLED
has nothing to deliver to (quiet return); any OTHER 409/404 means a completed
run's ideas would be silently discarded — it must RAISE (2026-07-02 infra-review
fix: previously every 409 was swallowed as 'delivered'). Exhausted transient
retries must raise so the task's failure path replaces a zombie RUNNING job.
"""

import json
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
_REGENERATION_COMPLETE = re.compile(r".+/api/workers/regeneration-complete$")
_REPORT_READY = re.compile(r".+/api/workers/report-ready$")
_JOB_FAILED = re.compile(r".+/api/workers/job-failed$")
_CATALOG_PAIN_POINTS_READY = re.compile(r".+/api/workers/catalog-pain-points-ready$")
_CATALOG_IDEAS_READY = re.compile(r".+/api/workers/catalog-ideas-ready$")


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
def test_report_ready_carries_dispatch_and_exact_winner(_wid, _dispatch):
    responses.add(responses.POST, _REPORT_READY, json={"status": "ok"}, status=200)
    from worker.progress import publish_report_ready

    winner_ref = {
        "idea_id": "idea-a",
        "idea_revision": 2,
        "solution_name": "Alpha Hub",
    }
    publish_report_ready(
        "job-1",
        "/tmp/report.json",
        winner_name="Alpha Hub",
        winner_ref=winner_ref,
    )

    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "w1",
        "job_id": "job-1",
        "report_path": "/tmp/report.json",
        "dispatch_id": "dispatch-2",
        "commercial_copy_contract_version": "paying-wallet-positive-copy-v1",
        "winner_name": "Alpha Hub",
        "winner_ref": winner_ref,
    }


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
def test_catalog_pain_points_ready_carries_dispatch(_wid, _dispatch):
    responses.add(responses.POST, _CATALOG_PAIN_POINTS_READY, json={}, status=200)
    from worker.progress import notify_catalog_pain_points_ready

    notify_catalog_pain_points_ready("job-1", "category-1", [], "niche", "/tmp/p.json")

    assert json.loads(responses.calls[0].request.body)["dispatch_id"] == "dispatch-2"


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
def test_catalog_ideas_ready_carries_dispatch(_wid, _dispatch):
    responses.add(responses.POST, _CATALOG_IDEAS_READY, json={}, status=200)
    from worker.progress import notify_catalog_ideas_ready

    notify_catalog_ideas_ready("job-1", "category-1", [], "niche")

    assert json.loads(responses.calls[0].request.body)["dispatch_id"] == "dispatch-2"


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
def test_quality_gate_stop_carries_exact_dispatch_and_structured_reason(_wid, _dispatch):
    responses.add(responses.POST, _JOB_FAILED, json={"success": True}, status=200)
    from worker.progress import notify_job_quality_gate_stop

    delivered = notify_job_quality_gate_stop(
        "job-1",
        "INSUFFICIENT_DATA",
        {"recommendation": "Broaden the source window", "quality_tier": "low"},
        9,
    )

    assert delivered is True
    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "w1",
        "job_id": "job-1",
        "dispatch_id": "dispatch-2",
        "error_message": "Broaden the source window",
        "error_stage": 9,
        "stop_reason": "INSUFFICIENT_DATA",
        "stop_reason_details": {
            "recommendation": "Broaden the source window",
            "quality_tier": "low",
        },
    }


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


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_regeneration_complete_delivers_batch_correlation_and_counts(
    mock_sleep, _wid, _dispatch
):
    responses.add(
        responses.POST,
        _REGENERATION_COMPLETE,
        json={"status": "ok", "idempotent": True},
        status=200,
    )
    from worker.progress import notify_regeneration_complete

    notify_regeneration_complete(
        "job-1",
        [],
        batch_ordinal=2,
        generated_count=3,
        ruled_out_count=3,
    )

    assert json.loads(responses.calls[0].request.body) == {
        "worker_id": "w1",
        "job_id": "job-1",
        "solutions": [],
        "dispatch_id": "dispatch-2",
        "commercial_copy_contract_version": "paying-wallet-positive-copy-v1",
        "batch_ordinal": 2,
        "generated_count": 3,
        "ruled_out_count": 3,
    }
    mock_sleep.assert_not_called()


@responses.activate
@patch("worker.progress._dispatch_payload", return_value={"dispatch_id": "dispatch-2"})
@patch("worker.progress._get_worker_id", return_value="w1")
@patch("worker.progress.time.sleep")
def test_regeneration_complete_exhausted_retries_raise(
    mock_sleep, _wid, _dispatch
):
    for _ in range(4):
        responses.add(
            responses.POST,
            _REGENERATION_COMPLETE,
            body=requests.exceptions.ConnectionError("backend down"),
        )
    from worker.progress import notify_regeneration_complete
    from worker.paid_pool_recovery import PaidPoolCompletionAmbiguous

    with pytest.raises(PaidPoolCompletionAmbiguous):
        notify_regeneration_complete("job-1", [])

    assert len(responses.calls) == 4
    assert mock_sleep.call_count == 3
