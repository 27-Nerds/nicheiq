"""
Integration tests for CheckpointManager's use of CheckpointValidator.

Tests verify that CheckpointManager correctly delegates validation to
CheckpointValidator and handles validation results appropriately.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.models.research_state import ResearchState
from nicheiq.utils.validation import CheckpointValidator


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
