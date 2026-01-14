"""
Status update module for direct database updates via backend API.

This module provides reliable job status updates by calling the backend API directly,
avoiding race conditions with Redis pub/sub where messages can be lost if the
SSE connection isn't established yet.
"""

import os

import requests
from loguru import logger


def mark_job_running(job_id: str) -> bool:
    """
    Mark job as RUNNING via backend API.

    This ensures the job status is updated in the database immediately when
    the worker starts processing, regardless of whether the frontend's SSE
    connection is established.

    Args:
        job_id: The job UUID

    Returns:
        True on success, False on failure (non-blocking)
    """
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:3001")
    internal_key = os.environ.get("INTERNAL_API_KEY", "")

    try:
        response = requests.patch(
            f"{backend_url}/api/jobs/{job_id}/status",
            json={"status": "RUNNING"},
            headers={"x-internal-key": internal_key},
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
