"""
Checkpoint management for ResearchFlow.

Handles saving and loading checkpoint state to enable resume functionality
and recovery from failures.
"""

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import types
from typing import Any, Union, get_args, get_origin

from loguru import logger

from ..config.settings import settings
from ..models.research_state import ResearchState
from ..utils.validation import CheckpointValidator

# Bump when a checkpoint stage-file schema changes incompatibly. Stamped into metadata on
# save; a mismatch on load means the checkpoint may not deserialize cleanly (see load guard).
CHECKPOINT_SCHEMA_VERSION = 1


def _stage_num_from_filename(name: str) -> int | None:
    """Extract the producing stage number from a checkpoint stage id/filename.

    'stage_3_pain_points.json' -> 3 ; 'stage_5_3_refinement.json' -> 5 ;
    'stage_6a_seed_expansion' -> 6 ; 'metadata.json' / non-stage -> None.
    """
    m = re.match(r"stage_(\d+)", name)
    return int(m.group(1)) if m else None


class CheckpointManager:
    """
    Manages checkpoint creation, saving, loading, and cleanup for research flows.

    Checkpoints are stored in a folder structure:
        output/checkpoints/checkpoint_{niche_slug}_{timestamp}/
            ├── metadata.json
            ├── stage_2_social_content.json
            ├── stage_3_pain_points.json
            └── ...
    """

    def __init__(
        self,
        niche_description: str,
        state: ResearchState,
        allowed_project_types: list[str | None] = None,
        job_id: str | None = None,
        entry_mode: str | None = None,
    ):
        """
        Initialize checkpoint manager.

        Args:
            niche_description: Niche being researched
            state: Research state object to checkpoint
            allowed_project_types: Optional project type constraints
            job_id: Optional job identifier for cross-user checkpoint isolation
            entry_mode: Optional input entry mode ('idea'|'audience'|'discovery'); persisted in
                metadata so it survives resume (re-synced onto the flow after restore).
        """
        self.niche_description = niche_description
        self.state = state
        self.allowed_project_types = allowed_project_types
        self.job_id = job_id
        self.entry_mode = entry_mode
        self.checkpoint_folder: Path | None = None
        self.validator = CheckpointValidator()
        # Paid follow-up operations inspect this after a failed save. ``True`` means the
        # stage file is still exactly the pre-save version; ``False`` means even the local
        # compensation write failed, so the operation must not be refunded yet.
        self.last_save_failure_rollback_safe = True

    def _get_niche_slug(self) -> str:
        """Generate filesystem-safe slug from niche description."""
        slug = "".join(c if c.isalnum() else "_" for c in self.niche_description[:50])
        return slug.lower().strip("_")

    def _get_checkpoint_pattern(self) -> str:
        """Get glob pattern for matching checkpoint folders belonging to this job."""
        niche_slug = self._get_niche_slug()
        if self.job_id:
            return f"checkpoint_{niche_slug}_{self.job_id}_*"
        return f"checkpoint_{niche_slug}_*"

    def _init_checkpoint_folder(self) -> Path:
        """Initialize checkpoint folder on first checkpoint save."""
        if not settings.checkpoint_enabled:
            raise RuntimeError("Checkpointing is disabled in settings")

        if self.checkpoint_folder is not None:
            return self.checkpoint_folder

        niche_slug = self._get_niche_slug()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.job_id:
            folder_name = f"checkpoint_{niche_slug}_{self.job_id}_{timestamp}"
        else:
            folder_name = f"checkpoint_{niche_slug}_{timestamp}"
        self.checkpoint_folder = settings.checkpoint_dir / folder_name
        self.checkpoint_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"✓ Checkpoint folder created: {self.checkpoint_folder}")
        return self.checkpoint_folder

    def save_stage(self, stage_name: str, stage_data: Any) -> bool:
        """
        Save individual stage data to checkpoint folder.

        Args:
            stage_name: Stage identifier (e.g., "stage_2_social_content")
            stage_data: Pydantic model or dict to serialize

        Returns:
            True if the save succeeded (or checkpointing is disabled — nothing to fail),
            False if it was attempted and failed. Exceptions are still swallowed (logged
            only) so ordinary pipeline stage saves never abort the run — callers that need
            to know whether the write actually landed (e.g. gate_patches.py, where a
            swallowed failure would silently discard a user's edit) MUST check this return
            value (Codex review finding 5).
        """
        if not settings.checkpoint_enabled:
            return True

        self.last_save_failure_rollback_safe = True
        stage_file: Path | None = None
        previous_stage_bytes: bytes | None = None
        stage_existed = False
        stage_replaced = False
        stage_temp: Path | None = None
        try:
            if stage_name == "stage_5_3_refinement" and self.job_id:
                from ..utils.idea_identity import (
                    link_legacy_findings_to_ideas,
                    stamp_new_idea_identities,
                    stamp_ruled_out_findings,
                )

                ideas = getattr(stage_data, "solution_ideas", stage_data)
                if isinstance(ideas, list):
                    stamp_new_idea_identities(
                        self.job_id,
                        ideas,
                        origin="phase1",
                        operation_key="initial",
                        force=True,
                        only_unowned=True,
                    )
                self.state.idea_ruled_out = link_legacy_findings_to_ideas(
                    self.state.idea_ruled_out,
                    ideas if isinstance(ideas, list) else [],
                )
                self.state.idea_ruled_out = stamp_ruled_out_findings(
                    self.job_id,
                    self.state.idea_ruled_out,
                    operation_key="phase1",
                )

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

            # Save the stage through an atomic replacement. More importantly, retain the
            # exact previous bytes until metadata also lands: metadata serialization can
            # fail after the stage write, and returning False while leaving the new paid
            # candidate on disk would let the caller refund an operation whose result
            # survived in the Phase-2 checkpoint.
            stage_file = checkpoint_folder / f"{stage_name}.json"
            stage_existed = stage_file.exists()
            if stage_existed:
                previous_stage_bytes = stage_file.read_bytes()
            stage_temp = stage_file.with_suffix(".json.tmp")
            with open(stage_temp, "w", encoding="utf-8") as f:
                json.dump(data_json, f, indent=2, ensure_ascii=False, default=str)
            stage_temp.replace(stage_file)
            stage_replaced = True

            # Update metadata
            self._update_checkpoint_metadata(stage_name)

            logger.info(f"✓ Checkpoint saved: {stage_name}")
            return True

        except Exception as e:
            if stage_temp is not None:
                try:
                    stage_temp.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    logger.debug(
                        f"Failed to clean checkpoint temp file {stage_temp}: {cleanup_error}"
                    )
            if stage_replaced and stage_file is not None:
                try:
                    if stage_existed:
                        restore_temp = stage_file.with_suffix(".json.restore.tmp")
                        restore_temp.write_bytes(previous_stage_bytes or b"")
                        restore_temp.replace(stage_file)
                    else:
                        stage_file.unlink(missing_ok=True)
                except Exception as restore_error:
                    self.last_save_failure_rollback_safe = False
                    logger.critical(
                        f"Failed to restore checkpoint {stage_name} after a partial save: "
                        f"{restore_error}. A paid caller must hold settlement and retry."
                    )
            logger.warning(f"Failed to save checkpoint for {stage_name}: {e}")
            # Don't fail the pipeline for checkpoint errors
            return False

    def save_cost_breakdown(self, rows: list) -> None:
        """Persist the run's cost-tracker stage usages (from CostTracker.export_state()).

        Written as cost_tracker.json in the checkpoint folder so the Phase-2 process
        (a separate worker task loading this checkpoint) can seed its fresh tracker and
        report cumulative Phase-1 + Phase-2 cost. Best-effort — never fails the pipeline.
        """
        if not settings.checkpoint_enabled:
            return
        try:
            checkpoint_folder = self._init_checkpoint_folder()
            cost_file = checkpoint_folder / "cost_tracker.json"
            with open(cost_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"✓ Checkpoint saved: cost_tracker ({len(rows)} usages)")
        except Exception as e:
            logger.warning(f"Failed to save cost breakdown checkpoint: {e}")

    def load_cost_breakdown(self) -> list | None:
        """Read cost_tracker.json from the loaded checkpoint folder (None if absent)."""
        if self.checkpoint_folder is None:
            return None
        cost_file = self.checkpoint_folder / "cost_tracker.json"
        if not cost_file.exists():
            return None
        try:
            with open(cost_file, encoding="utf-8") as f:
                rows = json.load(f)
            return rows if isinstance(rows, list) else None
        except Exception as e:
            logger.warning(f"Failed to load cost breakdown checkpoint: {e}")
            return None

    def flush_metadata(self) -> None:
        """Rewrite metadata.json from current state WITHOUT marking a stage completed.

        For state mutated with no following save_stage (e.g. skipped_stages set in
        _skip_stage's terminal cascade) — otherwise those fields never reach disk and are
        lost on resume."""
        self._update_checkpoint_metadata("")

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
                "job_id": self.job_id,
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "allowed_project_types": self.allowed_project_types,
                "entry_mode": self.entry_mode,
                "started_at": self.state.started_at.isoformat() if self.state.started_at else datetime.now().isoformat(),
                "completed_stages": [],
                "errors": self.state.errors.copy() if hasattr(self.state, 'errors') else [],
                "environment": {
                    "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}"
                }
            }

        # Update metadata
        metadata["schema_version"] = CHECKPOINT_SCHEMA_VERSION  # stamp pre-existing metadata too
        metadata["last_checkpoint_at"] = datetime.now().isoformat()
        metadata["current_stage"] = self.state.current_stage
        metadata["entry_mode"] = self.entry_mode
        if completed_stage and completed_stage not in metadata["completed_stages"]:
            metadata["completed_stages"].append(completed_stage)
        metadata["errors"] = self.state.errors.copy() if hasattr(self.state, 'errors') else []

        # Quality tier fields (for data quality summary in final report)
        if hasattr(self.state, 'social_content_quality_tier') and self.state.social_content_quality_tier:
            metadata["social_content_quality_tier"] = self.state.social_content_quality_tier
        if hasattr(self.state, 'pain_point_quality_tier') and self.state.pain_point_quality_tier:
            metadata["pain_point_quality_tier"] = self.state.pain_point_quality_tier
        if hasattr(self.state, 'pain_point_confidence_score') and self.state.pain_point_confidence_score is not None:
            metadata["pain_point_confidence_score"] = self.state.pain_point_confidence_score

        # Filtering stats (for data quality summary in final report)
        if hasattr(self.state, 'filtering_stats') and self.state.filtering_stats:
            metadata["filtering_stats"] = self.state.filtering_stats

        # Completed stages list (for diagnostic visibility in final report)
        if hasattr(self.state, 'completed_stages') and self.state.completed_stages:
            metadata["completed_stage_numbers"] = self.state.completed_stages

        # Fallback stages list (for quality warnings in final report)
        if hasattr(self.state, 'fallback_stages') and self.state.fallback_stages:
            metadata["fallback_stages"] = self.state.fallback_stages

        # Social content metrics (for research metadata in final report)
        if hasattr(self.state, 'social_content_metrics') and self.state.social_content_metrics:
            metadata["social_content_metrics"] = self.state.social_content_metrics

        # Catalog-seeded flag (transparency badge; must survive Phase-2 resume)
        if getattr(self.state, 'seeded_from_catalog', False):
            metadata["seeded_from_catalog"] = True

        # Phase-1 state fields consumed by the report/preview AFTER resume — must round-trip
        # (mirror fallback_stages; otherwise they reset to their model default on --resume /
        # Phase-2, silently dropping the user's idea_focus steer and report caveats/telemetry).
        metadata["idea_focus"] = getattr(self.state, "idea_focus", "auto")
        if getattr(self.state, "idea_coverage_caveats", None):
            metadata["idea_coverage_caveats"] = self.state.idea_coverage_caveats
        if getattr(self.state, "idea_ruled_out", None):
            metadata["idea_ruled_out"] = self.state.idea_ruled_out
        if getattr(self.state, "idea_funnel_counts", None):
            metadata["idea_funnel_counts"] = self.state.idea_funnel_counts
        if getattr(self.state, "idea_cell_allocation", None):
            metadata["idea_cell_allocation"] = self.state.idea_cell_allocation
        if getattr(self.state, "idea_overlap_groups", None):
            metadata["idea_overlap_groups"] = self.state.idea_overlap_groups
        if getattr(self.state, "buyer_job_partition", None):
            metadata["buyer_job_partition"] = self.state.buyer_job_partition
        if getattr(self.state, "idea_theses", None):
            metadata["idea_theses"] = self.state.idea_theses
        if getattr(self.state, "niche_incumbent_map", None):
            metadata["niche_incumbent_map"] = self.state.niche_incumbent_map
        if getattr(self.state, "niche_wallet_brief", None):
            metadata["niche_wallet_brief"] = self.state.niche_wallet_brief
        # `is not None` (not truthy): '' is a real "probed, found nothing" result for these two —
        # dropping it on save would make a later resume re-probe work this run already paid for
        # (eager-meandering-feather.md Phase 4, section C).
        if getattr(self.state, "niche_data_menu_text", None) is not None:
            metadata["niche_data_menu_text"] = self.state.niche_data_menu_text
        if getattr(self.state, "niche_dissatisfaction_text", None) is not None:
            metadata["niche_dissatisfaction_text"] = self.state.niche_dissatisfaction_text
        # "Check my idea" (validate_idea) fields — plain-value pattern like idea_focus.
        # inferred_fields uses `is not None`: an EMPTY list is a real "all stated" result.
        if getattr(self.state, "user_idea_text", None) is not None:
            metadata["user_idea_text"] = self.state.user_idea_text
        if getattr(self.state, "user_idea_brief", None) is not None:
            metadata["user_idea_brief"] = self.state.user_idea_brief
        if getattr(self.state, "user_idea_inferred_fields", None) is not None:
            metadata["user_idea_inferred_fields"] = self.state.user_idea_inferred_fields
        if getattr(self.state, "user_idea_pivot", None) is not None:
            metadata["user_idea_pivot"] = self.state.user_idea_pivot
        if getattr(self.state, "user_idea_identity_terms", None) is not None:
            metadata["user_idea_identity_terms"] = self.state.user_idea_identity_terms
        if getattr(self.state, "user_idea_brief_parity", None) is not None:
            metadata["user_idea_brief_parity"] = self.state.user_idea_brief_parity
        # Persist the pair by key presence, including its legacy/stale states. Metadata is
        # merged with the previous file, so explicit removal is required or a failed refresh
        # can resurrect an older summary/fingerprint on resume.
        _portfolio_summary = getattr(self.state, "idea_portfolio_summary", None)
        _portfolio_fingerprint = getattr(
            self.state, "idea_portfolio_summary_fingerprint", None
        )
        if _portfolio_summary is not None:
            metadata["idea_portfolio_summary"] = _portfolio_summary
        else:
            metadata.pop("idea_portfolio_summary", None)
        if _portfolio_fingerprint is not None:
            metadata["idea_portfolio_summary_fingerprint"] = _portfolio_fingerprint
        else:
            metadata.pop("idea_portfolio_summary_fingerprint", None)
        if getattr(self.state, "pipeline_degradations", None):
            metadata["pipeline_degradations"] = self.state.pipeline_degradations
        if getattr(self.state, "niche_drift_telemetry", None):
            metadata["niche_drift_telemetry"] = self.state.niche_drift_telemetry
        if getattr(self.state, "skipped_stages", None):
            metadata["skipped_stages"] = self.state.skipped_stages
        if getattr(self.state, "sources_searched", None):
            metadata["sources_searched"] = self.state.sources_searched

        # Guided-mode (chatMode) gate-patch fields (flows/gate_patches.py) — must round-trip
        # through resume like idea_focus above, since they are consumed later at the ideation
        # allocation choke point (UnifiedSolutionCrew._build_partition_cells), not at patch time.
        if getattr(self.state, "user_pain_scope", None) is not None:
            metadata["user_pain_scope"] = self.state.user_pain_scope.model_dump()
        if getattr(self.state, "user_audience_scope", None) is not None:
            metadata["user_audience_scope"] = self.state.user_audience_scope.model_dump()
        if getattr(self.state, "user_adjusted", False):
            metadata["user_adjusted"] = True

        # Stage completion timestamps (for timing summary in final report)
        if hasattr(self.state, 'stage_completion_timestamps') and self.state.stage_completion_timestamps:
            metadata["stage_completion_timestamps"] = {
                k: v.isoformat() if hasattr(v, 'isoformat') else str(v)
                for k, v in self.state.stage_completion_timestamps.items()
            }

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

    def find_latest_checkpoint(self, allow_cross_job: bool = False) -> Path | None:
        """Find most recent checkpoint folder for current niche/job.

        ``allow_cross_job`` gates the Tier-2 niche-only fallback. It defaults to False so
        a WORKER retry (same job_id as the failed job) only ever resumes its OWN checkpoint
        and never adopts an unrelated job's checkpoint when its own is missing (e.g. a
        Stage-1 failure that wrote nothing). The CLI ``--resume`` path opts in: it generates
        a fresh job_id per run and legitimately needs to continue prior niche progress.
        """
        if not settings.checkpoint_enabled or not settings.checkpoint_dir.exists():
            return None

        niche_slug = self._get_niche_slug()

        # Tier 1: job_id-scoped search (exact isolation)
        if self.job_id:
            pattern = f"checkpoint_{niche_slug}_{self.job_id}_*"
            checkpoints = sorted(
                settings.checkpoint_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if checkpoints:
                return checkpoints[0]

        # Tier 2: niche-only fallback (CLI resume with a fresh job_id each run). Opt-in only —
        # a worker retry must NOT silently adopt a different job's (possibly stale-schema) run.
        if not allow_cross_job:
            return None
        pattern = f"checkpoint_{niche_slug}_*"
        checkpoints = sorted(
            settings.checkpoint_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
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

            # Validate niche matches (skip when niche is empty, e.g. on-demand
            # tasks that load everything from the checkpoint)
            if self.niche_description and metadata["niche_description"] != self.niche_description:
                logger.warning(
                    f"Checkpoint niche doesn't match current niche:\n"
                    f"  Checkpoint: {metadata['niche_description'][:100]}...\n"
                    f"  Current: {self.niche_description[:100]}..."
                )
                return False

            checkpoint_job_id = metadata.get("job_id")

            # Schema-version guard: a checkpoint stamped with an older/missing schema_version
            # may not deserialize cleanly against the current Pydantic models. REFUSE to adopt
            # such a checkpoint across jobs (a fresh run is safer than forking stale-schema
            # data — this is exactly what caused the stale pain-point incident); for a same-job
            # resume, log and continue — the reconstruction-rewind below regenerates drifted stages.
            ckpt_version = metadata.get("schema_version")
            is_cross_job = bool(self.job_id and checkpoint_job_id and self.job_id != checkpoint_job_id)
            if ckpt_version != CHECKPOINT_SCHEMA_VERSION:
                if is_cross_job:
                    logger.warning(
                        f"Refusing cross-job resume: checkpoint schema_version={ckpt_version} != "
                        f"{CHECKPOINT_SCHEMA_VERSION} (source job={checkpoint_job_id}); starting fresh."
                    )
                    return False
                logger.warning(
                    f"Checkpoint schema_version={ckpt_version} != {CHECKPOINT_SCHEMA_VERSION}; "
                    f"relying on reconstruction-rewind for any drifted stages."
                )

            # Cross-job resume guard: if the source checkpoint belongs to a different
            # job, fork it to a fresh folder owned by the current job. Keeps the source
            # folder byte-identical for other resumes / inspection and prevents
            # save_stage + _update_checkpoint_metadata from corrupting the source.
            if is_cross_job:
                niche_slug = self._get_niche_slug()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                forked = settings.checkpoint_dir / f"checkpoint_{niche_slug}_{self.job_id}_{timestamp}"
                shutil.copytree(folder_path, forked)
                forked_meta_path = forked / "metadata.json"
                with open(forked_meta_path, encoding="utf-8") as f:
                    forked_metadata = json.load(f)
                forked_metadata["job_id"] = self.job_id
                forked_metadata["forked_from"] = folder_path.name
                forked_metadata["schema_version"] = CHECKPOINT_SCHEMA_VERSION
                with open(forked_meta_path, "w", encoding="utf-8") as f:
                    json.dump(forked_metadata, f, indent=2, default=str)
                logger.warning(
                    f"Cross-job resume: forked {folder_path.name} → {forked.name} "
                    f"(source job={checkpoint_job_id}, current job={self.job_id})"
                )
                folder_path = forked
                metadata = forked_metadata

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
        # Restore entry_mode from metadata so audience-framing survives resume. The flow re-syncs
        # this onto ResearchFlow.entry_mode after load (only matters if Stage 1 re-runs; the
        # framing fields themselves ride back on the restored stage_1_niche_context).
        if metadata.get("entry_mode") is not None:
            self.entry_mode = metadata.get("entry_mode")
        # Map stage files to state attributes
        stage_mapping = {
            # Stage 1-4: Initial stages
            "stage_1_niche_context.json": "niche_context",
            "stage_2_social_content.json": "social_content",
            "stage_3_pain_points.json": "pain_point_analysis",
            "stage_4_audience_mapping.json": "audience_mapping",
            "stage_5_competitor_mentions.json": "competitor_mentions_formatted",
            # Stage 5: Unified solution pipeline (6 tasks - divergent-convergent architecture)
            # Divergent pool: intermediate output (for debugging, not loaded to state)
            "stage_5_1_divergent.json": None,  # RawConceptList - debug only
            # Refinement onward: essential outputs (loaded to state for resume)
            "stage_5_3_refinement.json": "idea_generation",
            "stage_5_5_competitive.json": "competitive_analysis",
            "stage_5_6_selection.json": "solution_selection",
            "stage_5_niche_difficulty.json": "niche_difficulty_verdict",
            # Stage 6: SEO strategy (internal phases 6a/b/c/d)
            "stage_6a_seed_expansion.json": "seo_expanded_keywords",
            "stage_6b_bulk_validation.json": "seo_validation_results",
            "stage_6c_enrichment.json": "seo_enriched_keywords",
            "stage_6d_difficulty.json": "seo_enriched_keywords",
            "stage_6_seo_strategy.json": "seo_strategy_report",
            "stage_6_keyword_validation.json": "keyword_validation_results",
            "stage_6_keyword_validation_partial.json": "keyword_validation_results",
            # Stage 7-13: Post-solution validation stages
            "stage_7_pricing_validation.json": "pricing_strategies",
            "stage_8_traffic_monetization.json": "traffic_monetization_results",
            "stage_8_traffic_monetization_partial.json": "traffic_monetization_results",
            "stage_9_market_sizing.json": "market_sizing",
            "stage_10_solution_refinement.json": "solution_refinement",
            "stage_11_trend_longevity.json": "trend_longevity",
            "stage_12_seo_refinement.json": "seo_enrichment",
            "stage_13_data_sources.json": "data_source_research",
        }

        # Lowest stage whose data failed to deserialize (schema drift); triggers a rewind below.
        reconstruction_reset_stage: int | None = None

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
                            # Non-Pydantic type (dict, str, etc.) - set directly
                            # Unwrap single-key dict for plain string fields
                            if field_type is str and isinstance(stage_data, dict) and len(stage_data) == 1:
                                stage_data = next(iter(stage_data.values()))
                            setattr(self.state, state_attr, stage_data)
                            logger.debug(f"  ✓ Loaded {stage_file} → {state_attr} (raw data)")
                    except Exception as e:
                        # Schema drift: the saved JSON no longer satisfies the current Pydantic
                        # model. Do NOT keep the raw dict (it poisons downstream attribute access
                        # for any stage without a quality gate). Clear it and record the producing
                        # stage so progress rewinds and the stage RE-RUNS to regenerate valid data.
                        n = _stage_num_from_filename(stage_file)
                        logger.error(
                            f"  ✗ Failed to reconstruct {field_type} for {stage_file} → {state_attr}: {e}\n"
                            f"    Clearing it and scheduling re-run from stage {n}."
                        )
                        setattr(self.state, state_attr, None)
                        if n is not None:
                            reconstruction_reset_stage = (
                                n if reconstruction_reset_stage is None
                                else min(reconstruction_reset_stage, n)
                            )

        # Restore metadata fields
        self.state.current_stage = metadata.get("current_stage", 1)
        self.state.errors = metadata.get("errors", [])

        if metadata.get("started_at"):
            self.state.started_at = datetime.fromisoformat(metadata["started_at"])

        # Restore allowed_project_types from checkpoint metadata
        if metadata.get("allowed_project_types"):
            self.state.allowed_project_types = metadata["allowed_project_types"]

        # Restore quality tier fields
        if metadata.get("social_content_quality_tier"):
            self.state.social_content_quality_tier = metadata["social_content_quality_tier"]
        if metadata.get("pain_point_quality_tier"):
            self.state.pain_point_quality_tier = metadata["pain_point_quality_tier"]
        if metadata.get("pain_point_confidence_score") is not None:
            self.state.pain_point_confidence_score = metadata["pain_point_confidence_score"]

        # Restore filtering stats
        if metadata.get("filtering_stats"):
            self.state.filtering_stats = metadata["filtering_stats"]

        # Restore completed stages list
        if metadata.get("completed_stage_numbers"):
            self.state.completed_stages = metadata["completed_stage_numbers"]

        # Restore fallback stages list
        if metadata.get("fallback_stages"):
            self.state.fallback_stages = metadata["fallback_stages"]

        # Restore social content metrics
        if metadata.get("social_content_metrics"):
            self.state.social_content_metrics = metadata["social_content_metrics"]

        # Restore catalog-seeded flag (so Phase-2 reports keep the transparency badge)
        if metadata.get("seeded_from_catalog"):
            self.state.seeded_from_catalog = True

        # Restore Phase-1 state fields consumed by the report/preview after resume (see the
        # matching write block in _update_checkpoint_metadata). idea_focus is restored even at
        # its "auto" default so the resync in resume_from_checkpoint propagates the real value.
        if metadata.get("idea_focus"):
            self.state.idea_focus = metadata["idea_focus"]
        if metadata.get("idea_coverage_caveats"):
            self.state.idea_coverage_caveats = metadata["idea_coverage_caveats"]
        if metadata.get("idea_ruled_out"):
            self.state.idea_ruled_out = metadata["idea_ruled_out"]
        if metadata.get("idea_funnel_counts"):
            self.state.idea_funnel_counts = metadata["idea_funnel_counts"]
        if metadata.get("idea_cell_allocation"):
            self.state.idea_cell_allocation = metadata["idea_cell_allocation"]
        if metadata.get("idea_overlap_groups"):
            self.state.idea_overlap_groups = metadata["idea_overlap_groups"]
        if metadata.get("buyer_job_partition"):
            self.state.buyer_job_partition = metadata["buyer_job_partition"]
        if metadata.get("idea_theses"):
            self.state.idea_theses = metadata["idea_theses"]
        if metadata.get("niche_incumbent_map"):
            self.state.niche_incumbent_map = metadata["niche_incumbent_map"]
        if metadata.get("niche_wallet_brief"):
            self.state.niche_wallet_brief = metadata["niche_wallet_brief"]
        # "in" (not truthy): a saved '' ("probed, found nothing") must round-trip distinct from
        # "key absent" (never probed) — mirrors the `is not None` write above.
        if "niche_data_menu_text" in metadata:
            self.state.niche_data_menu_text = metadata["niche_data_menu_text"]
        if "niche_dissatisfaction_text" in metadata:
            self.state.niche_dissatisfaction_text = metadata["niche_dissatisfaction_text"]
        # "Check my idea" fields — "in" (not truthy) for inferred_fields so a saved []
        # ("all stated") round-trips distinct from "never parsed".
        if metadata.get("user_idea_text"):
            self.state.user_idea_text = metadata["user_idea_text"]
        if metadata.get("user_idea_brief"):
            self.state.user_idea_brief = metadata["user_idea_brief"]
        if "user_idea_inferred_fields" in metadata:
            self.state.user_idea_inferred_fields = metadata["user_idea_inferred_fields"]
        if metadata.get("user_idea_pivot"):
            self.state.user_idea_pivot = metadata["user_idea_pivot"]
        if metadata.get("user_idea_identity_terms"):
            self.state.user_idea_identity_terms = metadata["user_idea_identity_terms"]
        if metadata.get("user_idea_brief_parity"):
            self.state.user_idea_brief_parity = metadata["user_idea_brief_parity"]
        if "idea_portfolio_summary" in metadata:
            self.state.idea_portfolio_summary = metadata["idea_portfolio_summary"]
        if "idea_portfolio_summary_fingerprint" in metadata:
            self.state.idea_portfolio_summary_fingerprint = metadata[
                "idea_portfolio_summary_fingerprint"
            ]
        if metadata.get("pipeline_degradations"):
            self.state.pipeline_degradations = metadata["pipeline_degradations"]
        if metadata.get("niche_drift_telemetry"):
            self.state.niche_drift_telemetry = metadata["niche_drift_telemetry"]
        if metadata.get("skipped_stages"):
            self.state.skipped_stages = metadata["skipped_stages"]
        if metadata.get("sources_searched"):
            self.state.sources_searched = metadata["sources_searched"]

        # Legacy Stage-5 prose predates the positive paying-wallet publication contract. Apply
        # it once at hydration so every downstream consumer (resume, preview, and final report)
        # reads the same reconciled state without duplicating publication checks.
        self._reconcile_persisted_commercial_prose()

        # Compatibility hydration for checkpoints written before candidate/finding identity.
        # This runs after both the Stage-5 model and metadata ledger have been restored, and
        # mirrors the backend projection exactly for pool candidates.
        if self.job_id and self.state.idea_generation:
            from ..utils.idea_identity import (
                ensure_legacy_idea_identities,
                link_legacy_findings_to_ideas,
                stamp_ruled_out_findings,
            )

            ideas = getattr(self.state.idea_generation, "solution_ideas", None) or []
            ensure_legacy_idea_identities(self.job_id, ideas)
            self.state.idea_ruled_out = link_legacy_findings_to_ideas(
                self.state.idea_ruled_out,
                ideas,
            )
            self.state.idea_ruled_out = stamp_ruled_out_findings(
                self.job_id,
                self.state.idea_ruled_out,
                operation_key="legacy",
            )

        # Guided-mode (chatMode) gate-patch fields — see the matching write block above.
        if metadata.get("user_pain_scope"):
            from ..models.research_state import PainScope
            self.state.user_pain_scope = PainScope(**metadata["user_pain_scope"])
        if metadata.get("user_audience_scope"):
            from ..models.research_state import AudienceScope
            self.state.user_audience_scope = AudienceScope(**metadata["user_audience_scope"])
        if metadata.get("user_adjusted"):
            self.state.user_adjusted = True

        # Restore stage completion timestamps
        if metadata.get("stage_completion_timestamps"):
            self.state.stage_completion_timestamps = {
                k: datetime.fromisoformat(v) if isinstance(v, str) else v
                for k, v in metadata["stage_completion_timestamps"].items()
            }

        # ── Reconstruction-failure rewind ──
        # A stage whose data failed to deserialize (schema drift) was cleared above; rewind
        # progress to its producing stage so it RE-RUNS. Must run AFTER current_stage is
        # restored from metadata (above). Lowering current_stage covers stages 1-5; stages 4+
        # gate on metadata["completed_stages"] (read from disk via get_completed_stages), so
        # prune those entries on disk AND in-memory, plus the state's completed_stage_numbers.
        if reconstruction_reset_stage is not None:
            n = reconstruction_reset_stage
            logger.warning(
                f"Checkpoint reconstruction failed at stage ≥ {n} (schema drift); "
                f"rewinding to stage {n} for re-run."
            )
            self.state.current_stage = min(self.state.current_stage, n)
            completed = metadata.get("completed_stages") or []
            pruned = [s for s in completed if (_stage_num_from_filename(s) or 0) < n]
            if pruned != completed:
                metadata["completed_stages"] = pruned
                # Rewrite on disk: get_completed_stages() re-reads metadata.json at runtime.
                try:
                    meta_path = folder_path / "metadata.json"
                    if meta_path.exists():
                        with open(meta_path, encoding="utf-8") as f:
                            disk_meta = json.load(f)
                        disk_meta["completed_stages"] = pruned
                        with open(meta_path, "w", encoding="utf-8") as f:
                            json.dump(disk_meta, f, indent=2, default=str)
                except Exception as e:
                    logger.warning(f"Could not rewrite pruned completed_stages on disk: {e}")
            if getattr(self.state, "completed_stages", None):
                self.state.completed_stages = [s for s in self.state.completed_stages if s < n]

        # ── Checkpoint quality gates: detect poisoned data ──
        # Must run AFTER metadata restoration (line 402 sets current_stage from metadata).
        # If loaded data fails quality checks, discard it and reset to the producing stage.
        _CHECKPOINT_MINIMUMS = {
            "social_content": {
                "check": lambda sc: (
                    len(getattr(sc, "reddit_posts", None) or [])
                    + len(getattr(sc, "twitter_threads", None) or [])
                    + len(getattr(sc, "generic_posts", None) or [])
                ) >= 3,
                "stage": 2,
                "label": "social_content (< 3 posts)",
            },
            "pain_point_analysis": {
                "check": lambda pa: bool(getattr(pa, "pain_points", None)),
                "stage": 3,
                "label": "pain_point_analysis (0 pain points)",
            },
        }
        for attr_name, gate in _CHECKPOINT_MINIMUMS.items():
            value = getattr(self.state, attr_name, None)
            if value is not None and not gate["check"](value):
                logger.warning(
                    f"Checkpoint quality gate failed: {gate['label']}. "
                    f"Discarding — resetting to stage {gate['stage']} for re-run."
                )
                setattr(self.state, attr_name, None)
                n = gate["stage"]
                self.state.current_stage = min(self.state.current_stage, n)
                # Cascade fix (mirrors the reconstruction-failure rewind above): lowering
                # current_stage alone leaves downstream stages' "already completed" markers on
                # disk, silently suppressing their re-run even though their inputs were just
                # discarded (e.g. a gated empty pain_point_analysis leaving stage 4's audience
                # mapping marker in place, reused against regenerated pains). Prune completed
                # entries at/after the reset stage on disk AND in-memory, same as above.
                completed = metadata.get("completed_stages") or []
                pruned = [s for s in completed if (_stage_num_from_filename(s) or 0) < n]
                if pruned != completed:
                    metadata["completed_stages"] = pruned
                    try:
                        meta_path = folder_path / "metadata.json"
                        if meta_path.exists():
                            with open(meta_path, encoding="utf-8") as f:
                                disk_meta = json.load(f)
                            disk_meta["completed_stages"] = pruned
                            with open(meta_path, "w", encoding="utf-8") as f:
                                json.dump(disk_meta, f, indent=2, default=str)
                    except Exception as e:
                        logger.warning(f"Could not rewrite pruned completed_stages on disk: {e}")
                if getattr(self.state, "completed_stages", None):
                    self.state.completed_stages = [s for s in self.state.completed_stages if s < n]

    def _reconcile_persisted_commercial_prose(self) -> None:
        """Hydrate only paying-wallet prose that satisfies the shared positive contract."""
        from ..utils.niche_difficulty import (
            assess_niche_difficulty,
            reconcile_persisted_niche_difficulty_verdict,
            reconcile_persisted_paying_wallet_summary,
        )

        wallet = dict(getattr(self.state, "niche_wallet_brief", None) or {})
        wallet_class = wallet.get("wallet_class")
        wallet_evidence = wallet.get("evidence")
        verdict = getattr(self.state, "niche_difficulty_verdict", None)

        if verdict is not None:
            fact_pack = None
            try:
                pains = list(
                    getattr(getattr(self.state, "pain_point_analysis", None), "pain_points", None)
                    or []
                )
                ideas = list(
                    getattr(getattr(self.state, "idea_generation", None), "solution_ideas", None)
                    or []
                )
                niche_context = getattr(self.state, "niche_context", None)
                segments = getattr(
                    getattr(self.state, "audience_mapping", None), "audience_segments", None
                )
                distribution_ideas = [
                    idea
                    for idea in ideas
                    if getattr(idea, "winning_angle", None) == "distribution_seo"
                ]
                serp_owned_share = (
                    sum(1 for idea in distribution_ideas if getattr(idea, "_serp_owned", False))
                    / len(distribution_ideas)
                    if distribution_ideas
                    else None
                )
                fact_pack = assess_niche_difficulty(
                    pains,
                    ideas,
                    niche_context,
                    segments=segments,
                    niche_wallet_brief=wallet or None,
                    incumbent_map=list(
                        getattr(self.state, "niche_incumbent_map", None) or []
                    ) or None,
                    serp_owned_share=serp_owned_share,
                )
            except Exception as e:  # noqa: BLE001 - partial legacy inputs use verdict fallback
                logger.warning(
                    f"[Checkpoint] persisted verdict fact-pack reconstruction failed: {e}. "
                    "Using persisted deterministic fields."
                )

            niche = (
                getattr(getattr(self.state, "niche_context", None), "niche_description", None)
                or self.niche_description
                or None
            )
            self.state.niche_difficulty_verdict = (
                reconcile_persisted_niche_difficulty_verdict(
                    verdict,
                    wallet_class=wallet_class,
                    wallet_evidence=wallet_evidence,
                    fact_pack=fact_pack,
                    niche=niche,
                )
            )

        self.state.idea_portfolio_summary = reconcile_persisted_paying_wallet_summary(
            getattr(self.state, "idea_portfolio_summary", None),
            wallet_class=wallet_class,
            wallet_evidence=wallet_evidence,
        )

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
        pattern = self._get_checkpoint_pattern()

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
