"""
Checkpoint management for ResearchFlow.

Handles saving and loading checkpoint state to enable resume functionality
and recovery from failures.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import shutil
from datetime import datetime, timedelta

from loguru import logger

from ..config.settings import settings
from ..models.research_state import ResearchState


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
        allowed_project_types: Optional[List[str]] = None
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
        self.checkpoint_folder: Optional[Path] = None

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
                data_json = stage_data.model_dump(mode='json')
            elif isinstance(stage_data, dict):
                data_json = stage_data
            elif isinstance(stage_data, list):
                data_json = stage_data  # Lists are JSON-serializable
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
            with open(metadata_file, "r", encoding="utf-8") as f:
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

        # Save metadata
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

    def find_latest_checkpoint(self) -> Optional[Path]:
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
            # Load metadata
            metadata_file = folder_path / "metadata.json"
            if not metadata_file.exists():
                logger.error(f"Checkpoint metadata not found: {metadata_file}")
                return False

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

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

    def _reconstruct_state_from_checkpoint(self, folder_path: Path, metadata: Dict[str, Any]) -> None:
        """Reconstruct ResearchState from individual stage checkpoint files."""
        # Map stage files to state attributes
        stage_mapping = {
            "stage_5_social_content.json": "social_content",
            "stage_6_pain_points.json": "pain_point_analysis",
            "stage_7_solutions.json": "idea_generation",
            "stage_8_competitive.json": "competitive_analysis",
            "stage_8_5_refinement.json": "idea_generation",  # Stage 8.5 updates idea_generation with competitive insights
            "stage_8_75_solution_selection.json": "solution_selection",
            "stage_8_8_keyword_validation.json": "keyword_validation_results",  # Stage 8.8 keyword demand validation
            "stage_8_85_solution_refinement.json": "solution_refinement",  # Stage 8.85 strategic refinements
            "stage_9_seo_strategy.json": "seo_strategy_report",
            "stage_9_5_seo_refinement.json": "seo_enrichment",  # Stage 9.5 SEO score refinement
            "stage_9_75_data_sources.json": "data_source_research",
        }

        # Load each stage file if it exists
        for stage_file, state_attr in stage_mapping.items():
            file_path = folder_path / stage_file
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    stage_data = json.load(f)

                # Get the Pydantic model class for this attribute
                field_info = ResearchState.model_fields.get(state_attr)
                if field_info and field_info.annotation:
                    # Extract the actual type (handle Optional[Type])
                    field_type = field_info.annotation
                    if hasattr(field_type, '__origin__'):  # Optional type
                        field_type = field_type.__args__[0]

                    # Load based on field type
                    try:
                        # Handle legacy checkpoint format where lists were wrapped as {"data": str(...)}
                        if (isinstance(stage_data, dict) and
                            len(stage_data) == 1 and
                            "data" in stage_data and
                            isinstance(stage_data["data"], str)):
                            try:
                                import ast
                                stage_data = ast.literal_eval(stage_data["data"])
                                logger.debug(f"  Unwrapped legacy checkpoint format for {stage_file}")
                            except (ValueError, SyntaxError) as e:
                                logger.warning(f"  Failed to unwrap legacy checkpoint: {e}")

                        # Check if it's a Pydantic model (has model_dump method)
                        if hasattr(field_type, 'model_fields'):
                            # Pydantic model - instantiate with kwargs
                            setattr(self.state, state_attr, field_type(**stage_data))
                        else:
                            # Non-Pydantic type (list, dict, etc.) - set directly
                            setattr(self.state, state_attr, stage_data)
                        logger.debug(f"  Loaded {stage_file} → {state_attr}")
                    except Exception as e:
                        logger.warning(f"  Failed to load {stage_file}: {e}")

        # Restore metadata fields
        self.state.current_stage = metadata.get("current_stage", 1)
        self.state.errors = metadata.get("errors", [])

        if metadata.get("started_at"):
            self.state.started_at = datetime.fromisoformat(metadata["started_at"])

    def get_completed_stages(self, folder_path: Optional[Path] = None) -> List[str]:
        """Get list of completed stage identifiers from checkpoint folder."""
        checkpoint_folder = folder_path or self.checkpoint_folder
        if checkpoint_folder is None or not checkpoint_folder.exists():
            return []

        metadata_file = checkpoint_folder / "metadata.json"
        if not metadata_file.exists():
            return []

        with open(metadata_file, "r", encoding="utf-8") as f:
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
