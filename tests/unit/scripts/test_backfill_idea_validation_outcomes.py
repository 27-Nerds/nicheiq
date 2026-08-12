from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))

from scripts import backfill_idea_validation_outcomes as migration

FIXTURE_PATH = (
    Path(__file__).parents[1] / "report" / "fixtures" / "oc1_historical_contradictions.json"
)


def _fixture_blocks() -> list[dict]:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [deepcopy(fixture["block"]) for fixture in fixtures]


def _record(asset_id: int, relative_path: str, pool_version: int | None = 7):
    return migration.AssetRecord(
        id=asset_id,
        job_id=f"job-{asset_id}",
        file_path=relative_path,
        updated_at=datetime.now(UTC),
        candidate_pool_version=pool_version,
    )


class FakeRepository:
    def __init__(self, assets: list[migration.AssetRecord]):
        self.assets = assets
        self.started = 0
        self.committed: list[migration.Result] = []
        self.completed: dict[str, int] | None = None

    def enumerate_assets(self) -> list[migration.AssetRecord]:
        return self.assets

    def start_run(self, contract_version: str) -> str:
        assert contract_version == migration.CONTRACT_VERSION
        self.started += 1
        return "run-1"

    def commit_asset(self, _run_id: str, result: migration.Result) -> migration.Result:
        self.committed.append(result)
        return result

    def complete_run(self, _run_id: str, counts: dict[str, int]) -> None:
        self.completed = counts

    def fail_run(self, _run_id: str, error: str) -> None:  # pragma: no cover
        raise AssertionError(error)


def _write_registered_assets(tmp_path: Path) -> tuple[list[migration.AssetRecord], list[bytes]]:
    records: list[migration.AssetRecord] = []
    originals: list[bytes] = []
    for index, block in enumerate(_fixture_blocks(), start=1):
        relative = f"checkpoints/registered-{index}.json"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps({"idea_validation": block, "candidate_pool": ["keep"]}).encode()
        path.write_bytes(raw)
        records.append(_record(index, relative, pool_version=10 + index))
        originals.append(raw)
    return records, originals


def test_selector_requires_same_record_and_normalizes_enum_values() -> None:
    assert migration.is_same_record_contradiction(
        {"outcome": " WORTH_TESTING ", "red_team_verdict": " KILLED "}
    )
    assert not migration.is_same_record_contradiction(
        {
            "idea_validation": {"outcome": "worth_testing"},
            "other_idea": {"red_team_verdict": "killed"},
        }
    )


def test_dry_run_counts_two_registered_matches_without_writes(tmp_path: Path) -> None:
    records, originals = _write_registered_assets(tmp_path)
    unrelated = tmp_path / "checkpoints" / "preview_report_unregistered.json"
    unrelated_raw = json.dumps({"idea_validation": _fixture_blocks()[0]}).encode()
    unrelated.write_bytes(unrelated_raw)
    repository = FakeRepository(records)

    results = migration.run_registered_backfill(repository, tmp_path, apply=False)

    assert [result.status for result in results] == ["would-change", "would-change"]
    assert repository.started == 0
    assert repository.committed == []
    assert not list((tmp_path / "checkpoints").glob(".idea-validation-oc1-*.json"))
    for record, original in zip(records, originals, strict=True):
        assert (tmp_path / record.file_path).read_bytes() == original
    assert unrelated.read_bytes() == unrelated_raw


def test_apply_writes_immutable_sibling_audits_and_is_idempotent(tmp_path: Path) -> None:
    records, originals = _write_registered_assets(tmp_path)
    repository = FakeRepository(records)

    first = migration.run_registered_backfill(repository, tmp_path, apply=True)

    assert [result.status for result in first] == ["changed", "changed"]
    assert repository.completed == {
        "authoritative": 2,
        "changed": 2,
        "unchanged": 0,
        "skipped": 0,
        "conflict": 0,
    }
    for record, original, result in zip(records, originals, first, strict=True):
        source = tmp_path / record.file_path
        assert source.read_bytes() == original
        assert result.result_path and result.result_path != source
        assert result.result_path.exists()
        migrated = json.loads(result.result_path.read_text(encoding="utf-8"))
        assert migrated["idea_validation"]["outcome"] == "premise_unproven"
        assert migrated["candidate_pool"] == ["keep"]
        assert result.audit["candidatePoolVersion"] == record.candidate_pool_version
        assert "preview_cache" not in result.audit
        assert result.audit["idea_validation"] == {
            "status": "changed",
            "before_outcome": "worth_testing",
            "after_outcome": "premise_unproven",
            "red_team_verdict": "killed",
        }

    second_records = [
        _record(
            result.asset.id,
            result.registered_result_path,
            pool_version=result.asset.candidate_pool_version,
        )
        for result in first
        if result.asset and result.registered_result_path
    ]
    before = {
        result.result_path: result.result_path.stat() for result in first if result.result_path
    }
    second = migration.run_registered_backfill(FakeRepository(second_records), tmp_path, apply=True)

    assert [result.status for result in second] == ["unchanged", "unchanged"]
    for path, stat in before.items():
        after = path.stat()
        assert (after.st_ino, after.st_size, after.st_mtime_ns) == (
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
        )


def test_existing_immutable_symlink_is_rejected_even_when_target_bytes_match(
    tmp_path: Path,
) -> None:
    records, _originals = _write_registered_assets(tmp_path)
    dry_run = migration.prepare_registered_asset(records[0], tmp_path, write_immutable=False)
    assert dry_run.status == "would-change" and dry_run.result_path

    source_document = json.loads((tmp_path / records[0].file_path).read_bytes())
    reconciled, changed, _audit = migration.reconcile_document(source_document)
    assert changed
    matching_target = tmp_path / "matching-target.json"
    matching_target.write_bytes(migration._serialized(reconciled))
    dry_run.result_path.symlink_to(matching_target)

    result = migration.prepare_registered_asset(records[0], tmp_path, write_immutable=True)

    assert result.status == "skipped"
    assert "not a regular file" in result.detail
    assert dry_run.result_path.is_symlink()
    assert matching_target.read_bytes() == migration._serialized(reconciled)


class RecordingCursor:
    def __init__(self, *, cas_succeeds: bool):
        self.cas_succeeds = cas_succeeds
        self.calls: list[tuple[str, tuple | None]] = []
        self.last_query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.last_query = query
        self.calls.append((query, params))

    def fetchone(self):
        if 'RETURNING "id"' in self.last_query or "FOR UPDATE" in self.last_query:
            return {"id": 1} if self.cas_succeeds else None
        return None


class RecordingConnection:
    def __init__(self, *, cas_succeeds: bool):
        self.autocommit = True
        self.cursor_instance = RecordingCursor(cas_succeeds=cas_succeeds)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _postgres_repository(connection: RecordingConnection):
    repository = object.__new__(migration.PostgresBackfillRepository)
    repository.connection = connection
    return repository


def test_commit_compare_and_swap_restamps_hash_preserves_pool_and_audits(
    tmp_path: Path,
) -> None:
    records, originals = _write_registered_assets(tmp_path)
    prepared = migration.prepare_registered_asset(records[0], tmp_path, write_immutable=True)
    connection = RecordingConnection(cas_succeeds=True)

    committed = _postgres_repository(connection).commit_asset("run-1", prepared)

    assert committed.status == "changed"
    assert (tmp_path / records[0].file_path).read_bytes() == originals[0]
    assert prepared.result_path
    assert hashlib.sha256(prepared.result_path.read_bytes()).hexdigest() == prepared.result_sha256
    calls = connection.cursor_instance.calls
    assert any(
        'SET "filePath" = %s, "fileSizeBytes" = %s' in query
        and params
        == (
            prepared.registered_result_path,
            prepared.result_size,
            records[0].id,
            records[0].file_path,
            records[0].updated_at,
            records[0].candidate_pool_version,
        )
        for query, params in calls
    )
    assert any(
        '"commercialCopySha256" = %s' in query and params == (prepared.result_sha256, records[0].id)
        for query, params in calls
    )
    assert any(
        'SET "candidatePoolVersion" = %s' in query
        and params == (records[0].candidate_pool_version, records[0].id)
        for query, params in calls
    )
    audit_call = next(query_params for query_params in calls if "BackfillItem" in query_params[0])
    audit = json.loads(audit_call[1][-1])
    assert audit["idea_validation"]["after_outcome"] == "premise_unproven"
    assert audit["preview_cache"] == "invalidated_by_registered_path_change"


def test_job_asset_cas_conflict_is_audited_without_source_mutation(tmp_path: Path) -> None:
    records, originals = _write_registered_assets(tmp_path)
    prepared = migration.prepare_registered_asset(records[0], tmp_path, write_immutable=True)
    connection = RecordingConnection(cas_succeeds=False)

    committed = _postgres_repository(connection).commit_asset("run-1", prepared)

    assert committed.status == "conflict"
    assert "JobAsset row changed" in committed.detail
    assert (tmp_path / records[0].file_path).read_bytes() == originals[0]
    audit_call = next(
        query_params
        for query_params in connection.cursor_instance.calls
        if "BackfillItem" in query_params[0]
    )
    assert json.loads(audit_call[1][-1])["preview_cache"] == (
        "not_invalidated_cas_conflict"
    )


def test_no_live_registry_stops_before_any_file_mutation(tmp_path: Path) -> None:
    records, originals = _write_registered_assets(tmp_path)

    exit_code = migration.main(
        ["--apply", "--asset-root", str(tmp_path), "--local-root", str(tmp_path)]
    )

    assert exit_code == 2
    assert not list((tmp_path / "checkpoints").glob(".idea-validation-oc1-*.json"))
    for record, original in zip(records, originals, strict=True):
        assert (tmp_path / record.file_path).read_bytes() == original


def test_cli_requires_explicit_asset_root_even_when_output_env_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", "/ambiguous/output")

    with pytest.raises(SystemExit) as exc:
        migration.main(["--database-url", "postgresql://unused"])

    assert exc.value.code == 2


def test_repo_root_dry_run_uses_explicit_asset_root(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository_root = Path(__file__).parents[3]
    captured: dict[str, object] = {}

    class FakePostgresRepository(FakeRepository):
        def __init__(self, database_url: str, *, lock: bool):
            super().__init__([])
            captured.update(database_url=database_url, lock=lock)

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.chdir(repository_root)
    monkeypatch.setenv("OUTPUT_DIR", "/must/not/be/inferred")
    monkeypatch.setattr(migration, "PostgresBackfillRepository", FakePostgresRepository)

    exit_code = migration.main(
        [
            "--database-url",
            "postgresql://registry",
            "--asset-root",
            str(repository_root),
        ]
    )

    assert exit_code == 0
    assert captured == {
        "database_url": "postgresql://registry",
        "lock": False,
        "closed": True,
    }
    assert "mode=dry-run registered=0 matched=0" in capsys.readouterr().out


def test_api_image_and_gitignore_package_the_manual_runner() -> None:
    repository_root = Path(__file__).parents[3]

    dockerfile = (repository_root / "docker" / "Dockerfile.api").read_text(encoding="utf-8")
    gitignore = (repository_root / ".gitignore").read_text(encoding="utf-8")

    assert (
        "COPY scripts/backfill_idea_validation_outcomes.py "
        "./maintenance/backfill_idea_validation_outcomes.py"
    ) in dockerfile
    assert "!scripts/backfill_idea_validation_outcomes.py" in gitignore
