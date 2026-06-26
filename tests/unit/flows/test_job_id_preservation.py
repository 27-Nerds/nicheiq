"""
Tests covering job_id preservation across resume + cross-job checkpoint fork.

These tests guard against the bug where `state.job_id` was only assigned inside
`stage_1_validate_niche` (skipped on resume), leaving resumed jobs with
`state.job_id=None`. Symptoms included `_None.json` artifact filenames and
broken ChromaDB collection isolation across 6 crew constructors.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from nicheiq.flows.checkpoint_manager import CHECKPOINT_SCHEMA_VERSION, CheckpointManager
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.research_state import ResearchState


NICHE = "AI productivity tools for indie hackers"


def _write_checkpoint(
    folder: Path,
    *,
    metadata: dict,
    stage_files: dict[str, dict] | None = None,
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    # Default to the current schema_version so checkpoints represent up-to-date data; tests
    # exercising drift can pass schema_version explicitly in `metadata`.
    metadata = {"schema_version": CHECKPOINT_SCHEMA_VERSION, **metadata}
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))
    for name, body in (stage_files or {}).items():
        (folder / name).write_text(json.dumps(body, indent=2))
    return folder


def _hash_folder(folder: Path) -> dict[str, str]:
    """Return {relative_path: sha256} for every file in the folder."""
    out: dict[str, str] = {}
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(folder))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class TestConstructorAssignsJobId:
    """Fix #1: ResearchFlow.__init__ must populate state.job_id eagerly."""

    def test_constructor_with_explicit_job_id(self):
        flow = ResearchFlow(niche_description=NICHE, job_id="abc-123")
        assert flow.job_id == "abc-123"
        assert flow.state.job_id == "abc-123"

    def test_constructor_without_job_id_generates_uuid(self):
        flow = ResearchFlow(niche_description=NICHE)
        assert flow.job_id is not None
        assert flow.state.job_id == flow.job_id
        # Verify it looks like a UUID (parses cleanly)
        uuid.UUID(flow.job_id)


class TestResumePreservesJobId:
    """Resume must not clobber the constructor-set job_id."""

    def test_state_job_id_survives_resume(self, checkpoint_temp_dir):
        folder = checkpoint_temp_dir / "checkpoint_ai_productivity_tools_for_indie_hackers_new-job_20260101_120000"
        _write_checkpoint(
            folder,
            metadata={
                "niche_description": NICHE,
                "job_id": "new-job",
                "started_at": "2026-01-01T12:00:00",
                "current_stage": 3,
                "completed_stages": ["stage_1_niche_context"],
                "errors": [],
            },
            stage_files={"stage_1_niche_context.json": {"skipped": True, "reason": "test"}},
        )

        flow = ResearchFlow(niche_description=NICHE, job_id="new-job")
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            mock_settings.checkpoint_auto_cleanup = False
            mock_settings.checkpoint_max_age_days = 0

            assert flow.resume_from_checkpoint(folder) is True

        assert flow.state.job_id == "new-job"


class TestCrossJobFork:
    """Fix #2: cross-job resume forks the source folder, leaving source intact."""

    @pytest.fixture
    def source_checkpoint(self, checkpoint_temp_dir):
        niche_slug = "ai_productivity_tools_for_indie_hackers"
        folder = checkpoint_temp_dir / f"checkpoint_{niche_slug}_old-job_20260101_120000"
        _write_checkpoint(
            folder,
            metadata={
                "niche_description": NICHE,
                "job_id": "old-job",
                "started_at": "2026-01-01T12:00:00",
                "current_stage": 5,
                "completed_stages": ["stage_1_niche_context", "stage_2_social_content"],
                "completed_stage_numbers": [1, 2],
                "errors": [],
            },
            stage_files={
                "stage_1_niche_context.json": {"skipped": True, "reason": "test"},
                "stage_2_social_content.json": {"skipped": True, "reason": "test"},
            },
        )
        return folder

    def test_fork_creates_fresh_folder_and_preserves_source(
        self, checkpoint_temp_dir, source_checkpoint, sample_research_state
    ):
        source_hashes_before = _hash_folder(source_checkpoint)

        manager = CheckpointManager(
            niche_description=NICHE,
            state=sample_research_state,
            job_id="new-job",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            assert manager.load_checkpoint_folder(source_checkpoint) is True

        # checkpoint_folder points at a fresh forked folder, not the source
        assert manager.checkpoint_folder is not None
        assert manager.checkpoint_folder != source_checkpoint
        assert manager.checkpoint_folder.name.startswith(
            "checkpoint_ai_productivity_tools_for_indie_hackers_new-job_"
        )
        assert manager.checkpoint_folder.exists()

        # Source folder is byte-identical to its pre-load state
        assert _hash_folder(source_checkpoint) == source_hashes_before

        # Forked metadata reflects the new ownership
        forked_meta = json.loads((manager.checkpoint_folder / "metadata.json").read_text())
        assert forked_meta["job_id"] == "new-job"
        assert forked_meta["forked_from"] == source_checkpoint.name

    def test_get_completed_stages_reads_forked_metadata(
        self, checkpoint_temp_dir, source_checkpoint, sample_research_state
    ):
        manager = CheckpointManager(
            niche_description=NICHE,
            state=sample_research_state,
            job_id="new-job",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(source_checkpoint)

        # Forked folder carries the source's completed_stages list — resume logic
        # downstream sees the same skip decisions as if loading from source.
        assert manager.get_completed_stages() == [
            "stage_1_niche_context",
            "stage_2_social_content",
        ]

    def test_save_stage_writes_to_forked_folder(
        self, checkpoint_temp_dir, source_checkpoint, sample_research_state
    ):
        source_hashes_before = _hash_folder(source_checkpoint)

        manager = CheckpointManager(
            niche_description=NICHE,
            state=sample_research_state,
            job_id="new-job",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(source_checkpoint)
            manager.save_stage("stage_3_pain_points", {"pain_points": [], "note": "forked write"})

        # New stage file landed in forked folder
        assert (manager.checkpoint_folder / "stage_3_pain_points.json").exists()

        # Source folder untouched (metadata + stage files byte-identical)
        assert _hash_folder(source_checkpoint) == source_hashes_before


class TestSameJobResume:
    """Same-job resume adopts the source folder (no fork)."""

    def test_no_fork_when_job_ids_match(
        self, checkpoint_temp_dir, sample_research_state
    ):
        niche_slug = "ai_productivity_tools_for_indie_hackers"
        folder = checkpoint_temp_dir / f"checkpoint_{niche_slug}_same_20260101_120000"
        _write_checkpoint(
            folder,
            metadata={
                "niche_description": NICHE,
                "job_id": "same",
                "started_at": "2026-01-01T12:00:00",
                "current_stage": 3,
                "completed_stages": ["stage_1_niche_context"],
                "errors": [],
            },
            stage_files={"stage_1_niche_context.json": {"skipped": True, "reason": "test"}},
        )

        manager = CheckpointManager(
            niche_description=NICHE,
            state=sample_research_state,
            job_id="same",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(folder)

        assert manager.checkpoint_folder == folder
        # No sibling folder was forked
        forks = [
            p for p in checkpoint_temp_dir.iterdir()
            if p.is_dir() and p != folder
        ]
        assert forks == []


class TestCrossJobOptIn:
    """find_latest_checkpoint must not adopt another job's checkpoint unless opted in.

    Regression guard for the incident where a worker retry (same job_id, no checkpoint of
    its own after a Stage-1 failure) silently forked an unrelated older job's stale-schema
    checkpoint via the niche-only Tier-2 fallback.
    """

    NICHE_SLUG = "ai_productivity_tools_for_indie_hackers"

    def _other_job_checkpoint(self, checkpoint_temp_dir):
        folder = checkpoint_temp_dir / f"checkpoint_{self.NICHE_SLUG}_other-job_20260101_120000"
        return _write_checkpoint(folder, metadata={
            "niche_description": NICHE, "job_id": "other-job",
            "current_stage": 5, "completed_stages": [], "errors": [],
        })

    def test_worker_retry_does_not_adopt_other_job(self, checkpoint_temp_dir, sample_research_state):
        other = self._other_job_checkpoint(checkpoint_temp_dir)
        manager = CheckpointManager(niche_description=NICHE, state=sample_research_state, job_id="my-job")
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            # Default (worker retry): no own checkpoint -> start fresh, do NOT adopt other-job.
            assert manager.find_latest_checkpoint() is None
            # Opt-in (CLI --resume): the niche-only fallback returns the other-job folder.
            assert manager.find_latest_checkpoint(allow_cross_job=True) == other

    def test_tier1_still_found_with_default(self, checkpoint_temp_dir, sample_research_state):
        own = checkpoint_temp_dir / f"checkpoint_{self.NICHE_SLUG}_my-job_20260101_120000"
        _write_checkpoint(own, metadata={
            "niche_description": NICHE, "job_id": "my-job", "completed_stages": [], "errors": [],
        })
        manager = CheckpointManager(niche_description=NICHE, state=sample_research_state, job_id="my-job")
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            # The job's OWN checkpoint is still found by the job-scoped Tier-1 search.
            assert manager.find_latest_checkpoint() == own


class TestLegacyCheckpointWithoutJobIdInMetadata:
    """Legacy checkpoints (no job_id in metadata) must still load without fork."""

    def test_no_fork_when_metadata_missing_job_id(
        self, checkpoint_temp_dir, sample_research_state
    ):
        niche_slug = "ai_productivity_tools_for_indie_hackers"
        folder = checkpoint_temp_dir / f"checkpoint_{niche_slug}_20260101_120000"
        _write_checkpoint(
            folder,
            metadata={
                "niche_description": NICHE,
                # no job_id field
                "started_at": "2026-01-01T12:00:00",
                "current_stage": 3,
                "completed_stages": ["stage_1_niche_context"],
                "errors": [],
            },
            stage_files={"stage_1_niche_context.json": {"skipped": True, "reason": "test"}},
        )

        manager = CheckpointManager(
            niche_description=NICHE,
            state=sample_research_state,
            job_id="current",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(folder)

        # Legacy checkpoint adopted in place — no fork
        assert manager.checkpoint_folder == folder


class TestMaterializerRefusesWhenJobIdMissing:
    """Fix #3a: materializers must not silently produce `_None.json`."""

    def test_discovery_data_returns_none_without_job_id(self, tmp_path):
        flow = ResearchFlow(niche_description=NICHE, job_id="abc")
        # Force both sources to be missing, simulating a regression path
        flow.job_id = None
        flow.state.job_id = None

        result = flow._materialize_discovery_data(str(tmp_path))
        assert result is None
        # No file should have been created, period — particularly not _None.json
        assert list(tmp_path.glob("discovery_data_*.json")) == []

    def test_preview_report_returns_none_without_job_id(self, tmp_path):
        flow = ResearchFlow(niche_description=NICHE, job_id="abc")
        flow.job_id = None
        flow.state.job_id = None

        result = flow._materialize_preview_report(str(tmp_path))
        assert result is None
        assert list(tmp_path.glob("preview_report_*.json")) == []
