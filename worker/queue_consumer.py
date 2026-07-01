#!/usr/bin/env python3
"""
Queue consumer for NicheIQ.

Consumes jobs from the Redis queue (pushed by Node.js) and executes them.
This bridges the Node.js backend with the Python research pipeline.

Features:
- Graceful shutdown on SIGTERM/SIGINT
- Worker heartbeat for crash detection
- Automatic job recovery on worker restart

Usage:
    python -m worker.queue_consumer
"""

import gc
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

# Task types and modes (must match backend/src/services/queueService.ts)
TASK_TYPE_LANDING_PAGE = "landing_page"
TASK_TYPE_RESEARCH_PHASE2 = "research_phase2"
TASK_TYPE_REGENERATE_IDEAS = "regenerate_ideas"
TASK_TYPE_CATALOG_PAIN_POINTS = "catalog_pain_points"
TASK_TYPE_CATALOG_IDEAS = "catalog_ideas"
TASK_TYPE_CATALOG_PAIN_RESEARCH = "catalog_pain_research"
TASK_TYPE_CATALOG_DEEP_RESEARCH = "catalog_deep_research"
JOB_MODE_INTERACTIVE = "interactive"
STATUS_AWAITING_SELECTION = "awaiting_selection"

# Graceful shutdown
shutdown_requested = False
current_job_id = None
_signal_count = 0

# Post-job recycle — exit cleanly after N jobs so Docker restart: unless-stopped
# brings up a fresh process. This is the load-bearing backstop for memory
# leaks; recycle is post-job only (never signal-based), so in-flight jobs are
# never interrupted.
MAX_JOBS_PER_WORKER = int(os.environ.get("MAX_JOBS_PER_WORKER", "50"))
_jobs_processed = 0


def _current_rss_mb() -> float:
    """Return current process RSS in MB. Linux-only; returns 0.0 elsewhere."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # VmRSS:   123456 kB
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def signal_handler(signum, frame):
    """Handle shutdown signals with two-phase approach.

    1st signal: Graceful — set shutdown flag + trigger cancellation so the
    current job stops at the next stage boundary.
    2nd signal: Forced — os._exit(1) for immediate hard exit.
    """
    global shutdown_requested, _signal_count
    _signal_count += 1
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"

    if _signal_count == 1:
        # --- GRACEFUL: stop at next stage boundary ---
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        logger.info("Send signal again to force immediate exit.")
        shutdown_requested = True
        try:
            from .heartbeat import request_shutdown_cancellation
            request_shutdown_cancellation()
        except Exception as e:
            logger.error(f"Error setting cancellation flag: {e}")
    else:
        # --- FORCED: exit now ---
        logger.warning(f"Received {signal_name} again — forcing immediate exit")
        os._exit(1)


def get_redis_connection() -> redis.Redis:
    """Create Redis connection from environment."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def process_job(job_data: dict) -> None:
    """
    Process a single job from the queue.

    Args:
        job_data: Dict with job_id, niche, user_id, allowed_project_types
    """
    global current_job_id

    job_id = job_data.get("job_id")
    task_type = job_data.get("task_type", "research")

    current_job_id = job_id
    logger.info(f"Processing job {job_id} (task_type={task_type})")

    try:
        # Notify backend that we're starting this job
        from .heartbeat import notify_job_started, set_current_job
        set_current_job(job_id)

        # Check if job was cancelled while in queue
        should_proceed = notify_job_started(job_id)
        if not should_proceed:
            logger.info(f"Job {job_id} was cancelled - skipping processing")
            set_current_job(None)
            return

        if task_type == TASK_TYPE_LANDING_PAGE:
            from .tasks import run_landing_page_only

            result = run_landing_page_only(
                job_id=job_id,
                report_path=job_data["report_path"],
                page_mode=job_data.get("page_mode", "coming_soon"),
            )
        elif task_type == TASK_TYPE_RESEARCH_PHASE2:
            from .tasks import run_research_phase2

            result = run_research_phase2(
                job_id=job_id,
                checkpoint_path=job_data["checkpoint_path"],
                selected_solutions=job_data.get("selected_solutions") or [job_data.get("selected_solution", "")],
                selection_rationale=job_data.get("selection_rationale", ""),
            )
        elif task_type == TASK_TYPE_REGENERATE_IDEAS:
            from .tasks import run_regenerate_ideas

            result = run_regenerate_ideas(
                job_id=job_id,
                checkpoint_path=job_data["checkpoint_path"],
                existing_solution_names=job_data.get("existing_solution_names", []),
                niche=job_data.get("niche", ""),
                idea_focus=job_data.get("idea_focus"),
            )
        elif task_type == TASK_TYPE_CATALOG_PAIN_POINTS:
            from .tasks import run_catalog_pain_points

            result = run_catalog_pain_points(
                job_id=job_id,
                category_id=job_data["category_id"],
                category_name=job_data["category_name"],
                category_description=job_data.get("category_description", ""),
                parent_category_name=job_data.get("parent_category_name", ""),
            )
        elif task_type == TASK_TYPE_CATALOG_IDEAS:
            from .tasks import run_catalog_ideas

            result = run_catalog_ideas(
                job_id=job_id,
                category_id=job_data["category_id"],
                pain_points=job_data["pain_points"],
                niche=job_data.get("niche", ""),
                parent_category_name=job_data.get("parent_category_name", ""),
                existing_ideas=job_data.get("existing_ideas", []),
                # Phase 5.4 — when the admin generated ideas from existing
                # pain points, this is the pain-points-job's sourceJobId so
                # ideas inherit the same CatalogResearchContext.
                parent_source_job_id=job_data.get("parent_source_job_id"),
                content_categorization=job_data.get("content_categorization"),
            )
        elif task_type == TASK_TYPE_CATALOG_PAIN_RESEARCH:
            from .tasks import run_catalog_pain_research

            result = run_catalog_pain_research(
                job_id=job_id,
                pain_seeds=job_data["pain_seeds"],
                niche=job_data.get("niche", ""),
                user_id=job_data.get("user_id"),
                allowed_project_types=job_data.get("allowed_project_types"),
            )
        elif task_type == TASK_TYPE_CATALOG_DEEP_RESEARCH:
            from .tasks import run_catalog_deep_research

            result = run_catalog_deep_research(
                job_id=job_id,
                idea_seed=job_data["idea_seed"],
                niche=job_data.get("niche", ""),
                user_id=job_data.get("user_id"),
            )
        else:
            # Default research task
            niche = job_data.get("niche")
            user_id = job_data.get("user_id")
            allowed_project_types = job_data.get("allowed_project_types")
            resume = job_data.get("resume", False)
            job_mode = job_data.get("job_mode")
            entry_mode = job_data.get("entry_mode")
            idea_focus = job_data.get("idea_focus")

            logger.info(f"Processing research for user {user_id or 'anonymous'}: {niche[:50]}... (resume={resume}, mode={job_mode})")

            if job_mode == JOB_MODE_INTERACTIVE:
                from .tasks import run_interactive_research

                result = run_interactive_research(
                    job_id=job_id,
                    niche=niche,
                    user_id=user_id,
                    allowed_project_types=allowed_project_types,
                    resume=resume,
                    entry_mode=entry_mode,
                    idea_focus=idea_focus,
                )
            else:
                from .tasks import run_research_job

                result = run_research_job(
                    job_id=job_id,
                    niche=niche,
                    user_id=user_id,
                    allowed_project_types=allowed_project_types,
                    resume=resume,
                )

        logger.info(f"Job {job_id} completed: {result}")

        # For interactive jobs that are awaiting selection, don't notify completion
        if isinstance(result, dict) and result.get("status") == STATUS_AWAITING_SELECTION:
            logger.info(f"Job {job_id} awaiting user selection - worker releasing without completion notification")
        elif task_type in (TASK_TYPE_CATALOG_PAIN_POINTS, TASK_TYPE_CATALOG_IDEAS):
            logger.info(f"Job {job_id} catalog generation complete - worker releasing")
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)
        elif task_type == TASK_TYPE_REGENERATE_IDEAS:
            logger.info(f"Job {job_id} regeneration complete - worker releasing")
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)
        else:
            # Notify backend that job is done
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)

    except Exception as e:
        # Import here to avoid circular imports
        from .heartbeat import JobCancelledException, notify_job_completed, notify_job_failed

        # Handle cancellation (user-initiated or shutdown-triggered)
        if isinstance(e, JobCancelledException):
            if shutdown_requested:
                logger.info(f"Job {job_id} interrupted by worker shutdown")
                from .heartbeat import notify_shutdown
                notify_shutdown("shutdown")
                return  # run_consumer() loop will exit and call stop_heartbeat()
            else:
                logger.info(f"Job {job_id} cancelled by user - stopping gracefully")
                # Don't publish failure - backend already knows job is CANCELLED
                notify_job_completed(job_id)
                return

        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"Job {job_id} failed: {error_msg}\n{error_traceback}")

        # Regeneration failures should revert to AWAITING_SELECTION, not FAILED.
        # This preserves existing solutions and avoids an incorrect credit refund.
        if task_type == TASK_TYPE_REGENERATE_IDEAS:
            try:
                from .progress import notify_regeneration_failed
                notify_regeneration_failed(job_id, error_msg)
                return  # Don't fall through to notify_job_failed
            except Exception as revert_err:
                logger.error(f"Failed to revert regeneration for {job_id}: {revert_err}")
                # Fall through to notify_job_failed as last resort

        # Extract stage from exception if available (set by tasks.py)
        failed_stage = getattr(e, 'failed_stage', None)

        # Single point of failure notification - calls idempotent backend endpoint
        # This handles status update, refund, and clears worker's current job
        notify_job_failed(job_id, error_msg, failed_stage)

    finally:
        current_job_id = None
        from .heartbeat import set_current_job
        set_current_job(None)
        # Force a collection cycle so glibc (with MALLOC_ARENA_MAX=2) can return
        # arenas to the OS between jobs. Then log current RSS for leak-watching.
        gc.collect()
        logger.info(
            f"Job {job_id} done | rss_mb={_current_rss_mb():.0f} | "
            f"jobs={_jobs_processed + 1}/{MAX_JOBS_PER_WORKER}"
        )


def run_consumer():
    """Main consumer loop - blocks on Redis queue and processes jobs."""
    global shutdown_requested, _jobs_processed

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start heartbeat service
    from .heartbeat import start_heartbeat, get_worker_id
    start_heartbeat()

    worker_id = get_worker_id()
    redis_conn = get_redis_connection()

    logger.info(f"NicheIQ Queue Consumer started (Worker ID: {worker_id})")
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

            # Post-job recycle check. process_job() has returned (success,
            # failure, or user-cancellation), so the in-flight job is done
            # and it is safe to ask the loop to exit on its next iteration.
            _jobs_processed += 1
            if _jobs_processed >= MAX_JOBS_PER_WORKER:
                logger.info(
                    f"Reached MAX_JOBS_PER_WORKER={MAX_JOBS_PER_WORKER} — "
                    "recycling worker via clean exit"
                )
                shutdown_requested = True

        except redis.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            logger.info("Retrying in 5 seconds...")
            import time
            time.sleep(5)

        except Exception as e:
            logger.error(f"Consumer error: {e}")
            import time
            time.sleep(1)

    # Cleanup
    from .heartbeat import stop_heartbeat
    stop_heartbeat()

    logger.info("Queue consumer stopped")


if __name__ == "__main__":
    run_consumer()
