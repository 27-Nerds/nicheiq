from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))

from scripts import backfill_paying_wallet_assets as migration
from tests.unit.test_niche_difficulty import PAYING_WALLET_COMMERCIAL_ATTACKS

SAFE_COPY = (
    "Buyers in this niche demonstrably pay for tooling: willingness to pay is not the "
    "primary risk. Thin early signal; Deep Research validates."
)


def _asset(*, wallet_class: str = "paying", malformed_verdict: bool = False) -> dict:
    verdict: dict = {
        "difficulty_level": "medium",
        "software_addressability": 0.72,
        "headline": "Software Fit: Strong",
        "narrative_summary": "Avoid subscription pricing because willingness to pay is weak.",
        "key_challenges": ["Build only a free tool."],
        "key_strengths": ["Known buyers already purchase tools."],
        "unknown_verdict_field": {"keep": True},
    }
    if malformed_verdict:
        verdict["software_addressability"] = 9
    return {
        "niche": "Independent veterinary clinics managing medication",
        "market_reality": {
            "wallet": {"wallet_class": wallet_class, "evidence": "$99-399/mo incumbents"}
        },
        "niche_difficulty_verdict": verdict,
        "idea_portfolio_summary": "Use only a free tool because subscription pricing is not viable.",
        "unknown_root_field": {"keep": [1, 2, 3]},
    }


class FakeRepository:
    def __init__(self, assets: list[migration.AssetRecord]):
        self.assets = assets
        self.committed: list[migration.Result] = []
        self.completed: tuple[dict[str, int], dict[str, int]] | None = None
        self.chat_eligible_jobs: set[str] = set()

    def start_run(self, _contract_version: str) -> str:
        return "run-1"

    def enumerate_assets(self) -> list[migration.AssetRecord]:
        return self.assets

    def commit_asset(self, _run_id: str, result: migration.Result) -> migration.Result:
        self.committed.append(result)
        return result

    def reconcile_chat(self, _run_id, _replacements, _safe_copy, eligible_job_ids):
        self.chat_eligible_jobs = eligible_job_ids
        return {"changed": 0, "unchanged": 0, "conflict": 0}

    def complete_run(self, _run_id, counts, chat_counts) -> None:
        self.completed = counts, chat_counts

    def fail_run(self, _run_id, _error) -> None:  # pragma: no cover - failure assertion aid
        raise AssertionError("authoritative run unexpectedly failed")


def _record(asset_id: int, path: Path, asset_type: str = "PREVIEW_REPORT") -> migration.AssetRecord:
    return migration.AssetRecord(
        id=asset_id,
        job_id=f"job-{asset_id}",
        asset_type=asset_type,
        file_path=str(path),
        updated_at=datetime.now(UTC),
    )


def test_authoritative_run_enumerates_job_assets_not_filename_globs(tmp_path: Path) -> None:
    registered = tmp_path / "arbitrary-authoritative-name.json"
    unregistered = tmp_path / "preview_report_looks-discoverable.json"
    registered.write_text(json.dumps(_asset()), encoding="utf-8")
    unregistered_bytes = json.dumps(_asset()).encode()
    unregistered.write_bytes(unregistered_bytes)

    repository = FakeRepository([_record(7, registered)])
    results, _ = migration.run_authoritative_backfill(repository, tmp_path)

    assert len(results) == 1
    assert results[0].asset and results[0].asset.id == 7
    assert results[0].status == "changed"
    assert results[0].result_path != registered
    assert unregistered.read_bytes() == unregistered_bytes
    assert repository.completed and repository.completed[0]["authoritative"] == 1
    assert repository.chat_eligible_jobs == {"job-7"}


def test_malformed_verdict_does_not_block_valid_summary(tmp_path: Path) -> None:
    path = tmp_path / "preview_report_bad-verdict.json"
    original = _asset(malformed_verdict=True)
    path.write_text(json.dumps(original), encoding="utf-8")

    result = migration.prepare_registered_asset(_record(10, path), tmp_path)
    assert result.result_path
    reconciled = json.loads(result.result_path.read_text(encoding="utf-8"))

    assert result.status == "partial"
    assert result.sections["niche_difficulty_verdict"].status == "invalid"
    assert result.sections["idea_portfolio_summary"].status == "changed"
    assert reconciled["niche_difficulty_verdict"] == original["niche_difficulty_verdict"]
    assert reconciled["idea_portfolio_summary"] == SAFE_COPY
    assert reconciled["unknown_root_field"] == original["unknown_root_field"]
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_concurrent_writer_wins_and_migration_never_clobbers_source(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text(json.dumps(_asset()), encoding="utf-8")
    prepared = migration.prepare_registered_asset(_record(8, source, "REPORT_JSON"), tmp_path)
    assert prepared.status == "changed"
    assert prepared.result_path and prepared.result_path.exists()

    writer_bytes = b'{"newer_worker_write": true}'
    source.write_bytes(writer_bytes)

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Connection:
        autocommit = True

        def cursor(self):
            return Cursor()

    repository = object.__new__(migration.PostgresBackfillRepository)
    repository.connection = Connection()
    audited: list[str] = []
    repository._insert_item = lambda _cursor, _run, _result, status: audited.append(status)

    committed = repository.commit_asset("run-1", prepared)

    assert committed.status == "conflict"
    assert source.read_bytes() == writer_bytes
    assert audited == ["conflict"]


def test_second_pass_is_idempotent_on_immutable_reconciled_asset(tmp_path: Path) -> None:
    source = tmp_path / "report.json"
    source.write_text(json.dumps(_asset()), encoding="utf-8")
    first = migration.prepare_registered_asset(_record(9, source, "REPORT_JSON"), tmp_path)
    assert first.status == "changed" and first.result_path
    before = first.result_path.stat()

    second = migration.prepare_registered_asset(_record(9, first.result_path, "REPORT_JSON"), tmp_path)

    after = first.result_path.stat()
    assert second.status == "unchanged"
    assert second.result_path == first.result_path
    assert (before.st_ino, before.st_mtime_ns, before.st_size) == (
        after.st_ino,
        after.st_mtime_ns,
        after.st_size,
    )


def test_backfill_preserves_specific_compliant_headline(tmp_path: Path) -> None:
    source = tmp_path / "preview_report_specific.json"
    document = _asset()
    specific_headline = (
        "Software Fit: Strong — automating inventory and controlled substance compliance"
    )
    document["niche_difficulty_verdict"]["headline"] = specific_headline
    source.write_text(json.dumps(document), encoding="utf-8")

    result = migration.prepare_registered_asset(_record(14, source), tmp_path)

    assert result.status == "changed"
    assert result.result_path
    reconciled = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert reconciled["niche_difficulty_verdict"]["headline"] == specific_headline


def test_local_backfill_restores_generic_overwrite_from_same_job_checkpoint(
    tmp_path: Path,
) -> None:
    job_id = "51a491dc-c095-4e21-befb-5cadf540629a"
    checkpoints = tmp_path / "output" / "checkpoints"
    source_dir = checkpoints / f"checkpoint_veterinary_clinics_{job_id}_20260801_104107"
    source_dir.mkdir(parents=True)

    source_document = _asset()
    source_verdict = source_document["niche_difficulty_verdict"]
    source_verdict["headline"] = (
        "Software Fit: Strong — automating inventory and controlled substance compliance"
    )
    source_verdict["key_strengths"][0] = (
        "Controlled-substance reconciliation is a concrete workflow this product can own."
    )
    (source_dir / "stage_5_niche_difficulty.json").write_text(
        json.dumps(source_verdict), encoding="utf-8"
    )

    preview = checkpoints / f"preview_report_{job_id}.json"
    damaged = deepcopy(source_document)
    damaged["niche_difficulty_verdict"]["headline"] = (
        "Software Fit: Strong: a tool can directly own these pains"
    )
    damaged["niche_difficulty_verdict"]["key_strengths"][0] = (
        "Most pains are workflow or data problems a tool can directly own."
    )
    preview.write_text(json.dumps(damaged), encoding="utf-8")

    result = migration.backfill(preview, dry_run=False)
    reconciled = json.loads(preview.read_text(encoding="utf-8"))
    verdict = reconciled["niche_difficulty_verdict"]

    assert result.status == "changed"
    assert verdict["headline"] == source_verdict["headline"]
    assert verdict["key_strengths"][0] == source_verdict["key_strengths"][0]
    assert "avoid subscription pricing" not in verdict["narrative_summary"].lower()
    assert "build only a free tool" not in " ".join(verdict["key_challenges"]).lower()


def test_backfill_repairs_double_colon_when_preserved_source_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "preview_report_51a491dc-c095-4e21-befb-5cadf540629a.json"
    document = _asset()
    document["niche_difficulty_verdict"]["headline"] = (
        "Software Fit: Strong: a tool can directly own these pains"
    )
    path.write_text(json.dumps(document), encoding="utf-8")

    result = migration.backfill(path, dry_run=False)
    reconciled = json.loads(path.read_text(encoding="utf-8"))

    assert result.status == "changed"
    assert reconciled["niche_difficulty_verdict"]["headline"] == (
        "Software Fit: Strong. A tool can directly own these pains"
    )


def test_unknown_wallet_does_not_silently_skip_double_colon_repair(tmp_path: Path) -> None:
    path = tmp_path / "preview_report_unknown-wallet.json"
    document = _asset()
    document.pop("market_reality")
    document["niche_difficulty_verdict"]["headline"] = (
        "Software Fit: Strong: a tool can directly own these pains"
    )
    path.write_text(json.dumps(document), encoding="utf-8")

    result = migration.backfill(path, dry_run=False)
    reconciled = json.loads(path.read_text(encoding="utf-8"))

    assert result.status == "changed"
    assert result.sections["wallet"].status == "unknown"
    assert reconciled["niche_difficulty_verdict"]["headline"] == (
        "Software Fit: Strong. A tool can directly own these pains"
    )


def test_non_paying_asset_is_byte_mode_and_inode_pass_through(tmp_path: Path) -> None:
    path = tmp_path / "final_report_non-paying.json"
    raw = (json.dumps(_asset(wallet_class="free-culture"), separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    path.chmod(0o640)
    before = path.stat()

    result = migration.backfill(path, dry_run=False)
    after = path.stat()

    assert result.status == "unchanged"
    assert path.read_bytes() == raw
    assert stat_mode(after.st_mode) == 0o640
    assert after.st_ino == before.st_ino

    legacy_path = tmp_path / "preview_report_without-wallet.json"
    legacy_raw = b'{"niche":"legacy preview","unknown":true}\n'
    legacy_path.write_bytes(legacy_raw)
    legacy_before = legacy_path.stat()

    legacy_result = migration.backfill(legacy_path, dry_run=False)

    assert legacy_result.status == "skipped"
    assert legacy_path.read_bytes() == legacy_raw
    assert legacy_path.stat().st_ino == legacy_before.st_ino


@pytest.mark.parametrize(
    "mutate, expected_wallet_status",
    [
        (lambda asset: asset.pop("market_reality"), "unknown"),
        (lambda asset: asset["market_reality"].pop("wallet"), "unknown"),
        (
            lambda asset: asset["market_reality"]["wallet"].update(
                {"wallet_class": "unexpected-wallet"}
            ),
            "invalid",
        ),
        (
            lambda asset: asset["market_reality"]["wallet"].update(
                {"wallet_class": "paying", "evidence": ""}
            ),
            "unknown",
        ),
    ],
)
def test_unknown_wallet_schema_is_quarantined_not_not_applicable(
    tmp_path: Path, mutate, expected_wallet_status: str
) -> None:
    path = tmp_path / "unknown-wallet.json"
    document = _asset()
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")

    result = migration.prepare_registered_asset(_record(11, path), tmp_path)

    assert result.status == "skipped"
    assert result.status != "not_paying"
    assert result.sections["wallet"].status == expected_wallet_status


@pytest.mark.parametrize("wallet_class", ["mixed", "free-culture"])
def test_only_proven_non_paying_wallet_classes_are_not_applicable(
    tmp_path: Path, wallet_class: str
) -> None:
    path = tmp_path / f"{wallet_class}.json"
    path.write_text(json.dumps(_asset(wallet_class=wallet_class)), encoding="utf-8")

    result = migration.prepare_registered_asset(_record(12, path), tmp_path)

    assert result.status == "not_paying"
    assert result.sections["wallet"].status == "not_paying"


def test_proven_non_paying_job_is_included_in_historic_chat_audit(tmp_path: Path) -> None:
    path = tmp_path / "non-paying.json"
    path.write_text(json.dumps(_asset(wallet_class="free-culture")), encoding="utf-8")
    repository = FakeRepository([_record(13, path)])

    results, _ = migration.run_authoritative_backfill(repository, tmp_path)

    assert results[0].status == "not_paying"
    assert repository.chat_eligible_jobs == {"job-13"}


def test_historic_assistant_copy_uses_python_replacements_and_preserves_other_paragraphs() -> None:
    legacy_summary = "Use only a free tool because subscription pricing is not viable."
    content = f"The strongest idea is the inventory workflow.\n\n{legacy_summary}\n\nAsk me what to compare."

    reconciled = migration._reconcile_chat_content(
        content,
        ((legacy_summary, SAFE_COPY),),
        SAFE_COPY,
    )

    assert "inventory workflow" in reconciled
    assert "Ask me what to compare" in reconciled
    assert legacy_summary not in reconciled
    assert reconciled.count(SAFE_COPY) == 1


def test_historic_chat_cas_conflict_fails_the_mandatory_runner(tmp_path: Path) -> None:
    class ChatConflictRepository(FakeRepository):
        failure = ""

        def reconcile_chat(self, _run_id, _replacements, _safe_copy, _eligible_job_ids):
            return {"changed": 0, "unchanged": 0, "conflict": 1}

        def fail_run(self, _run_id, error) -> None:
            self.failure = error

    repository = ChatConflictRepository([])

    with pytest.raises(RuntimeError, match="historic chat reconciliation"):
        migration.run_authoritative_backfill(repository, tmp_path)

    assert "1 concurrent conflict" in repository.failure


def stat_mode(mode: int) -> int:
    return mode & 0o7777


@pytest.mark.parametrize(
    "label,attack", sorted(PAYING_WALLET_COMMERCIAL_ATTACKS.items())
)
def test_adversarial_commercial_paraphrase_is_removed_from_historic_chat(
    label: str, attack: str
) -> None:
    """Chat repair used to gate on the bypassable forbidden-phrase list alone.

    Every paraphrase in the corpus survived it verbatim, so an assistant message kept
    contradicting the paying-wallet card it was written about.
    """
    content = (
        "The strongest idea is the inventory workflow.\n\n"
        f"{attack}\n\n"
        "Ask me what to compare."
    )

    reconciled = migration._reconcile_chat_content(content, (), SAFE_COPY)

    assert attack not in reconciled, label
    assert "The strongest idea is the inventory workflow." in reconciled
    assert "Ask me what to compare." in reconciled
    assert reconciled.count(SAFE_COPY) == 1


def test_chat_repair_preserves_sanctioned_and_non_commercial_paragraphs() -> None:
    content = (
        "The strongest idea is the inventory workflow.\n\n"
        f"{SAFE_COPY}\n\n"
        "Ask me what to compare."
    )

    assert migration._reconcile_chat_content(content, (), SAFE_COPY) == content


def test_local_sweep_covers_job_reports_and_stage_five_checkpoints(tmp_path: Path) -> None:
    """The earlier sweep globbed report filenames only, so two corpus shapes went unscanned."""
    (tmp_path / "output" / "jobs" / "abc").mkdir(parents=True)
    (tmp_path / "output" / "checkpoints" / "checkpoint_x").mkdir(parents=True)
    expected = {
        tmp_path / "output" / "preview_report_a.json",
        tmp_path / "output" / "final_report_b.json",
        tmp_path / "output" / "jobs" / "abc" / "report.json",
        tmp_path / "output" / "checkpoints" / "checkpoint_x" / "stage_5_niche_difficulty.json",
    }
    for path in expected:
        path.write_text("{}", encoding="utf-8")
    (tmp_path / "output" / "checkpoints" / "checkpoint_x" / "metadata.json").write_text(
        "{}", encoding="utf-8"
    )

    assert set(migration._asset_paths([tmp_path])) == {path.resolve() for path in expected}


def _stage_5_checkpoint(tmp_path: Path, wallet_class: str = "paying") -> Path:
    run = tmp_path / "output" / "checkpoints" / (
        "checkpoint_freight_8d7fd414-f624-4e84-814c-ec5d7d56ae16_20260710_211026"
    )
    run.mkdir(parents=True)
    (run / "metadata.json").write_text(
        json.dumps(
            {
                "niche_wallet_brief": {
                    "wallet_class": wallet_class,
                    "evidence": "Truckstop $42-159/mo",
                }
            }
        ),
        encoding="utf-8",
    )
    verdict = _asset()["niche_difficulty_verdict"]
    verdict["headline"] = "Software Fit: Strong — Tools can directly own core dispatch pains"
    verdict["narrative_summary"] = (
        "Most products in this niche are used episodically, so one-time purchases or "
        "usage-based pricing may be more suitable than subscriptions."
    )
    verdict["key_challenges"] = [
        "Most pains are workflow or data problems a tool can directly own."
    ]
    path = run / "stage_5_niche_difficulty.json"
    path.write_text(json.dumps(verdict), encoding="utf-8")
    return path


def test_stage_five_checkpoint_is_classified_from_run_metadata_and_repaired(
    tmp_path: Path,
) -> None:
    """A bare verdict carries no wallet block; its run's own probe is the authority."""
    path = _stage_5_checkpoint(tmp_path)

    result = migration.backfill(path, dry_run=False)
    repaired = json.loads(path.read_text(encoding="utf-8"))

    assert result.status == "changed"
    assert result.sections["wallet"].status == "paying"
    assert "than subscriptions" not in repaired["narrative_summary"]
    assert repaired["headline"] == (
        "Software Fit: Strong — Tools can directly own core dispatch pains"
    )
    assert any("demonstrably pay for tooling" in point for point in repaired["key_strengths"])
    assert migration.backfill(path, dry_run=False).status == "unchanged"


def test_authoritative_wallet_rescues_an_asset_with_no_embedded_wallet_block(
    tmp_path: Path,
) -> None:
    """41 corpus assets were skipped forever because they never persisted market_reality."""
    job_id = "8d7fd414-f624-4e84-814c-ec5d7d56ae16"
    _stage_5_checkpoint(tmp_path)
    path = tmp_path / "output" / "jobs" / job_id / "report.json"
    path.parent.mkdir(parents=True)
    document = _asset()
    document.pop("market_reality")
    path.write_text(json.dumps(document), encoding="utf-8")

    result = migration.backfill(path, dry_run=False)

    assert result.status == "changed"
    assert result.sections["wallet"].status == "paying"
    reconciled = json.loads(path.read_text(encoding="utf-8"))
    assert "avoid subscription pricing" not in (
        reconciled["niche_difficulty_verdict"]["narrative_summary"].lower()
    )


def test_disagreeing_source_checkpoints_stay_unattributable(tmp_path: Path) -> None:
    """Identical re-runs agree, so file count is not the test; genuine disagreement is."""
    job_id = "51a491dc-c095-4e21-befb-5cadf540629a"
    checkpoints = tmp_path / "output" / "checkpoints"
    verdict = _asset()["niche_difficulty_verdict"]
    verdict["headline"] = "Software Fit: Strong — automating controlled substance compliance"
    for index in range(2):
        run = checkpoints / f"checkpoint_vet_{job_id}_2026080{index}_104107"
        run.mkdir(parents=True)
        (run / "stage_5_niche_difficulty.json").write_text(
            json.dumps(verdict), encoding="utf-8"
        )
    preview = checkpoints / f"preview_report_{job_id}.json"
    preview.write_text("{}", encoding="utf-8")

    preserved = migration._preserved_source_verdict(preview)
    assert preserved is not None and preserved.headline == verdict["headline"]

    divergent = dict(verdict, headline="Software Fit: Strong — a different run entirely")
    (checkpoints / f"checkpoint_vet_{job_id}_20260802_104107").mkdir(parents=True)
    (
        checkpoints
        / f"checkpoint_vet_{job_id}_20260802_104107"
        / "stage_5_niche_difficulty.json"
    ).write_text(json.dumps(divergent), encoding="utf-8")

    assert migration._preserved_source_verdict(preview) is None


def test_dropped_verdict_statement_never_rewrites_a_surviving_one() -> None:
    """These pairs are applied to historic chat, so index-wise pairing corrupts live prose."""
    before = {"key_challenges": ["off contract", "kept one", "kept two"]}
    after = {"key_challenges": ["kept one", "kept two"]}

    assert migration._verdict_string_replacements(before, after) == [("off contract", "")]
