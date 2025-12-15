"""
Checkpoint management for ResearchFlow.

Handles saving and loading checkpoint state to enable resume functionality
and recovery from failures.
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import types
from typing import Any, Union, get_args, get_origin

from loguru import logger

from ..config.settings import settings
from ..models.research_state import ResearchState
from ..utils.validation import CheckpointValidator


class CheckpointManager:
    """
    Manages checkpoint creation, saving, loading, and cleanup for research flows.

    Checkpoints are stored in a folder structure:
        output/checkpoints/checkpoint_{niche_slug}_{timestamp}/
            ├── metadata.json
            ├── stage_5_social_content.json
            ├── stage_6_pain_points.json
            └── ...
    """

    def __init__(
        self,
        niche_description: str,
        state: ResearchState,
        allowed_project_types: list[str | None] = None
    ):
        """
        Initialize checkpoint manager.

        Args:
            niche_description: Niche being researched
            state: Research state object to checkpoint
            allowed_project_types: Optional project type constraints
        """
        self.niche_description = niche_description
        self.state = state
        self.allowed_project_types = allowed_project_types
        self.checkpoint_folder: Path | None = None
        self.validator = CheckpointValidator()

    def _get_niche_slug(self) -> str:
        """Generate filesystem-safe slug from niche description."""
        slug = "".join(c if c.isalnum() else "_" for c in self.niche_description[:50])
        return slug.lower().strip("_")

    def _init_checkpoint_folder(self) -> Path:
        """Initialize checkpoint folder on first checkpoint save."""
        if not settings.checkpoint_enabled:
            raise RuntimeError("Checkpointing is disabled in settings")

        if self.checkpoint_folder is not None:
            return self.checkpoint_folder

        niche_slug = self._get_niche_slug()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"checkpoint_{niche_slug}_{timestamp}"
        self.checkpoint_folder = settings.checkpoint_dir / folder_name
        self.checkpoint_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"✓ Checkpoint folder created: {self.checkpoint_folder}")
        return self.checkpoint_folder

    def save_stage(self, stage_name: str, stage_data: Any) -> None:
        """
        Save individual stage data to checkpoint folder.

        Args:
            stage_name: Stage identifier (e.g., "stage_5_social_content")
            stage_data: Pydantic model or dict to serialize
        """
        if not settings.checkpoint_enabled:
            return

        try:
            # Initialize checkpoint folder if first checkpoint
            checkpoint_folder = self._init_checkpoint_folder()

            # Serialize stage data
            if hasattr(stage_data, 'model_dump'):
                # Single Pydantic model
                data_json = stage_data.model_dump(mode='json')
            elif isinstance(stage_data, list):
                # Check if list contains Pydantic models
                if stage_data and hasattr(stage_data[0], 'model_dump'):
                    # List of Pydantic models - serialize each one
                    data_json = [item.model_dump(mode='json') for item in stage_data]
                else:
                    # List of primitives/dicts - already JSON-serializable
                    data_json = stage_data
            elif isinstance(stage_data, dict):
                # Dict - need to serialize any Pydantic models in values
                data_json = {}
                for key, value in stage_data.items():
                    if hasattr(value, 'model_dump'):
                        data_json[key] = value.model_dump(mode='json')
                    else:
                        data_json[key] = value
            else:
                data_json = {"data": str(stage_data)}

            # Save stage file
            stage_file = checkpoint_folder / f"{stage_name}.json"
            with open(stage_file, "w", encoding="utf-8") as f:
                json.dump(data_json, f, indent=2, ensure_ascii=False, default=str)

            # Update metadata
            self._update_checkpoint_metadata(stage_name)

            logger.info(f"✓ Checkpoint saved: {stage_name}")

        except Exception as e:
            logger.warning(f"Failed to save checkpoint for {stage_name}: {e}")
            # Don't fail the pipeline for checkpoint errors

    def _update_checkpoint_metadata(self, completed_stage: str) -> None:
        """Update checkpoint metadata.json with current progress."""
        if self.checkpoint_folder is None:
            return

        metadata_file = self.checkpoint_folder / "metadata.json"

        # Load existing metadata if exists
        if metadata_file.exists():
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = {
                "niche_description": self.niche_description,
                "allowed_project_types": self.allowed_project_types,
                "started_at": self.state.started_at.isoformat() if self.state.started_at else datetime.now().isoformat(),
                "completed_stages": [],
                "errors": self.state.errors.copy() if hasattr(self.state, 'errors') else [],
                "environment": {
                    "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}"
                }
            }

        # Update metadata
        metadata["last_checkpoint_at"] = datetime.now().isoformat()
        metadata["current_stage"] = self.state.current_stage
        if completed_stage not in metadata["completed_stages"]:
            metadata["completed_stages"].append(completed_stage)
        metadata["errors"] = self.state.errors.copy() if hasattr(self.state, 'errors') else []

        # Save metadata with atomic write (prevents corruption)
        temp_file = metadata_file.with_suffix('.json.tmp')
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
            temp_file.replace(metadata_file)  # Atomic operation on POSIX systems
        except Exception as e:
            logger.warning(f"Failed to update checkpoint metadata: {e}")
            if temp_file.exists():
                temp_file.unlink()  # Clean up temp file on error
            raise  # Re-raise so outer try/catch can handle

    def find_latest_checkpoint(self) -> Path | None:
        """Find most recent checkpoint folder for current niche."""
        if not settings.checkpoint_enabled or not settings.checkpoint_dir.exists():
            return None

        niche_slug = self._get_niche_slug()
        pattern = f"checkpoint_{niche_slug}_*"

        checkpoints = sorted(
            settings.checkpoint_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return checkpoints[0] if checkpoints else None

    def load_checkpoint_folder(self, folder_path: Path) -> bool:
        """
        Load checkpoint from folder and reconstruct ResearchState.

        Args:
            folder_path: Path to checkpoint folder

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load and validate metadata using validator
            metadata_file = folder_path / "metadata.json"
            is_valid, metadata = self.validator.validate_metadata_file(metadata_file)
            if not is_valid:
                return False

            # Validate niche matches
            if metadata["niche_description"] != self.niche_description:
                logger.warning(
                    f"Checkpoint niche doesn't match current niche:\n"
                    f"  Checkpoint: {metadata['niche_description'][:100]}...\n"
                    f"  Current: {self.niche_description[:100]}..."
                )
                return False

            # Load individual stage files and reconstruct state
            self._reconstruct_state_from_checkpoint(folder_path, metadata)

            # Restore checkpoint folder reference
            self.checkpoint_folder = folder_path

            logger.info(f"✓ Checkpoint restored from: {folder_path.name}")
            logger.info(f"  Last completed stage: {metadata.get('completed_stages', [])[-1] if metadata.get('completed_stages') else 'none'}")
            logger.info(f"  Current stage: {self.state.current_stage}")

            return True

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False

    def _reconstruct_state_from_checkpoint(self, folder_path: Path, metadata: dict[str, Any]) -> None:
        """Reconstruct ResearchState from individual stage checkpoint files."""
        # Map stage files to state attributes
        stage_mapping = {
            # Stage 1-6.5: Initial stages
            "stage_1_niche_context.json": "niche_context",
            "stage_5_social_content.json": "social_content",
            "stage_6_pain_points.json": "pain_point_analysis",
            "stage_6_5_audience_mapping.json": "audience_mapping",
            # Stage 7: Unified solution pipeline (6 tasks - divergent-convergent architecture)
            # Tasks 1-2: Intermediate outputs (for debugging, not loaded to state)
            "stage_7_1_divergent.json": None,  # RawConceptList - debug only
            "stage_7_2_filtered.json": None,   # FilteredConceptList - debug only
            # Tasks 3-6: Essential outputs (loaded to state for resume)
            "stage_7_3_refinement.json": "idea_generation",
            "stage_7_4_competitive.json": "competitive_analysis",
            "stage_7_5_enhancements.json": None,  # CompetitiveEnhancements - debug only
            "stage_7_6_selection.json": "solution_selection",
            # Stage 8-8.7: Post-solution validation stages
            "stage_8_pricing_validation.json": "pricing_strategies",
            "stage_8_5_keyword_validation.json": "keyword_validation_results",
            "stage_8_5_keyword_validation_partial.json": "keyword_validation_results",
            "stage_8_55_traffic_monetization.json": "traffic_monetization_results",
            "stage_8_55_traffic_monetization_partial.json": "traffic_monetization_results",
            "stage_8_6_market_sizing.json": "market_sizing",
            "stage_8_7_solution_refinement.json": "solution_refinement",
            # Stage 9: SEO strategy (internal phases 9.5a/b/c)
            "stage_9_5a_seed_expansion.json": "stage_9_5a_expanded_keywords",
            "stage_9_5b_bulk_validation.json": "stage_9_5b_validation_results",
            "stage_9_5c_enrichment.json": "stage_9_5c_enriched_keywords",
            "stage_9_seo_strategy.json": "seo_strategy_report",
            # Stage 9.5-9.7: Post-SEO stages
            "stage_9_5_trend_longevity.json": "trend_longevity",
            "stage_9_6_seo_refinement.json": "seo_enrichment",
            "stage_9_7_data_sources.json": "data_source_research",
        }

        # Load each stage file if it exists
        for stage_file, state_attr in stage_mapping.items():
            file_path = folder_path / stage_file
            if file_path.exists():
                # Skip debug-only checkpoints (mapped to None)
                if state_attr is None:
                    logger.debug(f"  ⏭ Skipping {stage_file} (debug checkpoint, not loaded to state)")
                    continue

                # Validate stage file before loading
                if not self.validator.validate_stage_file(file_path):
                    logger.warning(f"Skipping corrupted stage file: {stage_file}")
                    continue

                with open(file_path, encoding="utf-8") as f:
                    stage_data = json.load(f)

                # Check if this is a "skipped" marker - don't try to load as Pydantic model
                if isinstance(stage_data, dict) and stage_data.get("skipped") is True:
                    skip_reason = stage_data.get("reason", "unknown")
                    logger.info(f"  ⏭ Skipping {stage_file} (was skipped: {skip_reason})")
                    continue

                # Get the Pydantic model class for this attribute
                field_info = ResearchState.model_fields.get(state_attr)
                if field_info and field_info.annotation:
                    # Extract the actual type (handle both Optional[X] and X | None)
                    field_type = field_info.annotation
                    origin = get_origin(field_type)
                    # Handle both Optional[X] (typing.Union) and X | None (types.UnionType)
                    if origin is Union or isinstance(field_type, types.UnionType):
                        args = get_args(field_type)
                        # Get the non-None type from the union
                        field_type = next((t for t in args if t is not type(None)), args[0])

                    # Load based on field type
                    try:
                        # Check if it's a List type
                        if get_origin(field_type) is list:
                            list_item_type = get_args(field_type)[0]
                            if hasattr(list_item_type, 'model_fields'):
                                # Backward compatibility: if stage_data is a dict (old single-object format),
                                # wrap it in a list for migration to new list format
                                if isinstance(stage_data, dict):
                                    logger.info(f"  ↑ Migrating old single-object format to list for {state_attr}")
                                    stage_data = [stage_data]

                                # List of Pydantic models - convert each dict
                                logger.debug(f"  Reconstructing list of {list_item_type.__name__} for {state_attr}")
                                reconstructed = [list_item_type(**item) for item in stage_data]
                                setattr(self.state, state_attr, reconstructed)
                                logger.debug(f"  ✓ Loaded {len(reconstructed)} {list_item_type.__name__} objects from {stage_file}")
                            else:
                                # List of primitives - set directly
                                setattr(self.state, state_attr, stage_data)
                                logger.debug(f"  ✓ Loaded {stage_file} → {state_attr} (primitive list)")
                        # Check if it's a Pydantic model (has model_fields)
                        elif hasattr(field_type, 'model_fields'):
                            # Pydantic model - instantiate with kwargs
                            logger.debug(f"  Reconstructing {field_type.__name__} for {state_attr}")
                            reconstructed = field_type(**stage_data)
                            setattr(self.state, state_attr, reconstructed)
                            logger.debug(f"  ✓ Loaded {stage_file} → {state_attr} ({field_type.__name__})")
                        else:
                            # Non-Pydantic type (dict, etc.) - set directly
                            setattr(self.state, state_attr, stage_data)
                            logger.debug(f"  ✓ Loaded {stage_file} → {state_attr} (raw data)")
                    except Exception as e:
                        logger.error(
                            f"  ✗ Failed to reconstruct Pydantic model for {stage_file} → {state_attr}: {e}\n"
                            f"    Field type: {field_type}\n"
                            f"    Falling back to raw dict data (this may cause attribute access errors later)"
                        )
                        # Fallback: set as raw dict
                        setattr(self.state, state_attr, stage_data)

        # Restore metadata fields
        self.state.current_stage = metadata.get("current_stage", 1)
        self.state.errors = metadata.get("errors", [])

        if metadata.get("started_at"):
            self.state.started_at = datetime.fromisoformat(metadata["started_at"])

        # Restore allowed_project_types from checkpoint metadata
        if metadata.get("allowed_project_types"):
            self.state.allowed_project_types = metadata["allowed_project_types"]

    def get_completed_stages(self, folder_path: Path | None = None) -> list[str]:
        """Get list of completed stage identifiers from checkpoint folder."""
        checkpoint_folder = folder_path or self.checkpoint_folder
        if checkpoint_folder is None or not checkpoint_folder.exists():
            return []

        metadata_file = checkpoint_folder / "metadata.json"
        if not metadata_file.exists():
            return []

        with open(metadata_file, encoding="utf-8") as f:
            metadata = json.load(f)

        return metadata.get("completed_stages", [])

    def cleanup_old_checkpoints(self) -> None:
        """Remove checkpoints older than configured max age."""
        if not settings.checkpoint_auto_cleanup or settings.checkpoint_max_age_days == 0:
            return

        if not settings.checkpoint_dir.exists():
            return

        cutoff_time = datetime.now() - timedelta(days=settings.checkpoint_max_age_days)
        niche_slug = self._get_niche_slug()
        pattern = f"checkpoint_{niche_slug}_*"

        removed_count = 0
        for checkpoint_folder in settings.checkpoint_dir.glob(pattern):
            if checkpoint_folder.is_dir():
                folder_mtime = datetime.fromtimestamp(checkpoint_folder.stat().st_mtime)
                if folder_mtime < cutoff_time:
                    try:
                        shutil.rmtree(checkpoint_folder)
                        removed_count += 1
                        logger.debug(f"Removed old checkpoint: {checkpoint_folder.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove checkpoint {checkpoint_folder.name}: {e}")

        if removed_count > 0:
            logger.info(f"✓ Cleaned up {removed_count} old checkpoint(s)")
