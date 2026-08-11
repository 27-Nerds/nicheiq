"""Regression coverage for paying-wallet prose restored from legacy checkpoints."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nicheiq.flows.checkpoint_manager import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointManager,
)
from nicheiq.utils import niche_difficulty

_FIXTURE_PATH = (
    Path(__file__).parents[2] / "fixtures" / "persisted_commercial_prose_51a491dc.json"
)
_NICHE = "Independent veterinary clinics managing medication"


def _fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _checkpoint_from_fixture(folder: Path, material: dict, *, wallet: dict) -> Path:
    folder.mkdir(parents=True)
    metadata = {
        "niche_description": _NICHE,
        "started_at": "2026-08-01T10:41:07",
        "current_stage": 6,
        "completed_stages": ["stage_5_niche_difficulty", "stage_5_6_selection"],
        "completed_stage_numbers": [5],
        "errors": [],
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "niche_wallet_brief": wallet,
        "idea_portfolio_summary": material["idea_portfolio_summary"],
    }
    (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (folder / "stage_5_niche_difficulty.json").write_text(
        json.dumps(material["niche_difficulty_verdict"]), encoding="utf-8"
    )
    return folder


def test_real_51a_paying_checkpoint_is_reconciled_during_hydration(
    tmp_path, sample_research_state
):
    material = _fixture()
    wallet = material["market_reality"]["wallet"]
    folder = _checkpoint_from_fixture(tmp_path / "checkpoint_51a", material, wallet=wallet)
    manager = CheckpointManager(_NICHE, sample_research_state)
    warnings: list[str] = []
    sink_id = niche_difficulty.logger.add(
        lambda message: warnings.append(str(message)), level="WARNING"
    )
    try:
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = tmp_path
            assert manager.load_checkpoint_folder(folder) is True
    finally:
        niche_difficulty.logger.remove(sink_id)

    hydrated_verdict = manager.state.niche_difficulty_verdict
    published = {
        "niche_difficulty_verdict": hydrated_verdict.model_dump(),
        "idea_portfolio_summary": manager.state.idea_portfolio_summary,
    }
    original_narrative = material["niche_difficulty_verdict"]["narrative_summary"]
    original_summary = material["idea_portfolio_summary"]
    expected_commercial_copy = niche_difficulty.paying_wallet_commercial_contract_copy(
        wallet["wallet_class"], wallet["evidence"]
    )

    assert hydrated_verdict.headline == material["niche_difficulty_verdict"]["headline"]
    assert hydrated_verdict.narrative_summary != original_narrative, (
        "HYDRATION_PUBLICATION_GUARD: removing the hydration check must expose the original "
        "contradictory verdict"
    )
    assert original_narrative not in json.dumps(published)
    assert original_summary not in json.dumps(published)
    assert hydrated_verdict.key_strengths[:2] == material["niche_difficulty_verdict"][
        "key_strengths"
    ][:2]
    assert hydrated_verdict.key_strengths == material["niche_difficulty_verdict"]["key_strengths"]
    assert "subscription pricing remains viable" in hydrated_verdict.key_challenges[-1]
    # D1: the contradiction is removed, the run's ANALYSIS is not. Collapsing this 1,715-char
    # analyst narrative to the one sanctioned sentence deleted the paid deliverable along with
    # the defect it was fixing.
    hydrated_summary = manager.state.idea_portfolio_summary
    assert hydrated_summary.endswith(expected_commercial_copy)
    assert hydrated_summary.count(expected_commercial_copy) == 1
    # Assert the PROPERTY, not the disappearance of one string. The previous version of this
    # line pinned `"willingness to pay is generally weak" not in hydrated_summary`, which is
    # why D1 shipped: the same artifact's OTHER contradiction — "pivot toward a free,
    # lead-generation-focused tool" — carries no negative word at all, so removing one literal
    # proved nothing about the rest of the paragraph.
    assert niche_difficulty.paying_wallet_summary_copy_violations(
        hydrated_summary,
        wallet_class=wallet["wallet_class"],
        wallet_evidence=wallet["evidence"],
        expected_copy=expected_commercial_copy,
    ) == []
    assert not niche_difficulty.has_zero_price_prescription(hydrated_summary)
    assert not niche_difficulty.has_negative_niche_wallet_claim(hydrated_summary)
    assert "pivot toward a free" not in hydrated_summary
    assert "Controlled-Substance Reconciliation Ledger" in hydrated_summary
    assert len(hydrated_summary) > len(expected_commercial_copy) + 500
    hydrated_fact_pack = niche_difficulty._persisted_verdict_fact_pack(
        hydrated_verdict,
        wallet_class=wallet["wallet_class"],
        wallet_evidence=wallet["evidence"],
    )
    assert niche_difficulty._commercial_copy_violations(
        hydrated_verdict, hydrated_fact_pack
    ) == []
    assert niche_difficulty.paying_wallet_summary_copy_violations(
        manager.state.idea_portfolio_summary,
        wallet_class=wallet["wallet_class"],
        wallet_evidence=wallet["evidence"],
        expected_copy=expected_commercial_copy,
    ) == []
    assert any("persisted paying-wallet commercial invariant rejected" in item for item in warnings)


def test_non_paying_legacy_checkpoint_prose_passes_through_untouched(
    tmp_path, sample_research_state
):
    material = _fixture()
    wallet = {
        "wallet_class": "free-culture",
        "evidence": "Most established routes are free.",
        "free_density": "high",
    }
    folder = _checkpoint_from_fixture(tmp_path / "checkpoint_non_paying", material, wallet=wallet)
    manager = CheckpointManager(_NICHE, sample_research_state)

    with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_dir = tmp_path
        assert manager.load_checkpoint_folder(folder) is True

    hydrated = manager.state.niche_difficulty_verdict.model_dump(exclude_none=True)
    # The reader-facing monetization line is backfilled on every restore (older checkpoints
    # predate the field); every PROSE field the checkpoint carried is untouched.
    assert set(hydrated) - set(material["niche_difficulty_verdict"]) == {"monetization_guidance"}
    assert hydrated["monetization_guidance"] == niche_difficulty.monetization_guidance(wallet)
    assert {k: v for k, v in hydrated.items() if k != "monetization_guidance"} == material[
        "niche_difficulty_verdict"
    ]
    assert manager.state.idea_portfolio_summary == material["idea_portfolio_summary"]


_OUTPUT_CHECKPOINTS = Path(__file__).parents[3] / "output" / "checkpoints"


def _paying_checkpoint_summaries() -> list[tuple[str, dict, str]]:
    """Every persisted `wallet_class == "paying"` run that carries a portfolio summary."""
    found = []
    for metadata_path in sorted(_OUTPUT_CHECKPOINTS.glob("*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        wallet = metadata.get("niche_wallet_brief") or {}
        summary = (metadata.get("idea_portfolio_summary") or "").strip()
        if (wallet.get("wallet_class") or "").lower() == "paying" and summary:
            found.append((metadata_path.parent.name, wallet, summary))
    return found


@pytest.mark.parametrize(
    "run_name,wallet,summary",
    _paying_checkpoint_summaries(),
    ids=lambda value: value[:48] if isinstance(value, str) else "",
)
def test_every_persisted_paying_run_publishes_without_contradiction(run_name, wallet, summary):
    """D1 over the REAL corpus, not one fixture.

    Asserting the property on a single checkpoint is what let D1 through: the fixture's own
    contradiction was pinned by name while a second real run carried three more, in registers
    no named rule covered. Every paying run in `output/` is checked, and the run's own analysis
    has to survive alongside the sanctioned statement.
    """
    expected = niche_difficulty.paying_wallet_commercial_contract_copy(
        wallet["wallet_class"], wallet.get("evidence")
    )
    assert expected is not None

    published = niche_difficulty.reconcile_persisted_paying_wallet_summary(
        summary, wallet_class=wallet["wallet_class"], wallet_evidence=wallet.get("evidence")
    )

    assert niche_difficulty.paying_wallet_summary_copy_violations(
        published,
        wallet_class=wallet["wallet_class"],
        wallet_evidence=wallet.get("evidence"),
        expected_copy=expected,
    ) == [], run_name
    # The valence-free half of D1: nothing published may RECOMMEND a shape in which this
    # niche's buyers do not pay, whether or not it says anything negative.
    assert not niche_difficulty.has_zero_price_prescription(published), run_name
    assert not niche_difficulty.has_negative_niche_wallet_claim(published), run_name
    assert published.count(expected) == 1, run_name
    # ...and the fix must not be "publish the one sanctioned sentence".
    assert len(published) > len(expected), run_name
