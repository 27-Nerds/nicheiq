#!/usr/bin/env python3
"""Reconcile contradictory idea-check outcomes in registered preview assets.

The default mode is read-only.  ``--apply`` writes a content-addressed immutable
sibling, compare-and-swaps the registered ``JobAsset`` pointer, re-stamps its
publication hash, restores the exact candidate-pool binding, and records the run
in the existing backfill audit ledger.  Filename scans are diagnostic only and
are never an authority for mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from nicheiq.report.idea_validation_block import resolve_idea_validation_outcome

CONTRACT_VERSION = "idea-validation-outcome-v1"
# Same exclusive publication lock used by the commercial-copy migration and shared
# by the JobAsset publication-fence trigger.
MIGRATION_LOCK_KEY = 0x4E495143435237


@dataclass(frozen=True)
class AssetRecord:
    id: int
    job_id: str
    file_path: str
    updated_at: datetime
    candidate_pool_version: int | None


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    raw: bytes
    sha256: str
    inode: int
    size: int
    mtime_ns: int
    mode: int


@dataclass
class Result:
    path: Path
    status: str
    detail: str = ""
    asset: AssetRecord | None = None
    source_sha256: str | None = None
    result_path: Path | None = None
    registered_result_path: str | None = None
    result_sha256: str | None = None
    result_size: int | None = None
    source_snapshot: FileSnapshot | None = None
    audit: dict[str, Any] = field(default_factory=dict)


def is_same_record_contradiction(block: Any) -> bool:
    """The measured OC-1 target; no prose or cross-record inference."""
    if not isinstance(block, dict):
        return False
    outcome = str(block.get("outcome") or "").strip().lower()
    red_team = str(block.get("red_team_verdict") or "").strip().lower()
    return outcome == "worth_testing" and red_team == "killed"


def reconcile_document(document: Any) -> tuple[Any, bool, dict[str, Any]]:
    """Apply the producer's one outcome resolver to one persisted preview document."""
    if not isinstance(document, dict):
        return document, False, {"status": "skipped", "reason": "root is not an object"}
    block = document.get("idea_validation")
    if not is_same_record_contradiction(block):
        return document, False, {"status": "unchanged"}

    assert isinstance(block, dict)  # narrowed by is_same_record_contradiction
    candidate_status = str(block.get("seed_candidate_status") or "active").strip().lower()
    outcome, headline = resolve_idea_validation_outcome(
        idea_name=block.get("idea_name") if isinstance(block.get("idea_name"), str) else None,
        demoted=candidate_status != "active",
        parity_raw=(
            block.get("incumbent_parity")
            if isinstance(block.get("incumbent_parity"), str)
            else None
        ),
        unanchored=bool(block.get("unanchored_hypothesis")),
        red_team_verdict="killed",
        refinement_present=isinstance(block.get("refinement"), dict),
        brief_parity_hit=bool(block.get("original_mechanism_parity")),
    )
    if outcome == "worth_testing":
        # A future precedence change must be deliberate.  Never silently publish a
        # migration result that no longer resolves the contradiction it selected.
        raise RuntimeError(
            "authoritative resolver left a killed worth_testing record contradictory"
        )

    reconciled = deepcopy(document)
    reconciled_block = reconciled["idea_validation"]
    reconciled_block["outcome"] = outcome
    reconciled_block["headline"] = headline
    return (
        reconciled,
        True,
        {
            "status": "changed",
            "before_outcome": "worth_testing",
            "after_outcome": outcome,
            "red_team_verdict": "killed",
        },
    )


def _serialized(document: Any) -> bytes:
    return json.dumps(document, indent=2, ensure_ascii=False, default=str).encode()


def _snapshot(path: Path) -> FileSnapshot:
    raw = path.read_bytes()
    info = path.stat()
    return FileSnapshot(
        path=path,
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        inode=info.st_ino,
        size=info.st_size,
        mtime_ns=info.st_mtime_ns,
        mode=info.st_mode,
    )


def _snapshot_matches(snapshot: FileSnapshot) -> bool:
    try:
        current = snapshot.path.stat()
        return (
            current.st_ino == snapshot.inode
            and current.st_size == snapshot.size
            and current.st_mtime_ns == snapshot.mtime_ns
            and hashlib.sha256(snapshot.path.read_bytes()).hexdigest() == snapshot.sha256
        )
    except OSError:
        return False


def _resolve_registered_path(file_path: str, asset_root: Path) -> Path:
    if not file_path:
        raise ValueError("empty JobAsset.filePath")
    candidate = Path(file_path)
    if ".." in candidate.parts:
        raise ValueError("parent traversal is not allowed")
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (asset_root / candidate).resolve()
    )
    root = asset_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path is outside asset root {root}")
    return resolved


def _immutable_path(record: AssetRecord, source: Path, sha256: str) -> tuple[Path, str]:
    result = source.parent / f".idea-validation-oc1-{record.id}-{sha256[:16]}.json"
    registered = (
        str(result)
        if Path(record.file_path).is_absolute()
        else str(Path(record.file_path).parent / result.name)
    )
    if len(registered) > 500:
        raise ValueError("immutable result path exceeds JobAsset.filePath capacity")
    return result, registered


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_immutable(path: Path, raw: bytes, source: FileSnapshot) -> bool:
    """Create once and reject any content collision at the deterministic path."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, stat.S_IMODE(source.mode))
    except FileExistsError:
        existing = path.lstat()
        if not stat.S_ISREG(existing.st_mode):
            raise RuntimeError(f"immutable result path is not a regular file: {path}")
        read_flags = os.O_RDONLY | os.O_NONBLOCK
        if hasattr(os, "O_NOFOLLOW"):
            read_flags |= os.O_NOFOLLOW
        try:
            existing_descriptor = os.open(path, read_flags)
        except OSError as exc:
            raise RuntimeError(
                f"immutable result path could not be opened safely: {path}"
            ) from exc
        try:
            if not stat.S_ISREG(os.fstat(existing_descriptor).st_mode):
                raise RuntimeError(f"immutable result path is not a regular file: {path}")
            with os.fdopen(existing_descriptor, "rb") as handle:
                existing_raw = handle.read()
                existing_descriptor = -1
        finally:
            if existing_descriptor >= 0:
                os.close(existing_descriptor)
        if hashlib.sha256(existing_raw).hexdigest() != hashlib.sha256(raw).hexdigest():
            raise RuntimeError(f"immutable result collision at {path}")
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copystat(source.path, path, follow_symlinks=True)
        _fsync_directory(path.parent)
        return True
    except Exception:
        path.unlink(missing_ok=True)
        raise


def prepare_registered_asset(
    record: AssetRecord,
    asset_root: Path,
    *,
    write_immutable: bool,
) -> Result:
    try:
        path = _resolve_registered_path(record.file_path, asset_root)
        source = _snapshot(path)
        document = json.loads(source.raw)
        reconciled, changed, audit = reconcile_document(document)
        if not changed:
            status = "skipped" if audit.get("status") == "skipped" else "unchanged"
            return Result(
                path=path,
                status=status,
                detail=str(audit.get("reason") or ""),
                asset=record,
                source_sha256=source.sha256,
                result_path=path,
                registered_result_path=record.file_path,
                result_sha256=source.sha256,
                result_size=source.size,
                source_snapshot=source,
                audit={
                    "idea_validation": audit,
                    "candidatePoolVersion": record.candidate_pool_version,
                },
            )

        result_raw = _serialized(reconciled)
        result_sha = hashlib.sha256(result_raw).hexdigest()
        result_path, registered_path = _immutable_path(record, path, result_sha)
        if write_immutable:
            _write_immutable(result_path, result_raw, source)
        return Result(
            path=path,
            status="changed" if write_immutable else "would-change",
            asset=record,
            source_sha256=source.sha256,
            result_path=result_path,
            registered_result_path=registered_path,
            result_sha256=result_sha,
            result_size=len(result_raw),
            source_snapshot=source,
            audit={
                "idea_validation": audit,
                "candidatePoolVersion": record.candidate_pool_version,
            },
        )
    except Exception as exc:  # one malformed registered asset must be audited, not guessed
        return Result(Path(record.file_path), "skipped", str(exc), asset=record)


class BackfillRepository(Protocol):
    def enumerate_assets(self) -> list[AssetRecord]: ...
    def start_run(self, contract_version: str) -> str: ...
    def commit_asset(self, run_id: str, result: Result) -> Result: ...
    def complete_run(self, run_id: str, counts: dict[str, int]) -> None: ...
    def fail_run(self, run_id: str, error: str) -> None: ...


def run_registered_backfill(
    repository: BackfillRepository,
    asset_root: Path,
    *,
    apply: bool,
) -> list[Result]:
    """Enumerate only registered previews; dry-run performs no repository/file writes."""
    assets = repository.enumerate_assets()
    if not apply:
        return [
            prepare_registered_asset(asset, asset_root, write_immutable=False) for asset in assets
        ]

    run_id = repository.start_run(CONTRACT_VERSION)
    results: list[Result] = []
    try:
        for asset in assets:
            prepared = prepare_registered_asset(asset, asset_root, write_immutable=True)
            results.append(repository.commit_asset(run_id, prepared))
        counts = {
            "authoritative": len(assets),
            "changed": sum(result.status == "changed" for result in results),
            "unchanged": sum(result.status == "unchanged" for result in results),
            "skipped": sum(result.status == "skipped" for result in results),
            "conflict": sum(result.status == "conflict" for result in results),
        }
        repository.complete_run(run_id, counts)
        return results
    except Exception as exc:
        repository.fail_run(run_id, str(exc))
        raise


def local_contradiction_paths(inputs: list[Path]) -> list[Path]:
    """Diagnostic corpus measurement only; never feeds the mutation path."""
    found: list[Path] = []
    for item in inputs:
        candidates = [item] if item.is_file() else sorted(item.rglob("preview_report_*.json"))
        for path in candidates:
            try:
                document = json.loads(path.read_bytes())
                if is_same_record_contradiction(document.get("idea_validation")):
                    found.append(path.resolve())
            except (OSError, ValueError, TypeError):
                continue
    return list(dict.fromkeys(found))


class PostgresBackfillRepository:
    def __init__(self, database_url: str, *, lock: bool):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency diagnostic
            raise RuntimeError("database mode requires psycopg[binary]") from exc
        parsed = urlsplit(database_url)
        pairs = parse_qsl(parsed.query)
        schema = next((value for key, value in pairs if key == "schema"), None)
        libpq_pairs = [(key, value) for key, value in pairs if key != "schema"]
        if schema and not any(key == "options" for key, _value in libpq_pairs):
            libpq_pairs.append(("options", f"-c search_path={schema}"))
        libpq_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(libpq_pairs), parsed.fragment)
        )
        self.connection = psycopg.connect(libpq_url, row_factory=dict_row)
        self.connection.autocommit = True
        self.locked = lock
        if lock:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))

    def close(self) -> None:
        try:
            if self.locked:
                with self.connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))
        finally:
            self.connection.close()

    def enumerate_assets(self) -> list[AssetRecord]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'SELECT "id", "jobId", "filePath", "updatedAt", "candidatePoolVersion" '
                'FROM "JobAsset" WHERE "assetType" = \'PREVIEW_REPORT\' ORDER BY "id"'
            )
            return [
                AssetRecord(
                    id=row["id"],
                    job_id=row["jobId"],
                    file_path=row["filePath"],
                    updated_at=row["updatedAt"],
                    candidate_pool_version=row["candidatePoolVersion"],
                )
                for row in cursor.fetchall()
            ]

    def start_run(self, contract_version: str) -> str:
        run_id = str(uuid.uuid4())
        with self.connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "CommercialCopyBackfillRun" '
                '("id", "contractVersion", "status") VALUES (%s, %s, \'RUNNING\')',
                (run_id, contract_version),
            )
        return run_id

    def _insert_item(self, cursor, run_id: str, result: Result) -> None:
        asset = result.asset
        assert asset is not None
        cursor.execute(
            'INSERT INTO "CommercialCopyBackfillItem" '
            '("runId", "targetKind", "targetId", "jobId", "assetType", "sourcePath", '
            '"resultPath", "sourceSha256", "resultSha256", "status", "reason", '
            '"sectionResults") VALUES '
            "(%s, 'JOB_ASSET', %s, %s, 'PREVIEW_REPORT', %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (
                run_id,
                str(asset.id),
                asset.job_id,
                asset.file_path,
                result.registered_result_path,
                result.source_sha256,
                result.result_sha256,
                result.status,
                result.detail or None,
                json.dumps(result.audit),
            ),
        )

    def _audit_conflict(self, run_id: str, result: Result, detail: str) -> Result:
        audit = deepcopy(result.audit)
        audit["preview_cache"] = "not_invalidated_cas_conflict"
        conflict = Result(
            path=result.path,
            status="conflict",
            detail=detail,
            asset=result.asset,
            source_sha256=result.source_sha256,
            result_path=result.result_path,
            registered_result_path=result.registered_result_path,
            result_sha256=result.result_sha256,
            result_size=result.result_size,
            audit=audit,
        )
        with self.connection.cursor() as cursor:
            self._insert_item(cursor, run_id, conflict)
        return conflict

    def commit_asset(self, run_id: str, result: Result) -> Result:
        asset = result.asset
        if asset is None:
            raise ValueError("registered result is missing its JobAsset record")
        if result.status != "skipped" and (
            result.source_snapshot is None or not _snapshot_matches(result.source_snapshot)
        ):
            return self._audit_conflict(
                run_id, result, "source content changed before JobAsset compare-and-swap"
            )

        self.connection.autocommit = False
        try:
            with self.connection.cursor() as cursor:
                if result.status == "changed":
                    cursor.execute(
                        'UPDATE "JobAsset" SET "filePath" = %s, "fileSizeBytes" = %s '
                        'WHERE "id" = %s AND "filePath" = %s AND "updatedAt" = %s '
                        'AND "candidatePoolVersion" IS NOT DISTINCT FROM %s '
                        'RETURNING "id"',
                        (
                            result.registered_result_path,
                            result.result_size,
                            asset.id,
                            asset.file_path,
                            asset.updated_at,
                            asset.candidate_pool_version,
                        ),
                    )
                else:
                    cursor.execute(
                        'SELECT "id" FROM "JobAsset" WHERE "id" = %s AND "filePath" = %s '
                        'AND "updatedAt" = %s '
                        'AND "candidatePoolVersion" IS NOT DISTINCT FROM %s FOR UPDATE',
                        (
                            asset.id,
                            asset.file_path,
                            asset.updated_at,
                            asset.candidate_pool_version,
                        ),
                    )
                if cursor.fetchone() is None:
                    self.connection.rollback()
                    self.connection.autocommit = True
                    return self._audit_conflict(
                        run_id, result, "JobAsset row changed before compare-and-swap"
                    )

                if result.status == "changed":
                    cursor.execute(
                        'UPDATE "JobAsset" SET "commercialCopyStatus" = \'RECONCILED\', '
                        '"commercialCopySha256" = %s, '
                        '"commercialCopyCheckedAt" = CURRENT_TIMESTAMP WHERE "id" = %s',
                        (result.result_sha256, asset.id),
                    )
                    # Both the path and hash updates trigger a bind to the Job's CURRENT
                    # pool.  This historical prose repair did not mutate candidates, so
                    # restore the artifact's exact pre-migration binding last.
                    cursor.execute(
                        'UPDATE "JobAsset" SET "candidatePoolVersion" = %s WHERE "id" = %s',
                        (asset.candidate_pool_version, asset.id),
                    )
                    # The backend cache reads JobAsset first and rejects cached data when
                    # its registered filePath/hash differs. Stamp this only after the CAS
                    # has succeeded; a conflict leaves the registered pointer unchanged.
                    result.audit["preview_cache"] = (
                        "invalidated_by_registered_path_change"
                    )
                self._insert_item(cursor, run_id, result)
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            raise
        finally:
            self.connection.autocommit = True

    def complete_run(self, run_id: str, counts: dict[str, int]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'UPDATE "CommercialCopyBackfillRun" SET "status" = \'COMPLETED\', '
                '"completedAt" = CURRENT_TIMESTAMP, "authoritativeAssets" = %s, '
                '"assetsChanged" = %s, "assetsUnchanged" = %s, "assetsSkipped" = %s, '
                '"assetsConflicted" = %s WHERE "id" = %s',
                (
                    counts["authoritative"],
                    counts["changed"],
                    counts["unchanged"],
                    counts["skipped"],
                    counts["conflict"],
                    run_id,
                ),
            )

    def fail_run(self, run_id: str, error: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                'UPDATE "CommercialCopyBackfillRun" SET "status" = \'FAILED\', '
                '"completedAt" = CURRENT_TIMESTAMP, "error" = %s WHERE "id" = %s',
                (error, run_id),
            )


def _print_results(results: list[Result], *, apply: bool, local_count: int | None) -> None:
    for result in results:
        asset = result.asset
        prefix = f"asset={asset.id} job={asset.job_id} " if asset else ""
        detail = f": {result.detail}" if result.detail else ""
        print(f"{result.status.upper()} {prefix}{result.path}{detail}")
    matched = sum(result.status in {"would-change", "changed"} for result in results)
    conflicts = sum(result.status == "conflict" for result in results)
    print(
        f"SUMMARY mode={'apply' if apply else 'dry-run'} registered={len(results)} "
        f"matched={matched} conflicts={conflicts}"
        + (f" local={local_count}" if local_count is not None else "")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="Authoritative PostgreSQL registry")
    parser.add_argument("--apply", action="store_true", help="Apply after reviewing dry-run output")
    parser.add_argument(
        "--asset-root",
        type=Path,
        required=True,
        help="Explicit root used to resolve registered relative JobAsset paths",
    )
    parser.add_argument(
        "--local-root",
        action="append",
        type=Path,
        default=[],
        help="Optional diagnostic local corpus count; never used for mutation",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print(
            "ERROR no live JobAsset registry: --database-url is required; no files were changed",
            file=sys.stderr,
        )
        return 2

    repository: PostgresBackfillRepository | None = None
    try:
        # Establish the authoritative registry before any immutable file can be written.
        repository = PostgresBackfillRepository(args.database_url, lock=args.apply)
        results = run_registered_backfill(
            repository,
            args.asset_root,
            apply=args.apply,
        )
    except Exception as exc:
        print(
            f"ERROR registered backfill unavailable: {exc}; no unregistered source was mutated",
            file=sys.stderr,
        )
        return 2
    finally:
        if repository is not None:
            repository.close()

    local_count = len(local_contradiction_paths(args.local_root)) if args.local_root else None
    _print_results(results, apply=args.apply, local_count=local_count)
    return 1 if any(result.status in {"skipped", "conflict"} for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
