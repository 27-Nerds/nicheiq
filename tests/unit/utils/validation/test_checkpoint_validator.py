"""
Comprehensive unit tests for CheckpointValidator.

Tests cover:
1. Metadata validation (schema, types, ranges)
2. Stage file validation (existence, corruption, JSON format)
3. Combined metadata file validation
4. Edge cases and error handling
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from nicheiq.utils.validation import CheckpointValidator


class TestCheckpointValidatorInit:
    """Test CheckpointValidator initialization."""

    def test_init_creates_validator(self):
        """Should successfully create validator instance."""
        validator = CheckpointValidator()
        assert validator is not None

    def test_required_fields_constant(self):
        """Should define required metadata fields."""
        validator = CheckpointValidator()
        assert validator.REQUIRED_METADATA_FIELDS == [
            "niche_description",
            "started_at",
            "current_stage"
        ]

    def test_valid_stage_range_constant(self):
        """Should define valid stage range (1-10)."""
        validator = CheckpointValidator()
        assert validator.VALID_STAGE_RANGE == (1, 10)


class TestMetadataValidation:
    """Test validate_metadata() method."""

    def test_valid_metadata_passes(self, valid_checkpoint_metadata):
        """Should accept valid metadata with all required fields."""
        validator = CheckpointValidator()
        result = validator.validate_metadata(valid_checkpoint_metadata)
        assert result is True

    def test_valid_metadata_minimal_fields(self):
        """Should accept metadata with only required fields."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    def test_valid_metadata_with_optional_fields(self):
        """Should accept metadata with optional fields."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "completed_stages": ["stage_1", "stage_2"],
            "errors": ["error1"],
            "environment": {"python_version": "3.11.0"}
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    # Missing field tests
    def test_missing_niche_description_fails(self):
        """Should reject metadata missing niche_description."""
        validator = CheckpointValidator()
        metadata = {
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    def test_missing_started_at_fails(self):
        """Should reject metadata missing started_at."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "current_stage": 5
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    def test_missing_current_stage_fails(self):
        """Should reject metadata missing current_stage."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00"
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    # Type validation tests
    def test_niche_description_wrong_type_fails(self):
        """Should reject non-string niche_description."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": 12345,  # Should be string
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    def test_current_stage_wrong_type_fails(self):
        """Should reject non-numeric current_stage."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": "invalid"  # Should be numeric
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    def test_current_stage_accepts_float(self):
        """Should accept float current_stage (for sub-stages like 8.5)."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 8.5  # Decimal sub-stage
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    def test_completed_stages_wrong_type_fails(self):
        """Should reject non-list completed_stages."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "completed_stages": "invalid"  # Should be list
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    def test_errors_wrong_type_fails(self):
        """Should reject non-list errors field."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "errors": "invalid"  # Should be list
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    # Stage range validation tests
    @pytest.mark.parametrize("stage", [1, 2, 5, 8, 10])
    def test_valid_stage_range_passes(self, stage):
        """Should accept current_stage within valid range (1-10)."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": stage
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    @pytest.mark.parametrize("stage", [0, -1, 11, 99, 100])
    def test_invalid_stage_range_fails(self, stage):
        """Should reject current_stage outside valid range (1-10)."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": stage
        }
        result = validator.validate_metadata(metadata)
        assert result is False

    @pytest.mark.parametrize("stage", [8.5, 8.75, 9.5, 9.75])
    def test_decimal_substages_pass(self, stage):
        """Should accept decimal sub-stages (8.5, 8.75, 9.5, 9.75)."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": stage
        }
        result = validator.validate_metadata(metadata)
        assert result is True


class TestStageFileValidation:
    """Test validate_stage_file() method."""

    def test_valid_stage_file_dict_passes(self, checkpoint_temp_dir, valid_stage_data_dict):
        """Should accept valid stage file with dict data."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "stage_6_pain_points.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(valid_stage_data_dict, f)

        result = validator.validate_stage_file(stage_file)
        assert result is True

    def test_valid_stage_file_list_passes(self, checkpoint_temp_dir, valid_stage_data_list):
        """Should accept valid stage file with list data."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "stage_9_keywords.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(valid_stage_data_list, f)

        result = validator.validate_stage_file(stage_file)
        assert result is True

    def test_nonexistent_file_fails(self, checkpoint_temp_dir):
        """Should reject non-existent stage file."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "nonexistent.json"

        result = validator.validate_stage_file(stage_file)
        assert result is False

    def test_empty_file_fails(self, checkpoint_temp_dir):
        """Should reject empty (corrupted) stage file."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "empty.json"
        stage_file.touch()  # Create empty file

        result = validator.validate_stage_file(stage_file)
        assert result is False

    def test_invalid_json_fails(self, checkpoint_temp_dir):
        """Should reject stage file with invalid JSON."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "invalid.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            f.write("{invalid json content")

        result = validator.validate_stage_file(stage_file)
        assert result is False

    def test_primitive_data_fails(self, checkpoint_temp_dir):
        """Should reject stage file with primitive data (not dict/list)."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "primitive.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump("just a string", f)

        result = validator.validate_stage_file(stage_file)
        assert result is False

    def test_null_data_fails(self, checkpoint_temp_dir):
        """Should reject stage file with null data."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "null.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(None, f)

        result = validator.validate_stage_file(stage_file)
        assert result is False

    def test_nested_valid_data_passes(self, checkpoint_temp_dir):
        """Should accept deeply nested valid data structures."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "nested.json"
        nested_data = {
            "level1": {
                "level2": {
                    "level3": [
                        {"item": "data"}
                    ]
                }
            }
        }
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(nested_data, f)

        result = validator.validate_stage_file(stage_file)
        assert result is True


class TestMetadataFileValidation:
    """Test validate_metadata_file() combined method."""

    def test_valid_metadata_file_passes(self, checkpoint_temp_dir, valid_checkpoint_metadata):
        """Should accept valid metadata file and return metadata."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(valid_checkpoint_metadata, f)

        is_valid, metadata = validator.validate_metadata_file(metadata_file)
        assert is_valid is True
        assert metadata == valid_checkpoint_metadata

    def test_nonexistent_metadata_file_fails(self, checkpoint_temp_dir):
        """Should reject non-existent metadata file."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "nonexistent.json"

        is_valid, metadata = validator.validate_metadata_file(metadata_file)
        assert is_valid is False
        assert metadata is None

    def test_empty_metadata_file_fails(self, checkpoint_temp_dir):
        """Should reject empty (corrupted) metadata file."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "metadata.json"
        metadata_file.touch()  # Create empty file

        is_valid, metadata = validator.validate_metadata_file(metadata_file)
        assert is_valid is False
        assert metadata is None

    def test_invalid_json_metadata_fails(self, checkpoint_temp_dir):
        """Should reject metadata file with invalid JSON."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        is_valid, metadata = validator.validate_metadata_file(metadata_file)
        assert is_valid is False
        assert metadata is None

    def test_invalid_schema_metadata_fails(self, checkpoint_temp_dir, invalid_metadata_missing_fields):
        """Should reject metadata file with invalid schema."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(invalid_metadata_missing_fields, f)

        is_valid, metadata = validator.validate_metadata_file(metadata_file)
        assert is_valid is False
        assert metadata is None

    def test_metadata_with_utf8_encoding(self, checkpoint_temp_dir):
        """Should handle UTF-8 encoded metadata correctly."""
        validator = CheckpointValidator()
        metadata_file = checkpoint_temp_dir / "metadata.json"
        metadata = {
            "niche_description": "AI tools for 日本語 developers 🚀",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5
        }
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False)

        is_valid, result = validator.validate_metadata_file(metadata_file)
        assert is_valid is True
        assert result["niche_description"] == "AI tools for 日本語 developers 🚀"


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_validates_empty_completed_stages_list(self):
        """Should accept empty completed_stages list."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 1,
            "completed_stages": []  # Empty list is valid
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    def test_validates_empty_errors_list(self):
        """Should accept empty errors list."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "errors": []  # Empty list is valid
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    def test_handles_extra_metadata_fields(self):
        """Should accept metadata with extra unknown fields."""
        validator = CheckpointValidator()
        metadata = {
            "niche_description": "Test niche",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 5,
            "unknown_field": "extra data",  # Extra fields should not cause failure
            "another_unknown": 123
        }
        result = validator.validate_metadata(metadata)
        assert result is True

    def test_stage_file_validation_handles_read_error(self, checkpoint_temp_dir):
        """Should gracefully handle file read errors."""
        validator = CheckpointValidator()
        stage_file = checkpoint_temp_dir / "test.json"

        # Create file with valid JSON
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump({"test": "data"}, f)

        # Mock open to raise exception
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = validator.validate_stage_file(stage_file)
            assert result is False

    def test_metadata_validation_logs_specific_errors(self, checkpoint_temp_dir, invalid_metadata_missing_fields):
        """Should log specific error messages for validation failures."""
        validator = CheckpointValidator()

        with patch("nicheiq.utils.validation.checkpoint_validator.logger") as mock_logger:
            validator.validate_metadata(invalid_metadata_missing_fields)

            # Should have logged error about missing field
            assert mock_logger.error.called
            error_msg = mock_logger.error.call_args[0][0]
            assert "missing required field" in error_msg.lower()

    def test_boundary_stage_values(self):
        """Should handle boundary stage values correctly."""
        validator = CheckpointValidator()

        # Min boundary (1)
        metadata_min = {
            "niche_description": "Test",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 1
        }
        assert validator.validate_metadata(metadata_min) is True

        # Max boundary (10)
        metadata_max = {
            "niche_description": "Test",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 10
        }
        assert validator.validate_metadata(metadata_max) is True

        # Just below min (0.99)
        metadata_below = {
            "niche_description": "Test",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 0.99
        }
        assert validator.validate_metadata(metadata_below) is False

        # Just above max (10.01)
        metadata_above = {
            "niche_description": "Test",
            "started_at": "2025-01-15T10:30:00",
            "current_stage": 10.01
        }
        assert validator.validate_metadata(metadata_above) is False
