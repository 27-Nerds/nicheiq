#!/usr/bin/env python3
"""
Queue consumer for NicheIQ.

Consumes jobs from the Redis queue (pushed by Node.js) and executes them.
This bridges the Node.js backend with the Python research pipeline.

Usage:
    python -m worker.queue_consumer
"""

import json
import os
import signal
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
import redis

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv(project_root / ".env")

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    project_root / "output" / "logs" / "worker_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)

# Queue configuration
QUEUE_NAME = "nicheiq:jobs"

# Graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logger.info("Shutdown signal received, finishing current job...")
    shutdown_requested = True


def get_redis_connection() -> redis.Redis:
    """Create Redis connection from environment."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def process_job(job_data: dict) -> None:
    """
    Process a single job from the queue.

    Args:
        job_data: Dict with job_id, niche, email, allowed_project_types
    """
    job_id = job_data.get("job_id")
    niche = job_data.get("niche")
    email = job_data.get("email")
    allowed_project_types = job_data.get("allowed_project_types")

    logger.info(f"Processing job {job_id}: {niche[:50]}...")

    try:
        from .tasks import run_research_job

        result = run_research_job(
            job_id=job_id,
            niche=niche,
            email=email,
            allowed_project_types=allowed_project_types,
        )

        logger.info(f"Job {job_id} completed: {result}")

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"Job {job_id} failed: {error_msg}\n{error_traceback}")

        # Publish failure to Redis
        from .progress import publish_job_failed
        publish_job_failed(job_id, error_msg)


def run_consumer():
    """Main consumer loop - blocks on Redis queue and processes jobs."""
    global shutdown_requested

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    redis_conn = get_redis_connection()

    logger.info(f"NicheIQ Queue Consumer started")
    logger.info(f"Redis URL: {os.environ.get('REDIS_URL', 'redis://localhost:6379')}")
    logger.info(f"Queue: {QUEUE_NAME}")
    logger.info("Waiting for jobs...")

    while not shutdown_requested:
        try:
            # Block waiting for jobs (timeout every 5 seconds to check shutdown flag)
            result = redis_conn.brpop(QUEUE_NAME, timeout=5)

            if result is None:
                # Timeout, check shutdown flag and continue
                continue

            queue_name, job_json = result

            try:
                job_data = json.loads(job_json)
                logger.info(f"Received job: {job_data.get('job_id')}")
                process_job(job_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid job JSON: {e}")
                continue

        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            logger.info("Retrying in 5 seconds...")
            import time
            time.sleep(5)

        except Exception as e:
            logger.error(f"Consumer error: {e}")
            import time
            time.sleep(1)

    logger.info("Queue consumer stopped")


if __name__ == "__main__":
    run_consumer()
