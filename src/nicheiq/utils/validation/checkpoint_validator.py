"""
Checkpoint validation utilities for checkpoint integrity and compatibility.

Validates checkpoint metadata and stage files to detect corruption or
incompatibility before loading into ResearchState.
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger


class CheckpointValidator:
    """
    Validates checkpoint metadata and stage files for integrity and compatibility.

    Used by CheckpointManager to verify checkpoint data before loading into
    ResearchState. Detects corruption (empty files, invalid JSON) and incompatibility
    (missing required fields, invalid stage ranges).

    Example:
        >>> validator = CheckpointValidator()
        >>> if validator.validate_metadata(metadata):
        ...     # Safe to load checkpoint
        ...     pass
    """

    # Checkpoint metadata schema requirements
    REQUIRED_METADATA_FIELDS = ["niche_description", "started_at", "current_stage"]
    VALID_STAGE_RANGE = (1, 10)  # Main stages 1-10, with decimal sub-stages

    def __init__(self):
        """Initialize checkpoint validator."""
        pass

    def validate_metadata(self, metadata: dict[str, Any]) -> bool:
        """
        Validate checkpoint metadata schema to detect corruption or incompatibility.

        Checks:
        1. Required fields exist (niche_description, started_at, current_stage)
        2. Field types are correct (str, str, numeric)
        3. current_stage is in valid range (1-10)
        4. Optional fields have correct types (completed_stages, errors)

        Args:
            metadata: Loaded metadata dictionary

        Returns:
            True if valid, False if corrupted or incompatible
        """
        # Check required fields exist
        for field in self.REQUIRED_METADATA_FIELDS:
            if field not in metadata:
                logger.error(f"Checkpoint missing required field: {field}")
                return False

        # Validate field types
        if not isinstance(metadata["niche_description"], str):
            logger.error("Checkpoint niche_description must be string")
            return False

        if not isinstance(metadata["current_stage"], (int, float)):
            logger.error("Checkpoint current_stage must be numeric")
            return False

        # Validate current_stage range (1-10 for main stages, with decimal sub-stages)
        min_stage, max_stage = self.VALID_STAGE_RANGE
        if not (min_stage <= metadata["current_stage"] <= max_stage):
            logger.error(
                f"Checkpoint current_stage out of range: {metadata['current_stage']} "
                f"(expected {min_stage}-{max_stage})"
            )
            return False

        # Validate completed_stages is list if present
        if "completed_stages" in metadata and not isinstance(metadata["completed_stages"], list):
            logger.error("Checkpoint completed_stages must be list")
            return False

        # Validate errors is list if present
        if "errors" in metadata and not isinstance(metadata["errors"], list):
            logger.error("Checkpoint errors must be list")
            return False

        return True

    def validate_stage_file(self, file_path: Path) -> bool:
        """
        Validate individual stage file for corruption.

        Checks:
        1. File exists and is not empty
        2. File contains valid JSON
        3. JSON root is dict or list (not primitive)

        Args:
            file_path: Path to stage checkpoint file

        Returns:
            True if valid, False if corrupted
        """
        try:
            # Check file exists and is not empty
            if not file_path.exists():
                return False

            if file_path.stat().st_size == 0:
                logger.warning(f"Stage file is empty (corrupted): {file_path.name}")
                return False

            # Attempt to parse JSON
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Basic sanity check: must be dict or list
            if not isinstance(data, (dict, list)):
                logger.warning(f"Stage file has invalid format: {file_path.name}")
                return False

            return True

        except json.JSONDecodeError as e:
            logger.warning(f"Stage file JSON parse error ({file_path.name}): {e}")
            return False
        except Exception as e:
            logger.warning(f"Stage file validation error ({file_path.name}): {e}")
            return False

    def validate_metadata_file(self, metadata_file: Path) -> tuple[bool, dict[str, Any] | None]:
        """
        Validate metadata file and return parsed metadata if valid.

        Convenience method that combines file existence check, JSON parsing,
        and schema validation in one call.

        Args:
            metadata_file: Path to metadata.json file

        Returns:
            Tuple of (is_valid, metadata_dict or None)
        """
        try:
            # Check file exists
            if not metadata_file.exists():
                logger.error(f"Checkpoint metadata not found: {metadata_file}")
                return (False, None)

            # Check file is not empty (corrupted)
            if metadata_file.stat().st_size == 0:
                logger.error(
                    f"Checkpoint metadata is empty (corrupted): {metadata_file}. "
                    f"Delete checkpoint folder to start fresh or reconstruct metadata manually."
                )
                return (False, None)

            # Parse JSON
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)

            # Validate schema
            if not self.validate_metadata(metadata):
                logger.error(f"Checkpoint metadata validation failed: {metadata_file}")
                logger.error("Checkpoint may be corrupted or from incompatible version")
                return (False, None)

            return (True, metadata)

        except json.JSONDecodeError as e:
            logger.error(f"Checkpoint metadata JSON parse error: {e}")
            return (False, None)
        except Exception as e:
            logger.error(f"Failed to validate metadata file: {e}")
            return (False, None)
