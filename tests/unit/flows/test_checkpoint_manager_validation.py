"""
Integration tests for CheckpointManager's use of CheckpointValidator.

Tests verify that CheckpointManager correctly delegates validation to
CheckpointValidator and handles validation results appropriately.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from nicheiq.flows.checkpoint_manager import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointManager,
    _stage_num_from_filename,
)
from nicheiq.models.research_state import ResearchState
from nicheiq.utils.validation import CheckpointValidator


_REWIND_NICHE = "AI-powered productivity tools"


def _build_checkpoint(folder, *, current_stage, completed_stages, stage_files,
                      schema_version=CHECKPOINT_SCHEMA_VERSION, job_id=None):
    """Write a checkpoint folder with a REAL (loadable) metadata + stage files."""
    folder.mkdir(parents=True, exist_ok=True)
    metadata = {
        "niche_description": _REWIND_NICHE,
        "started_at": "2026-01-01T12:00:00",
        "current_stage": current_stage,
        "completed_stages": list(completed_stages),
        "errors": [],
        "schema_version": schema_version,
    }
    if job_id is not None:
        metadata["job_id"] = job_id
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))
    for name, body in stage_files.items():
        (folder / name).write_text(json.dumps(body, indent=2))
    return folder


class TestReconstructionFailureReset:
    """A stage whose data fails Pydantic reconstruction (schema drift) is cleared and the
    pipeline rewinds to re-run it, instead of silently keeping a poisoned raw dict."""

    def _manager(self, sample_research_state, job_id=None):
        return CheckpointManager(
            niche_description=_REWIND_NICHE, state=sample_research_state, job_id=job_id,
        )

    def test_stage3_mismatch_clears_and_rewinds(self, checkpoint_temp_dir, sample_research_state):
        folder = _build_checkpoint(
            checkpoint_temp_dir / "checkpoint_ai_powered_productivity_tools_j_20260101",
            current_stage=5,
            completed_stages=["stage_3_pain_points"],
            stage_files={"stage_3_pain_points.json": {"bogus": 1}},  # missing required fields
        )
        manager = self._manager(sample_research_state)
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.load_checkpoint_folder(folder) is True
        # Poisoned dict is NOT retained, and progress rewinds to the producing stage (3 < 5).
        assert manager.state.pain_point_analysis is None
        assert manager.state.current_stage == 3

    def test_stage9_mismatch_reruns(self, checkpoint_temp_dir, sample_research_state):
        # Stages >= 6 gate on completed_stages (read from disk), not current_stage — the case
        # the first draft of this fix got wrong.
        folder = _build_checkpoint(
            checkpoint_temp_dir / "checkpoint_ai_powered_productivity_tools_k_20260101",
            current_stage=10,
            completed_stages=["stage_3_pain_points", "stage_9_market_sizing"],
            stage_files={"stage_9_market_sizing.json": {"bogus": 1}},
        )
        manager = self._manager(sample_research_state)
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.load_checkpoint_folder(folder) is True
            completed = manager.get_completed_stages()  # re-reads metadata.json from disk
        assert manager.state.market_sizing is None
        assert manager.state.current_stage == 9
        assert "stage_9_market_sizing" not in completed   # pruned -> will re-run
        assert "stage_3_pain_points" in completed         # earlier stage preserved

    def test_successful_reconstruction_unaffected(self, checkpoint_temp_dir, sample_research_state):
        # Skipped markers + no failing files -> no rewind, current_stage untouched.
        folder = _build_checkpoint(
            checkpoint_temp_dir / "checkpoint_ai_powered_productivity_tools_v_20260101",
            current_stage=5,
            completed_stages=["stage_3_pain_points"],
            stage_files={"stage_3_pain_points.json": {"skipped": True, "reason": "test"}},
        )
        manager = self._manager(sample_research_state)
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.load_checkpoint_folder(folder) is True
            assert manager.get_completed_stages() == ["stage_3_pain_points"]
        assert manager.state.current_stage == 5

    @pytest.mark.parametrize("name,expected", [
        ("stage_3_pain_points.json", 3),
        ("stage_5_3_refinement.json", 5),
        ("stage_6a_seed_expansion.json", 6),
        ("stage_9_market_sizing", 9),
        ("metadata.json", None),
        ("not_a_stage", None),
    ])
    def test_stage_num_derivation(self, name, expected):
        assert _stage_num_from_filename(name) == expected


class TestSchemaVersion:
    """Cross-job adoption of a stale-schema checkpoint is refused; current-version loads."""

    def test_mismatched_version_refuses_cross_job(self, checkpoint_temp_dir, sample_research_state):
        folder = _build_checkpoint(
            checkpoint_temp_dir / "checkpoint_ai_powered_productivity_tools_old-job_20260101",
            current_stage=3, completed_stages=[], stage_files={},
            schema_version=CHECKPOINT_SCHEMA_VERSION - 1, job_id="old-job",
        )
        manager = CheckpointManager(
            niche_description=_REWIND_NICHE, state=sample_research_state, job_id="new-job",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.load_checkpoint_folder(folder) is False

    def test_matching_version_loads(self, checkpoint_temp_dir, sample_research_state):
        folder = _build_checkpoint(
            checkpoint_temp_dir / "checkpoint_ai_powered_productivity_tools_old-job_20260102",
            current_stage=3, completed_stages=[], stage_files={},
            schema_version=CHECKPOINT_SCHEMA_VERSION, job_id="old-job",
        )
        manager = CheckpointManager(
            niche_description=_REWIND_NICHE, state=sample_research_state, job_id="new-job",
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.load_checkpoint_folder(folder) is True  # forks (cross-job, same version)


class TestCheckpointManagerValidatorIntegration:
    """Test CheckpointManager uses CheckpointValidator correctly."""

    def test_checkpoint_manager_creates_validator(self, sample_research_state):
        """Should initialize CheckpointValidator on creation."""
        manager = CheckpointManager(
            niche_description="Test niche",
            state=sample_research_state
        )
        assert manager.validator is not None
        assert isinstance(manager.validator, CheckpointValidator)
    def test_metadata_failure_restores_previous_stage_bytes(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """A False save must not leave the new paid result in the stage file."""
        manager = CheckpointManager(
            niche_description="Test niche",
            state=sample_research_state,
        )
        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir
            assert manager.save_stage("stage_5_3_refinement", {"pool": ["old"]}) is True

            stage_file = manager.checkpoint_folder / "stage_5_3_refinement.json"
            previous_bytes = stage_file.read_bytes()
            with patch.object(
                manager,
                "_update_checkpoint_metadata",
                side_effect=OSError("metadata disk fault"),
            ):
                assert manager.save_stage(
                    "stage_5_3_refinement", {"pool": ["unpaid-new"]}
                ) is False

        assert stage_file.read_bytes() == previous_bytes
        assert manager.last_save_failure_rollback_safe is True

    def test_load_checkpoint_uses_validator_for_metadata(
        self, checkpoint_temp_dir, populated_checkpoint_folder, sample_research_state
    ):
        """Should use validator.validate_metadata_file() when loading checkpoint."""
        manager = CheckpointManager(
            niche_description="AI-powered productivity tools",
            state=sample_research_state
        )

        # Mock validator to track calls
        manager.validator = Mock(spec=CheckpointValidator)
        manager.validator.validate_metadata_file.return_value = (True, {
            "niche_description": "AI-powered productivity tools",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 6,
            "completed_stages": [],
            "errors": []
        })
        manager.validator.validate_stage_file.return_value = True

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(populated_checkpoint_folder)

            # Verify validator was called
            manager.validator.validate_metadata_file.assert_called_once()
            call_args = manager.validator.validate_metadata_file.call_args[0][0]
            assert call_args.name == "metadata.json"

    def test_load_checkpoint_uses_validator_for_stage_files(
        self, checkpoint_temp_dir, populated_checkpoint_folder, sample_research_state
    ):
        """Should use validator.validate_stage_file() for each stage file."""
        manager = CheckpointManager(
            niche_description="AI-powered productivity tools",
            state=sample_research_state
        )

        # Mock validator to track calls
        manager.validator = Mock(spec=CheckpointValidator)
        manager.validator.validate_metadata_file.return_value = (True, {
            "niche_description": "AI-powered productivity tools",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 6,
            "completed_stages": [],
            "errors": []
        })
        manager.validator.validate_stage_file.return_value = True

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            manager.load_checkpoint_folder(populated_checkpoint_folder)

            # Verify stage file validation was called
            assert manager.validator.validate_stage_file.called
            assert manager.validator.validate_stage_file.call_count >= 1

    def test_load_checkpoint_fails_on_invalid_metadata(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should return False when validator rejects metadata."""
        manager = CheckpointManager(
            niche_description="Test niche",
            state=sample_research_state
        )

        # Create checkpoint folder with invalid metadata
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_test_20250115"
        checkpoint_folder.mkdir()

        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump({"invalid": "metadata"}, f)

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is False

    def test_load_checkpoint_skips_corrupted_stage_files(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should skip stage files that fail validation."""
        manager = CheckpointManager(
            niche_description="Test niche",
            state=sample_research_state
        )

        # Create checkpoint with valid metadata and one corrupted stage file
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_test_20250115"
        checkpoint_folder.mkdir()

        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "completed_stages": [],
            "errors": []
        }
        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Create corrupted stage file (empty)
        corrupted_file = checkpoint_folder / "stage_2_social_content.json"
        corrupted_file.touch()

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            # Mock logger to verify warning was logged
            with patch("nicheiq.flows.checkpoint_manager.logger") as mock_logger:
                result = manager.load_checkpoint_folder(checkpoint_folder)

                # Should still succeed (skip corrupted file)
                assert result is True

                # Should have logged warning about skipping corrupted file
                warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
                assert any("Skipping corrupted stage file" in str(call) for call in warning_calls)


class TestCheckpointManagerValidatorErrorHandling:
    """Test error handling when validator encounters issues."""

    def test_handles_validator_exception_gracefully(
        self, checkpoint_temp_dir, populated_checkpoint_folder, sample_research_state
    ):
        """Should handle validator exceptions without crashing."""
        manager = CheckpointManager(
            niche_description="AI-powered productivity tools",
            state=sample_research_state
        )

        # Mock validator to raise exception
        manager.validator = Mock(spec=CheckpointValidator)
        manager.validator.validate_metadata_file.side_effect = Exception("Validator error")

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            result = manager.load_checkpoint_folder(populated_checkpoint_folder)
            assert result is False

    def test_logs_validation_failures(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should log specific error messages from validator."""
        manager = CheckpointManager(
            niche_description="Test niche",
            state=sample_research_state
        )

        # Create checkpoint with invalid metadata
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_test_20250115"
        checkpoint_folder.mkdir()

        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump({"niche_description": "Wrong niche"}, f)  # Missing required fields

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            # The validator will log errors internally
            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is False


class TestCheckpointManagerNicheValidation:
    """Test niche description matching (non-validator responsibility)."""

    def test_rejects_mismatched_niche(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should reject checkpoint with different niche description."""
        manager = CheckpointManager(
            niche_description="Different niche",
            state=sample_research_state
        )

        # Create checkpoint with different niche
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_other_20250115"
        checkpoint_folder.mkdir()

        metadata = {
            "niche_description": "Original niche",  # Different from manager's niche
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "completed_stages": [],
            "errors": []
        }
        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is False

    def test_accepts_matching_niche(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should accept checkpoint with matching niche description."""
        niche = "AI-powered productivity tools"
        manager = CheckpointManager(
            niche_description=niche,
            state=sample_research_state
        )

        # Create checkpoint with matching niche
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_ai_20250115"
        checkpoint_folder.mkdir()

        metadata = {
            "niche_description": niche,  # Matches manager's niche
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "completed_stages": [],
            "errors": []
        }
        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is True


class TestCheckpointManagerEndToEnd:
    """End-to-end tests for checkpoint validation workflow."""

    def test_full_checkpoint_load_workflow(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should complete full checkpoint load workflow with validation."""
        niche = "AI productivity tools"
        manager = CheckpointManager(
            niche_description=niche,
            state=sample_research_state
        )

        # Create complete valid checkpoint
        checkpoint_folder = checkpoint_temp_dir / "checkpoint_ai_20250115_103000"
        checkpoint_folder.mkdir()

        metadata = {
            "niche_description": niche,
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 6,
            "completed_stages": ["stage_2_social_content", "stage_3_pain_points"],
            "errors": []
        }
        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Create valid stage files
        stage_data = {"test": "data"}
        stage_files = ["stage_2_social_content.json", "stage_3_pain_points.json"]
        for filename in stage_files:
            stage_file = checkpoint_folder / filename
            with open(stage_file, "w") as f:
                json.dump(stage_data, f)

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is True
            assert manager.checkpoint_folder == checkpoint_folder

    def test_partial_checkpoint_with_missing_stage_files(
        self, checkpoint_temp_dir, sample_research_state
    ):
        """Should handle checkpoint with some missing stage files."""
        niche = "Test niche"
        manager = CheckpointManager(
            niche_description=niche,
            state=sample_research_state
        )

        checkpoint_folder = checkpoint_temp_dir / "checkpoint_test_20250115"
        checkpoint_folder.mkdir()

        metadata = {
            "niche_description": niche,
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 6,
            "completed_stages": ["stage_2_social_content", "stage_3_pain_points"],
            "errors": []
        }
        metadata_file = checkpoint_folder / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Only create one stage file (other is missing)
        stage_file = checkpoint_folder / "stage_2_social_content.json"
        with open(stage_file, "w") as f:
            json.dump({"test": "data"}, f)

        with patch("nicheiq.flows.checkpoint_manager.settings") as mock_settings:
            mock_settings.checkpoint_enabled = True
            mock_settings.checkpoint_dir = checkpoint_temp_dir

            # Should still succeed (missing files are optional)
            result = manager.load_checkpoint_folder(checkpoint_folder)
            assert result is True
