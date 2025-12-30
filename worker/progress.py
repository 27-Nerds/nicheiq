"""
Progress reporting module for Redis pub/sub communication with Node.js backend.
"""

import json
import os
from typing import Any, Callable, Optional

import redis
from loguru import logger

# Redis connection for progress publishing
_redis_conn: Optional[redis.Redis] = None


def get_redis_connection() -> redis.Redis:
    """Get or create Redis connection for progress publishing."""
    global _redis_conn
    if _redis_conn is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis_conn = redis.Redis.from_url(redis_url, decode_responses=True)
    return _redis_conn


def get_progress_channel(job_id: str) -> str:
    """Get Redis channel name for a job's progress updates."""
    return f"job:{job_id}:progress"


def publish_progress(job_id: str, data: dict[str, Any]) -> None:
    """
    Publish progress update to Redis pub/sub channel.

    This is received by the Node.js backend SSE endpoint.

    Args:
        job_id: The job UUID
        data: Progress data dict with keys like:
            - stage: Stage number (float)
            - name: Stage name (str)
            - status: 'running', 'completed', 'failed'
            - error: Optional error message
    """
    try:
        conn = get_redis_connection()
        channel = get_progress_channel(job_id)
        message = json.dumps(data)
        conn.publish(channel, message)
        logger.debug(f"[Progress] Published to {channel}: {data.get('status')} stage {data.get('stage')}")
    except Exception as e:
        logger.error(f"[Progress] Failed to publish progress: {e}")


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


def create_progress_callback(job_id: str) -> Callable[[float, str, str], None]:
    """
    Create a progress callback function for ResearchFlow.

    This callback publishes stage updates to Redis, which the Node.js
    backend receives and forwards to connected SSE clients.

    Args:
        job_id: The job UUID

    Returns:
        Callback function that takes (stage_num, stage_name, status)
    """
    def callback(stage_num: float, stage_name: str, status: str) -> None:
        """
        Progress callback for ResearchFlow stages.

        Args:
            stage_num: Stage number (e.g., 1, 5, 6.5, 8.5)
            stage_name: Human-readable stage name
            status: 'running', 'completed', or 'failed'
        """
        publish_progress(job_id, {
            "stage": stage_num,
            "name": stage_name,
            "status": status,
        })

    return callback


def publish_job_completed(
    job_id: str,
    report_path: str,
    landing_path: Optional[str] = None
) -> None:
    """
    Publish job completion to Redis.

    Args:
        job_id: The job UUID
        report_path: Path to the generated report JSON
        landing_path: Optional path to the landing page HTML
    """
    data = {
        "status": "completed",
        "report_path": report_path,
    }
    if landing_path:
        data["landing_path"] = landing_path

    publish_progress(job_id, data)
    logger.info(f"[Progress] Job {job_id} completed - report: {report_path}")


def publish_job_failed(job_id: str, error: str, stage: Optional[float] = None) -> None:
    """
    Publish job failure to Redis.

    Args:
        job_id: The job UUID
        error: Error message
        stage: Optional stage where failure occurred
    """
    data = {
        "status": "failed",
        "error": error,
    }
    if stage is not None:
        data["stage"] = stage

    publish_progress(job_id, data)
    logger.error(f"[Progress] Job {job_id} failed at stage {stage}: {error}")
