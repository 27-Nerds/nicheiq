import fcntl
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from worker.paid_pool_recovery import (
    PaidPoolCompletionAmbiguous,
    PaidPoolMutationGuard,
    PaidPoolOperationFenced,
    PaidPoolRecoveryRequired,
    build_journal,
    run_paid_pool_recovery,
)


class _Response:
    def __init__(self, body):
        self._body = body
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _artifacts(tmp_path: Path, monkeypatch):
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    stage = checkpoint / "stage_5_3_refinement.json"
    metadata = checkpoint / "metadata.json"
    preview = tmp_path / "preview_report_job-1.json"
    stage.write_text("stage-before")
    metadata.write_text("metadata-before")
    preview.write_text("preview-before")
    monkeypatch.setattr(
        "worker.paid_pool_recovery.settings.checkpoint_dir",
        tmp_path,
    )
    return checkpoint, stage, metadata, preview


def test_guard_restores_forward_files_and_retains_before_image(tmp_path, monkeypatch):
    checkpoint, stage, metadata, preview = _artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "worker.paid_pool_recovery.requests.post",
        Mock(return_value=_Response({"prepared": True, "stale": False})),
    )
    guard = PaidPoolMutationGuard("job-1", "dispatch-1", str(checkpoint))
    try:
        guard.prepare()
        stage.write_text("stage-forward")
        metadata.write_text("metadata-forward")
        preview.write_text("preview-forward")
        guard.restore()
        assert stage.read_text() == "stage-before"
        assert metadata.read_text() == "metadata-before"
        assert preview.read_text() == "preview-before"
        assert all(Path(row["backupPath"]).exists() for row in guard.journal["files"])
    finally:
        guard.close()


def test_normal_operation_does_not_heartbeat_forever_behind_an_orphaned_lock(
    tmp_path,
    monkeypatch,
):
    checkpoint, stage, metadata, preview = _artifacts(tmp_path, monkeypatch)
    lock_path = checkpoint / ".paid-pool.lock"
    lock_path.touch()
    monkeypatch.setattr(
        "worker.paid_pool_recovery.MUTATION_LOCK_TIMEOUT_SECONDS", 0.01,
    )
    monkeypatch.setattr(
        "worker.paid_pool_recovery.MUTATION_LOCK_POLL_SECONDS", 0.001,
    )
    post = Mock()
    monkeypatch.setattr("worker.paid_pool_recovery.requests.post", post)
    guard = PaidPoolMutationGuard("job-1", "dispatch-1", str(checkpoint))

    try:
        with lock_path.open("a+b") as prior_writer:
            fcntl.flock(prior_writer.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(RuntimeError, match="artifact lock before mutation"):
                guard.prepare()
        assert stage.read_text() == "stage-before"
        assert metadata.read_text() == "metadata-before"
        assert preview.read_text() == "preview-before"
        assert not any(Path(row["backupPath"]).exists() for row in guard.journal["files"])
        post.assert_not_called()
    finally:
        guard.close()


def test_crash_after_forward_write_recovers_before_callback_and_then_cleans(
    tmp_path,
    monkeypatch,
):
    checkpoint, stage, metadata, preview = _artifacts(tmp_path, monkeypatch)
    journal = build_journal(str(checkpoint), str(preview), "dispatch-1")
    for row in journal["files"]:
        Path(row["backupPath"]).write_bytes(Path(row["canonicalPath"]).read_bytes())
        Path(row["canonicalPath"]).write_text("forward")

    calls = []

    def post(url, **_kwargs):
        calls.append(url)
        if url.endswith("/job-started"):
            return _Response({"shouldCancel": False})
        assert stage.read_text() == "stage-before"
        assert metadata.read_text() == "metadata-before"
        assert preview.read_text() == "preview-before"
        assert all(Path(row["backupPath"]).exists() for row in journal["files"])
        return _Response({"status": "ok"})

    monkeypatch.setattr("worker.paid_pool_recovery.requests.post", post)
    result = run_paid_pool_recovery(
        "job-1", "dispatch-1", "22222222-2222-4222-8222-222222222222", journal,
    )

    assert result["status"] == "recovered"
    assert calls[0].endswith("/job-started")
    assert calls[1].endswith("/paid-pool-recovery-complete")
    assert not any(Path(row["backupPath"]).exists() for row in journal["files"])


def test_refenced_old_recovery_cannot_overwrite_a_newer_pool(tmp_path, monkeypatch):
    checkpoint, stage, _metadata, preview = _artifacts(tmp_path, monkeypatch)
    journal = build_journal(str(checkpoint), str(preview), "dispatch-1")
    for row in journal["files"]:
        Path(row["backupPath"]).write_bytes(Path(row["canonicalPath"]).read_bytes())
        Path(row["canonicalPath"]).write_text("newer-paid-pool")

    monkeypatch.setattr(
        "worker.paid_pool_recovery.requests.post",
        Mock(return_value=_Response({"stale": True, "shouldCancel": True})),
    )
    with pytest.raises(PaidPoolOperationFenced):
        run_paid_pool_recovery(
            "job-1", "dispatch-1", "old-recovery-token", journal,
        )

    assert stage.read_text() == "newer-paid-pool"
    assert preview.read_text() == "newer-paid-pool"
    assert all(Path(row["backupPath"]).exists() for row in journal["files"])


def test_recovery_does_not_heartbeat_forever_behind_a_hung_writer_lock(
    tmp_path,
    monkeypatch,
):
    checkpoint, _stage, _metadata, preview = _artifacts(tmp_path, monkeypatch)
    journal = build_journal(str(checkpoint), str(preview), "dispatch-1")
    lock_path = Path(journal["lockPath"])
    lock_path.touch()
    monkeypatch.setattr(
        "worker.paid_pool_recovery.RECOVERY_LOCK_TIMEOUT_SECONDS", 0.01,
    )
    monkeypatch.setattr(
        "worker.paid_pool_recovery.RECOVERY_LOCK_POLL_SECONDS", 0.001,
    )
    post = Mock()
    monkeypatch.setattr("worker.paid_pool_recovery.requests.post", post)

    with lock_path.open("a+b") as original_writer:
        fcntl.flock(original_writer.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(PaidPoolRecoveryRequired, match="original paid-pool writer"):
            run_paid_pool_recovery(
                "job-1", "dispatch-1", "recovery-token", journal,
            )

    post.assert_not_called()


def test_cleanup_failure_after_commit_never_reenables_restore(tmp_path, monkeypatch):
    checkpoint, stage, _metadata, _preview = _artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "worker.paid_pool_recovery.requests.post",
        Mock(return_value=_Response({"prepared": True, "stale": False})),
    )
    guard = PaidPoolMutationGuard("job-1", "dispatch-1", str(checkpoint))
    try:
        guard.prepare()
        stage.write_text("accepted-forward")
        monkeypatch.setattr(
            "worker.paid_pool_recovery.cleanup_journal",
            Mock(side_effect=OSError("unlink denied")),
        )
        guard.commit_and_cleanup()
        guard.restore()
        assert stage.read_text() == "accepted-forward"
    finally:
        guard.close()


def test_lost_completion_response_is_ambiguous_not_refundable(monkeypatch):
    import requests

    from worker.progress import (
        clear_active_dispatch,
        notify_regeneration_complete,
        set_active_dispatch,
    )

    set_active_dispatch("job-1", "dispatch-1")
    monkeypatch.setattr(
        "worker.progress.requests.post",
        Mock(side_effect=requests.ConnectionError("response lost after commit")),
    )
    monkeypatch.setattr("worker.progress.time.sleep", Mock())
    try:
        with pytest.raises(PaidPoolCompletionAmbiguous):
            notify_regeneration_complete("job-1", [{"solution_name": "forward"}])
    finally:
        clear_active_dispatch("job-1")


def test_late_original_completion_rejects_stale_success(monkeypatch):
    from worker.progress import (
        clear_active_dispatch,
        notify_regeneration_complete,
        set_active_dispatch,
    )

    set_active_dispatch("job-1", "dispatch-1")
    monkeypatch.setattr(
        "worker.progress.requests.post",
        Mock(return_value=_Response({"status": "ok", "stale": True})),
    )
    try:
        with pytest.raises(PaidPoolOperationFenced):
            notify_regeneration_complete("job-1", [{"solution_name": "late"}])
    finally:
        clear_active_dispatch("job-1")
