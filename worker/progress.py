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
    5: "Search & Discovery",
    6: "Pain Point Analysis",
    6.5: "Audience Mapping",
    7: "Solution Pipeline",
    8: "Pricing Validation",
    8.5: "Keyword Validation",
    8.55: "Traffic Monetization",
    8.6: "Market Sizing",
    8.7: "Solution Refinement",
    9: "SEO Strategy",
    9.5: "Trend Analysis",
    9.6: "SEO Score Refinement",
    9.7: "Data Source Research",
    10: "Report Generation",
    11: "Landing Page Generation",
}


def publish_progress_via_api(
    job_id: str,
    stage: float,
    name: str,
    status: str,
    error: Optional[str] = None,
    report_path: Optional[str] = None,
    landing_path: Optional[str] = None,
) -> bool:
    """
    Publish progress update to backend API.

    This is the single path for all progress updates:
    - Stage transitions (running, completed, failed)
    - Job completion (with report_path)
    - Job failure (with error)

    Args:
        job_id: The job UUID
        stage: Stage number (e.g., 1, 5, 6.5, 9)
        name: Human-readable stage name
        status: 'running', 'completed', or 'failed'
        error: Optional error message (for failed status)
        report_path: Optional path to report (for job completion)
        landing_path: Optional path to landing page (for job completion)

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
) -> Callable[[float, Optional[str], str], None]:
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
        Callback function that takes (stage_num, stage_name, status)
    """
    def callback(stage_num: float, stage_name: Optional[str], status: str) -> None:
        """
        Progress callback for ResearchFlow stages.

        Args:
            stage_num: Stage number (e.g., 1, 5, 6.5, 8.5)
            stage_name: Human-readable stage name (optional - looked up from STAGE_NAMES if None)
            status: 'running', 'completed', or 'failed'
        """
        # Look up stage name if not provided
        name = stage_name if stage_name else STAGE_NAMES.get(stage_num, f"Stage {stage_num}")

        # Publish to backend API (handles DB update and SSE broadcast)
        should_cancel = publish_progress_via_api(
            job_id=job_id,
            stage=stage_num,
            name=name,
            status=status,
        )

        # Check for cancellation when a stage starts running (best point to stop)
        if check_cancellation and status == "running" and should_cancel:
            from .heartbeat import JobCancelledException
            raise JobCancelledException("Job cancelled by user")

    return callback


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
        stage=11 if landing_path else 10,  # Use last completed stage
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
