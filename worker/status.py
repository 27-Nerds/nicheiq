"""
Status update module for direct database updates via backend API.

This module provides job status updates by calling the backend API directly.
Stage progress updates are handled by the progress module (POST /api/workers/progress).
"""

import os

import requests
from loguru import logger


def mark_job_running(job_id: str) -> bool:
    """
    Mark job as RUNNING via backend API.

    This ensures the job status is updated in the database immediately when
    the worker starts processing.

    Note: Stage progress updates are handled separately by the progress module
    via POST /api/workers/progress.

    Args:
        job_id: The job UUID

    Returns:
        True on success, False on failure (non-blocking)
    """
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:3001")
    internal_secret = os.environ.get("INTERNAL_SERVICE_SECRET", "")

    try:
        response = requests.patch(
            f"{backend_url}/api/jobs/{job_id}/status",
            json={"status": "RUNNING"},
            headers={"x-internal-service": internal_secret},
            timeout=5,
        )
        response.raise_for_status()
        logger.info(f"[Worker] Job {job_id} status -> RUNNING")
        return True
    except requests.exceptions.Timeout:
        logger.warning(f"[Worker] Status update timed out for job {job_id}")
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Worker] Status update failed for job {job_id}: {e}")
        return False
