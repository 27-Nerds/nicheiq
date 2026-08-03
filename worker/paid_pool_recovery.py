"""Durable single-writer protocol for paid selection-pool mutations."""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path
from typing import BinaryIO

import requests
from loguru import logger

from nicheiq.config.settings import settings


class PaidPoolOperationFenced(RuntimeError):
    """This worker no longer owns the paid pool mutation generation."""


class PaidPoolRecoveryRequired(RuntimeError):
    """Canonical compensation failed; settlement must remain closed for recovery."""


class PaidPoolCompletionAmbiguous(RuntimeError):
    """Completion may have committed; keep forward files until backend arbitration."""


RECOVERY_LOCK_TIMEOUT_SECONDS = 30.0
RECOVERY_LOCK_POLL_SECONDS = 0.25
MUTATION_LOCK_TIMEOUT_SECONDS = 30.0
MUTATION_LOCK_POLL_SECONDS = 0.25


def _backend_url() -> str:
    return os.environ.get("BACKEND_URL", "http://localhost:3001")


def _internal_secret() -> str:
    return os.environ.get("INTERNAL_SERVICE_SECRET", "")


def build_journal(
    checkpoint_path: str,
    preview_path: str,
    dispatch_id: str,
) -> dict:
    checkpoint = Path(checkpoint_path)
    canonical = [
        checkpoint / "stage_5_3_refinement.json",
        checkpoint / "metadata.json",
        Path(preview_path),
    ]
    return {
        "schemaVersion": 1,
        "lockPath": str(checkpoint / ".paid-pool.lock"),
        "files": [
            {
                "canonicalPath": str(source),
                "backupPath": f"{source}.paid-op-{dispatch_id}.before",
            }
            for source in canonical
        ],
    }


def _atomic_copy(source: Path, destination: Path, *, preserve_existing: bool) -> None:
    if preserve_existing and destination.exists():
        return
    data = source.read_bytes()
    temp = destination.with_name(f"{destination.name}.tmp-{os.getpid()}")
    temp.write_bytes(data)
    if preserve_existing:
        try:
            os.link(temp, destination)
        except FileExistsError:
            pass
        finally:
            temp.unlink(missing_ok=True)
    else:
        temp.replace(destination)


def _restore_journal(journal: dict) -> None:
    for row in journal.get("files", []):
        canonical = Path(row["canonicalPath"])
        backup = Path(row["backupPath"])
        if not backup.is_file():
            raise RuntimeError(f"Paid-pool recovery backup is missing: {backup}")
        canonical.parent.mkdir(parents=True, exist_ok=True)
        _atomic_copy(backup, canonical, preserve_existing=False)


def cleanup_journal(journal: dict) -> None:
    for row in journal.get("files", []):
        Path(row["backupPath"]).unlink(missing_ok=True)


def _acquire_recovery_lock(lock_file: BinaryIO) -> None:
    """Bound recovery's wait so its healthy heartbeat cannot mask a hung original writer."""
    deadline = time.monotonic() + RECOVERY_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as error:
            if time.monotonic() >= deadline:
                raise PaidPoolRecoveryRequired(
                    "Timed out waiting for the original paid-pool writer to release its lock"
                ) from error
            time.sleep(RECOVERY_LOCK_POLL_SECONDS)


def _acquire_mutation_lock(lock_file: BinaryIO) -> None:
    """A normal paid operation must not heartbeat forever behind an orphaned lock."""
    deadline = time.monotonic() + MUTATION_LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Timed out waiting for the paid-pool artifact lock before mutation"
                ) from error
            time.sleep(MUTATION_LOCK_POLL_SECONDS)


class PaidPoolMutationGuard:
    """Hold the shared artifact lock from before-image creation through settlement."""

    def __init__(self, job_id: str, dispatch_id: str, checkpoint_path: str):
        self.job_id = job_id
        self.dispatch_id = dispatch_id
        self.checkpoint_path = checkpoint_path
        self.preview_path = str(
            Path(settings.checkpoint_dir) / f"preview_report_{job_id}.json"
        )
        self.journal = build_journal(
            checkpoint_path,
            self.preview_path,
            dispatch_id,
        )
        self._lock_file: BinaryIO | None = None
        self._prepared = False

    def prepare(self) -> None:
        lock_path = Path(self.journal["lockPath"])
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(lock_path, "a+b")
        _acquire_mutation_lock(self._lock_file)

        for row in self.journal["files"]:
            canonical = Path(row["canonicalPath"])
            if not canonical.is_file():
                raise RuntimeError(
                    f"Cannot prepare paid pool operation; canonical artifact is missing: {canonical}"
                )
            _atomic_copy(
                canonical,
                Path(row["backupPath"]),
                preserve_existing=True,
            )

        from .heartbeat import get_worker_id

        response = requests.post(
            f"{_backend_url()}/api/workers/paid-pool-operation-prepared",
            json={
                "worker_id": get_worker_id(),
                "job_id": self.job_id,
                "dispatch_id": self.dispatch_id,
                "checkpoint_path": self.checkpoint_path,
                "preview_path": self.preview_path,
            },
            headers={"x-internal-service": _internal_secret()},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("stale") or not payload.get("prepared"):
            raise PaidPoolOperationFenced(
                "Paid pool operation was fenced before preparation"
            )
        self._prepared = True

    def restore(self) -> None:
        if self._prepared:
            _restore_journal(self.journal)

    def commit_and_cleanup(self) -> None:
        # Backend success is the commit point. Never make a best-effort unlink failure look
        # like an uncommitted mutation: that would restore old files after DB accepted new ones.
        self._prepared = False
        try:
            cleanup_journal(self.journal)
        except OSError as error:
            logger.warning(
                f"Paid-pool before-image cleanup failed after commit for {self.dispatch_id}: "
                f"{error}"
            )

    def close(self) -> None:
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None


def cleanup_paid_pool_operation(
    checkpoint_path: str,
    job_id: str,
    dispatch_id: str,
) -> None:
    journal = build_journal(
        checkpoint_path,
        str(Path(settings.checkpoint_dir) / f"preview_report_{job_id}.json"),
        dispatch_id,
    )
    cleanup_journal(journal)


def run_paid_pool_recovery(
    job_id: str,
    dispatch_id: str,
    recovery_token: str,
    journal: dict,
) -> dict:
    """Restore the immutable before-image, then atomically refund/reopen in the backend."""
    lock_path = Path(journal["lockPath"])
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        # If the original worker is merely partitioned, it still owns this lock. Waiting here
        # prevents recovery from racing its final write; the dispatch token already fences its
        # callback, so it will restore/release or die before we proceed.
        _acquire_recovery_lock(lock_file)

        from .heartbeat import get_worker_id

        # A recovery delivery can be refenced while it is waiting for the original writer's
        # lock. Revalidate the exact token while HOLDING that lock; otherwise an old recovery
        # could wake after a newer recovery reopened selection and overwrite a later paid pool.
        authorization = requests.post(
            f"{_backend_url()}/api/workers/job-started",
            json={
                "worker_id": get_worker_id(),
                "job_id": job_id,
                "dispatch_id": dispatch_id,
                "recovery_token": recovery_token,
            },
            headers={"x-internal-service": _internal_secret()},
            timeout=30,
        )
        authorization.raise_for_status()
        authorization_body = authorization.json()
        if authorization_body.get("stale") or authorization_body.get("shouldCancel"):
            raise PaidPoolOperationFenced(
                "Paid pool recovery was refenced while waiting for the artifact lock"
            )

        _restore_journal(journal)

        payload = {
            "worker_id": get_worker_id(),
            "job_id": job_id,
            "dispatch_id": dispatch_id,
            "recovery_token": recovery_token,
        }
        delays = (2.0, 5.0, 10.0)
        last_error: Exception | None = None
        for delay in (*delays, None):
            try:
                response = requests.post(
                    f"{_backend_url()}/api/workers/paid-pool-recovery-complete",
                    json=payload,
                    headers={"x-internal-service": _internal_secret()},
                    timeout=30,
                )
                response.raise_for_status()
                body = response.json()
                if body.get("stale"):
                    raise RuntimeError("Paid pool recovery token was superseded")
                # Keep the immutable backups until the settlement response is confirmed. If
                # the response is lost, a refenced retry can restore them again idempotently.
                try:
                    cleanup_journal(journal)
                except OSError as error:
                    logger.warning(
                        f"Paid-pool recovery backup cleanup failed after settlement: {error}"
                    )
                return {"status": "recovered", "job_id": job_id}
            except (requests.RequestException, RuntimeError) as error:
                last_error = error
                if delay is None:
                    break
                time.sleep(delay)
        raise RuntimeError(f"Paid pool recovery completion was not confirmed: {last_error}")
