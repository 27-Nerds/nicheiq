"""
Worker heartbeat module for crash detection and recovery.

Sends periodic heartbeats to the backend to indicate the worker is alive.
On graceful shutdown (SIGTERM/SIGINT), notifies the backend immediately.
"""

import os
import socket
import threading
import uuid
from typing import Optional

import requests
from loguru import logger

from worker.error_classifier import classify_error, build_error_details

# Generate unique worker ID (persists for lifetime of process)
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"

# Heartbeat configuration
HEARTBEAT_INTERVAL_SECONDS = 15  # Send heartbeat every 15 seconds
HEARTBEAT_TIMEOUT_SECONDS = 5    # HTTP request timeout

# Current state
_current_job_id: Optional[str] = None
_heartbeat_thread: Optional[threading.Thread] = None
_shutdown_event: threading.Event = threading.Event()
_started = False

# Cancellation state (set by heartbeat response, checked by worker)
_cancellation_requested: bool = False
_cancellation_lock: threading.Lock = threading.Lock()


class JobCancelledException(Exception):
    """Exception raised when a job is cancelled by user."""
    pass


def is_cancellation_requested() -> bool:
    """Check if cancellation was requested for the current job."""
    with _cancellation_lock:
        return _cancellation_requested


def clear_cancellation_flag() -> None:
    """Clear the cancellation flag (called when starting a new job)."""
    global _cancellation_requested
    with _cancellation_lock:
        _cancellation_requested = False


def check_cancellation() -> None:
    """
    Check if cancellation was requested and raise exception if so.
    Call this at stage transitions to allow graceful cancellation.
    """
    if is_cancellation_requested():
        raise JobCancelledException("Job cancelled by user")


def request_shutdown_cancellation() -> None:
    """Set cancellation flag directly from signal handler.

    IMPORTANT: This function is called from a signal handler, so it must NOT
    acquire _cancellation_lock. Signal handlers run in the main thread between
    bytecodes — if the main thread already holds the lock (e.g. inside
    clear_cancellation_flag()), acquiring it here would deadlock.
    CPython's GIL guarantees atomic bool assignment, so this is safe.
    """
    global _cancellation_requested
    _cancellation_requested = True


def get_worker_id() -> str:
    """Get the unique worker ID for this process."""
    return WORKER_ID


def _get_backend_url() -> str:
    """Get backend URL from environment."""
    return os.environ.get("BACKEND_URL", "http://localhost:3001")


def _get_internal_secret() -> str:
    """Get internal service secret from environment."""
    return os.environ.get("INTERNAL_SERVICE_SECRET", "")


def _send_heartbeat() -> bool:
    """
    Send a heartbeat to the backend and check for cancellation.

    Returns:
        True if successful, False otherwise
    """
    global _cancellation_requested

    try:
        response = requests.post(
            f"{_get_backend_url()}/api/workers/heartbeat",
            json={
                "worker_id": WORKER_ID,
                "job_id": _current_job_id,
                "hostname": socket.gethostname(),
                "process_id": os.getpid(),
            },
            headers={"x-internal-service": _get_internal_secret()},
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        # Check for cancellation signal from backend
        try:
            data = response.json()
            if data.get("shouldCancel", False):
                with _cancellation_lock:
                    _cancellation_requested = True
                logger.warning(f"[Heartbeat] Received cancellation signal for job {_current_job_id}")
        except (ValueError, KeyError):
            pass  # Response parsing failed, ignore

        return True
    except requests.exceptions.Timeout:
        logger.warning("[Heartbeat] Heartbeat request timed out")
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Heartbeat] Failed to send heartbeat: {e}")
        return False


# Reliable-queue claim refresher (2026-07-02 infra review round 2): the queue consumer
# registers a callable that re-stamps the job's processing-list claim. Without refresh, a
# legitimately long job (backend max runtime 4h) outlives STALE_CLAIM_SECONDS (2h) and the
# sweep requeues it WHILE STILL RUNNING. Refreshing from this thread means a claim only goes
# stale when the worker is actually dead.
_claim_refresher = None


def set_claim_refresher(fn) -> None:
    """Register fn(job_id) to be called each heartbeat tick while a job is in flight."""
    global _claim_refresher
    _claim_refresher = fn


def _heartbeat_loop() -> None:
    """
    Background thread that sends periodic heartbeats.
    Runs until shutdown_event is set.
    """
    logger.info(f"[Heartbeat] Starting heartbeat thread for worker {WORKER_ID}")

    while not _shutdown_event.is_set():
        _send_heartbeat()
        if _current_job_id and _claim_refresher is not None:
            try:
                _claim_refresher(_current_job_id)
            except Exception as e:  # noqa: BLE001 — refresh is advisory, never kill the thread
                logger.debug(f"[Heartbeat] claim refresh failed (non-fatal): {e}")
        # Wait for interval or until shutdown
        _shutdown_event.wait(HEARTBEAT_INTERVAL_SECONDS)

    logger.info("[Heartbeat] Heartbeat thread stopped")


def start_heartbeat() -> None:
    """
    Start the background heartbeat thread.
    Should be called once when worker starts.
    """
    global _heartbeat_thread, _started

    if _started:
        logger.warning("[Heartbeat] Heartbeat already started")
        return

    _shutdown_event.clear()
    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _heartbeat_thread.start()
    _started = True

    logger.info(f"[Heartbeat] Worker {WORKER_ID} heartbeat started")


def stop_heartbeat() -> None:
    """
    Stop the background heartbeat thread.
    Called during graceful shutdown.
    """
    global _started

    if not _started:
        return

    _shutdown_event.set()

    if _heartbeat_thread and _heartbeat_thread.is_alive():
        _heartbeat_thread.join(timeout=2)

    _started = False
    logger.info("[Heartbeat] Heartbeat stopped")


def set_current_job(job_id: Optional[str]) -> None:
    """
    Update the current job being processed.

    Args:
        job_id: The job ID, or None if idle
    """
    global _current_job_id
    _current_job_id = job_id

    if job_id:
        # Clear cancellation flag when starting a new job
        clear_cancellation_flag()
        logger.debug(f"[Heartbeat] Now processing job {job_id}")
    else:
        logger.debug("[Heartbeat] Worker now idle")


def notify_job_started(job_id: str) -> bool:
    """
    Notify backend that this worker has started processing a job.

    Args:
        job_id: The job ID

    Returns:
        True if should proceed with processing, False if job was cancelled
    """
    global _current_job_id
    _current_job_id = job_id

    # Claim the dispatch, don't just announce arrival. The backend turns this into the
    # AUTHORIZED -> CLAIMED transition, which is what decides whether a later cancel owes the
    # user a refund (nothing ran) or not (work started). It also rejects a SECOND worker for
    # the same dispatch instead of waving it through as a duplicate.
    from .progress import _dispatch_payload

    try:
        response = requests.post(
            f"{_get_backend_url()}/api/workers/job-started",
            json={
                "worker_id": WORKER_ID,
                "job_id": job_id,
                **_dispatch_payload(job_id),
            },
            headers={"x-internal-service": _get_internal_secret()},
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        # Check if job was cancelled while in queue
        data = response.json()
        if data.get("shouldCancel", False):
            logger.warning(f"[Heartbeat] Job {job_id} was cancelled - aborting")
            return False

        logger.info(f"[Heartbeat] Notified backend: job {job_id} started")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Heartbeat] Failed to notify job started: {e}")
        return True  # Proceed anyway if backend unreachable


def notify_job_completed(job_id: str) -> bool:
    """
    Notify backend that this worker has finished processing a job.

    Args:
        job_id: The job ID

    Returns:
        True if successful, False otherwise
    """
    global _current_job_id
    _current_job_id = None

    try:
        response = requests.post(
            f"{_get_backend_url()}/api/workers/job-completed",
            json={
                "worker_id": WORKER_ID,
                "job_id": job_id,
            },
            headers={"x-internal-service": _get_internal_secret()},
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info(f"[Heartbeat] Notified backend: job {job_id} completed")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Heartbeat] Failed to notify job completed: {e}")
        return False


def notify_job_failed(job_id: str, error_message: str, error_stage: Optional[int] = None) -> bool:
    """
    Notify backend that a job has failed.
    This is the ONLY place worker should notify about job failures.

    The backend endpoint is idempotent - safe to call multiple times.
    Errors are automatically classified into user-friendly categories.

    Args:
        job_id: The job ID
        error_message: Error description
        error_stage: Optional stage number where failure occurred

    Returns:
        True if successful, False otherwise
    """
    global _current_job_id
    _current_job_id = None

    # Classify the error for user-friendly messaging
    classified = classify_error(error_message, error_stage)
    error_details = build_error_details(classified)

    logger.debug(f"[Heartbeat] Classified error as {classified.code} for job {job_id}")

    try:
        response = requests.post(
            f"{_get_backend_url()}/api/workers/job-failed",
            json={
                "worker_id": WORKER_ID,
                "job_id": job_id,
                "error_message": error_message,
                "error_stage": error_stage,
                "error_code": classified.code,
                "error_details": error_details,
            },
            headers={"x-internal-service": _get_internal_secret()},
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info(f"[Heartbeat] Notified backend: job {job_id} failed (code: {classified.code})")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"[Heartbeat] Failed to notify job failed: {e}")
        return False


def notify_shutdown(reason: str = "signal") -> bool:
    """
    Notify backend that this worker is shutting down.
    Called on SIGTERM/SIGINT before exiting.

    Args:
        reason: Reason for shutdown (e.g., "SIGTERM", "SIGINT")

    Returns:
        True if successful, False otherwise
    """
    try:
        response = requests.post(
            f"{_get_backend_url()}/api/workers/shutdown",
            json={
                "worker_id": WORKER_ID,
                "job_id": _current_job_id,
                "reason": reason,
            },
            headers={"x-internal-service": _get_internal_secret()},
            timeout=HEARTBEAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info(f"[Heartbeat] Shutdown notification sent: {reason}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"[Heartbeat] Failed to notify shutdown: {e}")
        return False


def get_current_job_id() -> Optional[str]:
    """Get the ID of the job currently being processed."""
    return _current_job_id
