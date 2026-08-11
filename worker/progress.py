"""
Progress reporting module for communicating with the Node.js backend via API.

This module publishes progress updates to the backend API, which then:
1. Updates the database
2. Broadcasts to SSE clients
3. Returns cancellation status
"""

import os
import time
from collections.abc import Callable
from typing import Any, Optional

import requests
from loguru import logger

COMMERCIAL_COPY_CONTRACT_VERSION = "paying-wallet-positive-copy-v1"


def _get_backend_url() -> str:
    """Get backend URL from environment."""
    return os.environ.get("BACKEND_URL", "http://localhost:3001")


def _get_internal_secret() -> str:
    """Get internal service secret from environment."""
    return os.environ.get("INTERNAL_SERVICE_SECRET", "")


def _get_worker_id() -> str:
    """Get worker ID from heartbeat module."""
    from .heartbeat import get_worker_id
    return get_worker_id()


# ── Dispatch identity ────────────────────────────────────────────────────────────────────
# The backend hands us a dispatch id with the queue payload; it must ride back on EVERY
# callback for that job. The backend CASes on it, so a callback from a superseded attempt
# (a duplicate delivery, or a worker whose job was cancelled and restarted) matches nothing
# and mutates nothing — instead of rewinding a run that has already moved on.
#
# It lives in a module-level registry rather than as an argument because the progress
# callbacks are invoked from deep inside the research pipeline, which has no reason to know
# about billing or dispatch identity. Keyed by job_id so a multi-job worker process can't
# leak one job's id onto another's callback.
#
# Absent = this job was dispatched by a backend that predates dispatch ids. We send nothing
# and the backend falls back to its narrow legacy path. That is why the worker ships FIRST:
# it must tolerate absence before the backend starts requiring presence.
_ACTIVE_DISPATCH: dict[str, str] = {}


def set_active_dispatch(job_id: str, dispatch_id: Optional[str]) -> None:
    """Record the dispatch this worker is authorized to report against for `job_id`."""
    if dispatch_id:
        _ACTIVE_DISPATCH[job_id] = dispatch_id
    else:
        _ACTIVE_DISPATCH.pop(job_id, None)


def clear_active_dispatch(job_id: str) -> None:
    """Drop the dispatch id once the job is released (success or failure)."""
    _ACTIVE_DISPATCH.pop(job_id, None)


def _dispatch_payload(job_id: str) -> dict[str, str]:
    """Spread into a callback body: {"dispatch_id": ...} when known, {} when not."""
    dispatch_id = _ACTIVE_DISPATCH.get(job_id)
    return {"dispatch_id": dispatch_id} if dispatch_id else {}


# Stage name mapping (matches backend/src/types/job.ts)
STAGE_NAMES = {
    1: "Niche Validation",
    2: "Search & Discovery",
    3: "Pain Point Analysis",
    4: "Audience Mapping",
    5: "Solution Pipeline",
    5.5: "Competitive Analysis",
    6: "SEO & Keyword Strategy",
    7: "Pricing Validation",
    8: "Traffic Monetization",
    9: "Market Sizing",
    10: "Solution Refinement",
    11: "Trend Analysis",
    12: "SEO Score Refinement",
    13: "Data Source Research",
    14: "Report Generation",
    15: "Landing Page Generation",
}


def publish_progress_via_api(
    job_id: str,
    stage: float,
    name: str,
    status: str,
    error: Optional[str] = None,
    report_path: Optional[str] = None,
    landing_path: Optional[str] = None,
    artifact: Optional[dict] = None,
) -> bool:
    """
    Publish progress update to backend API.

    This is the single path for all progress updates:
    - Stage transitions (running, completed, failed)
    - Job completion (with report_path)
    - Job failure (with error)

    Args:
        job_id: The job UUID
        stage: Stage number (e.g., 1, 2, 3, 4, 5)
        name: Human-readable stage name
        status: 'running', 'completed', or 'failed'
        error: Optional error message (for failed status)
        report_path: Optional path to report (for job completion)
        landing_path: Optional path to landing page (for job completion)
        artifact: Optional lightweight artifact dict for stage results

    Returns:
        True if job should be cancelled, False otherwise
    """
    try:
        payload: dict[str, Any] = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "stage": stage,
            "name": name,
            "status": status,
            **_dispatch_payload(job_id),
        }

        if error is not None:
            payload["error"] = error
        if report_path is not None:
            payload["report_path"] = report_path
            payload["commercial_copy_contract_version"] = COMMERCIAL_COPY_CONTRACT_VERSION
        if landing_path is not None:
            payload["landing_path"] = landing_path
        if artifact is not None:
            payload["artifact"] = artifact

        response = requests.post(
            f"{_get_backend_url()}/api/workers/progress",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=10,
        )
        response.raise_for_status()

        result = response.json()
        should_cancel = result.get("shouldCancel", False)

        logger.debug(
            f"[Progress] {status} stage {stage} ({name}) - shouldCancel={should_cancel}"
        )

        return should_cancel

    except requests.exceptions.Timeout:
        logger.warning(f"[Progress] Progress update timed out for job {job_id}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to publish progress: {e}")
        return False


def create_progress_callback(
    job_id: str,
    check_cancellation: bool = True
) -> Callable[[float, Optional[str], str, Optional[dict]], None]:
    """
    Create a progress callback function for ResearchFlow.

    This callback publishes stage updates to the backend API, which updates
    the database and broadcasts to connected SSE clients.

    If check_cancellation is True, also checks for cancellation at each
    stage transition (running -> completed) and raises JobCancelledException
    if the job was cancelled by the user.

    Args:
        job_id: The job UUID
        check_cancellation: If True, check for cancellation at stage transitions

    Returns:
        Callback function that takes (stage_num, stage_name, status, artifact)
    """
    def callback(stage_num: float, stage_name: Optional[str], status: str, artifact: Optional[dict] = None) -> None:
        """
        Progress callback for ResearchFlow stages.

        Args:
            stage_num: Stage number (e.g., 1, 2, 3, 4, 5)
            stage_name: Human-readable stage name (optional - looked up from STAGE_NAMES if None)
            status: 'running', 'completed', or 'failed'
            artifact: Optional lightweight artifact dict for stage results
        """
        # Look up stage name if not provided
        name = stage_name if stage_name else STAGE_NAMES.get(stage_num, f"Stage {stage_num}")

        # Publish to backend API (handles DB update and SSE broadcast)
        should_cancel = publish_progress_via_api(
            job_id=job_id,
            stage=stage_num,
            name=name,
            status=status,
            artifact=artifact,
        )

        # Check for cancellation when a stage starts running (best point to stop)
        if check_cancellation and status == "running":
            from .heartbeat import JobCancelledException, is_cancellation_requested
            if should_cancel or is_cancellation_requested():
                raise JobCancelledException("Job cancelled")

    return callback


def publish_report_ready(
    job_id: str,
    report_path: str,
    winner_name: str = None,
    winner_ref: Optional[dict] = None,
    cost_summary: Optional[dict] = None,
) -> None:
    """
    Notify backend that the research report is ready (before landing page).
    This triggers "report ready" notification so users can view reports immediately.

    Args:
        job_id: The job UUID
        report_path: Path to the generated report JSON
        winner_name: Optional name of the winning solution
        cost_summary: Optional LLM cost breakdown (CostTracker.get_summary()) to persist
            on the Job row for the admin pricing view
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "report_path": report_path,
            "commercial_copy_contract_version": COMMERCIAL_COPY_CONTRACT_VERSION,
            **_dispatch_payload(job_id),
        }
        if winner_name:
            payload["winner_name"] = winner_name
        if winner_ref:
            payload["winner_ref"] = winner_ref
        if cost_summary:
            payload["cost_summary"] = cost_summary

        response = requests.post(
            f"{_get_backend_url()}/api/workers/report-ready",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Report ready notification sent for job {job_id}")

    except requests.exceptions.RequestException as e:
        # Re-raise so queue_consumer reports a terminal attempt failure instead
        # of publishing false completion. /report-ready is idempotent, so a
        # later explicit retry can safely deliver the same asset.
        logger.error(f"[Progress] Failed to publish report-ready: {e}")
        raise


def publish_job_completed(
    job_id: str,
    report_path: str,
    landing_path: Optional[str] = None
) -> None:
    """
    Publish job completion to backend API.

    Args:
        job_id: The job UUID
        report_path: Path to the generated report JSON
        landing_path: Optional path to the landing page HTML
    """
    # Use a final stage to indicate completion
    publish_progress_via_api(
        job_id=job_id,
        stage=15 if landing_path else 14,  # Use last completed stage
        name="Completed",
        status="completed",
        report_path=report_path,
        landing_path=landing_path,
    )
    logger.info(f"[Progress] Job {job_id} completed - report: {report_path}")


def publish_job_failed(job_id: str, error: str, stage: Optional[float] = None) -> None:
    """
    Publish job failure to backend API.

    Args:
        job_id: The job UUID
        error: Error message
        stage: Optional stage where failure occurred
    """
    # Use stage 1 as fallback (stage 0 doesn't exist in DB and will cause validation error)
    stage_num = stage if stage is not None and stage > 0 else 1
    stage_name = STAGE_NAMES.get(stage_num, f"Stage {stage_num}")

    publish_progress_via_api(
        job_id=job_id,
        stage=stage_num,
        name=stage_name,
        status="failed",
        error=error,
    )
    logger.error(f"[Progress] Job {job_id} failed at stage {stage}: {error}")




def notify_ideas_ready(job_id: str, solutions: list[dict], checkpoint_path: str, total_to_validate: int = 0, skip_validation: bool = False, discovery_data_path: str = "", preview_report_path: str | None = None, cost_summary: Optional[dict] = None) -> None:
    """
    Notify backend that Phase 1 solution ideas are ready.

    Args:
        job_id: The job UUID
        solutions: List of solution preview dicts
        checkpoint_path: Path to phase 1 checkpoint
        total_to_validate: Number of solutions to validate
        skip_validation: If True, skip validation step
        discovery_data_path: Path to materialized discovery data JSON
        preview_report_path: Path to materialized preview report JSON

    Raises:
        requests.exceptions.RequestException: after all retries are exhausted.
        This delivery is the job's ONLY transition out of RUNNING, so a swallowed
        failure would leave it stuck RUNNING forever; raising lets the task's
        standard failure path take over (FAILED + refund) instead.
    """
    payload = {
        "worker_id": _get_worker_id(),
        "job_id": job_id,
        "solutions": solutions,
        "checkpoint_path": checkpoint_path,
        "total_to_validate": total_to_validate,
        "skip_validation": skip_validation,
        "discovery_data_path": discovery_data_path,
        # G2's Continue does NOT end at /gate-reached — it runs to stage 5 and terminates HERE.
        # Without the dispatch id this callback is the unguarded back door into the whole
        # guided flow.
        **_dispatch_payload(job_id),
    }
    if preview_report_path:
        payload["preview_report_path"] = preview_report_path
        payload["commercial_copy_contract_version"] = COMMERCIAL_COPY_CONTRACT_VERSION
    if cost_summary:
        payload["cost_summary"] = cost_summary

    retry_delays = (2.0, 5.0, 10.0)
    last_error: Exception = RuntimeError("unreachable")
    for attempt, delay in enumerate((*retry_delays, None), start=1):
        try:
            response = requests.post(
                f"{_get_backend_url()}/api/workers/ideas-ready",
                json=payload,
                headers={"x-internal-service": _get_internal_secret()},
                timeout=30,
            )
            # 409/404 = deterministic state conflict — retrying can't help, but the cases
            # differ: the backend answers lost-response retries with 200 {idempotent:true},
            # so a 409 means the job genuinely left RUNNING for another reason. CANCELLED
            # has nothing to deliver to (return quietly); anything else (FAILED etc.) means
            # a completed run's ideas would be silently discarded — raise so the loss is
            # visible in the worker's failure path instead of masquerading as delivery.
            if response.status_code in (404, 409):
                try:
                    state = (response.json() or {}).get("state", "")
                except ValueError:
                    state = ""
                if response.status_code == 409 and state == "CANCELLED":
                    logger.warning(
                        f"[Progress] Ideas-ready for job {job_id}: job was cancelled — "
                        "nothing to deliver, not retrying"
                    )
                    return
                msg = (
                    f"Ideas-ready rejected for job {job_id}: HTTP {response.status_code}"
                    + (f", job state {state}" if state else "")
                    + " — completed ideas could not be delivered"
                )
                logger.error(f"[Progress] {msg}")
                raise RuntimeError(msg)
            response.raise_for_status()
            logger.info(f"[Progress] Ideas ready notification sent for job {job_id} ({len(solutions)} solutions)")
            return
        except requests.exceptions.RequestException as e:
            last_error = e
            if delay is None:
                break
            logger.warning(
                f"[Progress] Ideas-ready attempt {attempt} failed for job {job_id}, "
                f"retrying in {delay}s: {e}"
            )
            time.sleep(delay)

    logger.error(f"[Progress] Failed to notify ideas ready for job {job_id} after {attempt} attempts")
    raise last_error



def notify_regeneration_complete(
    job_id: str,
    new_solutions: list[dict],
    cost_summary: Optional[dict] = None,
    batch_ordinal: Optional[int] = None,
    generated_count: Optional[int] = None,
    ruled_out_count: Optional[int] = None,
) -> None:
    """
    Notify backend that regeneration is complete with new solutions.

    Args:
        job_id: The job UUID
        new_solutions: List of new solution preview dicts
        cost_summary: Optional LLM cost breakdown (CostTracker.get_summary()) for this
            regeneration batch, accumulated onto the job's existing costUsd by the backend
    """
    payload = {
        "worker_id": _get_worker_id(),
        "job_id": job_id,
        "solutions": new_solutions,
        "commercial_copy_contract_version": COMMERCIAL_COPY_CONTRACT_VERSION,
        **_dispatch_payload(job_id),
    }
    if cost_summary:
        payload["cost_summary"] = cost_summary
    if batch_ordinal is not None:
        payload["batch_ordinal"] = batch_ordinal
    if generated_count is not None:
        payload["generated_count"] = generated_count
    if ruled_out_count is not None:
        payload["ruled_out_count"] = ruled_out_count

    delays = (2.0, 5.0, 10.0)
    last_error: Exception = RuntimeError("unreachable")
    for attempt, delay in enumerate((*delays, None), start=1):
        try:
            response = requests.post(
                f"{_get_backend_url()}/api/workers/regeneration-complete",
                json=payload,
                headers={"x-internal-service": _get_internal_secret()},
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("stale"):
                from .paid_pool_recovery import PaidPoolOperationFenced

                raise PaidPoolOperationFenced(
                    f"Regeneration dispatch for {job_id} was fenced before completion"
                )
            logger.info(f"[Progress] Regeneration complete notification sent for job {job_id}")
            return
        except requests.exceptions.RequestException as e:
            last_error = e
            if delay is None:
                break
            logger.warning(
                f"[Progress] Regeneration-complete attempt {attempt} failed for job "
                f"{job_id}, retrying in {delay}s: {e}"
            )
            time.sleep(delay)
    logger.error(
        f"[Progress] Failed to notify regeneration complete for job {job_id} "
        f"after {attempt} attempts"
    )
    from .paid_pool_recovery import PaidPoolCompletionAmbiguous

    raise PaidPoolCompletionAmbiguous(str(last_error)) from last_error



def notify_regeneration_failed(job_id: str, error_message: str) -> bool:
    """
    Notify backend that regeneration failed. Reverts job to AWAITING_SELECTION
    so the user can see existing solutions and retry.

    Args:
        job_id: The job UUID
        error_message: Description of what went wrong
    """
    payload = {
        "worker_id": _get_worker_id(),
        "job_id": job_id,
        "error_message": error_message[:2000],
        **_dispatch_payload(job_id),
    }
    delays = (2.0, 5.0, 10.0)
    for attempt, delay in enumerate((*delays, None), start=1):
        try:
            response = requests.post(
                f"{_get_backend_url()}/api/workers/regeneration-failed",
                json=payload,
                headers={"x-internal-service": _get_internal_secret()},
                timeout=30,
            )
            response.raise_for_status()
            if response.json().get("stale"):
                logger.warning(
                    f"[Progress] Regeneration failure for {job_id} belongs to a fenced writer"
                )
                return False
            logger.info(f"[Progress] Regeneration failed notification sent for job {job_id}")
            return True
        except requests.exceptions.RequestException as e:
            if delay is None:
                logger.error(
                    f"[Progress] Failed to notify regeneration failed for job {job_id} "
                    f"after {attempt} attempts: {e}"
                )
                return False
            logger.warning(
                f"[Progress] Regeneration-failed attempt {attempt} failed for job "
                f"{job_id}, retrying in {delay}s: {e}"
            )
            time.sleep(delay)
    return False


def notify_seed_complete(
    job_id: str,
    idea: dict,
    outcome: str,
    cost_summary: Optional[dict] = None,
) -> None:
    """
    Notify backend that a user-composed idea seed (eager-meandering-feather.md Phase 5)
    finished birth + scoring and was already MERGED and SAVED into the pool checkpoint by the
    caller. `outcome` is 'accepted' (cleared the market-fit bar) or 'demoted' (didn't) — both
    are delivered; a demoted seed still surfaces to the user (Examined & ruled out), never
    silently discarded (a paid request must not vanish).

    Mirrors `notify_gate_reached` and `notify_regeneration_complete`'s retry-then-RAISE
    contract: this delivery is the seed's ONLY transition out of QUEUED/RUNNING, and by
    the time this is called the merge is already durable on disk — the money is owed
    regardless of whether this call lands. Raising on exhausted retries lets the caller
    (`run_seed_idea`) tell a genuine pipeline failure apart from "the work is done and
    saved but nobody was told" — the backend must never refund or discard on the latter,
    only retry delivery against the dispatch id.

    Args:
        job_id: The job UUID
        idea: The seed's preview dict (`_solution_to_preview_dict`) — exactly one idea, active
            or demoted.
        outcome: 'accepted' | 'demoted'
        cost_summary: Optional live cost-tracker summary for the admin pricing view.
    """
    payload: dict[str, Any] = {
        "worker_id": _get_worker_id(),
        "job_id": job_id,
        "idea": idea,
        "outcome": outcome,
        "commercial_copy_contract_version": COMMERCIAL_COPY_CONTRACT_VERSION,
        **_dispatch_payload(job_id),
    }
    if cost_summary:
        payload["cost_summary"] = cost_summary

    retry_delays = (2.0, 5.0, 10.0)
    last_error: Exception = RuntimeError("unreachable")
    for attempt, delay in enumerate((*retry_delays, None), start=1):
        try:
            response = requests.post(
                f"{_get_backend_url()}/api/workers/seed-complete",
                json=payload,
                headers={"x-internal-service": _get_internal_secret()},
                timeout=30,
            )
            if response.status_code in (404, 409):
                try:
                    state = (response.json() or {}).get("state", "")
                except ValueError:
                    state = ""
                if response.status_code == 409 and state == "CANCELLED":
                    from .paid_pool_recovery import PaidPoolOperationFenced

                    logger.warning(
                        f"[Progress] Seed-complete for job {job_id}: job was cancelled — "
                        "restoring the fenced operation before returning"
                    )
                    raise PaidPoolOperationFenced(
                        f"Seed dispatch for {job_id} was cancelled before completion"
                    )
                msg = (
                    f"Seed-complete rejected for job {job_id}: HTTP {response.status_code}"
                    + (f", job state {state}" if state else "")
                    + " — seed outcome could not be delivered"
                )
                logger.error(f"[Progress] {msg}")
                raise RuntimeError(msg)
            response.raise_for_status()
            if response.json().get("stale"):
                from .paid_pool_recovery import PaidPoolOperationFenced

                raise PaidPoolOperationFenced(
                    f"Seed dispatch for {job_id} was fenced before completion"
                )
            logger.info(f"[Progress] Seed-complete notification sent for job {job_id} (outcome={outcome})")
            return
        except requests.exceptions.RequestException as e:
            last_error = e
            if delay is None:
                break
            logger.warning(
                f"[Progress] Seed-complete attempt {attempt} failed for job {job_id}, "
                f"retrying in {delay}s: {e}"
            )
            time.sleep(delay)

    logger.error(f"[Progress] Failed to notify seed complete for job {job_id} after {attempt} attempts")
    from .paid_pool_recovery import PaidPoolCompletionAmbiguous

    raise PaidPoolCompletionAmbiguous(str(last_error)) from last_error


def notify_seed_failed(job_id: str, error_message: str) -> bool:
    """
    Notify backend that a user-composed idea seed FAILED BEFORE anything was merged or saved
    (birth itself produced nothing — `execute_seed_pipeline` returned None, or the pipeline
    raised). Reverts QUEUED/RUNNING -> AWAITING_SELECTION and refunds the numbered
    `seed_idea_N` charge, mirroring `notify_gate_failed`'s bool-return contract.

    Returns:
        True if the revert was delivered, False otherwise. Callers MUST check this and never
        fall through to the generic job-failure path on a seed op — that path would refund the
        wrong charge ('discovery'/segment) for a job that never charged either of those a
        second time.
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "error_message": error_message[:2000],
            **_dispatch_payload(job_id),
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/seed-failed",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        if response.json().get("stale"):
            logger.warning(f"[Progress] Seed failure for {job_id} belongs to a fenced writer")
            return False
        logger.info(f"[Progress] Seed-failed notification sent for job {job_id}")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify seed failed: {e}")
        return False


def notify_catalog_pain_points_ready(
    job_id: str,
    category_id: str,
    pain_points: list[dict],
    niche: str,
    preview_report_path: Optional[str] = None,
) -> None:
    """
    Notify backend that catalog pain points are ready for merge/insert.

    Re-raises POST failures so queue_consumer reports the catalog run as FAILED
    instead of publishing false completion. The admin may trigger a fresh run;
    the backend handler remains idempotent for ambiguous callback delivery.

    Args:
        job_id: The job UUID
        category_id: The catalog category UUID
        pain_points: List of pain point dicts (from PainPoint.model_dump())
        niche: The niche description used for generation
        preview_report_path: Path to the materialized preview report file.
            Required for catalog flow — backend rejects requests without it.
    """
    try:
        payload: dict = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "category_id": category_id,
            "pain_points": pain_points,
            "niche": niche,
            **_dispatch_payload(job_id),
        }
        if preview_report_path:
            payload["preview_report_path"] = preview_report_path
            payload["commercial_copy_contract_version"] = COMMERCIAL_COPY_CONTRACT_VERSION

        response = requests.post(
            f"{_get_backend_url()}/api/workers/catalog-pain-points-ready",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Catalog pain points ready for job {job_id} ({len(pain_points)} pain points)")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify catalog pain points ready: {e}")
        raise


def notify_catalog_ideas_ready(
    job_id: str,
    category_id: str,
    ideas: list[dict],
    niche: str,
    parent_source_job_id: Optional[str] = None,
) -> None:
    """
    Notify backend that catalog ideas are ready for insert.

    Re-raises POST failures so queue_consumer reports the catalog run as FAILED.
    A fresh admin-triggered run is the supported retry path.

    Args:
        job_id: The job UUID
        category_id: The catalog category UUID
        ideas: List of idea dicts (from BaseSolutionIdea via _solution_to_preview_dict)
        niche: The niche description used for generation
        parent_source_job_id: Optional sourceJobId of the pain-points-job
            these ideas were generated from. When set, backend uses it as
            effectiveSourceJobId so ideas FK into the same context row.
    """
    try:
        payload: dict = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "category_id": category_id,
            "ideas": ideas,
            "niche": niche,
            **_dispatch_payload(job_id),
        }
        if parent_source_job_id:
            payload["parent_source_job_id"] = parent_source_job_id

        response = requests.post(
            f"{_get_backend_url()}/api/workers/catalog-ideas-ready",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Catalog ideas ready for job {job_id} ({len(ideas)} ideas)")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify catalog ideas ready: {e}")
        raise


def notify_gate_reached(
    job_id: str,
    gate_stage: int,
    checkpoint_path: str,
    gate_artifact: dict,
    cost_summary: Optional[dict] = None,
) -> None:
    """
    Notify backend that a guided-mode (chatMode) gate was reached (G1 after Stage 1, G2
    after Stage 4) — or re-reached after an `apply_stay` gate-action round-trip, with a
    refreshed artifact for the SAME gate.

    Mirrors `notify_ideas_ready`'s retry + idempotency contract: this delivery is the job's
    ONLY transition out of RUNNING/QUEUED for a gate stop, so a swallowed failure would leave
    it stuck forever — raise on exhausted retries so the worker's standard failure path
    (notify_job_failed) takes over instead of a silent stall. A 409 with state=CANCELLED
    returns quietly (nothing to deliver to); any other 404/409 raises since a reached gate
    silently discarded is a real loss the operator needs to see.

    Args:
        job_id: The job UUID
        gate_stage: 1 (G1, post-Stage-1) or 4 (G2, post-Stage-4)
        checkpoint_path: The EFFECTIVE post-resume checkpoint path
            (flow.checkpoint_mgr.checkpoint_folder) — NEVER the path the resume was given,
            since a cross-job resume forks to a new folder (Codex 10).
        gate_artifact: The gate card payload (_extract_stage_artifact(1) for G1,
            _build_g2_gate_artifact() for G2) — also the patch cross-check reference.
        cost_summary: Optional live cost-tracker summary for the admin pricing view.
    """
    payload: dict[str, Any] = {
        "worker_id": _get_worker_id(),
        "job_id": job_id,
        "gate_stage": gate_stage,
        "checkpoint_path": checkpoint_path,
        "gate_artifact": gate_artifact,
        **_dispatch_payload(job_id),
    }
    if cost_summary:
        payload["cost_summary"] = cost_summary

    retry_delays = (2.0, 5.0, 10.0)
    last_error: Exception = RuntimeError("unreachable")
    for attempt, delay in enumerate((*retry_delays, None), start=1):
        try:
            response = requests.post(
                f"{_get_backend_url()}/api/workers/gate-reached",
                json=payload,
                headers={"x-internal-service": _get_internal_secret()},
                timeout=30,
            )
            if response.status_code in (404, 409):
                try:
                    state = (response.json() or {}).get("state", "")
                except ValueError:
                    state = ""
                if response.status_code == 409 and state == "CANCELLED":
                    logger.warning(
                        f"[Progress] Gate-reached for job {job_id}: job was cancelled — "
                        "nothing to deliver, not retrying"
                    )
                    return
                msg = (
                    f"Gate-reached rejected for job {job_id}: HTTP {response.status_code}"
                    + (f", job state {state}" if state else "")
                    + " — reached gate could not be delivered"
                )
                logger.error(f"[Progress] {msg}")
                raise RuntimeError(msg)
            response.raise_for_status()
            logger.info(f"[Progress] Gate-reached notification sent for job {job_id} (gate_stage={gate_stage})")
            return
        except requests.exceptions.RequestException as e:
            last_error = e
            if delay is None:
                break
            logger.warning(
                f"[Progress] Gate-reached attempt {attempt} failed for job {job_id}, "
                f"retrying in {delay}s: {e}"
            )
            time.sleep(delay)

    logger.error(f"[Progress] Failed to notify gate reached for job {job_id} after {attempt} attempts")
    raise last_error


def notify_gate_failed(job_id: str, gate_stage: int, error_message: str) -> bool:
    """
    Notify backend that a gate CONTINUATION (`continue_from_gate`) failed — either resuming
    the checkpoint or re-running stages toward the next stop. Reverts the job QUEUED ->
    AWAITING_GATE (mirrors `notify_regeneration_failed`'s QUEUED -> AWAITING_SELECTION revert)
    so the user's existing gate artifact/patch history is preserved and the run is retryable,
    instead of being marked FAILED (which would trigger an incorrect credit refund).

    Args:
        job_id: The job UUID
        gate_stage: The gate stage the job was trying to continue from (1 or 4)
        error_message: Description of what went wrong

    Returns:
        True if the revert was delivered, False otherwise. Callers MUST check this (Codex
        review findings 4/6) — a swallowed delivery failure here would leave the job stuck in
        QUEUED forever with nobody told; on False the caller must fall through to the generic
        notify_job_failed path instead of treating the job as recovered.
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "gate_stage": gate_stage,
            "error_message": error_message[:2000],
            **_dispatch_payload(job_id),
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/gate-failed",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Gate-failed notification sent for job {job_id} (gate_stage={gate_stage})")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify gate failed: {e}")
        return False


def notify_job_quality_gate_stop(
    job_id: str,
    reason: str,
    details: dict,
    stage: int
) -> bool:
    """
    Notify backend that a quality gate intentionally stopped the job.

    This is different from a failure - it's an intentional stop due to
    insufficient data quality. The backend stores this in stopReason/stopReasonDetails
    fields to enable different UI treatment.

    Args:
        job_id: The job UUID
        reason: Stop reason code (e.g., 'INSUFFICIENT_DATA')
        details: Quality metrics and recommendation
        stage: Stage number where the stop occurred

    Returns:
        True if notification was successful
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "error_message": details.get("recommendation", "Quality check failed"),
            "error_stage": stage,
            "stop_reason": reason,
            "stop_reason_details": details,
            **_dispatch_payload(job_id),
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/job-failed",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=10,
        )
        response.raise_for_status()

        logger.info(
            f"[Progress] Job {job_id} stopped by quality gate at stage {stage}: {reason}"
        )
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify quality gate stop: {e}")
        return False
