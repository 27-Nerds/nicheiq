"""
Progress reporting module for communicating with the Node.js backend via API.

This module publishes progress updates to the backend API, which then:
1. Updates the database
2. Broadcasts to SSE clients
3. Returns cancellation status
"""

import os
from typing import Any, Callable, Optional

import requests
from loguru import logger


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
        }

        if error is not None:
            payload["error"] = error
        if report_path is not None:
            payload["report_path"] = report_path
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


def publish_report_ready(job_id: str, report_path: str, winner_name: str = None) -> None:
    """
    Notify backend that the research report is ready (before landing page).
    This triggers "report ready" notification so users can view reports immediately.

    Args:
        job_id: The job UUID
        report_path: Path to the generated report JSON
        winner_name: Optional name of the winning solution
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "report_path": report_path,
        }
        if winner_name:
            payload["winner_name"] = winner_name

        response = requests.post(
            f"{_get_backend_url()}/api/workers/report-ready",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Report ready notification sent for job {job_id}")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to publish report-ready: {e}")


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




def notify_ideas_ready(job_id: str, solutions: list[dict], checkpoint_path: str, total_to_validate: int = 0, skip_validation: bool = False) -> None:
    """
    Notify backend that Phase 1 solution ideas are ready.

    Args:
        job_id: The job UUID
        solutions: List of solution preview dicts
        checkpoint_path: Path to phase 1 checkpoint
        total_to_validate: Number of solutions to validate
        skip_validation: If True, skip validation step
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "solutions": solutions,
            "checkpoint_path": checkpoint_path,
            "total_to_validate": total_to_validate,
            "skip_validation": skip_validation,
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/ideas-ready",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Ideas ready notification sent for job {job_id} ({len(solutions)} solutions)")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify ideas ready: {e}")



def notify_regeneration_complete(job_id: str, new_solutions: list[dict]) -> None:
    """
    Notify backend that regeneration is complete with new solutions.

    Args:
        job_id: The job UUID
        new_solutions: List of new solution preview dicts
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "solutions": new_solutions,
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/regeneration-complete",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Regeneration complete notification sent for job {job_id}")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify regeneration complete: {e}")



def notify_regeneration_failed(job_id: str, error_message: str) -> None:
    """
    Notify backend that regeneration failed. Reverts job to AWAITING_SELECTION
    so the user can see existing solutions and retry.

    Args:
        job_id: The job UUID
        error_message: Description of what went wrong
    """
    try:
        payload = {
            "worker_id": _get_worker_id(),
            "job_id": job_id,
            "error_message": error_message[:2000],
        }

        response = requests.post(
            f"{_get_backend_url()}/api/workers/regeneration-failed",
            json=payload,
            headers={"x-internal-service": _get_internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        logger.info(f"[Progress] Regeneration failed notification sent for job {job_id}")

    except requests.exceptions.RequestException as e:
        logger.error(f"[Progress] Failed to notify regeneration failed: {e}")


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
