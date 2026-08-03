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
# Reliable-queue companions (2026-07-02 infra review: a bare BRPOP loses the job forever if
# the worker dies mid-processing). Jobs are BLMOVEd into the processing list, acked (LREM)
# after process_job returns, and stale entries are requeued by the sweep below.
PROCESSING_QUEUE = "nicheiq:jobs:processing"
CLAIMS_HASH = "nicheiq:jobs:claims"          # attempt key -> "<epoch>:<worker_id>"
STALE_CLAIM_SECONDS = 2 * 60 * 60            # > max observed job duration
REQUEUE_SWEEP_INTERVAL_SECONDS = 10 * 60

# Redis-side compare-and-set keeps a late worker for the same delivery from refreshing or deleting
# the lease owned by the worker that actually won it. Different dispatches already have different
# fields; the owner check also closes the duplicate-delivery race within one dispatch.
_CLAIM_ATTEMPT_LUA = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current then return 0 end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
return 1
"""

_REFRESH_CLAIM_LUA = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current then
  local sep = string.find(current, ':', 1, true)
  local owner = sep and string.sub(current, sep + 1) or ''
  if owner ~= ARGV[2] then return -1 end
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3] .. ':' .. ARGV[2])
return 1
"""

_ACK_PROCESSING_LUA = """
local removed = redis.call('LREM', KEYS[1], 1, ARGV[1])
local current = redis.call('HGET', KEYS[2], ARGV[2])
if current then
  local sep = string.find(current, ':', 1, true)
  local owner = sep and string.sub(current, sep + 1) or ''
  if owner == ARGV[3] then
    redis.call('HDEL', KEYS[2], ARGV[2])
  end
end
return removed
"""

_REQUEUE_STALE_LUA = """
local current = redis.call('HGET', KEYS[2], ARGV[2])
local claim_key = ARGV[2]
if not current then
  current = redis.call('HGET', KEYS[2], ARGV[4])
  claim_key = ARGV[4]
end
local stale = not current
if current then
  local sep = string.find(current, ':', 1, true)
  local claimed_at = sep and tonumber(string.sub(current, 1, sep - 1)) or nil
  stale = (not claimed_at) or claimed_at <= tonumber(ARGV[3])
end
if not stale then return 0 end
local removed = redis.call('LREM', KEYS[1], 1, ARGV[1])
if removed > 0 then
  redis.call('HDEL', KEYS[2], claim_key)
  redis.call('LPUSH', KEYS[3], ARGV[1])
end
return removed
"""

# Task types and modes (must match backend/src/services/queueService.ts)
TASK_TYPE_LANDING_PAGE = "landing_page"
TASK_TYPE_RESEARCH_PHASE2 = "research_phase2"
TASK_TYPE_REGENERATE_IDEAS = "regenerate_ideas"
TASK_TYPE_SEED_IDEA = "seed_idea"
TASK_TYPE_RECOVER_PAID_POOL = "recover_paid_pool_operation"
TASK_TYPE_CATALOG_PAIN_POINTS = "catalog_pain_points"
TASK_TYPE_CATALOG_IDEAS = "catalog_ideas"
TASK_TYPE_CATALOG_PAIN_RESEARCH = "catalog_pain_research"
TASK_TYPE_CATALOG_DEEP_RESEARCH = "catalog_deep_research"
TASK_TYPE_CONTINUE_FROM_GATE = "continue_from_gate"
JOB_MODE_INTERACTIVE = "interactive"
STATUS_AWAITING_SELECTION = "awaiting_selection"
STATUS_AWAITING_GATE = "awaiting_gate"

# Graceful shutdown
shutdown_requested = False
current_job_id = None
current_recovery_token = None
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
    # Clear the systemic-LLM breaker from any previous job in this process.
    from nicheiq.utils.llm_service import LLMService as _LLMSvc
    _LLMSvc.reset_systemic()
    global current_job_id, current_recovery_token

    job_id = job_data.get("job_id")
    task_type = job_data.get("task_type", "research")

    current_job_id = job_id
    current_recovery_token = job_data.get("recovery_token")
    logger.info(f"Processing job {job_id} (task_type={task_type})")

    # Register the dispatch id BEFORE anything reports home — notify_job_started is itself a
    # guarded callback, so the id has to be in place before that first call. Missing id (an
    # older backend, or a message that was already in the queue when this shipped) is fine:
    # every callback simply omits the field and the backend takes its legacy path.
    from .progress import set_active_dispatch, clear_active_dispatch
    dispatch_id = job_data.get("dispatch_id")
    set_active_dispatch(job_id, dispatch_id)
    if dispatch_id:
        logger.info(f"Job {job_id} dispatch={dispatch_id}")

    try:
        # Notify backend that we're starting this job
        from .heartbeat import notify_job_started, set_current_job
        set_current_job(job_id)

        # Check if job was cancelled while in queue
        should_proceed = notify_job_started(
            job_id,
            recovery_token=job_data.get("recovery_token"),
        )
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
                selected_solution_refs=job_data.get("selected_solution_refs"),
                selected_solution_snapshots=job_data.get("selected_solution_snapshots"),
                selection_fingerprint=job_data.get("selection_fingerprint"),
                selection_rationale=job_data.get("selection_rationale", ""),
                pool_identity_map=job_data.get("pool_identity_map"),
            )
        elif task_type == TASK_TYPE_REGENERATE_IDEAS:
            from .tasks import run_regenerate_ideas

            result = run_regenerate_ideas(
                job_id=job_id,
                checkpoint_path=job_data["checkpoint_path"],
                existing_solution_names=job_data.get("existing_solution_names", []),
                niche=job_data.get("niche", ""),
                idea_focus=job_data.get("idea_focus"),
                dispatch_id=job_data.get("dispatch_id"),
                batch_ordinal=job_data.get("batch_ordinal"),
                base_candidate_refs=job_data.get("base_candidate_refs"),
                pool_identity_map=job_data.get("pool_identity_map"),
            )
        elif task_type == TASK_TYPE_SEED_IDEA:
            from .tasks import run_seed_idea

            result = run_seed_idea(
                job_id=job_id,
                checkpoint_path=job_data["checkpoint_path"],
                seed={
                    "seed_text": job_data.get("seed_text", ""),
                    "pain_ref": job_data.get("pain_ref"),
                    "tool_ref": job_data.get("tool_ref"),
                    "synthesis_evaluation": job_data.get("synthesis_evaluation"),
                },
                niche=job_data.get("niche", ""),
                dispatch_id=job_data.get("dispatch_id"),
                base_candidate_refs=job_data.get("base_candidate_refs"),
                pool_identity_map=job_data.get("pool_identity_map"),
            )
        elif task_type == TASK_TYPE_RECOVER_PAID_POOL:
            from .paid_pool_recovery import run_paid_pool_recovery

            result = run_paid_pool_recovery(
                job_id=job_id,
                dispatch_id=job_data["dispatch_id"],
                recovery_token=job_data["recovery_token"],
                journal=job_data["recovery_journal"],
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
        elif task_type == TASK_TYPE_CONTINUE_FROM_GATE:
            from .tasks import continue_from_gate

            result = continue_from_gate(
                job_id=job_id,
                checkpoint_path=job_data["checkpoint_path"],
                gate_stage=job_data["gate_stage"],
                mode=job_data.get("mode", "continue"),
                patch=job_data.get("patch"),
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
            chat_mode = job_data.get("chat_mode", False)

            logger.info(f"Processing research for user {user_id or 'anonymous'}: {niche[:50]}... (resume={resume}, mode={job_mode}, chat_mode={chat_mode})")

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
                    chat_mode=chat_mode,
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
        if isinstance(result, dict) and result.get("status") in (STATUS_AWAITING_SELECTION, STATUS_AWAITING_GATE):
            logger.info(
                f"Job {job_id} awaiting {result.get('status')} - worker releasing without "
                "completion notification"
            )
        elif task_type in (TASK_TYPE_CATALOG_PAIN_POINTS, TASK_TYPE_CATALOG_IDEAS):
            logger.info(f"Job {job_id} catalog generation complete - worker releasing")
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)
        elif task_type == TASK_TYPE_REGENERATE_IDEAS:
            logger.info(f"Job {job_id} regeneration complete - worker releasing")
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)
        elif task_type == TASK_TYPE_SEED_IDEA:
            logger.info(f"Job {job_id} seed idea settled - worker releasing")
            from .heartbeat import notify_job_completed
            notify_job_completed(job_id)
        elif task_type == TASK_TYPE_RECOVER_PAID_POOL:
            logger.info(f"Job {job_id} paid pool operation recovered - worker releasing")
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

        from .paid_pool_recovery import (
            PaidPoolCompletionAmbiguous,
            PaidPoolOperationFenced,
            PaidPoolRecoveryRequired,
        )
        if isinstance(
            e,
            (PaidPoolCompletionAmbiguous, PaidPoolOperationFenced, PaidPoolRecoveryRequired),
        ):
            logger.warning(
                f"Job {job_id} writer was fenced; retained before-image for recovery"
            )
            return
        if task_type == TASK_TYPE_RECOVER_PAID_POOL:
            logger.error(
                f"Paid pool recovery for {job_id} did not settle; heartbeat will refence and retry"
            )
            return

        # Additional-batch failures settle/refund only that dispatch and restore
        # AWAITING_SELECTION; the parent research job and existing pool stay intact.
        # Two distinct outcomes reach here, both settled the same way:
        #   1. regeneration_delivery_only: the batch finished, but notify_regeneration_complete
        #      exhausted its retries. run_regenerate_ideas has already reverted the
        #      checkpoint/preview, so the refund below is owed and no ghost candidate survives.
        #   2. genuine pipeline failure: nothing was merged in the first place.
        if task_type == TASK_TYPE_REGENERATE_IDEAS:
            try:
                from .progress import notify_regeneration_failed
                if getattr(e, "regeneration_delivery_only", False):
                    error_msg = f"Batch completed but its result could not be delivered: {error_msg}"
                delivered = notify_regeneration_failed(job_id, error_msg)
                if not delivered:
                    logger.error(
                        f"Regeneration-failed revert not delivered for {job_id}; "
                        "leaving stale recovery to settle the operation without failing "
                        "the parent research job"
                    )
                elif dispatch_id:
                    from .paid_pool_recovery import cleanup_paid_pool_operation

                    cleanup_paid_pool_operation(
                        job_data["checkpoint_path"], job_id, dispatch_id,
                    )
                return  # Never fail the parent job for an additional-batch operation
            except Exception as revert_err:
                logger.error(f"Failed to revert regeneration for {job_id}: {revert_err}")
                return  # stale recovery is operation-scoped for REGENERATE

        # Seed-idea failures (eager-meandering-feather.md Phase 5) must NEVER fall through to
        # the generic notify_job_failed — that path refunds 'discovery'/segment, a charge the
        # seed op never made, and would mark the WHOLE research job FAILED over a small paid
        # follow-up request. Two distinct outcomes, neither of which is a generic job failure:
        #
        #   1. seed_delivery_only: evaluation finished, but notify_seed_complete exhausted its
        #      retries. run_seed_idea has already reverted the checkpoint/preview, so deliver
        #      seed-failed now to settle/refund the dispatch instead of leaving it RUNNING until
        #      stale recovery.
        #   2. genuine pipeline failure (birth produced nothing, or raised before any merge):
        #      notify_seed_failed reverts QUEUED/RUNNING -> AWAITING_SELECTION and refunds
        #      seed_idea_N. Its own delivery failure is ALSO not escalated to notify_job_failed
        #      — same reasoning as case 1, just the opposite charge.
        if task_type == TASK_TYPE_SEED_IDEA:
            if getattr(e, "seed_delivery_only", False):
                try:
                    from .progress import notify_seed_failed
                    delivered = notify_seed_failed(
                        job_id,
                        f"Evaluation completed but its result could not be delivered: {error_msg}",
                    )
                    if not delivered:
                        logger.error(
                            f"Seed delivery failure could not be settled for {job_id}; "
                            "the reverted result may remain QUEUED/RUNNING until stale recovery"
                        )
                    elif dispatch_id:
                        from .paid_pool_recovery import cleanup_paid_pool_operation

                        cleanup_paid_pool_operation(
                            job_data["checkpoint_path"], job_id, dispatch_id,
                        )
                except Exception as revert_err:
                    logger.error(
                        f"Failed to settle reverted seed delivery for {job_id}: {revert_err}"
                    )
                return
            try:
                from .progress import notify_seed_failed
                delivered = notify_seed_failed(job_id, error_msg)
                if not delivered:
                    logger.error(
                        f"Seed-failed revert not delivered for {job_id} — the job may be stuck "
                        "QUEUED/RUNNING; NOT falling through to notify_job_failed (would "
                        "incorrectly refund/fail the parent job for a seed-only failure)"
                    )
                elif dispatch_id:
                    from .paid_pool_recovery import cleanup_paid_pool_operation

                    cleanup_paid_pool_operation(
                        job_data["checkpoint_path"], job_id, dispatch_id,
                    )
            except Exception as revert_err:
                logger.error(f"Failed to revert seed idea for {job_id}: {revert_err}")
            return  # never generic notify_job_failed for a seed op, delivered or not

        # Gate-continuation failures (an invalid/stale patch, or a stage error while running
        # to the next stop) should revert to AWAITING_GATE, not FAILED — mirrors the
        # regeneration-failure interception above (Codex 7 / lead #4). Preserves the existing
        # gate artifact/patch history and avoids an incorrect credit refund; the user can retry.
        if task_type == TASK_TYPE_CONTINUE_FROM_GATE:
            try:
                from .progress import notify_gate_failed
                gate_stage = getattr(e, "gate_stage", None) or job_data.get("gate_stage")
                delivered = notify_gate_failed(job_id, gate_stage, error_msg)
                if delivered:
                    return  # Don't fall through to notify_job_failed
                logger.error(
                    f"Gate-failed revert not delivered for {job_id} — falling through to "
                    "notify_job_failed (never leave the job silently stuck in QUEUED)"
                )
                # Fall through to notify_job_failed as last resort
            except Exception as revert_err:
                logger.error(f"Failed to revert gate continuation for {job_id}: {revert_err}")
                # Fall through to notify_job_failed as last resort

        # Extract stage from exception if available (set by tasks.py)
        failed_stage = getattr(e, 'failed_stage', None)

        # Single point of failure notification - calls idempotent backend endpoint
        # This handles status update, refund, and clears worker's current job
        notify_job_failed(job_id, error_msg, failed_stage)

    finally:
        current_job_id = None
        current_recovery_token = None
        from .heartbeat import set_current_job
        set_current_job(None)
        # Drop the dispatch id with the job. A worker process handles many jobs in sequence,
        # and a leaked id would be stamped onto the NEXT job's callbacks — where it would match
        # nothing and silently no-op every one of them.
        clear_active_dispatch(job_id)
        # Force a collection cycle so glibc (with MALLOC_ARENA_MAX=2) can return
        # arenas to the OS between jobs. Then log current RSS for leak-watching.
        gc.collect()
        logger.info(
            f"Job {job_id} done | rss_mb={_current_rss_mb():.0f} | "
            f"jobs={_jobs_processed + 1}/{MAX_JOBS_PER_WORKER}"
        )


def _claim_key(
    job_id: str,
    dispatch_id: str | None,
    recovery_token: str | None = None,
) -> str:
    """Stable Redis field for one delivery attempt; identityless jobs use a fenced legacy key."""
    if recovery_token and dispatch_id:
        return f"recovery:{dispatch_id}:{recovery_token}"
    return f"dispatch:{dispatch_id}" if dispatch_id else f"legacy:{job_id}"


def _claim_processing_attempt(
    redis_conn,
    job_id: str,
    dispatch_id: str | None,
    worker_id: str,
    now: float,
    recovery_token: str | None = None,
) -> bool:
    """Acquire only this attempt; the backend start CAS arbitrates duplicate deliveries."""
    result = redis_conn.eval(
        _CLAIM_ATTEMPT_LUA,
        1,
        CLAIMS_HASH,
        _claim_key(job_id, dispatch_id, recovery_token),
        f"{now}:{worker_id}",
    )
    return result == 1


def _refresh_processing_claim(
    redis_conn,
    job_id: str,
    dispatch_id: str | None,
    worker_id: str,
    now: float,
    recovery_token: str | None = None,
) -> bool:
    """Refresh/create only this attempt's lease, without overwriting another worker's ownership."""
    result = redis_conn.eval(
        _REFRESH_CLAIM_LUA,
        1,
        CLAIMS_HASH,
        _claim_key(job_id, dispatch_id, recovery_token),
        worker_id,
        str(now),
    )
    return result == 1


def _ack_processing(
    redis_conn,
    raw_job_json: str,
    job_id: str | None,
    dispatch_id: str | None,
    worker_id: str,
    recovery_token: str | None = None,
) -> None:
    """Remove a finished/poison job from the processing list + its claim. Fail-soft: an ack
    failure only means the sweep requeues it later (at-least-once, never lost)."""
    try:
        if job_id:
            redis_conn.eval(
                _ACK_PROCESSING_LUA,
                2,
                PROCESSING_QUEUE,
                CLAIMS_HASH,
                raw_job_json,
                _claim_key(job_id, dispatch_id, recovery_token),
                worker_id,
            )
        else:
            redis_conn.lrem(PROCESSING_QUEUE, 1, raw_job_json)
    except redis.RedisError as e:
        logger.warning(f"[Requeue] ack failed (job {job_id}): {e} — sweep will reclaim")


def requeue_stale_processing(redis_conn) -> int:
    """Move stale processing-list entries (claim missing or older than STALE_CLAIM_SECONDS —
    i.e. their worker died mid-job) back onto the main queue. Malformed entries are dropped
    (poison). Returns the number requeued. Fail-soft on any redis error."""
    import time as _time
    requeued = 0
    try:
        entries = redis_conn.lrange(PROCESSING_QUEUE, 0, -1)
        now = _time.time()
        for raw in entries:
            try:
                payload = json.loads(raw)
                job_id = payload.get("job_id")
                dispatch_id = payload.get("dispatch_id")
                recovery_token = payload.get("recovery_token")
            except (json.JSONDecodeError, AttributeError):
                redis_conn.lrem(PROCESSING_QUEUE, 1, raw)
                logger.warning("[Requeue] dropped malformed processing entry")
                continue
            if not job_id:
                redis_conn.lrem(PROCESSING_QUEUE, 1, raw)
                logger.warning("[Requeue] dropped processing entry without job_id")
                continue
            moved = redis_conn.eval(
                _REQUEUE_STALE_LUA,
                3,
                PROCESSING_QUEUE,
                CLAIMS_HASH,
                QUEUE_NAME,
                raw,
                _claim_key(job_id, dispatch_id, recovery_token),
                str(now - STALE_CLAIM_SECONDS),
                job_id,
            )
            if moved:
                requeued += 1
                logger.info(
                    f"[Requeue] stale job {job_id} dispatch={dispatch_id or 'legacy'} "
                    "moved back to queue"
                )
    except redis.RedisError as e:
        logger.warning(f"[Requeue] sweep failed (non-fatal): {e}")
    return requeued


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

    # Claim refresh (infra review round 2): the heartbeat thread re-stamps the in-flight
    # job's claim so a long-running job (backend allows up to 4h) can never be sweep-requeued
    # while alive — a claim only ages past STALE_CLAIM_SECONDS when this worker is dead.
    from .heartbeat import set_claim_refresher
    import time as _time0

    def _refresh_claim(job_id: str, dispatch_id: str | None) -> None:
        _refresh_processing_claim(
            redis_conn,
            job_id,
            dispatch_id,
            worker_id,
            _time0.time(),
            current_recovery_token,
        )

    set_claim_refresher(_refresh_claim)

    # Reclaim anything a previously-crashed worker left behind before consuming.
    requeue_stale_processing(redis_conn)
    import time as _time
    _last_sweep = _time.time()

    while not shutdown_requested:
        try:
            # Reliable pop: BLMOVE tail->processing (producer LPUSHes the head, so RIGHT
            # keeps FIFO). The job survives a worker crash in the processing list and is
            # reclaimed by the stale sweep. Timeout 5s to re-check the shutdown flag.
            job_json = redis_conn.blmove(
                QUEUE_NAME, PROCESSING_QUEUE, timeout=5, src="RIGHT", dest="LEFT"
            )

            if job_json is None:
                # Timeout — check shutdown flag, run the periodic sweep, continue
                if _time.time() - _last_sweep >= REQUEUE_SWEEP_INTERVAL_SECONDS:
                    requeue_stale_processing(redis_conn)
                    _last_sweep = _time.time()
                continue

            job_id = None
            dispatch_id = None
            recovery_token = None
            try:
                job_data = json.loads(job_json)
                job_id = job_data.get("job_id")
                dispatch_id = job_data.get("dispatch_id")
                recovery_token = job_data.get("recovery_token")
                owns_claim = True
                if job_id:
                    try:
                        owns_claim = _claim_processing_attempt(
                            redis_conn,
                            job_id,
                            dispatch_id,
                            worker_id,
                            _time.time(),
                            recovery_token,
                        )
                    except redis.RedisError:
                        pass  # claim is advisory; the sweep treats a missing claim as stale
                logger.info(f"Received job: {job_id}")
                if owns_claim:
                    process_job(job_data)
                else:
                    logger.warning(
                        f"[Requeue] duplicate delivery already owned: job {job_id} "
                        f"dispatch={dispatch_id or 'legacy'} — dropping duplicate"
                    )
            except json.JSONDecodeError as e:
                logger.error(f"Invalid job JSON: {e}")
            finally:
                # process_job returned (success/failure/cancel — all handled inside it),
                # raised, or the payload was poison: this delivery attempt is DONE either
                # way — ack so the entry can't ping-pong via the stale sweep. A hard crash
                # (kill/OOM) never reaches this line; the sweep requeues those.
                _ack_processing(
                    redis_conn,
                    job_json,
                    job_id,
                    dispatch_id,
                    worker_id,
                    recovery_token,
                )

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
