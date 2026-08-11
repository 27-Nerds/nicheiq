"""
ResearchFlow - Main orchestration flow for the 16-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

import json
import math
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from crewai.flow.flow import Flow  # Flow = state container only; the @start/@listen graph was
# removed — all stages run via the _execute_remaining_stages sequential driver, never kickoff().

if TYPE_CHECKING:
    from ..models.research_state import NicheContext
from loguru import logger

from ..config.settings import settings
from ..crews import PainPointCrew, SEOStrategyCrew, UnifiedSolutionCrew
from ..crews.solution_refinement_crew import SolutionRefinementCrew
from ..crews.traffic_monetization_crew import TrafficMonetizationCrew
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.research_state import ResearchState
from ..report.utils.state_accessors import build_user_adjustments_summary
from ..tools.cached_serper_dev_tool import CachedSerperDevTool
from ..tools.reddit_tool import RedditCollectorTool
from ..tools.twitter_tool import TwitterCollectorTool
from ..utils.helpers import find_solution_by_name
from ..utils.keyword_filtering import check_keyword_relevance
from ..utils.segment_matching import match_pain_by_provenance, match_pain_to_segments, normalize_hub_name
from ..utils.score_refinement import (
    refine_cac_organic,
    refine_programmatic_opportunity,
    refine_scalability_score,
)
from ..utils.search_helpers import SearchHelper
from ..utils.seed_generation import SeedGenerator
from ..utils.token_monitor import ContentTokenMonitor, CostTracker
from ..utils.validation import KeywordRelevanceValidator
from .checkpoint_manager import CheckpointManager


class QualityGateStopException(Exception):
    """Raised when a quality gate intentionally stops the pipeline.

    This is not an error - it's an intentional stop due to insufficient
    data quality that would produce unreliable results.
    """

    def __init__(self, stage: int, reason: str, details: dict):
        self.stage = stage
        self.reason = reason
        self.details = details
        super().__init__(f"Quality gate at stage {stage}: {reason}")


def _best_segment_match(audience: str, names: list[str], threshold: float = 0.40, *,
                        preferred: str | None = None) -> str | None:
    """Fuzzy-match an audience string to the best segment name (stem-token overlap,
    reusing crew_guardrails._fuzzy_set_overlap). Returns the matched name when it clears
    `threshold`, else None.

    `preferred` (keyword-only) is a TIE-BREAK only — it never overrides a strictly higher
    score. Candidates within eps=1e-9 of the running best tie-break in order: the
    preferred name wins, then higher raw stem-token intersection, then stable-first
    (the earlier entry in `names` keeps its spot).

    Module-level (NOT a ResearchFlow method) on purpose: the CrewAI Flow metaclass wraps
    class methods as flow steps, which breaks a plain @staticmethod helper.
    """
    if not audience or not names:
        return None
    from ..utils.text_stemmer import stem_tokens
    from ..utils.validation.crew_guardrails import _fuzzy_set_overlap

    eps = 1e-9
    pref = (preferred or "").strip()
    audience_tokens = stem_tokens({t for t in str(audience).lower().split()})
    best_name, best_score, best_inter, best_is_pref = None, 0.0, -1, False
    for name in names:
        if not name:
            continue
        score = _fuzzy_set_overlap([audience], [name])
        if score <= 0.0 or score < best_score - eps:
            continue
        inter = len(audience_tokens & stem_tokens({t for t in str(name).lower().split()}))
        is_pref = bool(pref) and name == pref
        if best_name is None or score > best_score + eps:
            take = True
        elif is_pref and not best_is_pref:
            take = True  # tie within eps: preferred name wins
        elif is_pref == best_is_pref and inter > best_inter:
            take = True  # tie within eps: higher raw intersection wins
        else:
            take = False  # stable-first: keep the earlier candidate
        if take:
            best_name, best_score, best_inter, best_is_pref = name, score, inter, is_pref
    return best_name if (best_name is not None and best_score >= threshold) else None


def _shrink_gate_artifact(artifact: dict, list_fields: dict[str, str | None],
                          initial_caps: dict[str, int] | None = None,
                          max_size: int = 16384, label: str = "gate artifact") -> None:
    """Shared size guard for the composite G1/G2 gate artifacts (16KB budget each).

    `list_fields` maps artifact list keys -> the per-item string field to truncate as a
    last resort (None = the list items are plain strings). Sets
    `artifact["truncated"] = True` whenever ANY shrink fires, so the backend can reject a
    whole-list replacement patch built against a partial view (crossCheckGatePatch,
    jobs.ts) and the dossier can warn the analyst. Mutates in place; never raises.

    Module-level (NOT a ResearchFlow method) on purpose — see _best_segment_match.
    """
    try:
        if len(json.dumps(artifact)) <= max_size:
            return
        logger.warning(f"{label} exceeds {max_size}B, truncating lists")
        artifact["truncated"] = True
        for key, cap in (initial_caps or {}).items():
            artifact[key] = artifact[key][:cap]

        # Hard second check (Codex review finding 3, AMEND): the first truncation only
        # caps LIST LENGTH, not per-item field length — a run with unusually long titles
        # or names could still exceed the budget. Progressively shrink further (halving
        # list lengths, then truncating long string fields) until it fits; never emit an
        # oversized artifact.
        attempts = 0
        while len(json.dumps(artifact)) > max_size and attempts < 6:
            attempts += 1
            shrank = False
            for key in list_fields:
                if len(artifact[key]) > 1:
                    artifact[key] = artifact[key][: max(1, len(artifact[key]) // 2)]
                    shrank = True
            if not shrank:
                # Lists are already at their floor (<=1 item each) — truncate long
                # string fields as the last resort.
                for key, item_field in list_fields.items():
                    if item_field is None:
                        artifact[key] = [
                            (s[:117] + "...") if isinstance(s, str) and len(s) > 120 else s
                            for s in artifact[key]
                        ]
                    else:
                        for item in artifact[key]:
                            value = item.get(item_field)
                            if isinstance(value, str) and len(value) > 120:
                                item[item_field] = value[:117] + "..."

        if len(json.dumps(artifact)) > max_size:
            # Absolute last resort — never return an oversized artifact.
            logger.error(f"{label} still exceeds {max_size}B after truncation, dropping lists")
            keys = list(list_fields)
            for key in keys[1:]:
                artifact[key] = []
            if keys:
                artifact[keys[0]] = artifact[keys[0]][:1]
    except Exception as e:
        logger.warning(f"Failed to size-check {label}: {e}")


def finalize_graded_validation(
    validation_result: dict,
    graded_keywords: list[dict],
) -> dict:
    """Turn raw expansion metrics into a model-ready validation dict.

    ``seed_generation.calculate_validation_from_expansion`` reports
    ``expansion_pool_count`` — how many keywords the UNFILTERED expansion pool
    contributed. Semantic grading runs afterwards, and ``validated_count`` on
    CrewKeywordValidationResult means the GRADED, on-idea set, so the swap happens
    here and nowhere else. Measured live 2026-08-02: pool 50, graded 1 — publishing
    the pool count as "validated keywords" inflated demand in the selection
    rationale, the progress payload, the report table and the market-sizing prompt.

    The pool count is dropped rather than persisted: no consumer reads it, and adding
    a field to the ``extra='forbid'`` model would make a rollback reject the new
    checkpoints (checkpoint_manager clears the stage and silently re-spends DataForSEO).

    Mutates and returns ``validation_result``.
    """
    validation_result.pop("expansion_pool_count", None)
    validation_result["validated_keywords"] = graded_keywords
    validation_result["validated_count"] = len(graded_keywords)
    validation_result["accumulated_keywords_count"] = len(graded_keywords)
    return validation_result


def _calculate_difficulty_adjusted_score(
    validation: "CrewKeywordValidationResult",
) -> tuple[float | None, float | None, float | None]:
    """Recalculate keyword_demand_score including the difficulty factor (Stage 6-KV
    batched difficulty enrichment). Module-level so the formula is unit-testable.

    Demand-rescale fix (flow-weakness fix plan 2026-08, Step 2): both non-difficulty
    components now mirror the producer formula in
    ``seed_generation.calculate_validation_from_expansion`` instead of the old
    saturating approximations (volume_score used len(top_keywords) — capped at 5 —
    as denominator; avg_opportunity ignored per-keyword volume and saturation).

    Returns:
        (adjusted_score, avg_difficulty, rankability_factor).
        ``adjusted_score`` is ``None`` when ``validated_keywords`` is empty —
        graded-and-empty (correction 1): the keywords were graded and NONE
        individually passed, so demand is UNMEASURED. Returning the stale
        pre-grading ``keyword_demand_score`` here rewarded validation failure.
    """
    validated_keywords = validation.validated_keywords or []
    if not validated_keywords:
        # Graded-and-empty (or legacy checkpoint missing validated_keywords):
        # no per-keyword evidence — emit None, never a fabricated scalar.
        # Downstream skips the composite blend and two-tier ranks these below
        # validated-with-keywords solutions.
        return None, None, None

    # Extract difficulty values (may be None for some keywords)
    difficulties = [
        kw.get('keyword_difficulty')
        for kw in validated_keywords
        if kw.get('keyword_difficulty') is not None
    ]

    # Calculate average difficulty and rankability factor
    if difficulties:
        avg_difficulty = sum(difficulties) / len(difficulties)
        # Rankability factor: 1.0 for easy (0), 0.0 for hard (100)
        rankability_factor = 1 - (avg_difficulty / 100)
    else:
        avg_difficulty = None
        rankability_factor = None

    # volume_score: RELEVANCE-FILTERED keyword yield against the 20 seeds each
    # strategy attempt feeds into expansion. The denominator names the `count=20`
    # literal at the `generate_seeds_with_strategy(..., count=20)` call sites in
    # this file (the producer's own denominator, original_seed_count, is not
    # persisted).
    #
    # The numerator MUST be len(validated_keywords) — the graded, on-idea set.
    # `validated_count` now carries exactly that (finalize_graded_validation), but
    # checkpoints written before 2026-08 stored the UNFILTERED expansion pool there
    # (capped at keyword_quick_expansion_size=50). Measured live 2026-08-02:
    # validated_count=50 while len(validated_keywords)=1, so reading validated_count
    # saturated volume_score to 1.0 and reproduced the exact pre-fix inflation
    # (demand 0.9095 on a single on-idea keyword). Reading the list is resume-safe.
    volume_score = min(len(validation.validated_keywords or []) / 20, 1.0)

    # avg_opportunity: per-keyword producer formula (mirrors
    # seed_generation.calculate_validation_from_expansion exactly) — the old
    # aggregate `1 - avg_competition/100` ignored volume and saturation.
    opportunity_scores = []
    for kw in validated_keywords:
        volume = kw.get('search_volume') or 0
        competition = kw.get('competition_index') or 0
        volume_factor = min(volume / 1000, 1.0)
        competition_factor = 1 - (competition / 100)
        saturation_check = 1.0 if competition <= 60 else 0.7
        opportunity_scores.append(volume_factor * competition_factor * saturation_check)
    avg_opportunity = sum(opportunity_scores) / len(opportunity_scores)

    # New formula with difficulty: 55% volume + 25% opportunity + 20% rankability
    if rankability_factor is not None:
        adjusted_score = (
            (0.55 * volume_score) +
            (0.25 * avg_opportunity) +
            (0.20 * rankability_factor)
        )
    else:
        # Fall back to the producer's 60/40 weights when no difficulty data
        adjusted_score = (0.60 * volume_score) + (0.40 * avg_opportunity)

    return adjusted_score, avg_difficulty, rankability_factor


@dataclass
class PlatformSearchResult:
    """Return type for platform search pipelines (Stage 2 parallel execution)."""
    posts: list = field(default_factory=list)
    unique_results_count: int = 0
    relevant_urls_count: int = 0


class ResearchFlow(Flow[ResearchState]):
    """
    Main research flow orchestrating all 16 stages of the NicheIQ pipeline.

    Stages:
    1-4: Niche Input & Validation (Flow)
    5: Search & Discover (Flow + SerperDevTool)
    6: Pain Point Analysis (PainPointCrew)
    7-8.75: Unified Solution Pipeline (UnifiedSolutionCrew - ideation, competitive analysis, refinement, selection)
    8.8: Keyword Demand Validation (Flow - quick validation for top 3 solutions)
    8.85: Solution Refinement (SolutionRefinementCrew - strategic recommendations)
    9: Integrated Keyword Research + SEO Strategy (SEOStrategyCrew + DataForSEO)
    10: Final Report Generation (Flow)
    """

    def __init__(self, niche_description: str, allowed_project_types: list[str | None] = None, job_id: str | None = None, entry_mode: str | None = None, idea_focus: str = "auto"):
        """
        Initialize ResearchFlow with niche description.

        Args:
            niche_description: User's niche area description
            allowed_project_types: Optional list of allowed project types (saas, directory, aggregator, comparison-tool, marketplace)
            job_id: Optional job identifier for per-job ChromaDB collection isolation
            entry_mode: Optional entry mode ('idea', 'audience', 'discovery') for future mode-aware prompts
            idea_focus: GTM focus steer ('auto' | 'novelty' | 'distribution'); 'auto' is neutral
        """
        super().__init__()

        # Fail fast if any tier is pointed at an OpenRouter model that can't run there
        # (landing-page tiers raise; other UNSAFE tiers warn). Covers worker + CLI runs.
        from ..utils.llm_service import validate_openrouter_tier_compatibility
        validate_openrouter_tier_compatibility()

        # Store niche description for use in flow methods
        self.niche_description = niche_description
        self.allowed_project_types = allowed_project_types
        self.idea_focus = idea_focus or "auto"
        self.job_id = job_id or str(uuid.uuid4())
        self.state.job_id = self.job_id
        self.entry_mode = entry_mode

        # Track Knowledge objects created during the run for cleanup
        self._knowledge_objects: list = []

        # Initialize tools
        self.search_tool = CachedSerperDevTool()  # session-cached: benefits the whole run
        self.reddit_tool = RedditCollectorTool()
        self.twitter_tool = TwitterCollectorTool()
        if settings.enable_hackernews:
            from ..tools.hackernews_tool import HackerNewsCollectorTool
            self.hackernews_tool = HackerNewsCollectorTool()
        else:
            self.hackernews_tool = None
        if settings.enable_youtube:
            from ..tools.youtube_tool import YouTubeCollectorTool
            self.youtube_tool = YouTubeCollectorTool()
        else:
            self.youtube_tool = None

        # Import DataForSEO tool for iterative enrichment
        from ..tools.dataforseo_tool import DataForSEOExpandTool
        self.dataforseo_tool = DataForSEOExpandTool()

        logger.info(f"ResearchFlow initialized for niche: {niche_description[:100]}...")

        # Initialize cost tracker for run-level cost monitoring
        self.cost_tracker = CostTracker()

        # Initialize checkpoint manager
        self.checkpoint_mgr = CheckpointManager(
            niche_description=niche_description,
            state=self.state,
            allowed_project_types=allowed_project_types,
            job_id=self.job_id,
            entry_mode=self.entry_mode,
        )

        # Optional progress callback for web worker integration
        # Can be set after initialization: flow.progress_callback = callback
        # Callback signature: (stage_num: float, stage_name: str, status: str) -> None
        self.progress_callback = None

        # Lock for thread-safe state mutation in parallel competitive analysis
        self._competitive_lock = threading.Lock()

    # ========== KNOWLEDGE CLEANUP ==========

    def register_knowledge(self, knowledge) -> None:
        """Register a Knowledge object for cleanup at the end of the run."""
        if knowledge is not None:
            self._knowledge_objects.append(knowledge)

    def cleanup_collections(self) -> None:
        """
        Delete all ChromaDB collections created during this run.

        Uses Knowledge.reset() which correctly handles the ``knowledge_``
        prefix that CrewAI's KnowledgeStorage adds internally.
        Each reset is wrapped in try/except so concurrent workers or
        missing collections don't propagate errors.
        """
        if not self._knowledge_objects:
            return
        logger.info(f"Cleaning up {len(self._knowledge_objects)} ChromaDB knowledge collections...")
        for knowledge_obj in self._knowledge_objects:
            try:
                knowledge_obj.reset()
            except Exception as e:
                logger.debug(f"Knowledge cleanup skipped (already removed or unavailable): {e}")
        self._knowledge_objects.clear()

    # ========== HELPER METHODS ==========

    def _execute_with_retry(self, func, max_retries: int = 3, backoff: float = 2.0, operation_name: str = "operation"):
        """
        Execute function with exponential backoff retry for API failures.

        Args:
            func: Function to execute
            max_retries: Maximum retry attempts
            backoff: Base backoff time in seconds (exponentially increased)
            operation_name: Description of operation for logging

        Returns:
            Result of function call

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except (TimeoutError, ConnectionError) as e:
                last_exception = e
                if attempt == max_retries - 1:
                    logger.error(f"{operation_name} failed after {max_retries} attempts")
                    raise
                wait_time = backoff ** attempt
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
            except Exception as e:
                # Don't retry on non-network errors
                logger.error(f"{operation_name} failed with non-retryable error: {e}")
                raise

        # Should never reach here, but for type safety
        if last_exception:
            raise last_exception

    def _emit_progress(self, stage_num: float, stage_name: str | None, status: str, artifact: dict | None = None) -> None:
        """
        Emit progress update via callback if set.

        Used for web worker integration to publish real-time updates via Redis.

        Args:
            stage_num: Stage number (e.g., 1, 5, 6, 14)
            stage_name: Human-readable stage name (None to let callback look it up)
            status: 'running', 'completed', or 'failed'
            artifact: Optional lightweight artifact dict (<2KB) for stage results
        """
        if self.progress_callback:
            try:
                self.progress_callback(stage_num, stage_name, status, artifact)
            except Exception as e:
                # Re-raise cancellation exceptions — must not be swallowed
                if type(e).__name__ == "JobCancelledException":
                    raise
                logger.warning(f"Progress callback failed for stage {stage_num}: {e}")

    def resume_from_checkpoint(self, checkpoint_path: Path | None = None,
                               allow_cross_job: bool = False) -> bool:
        """
        Resume research flow from checkpoint.

        Args:
            checkpoint_path: Explicit checkpoint folder path, or None to auto-detect
            allow_cross_job: Permit auto-detect to fall back to a different job's checkpoint
                for the same niche (CLI --resume only). Ignored when checkpoint_path is given.

        Returns:
            True if resumed successfully, False otherwise
        """
        if not settings.checkpoint_enabled:
            logger.warning("Checkpointing is disabled - cannot resume")
            return False

        # Find checkpoint
        checkpoint = Path(checkpoint_path) if isinstance(checkpoint_path, str) else (
            checkpoint_path or self.checkpoint_mgr.find_latest_checkpoint(allow_cross_job=allow_cross_job))
        if not checkpoint:
            logger.info("No checkpoint found for this niche")
            return False

        # Load checkpoint
        if not self.checkpoint_mgr.load_checkpoint_folder(checkpoint):
            return False

        # Seed the cost tracker with Phase-1 usage if this checkpoint carries it, so a
        # Phase-2 continuation reports cumulative cost. Only interactive Phase-1 writes the
        # file; one-shot / catalog deep-research never do, so there is no double-count.
        cost_rows = self.checkpoint_mgr.load_cost_breakdown()
        if cost_rows:
            self.cost_tracker.load_state(cost_rows)
            logger.info(f"Restored {len(cost_rows)} cost usage(s) from checkpoint")

        # Re-sync entry_mode restored from checkpoint metadata onto the flow (load only
        # restores ResearchState; the flow attr won't update by itself). Keeps audience
        # framing correct if Stage 1 re-runs on resume. (Regenerate/phase-2 read framing from
        # the restored niche_context, which already carries the resolved fields.)
        if getattr(self.checkpoint_mgr, "entry_mode", None) is not None:
            self.entry_mode = self.checkpoint_mgr.entry_mode

        # Re-sync the user constraints restored into ResearchState back onto the flow attrs — the crew
        # reads self.allowed_project_types / self.idea_focus, NOT state, so without this a resumed or
        # regenerate run silently drops the original constraints (the latent allowed_project_types bug).
        if getattr(self.state, "allowed_project_types", None) is not None:
            self.allowed_project_types = self.state.allowed_project_types
        if getattr(self.state, "idea_focus", None):
            self.idea_focus = self.state.idea_focus

        # "Check my idea" resume: rebind the working niche to the derived market. Worker
        # retries rebuild the flow with the raw pitch and Phase-2 with "" — and Stage 1
        # only re-runs when its checkpoint is absent — so without this rebind the raw
        # pitch (or an empty string) would reach thread validation on any resumed
        # validate run. Contract: gate on state.user_idea_text, never flow.entry_mode
        # (several re-entry tasks construct ResearchFlow without entry_mode).
        if (getattr(self.state, "user_idea_text", None)
                and getattr(self.state, "niche_context", None) is not None
                and (getattr(self.state.niche_context, "niche_description", "") or "").strip()):
            self.niche_description = self.state.niche_context.niche_description

        # Cleanup old checkpoints
        self.checkpoint_mgr.cleanup_old_checkpoints()

        logger.info(f"Resume from stage {self.state.current_stage}")
        return True

    def run_with_resume(self, auto_resume: bool = True, stop_after_phase: int | None = None,
                        allow_cross_job: bool = False, stop_after_stage: float | None = None) -> str:
        """
        Execute research pipeline with checkpoint resume support.

        Args:
            auto_resume: If True, automatically resume from latest checkpoint if available
            stop_after_phase: If set, stop execution after this phase completes (1 = after solution pipeline)
            allow_cross_job: Permit auto-resume to adopt a different job's checkpoint for the
                same niche (CLI --resume only; worker retries keep the default False).
            stop_after_stage: Guided-mode (chatMode) gate stop — distinct from stop_after_phase.
                1 stops after Stage 1 (niche validation, G1); 4 stops after Stage 4 (audience
                mapping, G2), before Stage 5 runs. Unlike stop_after_phase, a stage-gate stop
                does NOT materialize a preview report (the run isn't done with Phase 1 yet).

        Returns:
            Path to final report
        """
        # Fresh run/resume: clear any systemic-LLM breaker from a previous job in this
        # process (a fixed account must not stay poisoned).
        from ..utils.llm_service import LLMService as _LLMSvc
        _LLMSvc.reset_systemic()

        # Try to resume from checkpoint
        if auto_resume and self.resume_from_checkpoint(allow_cross_job=allow_cross_job):
            logger.info("Resuming from checkpoint - skipping completed stages")

            # Emit progress for the stage we're resuming from
            # Pass None for stage_name - the callback will look it up from STAGE_NAMES
            self._emit_progress(self.state.current_stage, None, "running")

            return self._execute_remaining_stages(
                stop_after_phase=stop_after_phase, stop_after_stage=stop_after_stage)

        # No checkpoint or resume failed - run normal flow
        logger.info("Starting fresh research run")

        # Fresh full run: the single execution path for ALL cases. There is no CrewAI
        # @start/@listen graph; _execute_remaining_stages drives every stage directly.
        # current_stage defaults to 1, completed_stages is empty, so all stages run sequentially.
        return self._execute_remaining_stages(
            stop_after_phase=stop_after_phase, stop_after_stage=stop_after_stage)

    def _deep_research_audience_directive(self) -> str:
        """Front-load WHO the idea must serve + their real frustrations/current tools for the
        post-selection deep research. Empty string when no audience resolved — so it's a pure
        no-op then. DISTINCT from the Phase-1 audience-aware search/pain-mining bias.
        """
        nc, am = self.state.niche_context, self.state.audience_mapping
        aud = (getattr(nc, "resolved_primary_audience", None) or getattr(nc, "user_target_audience", None)) if nc else None
        if not aud:
            return ""
        tools = ", ".join((getattr(am, "tools_currently_used", None) or [])[:4]) if am else ""
        frus = ", ".join((getattr(am, "frustrations_with_existing", None) or [])[:4]) if am else ""
        bits = [f"**RESOLVED AUDIENCE (target the analysis at THESE users):** {aud}."]
        if tools:
            bits.append(f"Tools they use today: {tools}. Profile any that are genuine SUBSTITUTES for "
                        f"this solution, but do NOT drop the solution's direct competitors to make room — "
                        f"treat the rest as switching-cost context, not competitors.")
        if frus:
            bits.append(f"Their top frustrations with current tools (the gaps to verify): {frus}.")
        return "\n" + " ".join(bits) + "\n"

    def analyze_single_solution_competitors(self, solution_name: str) -> dict:
        """Run competitive analysis for a single solution on demand.

        Creates a mini 1-task crew with the competitive_researcher agent and a custom
        task description (standalone, not relying on CrewAI context chaining).
        Updates state.competitive_analysis with the result.

        Returns:
            Dict with solution_name, analyzed flag, and competitive_landscape data.
        """
        from crewai import Crew, Task
        from ..models.competitor import CompetitiveLandscape, CompetitiveAnalysisResult

        solution = find_solution_by_name(solution_name, self.state.idea_generation.solution_ideas)
        if not solution:
            logger.warning(f"Solution '{solution_name}' not found in state — cannot analyze competitors")
            return {"solution_name": solution_name, "analyzed": False, "error": "solution_not_found"}

        # Build standalone task description with embedded solution context
        niche_desc = ""
        if self.state.niche_context:
            niche_desc = self.state.niche_context.niche_description
        features_str = ", ".join(solution.core_features[:7]) if solution.core_features else "N/A"
        personas_str = ", ".join(
            (p if isinstance(p, str) else getattr(p, "persona_name", str(p)))
            for p in (solution.target_personas or [])[:4]
        )

        # Angle-conditioned research: front-load the idea's winning-angle defensibility question.
        # For novel ideas it focuses competitor research on the nearest rival's gap + clone speed;
        # for distribution_seo on who owns the SERP + beatability; for workflow on switching cost.
        angle_directive = ""
        from ..utils.angle_brief import build_angle_brief
        _ab = build_angle_brief(solution).get("angle_brief", "")
        if _ab:
            angle_directive = f"\n**ANGLE PRIORITY (answer this first):** {_ab}\n"

        # Audience-conditioned deep research (gated; empty -> no change). The crew task has no
        # inputs= dict, so the directive is embedded as text in the task description.
        audience_directive = self._deep_research_audience_directive()

        # Market-data handoff (mirrors angle_directive): the Phase-1 incumbent/wallet probes
        # already web-verified this idea's parity + the niche's real incumbents — hand them to
        # Stage-2 competitor research once instead of letting it re-discover them from scratch.
        # Niche anchor vocabulary (same block the Reddit/HN query generators get). The
        # solution name is INVENTED and can carry a word that belongs to another industry
        # ("HouseNut" = a venue's fixed cost, not household budgeting); without the niche's
        # named entities and excluded senses in front of it the researcher can profile the
        # wrong market entirely (live-caught 2026-08-03: Mint/YNAB for a live-music niche).
        from ..utils.validation.niche_anchor import format_anchor_block
        anchor_directive = format_anchor_block(self.state.niche_context)

        market_directive = ""
        from ..utils.market_brief import build_market_brief
        _mb = build_market_brief(self.state, solution)
        _mb_parts = [p for p in (_mb.get("market_brief", ""), _mb.get("market_incumbent_table", "")) if p]
        if _mb_parts:
            market_directive = "\n**MARKET REALITY (already web-verified — deepen, don't re-discover):**\n" + "\n\n".join(_mb_parts) + "\n"

        task_description = f"""Analyze the competitive landscape for a specific solution.

**Solution:** {solution.solution_name}
**Description:** {solution.description}
**Project Type:** {solution.project_type}
**Value Proposition:** {solution.value_proposition}
**Core Features:** {features_str}
**Target Personas:** {personas_str}
**Niche:** {niche_desc}
{anchor_directive}{angle_directive}{audience_directive}{market_directive}

WORKFLOW:
1. Generate search queries for this solution's competitive space
2. Search for competitors using available tools
3. Profile top 5-8 competitors (URL, features, pricing, positioning)
4. Identify market gaps and differentiation opportunities
5. Assess competitive intensity (LOW/MEDIUM/HIGH)
6. Recommend positioning strategy

OUTPUT: CompetitiveLandscape with solution_name, competitors, market_gaps,
differentiation_opportunities, competitive_intensity, recommended_positioning, pricing_insights.

RULES:
- Every competitor must have a verifiable source (URL or mention)
- Features must be from actual websites (not assumed)
- Every competitor must serve the **Niche** above. A product from another industry is not
  a competitor no matter how well its name matches this solution's name — run step 2 and
  report what the searches return, never what the solution's name suggests
- If no competitors found, report honestly
- Be comprehensive with market gaps — list ALL gaps found
"""

        # Create a standalone crew with the competitive researcher agent
        unified_crew = UnifiedSolutionCrew(
            pain_point_analysis=self.state.pain_point_analysis,
            social_content=self.state.social_content,
            allowed_project_types=getattr(self, "allowed_project_types", None),
            niche_context=self.state.niche_context,
            audience_mapping=getattr(self.state, "audience_mapping", None),
            checkpoint_mgr=self.checkpoint_mgr,
            job_id=self.state.job_id,
            idea_focus=getattr(self, "idea_focus", "auto"),
            cost_tracker=self.cost_tracker,
        )

        researcher_agent = unified_crew.competitive_researcher()
        analysis_task = Task(
            description=task_description,
            expected_output="CompetitiveLandscape Pydantic model with all fields populated.",
            agent=researcher_agent,
            output_pydantic=CompetitiveLandscape,
        )

        mini_crew = Crew(
            agents=[researcher_agent],
            tasks=[analysis_task],
            verbose=True,
        )

        logger.info(f"Running competitive analysis crew for: {solution_name}")
        crew_output = mini_crew.kickoff()

        landscape = crew_output.pydantic
        if landscape is None:
            raise ValueError(f"Competitive analysis returned None for {solution_name}")

        landscape = self._guard_landscape_on_niche(
            landscape, solution_name, mini_crew, analysis_task, task_description
        )

        # Ensure solution_name matches
        landscape.solution_name = solution_name

        # Thread-safe: lock all shared state mutations (supports parallel execution)
        with self._competitive_lock:
            # Record crew cost
            if hasattr(mini_crew, 'usage_metrics') and mini_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 7.5 - Competitive Analysis (On-Demand)",
                    usage_metrics=mini_crew.usage_metrics,
                    model=settings.brainstorm_llm,
                )

            # Build/update state.competitive_analysis
            if self.state.competitive_analysis is None:
                # Generate strategic recommendations from landscape data
                strategic_recs = self._generate_strategic_recommendations(landscape)
                top_opps = landscape.differentiation_opportunities[:5] if landscape.differentiation_opportunities else ["No opportunities identified"]
                self.state.competitive_analysis = CompetitiveAnalysisResult(
                    solution_landscapes=[landscape],
                    top_opportunities=top_opps,
                    strategic_recommendations=strategic_recs,
                )
            else:
                # Replace or append landscape by solution name
                existing = self.state.competitive_analysis.solution_landscapes
                replaced = False
                for i, ls in enumerate(existing):
                    if ls.solution_name.strip().lower() == solution_name.strip().lower():
                        existing[i] = landscape
                        replaced = True
                        break
                if not replaced:
                    existing.append(landscape)
                # Update strategic recommendations
                self.state.competitive_analysis.strategic_recommendations = (
                    self._generate_strategic_recommendations(landscape)
                )
                # Update top opportunities
                if landscape.differentiation_opportunities:
                    self.state.competitive_analysis.top_opportunities = landscape.differentiation_opportunities[:5]

            # Save to checkpoint
            self.checkpoint_mgr.save_stage("stage_5_5_competitive", self.state.competitive_analysis)

        result_data = landscape.model_dump(mode='json')
        return {
            "solution_name": solution_name,
            "analyzed": True,
            "competitive_landscape": result_data,
        }

    def _guard_landscape_on_niche(
        self,
        landscape: "CompetitiveLandscape",
        solution_name: str,
        mini_crew,
        analysis_task,
        task_description: str,
    ) -> "CompetitiveLandscape":
        """Reject an off-niche competitive landscape once, then caveat it.

        The researcher can skip its searches entirely and answer from the solution name's
        prior, returning a landscape from a different industry (live-caught 2026-08-03:
        "HouseNutIndex" → Mint + YNAB, zero searches). The check is deterministic — the
        landscape must share at least one niche vocabulary term — and DOWNGRADE-ONLY: a
        landscape that fails twice is kept verbatim and stamped, never rewritten, so the
        report can mark its counts/saturation/gaps as unverified instead of reading them
        as "the space is uncrowded".
        """
        from ..utils.validation.competitor_relevance import assess_landscape_relevance

        verdict = assess_landscape_relevance(landscape, self.state.niche_context)
        if not verdict["off_niche"]:
            return landscape

        logger.warning(
            f"[Competitive] '{solution_name}' landscape is off-niche "
            f"(no niche vocabulary in any competitor or gap) — re-running once"
        )
        analysis_task.description = task_description + """

**RETRY — YOUR PREVIOUS ANSWER WAS REJECTED.**
Not one competitor, market gap or positioning line you returned mentioned this niche. You
profiled a different industry, most likely because the solution's invented name reuses a
word from it. Start from the searches this time: call generate_competitor_queries, run the
returned queries with the search tool, and profile ONLY products the results show serving
the **Niche** above. If the searches surface nothing, return an empty competitors list and
say so — an honest empty landscape is correct, a foreign one is not.
"""
        try:
            retry_landscape = mini_crew.kickoff().pydantic
        except Exception as e:  # noqa: BLE001 — a failed retry must not lose the first result
            logger.warning(f"[Competitive] off-niche retry failed for '{solution_name}': {e}")
            retry_landscape = None

        if retry_landscape is not None:
            retry_verdict = assess_landscape_relevance(retry_landscape, self.state.niche_context)
            if not retry_verdict["off_niche"]:
                logger.info(f"[Competitive] '{solution_name}' retry returned an on-niche landscape")
                return retry_landscape
            landscape = retry_landscape
            verdict = retry_verdict

        landscape.off_niche_caveat = verdict["caveat"]
        # pipeline_degradations is the run-wide degradation ledger; it is surfaced verbatim
        # in data_quality_summary.quality_caveats.
        degradation = f"{solution_name}: {verdict['caveat']}"
        if degradation not in self.state.pipeline_degradations:
            self.state.pipeline_degradations.append(degradation)
        logger.warning(
            f"[Competitive] '{solution_name}' still off-niche after retry — landscape kept "
            "with an off_niche_caveat; its competitor/saturation/gap claims are unverified"
        )
        return landscape

    def _generate_strategic_recommendations(self, landscape: "CompetitiveLandscape") -> str:
        """Generate strategic recommendations text from a competitive landscape (min 50 chars).

        Shared with the report (utils/competitive_summary), which rebuilds this for the
        SELECTED solution — the state field this writes to is a single scalar that every
        landscape in the top-N overwrites, so it ends the run describing whichever idea
        happened to be analysed last.
        """
        from ..utils.competitive_summary import build_strategic_recommendations

        return build_strategic_recommendations(landscape)

    def _validate_stage_prerequisites(self, stage_num: float) -> bool:
        """
        Validate that required data exists before executing a stage.

        Args:
            stage_num: Stage number to validate prerequisites for

        Returns:
            True if prerequisites are met, False if stage should be skipped
        """
        prerequisites = {
            3: lambda: (
                self.state.social_content is not None and
                (bool(self.state.social_content.reddit_posts) or bool(self.state.social_content.twitter_threads) or bool(self.state.social_content.generic_posts))
            ),
            4: lambda: (
                self.state.social_content is not None and
                self.state.pain_point_analysis is not None
            ),
            5: lambda: (
                self.state.pain_point_analysis is not None and
                bool(self.state.pain_point_analysis.pain_points)
            ),
            5.5: lambda: (
                self.state.idea_generation is not None and
                bool(self.state.idea_generation.solution_ideas)
            ),
            5.7: lambda: (
                getattr(settings, 'keyword_validation_enabled', True) and
                self.state.solution_selection is not None and
                bool(getattr(self.state.solution_selection, 'all_solution_scores', []))
            ),
            5.8: lambda: (
                getattr(settings, 'solution_refinement_enabled', True) and
                self.state.solution_selection is not None and
                self.state.keyword_validation_results is not None
            ),
            6: lambda: (
                self.state.solution_selection is not None and
                self.state.idea_generation is not None
            ),
            6.5: lambda: (
                self.state.keyword_validation_results is not None and
                self.state.social_content is not None and
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            7: lambda: (
                self.state.idea_generation is not None and
                bool(self.state.idea_generation.solution_ideas) and
                self.state.seo_strategy_report is not None
            ),
            8: lambda: (
                self.state.pricing_strategies is not None and
                self.state.idea_generation is not None
            ),
            9: lambda: (
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            10: lambda: (
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            11: lambda: (
                settings.seo_refinement_enabled and
                self.state.seo_strategy_report is not None and
                self.state.solution_selection is not None
            ),
            13.5: lambda: (
                self.state.solution_selection is not None
            ),
        }

        # If no prerequisites defined, allow execution
        if stage_num not in prerequisites:
            return True

        # Check prerequisites
        try:
            return prerequisites[stage_num]()
        except Exception as e:
            logger.warning(f"Error checking prerequisites for stage {stage_num}: {e}")
            return False

    def _calculate_trend_metrics(self, monthly_searches: list[dict]) -> dict:
        """
        Calculate trend metrics from 12-month historical search data.

        Args:
            monthly_searches: List of dicts with year, month, search_volume

        Returns:
            Dict with trend_direction, trend_score, seasonality_index, is_evergreen
        """
        if not monthly_searches or len(monthly_searches) < 2:
            return {
                "trend_direction": "unknown",
                "trend_score": 0.0,
                "seasonality_index": 0.0,
                "is_evergreen": False
            }

        # Sort by date (newest first)
        sorted_data = sorted(
            monthly_searches,
            key=lambda x: (x.get("year", 0), x.get("month", 0)),
            reverse=True
        )

        volumes = [m.get("search_volume", 0) for m in sorted_data]

        # Trend direction: Compare recent 3 months vs older 3 months
        recent_avg = sum(volumes[:3]) / 3 if len(volumes) >= 3 else sum(volumes) / len(volumes)
        older_avg = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else sum(volumes) / len(volumes)

        if older_avg > 0:
            trend_pct = ((recent_avg - older_avg) / older_avg) * 100
        else:
            trend_pct = 0

        # Trend direction thresholds (symmetric ±20% thresholds)
        # Google Keyword Planner uses bucketed volumes where adjacent bucket jumps
        # are 22-40%, so ±20% filters single-bucket noise while preserving genuine shifts.
        # Low-volume noise floor: if both averages < 50, classify as stable
        if recent_avg < 50 and older_avg < 50:
            trend_direction = "stable"
        elif trend_pct > 20:
            trend_direction = "rising"
        elif trend_pct < -20:
            trend_direction = "declining"
        else:
            trend_direction = "stable"

        # Trend score: -1.0 to 1.0 (capped)
        trend_score = max(-1.0, min(1.0, trend_pct / 100))

        # Seasonality: coefficient of variation (std/mean)
        mean_vol = sum(volumes) / len(volumes) if volumes else 0
        if mean_vol > 0:
            variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
            std_dev = variance ** 0.5
            seasonality_index = min(1.0, std_dev / mean_vol)
        else:
            seasonality_index = 0.0

        # Evergreen: Low seasonality + stable/rising trend
        is_evergreen = seasonality_index < 0.3 and trend_direction != "declining"

        return {
            "trend_direction": trend_direction,
            "trend_score": round(trend_score, 2),
            "seasonality_index": round(seasonality_index, 2),
            "is_evergreen": is_evergreen,
            # For market-level aggregate growth (volume_growth_rate)
            "recent_avg": recent_avg,
            "older_avg": older_avg,
        }

    def _aggregate_keyword_trends(self) -> dict | None:
        """
        Aggregate per-keyword trends into market-level summary for Stage 11.

        Uses enriched keywords from Phase 6c to calculate:
        - Distribution of rising/stable/declining keywords
        - Percentage of search volume from rising keywords
        - Lists of seasonal and evergreen keywords
        - Overall market momentum assessment

        Returns:
            Dict with trend_distribution, rising_volume_pct, seasonal/evergreen keywords,
            market_momentum, or None if no enriched keywords available
        """
        enriched_keywords = self.state.seo_enriched_keywords
        if not enriched_keywords:
            logger.debug("[_aggregate_keyword_trends] No enriched keywords available")
            return None

        trends = {"rising": 0, "stable": 0, "declining": 0, "unknown": 0}
        total_volume = 0
        rising_volume = 0
        seasonal_keywords = []
        evergreen_keywords = []
        aggregate_recent = 0.0
        aggregate_older = 0.0

        for kw in enriched_keywords:
            monthly_searches = kw.get("monthly_searches", [])
            metrics = self._calculate_trend_metrics(monthly_searches)
            trends[metrics["trend_direction"]] += 1
            vol = kw.get("search_volume", 0)
            total_volume += vol
            aggregate_recent += metrics.get("recent_avg", 0) or 0
            aggregate_older += metrics.get("older_avg", 0) or 0

            if metrics["trend_direction"] == "rising":
                rising_volume += vol
            if metrics["seasonality_index"] > 0.3:
                seasonal_keywords.append({
                    "keyword": kw.get("keyword", ""),
                    "seasonality": metrics["seasonality_index"]
                })
            if metrics["is_evergreen"]:
                evergreen_keywords.append({
                    "keyword": kw.get("keyword", ""),
                    "volume": vol
                })

        # Sort by relevance (seasonality for seasonal, volume for evergreen)
        seasonal_keywords.sort(key=lambda x: x["seasonality"], reverse=True)
        evergreen_keywords.sort(key=lambda x: x["volume"], reverse=True)

        # Determine market momentum (percentage-based, excludes unknowns)
        known_total = trends["rising"] + trends["stable"] + trends["declining"]
        if known_total < 5:
            market_momentum = "Stable"
        else:
            rising_pct = trends["rising"] / known_total
            declining_pct = trends["declining"] / known_total
            if rising_pct > 0.35 and rising_pct > declining_pct:
                market_momentum = "Growing"
            elif declining_pct > 0.50:
                market_momentum = "Declining"
            else:
                market_momentum = "Stable"

        # Market-level volume growth from the SAME ±20% + <50/mo noise-floor
        # thresholds used per keyword (commit 0ef15e3's noise filtering) —
        # replaces the LLM's "estimate from the trend data" guess.
        if aggregate_recent < 50 and aggregate_older < 50:
            volume_growth_rate = "Unknown"
        elif aggregate_older > 0:
            agg_pct = (aggregate_recent - aggregate_older) / aggregate_older * 100
            if agg_pct > 20:
                volume_growth_rate = f"+{agg_pct:.0f}% over the 12-month window"
            elif agg_pct < -20:
                volume_growth_rate = f"{agg_pct:.0f}% over the 12-month window"
            else:
                volume_growth_rate = "Stable"
        else:
            volume_growth_rate = "Unknown"

        return {
            "trend_distribution": trends,
            "rising_volume_pct": (rising_volume / total_volume * 100) if total_volume else 0,
            "volume_growth_rate": volume_growth_rate,
            "total_keywords_analyzed": len(enriched_keywords),
            "top_seasonal_keywords": [kw["keyword"] for kw in seasonal_keywords[:5]],
            "top_evergreen_keywords": [kw["keyword"] for kw in evergreen_keywords[:10]],
            "evergreen_count": len(evergreen_keywords),
            "seasonal_count": len(seasonal_keywords),
            "market_momentum": market_momentum
        }

    def _record_pain_anchor_coverage(self, analysis) -> None:
        """Record dataset-level niche-anchor coverage into drift telemetry.

        NON-SCORING: computes the fraction of pain-point evidence quotes that
        contain a niche-anchor term and stores it on state for the Stage-10 caveat.
        Never raises; no-op when anchors inactive.
        """
        try:
            ctx = self.state.niche_context
            # Coverage vocabulary = compound/entity names PLUS audience jargon
            # (reconstitution, pinning, subq, BAC water...). On-niche quotes very
            # often use jargon without naming a specific compound, so entity-only
            # matching badly under-counts coverage and would emit a false drift caveat.
            anchor_terms = list(getattr(ctx, "anchor_entities", []) or []) if ctx else []
            jargon = list(getattr(ctx, "audience_jargon", []) or []) if ctx else []
            coverage_terms = anchor_terms + jargon
            if len(anchor_terms) < 3 or not analysis or not analysis.pain_points:
                return
            from ..utils.validation.niche_anchor import anchor_coverage, build_anchor_matchers
            matchers = build_anchor_matchers(coverage_terms)
            quotes = [
                q for pp in analysis.pain_points
                for q in (getattr(pp, "representative_quotes", None) or [])
            ]
            if not quotes:
                return
            coverage = anchor_coverage(quotes, matchers)
            self.state.niche_drift_telemetry["pain_evidence_anchor_coverage"] = round(coverage, 3)
            logger.info(
                f"[DRIFT] Pain-evidence niche-anchor coverage: {coverage:.0%} "
                f"({len(quotes)} quotes)"
            )
        except Exception as e:
            logger.debug(f"[DRIFT] anchor coverage telemetry skipped: {e}")

    def _validate_pain_point_quality(self, analysis) -> tuple[str, float]:
        """
        Validate pain point analysis quality and return tier classification.

        Uses evidence-based metrics to measure research quality (how real and
        well-sourced the data is), NOT niche attractiveness. Severity, WTP, and
        opportunity scores measure the niche itself and belong in the go/no-go
        verdict, not here.

        Evidence metrics:
        - unique_source_count: How many distinct Reddit posts provide evidence
        - subreddit_diversity: Cross-community validation (unique subreddits)
        - quote_density: Average quotes per pain point (evidence depth)
        - pain_point_count: Number of distinct problems identified

        Tiers:
        - GOLD: Broad, diverse evidence across multiple communities
        - SILVER: Adequate evidence from multiple sources
        - BRONZE: Minimum viable evidence to proceed
        - INSUFFICIENT: Below minimum threshold, should not proceed

        Args:
            analysis: PainPointAnalysisResult object from Stage 6

        Returns:
            Tuple of (quality_tier: str, confidence_score: float)
        """
        from ..models.pain_point import PainPointAnalysisResult

        if not isinstance(analysis, PainPointAnalysisResult):
            logger.error(f"Invalid analysis type: {type(analysis)}")
            return ("INSUFFICIENT", 0.0)

        if not analysis.pain_points:
            logger.warning("No pain points identified")
            return ("INSUFFICIENT", 0.0)

        # Calculate evidence-based quality metrics
        pain_points = analysis.pain_points
        total_count = len(pain_points)

        # Quote evidence density (average quotes per pain point)
        quote_density = sum(len(pp.representative_quotes) for pp in pain_points) / total_count if total_count > 0 else 0

        # Unique source count: distinct Reddit posts providing evidence across all pain points
        all_source_ids = set(
            sid for pp in pain_points for sid in pp.source_post_ids if sid
        )
        unique_source_count = len(all_source_ids)

        # Observability: warn if pain points have quotes but no source attribution
        for pp in pain_points:
            if pp.representative_quotes and not any(pp.source_post_ids):
                logger.warning(
                    f"Pain point '{pp.title[:50]}' has {len(pp.representative_quotes)} quotes "
                    f"but no source attribution — possible vector search failure"
                )

        # Subreddit diversity: unique subreddits across all source posts
        # Build post_id → subreddit lookup from social content
        post_id_to_subreddit: dict[str, str] = {}
        if self.state.social_content:
            for post in self.state.social_content.reddit_posts:
                post_id_to_subreddit[post.post_id] = post.subreddit

        # Map source_post_ids to subreddits, count unique
        subreddits_found: set[str] = set()
        unresolvable_ids: list[str] = []
        for sid in all_source_ids:
            subreddit = post_id_to_subreddit.get(sid)
            if subreddit:
                subreddits_found.add(subreddit)
            else:
                unresolvable_ids.append(sid)

        subreddit_diversity = len(subreddits_found)

        if unresolvable_ids:
            logger.warning(
                f"{len(unresolvable_ids)} source_post_ids could not be resolved to a subreddit "
                f"(posts may have been quality-filtered during collection). "
                f"Subreddit diversity may be undercounted."
            )

        # Cross-platform validation (for future dual-platform mode)
        cross_platform_count = 0
        for pp in pain_points:
            if pp.source_platforms and len(pp.source_platforms) > 1:
                cross_platform_count += 1

        # Determine platform mode
        single_platform_mode = not settings.enable_twitter or not settings.enable_reddit

        # Evidence-based weights — no LLM-assessed niche metrics
        if single_platform_mode:
            weights = {
                "unique_source_count": 0.30,
                "subreddit_diversity": 0.25,
                "quote_density": 0.25,
                "cross_platform": 0.0,
                "pain_point_count": 0.20,
            }
        else:
            weights = {
                "unique_source_count": 0.25,
                "subreddit_diversity": 0.15,
                "quote_density": 0.20,
                "cross_platform": 0.20,
                "pain_point_count": 0.20,
            }

        # Calculate confidence score (0-1) with normalized metrics.
        # quote_density is normalized by 5 (not 12): quotes are now stance-verified
        # and per-post-capped, so the realistic ceiling is ~5 genuine quotes/pain,
        # not the old pad-to-12 target. Full marks at 5 validated quotes/pain.
        confidence_score = (
            min(unique_source_count / 30, 1.0) * weights["unique_source_count"] +
            min(subreddit_diversity / 5, 1.0) * weights["subreddit_diversity"] +
            min(quote_density / 5, 1.0) * weights["quote_density"] +
            (cross_platform_count / max(total_count, 1)) * weights["cross_platform"] +
            min(total_count / 8, 1.0) * weights["pain_point_count"]
        )

        # Tier classification with detailed logging
        logger.info("=" * 60)
        logger.info("PAIN POINT QUALITY ASSESSMENT (Evidence-Based)")
        logger.info("=" * 60)
        logger.info(f"Pain point count: {total_count}")
        logger.info(f"Quote density: {quote_density:.1f} stance-verified quotes/pain point (target: ≥4 for GOLD)")
        logger.info(f"Unique source posts: {unique_source_count} (target: ≥20 for GOLD)")
        logger.info(f"Subreddit diversity: {subreddit_diversity} subreddits ({', '.join(sorted(subreddits_found)) if subreddits_found else 'none'})")
        if not single_platform_mode:
            logger.info(f"Cross-platform validation: {cross_platform_count}/{total_count} pain points")
        logger.info(f"Overall confidence score: {confidence_score:.2f}")

        # Tier gates — evidence-only, no LLM-assessed scores
        gold_cross_platform_ok = single_platform_mode or cross_platform_count >= 3
        if (
            unique_source_count >= 20 and
            subreddit_diversity >= 4 and
            total_count >= 5 and
            quote_density >= 4 and
            gold_cross_platform_ok
        ):
            tier = "GOLD"
            logger.info(f"✅ Quality Tier: {tier} (Premium Research - Broad, diverse evidence)")

        elif (
            unique_source_count >= 10 and
            subreddit_diversity >= 2 and
            total_count >= 3 and
            quote_density >= 2
        ):
            tier = "SILVER"
            logger.info(f"✅ Quality Tier: {tier} (Standard Research - Adequate evidence)")

        # BRONZE: no subreddit_diversity gate (single-subreddit research with
        # sufficient depth should still proceed)
        elif (
            unique_source_count >= 5 and
            total_count >= 2 and
            quote_density >= 1
        ):
            tier = "BRONZE"
            logger.warning(f"⚠️  Quality Tier: {tier} (Basic Research - Minimum viable evidence)")
            logger.warning("    Consider expanding social content collection for better insights")

        else:
            tier = "INSUFFICIENT"
            logger.error(f"❌ Quality Tier: {tier} (Insufficient - Should not proceed)")
            logger.error("    Recommendation: Expand social content collection or adjust niche focus")
            logger.error(
                f"    Gaps: unique_sources={unique_source_count} (need ≥5), "
                f"pain_points={total_count} (need ≥2), "
                f"quote_density={quote_density:.1f} (need ≥1)"
            )

        logger.info("=" * 60)

        return (tier, confidence_score)

    def _mark_stage_complete(self, stage: float, used_fallback: bool = False) -> None:
        """
        Mark a stage as complete with timestamp tracking.

        This enables diagnostic visibility into pipeline execution:
        - Which stages completed successfully
        - When each stage completed
        - Which stages used fallback/incomplete data

        Args:
            stage: Stage number (e.g., 5, 6, 6.5, 8.5)
            used_fallback: True if stage used fallback/incomplete data
        """
        # Track completed stage (avoid duplicates)
        if stage not in self.state.completed_stages:
            self.state.completed_stages.append(stage)
            self.state.completed_stages.sort()  # Keep sorted for readability
            logger.debug(f"[Stage Tracking] Stage {stage} marked complete")

        # Track completion timestamp. MUST match `started_at` (ResearchState uses
        # datetime.utcnow()) — both are stored naive with no tz marker, so mixing
        # now() and utcnow() silently skews every duration computed against
        # started_at by the local UTC offset.
        stage_key = str(stage)
        self.state.stage_completion_timestamps[stage_key] = datetime.utcnow()

        # Track fallback usage
        if used_fallback and stage not in self.state.fallback_stages:
            self.state.fallback_stages.append(stage)
            self.state.fallback_stages.sort()
            logger.warning(f"[Stage Tracking] Stage {stage} used fallback data")

        # Emit progress callback for web worker integration
        stage_names = {
            1: "Niche Validation",
            2: "Search & Discovery",
            3: "Pain Point Analysis",
            4: "Audience Mapping",
            5: "Solution Pipeline",
            5.5: "Competitive Analysis",
            6: "SEO & Keyword Strategy",
            7: "Pricing Validation",
            8: "Traffic Monetization",
            9: "Market Sizing",
            10: "Solution Refinement",
            11: "Trend Analysis",
            12: "SEO Score Refinement",
            13: "Data Source Research",
            14: "Report Generation",
        }
        stage_name = stage_names.get(stage, f"Stage {stage}")
        artifact = self._extract_stage_artifact(stage)
        self._emit_progress(stage, stage_name, "completed", artifact=artifact)

    def _skip_stage(self, stage_num: float, stage_name: str, reason: str) -> None:
        """Mark a stage as skipped with a user-friendly reason."""
        if stage_num not in self.state.completed_stages:
            self.state.completed_stages.append(stage_num)
            self.state.completed_stages.sort()
        if stage_num not in self.state.skipped_stages:
            self.state.skipped_stages.append(stage_num)
            self.state.skipped_stages.sort()
        self.state.stage_completion_timestamps[str(stage_num)] = datetime.utcnow()  # see _mark_stage_complete
        logger.info(f"[Stage Tracking] Stage {stage_num} ({stage_name}) skipped: {reason}")
        self._emit_progress(stage_num, stage_name, "skipped", artifact={"skip_reason": reason})
        # Persist skipped_stages now — a terminal skip cascade (stages 10-13 before the report)
        # may have no following save_stage to flush metadata, so it would be lost on resume.
        try:
            self.checkpoint_mgr.flush_metadata()
        except Exception as _e:  # noqa: BLE001 — checkpointing must never break the pipeline
            logger.debug(f"[Stage Tracking] metadata flush skipped: {_e}")

    def _extract_stage_artifact(self, stage: float) -> dict | None:
        """Extract a lightweight artifact dict for a completed stage.

        Stage 3 (pain points) allows up to 4KB to include all pain point
        summaries for the frontend showcase. All other stages use 2KB limit.

        Returns None if no artifact is available or extraction fails.
        """
        try:
            artifact = self._build_stage_artifact(stage)
            max_size = 8192 if stage == 3 else 2048
            if artifact and len(json.dumps(artifact)) > max_size:
                logger.warning(f"Artifact for stage {stage} exceeds {max_size}B, omitting")
                return None
            return artifact
        except Exception as e:
            logger.warning(f"Failed to extract artifact for stage {stage}: {e}")
            return None

    def _warm_gate_segment_payability(self, am, ppa) -> None:
        """Preliminary segment-payability scoring for the G2 gate card, computed ONLY when
        every segment still lacks a score. Production payability is normally warmed lazily
        inside Stage 5 (`UnifiedSolutionCrew._segment_payability_map`, with incumbent-pricing
        evidence) — but the G2 gate stops BEFORE Stage 5, so guided runs showed 'n/a' on every
        segment at exactly the moment the user decides segment emphasis (live-caught on the
        first guided run, 2026-07-12). This gate-time pass runs WITHOUT incumbent rows
        (preliminary, fail-soft); Stage 5 later re-scores with full evidence as always, so
        non-guided runs are byte-identical and idea stamping quality is unchanged."""
        try:
            segments = list(getattr(am, "audience_segments", None) or [])
            if not segments or any(getattr(s, "payability_score", None) is not None for s in segments):
                return
            from ..utils.segment_payability import norm_segment_name, score_segment_payability

            pains = list(getattr(ppa, "pain_points", None) or []) if ppa else []
            niche = getattr(getattr(self.state, "niche_context", None), "niche_description", "") or ""
            pay_map, usage = score_segment_payability(segments, pains, None, niche)
            if usage is not None and getattr(self, "cost_tracker", None):
                self.cost_tracker.record_llm_usage(
                    "Stage 4 - Segment Payability (gate preview)", usage.to_dict())
            for seg in segments:
                entry = pay_map.get(norm_segment_name(getattr(seg, "segment_name", "") or ""))
                if entry is not None:
                    seg.payability_score = entry.payability_score
                    seg.payability_class = entry.payability_class
                    seg.payability_rationale = entry.rationale or None
        except Exception as e:  # noqa: BLE001 — gate card enrichment must never block the gate
            logger.warning(f"[Gate G2] payability preview failed (non-fatal): {str(e)[:120]}")

    def _build_g2_gate_artifact(self) -> dict | None:
        """Dedicated composite gate artifact for the guided-mode G2 stop (after Stage 4).

        `_build_stage_artifact(4)` only carries counts (segment_count, primary_target,
        community_hubs) — too thin for the gate card AND the patch cross-check reference
        (Zod validates a `pain_scope`/`excluded_segments` patch against the titles/names
        this artifact lists, so both need the FULL identifiers). This builds a self-contained
        composite: full pain titles from Stage 3 + full segment names + payability labels from
        Stage 4, with its own (larger) size allowance since it must list every pain/segment,
        not a top-N sample.

        Degraded path (DR N4): if audience_mapping is missing/failed (Stage 4 prerequisites
        not met), still returns a pain-scope-only artifact so the gate isn't a dead end —
        the G2 patch's audience-scoping fields simply have nothing to validate against.
        Returns None only if pain_point_analysis is ALSO unavailable.
        """
        ppa = self.state.pain_point_analysis
        am = self.state.audience_mapping
        if not ppa and not am:
            return None

        artifact: dict = {"type": "audience_mapping_gate"}

        if ppa:
            artifact["pains"] = [
                {"title": p.title, "severity": p.severity_score, "opportunity":
                    p.opportunity_level.value if hasattr(p.opportunity_level, "value") else str(p.opportunity_level)}
                for p in ppa.pain_points
            ]
        else:
            artifact["pains"] = []
            artifact["degraded"] = "pain_scope_only"

        if am:
            self._warm_gate_segment_payability(am, ppa)
            # Effective primary (1.2e): a G2 patch's primary_target_segment override is
            # recorded on user_audience_scope (audience_mapping is never mutated) — the
            # gate card must reflect it, or an applied "make X primary" patch refreshes
            # the card byte-identically. The raw Stage-4 value rides along under its own
            # key; the patch cross-check reads artifact.segments only, so this is neutral.
            user_scope = getattr(self.state, "user_audience_scope", None)
            g2_primary = ((getattr(user_scope, "primary_target_segment", None) or "").strip()
                          if user_scope else "")
            artifact["primary_target"] = g2_primary or am.primary_target_segment
            artifact["primary_target_stage4"] = am.primary_target_segment
            artifact["segments"] = [
                {
                    "segment_name": s.segment_name,
                    "size_estimate": s.size_estimate,
                    "payability_class": s.payability_class,
                    "payability_score": s.payability_score,
                }
                for s in am.audience_segments
            ]
        else:
            artifact["segments"] = []

        # Own (larger) 16KB allowance — lists every pain/segment, not top-N. Shared
        # shrink helper with G1; also stamps `truncated` (the marker was missing here).
        _shrink_gate_artifact(
            artifact,
            list_fields={"pains": "title", "segments": "segment_name"},
            initial_caps={"pains": 40, "segments": 10},
            label="G2 gate artifact",
        )

        return artifact

    def _build_g1_gate_artifact(self) -> dict:
        """Dedicated composite gate artifact for the guided-mode G1 stop (after Stage 1).

        `_build_stage_artifact(1)` is the small SSE/progress artifact — it caps
        market_segments at 5 (and anchors at 8/4), so a 6+-segment niche rendered a gate
        card AND a patch cross-check reference that silently hid segments (F-013). This
        mirrors `_build_g2_gate_artifact`: FULL lists, its own 16KB allowance, and the
        shared shrink helper stamping `truncated` when it fires. The small SSE artifact
        stays as-is for progress events.

        Never returns None (a G1 gate must not dead-end): a missing niche_context
        degrades to a `{"degraded": ...}` marker instead.
        """
        ctx = self.state.niche_context
        if not ctx:
            return {"type": "niche_validation", "degraded": "niche_context_unavailable"}

        artifact: dict = {
            "type": "niche_validation",
            "niche_description": ctx.niche_description,
            "market_segments": list(ctx.market_segments or []),
            "industry_boundaries": ctx.industry_boundaries,
            "user_target_audience": getattr(ctx, "user_target_audience", None),
            "audience_scope": getattr(ctx, "audience_scope", None),
            "anchor_entities": list(getattr(ctx, "anchor_entities", None) or []),
            "disambiguation_exclusions": list(getattr(ctx, "disambiguation_exclusions", None) or []),
        }
        _shrink_gate_artifact(
            artifact,
            list_fields={"market_segments": None, "anchor_entities": None,
                         "disambiguation_exclusions": None},
            label="G1 gate artifact",
        )
        return artifact

    def _rederive_niche_context_dependents(self, niche_context: "NicheContext") -> None:
        """Re-derive Stage 1's DEPENDENT fields on an already-edited NicheContext after a G1
        guided-mode patch (Decisions §G1 / review B1 / Codex 2-3: "no downstream recompute"
        was true for G2 but false for G1 — Stage 1's own anchor/scope fields are derived FROM
        niche_description/user_target_audience, so editing those leaves anchor_entities /
        disambiguation_exclusions / anchor_communities / audience_jargon / community_search_terms
        and audience_scope stale/inconsistent before Stage 2 consumes them).

        Deliberately does NOT re-run the primary niche-context LLM call (`_generate_niche_context`
        regenerates niche_description/market_segments/industry_boundaries/user_target_audience
        from scratch, which would discard the user's just-applied patch) — instead re-runs only
        the isolated anchor-extraction call (`_extract_niche_anchors`, ONE cheap LLM call) against
        the EDITED niche_context in place, mirroring exactly what `_generate_niche_context` does
        with those two calls, and deterministically re-derives audience_scope (no LLM call: a
        classification call would risk disagreeing with the user's own edited
        user_target_audience). Mutates `niche_context` in place; never raises (mirrors
        `_extract_niche_anchors`'s own fail-soft contract).
        """
        # Deterministic audience_scope re-derivation: the classifier's OWN hard rule (see
        # _generate_niche_context) is "user_target_audience is null iff audience_scope=='niche'"
        # — apply the same rule in reverse from the (possibly user-edited) audience field.
        if (niche_context.user_target_audience or "").strip():
            if (niche_context.audience_scope or "niche") == "niche":
                niche_context.audience_scope = "segment_of_niche"
        else:
            niche_context.audience_scope = "niche"

        try:
            self._extract_niche_anchors(niche_context.niche_input, niche_context)
        except Exception as e:  # pragma: no cover - _extract_niche_anchors is itself fail-soft
            logger.warning(f"[Gate G1] niche-context dependent re-derivation failed (non-fatal): {e}")

    def _build_stage_artifact(self, stage: float) -> dict | None:
        """Build artifact dict for a specific stage from current state."""
        if stage == 1 and self.state.niche_context:
            ctx = self.state.niche_context
            return {
                "type": "niche_validation",
                "niche_description": ctx.niche_description,
                "market_segments": ctx.market_segments[:5],
                "industry_boundaries": ctx.industry_boundaries,
                # G1 gate card + patch-diff "before" values: the gate's whitelist can edit
                # user_target_audience, and applies re-derive the anchors — without these
                # fields an audience edit refreshed the card byte-identically and the UI
                # honestly showed "no change" (live-caught on the first guided run, 2026-07-12).
                "user_target_audience": getattr(ctx, "user_target_audience", None),
                "audience_scope": getattr(ctx, "audience_scope", None),
                "anchor_entities": list(getattr(ctx, "anchor_entities", None) or [])[:8],
                "disambiguation_exclusions": list(getattr(ctx, "disambiguation_exclusions", None) or [])[:4],
            }
        elif stage == 2 and self.state.social_content:
            sc = self.state.social_content
            fs = self.state.filtering_stats or {}
            # Compute manually - sc.total_reddit_comments is never populated
            total_comments = sum(len(p.comments) for p in sc.reddit_posts)
            total_twitter_replies = sum(len(t.replies) for t in sc.twitter_threads)
            total_interactions = total_comments + total_twitter_replies
            total_upvotes = sum(p.score for p in sc.reddit_posts if p.score > 0)
            return {
                "type": "search_discovery",
                "reddit_posts": len(sc.reddit_posts),
                "twitter_threads": len(sc.twitter_threads),
                "quality_tier": self.state.social_content_quality_tier,
                "subreddit_count": len(set(
                    getattr(p, 'subreddit', '') for p in sc.reddit_posts
                )),
                "urls_searched": fs.get("total_urls_searched", 0),
                "urls_relevant": fs.get("total_urls_relevant", 0),
                "total_interactions": total_interactions,
                "total_upvotes": total_upvotes,
            }
        elif stage == 3 and self.state.pain_point_analysis:
            ppa = self.state.pain_point_analysis
            sorted_points = sorted(ppa.pain_points, key=lambda p: p.severity_score, reverse=True)
            return {
                "type": "pain_points",
                "count": len(ppa.pain_points),
                "confidence": self.state.pain_point_confidence_score,
                "quality_tier": self.state.pain_point_quality_tier,
                "total_mentions": ppa.total_mentions,
                "top_categories": ppa.top_categories[:5],
                "pain_points": [
                    {
                        "title": p.title,
                        "short_summary": p.short_summary or p.description,
                        "severity": p.severity_score,
                        "wtp": p.commercial_intent,
                        "opportunity": p.opportunity_level.value if hasattr(p.opportunity_level, 'value') else str(p.opportunity_level),
                        "mentions": p.mention_count,
                        "categories": (p.categories or [])[:3],
                        "platforms": p.source_platforms or [],
                    }
                    for p in sorted_points
                ],
                # Backward compat for old frontend code
                "top": [{"title": p.title, "severity": p.severity_score} for p in sorted_points[:3]],
            }
        elif stage == 4:
            am = self.state.audience_mapping
            if am:
                return {
                    "type": "audience_mapping",
                    "segment_count": len(am.audience_segments),
                    "primary_target": am.primary_target_segment,
                    "community_hubs": am.community_hubs[:3] if am.community_hubs else [],
                }
            return None
        elif stage == 6:
            seo = self.state.seo_strategy_report
            kvr = self.state.keyword_validation_results
            sel = self.state.solution_selection
            result: dict = {"type": "seo_opportunity"}
            if kvr and len(kvr) > 0:
                primary_name = sel.selected_solution_name if sel else None
                k = next((v for v in kvr if getattr(v, 'solution_name', None) == primary_name), kvr[0])
                result.update({
                    # graded_keyword_count, not validated_count: legacy checkpoints stored
                    # the unfiltered expansion pool there and this payload is user-facing.
                    "validated_keywords": k.graded_keyword_count,
                    "total_volume": k.total_volume,
                    "demand_signal": getattr(k, 'demand_signal', None),
                    "avg_difficulty": getattr(k, 'avg_keyword_difficulty', None),
                    "rankability_factor": getattr(k, 'rankability_factor', None),
                })
            if seo:
                result.update({
                    "cluster_count": len(seo.topic_clusters) if seo.topic_clusters else 0,
                    "top_clusters": [
                        c.cluster_name for c in (seo.topic_clusters or [])[:3]
                    ],
                    "total_keywords_analyzed": getattr(seo, 'total_keywords_analyzed', None),
                })
            if sel and hasattr(sel, 'selected_solution_name'):
                result["winner_name"] = sel.selected_solution_name
            return result if len(result) > 1 else None
        elif stage == 7:
            ps = self.state.pricing_strategies
            sel = self.state.solution_selection
            if ps and len(ps) > 0:
                primary_name = sel.selected_solution_name if sel else None
                p = next((v for v in ps if getattr(v, 'solution_name', None) == primary_name), ps[0])
                return {
                    "type": "pricing",
                    "pricing_model": getattr(p, 'pricing_model', None),
                    "starter_price": p.recommended_starter_price,
                    "pro_price": p.recommended_pro_price,
                    "arpu": getattr(p, 'estimated_arpu', None),
                    "confidence": getattr(p, 'pricing_confidence', None),
                }
            return None
        elif stage == 9:
            ms = self.state.market_sizing
            if ms:
                result = {
                    "type": "market_sizing",
                    "tam": ms.total_addressable_market,
                    "sam": ms.serviceable_available_market,
                    "som_y1": ms.serviceable_obtainable_market_y1,
                    "viability": getattr(ms, 'market_viability_verdict', None),
                    "growth_rate": getattr(ms, 'market_growth_rate', None),
                }
                tm = self.state.traffic_monetization_results
                if tm and len(tm) > 0:
                    t = tm[0]
                    result["monetization"] = {
                        "model": getattr(t, 'monetization_model', None),
                        "monthly_revenue_range": getattr(t, 'estimated_monthly_revenue_range', None),
                    }
                return result
            return None
        elif stage == 11:
            tl = self.state.trend_longevity
            if tl:
                return {
                    "type": "trend_analysis",
                    "trend_direction": tl.trend_direction,
                    "momentum_score": tl.momentum_score,
                    "longevity_verdict": getattr(tl, 'longevity_verdict', None),
                    "market_maturity": getattr(tl, 'market_maturity', None),
                    "timing_recommendation": getattr(tl, 'timing_recommendation', None),
                    "trend_confidence": getattr(tl, 'trend_confidence', None),
                }
            return None
        return None

    # ──────────────────────────────────────────────────────────
    # Discovery Data Materialization (for frontend evidence UI)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _score_quote(text: str, upvotes: int = 0) -> float:
        """Score a quote for display quality. Higher = better for UI.

        Rejects fragments and rewards self-contained, frustration-laden quotes
        that convey genuine user voice.
        """
        # Hard rejections — return -1 for unusable quotes
        if not text or len(text.strip()) < 40:
            return -1.0
        stripped = text.strip()
        reject_prefixes = (
            "Edit to add", "Also ", "That would", "This.", "http",
            "https", "www.", "And ", "But ", "Or ", "Yeah ",
        )
        if any(stripped.startswith(p) for p in reject_prefixes):
            return -1.0
        # Reject bare URLs or mostly-URL quotes
        if stripped.count("http") > 0 and len(stripped) < 80:
            return -1.0

        score = 0.0

        # Length preference: 60-200 chars is the sweet spot
        length = len(stripped)
        if 60 <= length <= 200:
            score += 3.0
        elif 40 <= length < 60:
            score += 1.0
        elif 200 < length <= 300:
            score += 2.0
        else:
            score += 0.5

        # Frustration signal — first-person pain language
        frustration_phrases = [
            "i can't", "i've been", "i give up", "why would i",
            "i don't understand", "i don't get", "took", "hours",
            "gave up", "frustrated", "struggled", "confusing",
            "painful", "impossible", "nightmare", "ridiculous",
            "waste of time", "makes no sense", "spent", "failed",
            "disappointed", "hard to", "difficult", "overwhelming",
        ]
        lower = stripped.lower()
        frustration_hits = sum(1 for p in frustration_phrases if p in lower)
        score += min(frustration_hits * 1.5, 6.0)

        # First-person voice boost (makes it feel like a real person)
        first_person = ["i ", "i'", "my ", "me ", "i've", "i'm"]
        if any(lower.startswith(p) or f" {p}" in lower for p in first_person):
            score += 2.0

        # Upvote tiebreaker (log scale to avoid domination)
        if upvotes > 0:
            import math
            score += min(math.log2(upvotes + 1), 4.0)

        return score

    def _materialize_discovery_data(self, output_dir: str) -> str | None:
        """Assemble and write discovery data JSON for frontend evidence UI.

        Called after phase 1 completion when all data is in memory.
        Returns the file path if successful, None on failure.
        """
        try:
            state = self.state
            all_generic_posts = list(state.social_content.generic_posts or []) if state.social_content else []
            discovery_generic_posts = [
                post
                for post in all_generic_posts
                if post.platform != "hackernews"
                or (
                    post.relevance_grade is not None
                    and post.relevance_grade >= 2
                )
            ]
            excluded_hn_posts = [
                post
                for post in all_generic_posts
                if post.platform == "hackernews"
                and (
                    post.relevance_grade is None
                    or post.relevance_grade < 2
                )
            ]
            excluded_hn_post_ids = {post.post_id for post in excluded_hn_posts}

            # Build post_id → post lookup for cross-referencing engagement
            post_lookup: dict[str, object] = {}
            if state.social_content:
                for p in state.social_content.reddit_posts:
                    post_lookup[p.post_id] = p
                for p in discovery_generic_posts:
                    post_lookup[p.post_id] = p

            # ── Quotes: score and select top 3 per pain point ──
            quotes_by_pain: dict[str, list[dict]] = {}
            all_scored_quotes: list[tuple[float, dict, str]] = []  # (score, quote_dict, pain_title)

            if state.pain_point_analysis:
                for pp in state.pain_point_analysis.pain_points:
                    pain_quotes = []
                    raw_quotes = pp.representative_quotes or []
                    raw_ids = pp.source_post_ids or []
                    raw_attributions = getattr(pp, "speaker_attributions", None) or []

                    for i, q_text in enumerate(raw_quotes):
                        post_id = raw_ids[i] if i < len(raw_ids) else ""
                        if post_id in excluded_hn_post_ids:
                            continue
                        post = post_lookup.get(post_id)
                        upvotes = getattr(post, "score", 0) if post else 0

                        # Platform-aware source label and URL
                        if hasattr(post, "platform"):
                            # Generic source (HN, YouTube, etc.)
                            _platform_labels = {"hackernews": "Hacker News", "youtube": "YouTube"}
                            subreddit = _platform_labels.get(post.platform, post.platform)
                            url = getattr(post, "url", "") if post_id else ""
                        else:
                            # Reddit post
                            subreddit = getattr(post, "subreddit", "") if post else ""
                            url = f"https://reddit.com/comments/{post_id}" if post_id else ""

                        q_score = self._score_quote(q_text, upvotes)
                        if q_score < 0:
                            continue

                        quote_dict = {
                            "text": q_text[:300],  # cap length for safety
                            "post_id": post_id,
                            "source_url": url,
                            "upvotes": upvotes,
                            "subreddit": subreddit,
                        }
                        if i < len(raw_attributions) and raw_attributions[i] is not None:
                            quote_dict["speaker_attribution"] = raw_attributions[i].model_dump(
                                mode="json"
                            )
                        pain_quotes.append((q_score, quote_dict))
                        all_scored_quotes.append((q_score, quote_dict, pp.title))

                    # Top 3 per pain point
                    pain_quotes.sort(key=lambda x: x[0], reverse=True)
                    quotes_by_pain[pp.title] = [q[1] for q in pain_quotes[:3]]

            # ── Hero quote: best single quote across all pain points ──
            hero_quote = None
            if all_scored_quotes:
                all_scored_quotes.sort(key=lambda x: x[0], reverse=True)
                best = all_scored_quotes[0]
                hero_quote = {
                    **best[1],
                    "pain_point_title": best[2],
                }

            # ── Discussion trend (monthly post counts, last 12 months, all sources) ──
            discussion_trend = []
            all_social_posts = list(state.social_content.reddit_posts) if state.social_content else []
            all_social_posts += discovery_generic_posts
            if all_social_posts:
                from collections import Counter
                from datetime import timedelta

                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(days=365)
                monthly: Counter[str] = Counter()
                for p in all_social_posts:
                    created = getattr(p, "created_utc", None)
                    if not created:
                        continue
                    # Skip posts with estimated dates (e.g., YouTube without parseable upload date)
                    raw_eng = getattr(p, "raw_engagement", None)
                    if isinstance(raw_eng, dict) and raw_eng.get("date_estimated"):
                        continue
                    # Normalize: make aware if naive (Reddit posts may lack tzinfo)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if created >= cutoff:
                        monthly[created.strftime('%Y-%m')] += 1

                # Build sorted array with 0-filled gaps
                current = cutoff.replace(day=1)
                # End at the last COMPLETE month. The current month is partial, so plotting it
                # beside full months compares unequal windows — and because search APIs
                # over-return recent content, it landed as the series maximum on 4 of 4 audited
                # runs (2.4x/1.2x/4.3x/1.5x the next-highest month). That single partial bar drove
                # the headline: every one of those runs reported growth (+43/46/116/49%), which is
                # not four booming niches, it is a metric that can only say "up". Dropping it flips
                # this run's figure from +43% to -12%.
                end = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
                while current <= end:
                    key = current.strftime('%Y-%m')
                    discussion_trend.append({"month": key, "count": monthly.get(key, 0)})
                    current = (current + timedelta(days=32)).replace(day=1)

            # ── Growth rate (last 6 months vs prior 6 months) ──
            growth_pct = None
            if len(discussion_trend) >= 6:
                recent_half = sum(d["count"] for d in discussion_trend[-6:])
                prior_half = sum(d["count"] for d in discussion_trend[-12:-6]) if len(discussion_trend) >= 12 else sum(d["count"] for d in discussion_trend[:-6])
                if prior_half > 0:
                    growth_pct = round((recent_half - prior_half) / prior_half * 100)

            # ── Methodology ──
            fs = state.filtering_stats or {}
            urls_searched = fs.get("total_urls_searched", 0)
            urls_relevant = fs.get("total_urls_relevant", 0)
            if excluded_hn_post_ids:
                hn_relevant = fs.get(
                    "hackernews_urls_relevant",
                    fs.get("hackernews_posts_collected", 0),
                )
                urls_relevant = max(
                    0,
                    urls_relevant - min(len(excluded_hn_post_ids), hn_relevant),
                )
            scm = getattr(state, 'social_content_metrics', None)
            scm_dict = scm if isinstance(scm, dict) else {}
            total_engagement = scm_dict.get("total_engagement", 0)
            avg_engagement = scm_dict.get("avg_engagement_per_source", 0)
            if excluded_hn_posts and scm_dict:
                total_engagement = max(
                    0,
                    total_engagement - sum(post.score for post in excluded_hn_posts),
                )
                visible_source_count = max(
                    0,
                    scm_dict.get("total_sources", 0) - len(excluded_hn_posts),
                )
                avg_engagement = (
                    round(total_engagement / visible_source_count, 1)
                    if visible_source_count > 0 else 0
                )
            methodology = {
                "urls_searched": urls_searched,
                "urls_relevant": urls_relevant,
                "filtering_rate": round(urls_relevant / urls_searched * 100, 1) if urls_searched > 0 else 0,
                "quality_tier": state.social_content_quality_tier or "",
                "pain_point_quality_tier": state.pain_point_quality_tier or "",
                "pain_point_confidence": state.pain_point_confidence_score or 0,
                "total_engagement": total_engagement,
                "avg_engagement": avg_engagement,
            }

            # ── Community source names (Reddit subreddits + generic platform labels) ──
            subreddit_names = []
            subreddit_post_counts: dict[str, int] = {}
            _platform_labels = {"hackernews": "Hacker News", "youtube": "YouTube"}
            if state.social_content:
                # Reddit subreddits with r/ prefix
                reddit_sources = [
                    f"r/{getattr(p, 'subreddit', '')}" for p in state.social_content.reddit_posts
                    if getattr(p, "subreddit", "")
                ]
                # Generic sources by platform label
                generic_sources = [
                    _platform_labels.get(p.platform, p.platform)
                    for p in discovery_generic_posts
                    if p.platform
                ]
                subreddit_names = sorted(set(reddit_sources + generic_sources))

                # Per-source post counts (top 10 by volume) for distribution visualization
                from collections import Counter
                all_source_labels = (
                    [getattr(p, "subreddit", "") for p in state.social_content.reddit_posts if getattr(p, "subreddit", "")]
                    + [_platform_labels.get(p.platform, p.platform) for p in discovery_generic_posts if p.platform]
                )
                subreddit_post_counts = dict(Counter(all_source_labels).most_common(10))

            # ── Audience ──
            audience = None
            am = state.audience_mapping
            if am:
                audience = {
                    "segments": [
                        {
                            "segment_name": seg.segment_name,
                            "size_estimate": seg.size_estimate,
                            "pain_point_alignment": seg.pain_point_alignment[:3],
                            "motivation_drivers": seg.motivation_drivers[:5],
                            "expertise_level": seg.expertise_level,
                            "budget_sensitivity": seg.budget_sensitivity,
                            "discovery_channels": seg.discovery_channels[:5],
                        }
                        for seg in am.audience_segments
                    ],
                    "primary_target": am.primary_target_segment,
                    "prioritization_rationale": am.segment_prioritization_rationale,
                    "community_hubs": am.community_hubs[:10] if am.community_hubs else [],
                    "common_vocabulary": am.common_vocabulary[:15] if am.common_vocabulary else [],
                    "content_preferences": am.content_preferences or "",
                    "tools_currently_used": am.tools_currently_used[:10] if am.tools_currently_used else [],
                    "frustrations_with_existing": am.frustrations_with_existing[:5] if am.frustrations_with_existing else [],
                }

            # ── Influencers (top 8 by relevance_score) ──
            influencers = []
            if am and am.key_influencers:
                sorted_inf = sorted(am.key_influencers, key=lambda x: x.relevance_score, reverse=True)
                for inf in sorted_inf[:8]:
                    influencers.append({
                        "name": inf.name,
                        "platform": inf.platform,
                        "relevance_score": inf.relevance_score,
                        "content_focus": inf.content_focus,
                        "top_subreddits": inf.top_subreddits[:3] if inf.top_subreddits else [],
                        "top_posts": [
                            {
                                "title": tp.title[:120],
                                "subreddit": tp.subreddit,
                                "score": tp.score,
                                "url": tp.url,
                            }
                            for tp in (inf.top_posts or [])[:3]
                        ],
                    })

            # ── Social posts sample (top 10 by score across all sources) ──
            social_posts_sample = []
            if state.social_content:
                all_sample_posts = []
                for p in state.social_content.reddit_posts:
                    sample = {
                        "title": p.title[:200],
                        "subreddit": p.subreddit,
                        "score": p.score,
                        "num_comments": p.num_comments,
                        "url": p.url,
                        "created_utc": p.created_utc.isoformat() if p.created_utc else "",
                    }
                    if getattr(p, "speaker_attribution", None) is not None:
                        sample["speaker_attribution"] = p.speaker_attribution.model_dump(mode="json")
                    all_sample_posts.append(sample)
                for p in discovery_generic_posts:
                    container = _platform_labels.get(p.platform, p.platform)
                    sample = {
                        "title": p.title[:200],
                        "subreddit": container,
                        "score": p.score,
                        "num_comments": p.num_responses,
                        "url": p.url,
                        "created_utc": p.created_utc.isoformat() if p.created_utc else "",
                    }
                    if getattr(p, "speaker_attribution", None) is not None:
                        sample["speaker_attribution"] = p.speaker_attribution.model_dump(mode="json")
                    all_sample_posts.append(sample)
                social_posts_sample = sorted(all_sample_posts, key=lambda x: x["score"], reverse=True)[:10]

            sources_searched = None if state.sources_searched is None else {
                source: dict(details) if isinstance(details, dict) else details
                for source, details in state.sources_searched.items()
            }
            if sources_searched and "hackernews" in sources_searched and isinstance(
                sources_searched["hackernews"], dict
            ):
                sources_searched["hackernews"]["posts_found"] = sum(
                    1 for post in discovery_generic_posts
                    if post.platform == "hackernews"
                )

            # ── Assemble final structure ──
            discovery_data = {
                "methodology": methodology,
                "hero_quote": hero_quote,
                "quotes": quotes_by_pain,
                "audience": audience,
                "influencers": influencers,
                "social_posts_sample": social_posts_sample,
                "subreddit_names": subreddit_names,
                "subreddit_post_counts": subreddit_post_counts,
                "speaker_attribution_version": getattr(
                    state.social_content, "speaker_attribution_version", None
                ) if state.social_content else None,
                "speaker_attribution_target": getattr(
                    state.social_content, "speaker_attribution_target", None
                ) if state.social_content else None,
                "data_attribution": f"Public community activity from {', '.join(sorted(set(subreddit_names))) or 'Reddit'}",
                "sources_searched": sources_searched,
                "discussion_trend": discussion_trend,
                "discussion_growth_pct": growth_pct,
            }

            # Write to file
            job_id = getattr(self, "job_id", None) or getattr(state, "job_id", None)
            if not job_id:
                logger.error("[Discovery Data] job_id missing on flow and state; refusing to materialize")
                return None
            out_path = Path(output_dir) / f"discovery_data_{job_id}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(discovery_data, indent=2, default=str))
            logger.info(f"[Discovery Data] Materialized to {out_path} ({out_path.stat().st_size} bytes)")
            return str(out_path)

        except Exception as e:
            logger.warning(f"[Discovery Data] Failed to materialize: {e}")
            return None

    def _refresh_idea_portfolio_summary(
        self,
        *,
        reason: str,
        force: bool = False,
        persist: bool = False,
    ) -> bool:
        """Refresh portfolio guidance when the visible ids+revisions changed.

        This is intentionally fail-soft. A failed LLM pass leaves any older summary and
        fingerprint paired, so fingerprint-aware consumers degrade instead of presenting
        the old recommendation as current. Returns True only when new guidance was stored.
        """
        from ..models.solution_idea import visible_ideas
        from ..utils.idea_portfolio_summary import (
            generate_idea_portfolio_summary,
            idea_portfolio_fingerprint,
        )

        state = self.state
        ideas = list(
            getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or []
        )
        current_fingerprint = idea_portfolio_fingerprint(
            ideas,
            job_id=getattr(self, "job_id", None) or getattr(state, "job_id", None),
        )
        if current_fingerprint is None:
            logger.warning(
                f"[Portfolio Summary] {reason}: candidate fingerprint unavailable; "
                "keeping guidance fail-closed"
            )
            return False

        visible_count = len(visible_ideas(ideas))
        funnel_counts = dict(getattr(state, "idea_funnel_counts", None) or {})
        metadata_changed = funnel_counts.get("candidates_shown") != visible_count
        funnel_counts["candidates_shown"] = visible_count
        state.idea_funnel_counts = funnel_counts

        stored_fingerprint = getattr(state, "idea_portfolio_summary_fingerprint", None)
        stored_summary = getattr(state, "idea_portfolio_summary", None)
        checkpoint_mgr = getattr(self, "checkpoint_mgr", None)
        needs_refresh = force or stored_fingerprint != current_fingerprint
        # A legacy run with neither field has no stale guidance to suppress and no prior
        # summary attempt to refresh. New runs always receive a fingerprint in Stage 5.
        if not force and stored_fingerprint is None and stored_summary is None:
            needs_refresh = False
        if not needs_refresh:
            if metadata_changed and persist and checkpoint_mgr:
                try:
                    checkpoint_mgr.flush_metadata()
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[Portfolio Summary] count persistence failed: {e}")
            return False

        try:
            verdict = getattr(state, "niche_difficulty_verdict", None)
            niche_context = getattr(state, "niche_context", None)
            summary, usage = generate_idea_portfolio_summary(
                ideas,
                ruled_out=getattr(state, "idea_ruled_out", None),
                funnel_counts=funnel_counts,
                niche_wallet_brief=getattr(state, "niche_wallet_brief", None),
                niche_difficulty_headline=getattr(verdict, "headline", None),
                niche_difficulty_narrative=getattr(verdict, "narrative_summary", None),
                niche=(
                    getattr(niche_context, "niche_description", None)
                    or getattr(self, "niche_description", None)
                ),
            )
            cost_tracker = getattr(self, "cost_tracker", None)
            if usage is not None and cost_tracker is not None:
                cost_tracker.record_llm_usage(
                    "Stage 5 - Idea Portfolio Summary", usage.to_dict()
                )
            if summary:
                state.idea_portfolio_summary = summary
                state.idea_portfolio_summary_fingerprint = current_fingerprint
                metadata_changed = True
                logger.info(
                    f"[Portfolio Summary] {reason}: generated for {visible_count} candidates "
                    f"({len(summary)} chars)"
                )
            else:
                # With no older prose there is nothing stale to preserve. Record the pool
                # attempted so a later mutation will trigger another attempt without making
                # every ordinary preview materialization retry a paid call.
                if stored_summary is None:
                    state.idea_portfolio_summary = None
                    state.idea_portfolio_summary_fingerprint = current_fingerprint
                    metadata_changed = True
                logger.warning(
                    f"[Portfolio Summary] {reason}: grounded LLM pass produced no usable "
                    "guidance; keeping guidance fail-closed"
                )
        except Exception as e:  # noqa: BLE001
            if stored_summary is None:
                state.idea_portfolio_summary = None
                state.idea_portfolio_summary_fingerprint = current_fingerprint
                metadata_changed = True
            logger.warning(
                f"[Portfolio Summary] {reason}: refresh failed; keeping guidance "
                f"fail-closed: {e}"
            )

        if metadata_changed and persist and checkpoint_mgr:
            try:
                checkpoint_mgr.flush_metadata()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[Portfolio Summary] metadata persistence failed: {e}")
        return bool(
            getattr(state, "idea_portfolio_summary", None)
            and getattr(state, "idea_portfolio_summary_fingerprint", None)
            == current_fingerprint
        )

    def _current_recommended_candidates(self) -> list:
        """Resolve the recommendation authority the live selection surface uses."""
        state = self.state
        ideas = list(getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or [])
        if not ideas:
            return []

        # Interactive Phase 1 has no SolutionSelection. Its fingerprint-bound portfolio
        # summary's final sentence is the page-level recommendation authority.
        summary = getattr(state, "idea_portfolio_summary", None)
        stored_fingerprint = getattr(state, "idea_portfolio_summary_fingerprint", None)
        if summary and stored_fingerprint:
            from ..utils.idea_portfolio_summary import idea_portfolio_fingerprint

            current_fingerprint = idea_portfolio_fingerprint(
                ideas,
                job_id=getattr(self, "job_id", None) or getattr(state, "job_id", None),
            )
            if current_fingerprint == stored_fingerprint:
                paragraphs = [part.strip() for part in re.split(r"\n\s*\n", summary) if part.strip()]
                last_paragraph = paragraphs[-1] if paragraphs else ""
                sentences = [
                    part.strip()
                    for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", last_paragraph)
                    if part.strip()
                ]
                recommendation = sentences[-1] if sentences else last_paragraph
                if re.search(
                    r"\b(?:recommend(?:ed|s|ing)?|most deserves?|deserves? (?:further|deeper) "
                    r"validation|strongest|best (?:idea|option|candidate|pick)|top "
                    r"(?:idea|option|candidate|pick)|prioriti[sz]e|validate(?:d|s|ing)? "
                    r"first|first choice)\b",
                    recommendation,
                    re.IGNORECASE,
                ):
                    picks = []
                    for idea in ideas:
                        name = (getattr(idea, "solution_name", None) or "").strip()
                        head = re.split(r"[(:]", name, maxsplit=1)[0].strip()
                        aliases = [name] + ([head] if len(head) >= 4 and head != name else [])
                        if any(
                            re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", recommendation, re.IGNORECASE)
                            for alias in aliases if alias
                        ):
                            picks.append(idea)
                    if picks:
                        return picks

        selection = getattr(state, "solution_selection", None)
        recommendation_names = {
            name.strip()
            for name in [
                getattr(selection, "selected_solution_name", None),
                *(getattr(selection, "runner_up_solutions", None) or []),
            ]
            if isinstance(name, str) and name.strip()
        }
        return [
            idea for idea in ideas
            if (getattr(idea, "solution_name", None) or "").strip() in recommendation_names
        ]

    def _refresh_recommendation_audience_drift(self, *, persist: bool) -> object | None:
        """Bind the structured audience notice to the current persisted recommendation.

        Selection can change after the Stage-5 verdict (fallbacks, keyword pivots, or a resumed
        run), so preview materialization re-runs the three-way comparison from durable state.
        Only the selected solution and explicitly recorded runners-up are recommendation-scoped;
        unrelated pool candidates must never trigger the notice.

        The comparison is `audience_axes.detect_audience_drift`: buyer identity read on typed
        axes, not wording overlap.

        THREE reader-facing surfaces, one snapshot time. The audience card and the verdict card
        read `audience_drift_notice`; the Reality Check renders `verdict.key_challenges`, which
        `assess_niche_difficulty` appends `AUDIENCE_DRIFT_CHALLENGE` to. Rebinding only the two
        notice fields left the third warning behind: a recommendation that changed after Stage 5
        cleared both notices and the Reality Check went on warning about a buyer change that the
        current recommendation no longer shows. So the challenge list is rewritten here too —
        stripped of the pointer unconditionally, then re-appended only while the notice stands.

        Not covered, and deliberately: `verdict.narrative_summary`. The deterministic fallback
        narrative can quote `key_points[0]`, so a run whose prose LLM failed can carry the
        pointer sentence inside prose this function does not rewrite. It names no segment and no
        pair, so a stale copy misstates nothing pool-scoped — but it is not snapshot-bound.
        """
        state = self.state
        verdict = getattr(state, "niche_difficulty_verdict", None)
        niche_context = getattr(state, "niche_context", None)
        audience_mapping = getattr(state, "audience_mapping", None)

        from ..utils.audience_axes import AUDIENCE_DRIFT_CHALLENGE, detect_audience_drift

        notice = detect_audience_drift(
            getattr(niche_context, "user_target_audience", None),
            getattr(audience_mapping, "primary_target_segment", None),
            self._current_recommended_candidates(),
        )
        verdict_current = getattr(verdict, "audience_drift_notice", None)
        mapping_current = getattr(audience_mapping, "audience_drift_notice", None)
        challenges = list(getattr(verdict, "key_challenges", None) or [])
        if notice is not None and AUDIENCE_DRIFT_CHALLENGE in challenges:
            # Already carried: keep the position Stage 5 wrote it at rather than moving it to
            # the end on every no-op refresh.
            wanted_challenges = challenges
        else:
            wanted_challenges = [c for c in challenges if c != AUDIENCE_DRIFT_CHALLENGE]
            if notice is not None:
                wanted_challenges = [*wanted_challenges, AUDIENCE_DRIFT_CHALLENGE]
        if (verdict_current == notice and mapping_current == notice
                and wanted_challenges == challenges):
            return notice

        if verdict is not None:
            state.niche_difficulty_verdict = verdict.model_copy(
                update={
                    "audience_drift_notice": notice,
                    "key_challenges": wanted_challenges,
                }
            )
        if audience_mapping is not None:
            state.audience_mapping = audience_mapping.model_copy(
                update={"audience_drift_notice": notice}
            )
        checkpoint_mgr = getattr(self, "checkpoint_mgr", None)
        if persist and checkpoint_mgr is not None:
            # save_stage REPORTS failure by returning False as well as by raising, and the two
            # writes are independent — a warning-free return used to mean nothing about whether
            # either landed. A drift notice that only exists in memory is a warning that a
            # resumed run will not repeat, so an unconfirmed write is logged as an error naming
            # the stage. The preview itself is still published: it carries the notice inline,
            # so withholding it would remove the very warning this is protecting.
            #
            # `save_stage` returns True unconditionally when `settings.checkpoint_enabled` is
            # false, so this error cannot fire in that configuration. That is correct rather
            # than a hole: with checkpointing off there is no checkpoint to resume from, so
            # there is no "will not survive a resume" to warn about.
            targets = []
            if verdict is not None:
                targets.append(("stage_5_niche_difficulty", state.niche_difficulty_verdict))
            if audience_mapping is not None:
                targets.append(("stage_4_audience_mapping", state.audience_mapping))
            for stage_name, payload in targets:
                try:
                    saved = checkpoint_mgr.save_stage(stage_name, payload)
                except Exception as e:  # noqa: BLE001 - preview remains publishable
                    saved = False
                    logger.error(f"[Audience Drift] {stage_name} checkpoint write raised: {e}")
                if saved is False:
                    logger.error(
                        f"[Audience Drift] {stage_name} did not confirm the audience notice "
                        "write; the notice is in this preview but will not survive a resume"
                    )
        return notice

    def _materialize_preview_report(self, output_dir: str) -> str | None:
        """Assemble and write a preview report JSON that mirrors FinalReport shape.

        Called after Phase 1 completion alongside _materialize_discovery_data().
        Produces a Partial<Report>-shaped dict from stages 1-5 data only.
        Pure Python data reshaping unless the visible candidate fingerprint changed. A
        changed pool triggers the same fail-soft portfolio-summary LLM pass used in Stage 5.

        Returns the file path if successful, None on failure.
        """
        try:
            state = self.state
            if self.job_id and state.idea_generation:
                from ..utils.idea_identity import (
                    link_legacy_findings_to_ideas,
                    stamp_new_idea_identities,
                    stamp_ruled_out_findings,
                )

                stamp_new_idea_identities(
                    self.job_id,
                    state.idea_generation.solution_ideas,
                    origin="phase1",
                    operation_key="initial",
                    force=True,
                    only_unowned=True,
                )
                state.idea_ruled_out = link_legacy_findings_to_ideas(
                    state.idea_ruled_out,
                    state.idea_generation.solution_ideas,
                )
                state.idea_ruled_out = stamp_ruled_out_findings(
                    self.job_id,
                    state.idea_ruled_out,
                    operation_key="preview",
                )
            self._refresh_idea_portfolio_summary(
                reason="preview candidate-set check",
                persist=True,
            )
            self._refresh_recommendation_audience_drift(persist=True)
            report: dict = {}

            # ── Stage 1: Niche Context ──
            try:
                niche_ctx = getattr(state, "niche_context", None)
                if niche_ctx:
                    report["niche"] = niche_ctx.niche_description
                    report["niche_context"] = niche_ctx.model_dump()
                else:
                    report["niche"] = self.niche_description or "Unknown niche"
                    report["niche_context"] = None
            except Exception as e:
                logger.debug(f"[Preview Report] Niche context section failed: {e}")
                report["niche"] = self.niche_description or "Unknown niche"
                report["niche_context"] = None

            # ── Stage 2: Evidence Appendix (top reddit threads + quote sources) ──
            try:
                evidence_appendix: dict | None = None
                social = getattr(state, "social_content", None)
                if social and social.reddit_posts:
                    sorted_posts = sorted(
                        social.reddit_posts,
                        key=lambda p: p.score,
                        reverse=True,
                    )

                    top_reddit_threads = []
                    for post in sorted_posts[:5]:
                        top_reddit_threads.append({
                            "post_id": post.post_id,
                            "title": post.title,
                            "subreddit": post.subreddit,
                            "score": post.score,
                            "num_comments": post.num_comments,
                            "url": post.url,
                            "created_utc": post.created_utc.isoformat() if post.created_utc else "",
                            "key_insight": post.title,  # fallback: use title
                        })

                    # Build pain_point_quote_sources from Stage 3 quotes
                    pain_point_quote_sources = []
                    pain_analysis = getattr(state, "pain_point_analysis", None)
                    if pain_analysis and pain_analysis.pain_points:
                        # Build post_id → post lookup for metadata
                        post_lookup: dict[str, object] = {}
                        for p in social.reddit_posts:
                            post_lookup[p.post_id] = p

                        for pp in pain_analysis.pain_points:
                            quotes_with_sources = []
                            raw_quotes = pp.representative_quotes or []
                            raw_ids = pp.source_post_ids or []

                            for i, quote_text in enumerate(raw_quotes):
                                post_id = raw_ids[i] if i < len(raw_ids) else ""
                                post = post_lookup.get(post_id) if post_id else None
                                subreddit = getattr(post, "subreddit", "Unknown") if post else "Unknown"
                                score = getattr(post, "score", 0) if post else 0

                                quotes_with_sources.append({
                                    "quote": quote_text[:300],
                                    "post_id": post_id or "unknown",
                                    "subreddit": subreddit,
                                    "score": str(score),
                                })

                            pain_point_quote_sources.append({
                                "pain_point_title": pp.title,
                                "quotes_with_sources": quotes_with_sources,
                            })

                    evidence_appendix = {
                        "top_reddit_threads": top_reddit_threads,
                        "pain_point_quote_sources": pain_point_quote_sources,
                    }

                report["evidence_appendix"] = evidence_appendix
            except Exception as e:
                logger.debug(f"[Preview Report] Evidence appendix section failed: {e}")
                report["evidence_appendix"] = None

            # ── Stage 3: Pain Points + Analytics ──
            try:
                pain_analysis = getattr(state, "pain_point_analysis", None)
                if pain_analysis and pain_analysis.pain_points:
                    pain_points = pain_analysis.pain_points
                    report["detailed_pain_points"] = [pp.model_dump() for pp in pain_points]
                    # Idea-check runs: the anchored pains' dossier cards slice the first
                    # three quotes — put the idea-relevant excerpts first so the card
                    # under the verdict's own anchor can never show only off-topic ones.
                    from ..report.idea_validation_block import reorder_anchored_pain_quotes
                    reorder_anchored_pain_quotes(self.state, report["detailed_pain_points"])

                    # Synthesize pain_point_analytics from raw data
                    total = len(pain_points)
                    high_severity = sum(
                        1 for pp in pain_points if pp.severity_score >= 0.6
                    )
                    high_opportunity = sum(
                        1 for pp in pain_points
                        if getattr(pp.opportunity_level, "value", str(pp.opportunity_level)) == "high"
                    )

                    # Quadrant distribution
                    quadrants = {
                        "high_severity_high_wtp": 0,
                        "high_severity_low_wtp": 0,
                        "low_severity_high_wtp": 0,
                        "low_severity_low_wtp": 0,
                    }
                    for pp in pain_points:
                        sev_high = pp.severity_score >= 0.5
                        wtp_high = pp.commercial_intent >= 0.5
                        if sev_high and wtp_high:
                            quadrants["high_severity_high_wtp"] += 1
                        elif sev_high:
                            quadrants["high_severity_low_wtp"] += 1
                        elif wtp_high:
                            quadrants["low_severity_high_wtp"] += 1
                        else:
                            quadrants["low_severity_low_wtp"] += 1

                    avg_severity = sum(pp.severity_score for pp in pain_points) / total
                    avg_wtp = sum(pp.commercial_intent for pp in pain_points) / total

                    # Category distribution
                    category_counts: dict[str, int] = {}
                    for pp in pain_points:
                        for cat in (pp.categories or []):
                            category_counts[cat] = category_counts.get(cat, 0) + 1

                    # Top pain point by combined score
                    sorted_pps = sorted(
                        pain_points,
                        key=lambda p: p.severity_score + p.commercial_intent,
                        reverse=True,
                    )
                    top_title = sorted_pps[0].title if sorted_pps else "N/A"

                    report["pain_point_analytics"] = {
                        "total_pain_points": total,
                        "high_severity_count": high_severity,
                        "high_opportunity_count": high_opportunity,
                        "quadrant_distribution": quadrants,
                        "avg_severity": round(avg_severity, 3),
                        "avg_commercial_intent": round(avg_wtp, 3),
                        "top_pain_point_title": top_title,
                        "category_distribution": category_counts,
                    }

                    # Phase 5.5 — carry pain-analysis prose + ranked categories.
                    # These three sibling fields on PainPointAnalysisResult are
                    # always populated by the analyzer crew but were never
                    # surfaced into the preview report (50/50 checkpoints have
                    # them, 0/11 historical previews did).
                    report["pain_analysis_summary"] = getattr(pain_analysis, "analysis_summary", None)
                    report["top_pain_categories"] = list(getattr(pain_analysis, "top_categories", None) or [])
                    report["pain_total_mentions"] = getattr(pain_analysis, "total_mentions", None)
                else:
                    report["detailed_pain_points"] = None
                    report["pain_point_analytics"] = None
                    report["pain_analysis_summary"] = None
                    report["top_pain_categories"] = []
                    report["pain_total_mentions"] = None
            except Exception as e:
                logger.debug(f"[Preview Report] Pain points section failed: {e}")
                report["detailed_pain_points"] = None
                report["pain_point_analytics"] = None
                report["pain_analysis_summary"] = None
                report["top_pain_categories"] = []
                report["pain_total_mentions"] = None

            # ── Stage 3 (cont.): Content Categorization (themes + user segments) ──
            # Persisted so catalog_ideas worker can rehydrate it (avoids the
            # "No user segments available" warning in unified_solution_crew),
            # and so catalog landing pages can render themes/segments.
            try:
                if pain_analysis and pain_analysis.content_categorization:
                    report["content_categorization"] = pain_analysis.content_categorization.model_dump()
                else:
                    report["content_categorization"] = None
            except Exception as e:
                logger.debug(f"[Preview Report] Content categorization section failed: {e}")
                report["content_categorization"] = None

            # ── Stage 4: Audience Mapping (direct pass-through) ──
            try:
                am = getattr(state, "audience_mapping", None)
                report["audience_mapping"] = am.model_dump() if am else None
                drift = getattr(
                    getattr(state, "niche_difficulty_verdict", None),
                    "audience_drift_notice",
                    None,
                )
                if report["audience_mapping"] is not None and drift is not None:
                    report["audience_mapping"]["audience_drift_notice"] = drift.model_dump()
            except Exception as e:
                logger.debug(f"[Preview Report] Audience mapping section failed: {e}")
                report["audience_mapping"] = None

            # ── Stage 5: Solutions → AlternativeSolution[] format ──
            try:
                idea_gen = getattr(state, "idea_generation", None)
                comp_analysis = getattr(state, "competitive_analysis", None)

                alternative_solutions = []
                if idea_gen and idea_gen.solution_ideas:
                    # Build competitive landscape lookup
                    landscapes: dict[str, object] = {}
                    if comp_analysis:
                        for landscape in comp_analysis.solution_landscapes:
                            landscapes[landscape.solution_name] = landscape

                    # Honest brief: pain-title → community quotes (same helper as Phase 2)
                    from ..utils.calibration_notes import extract_criterion_reason
                    from ..utils.honest_brief import build_quotes_by_pain, demand_quotes_for
                    from ..utils.idea_tags import refresh_tag_facets
                    from ..models.solution_idea import visible_ideas
                    quotes_by_pain = build_quotes_by_pain(
                        getattr(getattr(state, "pain_point_analysis", None), "pain_points", None))

                    for solution in visible_ideas(idea_gen.solution_ideas):
                        description = getattr(solution, "description", "") or ""
                        tech_approach = getattr(solution, "technical_approach", "") or ""
                        diff_factors = getattr(solution, "differentiation_factors", []) or []
                        key_diff = diff_factors[0] if diff_factors else ""
                        personas = getattr(solution, "target_personas", []) or []
                        personas_text = ", ".join(personas[:2]) if personas else ""
                        features = getattr(solution, "core_features", []) or []
                        features_text = ", ".join(features[:5]) if features else ""

                        summary = (
                            f"**Overview:** {description}\n\n"
                            f"**Key Features:** {features_text}\n\n"
                            f"**Target Users:** {personas_text}. "
                            f"Differentiates through {key_diff}.\n\n"
                            f"**Technical Approach:** {tech_approach}"
                        ).strip()
                        if not summary:
                            summary = f"{solution.solution_name}: Solution concept for this market"

                        # Extract competitive data
                        landscape = landscapes.get(solution.solution_name)
                        top_competitors = None
                        market_gaps = None
                        competitive_intensity = None
                        if landscape:
                            comps = getattr(landscape, "competitors", []) or []
                            if comps:
                                top_competitors = [getattr(c, "name", str(c)) for c in comps[:3]]
                            gaps = getattr(landscape, "market_gaps", []) or []
                            if gaps:
                                market_gaps = gaps[:3]
                            competitive_intensity = getattr(landscape, "competitive_intensity", None)

                        # Extract scores defensively
                        market_fit = getattr(solution, "market_fit_score", None)
                        tech_feas = getattr(solution, "technical_feasibility_score", None)
                        novelty = getattr(solution, "novelty_score", None)
                        solo_dev = getattr(solution, "solo_dev_feasibility", None)
                        seo_score = getattr(solution, "seo_scalability_score", None)
                        obviousness = getattr(solution, "obviousness_score", None)
                        data_feas = getattr(solution, "data_feasibility_score", None)

                        alt = {
                            "solution_name": solution.solution_name,
                            "idea_id": getattr(solution, "idea_id", None),
                            "idea_revision": getattr(solution, "idea_revision", 1),
                            "identity_origin": getattr(
                                solution, "identity_origin", None,
                            ),
                            "identity_operation_id": getattr(
                                solution, "identity_operation_id", None,
                            ),
                            "headline": getattr(solution, "headline", None),
                            "short_description": getattr(solution, "short_description", None),
                            "summary": summary,
                            "description": description,
                            "value_proposition": getattr(solution, "value_proposition", "") or "",
                            "core_features": features[:5] if features else None,
                            "target_personas": personas[:3] if personas else None,
                            "technical_approach": tech_approach or None,
                            "market_fit_score": float(market_fit) if market_fit is not None else None,
                            "technical_feasibility_score": float(tech_feas) if tech_feas is not None else None,
                            "competitive_advantage_score": None,  # Not available in Phase 1
                            "seo_growth_potential_score": float(seo_score) if seo_score is not None else None,
                            "novelty_score": float(novelty) if novelty is not None else None,
                            "obviousness_score": float(obviousness) if obviousness is not None else None,
                            "solo_dev_feasibility": float(solo_dev) if solo_dev is not None else None,
                            "data_feasibility_score": float(data_feas) if data_feas is not None else None,
                            # review-3 fix: the independent build-feasibility estimate was
                            # computed but never shown to Phase-1 users
                            "build_feasibility_score": (
                                float(bf) if (bf := getattr(solution, "build_feasibility_score", None)) is not None else None),
                            "data_access_model": getattr(solution, "data_access_model", None),
                            "data_acquisition_notes": getattr(solution, "data_acquisition_notes", None),
                            # Audience-framing inputs (the frontend splits the grid on
                            # source_segment; project_type drives the type chip). Without these the
                            # "For {audience}" split can never fire on the preview surface.
                            "source_segment": getattr(solution, "source_segment", None),
                            "project_type": getattr(solution, "project_type", None),
                            "audience_fit": getattr(solution, "audience_fit", None),
                            # Angle-aware evaluation — so the angle badge + comment (and the novelty
                            # tooltip) render on the Phase-1 locked preview report, not just the
                            # selection grid. Without these the preview report shows winning_angle=None.
                            "winning_angle": getattr(solution, "winning_angle", None),
                            "angle_rationale": getattr(solution, "angle_rationale", None),
                            "novelty_rationale": getattr(solution, "novelty_rationale", None),
                            "key_differentiator": key_diff or "Unique approach to this market",
                            "best_suited_for": personas[0] if personas else "General market",
                            "pivot_trigger": "Consider if primary solution faces execution barriers",
                            "top_competitors": top_competitors,
                            "market_gaps": market_gaps,
                            "competitive_intensity": competitive_intensity,
                            "estimated_development_time": getattr(solution, "estimated_development_time", None),
                            "estimated_cac_organic": getattr(solution, "estimated_cac_organic", None),
                            "pricing_model": getattr(solution, "pricing_strategy", None),
                            # Phase 8 of detail-page IA rework — copy through
                            # so /pain-point/[slug] can cross-link to alts.
                            "pain_points_addressed": list(getattr(solution, "pain_points_addressed", []) or []),
                            # Honest brief: evidence + the critic's bear case (None-safe)
                            "demand_quotes": demand_quotes_for(
                                getattr(solution, "pain_points_addressed", None),
                                quotes_by_pain) or None,
                            "critic_concern": extract_criterion_reason(
                                getattr(solution, "calibration_notes", None),
                                "market_fit", max_len=280) or None,
                            "refine_binding_constraint": getattr(solution, "refine_binding_constraint", None),
                            "incumbent_parity": getattr(solution, "incumbent_parity", None),
                            "adjacent_market_parity": getattr(solution, "adjacent_market_parity", None),
                            # Adversarial red-team pass (Stage 5, post-demote) — survives/weakened/
                            # killed verdict + evidence-cited caveats. Threaded through so the G3
                            # chat dossier (backend/src/routes/chat.ts) can cite it; not otherwise
                            # surfaced on the preview report UI.
                            "red_team_verdict": getattr(solution, "red_team_verdict", None),
                            "red_team_caveats": getattr(solution, "red_team_caveats", None),
                            "source_segment_payability": getattr(solution, "source_segment_payability", None),
                            "source_segment_payability_class": getattr(solution, "source_segment_payability_class", None),
                            # Multi-Frame Idea Generation Portfolio: which frame minted this idea's cell
                            "source_frame": getattr(solution, "source_frame", None),
                            # Exact Concept Forge evaluation provenance. These fields are
                            # code-owned and must survive preview materialization so an
                            # accepted result remains linkable to the same activity record
                            # as a demoted result in examined_ruled_out.
                            "evaluation_id": getattr(solution, "evaluation_id", None),
                            "evaluation_source_message_id": getattr(
                                solution, "evaluation_source_message_id", None,
                            ),
                            "proposed_title": getattr(solution, "proposed_title", None),
                            "synthesis_evaluation": getattr(
                                solution, "synthesis_evaluation", None,
                            ),
                            "generation_operation_id": getattr(
                                solution, "generation_operation_id", None,
                            ),
                            "generation_batch_ordinal": getattr(
                                solution, "generation_batch_ordinal", None,
                            ),
                            # Closed-vocabulary filter facets (chips + future filtering).
                            "tags": refresh_tag_facets(solution).model_dump(),
                            "candidate_status": getattr(solution, "candidate_status", None),
                            "merged_from": getattr(solution, "merged_from", None),
                        }
                        alternative_solutions.append(alt)

                report["alternative_solutions"] = alternative_solutions if alternative_solutions else None

                # Extract competitor mentions
                competitor_mentions = getattr(state, "competitor_mentions_formatted", None)
                if not competitor_mentions and comp_analysis:
                    # Build from competitive analysis landscapes
                    all_comp_names = set()
                    for landscape in comp_analysis.solution_landscapes:
                        for comp in (getattr(landscape, "competitors", []) or []):
                            all_comp_names.add(getattr(comp, "name", str(comp)))
                    if all_comp_names:
                        competitor_mentions = ", ".join(sorted(all_comp_names))
                report["overall_competitive_insights"] = (
                    comp_analysis.strategic_recommendations if comp_analysis else None
                )
            except Exception as e:
                logger.debug(f"[Preview Report] Solutions section failed: {e}")
                report["alternative_solutions"] = None
                report["overall_competitive_insights"] = None

            # ── Metadata ──
            try:
                report["generated_at"] = datetime.utcnow().isoformat()

                fs = getattr(state, "filtering_stats", None) or {}
                reddit_count = 0
                twitter_count = 0
                generic_count = 0
                reddit_comments_count = 0
                top_subreddits: list[dict] = []
                social = getattr(state, "social_content", None)
                if social:
                    # Defensive: pydantic models default to [], but treat None
                    # the same to be safe.
                    reddit_posts = getattr(social, "reddit_posts", []) or []
                    twitter_threads = getattr(social, "twitter_threads", []) or []
                    generic_posts = getattr(social, "generic_posts", []) or []
                    reddit_count = len(reddit_posts)
                    twitter_count = len(twitter_threads)
                    generic_count = len(generic_posts)
                    reddit_comments_count = sum(
                        getattr(p, "num_comments", 0) or 0 for p in reddit_posts
                    )
                    from collections import Counter
                    sub_counter = Counter(
                        getattr(p, "subreddit", "") for p in reddit_posts
                        if getattr(p, "subreddit", "")
                    )
                    # Shape matches frontend SubredditBreakdown
                    # (frontend/src/lib/types/report.ts:637-640).
                    top_subreddits = [
                        {"name": name, "post_count": count}
                        for name, count in sub_counter.most_common(10)
                    ]

                report["research_metadata"] = {
                    "reddit_posts_analyzed": reddit_count,
                    "reddit_comments_analyzed": reddit_comments_count,
                    "twitter_threads_analyzed": twitter_count,
                    "generic_posts_analyzed": generic_count,
                    "top_subreddits": top_subreddits,
                    # Materializer-write timestamp (no upstream scrape time).
                    "collection_date": datetime.utcnow().isoformat(),
                    "filtering_stats": fs,
                    "started_at": state.started_at.isoformat() if getattr(state, "started_at", None) else None,
                    "completed_stages": getattr(state, "completed_stages", []),
                    "funnel_counts": dict(getattr(state, "idea_funnel_counts", None) or {}),
                }

                # Phase 5.5 — full quality-signal panel. pain_point_quality_tier
                # already projected as `dataQualityTier`; the rest power the
                # qualitySignals payload (hero badge + engagement-metric tile).
                # `overall_data_quality` is intentionally NOT synthesized here —
                # it's a FinalReport-only field; preview-backed catalog rows
                # leave it null and let the projection default to INSUFFICIENT.
                pain_point_quality_tier = getattr(state, "pain_point_quality_tier", None)
                report["data_quality_summary"] = {
                    "pain_point_quality_tier": pain_point_quality_tier,
                    "social_content_quality_tier": getattr(state, "social_content_quality_tier", None),
                    "pain_point_confidence_score": getattr(state, "pain_point_confidence_score", None),
                    "social_content_metrics": getattr(state, "social_content_metrics", None),
                    # Coverage/pain-concentration notes (informational) so the preview can surface
                    # them next to the ideas the user is choosing among.
                    "quality_caveats": list(getattr(state, "idea_coverage_caveats", None) or []),
                }
                ruled_out = [
                    dict(finding)
                    for finding in (getattr(state, "idea_ruled_out", None) or [])
                ]
                # Older findings stored only the verdict summary even though a demoted idea may
                # remain in the checkpoint pool. Backfill its read-only detail payload during
                # projection; rejected backfill ideas cannot be recovered from old checkpoints.
                ideas_by_name: dict[str, list] = {}
                for idea in (
                    getattr(getattr(state, "idea_generation", None),
                            "solution_ideas", None) or []
                ):
                    ideas_by_name.setdefault(
                        getattr(idea, "solution_name", "") or "",
                        [],
                    ).append(idea)
                ideas_by_ref = {
                    (
                        getattr(idea, "idea_id", None),
                        getattr(idea, "idea_revision", 1),
                    ): idea
                    for idea in (
                        getattr(getattr(state, "idea_generation", None),
                                "solution_ideas", None) or [])
                    if getattr(idea, "idea_id", None)
                }
                for finding in ruled_out:
                    if finding.get("idea"):
                        continue
                    idea = ideas_by_ref.get(
                        (
                            finding.get("idea_id"),
                            finding.get("idea_revision", 1),
                        )
                    )
                    if idea is None:
                        name_matches = ideas_by_name.get(
                            finding.get("idea_name") or "", []
                        )
                        idea = name_matches[0] if len(name_matches) == 1 else None
                    if idea is not None and hasattr(idea, "model_dump"):
                        finding["idea"] = idea.model_dump(mode="json")
                report["examined_ruled_out"] = ruled_out
                report["overlap_groups"] = list(getattr(state, "idea_overlap_groups", None) or [])
                # Thesis partition (utils/idea_theses.py) — the complete grouping the discovery
                # screen renders as one card per product thesis. {} on runs without a non-degraded
                # buyer-job partition; the UI then falls back to the flat candidate list.
                # RE-DERIVED here rather than projected from `state.idea_theses`: this projection
                # also runs after a regenerate/seed batch has merged NEW ideas into the pool, and
                # a stale Stage-5 rollup would leave those ideas in no thesis at all — a silent
                # drop the partition contract forbids. Pure + deterministic (no LLM, no probe),
                # and it reuses the PERSISTED partition so family ids stay stable across batches.
                report["idea_theses"] = dict(getattr(state, "idea_theses", None) or {})
                try:
                    from ..utils.buyer_jobs import partition_from_dict
                    from ..utils.idea_theses import build_idea_theses

                    _p = partition_from_dict(getattr(state, "buyer_job_partition", None))
                    if _p is not None:
                        _fresh = build_idea_theses(
                            getattr(getattr(state, "idea_generation", None),
                                    "solution_ideas", None) or [],
                            partition=_p,
                            cell_allocation=dict(getattr(state, "idea_cell_allocation", None) or {}),
                        )
                        if _fresh:
                            report["idea_theses"] = _fresh
                except Exception as e:
                    logger.debug(f"[Preview Report] thesis re-derivation skipped: {e}")
                # Market-data handoff: same web-verified facts the final report's market_reality
                # carries — shown once here so Phase-2 deep research (utils/market_brief.py)
                # never re-discovers them.
                report["market_reality"] = {
                    "incumbents": list(getattr(state, "niche_incumbent_map", None) or []),
                    "wallet": dict(getattr(state, "niche_wallet_brief", None) or {}),
                }
            except Exception as e:
                logger.debug(f"[Preview Report] Metadata section failed: {e}")
                report["generated_at"] = datetime.utcnow().isoformat()
                report["research_metadata"] = None
                report["data_quality_summary"] = None

            # Research Reality Check (computed end of Phase 1; visible on the discovery screen).
            _verdict = getattr(state, "niche_difficulty_verdict", None)
            report["niche_difficulty_verdict"] = _verdict.model_dump() if _verdict else None

            # Idea portfolio summary (computed end of Phase 1 alongside the verdict above).
            report["idea_portfolio_summary"] = getattr(state, "idea_portfolio_summary", None)
            report["idea_portfolio_summary_fingerprint"] = getattr(
                state, "idea_portfolio_summary_fingerprint", None
            )

            # Guided-mode (chatMode) honesty block (Phase C): gate patches applied earlier in
            # THIS run (G1/G2 — see flows/gate_patches.py) are already stamped on state by the
            # time Phase 1 completes and this preview is materialized.
            try:
                report["user_adjusted"] = getattr(state, "user_adjusted", False)
                report["user_adjustments"] = build_user_adjustments_summary(state)
            except Exception as e:
                logger.debug(f"[Preview Report] User adjustments section failed: {e}")
                report["user_adjusted"] = False
                report["user_adjustments"] = []

            # ── "Check my idea" (validate_idea): the idea_validation block ──
            # Pure reshape of state, marker-selected, rebuilt on EVERY materialize call
            # (regenerate/chat-seed operations rewrite this asset — the block must
            # reconstruct identically from state alone). None for every other mode.
            try:
                from ..report.idea_validation_block import build_idea_validation_block
                _iv = build_idea_validation_block(state, getattr(self, "entry_mode", None))
                if _iv is not None:
                    report["idea_validation"] = _iv
            except Exception as e:
                logger.error(f"[Preview Report] idea_validation block failed: {e}")

            # ── Write to file ──
            job_id = getattr(self, "job_id", None) or getattr(state, "job_id", None)
            if not job_id:
                logger.error("[Preview Report] job_id missing on flow and state; refusing to materialize")
                return None
            out_path = Path(output_dir) / f"preview_report_{job_id}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Keep readers on either the previous complete preview or the new complete
            # preview. Paid follow-up operations treat a None return as a failed commit and
            # compensate both this projection and the authoritative checkpoint.
            temp_path = out_path.with_suffix(".json.tmp")
            try:
                temp_path.write_text(json.dumps(report, indent=2, default=str))
                temp_path.replace(out_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
            logger.info(f"[Preview Report] Materialized to {out_path} ({out_path.stat().st_size} bytes)")
            return str(out_path)

        except Exception as e:
            logger.warning(f"[Preview Report] Failed to materialize: {e}")
            return None

    def _build_post_to_subreddit(self) -> dict[str, str]:
        """post_id -> raw subreddit (Reddit) or platform label (generic sources), built once per
        run from the collected corpus. Feeds the provenance-grounded evidence_segments signal
        (workstream C) -- which segment's community a pain's ACTUAL source posts came from, as
        opposed to the lexical affected_segments vocabulary match."""
        sc = getattr(self.state, "social_content", None)
        out: dict[str, str] = {}
        if not sc:
            return out
        for p in (sc.reddit_posts or []):
            if p.post_id:
                out[p.post_id] = p.subreddit
        for p in (sc.generic_posts or []):
            if p.post_id:
                out[p.post_id] = p.platform
        return out

    def _build_validated_hubs_by_segment(
        self, audience_result, post_to_subreddit: dict[str, str]
    ) -> dict[str, set[str]] | None:
        """Validate each segment's LLM-recalled community hubs before they're allowed to drive
        provenance matching (C) -- an unvalidated hub name is exactly the "hallucinated r/CottageFood"
        failure mode ``reddit_tool.validate_subreddits`` exists to catch elsewhere in the pipeline.

        Validation source (decision): subreddits ACTUALLY PRESENT in the collected corpus
        (``post_to_subreddit`` values) -- real by construction, zero API calls, always available
        (unlike a live PRAW client, which Stage 4 has no guaranteed access to).
        ``reddit_tool.validate_subreddits`` / ``discover_subreddits`` remain the live-API
        enrichment path for widening sparse segment hub lists; out of scope this round (plan
        workstream C risk note: "measure the validated-hub hit-rate first").

        Per-segment candidates come from that segment's own ``discovery_channels`` (free-text like
        "Reddit (r/OwnerOperators, r/Truckers)" -- parsed with the same anchor-parsing regex used
        for Stage-1 anchor communities). When a segment's own discovery_channels yields no
        corpus-validated hub, that segment simply has no validated hubs this run -- it is NOT
        backfilled from the niche-wide ``community_hubs`` prior, which is shared across all
        segments and would let one niche-hub post attribute its pain to multiple unrelated
        segments, contradicting evidence_segments' provenance contract.

        Returns None (never a guess) on any unexpected failure -- callers must treat None as
        "skip the provenance pass this run", leaving evidence_segments None (lexical
        affected_segments is untouched either way).
        """
        try:
            from ..tools.reddit_tool import RedditCollectorTool as _RedditTool

            corpus_subs = {normalize_hub_name(v) for v in post_to_subreddit.values()}
            corpus_subs.discard("")
            if not corpus_subs:
                return {}

            out: dict[str, set[str]] = {}
            for seg in audience_result.audience_segments or []:
                name = getattr(seg, "segment_name", "") or ""
                if not name:
                    continue
                own = {
                    normalize_hub_name(n)
                    for n in _RedditTool.extract_subreddits_from_anchors(
                        getattr(seg, "discovery_channels", None) or []
                    )
                } & corpus_subs
                out[name] = own
            return out
        except Exception as e:
            logger.warning(f"[Stage 4] Provenance hub validation failed, skipping evidence_segments: {e}")
            return None

    def _map_pain_points_to_segments(self, audience_result) -> None:
        """
        Map pain points to audience segments based on keyword matching.

        Phase 3: Enriches PainPoint.affected_segments by matching pain point
        categories and keywords against audience segment primary concerns.

        This enables:
        - Understanding which segments experience which pain points
        - Solution targeting based on segment-pain alignment
        - Marketing messaging specific to segment needs

        Also populates PainPoint.evidence_segments (workstream C) -- a provenance-grounded
        signal (which segment's validated community the pain's ACTUAL source posts came from),
        gated by settings.pain_provenance_segments.

        Args:
            audience_result: AudienceMappingResult from Stage 6.5
        """
        if not self.state.pain_point_analysis:
            return

        # Token-overlap match across the full segment vocab (name + alignment + motivations) vs
        # the full pain text (title + categories + description); leaves a pain null only when
        # nothing overlaps. See utils/segment_matching for why exact-token matching under-mapped.
        segments = audience_result.audience_segments
        mapped_count = 0

        validated_hubs_by_segment: dict[str, set[str]] | None = None
        post_to_subreddit: dict[str, str] = {}
        if settings.pain_provenance_segments:
            post_to_subreddit = self._build_post_to_subreddit()
            validated_hubs_by_segment = self._build_validated_hubs_by_segment(
                audience_result, post_to_subreddit
            )

        provenance_count = 0
        for pain_point in self.state.pain_point_analysis.pain_points:
            matched = match_pain_to_segments(pain_point, segments)
            if matched:
                pain_point.affected_segments = matched
                mapped_count += 1

            if validated_hubs_by_segment:
                provenance = match_pain_by_provenance(
                    pain_point, segments, post_to_subreddit, validated_hubs_by_segment
                )
                if provenance:
                    pain_point.evidence_segments = provenance
                    provenance_count += 1

        if mapped_count > 0:
            logger.info(
                f"[Stage 4] Mapped {mapped_count}/{len(self.state.pain_point_analysis.pain_points)} "
                f"pain points to audience segments"
            )
        if validated_hubs_by_segment is not None:
            logger.info(
                f"[Stage 4] Provenance-matched {provenance_count}/{len(self.state.pain_point_analysis.pain_points)} "
                f"pain points to segments via source-post hub overlap"
            )

    def _attribute_evidence_speakers(self, audience_result) -> None:
        """Stamp durable quote/post speaker roles after the final audience is known.

        This mutates attribution metadata only. It does not add, remove, or reorder
        collected content. Both affected checkpoints are re-saved so later report
        materialization and resume paths never need to re-derive a role from text.
        """
        if not self.state.social_content or not self.state.pain_point_analysis:
            return
        # A few symbol-level unit fixtures construct a bare flow without runtime
        # services. Production flows always own a tracker; do not turn those fixtures
        # into live LLM calls merely because they exercise Stage-4 resume mapping.
        cost_tracker = getattr(self, "cost_tracker", None)
        if cost_tracker is None:
            return

        from ..utils.speaker_attribution import attribute_evidence_speakers

        run = attribute_evidence_speakers(
            self.state.social_content,
            self.state.pain_point_analysis.pain_points,
            audience_result,
            cost_tracker=cost_tracker,
        )
        if not run.changed:
            return

        self.checkpoint_mgr.save_stage("stage_2_social_content", self.state.social_content)
        self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)
        logger.info(
            f"[Stage 4] Speaker attribution stamped {run.candidate_count} contributions "
            f"in {run.llm_calls} batch call(s); {run.unknown_count} unknown"
        )
        if run.failed_batches:
            message = (
                f"Speaker attribution failed for {run.failed_batches} batch(es); affected "
                "conversations remain explicitly unattributed and are not shown as buyer voices."
            )
            if message not in self.state.pipeline_degradations:
                self.state.pipeline_degradations.append(message)

    def _replay_completed_stages_progress(self, completed_stages: list[str]) -> None:
        """
        Emit progress updates for stages completed in previous runs.

        When resuming from checkpoint (manual or after crash/retry), the backend
        database may have been reset. This method replays "completed" status for
        all previously-completed stages to sync DB with checkpoint state.
        """
        # Map checkpoint stage names to (stage_number, display_name)
        stage_mapping = {
            "stage_1_niche_context": (1, "Niche Validation"),
            "stage_2_social_content": (2, "Search & Discovery"),
            "stage_3_pain_points": (3, "Pain Point Analysis"),
            "stage_4_audience_mapping": (4, "Audience Mapping"),
            "stage_5_6_selection": (5, "Solution Pipeline"),
            "stage_5_5_competitive": (5.5, "Competitive Analysis"),
            "stage_6_keyword_validation": (6, "Keyword Validation"),
            "stage_6_seo_strategy": (6, "SEO & Keyword Strategy"),
            "stage_7_pricing_validation": (7, "Pricing Validation"),
            "stage_8_traffic_monetization": (8, "Traffic Monetization"),
            "stage_9_market_sizing": (9, "Market Sizing"),
            "stage_10_solution_refinement": (10, "Solution Refinement"),
            "stage_11_trend_longevity": (11, "Trend Analysis"),
            "stage_12_seo_refinement": (12, "SEO Score Refinement"),
            "stage_13_data_sources": (13, "Data Source Research"),
        }

        for checkpoint_name in completed_stages:
            if checkpoint_name in stage_mapping:
                stage_num, stage_name = stage_mapping[checkpoint_name]
                if stage_num in self.state.skipped_stages:
                    logger.info(f"[Resume] Replaying skipped status for stage {stage_num}: {stage_name}")
                    self._emit_progress(stage_num, stage_name, "skipped", artifact={"skip_reason": "Previously skipped"})
                else:
                    logger.info(f"[Resume] Replaying completed status for stage {stage_num}: {stage_name}")
                    self._emit_progress(stage_num, stage_name, "completed")

    def _execute_remaining_stages(self, stop_after_phase: int | None = None, skip_bulk_replay: bool = False,
                                   stop_after_stage: float | None = None) -> str:
        """
        Execute remaining stages after checkpoint resume.
        Manually calls stage methods based on current_stage.
        Validates prerequisites before executing each stage to prevent cascade failures.

        Args:
            stop_after_phase: If set, stop after this phase (1 = Phase 1 / solution pipeline)
            skip_bulk_replay: If True, skip bulk replay of completed stages at the top.
                Phase 2 skip branches will emit staggered progress instead.
                Used by interactive Phase 2 continuation to avoid all stages
                flashing green at once.
            stop_after_stage: Guided-mode gate stop (1 = after Stage 1, 4 = after Stage 4,
                before Stage 5). Distinct from stop_after_phase: does NOT materialize a
                preview report, only saves cost breakdown + returns the stage artifact.
        """
        REPLAY_STAGGER_DELAY = 0.25  # seconds between replayed stage transitions

        current = self.state.current_stage
        logger.info(f"Executing stages from {current} onwards...")

        # Get list of completed stages to avoid re-running listener stages
        completed_stages = self.checkpoint_mgr.get_completed_stages()

        if not skip_bulk_replay:
            # Default: replay all completed stages at once (crash-recovery, CLI resume)
            self._replay_completed_stages_progress(completed_stages)

        # Stage mapping: (stage_number, method_name)
        # We need to execute stages >= current_stage
        try:
            if current <= 1:
                self.stage_1_validate_niche()

            # Guided-mode G1 gate: stop after Stage 1, before Stage 2 runs. Distinct from
            # stop_after_phase — no preview report is materialized (Phase 1 isn't done),
            # just the cost breakdown + the Stage-1 artifact for the gate card.
            if stop_after_stage is not None and stop_after_stage == 1:
                logger.info("Stopping after Stage 1 (guided-mode gate G1)")
                self.checkpoint_mgr.save_cost_breakdown(self.cost_tracker.export_state())
                return json.dumps(self._extract_stage_artifact(1) or {})

            if current <= 2:
                self.stage_2_search_and_discover()

            if current <= 3 and self._validate_stage_prerequisites(3):
                self.stage_3_analyze_pain_points()
            elif current <= 3:
                logger.info("Skipping Stage 3 (Pain Point Analysis) - prerequisites not met")

            # Stage 4: Only run if not already completed (listener stage)
            if current <= 4 and "stage_4_audience_mapping" not in completed_stages:
                if self._validate_stage_prerequisites(4):
                    self.stage_4_audience_mapping()
                else:
                    logger.info("Skipping Stage 4 (Audience Mapping) - prerequisites not met")
            elif "stage_4_audience_mapping" in completed_stages:
                logger.info("Skipping Stage 4 (Audience Mapping) - already completed")

            # Guided-mode G2 gate: stop after Stage 4, before Stage 5 runs. Placed
            # unconditionally after the Stage-4 block (not gated on it having succeeded) —
            # a failed audience-mapping prerequisite check still leaves pain_point_analysis
            # available, so the gate degrades to a pain-scope-only card (DR N4) instead of
            # never stopping. Distinct from stop_after_phase — no preview report.
            if stop_after_stage is not None and stop_after_stage == 4:
                g2_artifact = self._build_g2_gate_artifact()
                if g2_artifact is None:
                    # Neither pain_point_analysis nor audience_mapping survived — a gate
                    # stop here would produce an unusable AWAITING_GATE with an empty
                    # artifact (dead-end loop, nothing to review or patch). Do NOT stop:
                    # log and fall through to continue the run past the gate entirely.
                    logger.warning(
                        "G2 gate artifact unavailable (no pain analysis or audience "
                        "mapping) — skipping G2 gate stop and continuing the run"
                    )
                else:
                    logger.info("Stopping after Stage 4 (guided-mode gate G2)")
                    # Stage 3's parallel execution path calls
                    # save_stage("stage_4_audience_mapping", ...) at :3772 BEFORE advancing
                    # self.state.current_stage to 5 at :3784, so metadata.json's
                    # current_stage is stamped with the stale pre-advance value. Flush now
                    # so a G2-stopped checkpoint reloads at current_stage=5 (stages 1-4
                    # already marked complete) instead of re-running Stage 3 + Stage 4 on
                    # continuation (duplicate cost, identifier drift vs the validated patch).
                    self.checkpoint_mgr.flush_metadata()
                    self.checkpoint_mgr.save_cost_breakdown(self.cost_tracker.export_state())
                    return json.dumps(g2_artifact)

            # Stage 5: Unified Solution Pipeline
            if "stage_5_6_selection" not in completed_stages:
                if self._validate_stage_prerequisites(5):
                    # Interactive Phase 1 → skip Task 4 (user selects solutions instead)
                    skip = stop_after_phase is not None
                    logger.info("Executing Unified Solution Pipeline (Stage 5)...")
                    self.stage_5_unified_solution_pipeline(skip_selection=skip)
                    # Refresh completed_stages so subsequent stages see Stage 5 checkpoint
                    completed_stages = self.checkpoint_mgr.get_completed_stages()
                else:
                    logger.info("Skipping Stage 5 (Unified Solution Pipeline) - prerequisites not met")
                    # Skip all solution stages if prerequisites not met
                    self.state.current_stage = 6
            else:
                logger.info("Skipping Stage 5 (Unified Solution Pipeline) - already completed")

            # Check if we should stop after a specific stage (interactive mode)
            if stop_after_phase is not None and stop_after_phase <= 1:
                logger.info(f"Stopping after Phase {stop_after_phase} (interactive mode)")
                # Persist Phase-1 cost into the checkpoint so the separate Phase-2 process
                # can seed its tracker and report cumulative (Phase-1 + Phase-2) cost.
                self.checkpoint_mgr.save_cost_breakdown(self.cost_tracker.export_state())
                # CLI deliverable (review-3 fix): the preview materializer previously ran only
                # in the worker path, so --stop-after-phase 1 printed "Report saved to: "
                # with an empty path. Materialize here and return the real path (fail-soft).
                try:
                    preview_path = self._materialize_preview_report(str(settings.output_dir))
                except Exception as e:
                    logger.warning(f"Preview report materialization failed (non-fatal): {e}")
                    preview_path = None
                if preview_path:
                    logger.info(f"[OK] Phase-1 preview report written: {preview_path}")
                return preview_path or ""

            # Auto-run competitive analysis for selected solution if not already done
            if (self.state.solution_selection
                and self.state.solution_selection.selected_solution_name):
                selected_name = self.state.solution_selection.selected_solution_name
                # STRICT matching — do NOT use find_landscape_for_solution() here because
                # its fallback returns the first landscape regardless of name match,
                # which would skip auto-run when wrong solution's data exists.
                has_landscape = False
                if self.state.competitive_analysis:
                    needle = selected_name.strip().lower()
                    has_landscape = any(
                        ls.solution_name.strip().lower() == needle
                        for ls in self.state.competitive_analysis.solution_landscapes
                    )
                if not has_landscape:
                    self._emit_progress(5.5, "Competitive Analysis", "running")
                    logger.info(f"Auto-running competitive analysis for selected solution: {selected_name}")
                    self.analyze_single_solution_competitors(selected_name)  # must let exceptions propagate
                    self._emit_progress(5.5, "Competitive Analysis", "completed")
                    # Refresh completed_stages
                    completed_stages = self.checkpoint_mgr.get_completed_stages()
                elif skip_bulk_replay:
                    status = "skipped" if 5.5 in self.state.skipped_stages else "completed"
                    self._emit_progress(5.5, "Competitive Analysis", status)
                    time.sleep(REPLAY_STAGGER_DELAY)

            # Stage 6: SEO & Keyword Strategy (runs FIRST in Phase 2)
            if "stage_6_seo_strategy" not in completed_stages:
                if "stage_5_6_selection" in completed_stages:
                    if self._validate_stage_prerequisites(6):
                        self.stage_6_seo_strategy()
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 6 (SEO & Keyword Strategy) - prerequisites not met")
                else:
                    logger.info("Skipping Stage 6 (SEO & Keyword Strategy) - awaiting Stage 5")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 6 in self.state.skipped_stages else "completed"
                    self._emit_progress(6, "SEO & Keyword Strategy", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 6 (SEO & Keyword Strategy) - already completed")

            # Stage 7: Pricing Validation
            if "stage_7_pricing_validation" not in completed_stages:
                if "stage_6_seo_strategy" in completed_stages:
                    if self._validate_stage_prerequisites(7):
                        self.stage_7_pricing_validation()
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 7 (Pricing Validation) - prerequisites not met")
                        self._skip_stage(7, "Pricing Validation", "Prerequisites not met")
                else:
                    logger.info("Skipping Stage 7 (Pricing Validation) - awaiting Stage 6")
                    self._skip_stage(7, "Pricing Validation", "Awaiting SEO strategy")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 7 in self.state.skipped_stages else "completed"
                    self._emit_progress(7, "Pricing Validation", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 7 (Pricing Validation) - already completed")

            # Stage 8: Traffic Monetization
            if "stage_8_traffic_monetization" not in completed_stages:
                if "stage_7_pricing_validation" in completed_stages:
                    if self._validate_stage_prerequisites(8):
                        self.stage_8_traffic_monetization()
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 8 (Traffic Monetization) - prerequisites not met")
                        self._skip_stage(8, "Traffic Monetization", "Prerequisites not met")
                else:
                    logger.info("Skipping Stage 8 (Traffic Monetization) - awaiting Stage 7")
                    self._skip_stage(8, "Traffic Monetization", "Awaiting pricing validation")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 8 in self.state.skipped_stages else "completed"
                    self._emit_progress(8, "Traffic Monetization", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 8 (Traffic Monetization) - already completed")

            # Stage 9: Market Sizing
            if "stage_9_market_sizing" not in completed_stages:
                if "stage_8_traffic_monetization" in completed_stages or "stage_7_pricing_validation" in completed_stages:
                    if self._validate_stage_prerequisites(9):
                        self.stage_9_market_sizing()
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 9 (Market Sizing) - prerequisites not met")
                        self._skip_stage(9, "Market Sizing", "Prerequisites not met")
                else:
                    logger.info("Skipping Stage 9 (Market Sizing) - awaiting Stage 7")
                    self._skip_stage(9, "Market Sizing", "Awaiting pricing validation")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 9 in self.state.skipped_stages else "completed"
                    self._emit_progress(9, "Market Sizing", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 9 (Market Sizing) - already completed")

            # Stage 10: Solution Refinement
            if "stage_10_solution_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(10):
                    self.stage_10_solution_refinement()
                    completed_stages = self.checkpoint_mgr.get_completed_stages()
                else:
                    logger.info("Skipping Stage 10 (Solution Refinement) - prerequisites not met")
                    self._skip_stage(10, "Solution Refinement", "Prerequisites not met")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 10 in self.state.skipped_stages else "completed"
                    self._emit_progress(10, "Solution Refinement", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 10 (Solution Refinement) - already completed")

            # Stage 11: Trend Longevity
            if "stage_11_trend_longevity" not in completed_stages:
                if self._validate_stage_prerequisites(11):
                    self.stage_11_trend_longevity()
                else:
                    logger.info("Skipping Stage 11 (Trend Longevity) - prerequisites not met")
                    self._skip_stage(11, "Trend Analysis", "Prerequisites not met")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 11 in self.state.skipped_stages else "completed"
                    self._emit_progress(11, "Trend Analysis", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 11 (Trend Longevity) - already completed")

            # Stage 12: SEO Refinement
            if "stage_12_seo_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(12):
                    self.stage_12_refine_seo_scores()
                else:
                    logger.info("Skipping Stage 12 (SEO Refinement) - prerequisites not met")
                    self._skip_stage(12, "SEO Score Refinement", "Prerequisites not met")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 12 in self.state.skipped_stages else "completed"
                    self._emit_progress(12, "SEO Score Refinement", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 12 (SEO Refinement) - already completed")

            # Stage 13: Data Source Research
            if "stage_13_data_sources" not in completed_stages:
                if self._validate_stage_prerequisites(13):
                    self.stage_13_research_data_sources()
                else:
                    logger.info("Skipping Stage 13 (Data Source Research) - prerequisites not met")
                    self._skip_stage(13, "Data Source Research", "Prerequisites not met")
            else:
                if skip_bulk_replay:
                    status = "skipped" if 13 in self.state.skipped_stages else "completed"
                    self._emit_progress(13, "Data Source Research", status)
                    time.sleep(REPLAY_STAGGER_DELAY)
                logger.info("Skipping Stage 13 (Data Source Research) - already completed")

            # Stage 14: Report Generation
            if "stage_14_report" not in completed_stages:
                self.stage_14_generate_report()
            else:
                logger.info("Skipping Stage 14 (Report Generation) - already completed")

            # Return the actual report path stored during stage 10
            if hasattr(self, 'report_path') and self.report_path:
                return self.report_path

        except Exception as e:
            logger.error(f"Error during stage execution: {e}")
            self.state.errors.append(f"Resume execution failed: {str(e)}")
            raise

        return ""

    # ========== STAGE METHODS ==========

    def stage_1_validate_niche(self):
        """
        Stage 1-4: Niche Input & Validation

        Validates the niche description and generates structured NicheContext using LLM.
        """
        logger.info("=" * 80)
        logger.info("STAGE 1-4: Niche Input & Validation")
        logger.info("=" * 80)
        self._emit_progress(1, "Niche Validation", "running")

        niche = self.niche_description.strip()

        if not niche:
            raise ValueError("Niche description cannot be empty")

        if len(niche) < 10:
            logger.warning("Niche description is very short. Consider providing more detail.")

        if len(niche) > 1000:
            logger.warning("Niche description is very long. Consider condensing to key points.")

        logger.info(f"[OK] Niche validated: {niche[:100]}...")
        logger.info(f"[OK] Target location: {settings.target_location}")
        logger.info(f"[OK] Target language: {settings.target_language}")

        # Store user constraints in state for persistence
        self.state.allowed_project_types = self.allowed_project_types
        self.state.idea_focus = self.idea_focus
        if self.allowed_project_types:
            logger.info(f"[OK] Project type constraints: {', '.join(self.allowed_project_types)}")

        # Generate structured NicheContext using LLM
        logger.info("\nGenerating structured niche context...")
        try:
            niche_context = self._generate_niche_context(niche)
            self.state.niche_context = niche_context
            logger.info("[OK] Niche context generated")
            # Ensure market_segments contains strings
            segments = [str(s) for s in niche_context.market_segments[:3]] if niche_context.market_segments else []
            logger.info(f"  - Market segments: {', '.join(segments)}...")
            logger.info("  - Industry boundaries defined")
        except Exception as e:
            logger.error(f"Failed to generate niche context with LLM: {e}")
            raise RuntimeError(f"Stage 1 failed: Could not generate niche context - {e}") from e

        if (self.entry_mode or "").strip().lower() == "validate_idea":
            # "Check my idea": the input was the user's pitch. Keep the raw pitch for the
            # display/echo surfaces, then REBIND the working niche to the derived market —
            # consumers that take self.niche_description raw (thread-relevance validation
            # in Stage 2) must never grade scraped threads against a product pitch.
            self.state.user_idea_text = niche
            self.niche_description = self.state.niche_context.niche_description
            logger.info(
                "[Idea Check] working niche rebound to derived market; "
                f"brief={'set' if getattr(self.state, 'user_idea_brief', None) else 'MISSING'}")

        self.state.current_stage = 2
        self._mark_stage_complete(1)

        # Checkpoint: Save niche context for resume
        self.checkpoint_mgr.save_stage("stage_1_niche_context", self.state.niche_context)

    def _generate_niche_context(self, niche_input: str) -> "NicheContext":
        """Generate structured NicheContext using LLM with structured output."""
        from ..models.research_state import NicheContext
        from ..utils.llm_service import LLMService

        # entry_mode is only a HINT (a prior nudge) — the input is classified on its own
        # merits below, so an unknown/new/None mode degrades safely to "no signal". Map each
        # known mode to its prior; the classifier is what actually decides audience_scope.
        _mode = (self.entry_mode or "").strip().lower()
        is_idea_check = _mode == "validate_idea"
        _niche_prior = ("the input is likely a plain niche — but still detect an audience if the "
                        "input clearly names one")
        entry_hint = {
            "audience": ('the user picked the "audience" entry mode ("Who are you building for?"), '
                         "so the input is LIKELY a target audience"),
            "idea": f"the user picked the idea/niche entry mode, so {_niche_prior}",
            "discovery": ("the user picked discovery mode, so the input may be either a niche or an "
                          "audience — classify it on its own merits"),
            # Catalog/seed-derived modes mostly bypass this call; if reached, the input is a
            # catalog topic, so treat it like a plain niche.
            "pain_research": f"this is a catalog topic, so {_niche_prior}",
            "deep_idea": f"this is a catalog topic, so {_niche_prior}",
            "pain_remix": f"this is a catalog topic, so {_niche_prior}",
            "validate_idea": ("the input is the user's OWN PRODUCT IDEA — a pitch, not a niche; "
                              "follow the IDEA-CHECK PRE-STEP and research the market the idea "
                              "competes in"),
        }.get(_mode, "there is no entry-mode signal — classify the input purely on its own merits")

        # "Check my idea": an ADDITIVE pre-step over the same A/B-tuned STEP 1-5 prompt —
        # the steps themselves are never restructured. The extra parse fields ride a
        # subclass so the base NicheContext model is untouched (checkpoints restore the
        # stage_1 file as the base model, so the context is rebuilt clean below).
        idea_pre_step = ""
        idea_json_fields = ""
        output_model: type[NicheContext] = NicheContext
        if is_idea_check:
            from pydantic import Field as _Field

            class _IdeaCheckNicheContext(NicheContext):
                idea_name: str = _Field(
                    default="", description="Short display name for the product (max 40 chars)")
                idea_brief: str = _Field(
                    default="",
                    description="One-sentence canonical brief: what it is, who it's for, "
                                "what problem it addresses")
                idea_inferred_fields: list[str] = _Field(default_factory=list)
                # Four FLAT lists (not dict-of-lists: json_schema shaping has no
                # additionalProperties handling) — verbatim pitch keywords per clause,
                # consumed by the seed drift detector + brief-parity probe.
                idea_mechanism_terms: list[str] = _Field(default_factory=list)
                idea_audience_terms: list[str] = _Field(default_factory=list)
                idea_problem_terms: list[str] = _Field(default_factory=list)
                idea_delivery_terms: list[str] = _Field(default_factory=list)

            output_model = _IdeaCheckNicheContext
            idea_pre_step = """
**IDEA-CHECK PRE-STEP — the input is the user's own PRODUCT IDEA (a pitch, not a niche):**
Before the numbered steps, extract the product itself:
- idea_name: a short display name for the product (max 40 characters, title-like, no quotes).
- idea_brief: ONE sentence, at most 300 characters, canonically stating what the product is (its mechanism and form), who it is for, and the problem it addresses. Use only facts from the pitch — never invent features.
- idea_inferred_fields: which of ["audience", "problem", "delivery"] you had to INFER because the pitch does not state them (empty list when all three are stated).
- idea_mechanism_terms / idea_audience_terms / idea_problem_terms / idea_delivery_terms: up to 4 short keywords or phrases QUOTED VERBATIM from the pitch naming each clause (mechanism = what the product does; audience = who it is for; problem = the pain it removes; delivery = the product form or channel). Use [] for any clause listed in idea_inferred_fields — these lists must quote the pitch, never your inference.
Then run STEP 1-5 on the MARKET THE IDEA COMPETES IN: classify the idea's stated buyer in STEP 1, and derive the full product market the idea belongs to in STEPs 2-5. The market — never the product itself — is the research subject.
"""
            idea_json_fields = ('  "idea_name": "...",\n'
                                '  "idea_brief": "...",\n'
                                '  "idea_inferred_fields": ["audience and/or problem and/or delivery — often empty"],\n'
                                '  "idea_mechanism_terms": ["verbatim pitch keywords"],\n'
                                '  "idea_audience_terms": ["verbatim pitch keywords, [] when inferred"],\n'
                                '  "idea_problem_terms": ["verbatim pitch keywords, [] when inferred"],\n'
                                '  "idea_delivery_terms": ["verbatim pitch keywords, [] when inferred"],\n')

        prompt = f"""You are a market research analyst. First CLASSIFY the input, then map the
FULL market it belongs to. Work in THIS EXACT ORDER — each step constrains the next.

**Input:** {niche_input}
Entry-mode hint: {entry_hint}
{idea_pre_step}
**STEP 1 — Classify the input (fill audience_scope, then user_target_audience):**
The input may name a product/market, a target audience (who someone builds for), or both.
- audience_scope — exactly one of:
  - "niche": a product/market/topic with NO specific buyer named.
  - "segment_of_niche": a specific buyer/role/use-case INSIDE one clear product market (you can name the market and its sibling buyers).
  - "community": a buyer group that is its OWN audience spanning MANY unrelated product markets (you cannot pick one market for them).
  - "too_broad": a demographic so general it implies no focusable market.
  Decision pivot — applies ONLY when the input names a buyer/audience. If it names just a product, topic, or market with NO buyer — even when narrowed by a descriptor, attribute, or qualifier — choose niche and skip this pivot.
  When a buyer IS named, choose segment_of_niche vs community by classifying from the FULL phrase, not a single keyword:
  - is this group simply ONE buyer-type of a single nameable product/service category (which has other buyer-types)? → segment_of_niche.
  - or is it defined by a shared identity, passion, hobby, profession, or affiliation whose members get MANY DIFFERENT jobs done across unrelated categories? → community.
  Tie-break: when you cannot name one category without it feeling forced, choose community — never fabricate a parent market the audience merely participates in.
- user_target_audience — the audience string whenever audience_scope is NOT "niche" (verbatim or lightly normalized). It is null ONLY when audience_scope is "niche". If the whole input IS the audience, set this to that input.

**STEP 2 — Name the BROAD market to research (think before writing the niche fields):**
- audience_scope="niche" → the market IS the input.
- audience_scope="segment_of_niche" → the FULL underlying product market the audience sits in (e.g. "athletes interested in peptides" → the peptide-supplements market AS A WHOLE). The stated audience is ONE segment of that market, never the whole market.
- audience_scope="community"/"too_broad" → the AUDIENCE ITSELF is the subject; describe their world. Do NOT invent one product niche for them.

**STEP 3 — niche_description:** 2-3 specific, actionable sentences describing the BROAD market from Step 2 — what it encompasses — NOT just the stated audience's slice of it.

**STEP 4 — market_segments:** 3-7 distinct segments of the SAME subject named in Step 2. Each segment is a GROUP OF PEOPLE defined by the job/outcome they are trying to get done (Jobs-To-Be-Done), specific in needs/context (e.g. "Small e-commerce businesses with 10-50 employees", not "small businesses").
- segment_of_niche → the OTHER major buyer groups across the parent product market (the named audience is at most ONE of them), not only sub-groups of it.
- community / too_broad → distinct sub-groups WITHIN the audience's own world, split by the different jobs/contexts they pursue — not a parent industry's buyers.
- DEMAND-SIDE ONLY: every segment must be phrased as the END-USER group you would build FOR. NEVER list a role that sells to, serves, monetizes, or supplies the audience — exclude platforms, vendors, marketplaces, organizers, sponsors, agencies, producers, AND advisors/planners/coaches/consultants and creators-as-businesses. If a label names a profession that profits from the audience rather than the audience itself, it is WRONG.

**STEP 5 — industry_boundaries:** 2-3 sentences on what is IN vs OUT of the broad market; name adjacent markets that are NOT part of it.

**WORKED EXAMPLE — input "athletes and serious gym-goers interested in peptides":**
- audience_scope = "segment_of_niche"
- user_target_audience = "athletes and serious gym-goers interested in peptides"
- niche_description = the peptide-supplements market overall (research/therapeutic peptides for performance, recovery, longevity, weight management, skin, cognition)
- market_segments (BROAD — note the non-athlete types):
    ["Performance athletes & bodybuilders", "Anti-aging / longevity users",
     "Weight-loss / GLP-1 users", "Injury-recovery & rehab patients",
     "Biohackers & nootropic users", "Skin / cosmetic peptide users"]
- WRONG (silently narrowed to the audience — do NOT do this):
    ["Competitive bodybuilders", "CrossFit athletes", "Natural bodybuilders"]
    — all three are sub-types of the stated audience; the rest of the market is missing.

**More classification examples:**
- "peptide supplements" → audience_scope="niche", user_target_audience=null
- "experienced tirzepatide users" → audience_scope="segment_of_niche", user_target_audience="experienced tirzepatide users" (broad market = peptide/GLP-1 supplements)
- "peptide supplements for bodybuilders" → audience_scope="segment_of_niche", user_target_audience="bodybuilders"
- "porsche owners" → audience_scope="community", user_target_audience="porsche owners"
- "older adults" → audience_scope="too_broad", user_target_audience="older adults"

**HARD RULES (never break):**
1. Never invent an audience from a plain niche → audience_scope="niche", user_target_audience=null.
2. Never fabricate a single product niche for a community/too_broad audience — leave the market open and describe the audience's world.
3. When audience_scope is NOT "niche", describe the BROADER subject from Step 2 (segment_of_niche → the parent product market; community/too_broad → the audience's whole world), never only the literal stated label.

Return a valid JSON object with this structure (emit the fields in this order):
{{
{idea_json_fields}  "audience_scope": "<niche | segment_of_niche | community | too_broad>",
  "user_target_audience": "<the audience, or null only when audience_scope is niche>",
  "niche_description": "...",
  "market_segments": ["segment 1", "segment 2", "..."],
  "industry_boundaries": "..."
}}"""

        # Use centralized LLM service for structured output. Structured-classification tier
        # (first-party model via json_schema) — see settings.niche_context_llm.
        # Moderate temperature (0.5) for balanced understanding + structured strategy.
        context, usage = LLMService.invoke_structured(
            prompt=prompt,
            output_model=output_model,
            temperature=0.5,
            timeout=120,
            model_name=settings.niche_context_llm
        )

        # Record cost if tracker is available
        if hasattr(self, 'cost_tracker') and self.cost_tracker:
            self.cost_tracker.record_llm_usage("Stage 1 - Niche Context", usage.to_dict())

        # Add niche_input to the context
        context.niche_input = niche_input

        if is_idea_check:
            # Stash the parsed idea on state (checkpoint-metadata-persisted), then rebuild
            # a CLEAN base NicheContext — the stage_1 checkpoint is restored as the base
            # model, so the subclass-only fields must never reach it.
            self.state.user_idea_brief = (getattr(context, "idea_brief", "") or "").strip() or None
            self.state.user_idea_inferred_fields = [
                f for f in (getattr(context, "idea_inferred_fields", None) or [])
                if f in ("audience", "problem", "delivery")
            ]
            _identity_terms = {
                key: [t.strip() for t in (getattr(context, f"idea_{key}_terms", None) or [])
                      if isinstance(t, str) and t.strip()][:4]
                for key in ("mechanism", "audience", "problem", "delivery")
            }
            self.state.user_idea_identity_terms = (
                _identity_terms if any(_identity_terms.values()) else None)
            context = NicheContext(**{
                k: v for k, v in context.model_dump().items()
                if k in NicheContext.model_fields
            })

        # Post-parse guards (two directions):
        #  - niche/empty scope → never frame a plain niche: clear any echoed audience.
        #  - focusable scope (segment_of_niche/community/too_broad) → MUST carry an audience
        #    label. The classifier occasionally sets a focusable scope but leaves
        #    user_target_audience null (esp. when the whole input IS the audience, as in
        #    "solve for a group" mode). Fall back to the user's literal input so framing +
        #    audience-aware research actually engage.
        scope = (context.audience_scope or "").strip().lower()
        if scope in ("", "niche"):
            context.audience_scope = "niche"
            context.user_target_audience = None
        else:
            if not (context.user_target_audience or "").strip():
                context.user_target_audience = niche_input.strip()
                logger.info(
                    "[Stage 1] classifier left user_target_audience null on a "
                    f"{scope!r} input — falling back to the literal input")
        logger.info(
            f"[Stage 1] audience_scope={context.audience_scope!r} "
            f"user_target_audience={context.user_target_audience!r}")

        # Second, ISOLATED call: extract niche-anchor entities/exclusions on the
        # reasoning-tier model. Disambiguation needs world knowledge + reasoning
        # (the weakest model is what previously caused niche drift). This call is
        # fully fault-tolerant: any failure falls back to empty anchor lists and
        # the run continues with anchor-based drift protection inactive.
        self._extract_niche_anchors(niche_input, context)
        self._discover_anchor_subreddits(context)
        return context

    def _discover_anchor_subreddits(self, context: "NicheContext") -> None:
        """Find REAL subreddits by keyword search and append them to anchor_communities.

        LLM-recalled community names hallucinate for small niches (live 2026-07-02: Stage 1
        confidently named the nonexistent r/CottageFood while the real r/CottageFoodBusiness and
        r/cottagefoodoperators went unfound). Queries = the anchors call's community_search_terms
        + queries derived from the recalled anchor NAMES themselves (even a hallucinated name is a
        good QUERY). Discovered subs are appended as 'r/Name' entries, so the anchor-subreddit
        collection pass and the report's community hubs pick them up with no further wiring.
        Fail-soft: any error leaves anchor_communities unchanged.
        """
        if not settings.enable_reddit:
            return
        try:
            from ..tools.reddit_tool import RedditCollectorTool as _RedditTool
            tool = _RedditTool()
            queries = list(dict.fromkeys(
                [q.strip().lower() for q in (context.community_search_terms or []) if q and q.strip()]
                + _RedditTool.queries_from_anchor_names(context.anchor_communities or [])
            ))[:6]
            if not queries:
                return
            niche_text = f"{context.niche_description} {context.user_target_audience or ''}"
            found = tool.discover_subreddits(queries, niche_text)
            existing = {n.lower() for n in _RedditTool.extract_subreddits_from_anchors(
                context.anchor_communities or [])}
            for c in found:
                if c["name"].lower() not in existing:
                    context.anchor_communities.append(f"r/{c['name']} (Reddit, discovered)")
        except Exception as e:
            logger.warning(f"[Stage 1] Subreddit discovery failed (non-fatal): {str(e)[:100]}")

    def _extract_niche_anchors(self, niche_input: str, context: "NicheContext") -> None:
        """Populate context.anchor_* fields via an isolated reasoning-model call.

        Never raises: on any failure the anchor fields stay empty (already their
        default) and a telemetry flag marks drift-protection as inactive.
        """
        from pydantic import BaseModel, ConfigDict, Field
        from ..utils.llm_service import LLMService

        class _NicheAnchors(BaseModel):
            model_config = ConfigDict(extra='ignore')
            anchor_entities: list[str] = Field(default_factory=list)
            disambiguation_exclusions: list[str] = Field(default_factory=list)
            anchor_communities: list[str] = Field(default_factory=list)
            audience_jargon: list[str] = Field(default_factory=list)
            community_search_terms: list[str] = Field(default_factory=list)

        # Outcome-oriented prompt + explicit output contract. Two FORMAT-ONLY
        # illustrations from maximally-different, unrelated domains calibrate the
        # required precision level without biasing the content toward any domain.
        prompt = f"""You disambiguate a niche by extracting its anchor vocabulary.

**Niche Input:** {niche_input}
**Refined Description:** {context.niche_description}

Extract five lists. Be specific and derive EVERYTHING from the niche above.

1. **anchor_entities** (8-20): SPECIFIC named entities — proper-noun products,
   compounds, models, brands, or named techniques/protocols — that an on-topic
   discussion in THIS niche will usually reference and an adjacent-but-different
   niche will NOT. Each MUST be a specific named item, never a broad category word.
2. **disambiguation_exclusions**: other audiences/senses/adjacent fields that share
   this niche's words but are OUT of scope (list the out-of-scope meanings). Empty
   list if the niche is genuinely unambiguous.
3. **anchor_communities** (3-8): specific online communities/forums where this niche
   concentrates. Prefer specific over general.
4. **audience_jargon** (8-12): insider terms/phrases the audience actually uses.
   Any acronym or initialism MUST be written as "ACRONYM (full expansion)" — e.g.
   "DVI (digital vehicle inspection)" — never a bare acronym.
5. **community_search_terms** (3-6): SHORT terms (STRICTLY 1-3 words) someone would
   type into a community-search box to FIND this niche's groups — the topic/identity
   words communities NAME themselves after (e.g. a hobby name, a practitioner identity,
   a defining compound term). NOT jargon, NOT sentences.

COMPLETION CHECK before answering: verify every anchor_entities item is a specific
named item (proper noun / compound / model / branded technique), NOT a category word.

--- FORMAT ILLUSTRATIONS (unrelated domains — show the PRECISION LEVEL only; never
reuse this content, derive everything from the niche above) ---
• Niche "home espresso enthusiasts": anchor_entities ~ [Niche Zero, Gaggia Classic,
  Niche grinders, 58mm portafilter, James Hoffmann, VST basket]; exclusions ~
  [commercial café equipment, pod/capsule machines].
• Niche "indie iOS game developers": anchor_entities ~ [SpriteKit, TestFlight,
  App Store Connect, StoreKit 2, GameplayKit]; exclusions ~ [Android/Unity-only devs,
  AAA console studios].
--- END ILLUSTRATIONS ---

Return JSON: {{"anchor_entities": [...], "disambiguation_exclusions": [...],
"anchor_communities": [...], "audience_jargon": [...], "community_search_terms": [...]}}"""

        try:
            anchors, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_NicheAnchors,
                timeout=120,
                model_name=settings.brainstorm_llm,
                reasoning_effort="medium",
            )
            context.anchor_entities = anchors.anchor_entities or []
            context.disambiguation_exclusions = anchors.disambiguation_exclusions or []
            context.anchor_communities = anchors.anchor_communities or []
            context.audience_jargon = anchors.audience_jargon or []
            context.community_search_terms = anchors.community_search_terms or []
            if hasattr(self, 'cost_tracker') and self.cost_tracker:
                self.cost_tracker.record_llm_usage("Stage 1 - Niche Anchors", usage.to_dict())
        except Exception as e:
            # Fault-tolerant: keep empty anchors, continue with protection inactive.
            logger.warning(
                f"Niche-anchor extraction failed (non-fatal, drift protection "
                f"inactive for this run): {e}"
            )

        # Telemetry: anchors are 'active' only with enough named entities to be
        # meaningful. Below the threshold, every downstream anchor gate is a no-op
        # (fail-open) so generic niches are never starved.
        anchors_active = len(context.anchor_entities) >= 3
        self.state.niche_drift_telemetry["anchors_active"] = anchors_active
        self.state.niche_drift_telemetry["anchor_entity_count"] = len(context.anchor_entities)
        if anchors_active:
            logger.info(
                f"[OK] Niche anchors: {len(context.anchor_entities)} entities, "
                f"{len(context.disambiguation_exclusions)} exclusions "
                f"(e.g. {', '.join(context.anchor_entities[:5])})"
            )
        else:
            logger.warning(
                f"[WARN] Niche-anchor extraction produced only "
                f"{len(context.anchor_entities)} entities (<3) — drift protection "
                f"inactive for this run."
            )

    # ── Platform search pipeline methods (Stage 2 parallel execution) ──────

    def _search_reddit_pipeline(self, search_queries: list, niche_description: str) -> PlatformSearchResult:
        """Full Reddit pipeline: Serper search → freshness → PRAW → dedup → LLM validation → collect."""
        try:
            from ..utils.validation import ThreadRelevanceValidator
            validator = ThreadRelevanceValidator()

            reddit_queries = [q for q in search_queries if q.platform in ("reddit", "both")]
            logger.info(f"[Reddit] Searching for relevant discussions ({len(reddit_queries)}/{len(search_queries)} queries)...")
            reddit_results = []
            reddit_query_strs = [f"site:reddit.com {sq.query}" for sq in reddit_queries]
            batch_results = self.search_tool.batch_run_raw(reddit_query_strs) if reddit_query_strs else {}
            for search_query, q_str in zip(reddit_queries, reddit_query_strs):
                try:
                    results = batch_results.get(q_str, {})
                    search_items = SearchHelper.extract_results_from_serper(results, "reddit.com")
                    reddit_results.extend(search_items)
                except Exception as e:
                    logger.error(f"[Reddit] Search failed for '{search_query.query}': {e}")

            standard_count = len(reddit_results)
            logger.info(f"[Reddit] Found {standard_count} results from standard search")

            # ── Freshness Serper pass ──
            freshness_serper_count = 0
            if settings.reddit_freshness_search_enabled:
                freshness_queries = reddit_queries[:max(1, math.ceil(len(reddit_queries) * settings.reddit_freshness_query_fraction))]
                freshness_query_strs = [f"site:reddit.com {sq.query}" for sq in freshness_queries]
                freshness_batch = (
                    self.search_tool.batch_run_raw(freshness_query_strs, tbs=settings.reddit_freshness_tbs)
                    if freshness_query_strs else {}
                )
                for search_query, q_str in zip(freshness_queries, freshness_query_strs):
                    try:
                        results = freshness_batch.get(q_str, {})
                        search_items = SearchHelper.extract_results_from_serper(results, "reddit.com")
                        reddit_results.extend(search_items)
                        freshness_serper_count += len(search_items)
                    except Exception as e:
                        logger.error(f"[Reddit] Freshness search failed for '{search_query.query}': {e}")

                logger.info(f"[Reddit] Found {freshness_serper_count} results from freshness search (tbs={settings.reddit_freshness_tbs})")

            # ── PRAW native search pass ──
            if settings.reddit_native_search_enabled:
                try:
                    from ..tools.reddit_tool import RedditCollectorTool as _RedditTool

                    existing_urls = [r.url for r in reddit_results]
                    url_subs = _RedditTool.extract_subreddits_from_urls(existing_urls)
                    praw_tool = _RedditTool()

                    # Anchor-subreddit targeting (always on; live-verified 2026-07-02): prepend the
                    # DEDICATED communities Stage 1 identified (anchor_communities) ahead of the
                    # URL-extracted subs — otherwise the native pass only re-searches what generic
                    # keyword search already found (rich-get-richer; r/Baking 149 posts, dedicated sub
                    # 0). Anchor names are LLM output → pre-validate so a hallucinated sub can't trip
                    # the search circuit breaker (live-proven: caught nonexistent 'r/CottageFood' and
                    # degraded to a clean no-op). Known limit: LLM-memory anchors are unreliable for
                    # small communities — a PRAW subreddits.search discovery step is the backlogged fix.
                    anchors = getattr(self.state.niche_context, "anchor_communities", None) or []
                    anchor_subs = _RedditTool.extract_subreddits_from_anchors(anchors)
                    if anchor_subs:
                        anchor_subs = praw_tool.validate_subreddits(anchor_subs)
                        logger.info(f"[Reddit] Anchor subreddits from Stage 1: {anchor_subs}")
                    seen_subs: set[str] = set()
                    target_subs = []
                    for s in anchor_subs + url_subs:
                        if s.lower() not in seen_subs:
                            seen_subs.add(s.lower())
                            target_subs.append(s)
                    target_subs = target_subs[:settings.reddit_native_max_subreddits]

                    if target_subs:
                        native_queries = reddit_queries[:max(1, math.ceil(len(reddit_queries) * settings.reddit_native_search_query_fraction))]
                        praw_results = praw_tool.search_subreddits(
                            queries=[q.query for q in native_queries],
                            subreddits=target_subs,
                            time_filter=settings.reddit_native_search_time_filter,
                            max_results_per_query=settings.reddit_native_search_max_results,
                            already_collected_urls=set(existing_urls),
                        )
                        reddit_results.extend(praw_results)
                        logger.info(f"[Reddit] Found {len(praw_results)} results from PRAW native search")
                        # Small dedicated subs (live-proven r/CottageFoodBusiness, 83 subscribers):
                        # query search inside them is structurally empty — wholesale-fetch their
                        # new/top listings instead; thread validation grades them like any candidate.
                        wholesale = praw_tool.fetch_small_subreddit_posts(
                            target_subs,
                            already_collected_urls=set(existing_urls) | {r.url for r in praw_results},
                        )
                        reddit_results.extend(wholesale)
                        if wholesale:
                            logger.info(f"[Reddit] Wholesale small-sub fetch added {len(wholesale)} candidates")
                    else:
                        logger.info("[Reddit] No subreddits identified for PRAW native search")
                except Exception as e:
                    logger.error(f"[Reddit] PRAW native search failed: {e}")

            # Deduplicate by URL
            seen_urls: set[str] = set()
            unique_reddit_results = []
            for result in reddit_results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_reddit_results.append(result)

            new_from_freshness = len(unique_reddit_results) - standard_count
            logger.info(f"[Reddit] After dedup: {len(unique_reddit_results)} unique ({new_from_freshness} new from freshness)")

            # LLM validation
            logger.info("[Reddit] Validating thread relevance...")
            from ..utils.validation.niche_anchor import format_anchor_block
            validated = validator.validate_batch_parallel(
                niche_description=niche_description,
                search_results=unique_reddit_results,
                batch_size=10,
                anchor_guidance=format_anchor_block(self.state.niche_context),
            )
            # Keep threads at/above the relevance grade; carry the grade so collect_posts can
            # relax engagement thresholds for more-relevant threads and tag posts for the
            # relevance-weighted token budget downstream.
            min_grade = settings.thread_relevance_min_grade
            grade_by_url = {result.url: g for result, g in validated if g >= min_grade}
            reddit_urls = list(grade_by_url)
            filtered_count = len(unique_reddit_results) - len(reddit_urls)
            logger.info(f"[Reddit] Filtered {filtered_count} irrelevant, kept {len(reddit_urls)} relevant discussions")

            # Degradation ledger: batches whose LLM grading failed OPEN kept threads at a default
            # grade without real relevance grading — surface it as a report quality caveat.
            if getattr(validator, "failed_open_threads", 0):
                msg = (f"Thread relevance grading unavailable for {validator.failed_open_threads} "
                       f"Reddit thread(s) across {validator.failed_open_batches} batch(es) (LLM errors, "
                       f"fail-open) — those threads were kept ungraded and may be off-topic.")
                if msg not in self.state.pipeline_degradations:
                    self.state.pipeline_degradations.append(msg)

            # Collect full posts
            logger.info("[Reddit] Collecting posts and comments...")
            reddit_posts = self.reddit_tool.collect_posts(reddit_urls, grade_by_url=grade_by_url)
            logger.info(f"[Reddit] Collected {len(reddit_posts)} quality posts")

            return PlatformSearchResult(
                posts=reddit_posts,
                unique_results_count=len(unique_reddit_results),
                relevant_urls_count=len(reddit_urls),
            )
        except Exception as exc:
            logger.error(f"[Reddit] Pipeline failed: {exc}")
            return PlatformSearchResult()

    def _search_twitter_pipeline(self, search_queries: list, niche_description: str) -> PlatformSearchResult:
        """Full Twitter pipeline: Serper search → dedup → LLM validation → collect."""
        try:
            from ..utils.validation import ThreadRelevanceValidator
            validator = ThreadRelevanceValidator()

            twitter_queries = [q for q in search_queries if q.platform in ("twitter", "both")]
            logger.info(f"[Twitter] Searching for relevant discussions ({len(twitter_queries)}/{len(search_queries)} queries)...")
            twitter_results = []
            twitter_query_strs = [f"(site:twitter.com OR site:x.com) {sq.query}" for sq in twitter_queries]
            twitter_batch = self.search_tool.batch_run_raw(twitter_query_strs) if twitter_query_strs else {}
            for search_query, q_str in zip(twitter_queries, twitter_query_strs):
                try:
                    results = twitter_batch.get(q_str, {})
                    twitter_results_1 = SearchHelper.extract_results_from_serper(results, "twitter.com")
                    twitter_results_2 = SearchHelper.extract_results_from_serper(results, "x.com")
                    twitter_results.extend(twitter_results_1 + twitter_results_2)
                except Exception as e:
                    logger.error(f"[Twitter] Search failed for '{search_query.query}': {e}")

            seen_urls: set[str] = set()
            unique_twitter_results = []
            for result in twitter_results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_twitter_results.append(result)

            logger.info(f"[Twitter] Found {len(unique_twitter_results)} unique results from {len(twitter_queries)} queries")

            # LLM validation
            logger.info("[Twitter] Validating thread relevance...")
            from ..utils.validation.niche_anchor import format_anchor_block
            validated = validator.validate_batch_parallel(
                niche_description=niche_description,
                search_results=unique_twitter_results,
                batch_size=10,
                anchor_guidance=format_anchor_block(self.state.niche_context),
            )
            twitter_urls = [result.url for result, g in validated if g >= settings.thread_relevance_min_grade]
            filtered_count = len(unique_twitter_results) - len(twitter_urls)
            logger.info(f"[Twitter] Filtered {filtered_count} irrelevant, kept {len(twitter_urls)} relevant discussions")

            # Collect full threads
            logger.info("[Twitter] Collecting threads...")
            twitter_threads = self.twitter_tool.collect_threads(twitter_urls)
            logger.info(f"[Twitter] Collected {len(twitter_threads)} quality threads")

            return PlatformSearchResult(
                posts=twitter_threads,
                unique_results_count=len(unique_twitter_results),
                relevant_urls_count=len(twitter_urls),
            )
        except Exception as exc:
            logger.error(f"[Twitter] Pipeline failed: {exc}")
            return PlatformSearchResult()

    def _search_hackernews_pipeline(self, search_queries: list, niche_description: str) -> PlatformSearchResult:
        """Full HN pipeline: Algolia candidates → strict semantic gate → collect."""
        try:
            hn_queries = [q.query for q in search_queries if q.platform in ("hackernews", "both")]
            if not hn_queries:
                hn_queries = [q.query for q in search_queries[:8]]
            logger.info(f"[HN] Collecting stories via Algolia API ({len(hn_queries)} queries)...")
            from ..utils.validation.niche_anchor import format_anchor_block
            collection = self.hackernews_tool.search_relevant_and_collect(
                queries=hn_queries,
                niche_description=niche_description,
                min_points=settings.min_hn_points,
                min_hn_comments=settings.min_hn_comments,
                max_total=25,
                anchor_guidance=format_anchor_block(self.state.niche_context),
            )
            logger.info(
                f"[HN] Collected {len(collection.posts)} stories "
                f"({collection.relevant_count}/{collection.candidate_count} relevant candidates)"
            )
            return PlatformSearchResult(
                posts=collection.posts,
                unique_results_count=collection.candidate_count,
                relevant_urls_count=collection.relevant_count,
            )
        except Exception as exc:
            logger.warning(f"[HN] Pipeline failed (non-fatal): {exc}")
            return PlatformSearchResult()

    def _search_youtube_pipeline(self, search_queries: list, niche_description: str) -> PlatformSearchResult:
        """Full YouTube pipeline: Serper search → dedup → transcript collection + token_jaccard filtering."""
        try:
            yt_queries = [q.query for q in search_queries if q.platform in ("youtube", "both")]
            if not yt_queries:
                yt_queries = [q.query for q in search_queries[:6]]

            logger.info(f"[YouTube] Searching for videos ({len(yt_queries)} queries)...")
            yt_serper_results = []
            seen_yt_urls: set[str] = set()
            yt_search_queries = [SearchHelper.build_youtube_query(q) for q in yt_queries[:10]]
            yt_batch = self.search_tool.batch_run_raw(yt_search_queries) if yt_search_queries else {}
            for query, yt_search_query in zip(yt_queries[:10], yt_search_queries):
                try:
                    results = yt_batch.get(yt_search_query, {})
                    extracted = SearchHelper.extract_results_from_serper(results, "youtube.com")
                    for r in extracted:
                        if r.url not in seen_yt_urls:
                            seen_yt_urls.add(r.url)
                            yt_serper_results.append(r)
                except Exception as exc:
                    logger.debug(f"[YouTube] Serper search failed for '{query}': {exc}")

            if not yt_serper_results:
                logger.info("[YouTube] No Serper results found")
                return PlatformSearchResult()

            yt_niche_keywords = list(set(
                word for q in yt_queries[:5]
                for word in q.lower().split() if len(word) > 2
            ))
            yt_candidate_cap = settings.max_youtube_videos * 2
            youtube_posts = self.youtube_tool.search_and_collect(
                serper_results=yt_serper_results[:yt_candidate_cap],
                niche_description=niche_description,
                min_views=settings.min_youtube_views,
                max_total=settings.max_youtube_videos,
                niche_keywords=yt_niche_keywords,
            )
            logger.info(f"[YouTube] Collected {len(youtube_posts)} transcripts")
            return PlatformSearchResult(
                posts=youtube_posts,
                unique_results_count=len(yt_serper_results),
                relevant_urls_count=len(youtube_posts),
            )
        except Exception as exc:
            logger.warning(f"[YouTube] Pipeline failed (non-fatal): {exc}")
            return PlatformSearchResult()

    def stage_2_search_and_discover(self):
        """
        Stage 2: Search & Discover

        Searches Reddit, Twitter, HN, and YouTube in parallel for social discussions.
        """
        logger.info("=" * 80)
        logger.info("STAGE 5: Search & Discover")
        logger.info("=" * 80)
        self._emit_progress(2, "Search & Discovery", "running")

        # Generate strategic search queries
        from ..utils.generation import QueryGenerator
        query_gen = QueryGenerator()

        # Build enabled platforms list from settings
        enabled_platforms = []
        if settings.enable_reddit:
            enabled_platforms.append("reddit")
        if settings.enable_twitter:
            enabled_platforms.append("twitter")
        if settings.enable_hackernews:
            enabled_platforms.append("hackernews")
        if settings.enable_youtube:
            enabled_platforms.append("youtube")

        logger.info(f"Generating search queries for {len(enabled_platforms)} platforms: {enabled_platforms}...")
        _aud = self._audience_for_research()
        if _aud:
            logger.info(f"[Part C] Audience-aware research ENGAGED — soft, additive bias for: {_aud!r}")
        queries = query_gen.generate_all_platform_queries(
            niche_description=self.niche_description,
            niche_context=self.state.niche_context,
            enabled_platforms=enabled_platforms if enabled_platforms else None,
            target_audience=_aud,
        )

        # Capture niche-anchor query telemetry for the Stage-10 drift caveat.
        if getattr(query_gen, "anchor_telemetry", None):
            self.state.niche_drift_telemetry.update(query_gen.anchor_telemetry)

        # Convert to SearchQuery objects
        from ..models.research_state import SearchQuery
        self.state.search_queries = [
            SearchQuery(
                query=q["query"],
                query_type=q.get("type", "problem"),
                platform=q.get("platform", "both")
            )
            for q in queries
        ]
        logger.info(f"[OK] Generated {len(self.state.search_queries)} search queries")

        # ── Run all platform pipelines in parallel ──
        from ..utils.parallel_collection import ParallelCollector

        tasks = []
        if settings.enable_reddit:
            tasks.append(("reddit", lambda: self._search_reddit_pipeline(self.state.search_queries, self.niche_description)))
        if settings.enable_twitter:
            tasks.append(("twitter", lambda: self._search_twitter_pipeline(self.state.search_queries, self.niche_description)))
        if settings.enable_hackernews and self.hackernews_tool:
            tasks.append(("hackernews", lambda: self._search_hackernews_pipeline(self.state.search_queries, self.niche_description)))
        if settings.enable_youtube and self.youtube_tool:
            tasks.append(("youtube", lambda: self._search_youtube_pipeline(self.state.search_queries, self.niche_description)))

        if not tasks:
            logger.warning("All social content sources disabled — no social content will be collected")

        logger.info(f"Running {len(tasks)} platform pipelines in parallel: {[t[0] for t in tasks]}")
        parallel_results = ParallelCollector.collect_parallel(tasks, max_workers=min(len(tasks), 4)) if tasks else {}

        # Unpack results (None-safe: ParallelCollector stores None on failure, skipped platforms absent)
        _empty = PlatformSearchResult()
        reddit_result = parallel_results.get("reddit") or _empty
        twitter_result = parallel_results.get("twitter") or _empty
        hn_result = parallel_results.get("hackernews") or _empty
        yt_result = parallel_results.get("youtube") or _empty

        reddit_posts = reddit_result.posts
        twitter_threads = twitter_result.posts
        hn_posts = hn_result.posts
        youtube_posts = yt_result.posts

        if not settings.enable_reddit:
            logger.info("Reddit collection disabled (ENABLE_REDDIT=false)")
        if not settings.enable_twitter:
            logger.info("Twitter collection disabled (ENABLE_TWITTER=false)")

        # Record which platforms were searched and what they found
        self.state.sources_searched = {
            "reddit": {"enabled": settings.enable_reddit, "posts_found": len(reddit_posts)},
            "twitter": {"enabled": settings.enable_twitter, "posts_found": len(twitter_threads)},
            "hackernews": {"enabled": settings.enable_hackernews, "posts_found": len(hn_posts)},
            "youtube": {"enabled": settings.enable_youtube, "posts_found": len(youtube_posts)},
        }

        # Hard stop if insufficient social content (< 3 posts prevents poisoned checkpoints)
        total_content = len(reddit_posts) + len(twitter_threads) + len(hn_posts) + len(youtube_posts)
        if total_content < 3:
            logger.error("=" * 80)
            logger.error(f"PIPELINE STOPPED: Insufficient social content ({total_content} posts, minimum 3)")
            logger.error("Cannot proceed — pain point analysis requires at least 3 discussions.")
            logger.error("Possible causes:")
            logger.error("  - Niche too narrow (try broadening the search)")
            logger.error("  - Reddit/Twitter API issues")
            logger.error("  - All sources returned empty results")
            logger.error("=" * 80)
            raise ValueError(f"Insufficient social content ({total_content} posts, minimum 3). Cannot proceed — would fail at pain point analysis.")

        # Token monitoring: Estimate size of collected content
        if settings.token_monitoring_enabled:
            _monitor = ContentTokenMonitor()  # Reserved for future token monitoring

            # Estimate Reddit content size (rough approximation)
            reddit_char_count = sum(
                len(post.title) + len(post.selftext or "") +
                sum(len(c.body) for c in post.comments)
                for post in reddit_posts
            )
            logger.info(
                f"Stage 5 - Collected Reddit content: {len(reddit_posts)} posts, "
                f"~{reddit_char_count:,} characters"
            )

            # Log post freshness distribution
            if reddit_posts:
                from datetime import datetime as _dt, timezone as _tz
                _now = _dt.now(_tz.utc)
                fresh_count = sum(1 for p in reddit_posts if (_now - p.created_utc).days < 180)
                mid_count = sum(1 for p in reddit_posts if 180 <= (_now - p.created_utc).days < 365)
                old_count = sum(1 for p in reddit_posts if (_now - p.created_utc).days >= 365)
                total = len(reddit_posts)
                days_list = sorted([(_now - p.created_utc).days for p in reddit_posts])
                median_days = days_list[len(days_list) // 2]
                logger.info(
                    f"[OK] Post freshness distribution: "
                    f"{fresh_count * 100 // total}% <180d, "
                    f"{mid_count * 100 // total}% 180-365d, "
                    f"{old_count * 100 // total}% >365d "
                    f"(median: {median_days}d)"
                )

            # Estimate Twitter content size (rough approximation)
            if twitter_threads:
                twitter_char_count = sum(
                    len(thread.original_tweet.text) +
                    sum(len(reply.text) for reply in thread.replies)
                    for thread in twitter_threads
                )
                logger.info(
                    f"Stage 5 - Collected Twitter content: {len(twitter_threads)} threads, "
                    f"~{twitter_char_count:,} characters"
                )
            else:
                twitter_char_count = 0

            # Log combined estimate (including generic sources)
            generic_char_count = sum(len(p.body or "") for p in hn_posts + youtube_posts)
            total_chars = reddit_char_count + twitter_char_count + generic_char_count
            # Rough token estimate (1 token ≈ 4 chars)
            estimated_tokens = total_chars // 4
            logger.info(
                f"Stage 5 - Total collected content: ~{total_chars:,} characters "
                f"(~{estimated_tokens:,} tokens estimated, "
                f"generic: ~{generic_char_count:,} chars from {len(hn_posts)} HN + {len(youtube_posts)} YouTube)"
            )

        # Store in social_content collection
        from ..models.social_content import SocialContentCollection
        total_generic_responses = sum(p.num_responses for p in hn_posts + youtube_posts)
        self.state.social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=twitter_threads,
            generic_posts=hn_posts + youtube_posts,
            total_generic_responses=total_generic_responses,
        )

        # Track filtering statistics (Phase 2.5: Data quality transparency)
        reddit_searched = reddit_result.unique_results_count
        reddit_relevant = reddit_result.relevant_urls_count
        twitter_searched = twitter_result.unique_results_count
        twitter_relevant = twitter_result.relevant_urls_count
        yt_searched = yt_result.unique_results_count
        yt_collected = len(youtube_posts)
        hn_searched = hn_result.unique_results_count
        hn_relevant = hn_result.relevant_urls_count
        hn_collected = len(hn_posts)

        total_searched = reddit_searched + twitter_searched + yt_searched + hn_searched
        total_relevant = reddit_relevant + twitter_relevant + yt_collected + hn_relevant

        self.state.filtering_stats = {
            "reddit_urls_searched": reddit_searched,
            "reddit_urls_relevant": reddit_relevant,
            "reddit_filtering_rate": (reddit_searched - reddit_relevant) / reddit_searched if reddit_searched > 0 else 0,
            "twitter_urls_searched": twitter_searched,
            "twitter_urls_relevant": twitter_relevant,
            "twitter_filtering_rate": (twitter_searched - twitter_relevant) / twitter_searched if twitter_searched > 0 else 0,
            "youtube_urls_searched": yt_searched,
            "youtube_posts_collected": yt_collected,
            "hackernews_urls_searched": hn_searched,
            "hackernews_urls_relevant": hn_relevant,
            "hackernews_posts_collected": hn_collected,
            "total_urls_searched": total_searched,
            "total_urls_relevant": total_relevant,
            "overall_filtering_rate": (
                (total_searched - total_relevant) / total_searched
            ) if total_searched > 0 else 0,
        }
        logger.info(
            f"[Filtering Stats] Reddit: {reddit_relevant}/{reddit_searched} relevant "
            f"({self.state.filtering_stats['reddit_filtering_rate']*100:.1f}% filtered)"
        )
        if twitter_searched > 0:
            logger.info(
                f"[Filtering Stats] Twitter: {twitter_relevant}/{twitter_searched} relevant "
                f"({self.state.filtering_stats['twitter_filtering_rate']*100:.1f}% filtered)"
            )
        if yt_searched > 0:
            logger.info(f"[Filtering Stats] YouTube: {yt_collected}/{yt_searched} collected")
        if hn_searched > 0:
            logger.info(
                f"[Filtering Stats] HN: {hn_relevant}/{hn_searched} relevant, "
                f"{hn_collected} collected"
            )

        # Validate social content quality
        from ..utils.validation import SocialContentValidator
        validator = SocialContentValidator()
        quality_tier, metrics = validator.validate_quality(self.state.social_content)

        # Store quality assessment in state (for reporting)
        self.state.social_content_quality_tier = quality_tier
        self.state.social_content_metrics = metrics

        # Early warning for insufficient content
        if quality_tier == "INSUFFICIENT":
            logger.error("=" * 80)
            logger.error("⚠️  CRITICAL: Social content quality below minimum threshold")
            logger.error("    Pipeline may produce poor results with limited data.")
            logger.error("    Consider:")
            logger.error("    1. Expanding search query count (NUM_SEARCH_QUERIES)")
            logger.error("    2. Lowering minimum engagement thresholds")
            logger.error("    3. Adjusting niche focus to broader market")
            logger.error("=" * 80)
            # Continue anyway (user decision), but flag in errors
            self.state.errors.append(f"Stage 2: Insufficient social content quality ({quality_tier})")

        # Only advance stage and save checkpoint if quality is sufficient
        # (Fix 1 should prevent INSUFFICIENT from reaching here, but defense-in-depth)
        if quality_tier == "INSUFFICIENT":
            logger.warning(
                "Stage 2 quality is INSUFFICIENT — not advancing stage or saving checkpoint. "
                "Next run will re-collect from scratch."
            )
        else:
            self.state.current_stage = 3
            self._mark_stage_complete(2, used_fallback=(quality_tier == "MINIMAL"))
            self.checkpoint_mgr.save_stage("stage_2_social_content", self.state.social_content)

    def _run_pain_point_crew(self) -> dict:
        """
        Helper method to run PainPointCrew in parallel execution context.

        Returns:
            Dict with 'result' (PainPointAnalysisResult) and 'usage_metrics'
        """
        logger.info("[Parallel] Starting PainPointCrew...")

        pain_point_crew = PainPointCrew(
            reddit_posts=self.state.social_content.reddit_posts,
            twitter_threads=self.state.social_content.twitter_threads,
            generic_posts=self.state.social_content.generic_posts,
            niche_description=self.niche_description,
            market_segments=self.state.niche_context.market_segments,
            industry_boundaries=self.state.niche_context.industry_boundaries,
            niche_anchor_terms=(
                (self.state.niche_context.anchor_entities or [])
                + (self.state.niche_context.audience_jargon or [])
            ),
            target_audience=self._audience_for_research(),
            job_id=self.state.job_id,
            cost_tracker=self.cost_tracker,
        )

        result = pain_point_crew.analyze()
        logger.info(f"[Parallel] PainPointCrew complete: {len(result.pain_points) if result else 0} pain points")

        # Copy the crew's degradation ledger into state (mirrors the coverage_caveats pattern) so
        # fail-open gates / token pressure surface as report quality caveats instead of log-only.
        crew_degradations = getattr(pain_point_crew, "degradation_events", None) or []
        for d in crew_degradations:
            if d not in self.state.pipeline_degradations:
                self.state.pipeline_degradations.append(d)

        # Collect Knowledge objects for cleanup
        knowledge_objects = []
        if getattr(pain_point_crew, '_crew_knowledge', None):
            knowledge_objects.append(pain_point_crew._crew_knowledge)
        if getattr(pain_point_crew, '_enrichment_knowledge', None):
            knowledge_objects.append(pain_point_crew._enrichment_knowledge)

        return {
            "result": result,
            "usage_metrics": pain_point_crew.usage_metrics,
            "knowledge_objects": knowledge_objects,
        }

    def _run_audience_mapping_crew(self, pain_point_analysis=None) -> dict:
        """
        Helper method to run AudienceMappingCrew in parallel execution context.

        Args:
            pain_point_analysis: Optional pain point analysis for segment alignment.
                                 Can be None when running in parallel (alignment done later).

        Returns:
            Dict with 'result' (AudienceMappingResult) and 'usage_metrics'
        """
        from ..crews import AudienceMappingCrew
        from ..models.pain_point import PainPointAnalysisResult

        logger.info("[Parallel] Starting AudienceMappingCrew...")

        _nc = getattr(self.state, "niche_context", None)
        audience_crew = AudienceMappingCrew(
            reddit_posts=self.state.social_content.reddit_posts if self.state.social_content else [],
            twitter_threads=self.state.social_content.twitter_threads if self.state.social_content else [],
            generic_posts=self.state.social_content.generic_posts if self.state.social_content else [],
            niche_description=self.niche_description,
            job_id=self.state.job_id,
            # Part D: Stage-1 resolution as a grounding prior + boundary guard (used only when
            # enable_audience_segment_grounding is on; degrade-safe to [] / "" without niche_context).
            market_segments=getattr(_nc, "market_segments", None),
            industry_boundaries=getattr(_nc, "industry_boundaries", "") or "",
            disambiguation_exclusions=getattr(_nc, "disambiguation_exclusions", None),
            # Codex-review fix: primary segment must respect the user's stated audience
            user_target_audience=getattr(_nc, "user_target_audience", None),
        )

        # Use provided pain_point_analysis or create empty placeholder for parallel execution
        # When running in parallel, pain points aren't available yet - alignment done in post-processing
        if pain_point_analysis is None:
            pain_point_analysis = PainPointAnalysisResult(
                niche=self.niche_description,
                pain_points=[],
                total_mentions=0,
                top_categories=[],
                analysis_summary="Placeholder for parallel execution"
            )

        result = audience_crew.analyze(
            pain_point_analysis=pain_point_analysis,
            niche_description=self.niche_description
        )

        logger.info(f"[Parallel] AudienceMappingCrew complete: {len(result.audience_segments) if result else 0} segments")

        # Collect Knowledge objects for cleanup
        knowledge_objects = []
        if getattr(audience_crew, '_crew_knowledge', None):
            knowledge_objects.append(audience_crew._crew_knowledge)

        return {
            "result": result,
            "usage_metrics": audience_crew.usage_metrics,
            "knowledge_objects": knowledge_objects,
        }

    def stage_3_analyze_pain_points(self):
        """
        Stage 6: Pain Point Analysis + Audience Mapping (Parallel Execution)

        Runs PainPointCrew and AudienceMappingCrew in parallel for ~30-50% time savings.
        Both crews process the same social content independently:
        - PainPointCrew extracts validated pain points
        - AudienceMappingCrew identifies audience segments and influencers

        Post-processing aligns pain points to segments after both complete.
        """
        logger.info("=" * 80)
        logger.info("STAGE 6: Pain Point Analysis + Audience Mapping (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(3, "Pain Point Analysis", "running")

        if not self.state.social_content or (not self.state.social_content.reddit_posts and not self.state.social_content.twitter_threads and not self.state.social_content.generic_posts):
            logger.warning("No social content collected. Skipping pain point analysis.")
            self.state.current_stage = 4
            self.checkpoint_mgr.save_stage("stage_3_pain_points", {"skipped": True, "reason": "No social content collected"})
            return

        # ANTI-HALLUCINATION CHECK: Verify content quality
        generic_posts = self.state.social_content.generic_posts or []
        total_discussions = len(self.state.social_content.reddit_posts) + len(self.state.social_content.twitter_threads) + len(generic_posts)
        total_comments = sum(len(post.comments) for post in self.state.social_content.reddit_posts)
        total_replies = sum(len(thread.replies) for thread in self.state.social_content.twitter_threads)
        total_generic_responses = sum(p.num_responses for p in generic_posts)
        total_engagement = total_comments + total_replies + total_generic_responses

        if total_discussions < 3:
            logger.warning(
                f"Insufficient social content quality ({total_discussions} discussions, minimum 3 required) "
                f"- skipping pain point analysis to prevent hallucination"
            )
            self.state.current_stage = 4
            self.checkpoint_mgr.save_stage("stage_3_pain_points", {"skipped": True, "reason": f"Insufficient content quality: {total_discussions} discussions < 3 minimum"})
            return

        if total_engagement < 5:
            logger.warning(
                f"Low discussion engagement ({total_engagement} comments/replies) "
                f"- pain point quality may be limited"
            )

        logger.info(f"Content quality check: {total_discussions} discussions with {total_engagement} comments/replies")

        # Validate required state fields exist before proceeding
        if not self.state.social_content:
            raise ValueError(
                "Stage 6 requires social_content from Stage 5. "
                "Ensure Stage 5 completed successfully before running Stage 6."
            )
        if not self.state.niche_context:
            raise ValueError(
                "Stage 6 requires niche_context from Stage 1. "
                "Ensure Stage 1 completed successfully before running Stage 6."
            )

        # Run PainPointCrew and AudienceMappingCrew in parallel
        logger.info("[Stage 3] Running PainPointCrew and AudienceMappingCrew in PARALLEL...")
        self._emit_progress(4, "Audience Mapping", "running")  # Emit running so duration can be tracked

        pain_point_result = None
        audience_result = None
        pain_point_usage = None
        audience_usage = None

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both crews for parallel execution
            futures = {
                executor.submit(self._run_pain_point_crew): "pain_points",
                executor.submit(self._run_audience_mapping_crew, None): "audience"  # Pass None - alignment done later
            }

            # Collect results as they complete
            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    result_dict = future.result()
                    if task_name == "pain_points":
                        pain_point_result = result_dict["result"]
                        pain_point_usage = result_dict["usage_metrics"]
                        for k in result_dict.get("knowledge_objects", []):
                            self.register_knowledge(k)
                        logger.info("[Parallel] PainPointCrew finished successfully")
                    else:  # audience
                        audience_result = result_dict["result"]
                        audience_usage = result_dict["usage_metrics"]
                        for k in result_dict.get("knowledge_objects", []):
                            self.register_knowledge(k)
                        logger.info("[Parallel] AudienceMappingCrew finished successfully")
                except Exception as e:
                    logger.error(f"[Parallel] {task_name} crew failed: {e}")
                    if task_name == "pain_points":
                        raise RuntimeError(f"PainPointCrew failed: {e}")
                    # Audience mapping failure is non-fatal - continue without it

        # Store pain point analysis result
        self.state.pain_point_analysis = pain_point_result

        # Record PainPointCrew cost
        if pain_point_usage:
            self.cost_tracker.record_crew_usage(
                stage="Stage 6 - Pain Point Analysis",
                usage_metrics=pain_point_usage,
                model=settings.content_analysis_llm
            )

        # Log pain point results
        logger.info(f"[OK] Identified {len(self.state.pain_point_analysis.pain_points)} pain points")
        logger.info(f"[OK] Total mentions: {self.state.pain_point_analysis.total_mentions}")
        top_cats = [str(c) for c in self.state.pain_point_analysis.top_categories[:3]] if self.state.pain_point_analysis.top_categories else []
        logger.info(f"[OK] Top categories: {', '.join(top_cats)}")

        # Log high-opportunity pain points
        high_opp = [
            pp for pp in self.state.pain_point_analysis.pain_points
            if pp.opportunity_level.value == "high"
        ]
        if high_opp:
            logger.info(f"[OK] High-opportunity pain points: {len(high_opp)}")
            for pp in high_opp[:3]:
                logger.info(f"  - {pp.title} (Severity: {pp.severity_score:.2f}, WTP: {pp.commercial_intent:.2f})")

        # Quality Gate: Validate pain point analysis quality
        quality_tier, confidence_score = self._validate_pain_point_quality(self.state.pain_point_analysis)
        self.state.pain_point_quality_tier = quality_tier
        self.state.pain_point_confidence_score = confidence_score

        # Niche-drift OBSERVABILITY (non-scoring): record what fraction of pain-point
        # evidence actually mentions the niche's anchor vocabulary. Does NOT alter the
        # tier/confidence above — it only feeds a human-readable caveat in the report.
        self._record_pain_anchor_coverage(self.state.pain_point_analysis)

        # Decision: Proceed based on quality tier
        if quality_tier == "INSUFFICIENT":
            logger.warning("Pain point quality insufficient - stopping pipeline (intentional quality gate)")
            logger.warning("Recommendation: Expand social content collection or refine niche focus")
            self.state.errors.append(
                f"Stage 6 quality gate failed: {quality_tier} tier (confidence: {confidence_score:.2f})"
            )
            # Save checkpoint with current state
            self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)

            # Calculate metrics for the stop details
            pain_points = self.state.pain_point_analysis.pain_points if self.state.pain_point_analysis else []
            total_count = len(pain_points)
            quote_density = sum(len(pp.representative_quotes) for pp in pain_points) / total_count if total_count > 0 else 0
            unique_sources = len(set(
                sid for pp in pain_points for sid in pp.source_post_ids if sid
            ))

            raise QualityGateStopException(
                stage=6,
                reason="INSUFFICIENT_DATA",
                details={
                    "qualityTier": quality_tier,
                    "confidenceScore": confidence_score,
                    "metrics": {
                        "painPointCount": total_count,
                        "quoteDensity": round(quote_density, 2),
                        "uniqueSourceCount": unique_sources,
                    },
                    "recommendation": "Expand social content collection or refine niche focus"
                }
            )

        # Quality tier acceptable - proceed with pipeline
        logger.info(f"Quality gate passed - proceeding with {quality_tier} tier data (confidence: {confidence_score:.2f})")

        # Mark Stage 6 complete
        is_fallback = (quality_tier == "BRONZE" and settings.enable_twitter)
        self._mark_stage_complete(3, used_fallback=is_fallback)

        # Checkpoint: Save pain point analysis
        self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)

        # Store audience mapping result (from parallel execution)
        if audience_result:
            self.state.audience_mapping = audience_result

            # Record AudienceMappingCrew cost
            if audience_usage:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 6.5 - Audience Mapping",
                    usage_metrics=audience_usage,
                    model=settings.openai_model_name
                )

            # Post-processing: Map pain points to audience segments
            # This alignment happens AFTER both crews complete
            if self.state.pain_point_analysis and audience_result.audience_segments:
                self._map_pain_points_to_segments(audience_result)
                # Re-save pain points with affected_segments populated
                self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)

            # Roles are relative to the FINAL primary segment, so this deliberately
            # runs only after pain + audience results have converged.
            self._attribute_evidence_speakers(audience_result)

            # Mark Stage 6.5 complete
            self._mark_stage_complete(4)

            # Checkpoint: Save audience mapping
            self.checkpoint_mgr.save_stage("stage_4_audience_mapping", audience_result)

            logger.info("[Stage 4] Audience Mapping Complete (parallel)")
            logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
            logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
            logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
            logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
            logger.info(f"  Recommended Channels: {', '.join(audience_result.recommended_channels[:3])}")
        else:
            logger.warning("[Stage 4] Audience mapping failed (parallel) - continuing without audience data")

        # Update stage - both 3 and 4 are now complete
        self.state.current_stage = 5
        self._emit_progress(4, "Audience Mapping", "completed")

        logger.info("[Stage 3] Parallel execution complete - PainPointCrew + AudienceMappingCrew")

    def stage_4_audience_mapping(self):
        """
        Stage 6.5: Audience & Influence Mapping (Pass-through)

        NOTE: Audience mapping now runs in parallel with Stage 6 for performance.
        This method is a pass-through that verifies results are available.

        If audience mapping failed in parallel execution, this stage can retry sequentially.
        """
        # Check if audience mapping was already completed in parallel
        if self.state.audience_mapping:
            logger.info("[Stage 4] Audience mapping already completed (parallel execution)")
            # Re-run segment mapping if pain points lack affected_segments (checkpoint resume case),
            # OR if provenance is enabled but a legacy checkpoint's fully-populated lexical mapping
            # skipped it entirely, leaving evidence_segments None forever. The mapping is
            # deterministic and idempotent, so re-running it on resume is safe.
            pain_points = self.state.pain_point_analysis.pain_points if self.state.pain_point_analysis else []
            needs_lexical_mapping = any(pp.affected_segments is None for pp in pain_points)
            needs_provenance_mapping = (
                settings.pain_provenance_segments
                and self.state.social_content
                and pain_points
                and all(getattr(pp, "evidence_segments", None) is None for pp in pain_points)
            )
            if (self.state.pain_point_analysis
                    and self.state.audience_mapping.audience_segments
                    and (needs_lexical_mapping or needs_provenance_mapping)):
                self._map_pain_points_to_segments(self.state.audience_mapping)
                self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)
            self._attribute_evidence_speakers(self.state.audience_mapping)
            self.state.current_stage = 5
            return

        # Fallback: Run sequentially if parallel execution failed
        logger.info("=" * 80)
        logger.info("STAGE 6.5: Audience & Influence Mapping (Sequential Fallback)")
        logger.info("=" * 80)
        self._emit_progress(4, "Audience Mapping", "running")

        # Check if we have required data
        if not self.state.social_content:
            logger.warning("[Stage 4] No social content - skipping audience mapping")
            self.state.current_stage = 5
            return

        if not self.state.pain_point_analysis:
            logger.warning("[Stage 4] No pain point analysis - skipping audience mapping")
            self.state.current_stage = 5
            return

        # Run audience mapping crew sequentially (fallback)
        logger.info(f"[Stage 4] Running AudienceMappingCrew sequentially (fallback)...")

        result_dict = self._run_audience_mapping_crew(self.state.pain_point_analysis)
        audience_result = result_dict["result"]
        audience_usage = result_dict["usage_metrics"]

        # Record crew cost
        if audience_usage:
            self.cost_tracker.record_crew_usage(
                stage="Stage 6.5 - Audience Mapping (fallback)",
                usage_metrics=audience_usage,
                model=settings.openai_model_name
            )

        # Check if analysis succeeded
        if not audience_result:
            logger.warning("[Stage 4] Audience mapping failed - continuing without audience data")
            self.state.current_stage = 5
            return

        # Store result
        self.state.audience_mapping = audience_result
        self.state.current_stage = 5

        # Post-processing: Map pain points to audience segments
        if self.state.pain_point_analysis and audience_result.audience_segments:
            self._map_pain_points_to_segments(audience_result)
            # Re-save pain points with affected_segments populated
            self.checkpoint_mgr.save_stage("stage_3_pain_points", self.state.pain_point_analysis)

        self._attribute_evidence_speakers(audience_result)

        # Mark stage complete with tracking
        self._mark_stage_complete(4)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_4_audience_mapping", audience_result)

        logger.info("[Stage 4] Audience Mapping Complete (fallback)")
        logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
        logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
        logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
        logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
        logger.info(f"  Recommended Channels: {', '.join(audience_result.recommended_channels[:3])}")

    def _audience_for_research(self) -> str | None:
        """Part C gate. Returns the user's target audience for SOFT, ADDITIVE research
        bias (queries + pain mining) ONLY when Stage-1 classified a focusable audience
        (segment_of_niche | community).
        Excludes 'niche' (no audience) and 'too_broad' (biasing would broaden, not focus).
        Returns None otherwise → research stays fully broad (default). Never narrows.
        """
        nc = getattr(self.state, "niche_context", None)
        if nc is None:
            return None
        scope = (getattr(nc, "audience_scope", None) or "").strip().lower()
        if scope not in ("segment_of_niche", "community"):
            return None
        audience = (getattr(nc, "user_target_audience", None) or "").strip()
        return audience or None

    def _refine_audience_against_ideas(self) -> None:
        """Post-generation re-resolution of resolved_primary_audience against the ACTUAL
        generated idea source_segments — the namespace the frontend matches cards on.

        The Stage-4 pass (_resolve_primary_audience) matches audience_mapping persona segments,
        but the refiner relabels each idea's source_segment to a buyer-type vocabulary, so the
        two namespaces diverge and the frontend split could never fire. This upgrades the label
        to a real, matchable source_segment when the audience maps to one; otherwise it leaves
        the Stage-4 value untouched (frontend then shows a single 'For {audience}' eyebrow)."""
        nc = getattr(self.state, "niche_context", None)
        if nc is None:
            return
        if (getattr(nc, "audience_scope", None) or "").strip().lower() != "segment_of_niche":
            return
        audience = (getattr(nc, "user_target_audience", None) or "").strip()
        if not audience:
            return
        ig = getattr(self.state, "idea_generation", None)
        ideas = (getattr(ig, "solution_ideas", None) or []) if ig else []
        segs = sorted({(getattr(i, "source_segment", None) or "").strip() for i in ideas} - {""})
        # 1.2(c): resolve the PREFERRED idea segment through the effective primary label —
        # the G2 override when present, else the Stage-4-resolved label — mapped into the
        # idea-segment namespace via _best_segment_match.
        user_scope = getattr(self.state, "user_audience_scope", None)
        g2_primary = ((getattr(user_scope, "primary_target_segment", None) or "").strip()
                      if user_scope else "")
        primary_label = g2_primary or (getattr(nc, "resolved_primary_audience", None) or "").strip()
        preferred = _best_segment_match(primary_label, segs) if primary_label else None
        if g2_primary:
            # The override redirects the label — but ONLY onto a real idea segment.
            # No match: keep the current label (never overwrite with an unmatchable name),
            # log, and surface an idea_coverage_caveat.
            if preferred is None:
                logger.info(f"[Audience] G2 override {g2_primary!r} has no matching idea segment")
                caveat = (f'Your chosen primary segment "{g2_primary}" does not match any '
                          "generated idea's segment label, so idea framing keeps the run's "
                          "resolved audience label.")
                existing = list(getattr(self.state, "idea_coverage_caveats", None) or [])
                if caveat not in existing:
                    existing.append(caveat)
                self.state.idea_coverage_caveats = existing
                return
            matched = preferred
        else:
            matched = _best_segment_match(audience, segs, preferred=preferred)
        if matched and matched != getattr(nc, "resolved_primary_audience", None):
            nc.resolved_primary_audience = matched
            logger.info(
                f"[Audience] refined against idea segments -> resolved_primary_audience={matched!r}")
            try:
                self.checkpoint_mgr.save_stage("stage_1_niche_context", self.state.niche_context)
            except Exception as e:
                logger.warning(f"Re-checkpoint of niche_context (idea refine) skipped: {e}")

    def _tag_audience_fit(self, persist: bool = True) -> None:
        """Part A: tag each generated idea with audience_fit — does it primarily serve the user's
        stated audience? A single FAIL-OPEN structured LLM judgment over the ideas' personas
        (token overlap can't tell that "Bodybuilders & Performance Athletes" serves "gym-goers").
        Post-processing only: never changes which pains/segments were researched, and never
        mutates a stored score. It DOES feed ranking — an idea tagged False takes a
        composite-only penalty (settings.audience_fit_penalty) once pool coverage is >=90%.

        Idempotent over the FULL pool: always re-tags every idea, so it can be re-run after a
        batch/seed appends late-born ideas without leaving stale partials.

        Only runs for segment_of_niche. On any failure it leaves audience_fit=None, so the
        frontend falls back to the source_segment match (_refine_audience_against_ideas). If the
        judgment returns an empty set it is treated as inconclusive (left None) rather than
        marking every idea non-fit.

        ``persist=False`` skips the re-checkpoint — for callers (worker batch/seed paths) that
        own the single authoritative save of the merged pool and whose refund/rollback path
        depends on nothing else writing stage_5_3_refinement first."""
        nc = getattr(self.state, "niche_context", None)
        if nc is None or (getattr(nc, "audience_scope", None) or "").strip().lower() != "segment_of_niche":
            return
        audience = (getattr(nc, "user_target_audience", None) or "").strip()
        ig = getattr(self.state, "idea_generation", None)
        ideas = (getattr(ig, "solution_ideas", None) or []) if ig else []
        if not audience or not ideas:
            return

        # RESET-FIRST (mirrors _stamp_payability): audience_fit is CODE-OWNED but sits on
        # BaseSolutionIdea — the same model generator LLMs emit through structured output, so a
        # fabricated value must never survive. It is now score-bearing, so a stale/invented True
        # would silently buy an idea 0.05 of composite. Reset the whole pool, then stamp.
        for it in ideas:
            try:
                it.audience_fit = None
            except Exception:
                pass

        digest = []
        for it in ideas:
            nm = getattr(it, "solution_name", "") or ""
            seg = getattr(it, "source_segment", "") or ""
            persona = (getattr(it, "target_personas", None) or [""])[0] or ""
            digest.append(f"- {nm} (segment: {seg}; serves: {persona[:160]})")
        prompt = (
            f'The user is building products FOR this target audience: "{audience}".\n\n'
            "For EACH idea below, decide whether it primarily serves THAT audience or a close "
            "sub-group of it — judge by WHO it serves (the persona), not by exact wording. "
            "Return only the solution_name values that fit.\n\nIDEAS:\n" + "\n".join(digest)
        )
        try:
            from ..models.solution_idea import AudienceFitResult
            from ..utils.llm_service import LLMService
            result, _usage = LLMService.invoke_structured(
                prompt=prompt, output_model=AudienceFitResult, temperature=0.0,
                timeout=60, model_name=settings.niche_context_llm,
            )
            fits = {str(n).strip().lower() for n in (result.serves_audience or []) if str(n).strip()}
        except Exception as e:
            logger.warning(f"[Audience] audience_fit tagging failed (fail-open, no tags): {e}")
            return
        if not fits:
            logger.info("[Audience] audience_fit inconclusive (empty) — leaving untagged")
            return
        tagged = 0
        for it in ideas:
            fit = (getattr(it, "solution_name", "") or "").strip().lower() in fits
            try:
                it.audience_fit = bool(fit)
            except Exception:
                pass
            tagged += int(fit)
        logger.info(f"[Audience] audience_fit: {tagged}/{len(ideas)} ideas serve {audience!r}")
        if not persist:
            return
        try:
            self.checkpoint_mgr.save_stage("stage_5_3_refinement", self.state.idea_generation)
        except Exception as e:
            logger.warning(f"Re-checkpoint of idea_generation (audience_fit) skipped: {e}")

    def _resolve_primary_audience(self) -> None:
        """Resolve the audience-framing label (OUTPUT framing only — NEVER mutate
        audience_mapping.primary_target_segment, which feeds generation). Idempotent.

        NOTE: no longer a CrewAI @listen node (an underscore-named listener KeyErrors —
        CrewAI skips `_`-prefixed names in its executable-method registry). It is invoked
        directly from stage_5_unified_solution_pipeline, which runs after every Stage-4 exit.

        - segment_of_niche: set niche_context.resolved_primary_audience to the discovered
          audience_segments.segment_name best-matching user_target_audience (fuzzy >= 0.40);
          fall back to the raw audience string if none clears / no audience_mapping.
        - community / too_broad: leave resolved_primary_audience=None (banner uses
          user_target_audience directly); for too_broad append a breadth caveat to
          idea_coverage_caveats.
        - niche / None: no-op.
        Re-checkpoints niche_context so resolved fields survive resume/regenerate.

        EXCEPTION (2026-07): divergent_stated_audience_floor_count reads resolved_primary_audience
        at allocation to guarantee <=N cells for stated-audience pains — a deliberate, bounded
        (default 1 cell) allocation floor mirroring the severity/commercial floors. It biases WHICH
        already-extracted pains get ideated; it never changes what was researched or extracted.
        """
        nc = getattr(self.state, "niche_context", None)
        if nc is None:
            return
        scope = (getattr(nc, "audience_scope", None) or "").strip().lower()
        audience = (getattr(nc, "user_target_audience", None) or "").strip()
        if not scope or scope == "niche" or not audience:
            return

        if scope == "segment_of_niche":
            am = getattr(self.state, "audience_mapping", None)
            segs = (getattr(am, "audience_segments", None) or []) if am else []
            names = [n for n in (getattr(s, "segment_name", None) for s in segs) if n]
            # Precedence (1.2b): a G2 gate patch's primary_target_segment override wins
            # EXACTLY when it names an existing segment; else fuzzy-match the stated
            # audience with the Stage-4 primary as tie-break preference; raw fallback
            # when nothing clears (the frontend renders a single "For {audience}" eyebrow
            # when nothing matches). This is re-resolved post-generation against the real
            # idea source_segments — see _refine_audience_against_ideas (the namespace
            # the frontend actually matches).
            user_scope = getattr(self.state, "user_audience_scope", None)
            g2_primary = ((getattr(user_scope, "primary_target_segment", None) or "").strip()
                          if user_scope else "")
            if g2_primary and g2_primary in names:
                resolved = g2_primary
            else:
                preferred = getattr(am, "primary_target_segment", None) if am else None
                resolved = _best_segment_match(audience, names, preferred=preferred) or audience
            nc.resolved_primary_audience = resolved
            logger.info(f"[Audience] segment framing -> resolved_primary_audience={resolved!r}")
        else:
            # community / too_broad — no per-segment tagging; the banner uses user_target_audience.
            nc.resolved_primary_audience = None
            if scope == "too_broad":
                caveat = (f'Very broad audience ("{audience}") — research spans many unrelated '
                          f'needs; narrow it (e.g. "{audience} + a specific problem") for sharper '
                          f'opportunities.')
                existing = list(getattr(self.state, "idea_coverage_caveats", None) or [])
                if caveat not in existing:
                    existing.append(caveat)
                self.state.idea_coverage_caveats = existing
            logger.info(f"[Audience] {scope} -> banner for {audience!r} (no segment tagging)")

        try:
            self.checkpoint_mgr.save_stage("stage_1_niche_context", self.state.niche_context)
        except Exception as e:
            logger.warning(f"Re-checkpoint of niche_context skipped: {e}")

    def _build_headless_selection(self, refined_solutions):
        """Auto-select a winner for the headless per-cell-tournament path.

        The tournament returns no SolutionSelection (there is no LLM Task-4 selector), so a
        non-interactive run must pick a winner itself. Ranks the final, calibrated ideas with
        the same helper the skipped-selector path uses (compute_solution_scores → composite,
        rank, score_source='interactive') and takes the top-ranked idea ELIGIBLE for the
        automatic recommendation (`choose_auto_pick` — a red-team-killed idea keeps its rank
        but never gets the automatic pick; the skip is cited in the rationale). Interactive
        runs never reach here (skip_selection=True keeps solution_selection=None so the user
        picks in the UI).
        """
        from nicheiq.utils.score_helpers import choose_auto_pick, compute_solution_scores
        from nicheiq.models.solution_selection import SolutionSelection
        from nicheiq.models.solution_idea import visible_ideas
        ideas = visible_ideas(refined_solutions.solution_ideas) or refined_solutions.solution_ideas
        scores = compute_solution_scores(ideas)
        winner_score, withheld_note = choose_auto_pick(scores, ideas)
        winner_name = winner_score.solution_name
        winner_idea = next((i for i in ideas if i.solution_name == winner_name), ideas[0])
        rationale = (
            f"{winner_name} was auto-selected as the top-ranked eligible concept from the "
            f"per-cell tournament, scoring highest on the blended market-fit, feasibility, "
            f"novelty and SEO composite ({(winner_score.composite_score or 0.0):.2f}) across "
            f"{len(scores)} candidate ideas. Runner-up concepts are retained for comparison "
            f"in all_solution_scores."
        )
        if withheld_note:
            rationale = f"{rationale}\n\n{withheld_note}"
            logger.info(f"[Stage 5] Auto-pick guard: {withheld_note}")
        return SolutionSelection(
            selected_solution_name=winner_name,
            selection_rationale=rationale,
            recommended_focus=self._build_recommended_focus(solution=winner_idea, keyword_validation=None),
            all_solution_scores=scores,
            # Everything but the winner stays a runner-up IN RANK ORDER — a skipped
            # (red-team-killed) leader keeps rank 1 in all_solution_scores and heads the
            # runner-ups; only the automatic pick is withheld from it.
            runner_up_solutions=[s.solution_name for s in scores if s.solution_name != winner_name],
        )

    def _withhold_killed_auto_pick(self) -> None:
        """Re-point an AUTOMATIC selection off a red-team-killed idea (paired with the
        2026-08-02 removal of the red-team parity coupling).

        The Task-4 strategic selector runs BEFORE the red-team pass, so its winner can be
        killed after the fact — and `apply_red_team_downgrade` (the only other consequence
        of a kill) runs at final report assembly, AFTER selection, and explicitly permits a
        killed idea to remain selected. With the parity cap gone, a killed idea's score
        REBOUNDS, so without this guard the fix would make a killed idea an even stronger
        automatic #1.

        No-op unless the current selection is itself killed, so a healthy LLM pick is never
        overridden by the composite leader. USER selections are exempt (`_user_selected_
        solutions` — same guard as the keyword pivot): a human may pick a killed idea, the
        pipeline may not pick one for them. When EVERY candidate is killed the selection
        stands and only the stated non-endorsement is appended (degrade loudly, not
        silently). The dethroned idea keeps its rank and heads the runner-ups.
        """
        from nicheiq.utils.score_helpers import choose_auto_pick, red_team_killed

        sel = self.state.solution_selection
        ideas = (self.state.idea_generation.solution_ideas
                 if self.state.idea_generation else None) or []
        if not sel or not ideas:
            return
        current = sel.selected_solution_name
        if current in (getattr(self.state, "_user_selected_solutions", None) or set()):
            return
        if not red_team_killed(find_solution_by_name(current, ideas)):
            return

        pick, note = choose_auto_pick(sel.all_solution_scores or [], ideas)
        if pick is None or note is None:
            return
        if red_team_killed(find_solution_by_name(pick.solution_name, ideas)):
            # Whole pool killed — keep the selection, state the non-endorsement.
            sel.selection_rationale = f"{sel.selection_rationale or ''}\n\n{note}".strip()
            logger.warning(f"[Stage 5] Auto-pick guard: {note}")
            return

        sel.original_selection_reasoning = sel.selection_rationale
        sel.selection_rationale = f"{sel.selection_rationale or ''}\n\n{note}".strip()
        sel.selected_solution_name = pick.solution_name
        runner_ups = [n for n in (sel.runner_up_solutions or []) if n != pick.solution_name]
        if current and current not in runner_ups:
            runner_ups.insert(0, current)
        sel.runner_up_solutions = runner_ups
        new_winner = find_solution_by_name(pick.solution_name, ideas)
        if new_winner:
            sel.recommended_focus = self._build_recommended_focus(
                solution=new_winner, keyword_validation=None)
        logger.warning(
            f"[Stage 5] Auto-pick guard: '{current}' was red-team killed — automatic "
            f"recommendation moved to '{pick.solution_name}' (killed idea kept in the list)"
        )

    def _inject_validate_seed(self, unified_crew, refined_solutions) -> None:
        """"Check my idea": run the user's idea through the seed pipeline on the WARM crew
        at the end of Stage 5 (plan P4). The seed rides `execute_seed_pipeline` — the real
        birth path with the fidelity identity lock — and is APPENDED to the pool with the
        durable `generation_operation_id='validate'` marker (stamped AFTER the call: the
        pool contract nulls the field internally).

        Snapshot-and-restore contract: `execute_seed_pipeline` resets the crew's per-op
        scratch state at entry (ruled-out ledger, funnel counts, Serper budget, seed-context
        residue) and the Stage-5 telemetry harvest reads those attrs AFTER this method — so
        the full set is snapshotted before the call and restored after, and only the seed's
        own ruled-out entries are merged deliberately. Best-effort: only the systemic-LLM
        breaker propagates; any other failure degrades to a report-visible note.
        """
        from ..crews.unified_solution_crew import SeedRequest
        from ..utils.llm_service import LLMSystemicError

        seed_text = (getattr(self.state, "user_idea_brief", None) or "").strip()
        if not seed_text:
            # Brief extraction failed at Stage 1 — fall back to the head of the raw pitch
            # (the fidelity lock is weaker against long text; better than no evaluation).
            seed_text = (getattr(self.state, "user_idea_text", None) or "").strip()[:300]
        if not seed_text:
            logger.error("[Idea Check] no idea text on state — skipping seed injection")
            return

        _SNAP_ATTRS = (
            "_tournament_ctx", "ruled_out_pains", "overlap_groups", "funnel_counts",
            "_ma_serper_calls", "_ma_search_lock", "_birth_verified_names",
            "_route_label_counts", "coverage_caveats",
            "_current_seed_text", "_current_seed_dispatch_id", "_current_seed_evaluation",
        )
        snapshot = {a: getattr(unified_crew, a, None) for a in _SNAP_ATTRS}
        seed = None
        pivot = None
        seed_ruled_out: list = []
        seed_serper_calls = 0
        seed_brief_probe_calls = 0
        try:
            # Stage number 5 EXACTLY — unregistered numbers are silently rejected by the
            # backend validator. This emit is also the last cancel checkpoint before
            # minutes of uninterruptible seed-tail work.
            self._emit_progress(5, "Solution Pipeline", "running")
            seed = unified_crew.execute_seed_pipeline(
                SeedRequest(
                    seed_text=seed_text, dispatch_id="validate",
                    # Stated-clause preservation: the evaluated project must stay the
                    # pitched product (delivery form, buyer, core mechanism).
                    identity_terms=getattr(
                        self.state, "user_idea_identity_terms", None),
                    inferred_fields=list(getattr(
                        self.state, "user_idea_inferred_fields", None) or []),
                ))
            seed_ruled_out = list(getattr(unified_crew, "ruled_out_pains", None) or [])
            seed_serper_calls = getattr(unified_crew, "_ma_serper_calls", 0) or 0
            if seed is not None:
                parity = (getattr(seed, "incumbent_parity", None) or "").strip().lower()
                if parity.startswith(("shipped", "partial")):
                    pivot = self._attempt_validate_pivot(unified_crew, seed)
                else:
                    self.state.user_idea_pivot = {
                        "attempted": False, "outcome": "not_attempted",
                        "trigger_finding": None, "because": None, "keeps": None,
                        "changes": None, "reason_not_shown": None, "ries_label": None,
                        "name": None,
                    }
                if parity.startswith("none"):
                    # Q1: the in-wave probe searched the EVALUATED mechanism's vocabulary
                    # and found nothing — probe the PITCHED mechanism too (display-only;
                    # never feeds outcome/confidence/pivot). Count logged below; the
                    # queries run inside the snapshot window like the seed's own spend.
                    _terms = getattr(self.state, "user_idea_identity_terms", None) or {}
                    note, seed_brief_probe_calls = unified_crew._probe_seed_brief_parity(
                        seed, _terms.get("mechanism") or [])
                    if note is not None:
                        self.state.user_idea_brief_parity = note
        except LLMSystemicError:
            raise
        except Exception as e:  # noqa: BLE001 — degrade, never kill a paid Phase 1
            logger.error(f"[Idea Check] seed injection failed (non-fatal): {e}")
        finally:
            # Restore the pool's scratch state so the harvest below reads pool values.
            # `_ma_serper_calls` is restored too — the seed gets no fresh Serper budget;
            # its own spend is logged below. `_tournament_ctx` is then nulled: the seed
            # path re-sets it to a one-cell context and never clears it.
            for attr, value in snapshot.items():
                setattr(unified_crew, attr, value)
            unified_crew._tournament_ctx = None

        if seed is None:
            self.state.pipeline_degradations = list(
                getattr(self.state, "pipeline_degradations", None) or []
            ) + ["Idea check: your idea could not be evaluated in this market "
                 "(the seed pipeline returned no result)."]
            logger.error("[Idea Check] seed pipeline produced no idea — degraded")
            return

        seed.generation_operation_id = "validate"
        refined_solutions.solution_ideas.append(seed)
        self._stamp_validate_duplicate(seed, refined_solutions)
        if seed_ruled_out:
            self.state.idea_ruled_out = list(
                getattr(self.state, "idea_ruled_out", None) or []) + seed_ruled_out
        if pivot is not None:
            pivot.generation_operation_id = "validate_pivot"
            refined_solutions.solution_ideas.append(pivot)
        logger.info(
            f"[Idea Check] seed '{getattr(seed, 'solution_name', '?')}' injected "
            f"(status={getattr(seed, 'candidate_status', '?')}, "
            f"pivot={'accepted' if pivot is not None else 'no'}, "
            f"seed_serper_calls={seed_serper_calls}, "
            f"seed_brief_probe_calls={seed_brief_probe_calls})")

        # Telemetry only (quality pass Q4): the report block recomputes this from
        # persisted state — a value stashed here would not survive re-materialize.
        try:
            from ..utils.seed_fidelity import seed_clause_drift
            drifted = seed_clause_drift(
                getattr(self.state, "user_idea_identity_terms", None), seed,
                getattr(self.state, "user_idea_inferred_fields", None))
            if drifted:
                logger.warning(
                    "[Idea Check] evaluated seed drifted from the pitch on: "
                    + ", ".join(drifted))
        except Exception as exc:  # never let telemetry break injection
            logger.warning(f"[Idea Check] clause-drift telemetry failed: {exc}")

    def _attempt_validate_pivot(self, unified_crew, seed):
        """Single accept-guarded wedge-pivot revision of the user's idea (plan P4.19).
        APPEND semantics — the seed is never replaced. The attempt is recorded on
        `state.user_idea_pivot` REGARDLESS of outcome (the report's pivot-absent state is
        mandatory copy: rejection is the expected common case — `_pivot_acceptable`
        requires the revision's own parity to clear to 'none')."""
        finding = (getattr(seed, "incumbent_parity", "") or "").strip()
        # Shared stamp parser (2026-08): the old token loop returned the CLASS word
        # ("substitute") for paren-format stamps — trigger_incumbent then named no product.
        from ..validators.report_consistency import parse_stamp_vendor
        parsed = parse_stamp_vendor(finding)
        inc_name = parsed[1] if parsed else ""
        gaps_by_name: dict[str, str] = {}
        for row in (getattr(unified_crew, "_incumbent_rows", None) or []):
            name = (row.get("name") or "").strip().lower()
            if name:
                gaps_by_name[name] = (row.get("gap") or "").strip()
        gap = gaps_by_name.get(inc_name.lower(), "")

        record = {
            "attempted": True, "outcome": "rejected",
            "trigger_finding": finding, "because": gap or None,
            # The report labels the trigger with this name ("TeamSnap already ships part
            # of this") instead of echoing the raw parity note a second time.
            "trigger_incumbent": inc_name or None,
            "keeps": None, "changes": None, "reason_not_shown": None,
            "ries_label": None, "name": None,
        }
        try:
            rev = unified_crew._generate_pivot_revision(seed, gaps_by_name)
            if rev is None:
                record["rejection_code"] = "no_design"
                record["reason_not_shown"] = (
                    "We drafted one revision of your idea against this gap, but it did "
                    "not produce a usable design, so we're not proposing it.")
                return None
            unified_crew._score_wave([rev])
            if not unified_crew._pivot_acceptable(seed, rev):
                # Re-derive WHY with the guard's own checks, in its order — the single
                # "scored no better" sentence lied when the revision scored BETTER but
                # its parity did not clear to 'none'.
                from ..utils.score_helpers import _composite_for_angle

                def _comp(i):
                    return _composite_for_angle(
                        getattr(i, "market_fit_score", None),
                        getattr(i, "technical_feasibility_score", None),
                        getattr(i, "novelty_score", None),
                        getattr(i, "seo_scalability_score", None),
                        getattr(i, "winning_angle", None))

                score_dims = [getattr(rev, k, None) for k in
                              ("market_fit_score", "technical_feasibility_score",
                               "novelty_score", "seo_scalability_score")]
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                           for v in score_dims):
                    record["rejection_code"] = "incomplete_scores"
                    record["reason_not_shown"] = (
                        "We drafted one revision of your idea against this gap. It "
                        "scored no better than your original, so we're not proposing it.")
                    return None
                rev_comp, orig_comp = _comp(rev), _comp(seed)
                rev_par = (getattr(rev, "incumbent_parity", None) or "").strip().lower()
                if rev_comp > orig_comp and not rev_par.startswith("none"):
                    record["rejection_code"] = "parity_not_cleared"
                    record["reason_not_shown"] = (
                        "It scored better, but a named product already ships the "
                        "revised mechanism too, so we're not proposing it.")
                else:
                    record["rejection_code"] = "not_better"
                    record["reason_not_shown"] = (
                        "It scored no better than your original, so we're not "
                        "proposing it.")
                # The acceptance decision's OWN numbers (the same angle composite
                # _pivot_acceptable compared) — deliberately NOT the workbench's
                # displayCompositeScore; do not repoint these at the UI score.
                record["rejected_name"] = getattr(rev, "solution_name", None)
                record["rejected_pitch"] = (
                    (getattr(rev, "value_proposition", None) or "")[:160]) or None
                record["rejected_composite"] = round(rev_comp * 100)
                record["original_composite"] = round(orig_comp * 100)
                return None
            record["outcome"] = "accepted"
            record["name"] = getattr(rev, "solution_name", None)
            seed_personas = list(getattr(seed, "target_personas", None) or [])
            rev_personas = list(getattr(rev, "target_personas", None) or [])
            # "; " — the items are whole phrases; comma-joining them produced one
            # six-comma run-on with no item boundaries.
            record["keeps"] = "; ".join(
                seed_personas[:2]
                + list(getattr(seed, "pain_points_addressed", None) or [])[:1]) or None
            record["changes"] = ((getattr(rev, "innovation_angle", None)
                                  or getattr(rev, "value_proposition", "") or "")[:200]) or None
            if seed_personas and rev_personas and seed_personas[0] != rev_personas[0]:
                record["ries_label"] = "customer-segment"
            elif record["changes"]:
                record["ries_label"] = "zoom-in"
            return rev
        finally:
            self.state.user_idea_pivot = record

    def _stamp_validate_duplicate(self, seed, refined_solutions) -> None:
        """duplicate_of seed<->pool: a generated idea structurally matching the user's idea
        is a DEMAND signal ("our own generator independently arrived at your idea"), never a
        drop — both ideas are kept. Matcher failures are error-logged (this feeds a verdict
        signal; the regenerate path's silent `except: pass` is deliberately not copied)."""
        try:
            from ..utils.validation.crew_guardrails import detect_catalog_duplicate
            for other in refined_solutions.solution_ideas:
                if other is seed:
                    continue
                existing = {
                    "name": getattr(other, "solution_name", "") or "",
                    "description": getattr(other, "description", "") or "",
                    "value_proposition": getattr(other, "value_proposition", "") or "",
                    "target_personas": list(getattr(other, "target_personas", None) or []),
                }
                if existing["name"] and detect_catalog_duplicate(seed, existing):
                    seed.duplicate_of = existing["name"]
                    logger.info(
                        f"[Idea Check] pool idea '{existing['name']}' independently matches "
                        "the user's idea — recorded as a demand signal (both kept)")
                    return
        except Exception as e:  # noqa: BLE001
            logger.error(f"[Idea Check] duplicate matcher failed (verdict signal lost): {e}")

    def stage_5_unified_solution_pipeline(self, skip_selection: bool = False):
        """
        Stage 7: Unified Solution Pipeline (CrewAI Best Practice)

        4-task divergent-convergent pipeline:
        - Task 7.1: Divergent Exploration (generate 8-12 raw concepts)
        - Task 7.2: Diversity Filtering (filter to 5-7 unique)
        - Task 7.3: Solution Refinement (expand to full specs)
        - Task 7.4: Solution Selection (strategic scoring and selection)
          Skipped when skip_selection=True (interactive mode).

        Competitive analysis is run on-demand per-solution in Stage 7.5.
        """
        logger.info("=" * 80)
        logger.info("STAGE 5: Unified Solution Pipeline")
        logger.info("=" * 80)
        self._emit_progress(5, "Solution Pipeline", "running")

        # Resolve the audience-framing label here (idempotent) — Stage 5 runs after EVERY
        # Stage-4 exit path (success + all early returns), so this single call covers them all,
        # including the audience_mapping-is-None fallback. OUTPUT framing only.
        try:
            self._resolve_primary_audience()
        except Exception as e:
            logger.warning(f"Primary-audience resolution skipped: {e}")

        # Prerequisites check
        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            error_msg = "No pain points available - cannot proceed with solution pipeline"
            logger.error(error_msg)
            self.checkpoint_mgr.save_stage("stage_5_skipped", {"skipped": True, "reason": "No pain points available"})
            raise RuntimeError(f"Stage 7 failed: {error_msg}")

        # ANTI-HALLUCINATION CHECK: Verify pain point quality
        high_priority = [
            pp for pp in self.state.pain_point_analysis.pain_points
            if pp.opportunity_level.value == "high"
        ]
        medium_priority = [
            pp for pp in self.state.pain_point_analysis.pain_points
            if pp.opportunity_level.value == "medium"
        ]

        if not high_priority and not medium_priority:
            error_msg = "No high or medium priority pain points available - cannot proceed with solution pipeline"
            logger.error(error_msg)
            self.checkpoint_mgr.save_stage("stage_5_skipped", {"skipped": True, "reason": "No high/medium priority pain points"})
            raise RuntimeError(f"Stage 7 failed: {error_msg}")

        logger.info(
            f"Pain point quality check: {len(high_priority)} high-priority, "
            f"{len(medium_priority)} medium-priority pain points"
        )

        # Compute competitor mentions once and cache for regeneration
        if not self.state.competitor_mentions_formatted and self.state.social_content:
            from nicheiq.utils.crew_helpers.content_preparers import format_competitor_mentions_for_prompt
            known_tools = (
                self.state.audience_mapping.tools_currently_used
                if self.state.audience_mapping and self.state.audience_mapping.tools_currently_used
                else None
            )
            self.state.competitor_mentions_formatted = format_competitor_mentions_for_prompt(
                self.state.social_content, known_tools=known_tools
            )
            self.checkpoint_mgr.save_stage(
                "stage_5_competitor_mentions",
                {"text": self.state.competitor_mentions_formatted}
            )
            logger.info(f"Cached competitor mentions ({len(self.state.competitor_mentions_formatted)} chars)")

        try:
            # Initialize UnifiedSolutionCrew with audience intelligence from Stage 6.5
            unified_crew = UnifiedSolutionCrew(
                pain_point_analysis=self.state.pain_point_analysis,
                social_content=self.state.social_content,
                allowed_project_types=self.allowed_project_types,
                niche_context=self.state.niche_context,
                audience_mapping=self.state.audience_mapping,
                checkpoint_mgr=self.checkpoint_mgr,
                job_id=self.state.job_id,
                competitor_mentions_text=self.state.competitor_mentions_formatted,
                idea_focus=getattr(self, "idea_focus", "auto"),
                cost_tracker=self.cost_tracker,
                user_pain_scope=getattr(self.state, "user_pain_scope", None),
                user_audience_scope=getattr(self.state, "user_audience_scope", None),
            )

            # Execute complete pipeline
            logger.info("Executing unified solution pipeline...")
            (
                refined_solutions,
                solution_selection,
            ) = unified_crew.execute_pipeline(skip_selection=skip_selection)

            # Record crew cost
            if unified_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 7 - Unified Solution Pipeline",
                    usage_metrics=unified_crew.usage_metrics,
                    model=settings.brainstorm_llm
                )

            # Save results to state
            self.state.idea_generation = refined_solutions
            self.state.solution_selection = solution_selection

            # "Check my idea": inject the user's idea through the seed pipeline on the
            # warm crew (plan P4) — before headless selection and the audience re-tag so
            # the seed participates in both.
            if (self.entry_mode or "").strip().lower() == "validate_idea" and refined_solutions:
                self._inject_validate_seed(unified_crew, refined_solutions)

            # Headless per-cell-tournament auto-select: the tournament path returns
            # solution_selection=None (no LLM Task-4 selector). For a NON-interactive run,
            # pick the top-ranked calibrated idea so Stage 6+ can proceed. Interactive runs
            # (skip_selection=True) intentionally keep None — the user selects in the UI.
            if (solution_selection is None and not skip_selection
                    and refined_solutions and refined_solutions.solution_ideas):
                solution_selection = self._build_headless_selection(refined_solutions)
                self.state.solution_selection = solution_selection
                logger.info(
                    f"[Stage 5] Headless tournament auto-select: "
                    f"{solution_selection.selected_solution_name}"
                )
            # Re-resolve the audience label against the real generated idea segments so the
            # frontend grid can actually split (the Stage-4 guess used a different namespace),
            # then tag each idea's audience_fit (semantic primary/adjacent signal).
            self._refine_audience_against_ideas()
            self._tag_audience_fit()

            # "Check my idea" durable save (plan P4.17): without it the seeded idea never
            # reaches the checkpoint Phase 2 resolves selections from — execute_pipeline's
            # own save precedes the injection, _tag_audience_fit's save is multi-gated, and
            # the worker-tail identity save is conditional on missing identities.
            if (self.entry_mode or "").strip().lower() == "validate_idea":
                try:
                    self.checkpoint_mgr.save_stage(
                        "stage_5_3_refinement", self.state.idea_generation)
                except Exception as _e:  # noqa: BLE001
                    logger.warning(f"[Idea Check] stage_5_3 durable save failed: {_e}")

            # Research Reality Check: candid software-fit verdict, computed once here over
            # all pains + all generated ideas. Read later by both the preview materializer
            # and the full report. Best-effort — never blocks the pipeline.
            try:
                from ..utils.niche_difficulty import (
                    assess_niche_difficulty,
                    generate_niche_difficulty_verdict,
                )
                _pains = (
                    self.state.pain_point_analysis.pain_points
                    if self.state.pain_point_analysis
                    else []
                )
                _ideas = refined_solutions.solution_ideas if refined_solutions else []
                _nctx = self.state.niche_context
                _niche = getattr(_nctx, "niche_description", None) or self.niche_description
                _dup_rate = getattr(unified_crew, "_concept_already_exists_share", None)
                _segments = getattr(self.state.audience_mapping, "audience_segments", None)
                _wallet_brief = getattr(unified_crew, "_niche_wallet_brief", None) or None
                # Market-awareness inputs (2026-07-10): web-verified incumbent map (tooling
                # density) + SERP-owned share among distribution-angle ideas. None when the
                # probes didn't run — assess_niche_difficulty is byte-identical-legacy then.
                _inc_map = list(getattr(unified_crew, "_incumbent_rows", None) or []) or None
                _dist = [i for i in (_ideas or [])
                         if getattr(i, "winning_angle", None) == "distribution_seo"]
                _serp_share = (sum(1 for i in _dist if getattr(i, "_serp_owned", False))
                               / len(_dist) if _dist else None)
                _recommended = self._current_recommended_candidates()
                # The verdict card and this stage must not narrate the buyer with two different
                # comparators, so `assess_niche_difficulty` reads the same typed axes for the
                # message it appends to key_challenges. The recommendation is handed over
                # unconditionally: whether there is anything to say is the comparator's call,
                # not this caller's.
                from ..utils.audience_axes import detect_audience_drift
                _typed_drift = detect_audience_drift(
                    getattr(_nctx, "user_target_audience", None),
                    getattr(self.state.audience_mapping, "primary_target_segment", None),
                    _recommended,
                )
                _fact_pack = assess_niche_difficulty(
                    _pains, _ideas, _nctx, concept_duplication_rate=_dup_rate,
                    segments=_segments, niche_wallet_brief=_wallet_brief,
                    incumbent_map=_inc_map, serp_owned_share=_serp_share,
                    dossier_primary_segment=getattr(
                        self.state.audience_mapping, "primary_target_segment", None
                    ),
                    recommended_candidates=_recommended)
                if _fact_pack is not None:
                    _verdict, _usage = generate_niche_difficulty_verdict(
                        _fact_pack, _niche, _nctx
                    )
                    _verdict = _verdict.model_copy(update={
                        "audience_drift_notice": _typed_drift,
                    })
                    self.state.niche_difficulty_verdict = _verdict
                    # Stamp the same notice onto audience_mapping and persist both, so the
                    # verdict and the audience card cannot disagree about the buyer even if
                    # the run never reaches preview materialization.
                    self._refresh_recommendation_audience_drift(persist=True)
                    # Persist so the verdict survives resume (read by the report + preview);
                    # restored via stage_mapping. save_stage also flushes checkpoint metadata.
                    try:
                        self.checkpoint_mgr.save_stage("stage_5_niche_difficulty", _verdict)
                    except Exception as _e:  # noqa: BLE001
                        logger.warning(f"[Niche Difficulty] checkpoint skipped: {_e}")
                    if _usage is not None:
                        self.cost_tracker.record_llm_usage(
                            "Stage 5 - Niche Difficulty", _usage.to_dict()
                        )
                    logger.info(
                        f"[Niche Difficulty] {_verdict.difficulty_level} "
                        f"(addressability {_verdict.software_addressability:.0%})"
                    )
            except Exception as e:  # noqa: BLE001 — non-critical enrichment
                logger.warning(f"[Niche Difficulty] verdict step failed: {e}")

            # Segment payability was written back onto audience_mapping's segments DURING the
            # pipeline, but the stage_4 checkpoint was saved before that — re-save so
            # segment-level payability survives resume (idea-level stamps persist via stage_5_3).
            if self.state.audience_mapping is not None:
                _segs = getattr(self.state.audience_mapping, "audience_segments", None) or []
                if any(getattr(s, "payability_score", None) is not None for s in _segs):
                    try:
                        self.checkpoint_mgr.save_stage(
                            "stage_4_audience_mapping", self.state.audience_mapping)
                    except Exception as _e:  # noqa: BLE001
                        logger.warning(f"[Payability] stage_4 re-save skipped: {_e}")

            # Surface any uncovered high-severity pains (post-crew coverage check).
            # MERGE (don't overwrite) — preserve any earlier caveat (e.g. the Stage-4 breadth
            # caveat for a too_broad audience) added before this stage.
            _crew_caveats = list(getattr(unified_crew, "coverage_caveats", None) or [])
            _existing_caveats = list(getattr(self.state, "idea_coverage_caveats", None) or [])
            self.state.idea_coverage_caveats = _existing_caveats + [
                c for c in _crew_caveats if c not in _existing_caveats
            ]
            self.state.idea_ruled_out = (
                list(getattr(self.state, "idea_ruled_out", None) or [])
                + list(getattr(unified_crew, "ruled_out_pains", None) or [])
            )
            if getattr(unified_crew, "funnel_counts", None):
                self.state.idea_funnel_counts = dict(unified_crew.funnel_counts)
            if getattr(unified_crew, "cell_allocation_telemetry", None):
                self.state.idea_cell_allocation = dict(unified_crew.cell_allocation_telemetry)
            if getattr(unified_crew, "overlap_groups", None):
                self.state.idea_overlap_groups = list(unified_crew.overlap_groups)
            # Thesis-level portfolio partition (docs/DIVERSITY_DECISION_2026-08.md): group the
            # VISIBLE pool by the run's buyer-job family so the UI can show one card per product
            # thesis with its variants nested, plus the validated families no concept covers.
            # Deterministic rollup of signals already on the ideas — no LLM call, no new probe.
            try:
                from ..utils.idea_theses import build_idea_theses

                _partition = getattr(unified_crew, "_buyer_job_partition", None)
                # Persist the partition itself, not just the theses derived from it: later
                # regenerate/seed batches REUSE it (see _ensure_buyer_job_partition) so their
                # ideas carry the same family ids instead of a fresh, incompatible labeling.
                # Degraded (theme-fallback) partitions are not stored — a later batch should get
                # a real labeler attempt rather than inherit the degradation.
                if _partition is not None and not _partition.degraded:
                    self.state.buyer_job_partition = _partition.to_telemetry()
                _theses = build_idea_theses(
                    refined_solutions.solution_ideas if refined_solutions else [],
                    partition=_partition,
                    cell_allocation=self.state.idea_cell_allocation,
                )
                if _theses:
                    self.state.idea_theses = _theses
            except Exception as e:  # noqa: BLE001 — presentation must never block the pipeline
                logger.warning(f"[IdeaTheses] step skipped: {e}")
            # Market-data handoff: the Phase-1 incumbent/wallet probes are web-verified facts —
            # shown to the user once (preview/report market_reality) and handed to Phase-2 once
            # (utils/market_brief.py), never re-discovered independently per crew.
            self.state.niche_incumbent_map = (
                list(getattr(self.state, "niche_incumbent_map", None) or [])
                + list(getattr(unified_crew, "_incumbent_rows", None) or [])
            )
            if getattr(unified_crew, "_niche_wallet_brief", None):
                self.state.niche_wallet_brief = dict(unified_crew._niche_wallet_brief)
            # Same handoff for the two remaining instance-only Phase-1 caches (eager-meandering-
            # feather.md Phase 4, section C) — without this a later user-seed pipeline would
            # cold-re-probe (LLM calls) work this run already paid for. `is not None` (not
            # truthy) because '' is a real "probed, found nothing" result, not "never probed".
            if getattr(unified_crew, "_data_menu_text", None) is not None:
                self.state.niche_data_menu_text = unified_crew._data_menu_text
            if getattr(unified_crew, "_dissatisfaction_text", None) is not None:
                self.state.niche_dissatisfaction_text = unified_crew._dissatisfaction_text

            # Initial portfolio summary. The helper derives the exact deterministic Phase-1
            # identities the worker will stamp before publishing, so preview materialization
            # sees the same fingerprint and does not pay for a duplicate LLM call.
            self._refresh_idea_portfolio_summary(reason="initial Stage 5", force=True)

            # Flush now: the crew's own stage_5_3 re-save ran BEFORE this merge, and a Phase-1
            # stop has no later save_stage — without this the ruled-out ledger / funnel counts /
            # overlap groups never reach metadata.json and are lost on Phase-2 resume
            # (live-caught on the 2026-07-09 cottage-food smoke run).
            if self.checkpoint_mgr:
                try:
                    self.checkpoint_mgr.flush_metadata()
                except Exception as _e:  # noqa: BLE001 — checkpointing must never break the pipeline
                    logger.debug(f"[Stage 5] metadata flush skipped: {_e}")

            if solution_selection is not None:
                # DEFENSIVE: Validate solution selection - detect error strings
                # The LLM may return "Insufficient evidence for strategic selection" if context chain fails
                INVALID_SELECTION_PATTERNS = [
                    "insufficient evidence",
                    "unable to select",
                    "cannot determine",
                    "no clear winner",
                ]
                selected_name = self.state.solution_selection.selected_solution_name or ""

                if any(pattern in selected_name.lower() for pattern in INVALID_SELECTION_PATTERNS):
                    logger.warning(
                        f"⚠️ Solution selection returned error string: '{selected_name}'. "
                        f"Triggering fallback selection..."
                    )

                    # Fallback: Select highest market_fit_score from idea_generation
                    if self.state.idea_generation and self.state.idea_generation.solution_ideas:
                        sorted_ideas = sorted(
                            self.state.idea_generation.solution_ideas,
                            key=lambda s: getattr(s, 'market_fit_score', 0) or 0,
                            reverse=True
                        )
                        fallback_solution = sorted_ideas[0]
                        fallback_name = fallback_solution.solution_name
                        fallback_score = getattr(fallback_solution, 'market_fit_score', 'N/A')

                        logger.warning(
                            f"✓ Fallback selected: '{fallback_name}' "
                            f"(market_fit_score: {fallback_score})"
                        )

                        # Update selection state
                        self.state.solution_selection.selected_solution_name = fallback_name
                        original_rationale = self.state.solution_selection.selection_rationale or ""
                        self.state.solution_selection.selection_rationale = (
                            f"[AUTO-FALLBACK] LLM selection failed with '{selected_name}'. "
                            f"Auto-selected highest market_fit_score ({fallback_score}). "
                            f"Original response: {original_rationale[:200]}..."
                        )

                        # Update recommended_focus for fallback solution
                        self.state.solution_selection.recommended_focus = (
                            self._build_recommended_focus(
                                solution=fallback_solution,
                                keyword_validation=None,
                            )
                        )

                        # Re-save checkpoint with fallback mutations
                        self.checkpoint_mgr.save_stage(
                            "stage_5_6_selection",
                            self.state.solution_selection.model_dump(),
                        )

                        # Track fallback for visibility
                        if not hasattr(self.state, 'fallback_stages'):
                            self.state.fallback_stages = []
                        self.state.fallback_stages.append(7.4)
                    else:
                        logger.error(
                            "⚠️ Fallback failed - no solutions available in idea_generation. "
                            "Pipeline will proceed with invalid selection name."
                        )

                # Backfill all_solution_scores for solutions the LLM didn't score
                # Uses utility to ensure consistent field mapping
                if (self.state.idea_generation
                        and self.state.idea_generation.solution_ideas):
                    from nicheiq.utils.score_helpers import backfill_solution_scores
                    # Provenance: scores already present at this point came from
                    # the Task 4 strategic selector (backfilled ones get tagged
                    # 'backfill' inside the helper)
                    for _score in (self.state.solution_selection.all_solution_scores or []):
                        if _score.score_source is None:
                            _score.score_source = 'llm'
                    self.state.solution_selection.all_solution_scores = backfill_solution_scores(
                        self.state.solution_selection.all_solution_scores,
                        self.state.idea_generation.solution_ideas,
                    )
                    # De-invert the ranking: the Task-4 selector LLM's composite never saw the
                    # critic's build_feasibility, so a low-buildability idea can rank too high.
                    # Apply the downgrade-only feasibility adjustment to the LLM-scored entries.
                    from nicheiq.utils.score_helpers import apply_feasibility_to_scores
                    self.state.solution_selection.all_solution_scores = apply_feasibility_to_scores(
                        self.state.solution_selection.all_solution_scores,
                        self.state.idea_generation.solution_ideas,
                    )

                # Auto-pick guard: the Task-4 selector ran BEFORE the red-team pass, so its
                # winner may have been killed since. Runs on the FINAL ranking (post-backfill,
                # post-feasibility) so the replacement is the real top eligible idea. No-op
                # for a surviving winner and for user selections. Fail-soft.
                try:
                    self._withhold_killed_auto_pick()
                except Exception as e:
                    logger.warning(f"[Stage 5] Auto-pick guard skipped: {e}")

                # Persist the selection reflecting backfill/feasibility/auto-pick guard — and
                # the headless tournament build, which UnifiedSolutionCrew did not checkpoint
                # (it returned None). save_stage also flushes checkpoint metadata.
                self.checkpoint_mgr.save_stage(
                    "stage_5_6_selection",
                    self.state.solution_selection.model_dump(),
                )

            # Log results
            logger.info("[OK] Solution Pipeline Complete:")
            logger.info(f"  - Generated {len(refined_solutions.solution_ideas)} solutions")
            if solution_selection:
                logger.info(f"  - Selected: {solution_selection.selected_solution_name}")
            else:
                logger.info("  - Selection: skipped (interactive mode)")

            # Update stage (continue to keyword validation)
            self.state.current_stage = 5.7

            # Mark stage complete with tracking
            self._mark_stage_complete(5)

            # Checkpoints saved internally by UnifiedSolutionCrew.execute_pipeline()
            # All 4 task outputs checkpointed: stage_7_1 through stage_7_3, stage_7_6
            logger.debug("Stage 7 checkpoints saved by UnifiedSolutionCrew")

        except Exception as e:
            logger.error(f"Unified solution pipeline failed: {e}")
            raise

    def _iterative_keyword_enrichment(
        self,
        conceptual_keywords: list,
        validated_seeds: list,
        topic_clusters: list,
        selected_solution = None,
        niche_context = None,
        initial_keywords: list | None = None,
    ) -> list:
        """
        Phase 6c: Iteratively enrich keywords with DataForSEO using VALIDATED seeds.

        Uses VALIDATED seeds (pre-filtered by get_search_volume in Phase 6b) instead of
        raw conceptual keywords to maximize success rate and reduce API waste.

        NEW: Adds LLM-based relevance validation after expansion to filter out irrelevant
        keywords (e.g., "find my device", "discover card", "dental labs").

        Args:
            conceptual_keywords: Full list of ConceptualKeyword objects for cluster coverage calculation
            validated_seeds: Pre-validated keywords with search volume (from Phase 6b bulk validation)
            topic_clusters: List of ConceptualTopicCluster objects from Phase 6a
            selected_solution: Selected SolutionIdea for relevance validation (optional)
            niche_context: NicheContext for relevance validation (optional)
            initial_keywords: Pre-loaded keywords from anchor enrichment (optional)

        Returns:
            List of enriched keywords with search volumes and competition data
        """
        # Build validated keyword lookup for filtering conceptual keywords
        validated_keyword_set = {kw['keyword'].lower() for kw in validated_seeds}

        # Filter conceptual keywords to only validated ones
        validated_conceptual = [
            kw for kw in conceptual_keywords
            if kw.keyword.lower() in validated_keyword_set
        ]

        logger.info(
            f"Starting enrichment with {len(validated_conceptual)}/{len(conceptual_keywords)} "
            f"validated conceptual seeds across {len(topic_clusters)} clusters"
        )

        # Initialize keyword relevance validator
        validator = KeywordRelevanceValidator()
        logger.info("[Validation] Initialized KeywordRelevanceValidator for relevance filtering")

        # Prepare validation context (fallback to safe defaults if not provided)
        niche_description = niche_context.niche_description if niche_context else self.niche_description
        solution_name = selected_solution.solution_name if selected_solution else "Unknown Solution"
        solution_description = selected_solution.value_proposition if selected_solution else "Unknown Description"
        project_type = selected_solution.project_type if selected_solution else "saas"

        # Initialize with pre-validated keywords (+ anchor-enriched if provided)
        all_enriched = (initial_keywords or []) + validated_seeds.copy()
        seeds_used = set()
        # Track enriched keyword strings for deduplication across rounds
        enriched_keyword_strings = {kw['keyword'].lower() for kw in all_enriched}
        max_rounds = settings.keyword_enrichment_max_rounds

        # NEW: Persistent validation cache across enrichment rounds
        # This cache is passed to validate_batch_parallel() to avoid re-validating
        # the same keywords in subsequent rounds (~30-35% LLM call reduction)
        enrichment_validation_cache: dict[str, tuple] = {}

        initial_count = len(initial_keywords) if initial_keywords else 0
        logger.info(
            f"Starting with {len(all_enriched)} pre-validated keywords "
            f"({initial_count} from anchor enrichment + {len(validated_seeds)} from bulk validation)"
        )

        for round_num in range(1, max_rounds + 1):
            # Select next batch of validated seeds
            next_seeds = self._select_next_seed_batch(
                conceptual_keywords=validated_conceptual,  # Only use validated seeds
                enriched_so_far=all_enriched,
                topic_clusters=topic_clusters,
                seeds_used=seeds_used,
                batch_size=settings.keyword_enrichment_batch_size
            )

            if not next_seeds:
                logger.info(f"No more seeds to process after {round_num - 1} rounds")
                break

            # Call DataForSEO Keyword Expansion
            logger.info(f"Round {round_num}: Enriching {len(next_seeds)} seeds...")
            suggestions = self.dataforseo_tool.expand_keywords(
                seed_keywords=next_seeds,
                location_code=settings.target_location
            )

            # NEW: Validate keyword relevance with LLM (pre-filter + semantic validation + parallel processing)
            cache_size_before = len(enrichment_validation_cache)
            logger.info(f"[Round {round_num}] Validating {len(suggestions)} expanded keywords (cache size: {cache_size_before})...")
            validation_results = validator.validate_batch_parallel(
                keywords=suggestions,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type,
                batch_size=settings.keyword_validation_batch_size,
                threshold=settings.keyword_relevance_threshold,
                validation_cache=enrichment_validation_cache,  # Persist cache across rounds
                # max_workers defaults to settings.keyword_validation_max_workers (3)
            )
            cache_size_after = len(enrichment_validation_cache)
            cache_hits_this_round = len(suggestions) - (cache_size_after - cache_size_before)
            if cache_hits_this_round > 0:
                logger.info(f"[Round {round_num}] Cache hits: {cache_hits_this_round} (new entries: {cache_size_after - cache_size_before})")

            # Filter to only relevant keywords
            relevant_suggestions = [
                kw_dict for kw_dict, is_relevant, _score in validation_results
                if is_relevant
            ]

            logger.info(
                f"[Round {round_num}] Validation complete: {len(relevant_suggestions)}/{len(suggestions)} "
                f"keywords passed relevance check (filtered {len(suggestions) - len(relevant_suggestions)})"
            )

            # Merge and deduplicate (only relevant keywords)
            # Filter out keywords we already have (case-insensitive)
            new_keywords = [
                kw for kw in relevant_suggestions
                if kw['keyword'].lower() not in enriched_keyword_strings
            ]
            duplicates_filtered = len(relevant_suggestions) - len(new_keywords)
            if duplicates_filtered > 0:
                logger.info(f"[Round {round_num}] Filtered {duplicates_filtered} duplicate keywords")
            all_enriched.extend(new_keywords)
            enriched_keyword_strings.update(kw['keyword'].lower() for kw in new_keywords)
            seeds_used.update(next_seeds)

            # Check if we have enough
            quality_keywords = [
                k for k in all_enriched
                if k.get('search_volume', 0) >= settings.keyword_enrichment_min_volume
            ]
            coverage = self._calculate_cluster_coverage(quality_keywords, topic_clusters, conceptual_keywords)

            logger.info(
                f"Round {round_num} complete: {len(quality_keywords)} quality keywords "
                f"({len(all_enriched)} total), {coverage:.1%} cluster coverage"
            )

            # Stopping condition
            if (
                len(quality_keywords) >= settings.keyword_enrichment_target_count
                and coverage >= settings.keyword_cluster_min_coverage
            ):
                logger.info(f"✓ Enrichment target reached after {round_num} rounds")
                break

        logger.info(
            f"Enrichment complete: {len(all_enriched)} keywords discovered, "
            f"{len(quality_keywords)} with volume >= {settings.keyword_enrichment_min_volume}"
        )
        logger.info(
            f"[Validation Cache] Final size: {len(enrichment_validation_cache)} entries "
            f"(LLM calls saved by caching across rounds)"
        )
        return all_enriched

    def _llm_real_phrase_seeds(self, ctx, broad_seeds: list[str]) -> list[str]:
        """P0a: LLM-generate real 2-3 word search-phrase seeds for contains-seed expansion, grounded in
        the idea's value-prop + pains (and the proven-real broad idea-intent terms as examples). These
        surface an idea's OWN SEO axis when the broad Google-Ads set is category-only. Returns [] on any
        failure (fail-soft). Constrains to 2-3 word phrases (contains-seed needs short real phrases)."""
        try:
            from pydantic import BaseModel, Field as _F
            from ..utils.llm_service import LLMService

            class _Seeds(BaseModel):
                seeds: list[str] = _F(default_factory=list,
                                      description="8-10 SHORT 2-3 word real search phrases for the idea's specific job")

            resp, _ = LLMService.invoke_structured(
                prompt=(
                    f"Product job: {ctx.value_proposition}\n"
                    f"Problems it solves: {'; '.join(ctx.pains[:6])}\n"
                    f"Real search terms people already use in this space: {broad_seeds[:10] or '(none found)'}\n\n"
                    f"List 8-10 SHORT seed phrases (STRICTLY 2-3 words) that are REAL, COMMON search terms "
                    f"for this product's SPECIFIC job — the exact problem/outcome, NOT the broad category, "
                    f"and NOT abstract descriptions. They must be phrases that real keywords literally "
                    f"contain (like the examples above, or 'partial rent', 'cost per token'). Avoid "
                    f"conceptual phrases like 'reproducible model tests'. Return JSON."),
                output_model=_Seeds, temperature=0.3,
                model_name=settings.report_structured_llm, reasoning_effort="none")
            out = []
            for s in (getattr(resp, "seeds", None) or []):
                s = (s or "").strip()
                if s and 1 <= len(s.split()) <= 3:
                    out.append(s)
            return out
        except Exception as e:
            logger.warning(f"[Stage 6][ContainsSeed] LLM seed-gen failed: {str(e)[:100]}")
            return []

    def _augment_idea_intent_keywords(self, enriched_keywords: list[dict], selected_solution=None) -> list[dict]:
        """Additive contains-seed discovery (Stage 6): surface the idea-intent long-tail that the broad
        Google-Ads expansion (keywords_for_keywords) structurally misses — it returns the category
        neighborhood regardless of seed. Validated 2026-07-01 to add 4-12x more idea-intent keywords.

        Pipeline: grade the existing set -> its idea-intent keywords are GROUNDED seeds (proven-real,
        on-idea search terms; seed quality is the make-or-break factor) -> DataForSEO keyword_suggestions
        (contains-seed) on them -> grade the results -> MERGE the idea-intent survivors. Purely additive:
        never removes an existing keyword. Fail-soft: any error returns the input unchanged.
        """
        if not selected_solution or not enriched_keywords:
            logger.info(
                "[SEO-RELEVANCE] guard inactive (no selected solution or empty keyword set) "
                "— keywords ship ungraded")
            return enriched_keywords
        try:
            from ..utils.validation.keyword_intent_validator import (
                KeywordIntentRelevanceValidator, IdeaContext,
            )
            validator = KeywordIntentRelevanceValidator()
            ctx = IdeaContext(
                value_proposition=getattr(selected_solution, "value_proposition", "") or "",
                pains=getattr(selected_solution, "pain_points_addressed", None) or [],
                angle=getattr(selected_solution, "winning_angle", "") or "",
                niche=self.niche_description or "",
            )
            ming = settings.keyword_relevance_min_grade
            merge_min = settings.contains_seed_merge_min_grade  # JOB-only merge gate (A/B 2026-07-01)
            existing = {(k.get("keyword", "") or "").lower() for k in enriched_keywords}
            # 1) grade the existing set -> grounded seeds (idea-intent, <=3 words = real, expandable)
            grades = validator.grade_keywords(ctx, [k.get("keyword", "") for k in enriched_keywords if k.get("keyword")])
            # Q-049: stamp the grade on every keyword row NOW — before any early return below —
            # so the three-band volume accounting downstream always sees the full graded set.
            # Ungraded rows keep None (RETAINED fail-open, counted as category reach downstream).
            for k in enriched_keywords:
                k["idea_intent_grade"] = grades.get(k.get("keyword", ""))
            ungraded = sum(1 for k in enriched_keywords if k.get("idea_intent_grade") is None)
            if ungraded / len(enriched_keywords) > 0.2:
                logger.warning(
                    f"[SEO-RELEVANCE] guard degraded ({ungraded}/{len(enriched_keywords)} keywords "
                    f"ungraded, >20%) — idea-intent volume bands will be withheld")
            broad_seeds = list(dict.fromkeys(
                k.get("keyword") for k in enriched_keywords
                if (grades.get(k.get("keyword", "")) or 0) >= ming and 1 <= len((k.get("keyword", "") or "").split()) <= 3
            ))
            # P0a: ALSO ground seeds in the idea's OWN value-prop/pains language via an LLM (grounded in
            # the proven-real broad idea-intent terms as examples). This surfaces the idea's real SEO axis
            # even when the broad Google-Ads set is ~100% category (broad_seeds empty/generic) — the
            # catastrophic-drift case. Flag-gated (dark pending A/B).
            # LLM real-phrase seeds fire when P0a is enabled OR — the thin-case auto-trigger — when the
            # broad set is too thin to cover the idea's SEO axis (few grounded seeds ⇒ thin beachhead).
            thin = (settings.contains_seed_thin_seed_threshold > 0
                    and len(broad_seeds) < settings.contains_seed_thin_seed_threshold)
            use_llm_seeds = settings.contains_seed_llm_seeds or thin
            llm_seeds = self._llm_real_phrase_seeds(ctx, broad_seeds) if use_llm_seeds else []
            seeds = list(dict.fromkeys(s for s in (broad_seeds + llm_seeds) if s))[:settings.contains_seed_max_seeds]
            if not seeds:
                logger.info("[Stage 6][ContainsSeed] no grounding seeds (broad or LLM) — skipping augmentation")
                return enriched_keywords
            logger.info(
                f"[Stage 6][ContainsSeed] seeds: {len(broad_seeds)} broad + {len(llm_seeds)} LLM "
                f"({'thin-case auto-trigger' if thin and not settings.contains_seed_llm_seeds else 'flag'}) "
                f"-> {len(seeds)} used"
            )
            # 2) contains-seed expansion of the grounded seeds
            suggestions: list[dict] = []
            n_contains = 0
            for s in seeds:
                suggestions += self.dataforseo_tool.get_keyword_suggestions(s, limit=settings.contains_seed_per_seed)
            n_contains = len(suggestions)
            # 2b) related-keywords arm (SERP 'searches related to' graph): semantically-adjacent REAL
            # queries that DON'T contain the seed — the gap contains-seed can't cover ('cottage food
            # law texas' → 'selling baked goods from home texas'). Appended into the SAME suggestions
            # list so the grading gate below controls drift identically. A/B-validated 2026-07-02
            # (flag removed): +17 exclusive on-idea licensing keywords, 27% gate survival, tiny cost.
            for s in seeds:
                suggestions += self.dataforseo_tool.get_related_keywords(
                    s, depth=settings.related_keywords_depth,
                    limit=settings.related_keywords_per_seed)
            logger.info(
                f"[Stage 6][ContainsSeed] per-arm: {n_contains} contains-seed + "
                f"{len(suggestions) - n_contains} related-graph suggestions")
            new = list(dict.fromkeys(
                k.get("keyword") for k in suggestions
                if k.get("keyword") and (k.get("keyword") or "").lower() not in existing
            ))
            if not new:
                return enriched_keywords
            # 3) grade the new suggestions, keep only idea-intent, merge
            new_grades = validator.grade_keywords(ctx, new)
            vol = {(k.get("keyword") or "").lower(): (k.get("search_volume", 0) or 0) for k in suggestions}
            comp = {(k.get("keyword") or "").lower(): k.get("competition") for k in suggestions}
            merged, seen = [], set()
            for kw in new:
                kl = kw.lower()
                if (new_grades.get(kw) or 0) >= merge_min and kl not in seen:
                    seen.add(kl)
                    merged.append({"keyword": kw, "search_volume": vol.get(kl, 0), "competition": comp.get(kl),
                                   "idea_intent_grade": new_grades.get(kw)})
            logger.info(
                f"[Stage 6][ContainsSeed] {len(seeds)} grounded seeds -> {len(suggestions)} suggestions -> "
                f"+{len(merged)} idea-intent keywords merged (was {len(enriched_keywords)})"
            )
            return enriched_keywords + merged
        except Exception as e:
            logger.warning(f"[Stage 6][ContainsSeed] augmentation failed, using base set: {str(e)[:120]}")
            logger.info(
                f"[SEO-RELEVANCE] guard degraded (augmentation/grading failed: {str(e)[:80]}) "
                f"— keywords may ship ungraded")
            return enriched_keywords

    def _regrade_resumed_keywords(self, enriched_keywords: list[dict], selected_solution=None) -> None:
        """6c-resume grade backfill (Q-049): checkpointed keyword sets can predate the
        idea_intent_grade stamping. Re-grades IN PLACE, only when no row carries a grade yet
        (a graded checkpoint is never re-graded). Fail-soft: any failure leaves the set
        ungraded — the coverage guard then keeps the volume-band fields None."""
        if not enriched_keywords:
            return
        if any(isinstance(k, dict) and "idea_intent_grade" in k for k in enriched_keywords):
            logger.info("[SEO-RELEVANCE] resume: grades already present — re-grade skipped")
            return
        if not selected_solution:
            logger.info(
                "[SEO-RELEVANCE] guard inactive (resume without selected solution) "
                "— keywords ship ungraded")
            return
        try:
            from ..utils.validation.keyword_intent_validator import (
                KeywordIntentRelevanceValidator, IdeaContext,
            )
            ctx = IdeaContext(
                value_proposition=getattr(selected_solution, "value_proposition", "") or "",
                pains=getattr(selected_solution, "pain_points_addressed", None) or [],
                angle=getattr(selected_solution, "winning_angle", "") or "",
                niche=self.niche_description or "",
            )
            grades = KeywordIntentRelevanceValidator().grade_keywords(
                ctx, [k.get("keyword", "") for k in enriched_keywords if k.get("keyword")])
            for k in enriched_keywords:
                k["idea_intent_grade"] = grades.get(k.get("keyword", ""))
            graded = sum(1 for k in enriched_keywords if k.get("idea_intent_grade") is not None)
            logger.info(
                f"[SEO-RELEVANCE] resume re-grade: {graded}/{len(enriched_keywords)} keywords graded")
        except Exception as e:
            logger.warning(
                f"[SEO-RELEVANCE] guard degraded (resume re-grade failed: {str(e)[:100]}) "
                f"— keywords ship ungraded")

    def _enrich_anchor_keywords(
        self,
        anchor_keywords: list[dict],
        selected_solution=None,
        niche_context=None,
    ) -> list[dict]:
        """
        Enrich anchor keywords from keyword validation via DataForSEO expansion.

        Simpler than _iterative_keyword_enrichment - no cluster tracking needed.
        Uses anchor keyword strings as expansion seeds, then high-volume discoveries.

        Args:
            anchor_keywords: Keyword dicts with 'keyword', 'search_volume' keys
            selected_solution: SolutionIdea for relevance validation context
            niche_context: NicheContext for relevance validation context

        Returns:
            List of enriched keyword dicts with search metrics
        """
        all_enriched = anchor_keywords.copy()
        enriched_keyword_strings = {kw['keyword'].lower() for kw in all_enriched}
        seeds_used: set[str] = set()
        validator = KeywordRelevanceValidator()
        validation_cache: dict[str, tuple] = {}

        niche_description = niche_context.niche_description if niche_context else self.niche_description
        solution_name = selected_solution.solution_name if selected_solution else "Unknown"
        solution_description = selected_solution.value_proposition if selected_solution else ""
        project_type = selected_solution.project_type if selected_solution else "saas"

        anchor_seed_strings = [kw['keyword'] for kw in anchor_keywords]
        batch_size = settings.keyword_enrichment_batch_size

        logger.info(
            f"[Anchor Enrichment] Starting with {len(anchor_keywords)} anchor keywords, "
            f"target: {settings.keyword_enrichment_target_count} quality keywords"
        )

        for round_num in range(1, settings.keyword_enrichment_max_rounds + 1):
            # Seed selection: anchor keywords first, then discoveries to expand from.
            remaining_anchors = [s for s in anchor_seed_strings if s not in seeds_used]
            next_seeds = remaining_anchors[:batch_size]
            if len(next_seeds) < batch_size:
                fill = batch_size - len(next_seeds)
                pool = [k for k in all_enriched if k['keyword'] not in seeds_used
                        and k['keyword'] not in next_seeds and k.get('search_volume', 0) > 1000]
                chosen = sorted(pool, key=lambda k: k.get('search_volume', 0), reverse=True)
                next_seeds += [k['keyword'] for k in chosen[:fill] if k['keyword'] not in next_seeds]

            if not next_seeds:
                logger.info(f"[Anchor Enrichment] No more seeds after {round_num - 1} rounds")
                break

            # DataForSEO expansion
            logger.info(f"[Anchor Enrichment] Round {round_num}: Expanding {len(next_seeds)} seeds...")
            suggestions = self.dataforseo_tool.expand_keywords(
                seed_keywords=next_seeds,
                location_code=settings.target_location
            )

            # LLM relevance validation
            results = validator.validate_batch_parallel(
                keywords=suggestions,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type,
                batch_size=settings.keyword_validation_batch_size,
                threshold=settings.keyword_relevance_threshold,
                validation_cache=validation_cache,
            )

            # Filter relevant + deduplicate
            new_keywords = [
                kw_dict for kw_dict, is_relevant, _ in results
                if is_relevant and kw_dict['keyword'].lower() not in enriched_keyword_strings
            ]

            all_enriched.extend(new_keywords)
            enriched_keyword_strings.update(kw['keyword'].lower() for kw in new_keywords)
            seeds_used.update(next_seeds)

            # Check target (count-based only, no cluster coverage)
            quality_count = sum(
                1 for k in all_enriched
                if k.get('search_volume', 0) >= settings.keyword_enrichment_min_volume
            )
            logger.info(
                f"[Anchor Enrichment] Round {round_num}: {quality_count} quality keywords "
                f"({len(all_enriched)} total, +{len(new_keywords)} new)"
            )

            if quality_count >= settings.keyword_enrichment_target_count:
                logger.info(f"[Anchor Enrichment] Target reached after {round_num} rounds")
                break

        quality_final = sum(
            1 for k in all_enriched
            if k.get('search_volume', 0) >= settings.keyword_enrichment_min_volume
        )
        logger.info(
            f"[Anchor Enrichment] Complete: {len(all_enriched)} total, "
            f"{quality_final} quality (target: {settings.keyword_enrichment_target_count})"
        )
        return all_enriched

    def _select_next_seed_batch(
        self,
        conceptual_keywords: list,
        enriched_so_far: list,
        topic_clusters: list,
        seeds_used: set,
        batch_size: int = 20
    ) -> list:
        """
        Smart seed selection prioritizing uncovered clusters and high-performers.

        NOTE: As of Phase 6b redesign, conceptual_keywords contains only
        PRE-VALIDATED keywords (filtered by get_search_volume bulk validation).
        This ensures high success rate when expanding seeds.

        Args:
            conceptual_keywords: List of ConceptualKeyword objects (validated seeds only)
            enriched_so_far: List of enriched keyword dicts from DataForSEO
            topic_clusters: List of ConceptualTopicCluster objects
            seeds_used: Set of keywords already used as seeds
            batch_size: Number of seeds to select

        Returns:
            List of keyword strings to use as next seeds
        """
        candidates = []

        # Priority 1: Seeds from underrepresented clusters (40% of batch)
        underrepresented = self._find_underrepresented_clusters(enriched_so_far, topic_clusters, conceptual_keywords)
        cluster_seeds = [
            kw.keyword for kw in conceptual_keywords
            if kw.cluster in underrepresented and kw.keyword not in seeds_used
        ]
        # Sort by priority (1=highest)
        cluster_seeds_sorted = sorted(
            [kw for kw in conceptual_keywords if kw.keyword in cluster_seeds],
            key=lambda k: k.priority
        )
        candidates.extend([kw.keyword for kw in cluster_seeds_sorted[:int(batch_size * 0.4)]])

        # Priority 2: High-volume keywords as new seeds - suggestions of suggestions (30% of batch)
        high_performers = sorted(
            [k for k in enriched_so_far if k.get('search_volume', 0) > 5000],
            key=lambda k: k.get('search_volume', 0),
            reverse=True
        )
        candidates.extend([
            k['keyword'] for k in high_performers[:int(batch_size * 0.3)]
            if k['keyword'] not in seeds_used
        ])

        # Priority 3: Remaining high-priority conceptual seeds (30% of batch)
        remaining = [
            kw for kw in conceptual_keywords
            if kw.keyword not in seeds_used
        ]
        remaining_sorted = sorted(remaining, key=lambda k: k.priority)
        candidates.extend([kw.keyword for kw in remaining_sorted[:int(batch_size * 0.3)]])

        # Return up to batch_size unique seeds
        unique_candidates = []
        seen = set()
        for candidate in candidates:
            if candidate not in seen and candidate not in seeds_used:
                unique_candidates.append(candidate)
                seen.add(candidate)
                if len(unique_candidates) >= batch_size:
                    break

        return unique_candidates

    def _find_underrepresented_clusters(
        self,
        enriched_keywords: list,
        topic_clusters: list,
        conceptual_keywords: list
    ) -> list:
        """
        Find topic clusters that have few enriched keywords.

        Args:
            enriched_keywords: List of enriched keyword dicts from DataForSEO
            topic_clusters: List of ConceptualTopicCluster objects
            conceptual_keywords: List of ConceptualKeyword objects

        Returns:
            List of cluster names that need more coverage
        """
        # Count enriched keywords per cluster
        cluster_counts = {}
        enriched_keyword_set = {k['keyword'].lower() for k in enriched_keywords}

        for conceptual_kw in conceptual_keywords:
            if conceptual_kw.keyword.lower() in enriched_keyword_set:
                cluster_counts[conceptual_kw.cluster] = cluster_counts.get(conceptual_kw.cluster, 0) + 1

        # Find clusters below average
        if not cluster_counts:
            # No enriched keywords yet - return all clusters
            return [c.name for c in topic_clusters]

        avg_count = sum(cluster_counts.values()) / len(topic_clusters)
        underrepresented = [
            cluster.name for cluster in topic_clusters
            if cluster_counts.get(cluster.name, 0) < avg_count
        ]

        return underrepresented if underrepresented else [c.name for c in topic_clusters[:2]]

    def _calculate_cluster_coverage(
        self,
        enriched_keywords: list,
        topic_clusters: list,
        conceptual_keywords: list
    ) -> float:
        """
        Calculate what percentage of topic clusters have enriched keywords.

        Args:
            enriched_keywords: List of enriched keyword dicts from DataForSEO
            topic_clusters: List of ConceptualTopicCluster objects
            conceptual_keywords: List of ConceptualKeyword objects

        Returns:
            Float between 0.0 and 1.0 representing cluster coverage
        """
        if not topic_clusters:
            return 0.0

        # Map enriched keywords back to clusters
        enriched_keyword_set = {k['keyword'].lower() for k in enriched_keywords}
        clusters_with_keywords = set()

        for conceptual_kw in conceptual_keywords:
            if conceptual_kw.keyword.lower() in enriched_keyword_set:
                clusters_with_keywords.add(conceptual_kw.cluster)

        coverage = len(clusters_with_keywords) / len(topic_clusters)
        return coverage

    def _enrich_with_difficulty(self, enriched_keywords: list[dict]) -> list[dict]:
        """
        Add keyword_difficulty scores to top 1000 keywords by volume.

        Calls DataForSEO Labs bulk_keyword_difficulty API for SEO difficulty scores.
        These scores reflect actual ranking difficulty (backlink strength of top 10),
        NOT Google Ads competition (advertiser density).

        Timeline derivation from difficulty:
        - difficulty < 25: "1-3 months" (easy)
        - difficulty 25-40: "3-6 months"
        - difficulty 40-60: "6-9 months"
        - difficulty 60-75: "9-15 months"
        - difficulty > 75: "12-18+ months" (hard)

        Args:
            enriched_keywords: List of keyword dicts from DataForSEO enrichment

        Returns:
            Same list with 'keyword_difficulty' field added (None for keywords
            outside top 1000 or not found in API response)
        """
        if not enriched_keywords:
            logger.warning("[Difficulty] No enriched keywords to process")
            return enriched_keywords

        # Sort by volume descending
        sorted_kws = sorted(
            enriched_keywords,
            key=lambda k: k.get('search_volume', 0) or 0,
            reverse=True
        )

        # Get top 1000 keyword strings for API call
        top_1000_strings = [k['keyword'] for k in sorted_kws[:1000] if k.get('keyword')]

        if not top_1000_strings:
            logger.warning("[Difficulty] No valid keyword strings found in top 1000")
            return enriched_keywords

        logger.info(f"[Difficulty] Fetching SEO difficulty for top {len(top_1000_strings)} keywords by volume")

        # Single API call for difficulty scores
        try:
            difficulty_map = self.dataforseo_tool.get_keyword_difficulty(
                keywords=top_1000_strings,
                location_code=settings.target_location,
                language_code=settings.target_language
            )

            if not difficulty_map:
                logger.warning("[Difficulty] No difficulty scores returned from API")
                # Still set keyword_difficulty to None for all keywords
                for kw in enriched_keywords:
                    kw['keyword_difficulty'] = None
                return enriched_keywords

            # Merge difficulty back into enriched_keywords
            enriched_count = 0
            for kw in enriched_keywords:
                kw_key = kw.get('keyword', '').lower().strip()
                difficulty = difficulty_map.get(kw_key)
                kw['keyword_difficulty'] = difficulty
                if difficulty is not None:
                    enriched_count += 1

            logger.info(
                f"[Difficulty] Enriched {enriched_count}/{len(enriched_keywords)} keywords "
                f"with SEO difficulty scores"
            )

            # Log difficulty distribution for insights
            difficulties = [d for d in difficulty_map.values() if d is not None]
            if difficulties:
                avg_diff = sum(difficulties) / len(difficulties)
                easy_count = sum(1 for d in difficulties if d < 30)
                medium_count = sum(1 for d in difficulties if 30 <= d < 60)
                hard_count = sum(1 for d in difficulties if d >= 60)
                logger.info(
                    f"[Difficulty] Distribution: Easy(<30)={easy_count}, "
                    f"Medium(30-60)={medium_count}, Hard(>60)={hard_count}, "
                    f"Avg={avg_diff:.1f}"
                )

        except Exception as e:
            logger.error(f"[Difficulty] API call failed: {e}. Proceeding without difficulty data.")
            # Set keyword_difficulty to None for all keywords on error
            for kw in enriched_keywords:
                kw['keyword_difficulty'] = None

        return enriched_keywords

    # UGC / forum / aggregator surfaces — when these dominate a SERP, a purpose-built site has room
    # to rank (the niche isn't owned by a strong dedicated incumbent). Heuristic, not a DA/DR signal.
    _UGC_SERP_DOMAINS = (
        "reddit.com", "quora.com", "stackexchange.com", "stackoverflow.com", "medium.com",
        "blogspot.", "wordpress.com", "pinterest.", "facebook.com", "youtube.com", "tumblr.",
        "github.com", "news.ycombinator", "linkedin.com",
    )

    # Institutional surfaces — when these DOMINATE a SERP, a new commercial domain faces a real
    # ranking headwind that keyword-difficulty scores can understate (gov/edu/.mil + Wikipedia rarely
    # carry the link signals KD models weigh). Caution-only signal, matched on the host suffix.
    _INSTITUTIONAL_SERP_SUFFIXES = (".gov", ".edu", ".mil")

    def _compute_seo_kill_question(self, enriched_keywords, selected_solution):
        """Deterministic SEO-thesis stress test for a distribution_seo idea (no LLM).

        Reuses the already-validated keyword set (search_volume + keyword_difficulty) for the page
        ceiling + KD distribution (no new keyword API calls); a small SERP sample reads beatability.
        Returns a SeoKillQuestion. Fail-soft to the caller.
        """
        import statistics
        from ..models.seo_strategy import SeoKillQuestion
        from ..utils.intent_volume_bands import MIN_GRADED_COVERAGE, graded_coverage, keyword_grade

        def _vol(k):
            return k.get("search_volume", 0) or 0 if isinstance(k, dict) else (getattr(k, "search_volume", 0) or 0)

        def _kd(k):
            v = k.get("keyword_difficulty") if isinstance(k, dict) else getattr(k, "keyword_difficulty", None)
            return v if isinstance(v, (int, float)) else None

        def _kw(k):
            return (k.get("keyword", "") if isinstance(k, dict) else getattr(k, "keyword", "")) or ""

        # 0. Off-topic exclusion (Q-049): keywords the intent grader marked grade-0 (OFFTOPIC)
        # are not this idea's page universe — drop them from ALL kill-question inputs. Ungraded
        # rows are RETAINED (fail-open). Kill-switched by seo_offtopic_volume_guard.
        all_rows = list(enriched_keywords or [])
        if settings.seo_offtopic_volume_guard:
            rows = [k for k in all_rows if keyword_grade(k) != 0]
            if len(rows) != len(all_rows):
                logger.info(
                    f"[SEO-KILL] grade-0 (off-topic) keywords excluded from inputs: "
                    f"{len(all_rows)} -> {len(rows)}")
        else:
            rows = all_rows

        # 1. Page universe — distinct non-zero-volume intents (each = one indexable programmatic page).
        with_vol = [k for k in rows if _vol(k) > 0]
        ceiling = len(with_vol)
        head = sum(1 for k in with_vol if _vol(k) >= 1000)
        mid = sum(1 for k in with_vol if 100 <= _vol(k) < 1000)
        tail = sum(1 for k in with_vol if 1 <= _vol(k) < 100)

        # 2. KD distribution — how many pages are realistically winnable on a new (DA~0) domain.
        kds = [v for v in (_kd(k) for k in with_vol) if v is not None]
        median_kd = round(statistics.median(kds), 1) if kds else None
        rankable_kd = settings.seo_kill_question_rankable_kd
        winnable = sum(1 for v in kds if v < rankable_kd)
        # KD coverage — DataForSEO omits KD for many (often easy) long-tail intents, so on sparse coverage
        # `winnable`/`median_kd` reflect a tiny biased subsample, not the real page universe. The verdict
        # floor (apply_seo_kill_downgrade) abstains below this; the display verdict says so rather than
        # over-claiming "only N winnable".
        kd_n = len(kds)
        kd_coverage = (kd_n / ceiling) if ceiling else 0.0
        kd_sparse = (kd_n < settings.seo_kill_question_min_kd_sample
                     or kd_coverage < settings.seo_kill_question_min_kd_coverage)

        # 3. SERP shape — sample the highest-volume intents and read TWO independent signals from the
        # same fetch (no extra API calls):
        #   • forum_soft (UPSIDE-only): UGC/forum-dominated SERPs = extra ranking room. Absence (0.0) is
        #     NEUTRAL (professional SERPs have no forums by default), never a downgrade.
        #   • institutional (CAUTION-only): gov/edu/.mil/Wikipedia-DOMINATED SERPs = a ranking headwind
        #     that low KD can understate. High share is a flag to verify winnability, NOT a kill.
        # Neither enters the verdict — KD is the real competition signal. They only color the rationale.
        from urllib.parse import urlparse

        def _is_institutional(link: str) -> bool:
            host = urlparse(link or "").netloc.lower()
            return (host.endswith(self._INSTITUTIONAL_SERP_SUFFIXES)
                    or ".gov." in host or "wikipedia.org" in host)

        forum_soft, institutional, serp_n = None, None, 0
        sample_n = settings.seo_kill_question_serp_sample
        serper = getattr(self, "serper_tool", None) or getattr(self, "search_tool", None)
        if sample_n and serper is not None:
            sample = sorted(with_vol, key=_vol, reverse=True)[:sample_n]
            soft_hits, inst_hits = 0, 0
            for k in sample:
                try:
                    res = serper.run(search_query=_kw(k))
                    organic = (res.get("organic", []) if isinstance(res, dict) else [])[:5]
                    links = [(o.get("link", "") or "").lower() for o in organic]
                    ugc = sum(1 for l in links if any(d in l for d in self._UGC_SERP_DOMAINS))
                    inst = sum(1 for l in links if _is_institutional(l))
                    if ugc >= 2:
                        soft_hits += 1
                    if inst >= 3:  # a clear majority of the top 5 — genuinely institution-owned
                        inst_hits += 1
                    serp_n += 1
                except Exception as e:
                    logger.debug(f"[SEO-KILL] SERP sample failed for '{_kw(k)[:40]}': {str(e)[:80]}")
            forum_soft = round(soft_hits / serp_n, 2) if serp_n else None
            institutional = round(inst_hits / serp_n, 2) if serp_n else None

        # 4. Penalty risk — a large page universe that's mostly near-zero-volume tail reads as the kind
        # of thin, templated programmatic site that trips scaled-content / helpful-content actions.
        tail_share = (tail / ceiling) if ceiling else 0.0
        penalty_risk = ceiling >= settings.seo_kill_question_high_page_count and tail_share >= 0.7

        # 5. One-line verdict (the kill-question answered).
        if ceiling < 30:
            verdict = (f"Weak SEO thesis — only {ceiling} non-zero-volume intents; too few pages to "
                       f"justify a programmatic distribution play.")
        elif penalty_risk:
            verdict = (f"Large but THIN page universe ({ceiling} pages, {round(tail_share * 100)}% "
                       f"near-zero-volume tail) — scaled-content / helpful-content penalty risk.")
        elif kd_sparse:
            verdict = (f"Page universe exists ({ceiling}), but KD data is too sparse "
                       f"({kd_n} of {ceiling} intents scored) to judge winnability — treat the "
                       f"winnable / KD figures as indicative only.")
        elif median_kd is not None and median_kd >= 60:
            verdict = (f"Page universe exists ({ceiling}) but KD is high (median {median_kd}) — slow "
                       f"time-to-rank on a new domain; only {winnable} realistically winnable.")
        else:
            verdict = (f"SEO thesis holds — {ceiling} indexable intents, {winnable} winnable on a new "
                       f"domain (median KD {median_kd}).")
        # Both SERP signals are rationale-only color (never the verdict). Forum-softness is upside —
        # cite only when present so 0.0 never reads as "0% beatable". Institutional dominance is a
        # caution — cite only when a majority of sampled SERPs are gov/edu-owned (a headwind KD misses).
        soft_clause = (f"; {round(forum_soft * 100)}% of {serp_n} sampled SERPs are forum-soft (bonus room)"
                       if forum_soft else "")
        inst_clause = (f"; {round(institutional * 100)}% of {serp_n} sampled SERPs are authority-heavy "
                       f"(gov/edu-dominated) — expect a ranking headwind KD understates"
                       if institutional and institutional >= 0.5 else "")
        rationale = (f"Page ceiling {ceiling} (head {head} / mid {mid} / tail {tail}); KD on {kd_n}/{ceiling} "
                     f"intents; median KD {median_kd}; winnable<{rankable_kd:.0f} = {winnable}{soft_clause}{inst_clause}.")

        # 6. On-idea slice (display + telemetry only — never feeds the verdict): the page universe
        # restricted to idea-intent keywords (grade >= min_grade). None when the grader covered
        # <80% of the input set (same coverage guard as the volume bands).
        on_idea_ceiling, on_idea_winnable = None, None
        if all_rows and graded_coverage(all_rows) >= MIN_GRADED_COVERAGE:
            ming = settings.keyword_relevance_min_grade
            on_rows = [k for k in with_vol
                       if keyword_grade(k) is not None and keyword_grade(k) >= ming]
            on_idea_ceiling = len(on_rows)
            on_idea_winnable = sum(
                1 for k in on_rows if _kd(k) is not None and _kd(k) < rankable_kd)

        return SeoKillQuestion(
            indexable_page_ceiling=ceiling, head_count=head, mid_count=mid, tail_count=tail,
            median_keyword_difficulty=median_kd, winnable_pages=winnable, kd_sample_size=kd_n,
            forum_soft_serp_share=forum_soft, institutional_serp_share=institutional, serp_sampled=serp_n,
            penalty_risk_flag=penalty_risk,
            on_idea_page_ceiling=on_idea_ceiling, on_idea_winnable=on_idea_winnable,
            verdict=verdict, rationale=rationale,
        )

    def _append_seo_intent_caveat(self, seo_strategy, enriched_keywords) -> None:
        """Q-049 volume-honesty degradation caveat (Stage 6). Fires when the analyzed keyword
        volume is dominated by category / off-topic reach: idea-intent share < 10%, OR off-topic
        share > 30%, OR a single dominant (>50%) head term whose grade is missing or below
        keyword_relevance_min_grade. Suppressed entirely when the band fields are None (graded
        coverage < 80%) or seo_offtopic_volume_guard is off. Fail-soft; appends at most one
        deduplicated entry to state.pipeline_degradations."""
        try:
            if not settings.seo_offtopic_volume_guard or seo_strategy is None:
                return
            iiv = getattr(seo_strategy, "idea_intent_monthly_volume", None)
            off = getattr(seo_strategy, "offtopic_volume_share", None)
            cat = getattr(seo_strategy, "category_volume_share", None)
            total = getattr(seo_strategy, "total_monthly_volume", 0) or 0
            if iiv is None or off is None or cat is None or total <= 0:
                return
            from ..utils.intent_volume_bands import keyword_grade

            def _vol(k):
                if isinstance(k, dict):
                    return k.get("search_volume", 0) or 0
                return getattr(k, "search_volume", 0) or 0

            intent_share = iiv / total
            reasons = []
            if intent_share < 0.10:
                reasons.append(
                    f"idea-intent keywords carry only {intent_share:.0%} of the analyzed volume")
            if off > 0.30:
                reasons.append(f"{off:.0%} of the analyzed volume is off-topic (grade 0)")
            rows = list(enriched_keywords or [])
            if rows:
                top1 = max(rows, key=_vol)
                t1v = _vol(top1)
                g = keyword_grade(top1)
                if t1v / total > 0.5 and (g is None or g < settings.keyword_relevance_min_grade):
                    kw_s = (top1.get("keyword", "") if isinstance(top1, dict)
                            else getattr(top1, "keyword", "")) or "?"
                    reasons.append(
                        f"a single non-idea-intent keyword ('{kw_s[:60]}') carries "
                        f"{t1v / total:.0%} of the analyzed volume")
            if not reasons:
                return
            msg = (f"SEO volume honesty: {'; '.join(reasons)} — idea-intent demand is {iiv:,}/mo "
                   f"of the {total:,}/mo analyzed keyword set; treat the headline keyword volume "
                   f"as category reach, not validated idea demand.")
            if msg not in self.state.pipeline_degradations:
                self.state.pipeline_degradations.append(msg)
            logger.info(f"[SEO-RELEVANCE] degradation caveat appended: {msg[:160]}")
        except Exception as e:
            logger.warning(f"[SEO-RELEVANCE] caveat computation failed: {str(e)[:100]}")

    def _validate_solution_pricing(self, solution_name: str) -> dict:
        """
        Helper method to validate pricing for a single solution (thread-safe).

        Creates a new PricingStrategyCrew instance per call for thread safety.

        Args:
            solution_name: Name of the solution to validate

        Returns:
            Dict with 'solution_name', 'result' (PricingStrategyResult), and 'usage_metrics'
        """
        from ..crews import PricingStrategyCrew

        logger.info(f"[Parallel] Starting pricing validation for: {solution_name}")

        # Find full solution object
        solution = find_solution_by_name(
            solution_name,
            self.state.idea_generation.solution_ideas
        )

        if not solution:
            logger.warning(f"[Parallel] Solution '{solution_name}' not found in idea generation")
            return {
                "solution_name": solution_name,
                "result": None,
                "usage_metrics": None
            }

        # Create new PricingStrategyCrew instance for thread safety
        pricing_crew = PricingStrategyCrew()

        # Market-data handoff (utils/market_brief.py): same Phase-1 web-verified facts the
        # competitor/SEO/market-sizing crews receive, so pricing doesn't miss an incumbent's
        # known price point or re-derive the niche wallet class from scratch.
        from ..utils.market_brief import build_market_brief
        _market_vars = build_market_brief(self.state, solution)

        # Run pricing analysis
        pricing_result = pricing_crew.analyze(
            selected_solution=solution,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description,
            allowed_project_types=self.state.allowed_project_types,
            market_sizing=self.state.market_sizing,
            audience_mapping=self.state.audience_mapping,
            solution_scores=(
                self.state.solution_selection.all_solution_scores
                if self.state.solution_selection else None
            ),
            **_market_vars,
        )

        if pricing_result:
            logger.info(f"[Parallel] Pricing complete for {solution_name}: Starter {pricing_result.recommended_starter_price}")
        else:
            logger.warning(f"[Parallel] Pricing failed for {solution_name}")

        return {
            "solution_name": solution_name,
            "result": pricing_result,
            "usage_metrics": pricing_crew.usage_metrics
        }

    def _run_competitive_analysis(self):
        """Competitive Analysis: On-demand competitive analysis for the selected solution.

        Competitive analysis is needed before downstream stages 8, 8.6, 8.7 can use it, so this
        auto-runs it for the selected solution.
        """
        if self.state.competitive_analysis:
            return  # Already have data (e.g., from checkpoint)
        if not self.state.solution_selection:
            logger.warning("[Stage 7.5] No solution selection - skipping")
            return
        selected_name = self.state.solution_selection.selected_solution_name
        if not selected_name:
            logger.warning("[Stage 7.5] No selected solution name - skipping")
            return
        logger.info(f"[Stage 7.5] Running competitive analysis for: {selected_name}")
        self._emit_progress(5.5, "Competitive Analysis", "running")
        self.analyze_single_solution_competitors(selected_name)
        self._emit_progress(5.5, "Competitive Analysis", "completed")

    def stage_6_seo_strategy(self):
        """
        Stage 6: Integrated Keyword Validation + SEO Strategy Development

        Runs keyword validation for top solutions, then SEOStrategyCrew performs
        complete workflow FOR THE SELECTED SOLUTION:
        1. Validates keyword demand for top N solutions
        2. Generates seed keywords specifically for selected solution
        3. Expands keywords using DataForSEO API
        4. Analyzes and creates tiered SEO strategy
        """
        logger.info("=" * 80)
        logger.info("STAGE 6: Integrated Keyword Validation + SEO Strategy")
        logger.info("=" * 80)
        self._emit_progress(6, "SEO & Keyword Strategy", "running")

        # Early exit if SEO strategy already exists from checkpoint
        if self.state.seo_strategy_report is not None:
            logger.info("✓ SEO strategy already loaded from checkpoint - skipping Stage 6")
            self._emit_progress(6, "SEO & Keyword Strategy", "completed")
            return

        # Run integrated keyword validation as part of Stage 6
        if not self.state.keyword_validation_results:
            self._run_integrated_keyword_validation()

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("No solution selected - skipping SEO strategy")
            self.state.seo_strategy_report = None
            self.state.current_stage = 7
            self._skip_stage(6, "SEO & Keyword Strategy", "No solution selected")
            self.checkpoint_mgr.save_stage("stage_6_seo_strategy", {"skipped": True, "reason": "No solution selected"})
            return

        # Check if we have required data
        if not self.state.idea_generation:
            logger.warning("Insufficient data for SEO strategy - skipping")
            self.state.seo_strategy_report = None
            self.state.current_stage = 7
            self._skip_stage(6, "SEO & Keyword Strategy", "Insufficient data for SEO strategy")
            self.checkpoint_mgr.save_stage("stage_6_seo_strategy", {"skipped": True, "reason": "Insufficient data for SEO strategy"})
            return

        # Get the selected solution (with fuzzy matching fallback)
        selected_solution_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_solution_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(
                f"Selected solution '{selected_solution_name}' not found in solution ideas! "
                f"Available solutions: {[sol.solution_name for sol in self.state.idea_generation.solution_ideas]}"
            )
            self.state.seo_strategy_report = None
            self.state.current_stage = 7
            self._skip_stage(6, "SEO & Keyword Strategy", "Selected solution not found")
            self.checkpoint_mgr.save_stage("stage_6_seo_strategy", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        logger.info(f"Generating SEO strategy for selected solution: {selected_solution_name}")

        # ── Collect anchor keywords from keyword validation ──
        anchor_keywords = []

        if self.state.keyword_validation_results:
            selected_kv = next(
                (v for v in self.state.keyword_validation_results
                 if v.solution_name == selected_solution_name), None
            )
            if selected_kv:
                # Full validated keywords (have 'keyword', 'search_volume', 'competition_index')
                if selected_kv.validated_keywords:
                    anchor_keywords.extend(selected_kv.validated_keywords)
                # Fallback to top_keywords (uses 'volume'/'competition' keys -> normalize)
                elif selected_kv.top_keywords:
                    anchor_keywords.extend([
                        {
                            'keyword': kw.get('keyword', ''),
                            'search_volume': kw.get('volume', kw.get('search_volume', 0)),
                            'competition_index': kw.get('competition', kw.get('competition_index', 0)),
                        }
                        for kw in selected_kv.top_keywords
                        if kw.get('keyword')
                    ])

        # Also add organic_discovery_queries (concrete only, validated via DataForSEO)
        if selected_solution.organic_discovery_queries:
            existing = {kw.get('keyword', '').lower() for kw in anchor_keywords}
            concrete_queries = [
                q for q in selected_solution.organic_discovery_queries
                if q.lower() not in existing and '[' not in q and ']' not in q
            ]
            if concrete_queries:
                try:
                    odq_validated = self.dataforseo_tool.get_search_volume(
                        keywords=concrete_queries, location_code=settings.target_location
                    )
                    valid_odq = [kw for kw in odq_validated if kw.get('search_volume', 0) > 0]
                    anchor_keywords.extend(valid_odq)
                except Exception as e:
                    logger.warning(f"[Stage 6] Failed to validate organic_discovery_queries: {e}")

        anchor_keyword_strings = [kw.get('keyword', '') for kw in anchor_keywords if kw.get('keyword')]

        if anchor_keywords:
            logger.info(f"[Stage 6] Collected {len(anchor_keywords)} anchor keywords from keyword validation")
        else:
            logger.info("[Stage 6] No anchor keywords available from keyword validation - will use LLM path")

        # ── Phase 6-anchor: Enrich anchor keywords (priority path) ──
        anchor_enriched = []
        anchor_sufficient = False

        if anchor_keywords:
            anchor_enriched = self._enrich_anchor_keywords(
                anchor_keywords=anchor_keywords,
                selected_solution=selected_solution,
                niche_context=self.state.niche_context,
            )

            # Check if anchor enrichment is sufficient
            quality_count = sum(
                1 for k in anchor_enriched
                if k.get('search_volume', 0) >= settings.keyword_enrichment_min_volume
            )
            anchor_sufficient = quality_count >= settings.keyword_enrichment_target_count
            logger.info(
                f"[Stage 6] Anchor enrichment: {quality_count} quality keywords "
                f"(target: {settings.keyword_enrichment_target_count}) -> "
                f"{'SUFFICIENT - skipping LLM phases' if anchor_sufficient else 'INSUFFICIENT - running LLM fallback'}"
            )

        # ── Decide: skip LLM or run as fallback ──
        if anchor_sufficient:
            # Anchor keywords are enough - skip 6a/b/c entirely
            enriched_keywords = anchor_enriched
            expanded_keywords = None  # Strategy creation handles None gracefully

            # Additive contains-seed discovery: merge the idea-intent long-tail the broad expansion missed.
            enriched_keywords = self._augment_idea_intent_keywords(enriched_keywords, selected_solution)

            # Store to state for downstream Stage 11 trend analysis
            self.state.seo_enriched_keywords = enriched_keywords
            self.checkpoint_mgr.save_stage("stage_6c_enrichment", enriched_keywords)

            logger.info(f"[Stage 6] Using {len(enriched_keywords)} anchor-enriched keywords (LLM phases skipped)")

        else:
            # ── LLM fallback: Initialize SEOStrategyCrew + run 6a/b/c ──
            from ..utils.market_brief import build_market_brief
            seo_crew = SEOStrategyCrew(
                niche=self.niche_description,
                selected_solution=selected_solution,
                selection_rationale=self.state.solution_selection.selection_rationale,
                competitive_analysis=self.state.competitive_analysis,
                pain_points=self.state.pain_point_analysis,
                niche_context=self.state.niche_context,
                allowed_project_types=self.state.allowed_project_types,
                audience_mapping=self.state.audience_mapping,
                covered_keywords=anchor_keyword_strings or None,
                job_id=self.state.job_id,
                market_brief_vars=build_market_brief(self.state, selected_solution),
            )

            # Check for existing sub-phase checkpoints (enables partial resume)
            completed_stages = self.checkpoint_mgr.get_completed_stages()
            has_9_5a = "stage_6a_seed_expansion" in completed_stages
            has_9_5b = "stage_6b_bulk_validation" in completed_stages
            has_9_5c = "stage_6c_enrichment" in completed_stages

            # Phase 6a: Conceptual keyword expansion (SEO crew)
            logger.info(f"Phase 6a: Conceptual keyword expansion for {selected_solution_name}...")

            # Resume from checkpoint if available (with validation)
            if has_9_5a and self.state.seo_expanded_keywords:
                from ..models.seo_strategy import ExpandedKeywordList
                try:
                    expanded_keywords = ExpandedKeywordList(**self.state.seo_expanded_keywords)
                    # Validate restored data has required content
                    if not expanded_keywords.keywords or len(expanded_keywords.keywords) < 5:
                        raise ValueError(f"Restored 6a checkpoint has insufficient keywords ({len(expanded_keywords.keywords) if expanded_keywords.keywords else 0})")
                    logger.info(f"Resuming from Phase 6a checkpoint ({len(expanded_keywords.keywords)} keywords)")
                except Exception as e:
                    logger.warning(f"Phase 6a checkpoint invalid: {e}. Re-running expansion...")
                    expanded_keywords = seo_crew.expand_keywords_phase_1()
            else:
                expanded_keywords = seo_crew.expand_keywords_phase_1()
            logger.info(
                f"Conceptual expansion complete: {len(expanded_keywords.keywords)} keywords, "
                f"{len(expanded_keywords.topic_clusters)} clusters"
            )

            # Checkpoint 6a: Save expanded keywords
            self.state.seo_expanded_keywords = expanded_keywords.model_dump(mode='json')
            self.checkpoint_mgr.save_stage("stage_6a_seed_expansion", self.state.seo_expanded_keywords)
            logger.info("Phase 6a checkpoint saved: seed_expansion")

            # Phase 6b: Bulk validation with DataForSEO
            logger.info("Phase 6b: Bulk validation of conceptual keywords with DataForSEO...")

            # Resume from checkpoint if available (with validation)
            resume_9_5b = False
            if has_9_5b and self.state.seo_validation_results:
                quality_validated = self.state.seo_validation_results.get("validated_keywords", [])
                min_volume = self.state.seo_validation_results.get("threshold_used", 500)
                # Validate restored data
                if quality_validated and len(quality_validated) >= 1:
                    logger.info(f"Resuming from Phase 6b checkpoint ({len(quality_validated)} validated keywords)")
                    resume_9_5b = True
                else:
                    logger.warning("Phase 6b checkpoint has no validated keywords. Re-running validation...")

            if not resume_9_5b:
                # Extract keyword strings from conceptual keywords
                conceptual_keyword_strings = [kw.keyword for kw in expanded_keywords.keywords]
                logger.info(f"Validating {len(conceptual_keyword_strings)} conceptual keywords...")

                # Bulk validate using get_search_volume (handles up to 1,000 keywords)
                validated_keywords = self.dataforseo_tool.get_search_volume(
                    keywords=conceptual_keyword_strings,
                    location_code=settings.target_location
                )

                logger.info(f"DataForSEO returned metrics for {len(validated_keywords)} keywords")

                # Filter to keywords meeting minimum volume threshold
                min_volume = settings.keyword_enrichment_min_volume  # Default: 500
                quality_validated = [
                    kw for kw in validated_keywords
                    if kw.get('search_volume', 0) >= min_volume
                ]

                logger.info(
                    f"Validation complete: {len(quality_validated)}/{len(conceptual_keyword_strings)} "
                    f"keywords have volume >= {min_volume}"
                )

                # Fallback: If too few validated keywords, lower threshold and retry filter
                if len(quality_validated) < 20:
                    logger.warning(
                        f"Only {len(quality_validated)} keywords meet volume threshold. "
                        f"Lowering to {min_volume // 5} to find more seeds..."
                    )
                    quality_validated = [
                        kw for kw in validated_keywords
                        if kw.get('search_volume', 0) >= (min_volume // 5)
                    ]
                    logger.info(f"With lowered threshold: {len(quality_validated)} validated keywords")

                # Checkpoint 6b: Save validation results
                self.state.seo_validation_results = {
                    "validated_keywords": quality_validated,
                    "original_count": len(conceptual_keyword_strings),
                    "passed_count": len(quality_validated),
                    "threshold_used": min_volume
                }
                self.checkpoint_mgr.save_stage("stage_6b_bulk_validation", self.state.seo_validation_results)
                logger.info("Phase 6b checkpoint saved: bulk_validation")

            # Absolute minimum check
            if len(quality_validated) < 5:
                logger.error(
                    f"Bulk validation failed: Only {len(quality_validated)} keywords have search volume. "
                    f"Niche may be too specific or DataForSEO has insufficient data."
                )
                logger.warning("Skipping SEO strategy generation - insufficient keyword data")
                self.state.current_stage = 7
                self._skip_stage(6, "SEO & Keyword Strategy", f"Insufficient keyword data ({len(quality_validated)} keywords)")
                self.checkpoint_mgr.save_stage("stage_6_seo_strategy", {
                    "skipped": True,
                    "reason": f"Insufficient validated keywords ({len(quality_validated)} < 5)"
                })
                return

            # Phase 6c: Iterative DataForSEO enrichment (programmatic)
            logger.info(
                f"Phase 6c: Iterative keyword enrichment with {len(quality_validated)} "
                f"validated seeds..."
            )

            # Resume from checkpoint if available (with validation)
            resume_9_5c = False
            if has_9_5c and self.state.seo_enriched_keywords:
                enriched_keywords = self.state.seo_enriched_keywords
                # Validate restored data has sufficient keywords
                if enriched_keywords and len(enriched_keywords) >= 5:
                    logger.info(f"Resuming from Phase 6c checkpoint ({len(enriched_keywords)} enriched keywords)")
                    resume_9_5c = True
                else:
                    logger.warning(f"Phase 6c checkpoint has insufficient keywords ({len(enriched_keywords) if enriched_keywords else 0}). Re-running enrichment...")

            if resume_9_5c:
                # Q-049: checkpointed keywords may predate idea-intent grade stamping —
                # backfill grades (skipped when the checkpoint already carries them).
                self._regrade_resumed_keywords(enriched_keywords, selected_solution)

            if not resume_9_5c:
                enriched_keywords = self._iterative_keyword_enrichment(
                    conceptual_keywords=expanded_keywords.keywords,
                    validated_seeds=quality_validated,
                    topic_clusters=expanded_keywords.topic_clusters,
                    selected_solution=selected_solution,
                    niche_context=self.state.niche_context,
                    initial_keywords=anchor_enriched if anchor_enriched else None,
                )
                # Additive contains-seed discovery: merge the idea-intent long-tail the broad expansion missed.
                enriched_keywords = self._augment_idea_intent_keywords(enriched_keywords, selected_solution)
                # Checkpoint 6c: Save enriched keywords
                self.state.seo_enriched_keywords = enriched_keywords
                self.checkpoint_mgr.save_stage("stage_6c_enrichment", enriched_keywords)
                logger.info("Phase 6c checkpoint saved: enrichment")

            logger.info(f"Enrichment complete: {len(enriched_keywords)} keywords with search data")

            # Quality Gate: Validate keyword enrichment coverage
            total_expanded = len(expanded_keywords.keywords) if hasattr(expanded_keywords, 'keywords') else len(quality_validated)
            total_enriched = len(enriched_keywords)
            enrichment_coverage = total_enriched / total_expanded if total_expanded > 0 else 0.0

            logger.info("=" * 60)
            logger.info("KEYWORD ENRICHMENT COVERAGE ASSESSMENT")
            logger.info("=" * 60)
            logger.info(f"Total keywords expanded (Phase 6a): {total_expanded}")
            logger.info(f"Validated seeds (Phase 6b): {len(quality_validated)}")
            logger.info(f"Final enriched keywords (Phase 6c): {total_enriched}")
            logger.info(f"Enrichment coverage: {enrichment_coverage:.1%}")

            if enrichment_coverage < settings.keyword_enrichment_min_coverage:
                logger.warning(
                    f"LOW ENRICHMENT COVERAGE: {enrichment_coverage:.1%} < threshold {settings.keyword_enrichment_min_coverage:.1%}"
                )
                logger.warning(
                    "Possible causes: (1) Niche/solution mismatch, (2) Too aggressive filtering, (3) Limited search demand"
                )
                logger.warning(
                    f"Recommendation: Review relevance validator thresholds or expand seed generation strategy"
                )
            elif enrichment_coverage >= settings.keyword_enrichment_target_coverage:
                logger.info(
                    f"EXCELLENT COVERAGE: {enrichment_coverage:.1%} >= target {settings.keyword_enrichment_target_coverage:.1%}"
                )
                logger.info("Strong keyword-solution alignment - high confidence in SEO strategy")
            else:
                logger.info(
                    f"Acceptable coverage: {enrichment_coverage:.1%} (between min {settings.keyword_enrichment_min_coverage:.1%} and target {settings.keyword_enrichment_target_coverage:.1%})"
                )

            logger.info("=" * 60)

        # ── Phase 6d: Keyword Difficulty Enrichment ──
        # Add SEO difficulty scores (0-100) to top 1000 keywords for accurate timeline estimates
        logger.info("Phase 6d: Enriching keywords with SEO difficulty scores...")
        enriched_keywords = self._enrich_with_difficulty(enriched_keywords)

        # Update state with difficulty-enriched keywords
        self.state.seo_enriched_keywords = enriched_keywords
        self.checkpoint_mgr.save_stage("stage_6d_difficulty", enriched_keywords)
        logger.info("Phase 6d checkpoint saved: difficulty enrichment")

        # ── Strategy creation (shared by both paths) ──
        # When anchor_sufficient=True, seo_crew wasn't initialized above - initialize now for strategy creation
        if anchor_sufficient:
            from ..utils.market_brief import build_market_brief
            seo_crew = SEOStrategyCrew(
                niche=self.niche_description,
                selected_solution=selected_solution,
                selection_rationale=self.state.solution_selection.selection_rationale,
                competitive_analysis=self.state.competitive_analysis,
                pain_points=self.state.pain_point_analysis,
                niche_context=self.state.niche_context,
                allowed_project_types=self.state.allowed_project_types,
                audience_mapping=self.state.audience_mapping,
                job_id=self.state.job_id,
                market_brief_vars=build_market_brief(self.state, selected_solution),
            )

        try:
            logger.info(f"Creating final SEO strategy (multitask flow) for {selected_solution_name}...")
            seo_strategy = seo_crew.create_strategy_multitask(
                enriched_keywords=enriched_keywords,
                expanded_keywords=expanded_keywords
            )

            # Collect Knowledge objects for cleanup
            if getattr(seo_crew, '_crew_knowledge', None):
                self.register_knowledge(seo_crew._crew_knowledge)

            # Record crew cost
            if seo_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 6 - SEO Strategy",
                    usage_metrics=seo_crew.usage_metrics,
                    model=settings.openai_model_name
                )

            # VALIDATION: Verify keyword utilization (detect dropped keywords)
            total_tier_1 = len(seo_strategy.tier_1_keywords)
            total_tier_2 = len(seo_strategy.tier_2_keywords or [])
            total_tier_3 = sum(len(g.keywords) for g in (seo_strategy.tier_3_geographic_groups or []))
            total_tier_4 = sum(len(g.keywords) for g in (seo_strategy.tier_4_category_groups or []))
            total_tiered = total_tier_1 + total_tier_2 + total_tier_3 + total_tier_4

            input_count = len(enriched_keywords)
            utilization = total_tiered / input_count if input_count > 0 else 0

            filtered_count = input_count - total_tiered
            filtering_rate = filtered_count / input_count if input_count > 0 else 0

            logger.info(
                f"Keyword analysis: {total_tiered}/{input_count} tiered ({utilization:.1%}), "
                f"{filtered_count} filtered ({filtering_rate:.1%}) - "
                f"Tier 1: {total_tier_1}, Tier 2: {total_tier_2}, Tier 3: {total_tier_3}, Tier 4: {total_tier_4}"
            )

            # Quality Gate: Validate tiering coverage
            if input_count > 20:
                if utilization < settings.keyword_tiering_min_coverage:
                    logger.warning(
                        f"⚠️  LOW TIERING COVERAGE: {total_tiered}/{input_count} tiered ({utilization:.1%}) < threshold {settings.keyword_tiering_min_coverage:.1%}"
                    )
                    logger.warning(
                        "This suggests either: (1) Filtering was too aggressive (check STEP 0), "
                        "or (2) Tier 3/4 grouping was incomplete. Review key_findings for details."
                    )
                elif utilization >= settings.keyword_enrichment_target_coverage:
                    logger.info(
                        f"✅ EXCELLENT TIERING COVERAGE: {utilization:.1%} of keywords distributed across tiers (target: {settings.keyword_enrichment_target_coverage:.1%})"
                    )
                else:
                    logger.info(f"✓ Good tiering coverage: {utilization:.1%} of keywords distributed across tiers")

            # SEO kill-question (distribution_seo deep research): attach a deterministic thesis
            # stress-test (page ceiling, winnable pages, penalty risk) so the report flags pSEO ideas
            # that score great on keyword volume but have no real page universe / face a penalty.
            if getattr(selected_solution, "winning_angle", None) == "distribution_seo":
                try:
                    seo_strategy.seo_kill_question = self._compute_seo_kill_question(
                        enriched_keywords, selected_solution)
                    logger.info(f"[SEO-KILL] {seo_strategy.seo_kill_question.verdict}")
                except Exception as e:
                    logger.warning(f"[SEO-KILL] skipped: {str(e)[:120]}")

            self.state.seo_strategy_report = seo_strategy
            # Q-049: volume-honesty degradation caveat (fires only when the band fields were
            # computed and the analyzed volume is dominated by category/off-topic reach).
            self._append_seo_intent_caveat(seo_strategy, enriched_keywords)

            logger.info(
                f"[OK] SEO strategy complete for {selected_solution_name}: "
                f"{seo_strategy.total_keywords_analyzed} keywords analyzed, "
                f"{len(seo_strategy.tier_1_keywords)} Tier 1 keywords, "
                f"{len(seo_strategy.topic_clusters) if seo_strategy.topic_clusters else 0} topic clusters"
            )
        except Exception as e:
            # Degrade like every other Phase-2 stage — NEVER kill a job that has already spent the
            # (expensive) keyword/DataForSEO budget over one flaky LLM sub-task. The report ships
            # without the SEO section; downstream already tolerates seo_strategy_report=None
            # (same as the "no solution selected" path above).
            logger.error(f"SEO strategy generation failed — skipping Stage 6 (report ships without SEO): {e}")
            self.state.seo_strategy_report = None
            self.state.current_stage = 7
            self._skip_stage(6, "SEO & Keyword Strategy", "SEO strategy generation failed")
            self.checkpoint_mgr.save_stage(
                "stage_6_seo_strategy",
                {"skipped": True, "reason": f"SEO strategy generation failed: {str(e)[:200]}"},
            )
            return

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 7

        # Mark stage complete with tracking - flag fallback if Tier 0/1 keywords are empty
        seo_report = self.state.seo_strategy_report
        tier0_empty = not seo_report.tier_0_keywords if seo_report else True
        tier1_empty = not seo_report.tier_1_keywords if seo_report else True
        used_fallback = tier0_empty or tier1_empty
        if used_fallback:
            logger.warning(f"⚠️ Stage 6 completed with limited keywords: Tier0={'empty' if tier0_empty else 'ok'}, Tier1={'empty' if tier1_empty else 'ok'}")
        self._mark_stage_complete(6, used_fallback=used_fallback)

        # Checkpoint: Save SEO strategy
        if self.state.seo_strategy_report:
            self.checkpoint_mgr.save_stage("stage_6_seo_strategy", self.state.seo_strategy_report)

    def _ensure_selected_in_topn(self, top_n: list, all_scores: list) -> list:
        """Guarantee the selected winner stays in the Stage 7/8 working set.

        Stages 7/8 pick top-N by RAW composite_score, but Stage-6 keyword validation can pivot
        selected_solution_name to a lower-raw-composite idea. Without this, the pivoted winner
        loses its pricing/traffic and the report (which looks these up BY the selected name)
        renders nothing for the actual recommendation. Appends the selected score if missing.
        """
        sel = getattr(getattr(self.state, "solution_selection", None), "selected_solution_name", None)
        if not sel or any(s.solution_name == sel for s in top_n):
            return top_n
        match = next((s for s in (all_scores or []) if s.solution_name == sel), None)
        if match is not None:
            logger.info(f"[Stage 7/8] Adding pivoted selected winner '{sel}' to the top-N working set")
            return list(top_n) + [match]
        return top_n

    def stage_7_pricing_validation(self):
        """
        Stage 8: Pricing Strategy Validation for Top N Solutions (Parallel Execution)

        Validates monetization strategy for top N solutions in parallel for ~50% time savings.
        Each solution's pricing analysis runs independently.

        Analyzes:
        - Competitor pricing benchmarks from competitive analysis
        - Pain point willingness-to-pay (WTP) scores
        - Solution features and positioning
        """
        logger.info("=" * 80)
        logger.info("STAGE 8: Pricing Strategy Validation (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(7, "Pricing Validation", "running")

        # Check if we have solution selection with scores
        if not self.state.solution_selection:
            logger.warning("[Stage 7] No solution selected - skipping pricing validation")
            self.state.current_stage = 8
            self._skip_stage(7, "Pricing Validation", "No solution selected for pricing analysis")
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 7] No pain point analysis - skipping pricing validation")
            self.state.current_stage = 8
            self._skip_stage(7, "Pricing Validation", "Insufficient pain point data for pricing")
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 7] No competitive analysis - skipping pricing validation")
            self.state.current_stage = 8
            self._skip_stage(7, "Pricing Validation", "No competitive data for pricing benchmarking")
            return

        # Check if we have idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 7] No solution ideas - skipping pricing validation")
            self.state.current_stage = 8
            self._skip_stage(7, "Pricing Validation", "No solution ideas for pricing validation")
            return

        # Get top N solutions from all_solution_scores (like keyword validation)
        all_scores = self.state.solution_selection.all_solution_scores
        if not all_scores or len(all_scores) < 1:
            logger.warning("[Stage 7] No solution scores available - skipping")
            self.state.current_stage = 8
            self._skip_stage(7, "Pricing Validation", "No solution scores for pricing analysis")
            return

        # Sort by composite score and take top N (configurable)
        top_n_scores = sorted(all_scores, key=lambda s: s.composite_score, reverse=True)[:settings.top_solutions_for_validation]
        top_n_scores = self._ensure_selected_in_topn(top_n_scores, all_scores)

        logger.info(f"[Stage 7] Analyzing pricing for top {len(top_n_scores)} solutions (PARALLEL)")

        # Resume support: track already validated solutions
        pricing_results = []
        already_validated = set()
        if self.state.pricing_strategies:
            pricing_results = list(self.state.pricing_strategies)
            already_validated = {p.solution_name for p in pricing_results}
            if already_validated:
                logger.info(f"[Stage 7] Resuming - {len(already_validated)} solutions already validated: {already_validated}")

        # Filter solutions that need validation
        solutions_to_validate = [
            solution_score.solution_name
            for solution_score in top_n_scores
            if solution_score.solution_name not in already_validated
        ]

        if not solutions_to_validate:
            logger.info("[Stage 7] All solutions already validated - skipping")
            self.state.current_stage = 8
            self.checkpoint_mgr.save_stage(
                "stage_7_pricing_validation",
                [p.model_dump() for p in pricing_results]
            )
            self._mark_stage_complete(7)
            return

        logger.info(f"[Stage 7] Validating {len(solutions_to_validate)} solutions in parallel (max_workers=2)")

        # Run pricing validation in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all pricing validation tasks
            futures = {
                executor.submit(self._validate_solution_pricing, solution_name): solution_name
                for solution_name in solutions_to_validate
            }

            # Collect results as they complete
            for future in as_completed(futures):
                solution_name = futures[future]
                try:
                    result_dict = future.result()
                    pricing_result = result_dict["result"]
                    usage_metrics = result_dict["usage_metrics"]

                    # Record crew cost
                    if usage_metrics:
                        self.cost_tracker.record_crew_usage(
                            stage=f"Stage 8 - Pricing Strategy ({solution_name})",
                            usage_metrics=usage_metrics,
                            model=settings.openai_model_name
                        )

                    if pricing_result:
                        pricing_results.append(pricing_result)
                        logger.info(f"[Stage 7] Pricing validation complete: {solution_name}")

                        # Incremental checkpoint (thread-safe: append only)
                        self.state.pricing_strategies = pricing_results
                        self.checkpoint_mgr.save_stage(
                            "stage_7_pricing_validation",
                            [p.model_dump() for p in pricing_results]
                        )
                    else:
                        logger.warning(f"[Stage 7] Pricing validation failed: {solution_name}")

                except Exception as e:
                    logger.error(f"[Stage 7] Pricing validation error for {solution_name}: {e}")

        # Store final results
        self.state.pricing_strategies = pricing_results
        self.state.current_stage = 8

        # Mark stage complete with tracking
        self._mark_stage_complete(7)

        logger.info(f"[Stage 7] Pricing Strategy Validation Complete - {len(pricing_results)}/{len(top_n_scores)} solutions analyzed (PARALLEL)")

    def _validate_solution_keywords(
        self,
        solution_name: str,
        audience_vocab: list | None,
        start_attempt: int = 1,
        initial_state: dict | None = None,
    ) -> dict:
        """
        Helper method to validate keywords for a single solution (thread-safe).

        Creates new SeedGenerator instance per call for thread safety.

        Args:
            solution_name: Name of the solution to validate
            audience_vocab: Audience vocabulary from Stage 6.5
            start_attempt: First pivot attempt to run (2 when the batched
                attempt-1 pre-pass already ran for this solution)
            initial_state: Carry-over from the batched attempt-1 pre-pass:
                {'validation_result', 'relevance_score', 'good_keywords'}

        Returns:
            Dict with 'solution_name', 'validation_result' (dict), 'attempts_made',
            'best_relevance_score', 'accumulated_keywords_count'
        """
        logger.info(f"[Parallel] Starting keyword validation for: {solution_name}")

        # Find the full solution object
        solution = find_solution_by_name(
            solution_name,
            self.state.idea_generation.solution_ideas
        )

        if not solution:
            logger.warning(f"[Parallel] Solution '{solution_name}' not found in idea generation")
            return {
                "solution_name": solution_name,
                "validation_result": None,
                "attempts_made": 0,
                "best_relevance_score": 0.0,
                "accumulated_keywords_count": 0
            }

        # Initialize seed generator for this solution (new instance for thread safety)
        # Pass shared dataforseo_tool for cache continuity across keyword validation and Phase 6d
        seed_generator = SeedGenerator(
            state=self.state,
            niche_context=self.state.niche_context if hasattr(self.state, 'niche_context') else None,
            pain_point_analysis=self.state.pain_point_analysis if hasattr(self.state, 'pain_point_analysis') else None,
            audience_vocabulary=audience_vocab,
            dataforseo_client=self.dataforseo_tool,
        )

        # Adaptive keyword generation with pivot strategies.
        # Seed from the batched attempt-1 pre-pass when provided so pivots
        # build on (not discard) the batch evidence.
        initial_state = initial_state or {}
        accumulated_good_keywords = list(initial_state.get("good_keywords") or [])
        accumulated_keyword_strings = {
            kw.get('keyword', '').lower() for kw in accumulated_good_keywords
        }
        best_relevance_score = initial_state.get("relevance_score") or 0.0
        best_validation_result = initial_state.get("validation_result")
        max_attempts = getattr(settings, 'keyword_pivot_max_attempts', 3)
        relevance_threshold = getattr(settings, 'keyword_relevance_threshold', 0.6)
        keyword_validation_cache: dict[str, tuple] = {}
        final_attempt = max(0, start_attempt - 1)

        for attempt in range(start_attempt, max_attempts + 1):
            final_attempt = attempt
            logger.info(f"[Parallel] {solution_name} - Attempt {attempt}/{max_attempts}")

            # Generate seeds with current strategy
            seeds = seed_generator.generate_seeds_with_strategy(solution, attempt, count=20)

            if not seeds:
                logger.warning(f"[Parallel] {solution_name} - Attempt {attempt}: No seeds generated")
                continue

            # Quick expansion for relevance testing
            expanded_keywords = seed_generator.expand_seeds_quick(
                seeds,
                target_size=getattr(settings, 'keyword_quick_expansion_size', 50)
            )

            # Derive validation metrics from expanded keywords (no extra API call)
            validation_result = seed_generator.calculate_validation_from_expansion(
                expanded_keywords, solution_name, original_seed_count=len(seeds)
            )

            # Check relevance
            niche_context = self.state.niche_context if hasattr(self.state, 'niche_context') else None
            relevance_score, good_keywords, issues = check_keyword_relevance(
                expanded_keywords,
                solution,
                niche_context=niche_context,
                validation_cache=keyword_validation_cache,
                audience_vocabulary=audience_vocab
            )

            # Accumulate good keywords across attempts
            if good_keywords:
                new_good = [
                    kw for kw in good_keywords
                    if kw.get('keyword', '').lower() not in accumulated_keyword_strings
                ]
                accumulated_good_keywords.extend(new_good)
                accumulated_keyword_strings.update(kw.get('keyword', '').lower() for kw in new_good)

            # Track best result
            if relevance_score > best_relevance_score:
                best_relevance_score = relevance_score
                best_validation_result = validation_result

            # Check if we have good enough keywords
            if relevance_score >= relevance_threshold:
                logger.info(f"[Parallel] {solution_name} - SUCCESS at attempt {attempt}")
                break

        # Compute niche-relevant volume from semantically filtered keywords
        # If semantic validation clearly failed (low relevance), leave as None
        # so downstream falls back to total_volume
        if best_relevance_score >= 0.3:
            niche_relevant_volume = sum(
                kw.get('search_volume', 0) for kw in accumulated_good_keywords
            )
        else:
            niche_relevant_volume = None
            logger.warning(
                f"[Parallel] {solution_name} - best_relevance_score={best_relevance_score:.2f} < 0.3, "
                "skipping niche_relevant_volume (semantic filtering unreliable)"
            )

        # Return result
        if best_validation_result:
            best_validation_result["attempts_made"] = final_attempt
            best_validation_result["best_relevance_score"] = best_relevance_score
            best_validation_result["niche_relevant_volume"] = niche_relevant_volume
            # Swaps the unfiltered expansion-pool count for the graded set.
            finalize_graded_validation(best_validation_result, accumulated_good_keywords)

            # Log filter ratio when both volumes are available
            if niche_relevant_volume is not None:
                raw_volume = best_validation_result.get("total_volume", 0)
                if raw_volume > 0:
                    ratio = niche_relevant_volume / raw_volume
                    logger.info(
                        f"[Parallel] {solution_name} - niche_relevant_volume={niche_relevant_volume:,} "
                        f"vs total_volume={raw_volume:,} (ratio={ratio:.1%})"
                    )

            logger.info(f"[Parallel] {solution_name} complete: {final_attempt} attempts, relevance={best_relevance_score:.2f}")
        else:
            logger.warning(f"[Parallel] {solution_name} - All attempts failed")

        return {
            "solution_name": solution_name,
            "validation_result": best_validation_result,
            "attempts_made": final_attempt,
            "best_relevance_score": best_relevance_score,
            "accumulated_keywords_count": len(accumulated_good_keywords)
        }

    def _prefilter_fallback_keywords(self, keywords: list[dict], solution, niche_context) -> list[dict]:
        """Deterministic prefilter for the batched-attempt-1 generic fallback (4.2): before a
        thin-seed solution adopts the CROSS-SOLUTION expansion pool, keep only keywords whose
        tokens overlap this solution's own corpus (value-prop + pains + winning angle +
        jargon-expanded audience vocabulary). Survivors are volume-sorted; the survivors are
        used even when <20 remain (fail-closed — never the raw cross-solution pool). An empty
        corpus token set fails open (returns the volume-sorted input unchanged)."""
        from ..utils.jargon_glossary import build_jargon_glossary, expand_jargon
        from ..utils.validation.thread_validator import _tokenize_for_prefilter

        pool = list(keywords or [])
        pool.sort(key=lambda k: k.get("search_volume", 0) or 0, reverse=True)
        glossary = build_jargon_glossary(niche_context)
        corpus_parts = [
            getattr(solution, "value_proposition", "") or "",
            " ".join(str(p) for p in (getattr(solution, "pain_points_addressed", None) or [])),
            getattr(solution, "winning_angle", "") or "",
            " ".join(str(j) for j in (getattr(niche_context, "audience_jargon", None) or [])),
        ]
        corpus = expand_jargon(" ".join(p for p in corpus_parts if p), glossary)
        corpus_tokens = _tokenize_for_prefilter(corpus)
        if not corpus_tokens:
            return pool  # fail-open: no corpus to filter against
        survivors = []
        for k in pool:
            kw_text = expand_jargon(k.get("keyword", "") or "", glossary)
            if _tokenize_for_prefilter(kw_text) & corpus_tokens:
                survivors.append(k)
        logger.info(
            f"[Stage 6-KV] fallback prefilter: {len(pool)} -> {len(survivors)} keywords "
            f"({getattr(solution, 'solution_name', '?')})")
        return survivors

    def _batched_attempt_one_validation(
        self,
        solutions_to_validate: list[str],
        audience_vocab: list | None,
    ) -> dict[str, dict]:
        """
        Attempt-1 keyword validation for ALL solutions via ONE batched expansion.

        Instead of one expand_keywords call per solution (5 solutions = 5 calls),
        the diverse seeds of every solution are expanded in a single batched call
        and the results distributed back per solution. Pivot attempts (2+) still
        run per-solution, but only for solutions that fail relevance here.

        Returns:
            {solution_name: {'validation_result', 'relevance_score', 'good_keywords'}}
            Empty dict on batch failure (callers fall back to per-solution attempt 1).
        """
        batch_states: dict[str, dict] = {}
        solution_seeds: dict[str, list[str]] = {}
        diverse_union: list[str] = []
        seen_seeds: set[str] = set()
        niche_context = self.state.niche_context if hasattr(self.state, 'niche_context') else None

        for name in solutions_to_validate:
            solution = find_solution_by_name(name, self.state.idea_generation.solution_ideas)
            if not solution:
                logger.warning(f"[Stage 6-KV] Solution '{name}' not found - skipping batch seed generation")
                continue
            seed_generator = SeedGenerator(
                state=self.state,
                niche_context=niche_context,
                pain_point_analysis=self.state.pain_point_analysis if hasattr(self.state, 'pain_point_analysis') else None,
                audience_vocabulary=audience_vocab,
                dataforseo_client=self.dataforseo_tool,
            )
            seeds = seed_generator.generate_seeds_with_strategy(solution, attempt=1, count=20)
            if not seeds:
                continue
            solution_seeds[name] = seeds
            # Mirror expand_seeds_quick's diverse-seed selection (5 per solution)
            step = max(1, len(seeds) // 5)
            diverse = [seeds[i] for i in range(0, min(len(seeds), 20), step)][:5]
            for s in diverse:
                key = s.lower().strip()
                if key not in seen_seeds:
                    seen_seeds.add(key)
                    diverse_union.append(s)

        if not solution_seeds:
            return batch_states

        quick_size = getattr(settings, 'keyword_quick_expansion_size', 50)
        try:
            all_expanded = self.dataforseo_tool.expand_keywords(
                seed_keywords=diverse_union,
                location_code=settings.target_location,
                max_results_per_batch=quick_size * max(len(solution_seeds), 1),
            )
        except Exception as e:
            logger.warning(
                f"[Stage 6-KV] Batched attempt-1 expansion failed ({e}) - "
                "falling back to per-solution validation"
            )
            return batch_states

        logger.info(
            f"[Stage 6-KV] Batched attempt-1 expansion: {len(diverse_union)} seeds "
            f"from {len(solution_seeds)} solutions → {len(all_expanded)} keywords (1 batched call)"
        )

        for name, seeds in solution_seeds.items():
            solution = find_solution_by_name(name, self.state.idea_generation.solution_ideas)
            if not solution:
                continue
            seed_generator = SeedGenerator(
                state=self.state,
                niche_context=niche_context,
                pain_point_analysis=self.state.pain_point_analysis if hasattr(self.state, 'pain_point_analysis') else None,
                audience_vocabulary=audience_vocab,
                dataforseo_client=self.dataforseo_tool,
            )
            # Distribute: keep keywords overlapping this solution's seeds;
            # fall back to the whole batch (all niche-relevant) when too few match
            seed_terms = [s.lower() for s in seeds]
            solution_keywords = [
                kw for kw in all_expanded
                if any(term in kw.get('keyword', '').lower() for term in seed_terms)
            ]
            if len(solution_keywords) < 20:
                if settings.seo_fallback_prefilter:
                    # 4.2: never hand a thin-seed solution the RAW cross-solution pool —
                    # prefilter it against this solution's own corpus first (fail-closed:
                    # the survivors are used even when <20 remain).
                    solution_keywords = self._prefilter_fallback_keywords(
                        all_expanded, solution, niche_context)
                else:
                    solution_keywords = list(all_expanded)
            if len(solution_keywords) > quick_size:
                solution_keywords = sorted(
                    solution_keywords,
                    key=lambda x: x.get('search_volume', 0),
                    reverse=True,
                )[:quick_size]

            validation_result = seed_generator.calculate_validation_from_expansion(
                solution_keywords, name, original_seed_count=len(seeds)
            )
            relevance_score, good_keywords, _issues = check_keyword_relevance(
                solution_keywords,
                solution,
                niche_context=niche_context,
                audience_vocabulary=audience_vocab,
            )
            batch_states[name] = {
                "validation_result": validation_result,
                "relevance_score": relevance_score,
                "good_keywords": good_keywords,
            }
            logger.info(
                f"[Stage 6-KV] Batched attempt 1: {name} relevance={relevance_score:.2f}, "
                f"{len(good_keywords)} good keywords"
            )

        return batch_states

    def _run_integrated_keyword_validation(self):
        """
        Integrated Keyword Validation for Top N Solutions (Parallel)

        Validates keyword demand for top N solutions in parallel for ~50% time savings.
        Each solution's keyword validation (including adaptive pivot strategies) runs independently.

        Adjusts composite scores based on actual market search behavior.
        """
        logger.info("=" * 80)
        logger.info("Keyword Demand Validation (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(6, "Keyword Validation", "running")

        # Check if feature is enabled
        if not getattr(settings, 'keyword_validation_enabled', True):
            logger.info("[Stage 6-KV] Keyword validation disabled - skipping")
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 6-KV] No solution selected - skipping keyword validation")
            return

        # Get top N solutions from all_solution_scores (configurable)
        all_scores = self.state.solution_selection.all_solution_scores
        if not all_scores or len(all_scores) < 1:
            logger.warning("[Stage 6-KV] No solution scores available - skipping")
            return

        # Sort by composite score and take top N (configurable)
        top_n_scores = sorted(all_scores, key=lambda s: s.composite_score, reverse=True)[:settings.top_solutions_for_validation]

        # Phase 2.2: Always include selected solution for validation (prevents data loss)
        selected_name = self.state.solution_selection.selected_solution_name
        top_n_names = {s.solution_name for s in top_n_scores}
        if selected_name and selected_name not in top_n_names:
            selected_score = next(
                (s for s in all_scores if s.solution_name == selected_name),
                None
            )
            if selected_score:
                top_n_scores.append(selected_score)
                logger.info(f"[Stage 6-KV] Added selected solution '{selected_name}' to validation set")

        logger.info(f"[Stage 6-KV] Validating keyword demand for {len(top_n_scores)} solutions (PARALLEL)")

        # Resume support: Load existing validation results
        validation_results = []
        already_validated = set()
        if self.state.keyword_validation_results:
            validation_results = list(self.state.keyword_validation_results)
            already_validated = {v.solution_name for v in validation_results}
            if already_validated:
                logger.info(f"[Stage 6-KV] Resuming - {len(already_validated)} solutions already validated")

        # Extract audience vocabulary for keyword grounding
        audience_vocab = (
            self.state.audience_mapping.common_vocabulary
            if self.state.audience_mapping else None
        )
        if audience_vocab:
            logger.info(f"[Stage 6-KV] Using {len(audience_vocab)} audience vocabulary terms")

        # Filter solutions that need validation
        solutions_to_validate = [
            solution_score.solution_name
            for solution_score in top_n_scores
            if solution_score.solution_name not in already_validated
        ]

        if not solutions_to_validate:
            logger.info("[Stage 6-KV] All solutions already validated - skipping to post-processing")
        else:
            # Batched attempt-1 pre-pass: one expand_keywords call for ALL
            # solutions instead of one per solution. Solutions passing the
            # relevance threshold here never enter the per-solution pivot loop.
            relevance_threshold = getattr(settings, 'keyword_relevance_threshold', 0.6)
            batch_states = self._batched_attempt_one_validation(solutions_to_validate, audience_vocab)

            def _record_validation(result_dict: dict, solution_name: str) -> None:
                validation_result = result_dict["validation_result"]
                if validation_result:
                    validation_obj = CrewKeywordValidationResult(**validation_result)
                    validation_results.append(validation_obj)
                    logger.info(
                        f"[Stage 6-KV] Keyword validation complete: {solution_name} "
                        f"({result_dict['attempts_made']} attempts, relevance={result_dict['best_relevance_score']:.2f})"
                    )
                    # Incremental checkpoint (thread-safe: append only)
                    self.state.keyword_validation_results = validation_results
                    self.checkpoint_mgr.save_stage(
                        "stage_6_keyword_validation_partial",
                        [v.model_dump() for v in validation_results]
                    )
                else:
                    logger.warning(f"[Stage 6-KV] Keyword validation failed: {solution_name}")

            needs_pivot: list[str] = []
            for solution_name in solutions_to_validate:
                state = batch_states.get(solution_name)
                # Acceptance needs BOTH pool relevance AND actual validated keywords. A pool can score
                # just over the relevance threshold while ZERO keywords individually pass (observed live
                # 2026-07-02: all 5 solutions accepted at relevance 0.61 with 0 good keywords → empty
                # validated sets → nrv=0 cascaded into demand/beachhead). 0 good keywords ⇒ pivot.
                if (state and state["validation_result"]
                        and state["relevance_score"] >= relevance_threshold
                        and (state["good_keywords"] or [])):
                    vr = state["validation_result"]
                    good_keywords = state["good_keywords"] or []
                    vr["attempts_made"] = 1
                    vr["best_relevance_score"] = state["relevance_score"]
                    vr["niche_relevant_volume"] = (
                        sum(kw.get('search_volume', 0) for kw in good_keywords)
                        if state["relevance_score"] >= 0.3 else None
                    )
                    # Swaps the unfiltered expansion-pool count for the graded set.
                    finalize_graded_validation(vr, good_keywords)
                    _record_validation(
                        {
                            "validation_result": vr,
                            "attempts_made": 1,
                            "best_relevance_score": state["relevance_score"],
                        },
                        solution_name,
                    )
                else:
                    needs_pivot.append(solution_name)

            if needs_pivot:
                logger.info(
                    f"[Stage 6-KV] {len(needs_pivot)} solution(s) below relevance threshold "
                    f"after batched attempt 1 - running pivot attempts in parallel (max_workers=2)"
                )
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Solutions covered by the batch start at attempt 2 (carrying
                    # batch evidence); batch-failure solutions start fresh at 1.
                    futures = {
                        executor.submit(
                            self._validate_solution_keywords,
                            solution_name,
                            audience_vocab,
                            2 if solution_name in batch_states else 1,
                            batch_states.get(solution_name),
                        ): solution_name
                        for solution_name in needs_pivot
                    }

                    # Collect results as they complete
                    for future in as_completed(futures):
                        solution_name = futures[future]
                        try:
                            _record_validation(future.result(), solution_name)
                        except Exception as e:
                            logger.error(f"[Stage 6-KV] Keyword validation error for {solution_name}: {e}")

        # Store validation results in state
        self.state.keyword_validation_results = validation_results

        # ═══════════════════════════════════════════════════════════════════════
        # BATCHED DIFFICULTY ENRICHMENT (Phase 3 & 4)
        # Fetch keyword difficulty for ALL validated keywords in a single API call
        # and recalculate keyword_demand_score with difficulty-adjusted formula
        # ═══════════════════════════════════════════════════════════════════════

        def _has_difficulty_data(results: list) -> bool:
            """Check if any validated keyword already has difficulty data (from resume)."""
            for validation in results:
                if validation.validated_keywords:
                    for kw in validation.validated_keywords:
                        if kw.get('keyword_difficulty') is not None:
                            return True
            return False

        # _calculate_difficulty_adjusted_score is a module-level helper (unit-testable).

        # Check if difficulty data already present (resume case)
        if _has_difficulty_data(validation_results):
            logger.info("[Stage 6-KV] Difficulty data already present from checkpoint - skipping API call")
        elif validation_results:
            # Collect all unique validated keywords across all solutions
            all_validated_keywords: list[dict] = []
            for validation in validation_results:
                if validation.validated_keywords:
                    all_validated_keywords.extend(validation.validated_keywords)

            # Dedupe and get unique keyword strings
            unique_keywords = list({
                kw.get('keyword', '').lower().strip()
                for kw in all_validated_keywords
                if kw.get('keyword')
            })

            if unique_keywords:
                logger.info(
                    f"[Stage 6-KV] Fetching difficulty for {len(unique_keywords)} unique keywords (batched)"
                )
                try:
                    difficulty_map = self.dataforseo_tool.get_keyword_difficulty(
                        keywords=unique_keywords[:1000],  # Cap at 1000 for cost control
                        location_code=settings.target_location
                    )

                    # Backfill difficulty into all validation results
                    enriched_count = 0
                    for validation in validation_results:
                        if validation.validated_keywords:
                            for kw in validation.validated_keywords:
                                kw_lower = kw.get('keyword', '').lower().strip()
                                if kw_lower in difficulty_map:
                                    kw['keyword_difficulty'] = difficulty_map[kw_lower]
                                    enriched_count += 1

                    logger.info(
                        f"[Stage 6-KV] Enriched {enriched_count} keyword entries with difficulty scores "
                        f"({len(difficulty_map)} unique difficulties fetched)"
                    )

                    # Recalculate keyword_demand_score with difficulty for each validation
                    for validation in validation_results:
                        old_score = validation.keyword_demand_score
                        new_score, avg_diff, rank_factor = _calculate_difficulty_adjusted_score(validation)

                        if new_score is None:
                            # Graded-and-empty (correction 1): no validated keywords —
                            # demand is unmeasured. Keep the model's scalar untouched
                            # (keyword_demand_score is a required float; writing None
                            # would poison the checkpoint round-trip). The None-demand
                            # handling lives at the scoring loop below, keyed off the
                            # empty validated set so resume/API-failure paths get it too.
                            logger.info(
                                f"[Stage 6-KV] {validation.solution_name}: empty validated "
                                "set — demand unmeasured, difficulty recalc skipped"
                            )
                            continue

                        # Update validation object (CrewKeywordValidationResult)
                        # Need to mutate the object since it's a Pydantic model
                        object.__setattr__(validation, 'keyword_demand_score', new_score)
                        object.__setattr__(validation, 'avg_keyword_difficulty', avg_diff)
                        object.__setattr__(validation, 'rankability_factor', rank_factor)

                        if avg_diff is not None:
                            logger.info(
                                f"[Stage 6-KV] {validation.solution_name}: "
                                f"difficulty={avg_diff:.1f}, rankability={rank_factor:.2f}, "
                                f"demand_score={old_score:.3f}→{new_score:.3f}"
                            )

                    # Save checkpoint after difficulty enrichment
                    self.checkpoint_mgr.save_stage(
                        "stage_6_keyword_validation",
                        [v.model_dump() for v in validation_results]
                    )
                    logger.info("[Stage 6-KV] Checkpoint saved: difficulty enrichment complete")

                except Exception as e:
                    logger.warning(
                        f"[Stage 6-KV] Difficulty fetch failed: {e}. "
                        "Proceeding without difficulty-adjusted scoring."
                    )
            else:
                logger.info("[Stage 6-KV] No keywords to fetch difficulty for - skipping")

        # Update state with enriched validation results
        self.state.keyword_validation_results = validation_results

        # Track validated solution names
        validated_names = set(v.solution_name for v in validation_results)

        # Mark non-validated solutions (preserve original scores for reference)
        # Instead of nullifying, we keep scores but mark validation status
        for solution_score in all_scores:
            if solution_score.solution_name not in validated_names:
                # Preserve existing scores but add metadata field
                # NOTE: We don't nullify keyword_demand_score/adjusted_composite_score
                # This allows alternative solutions to retain their data for comparison
                logger.debug(
                    f"[Stage 6-KV] {solution_score.solution_name} not in top-3 validation set - "
                    f"preserving existing scores (composite: {solution_score.composite_score:.2f})"
                )
                # If the solution had no keyword scores, set to base composite score
                if solution_score.adjusted_composite_score is None:
                    solution_score.adjusted_composite_score = solution_score.composite_score

        # Re-score solutions using keyword demand
        logger.info("[Stage 6-KV] Re-scoring solutions with keyword demand data")
        from nicheiq.utils.score_helpers import (
            blend_adjusted_composite,
            choose_auto_pick,
            demand_with_beachhead_magnitude,
            rerank_solutions_by_adjusted_score,
        )

        for validation in validation_results:
            # Find corresponding solution score
            for solution_score in all_scores:
                if solution_score.solution_name == validation.solution_name:
                    if not validation.validated_keywords:
                        # Graded-and-empty (flow-weakness fix plan 2026-08, correction 1):
                        # the keywords were graded and NONE individually passed — demand is
                        # UNMEASURED, not the stale pre-grading scalar. No fabricated demand,
                        # no blend (adjusted = composite); rerank_solutions_by_adjusted_score
                        # two-tiers these below validated-with-keywords solutions. Keyed off
                        # the validated set itself so all three difficulty paths (normal /
                        # resume-skip / API-failure) land here uniformly.
                        solution_score.keyword_demand_score = None
                        solution_score.demand_unmeasured = True
                        solution_score.adjusted_composite_score = solution_score.composite_score
                        logger.info(
                            f"[Stage 6-KV] {solution_score.solution_name}: graded-and-empty "
                            f"validated set — demand unmeasured, adjusted = composite "
                            f"({solution_score.composite_score:.2f})"
                        )
                        break
                    # Reset-then-stamp: a measured solution must never carry a stale
                    # demand_unmeasured=True from an earlier pass/checkpoint.
                    solution_score.demand_unmeasured = False
                    # P3b (A/B-validated 2026-07-01, always on): fold beachhead MAGNITUDE into the
                    # ratio-based demand so a thin-but-clean beachhead can't out-rank a truly higher-demand
                    # idea (live: MountLimit demand 0.98 on a 720/mo beachhead → selection A/B picked the
                    # genuinely-better NINA once its real beachhead was reflected).
                    demand = demand_with_beachhead_magnitude(
                        validation.keyword_demand_score,
                        getattr(validation, "niche_relevant_volume", None),
                        getattr(validation, "total_volume", 0),
                    )
                    if demand != validation.keyword_demand_score:
                        logger.info(
                            f"[Stage 6-KV][P3b] {solution_score.solution_name}: demand "
                            f"{validation.keyword_demand_score:.2f} -> {demand:.2f} "
                            f"(niche_relevant_volume={getattr(validation, 'niche_relevant_volume', None)})"
                        )
                    # Store keyword demand score
                    solution_score.keyword_demand_score = demand

                    # Adjusted composite: bounded 0.7/0.3 blend, NOT multiplication
                    # (see blend_adjusted_composite for rationale)
                    base_score = solution_score.composite_score
                    solution_score.adjusted_composite_score = blend_adjusted_composite(
                        base_score, demand
                    )

                    logger.info(
                        f"[Stage 6-KV] {solution_score.solution_name}: "
                        f"base={base_score:.2f}, keyword_demand={demand:.2f}, "
                        f"adjusted={solution_score.adjusted_composite_score:.2f}"
                    )
                    break

        # Re-rank validated solutions (novelty tiebreaker + stale-rank rewrite
        # included — see rerank_solutions_by_adjusted_score)
        ranked_solutions = rerank_solutions_by_adjusted_score(all_scores, validated_names)

        if ranked_solutions:
            # Auto-pick guard: the keyword rerank is a second automatic #1 derivation, so a
            # red-team-killed idea must not win it either. `choose_auto_pick` keeps the
            # ranked list (and the killed idea's rank) untouched — it only walks past
            # ineligible leaders and returns an attributable note.
            ideas_pool = (self.state.idea_generation.solution_ideas
                          if self.state.idea_generation else None) or []
            winner_score, withheld_note = choose_auto_pick(ranked_solutions, ideas_pool)
            new_winner = winner_score.solution_name
            original_winner = self.state.solution_selection.selected_solution_name

            if new_winner != original_winner:
                self._apply_keyword_pivot(
                    ranked_solutions, all_scores, validation_results, validated_names,
                    winner_score=winner_score, withheld_note=withheld_note,
                )
            else:
                logger.info(f"[Stage 6-KV] Winner confirmed by keyword validation: {new_winner}")
                if withheld_note:
                    self.state.solution_selection.selection_rationale = (
                        f"{self.state.solution_selection.selection_rationale or ''}"
                        f"\n\n{withheld_note}".strip()
                    )
                    logger.warning(f"[Stage 6-KV] Auto-pick guard: {withheld_note}")

        # Save keyword validation results (stage completion handled by stage_6_seo_strategy)
        self.checkpoint_mgr.save_stage("stage_6_keyword_validation", validation_results)

        # FIX: Also save modified solution_selection to checkpoint (mutations happened above)
        # This ensures winner changes and rationale updates survive resume
        if self.state.solution_selection:
            self.checkpoint_mgr.save_stage(
                "stage_5_6_selection",
                self.state.solution_selection.model_dump()
            )
            logger.debug("[Stage 6-KV] Updated solution_selection checkpoint after keyword re-ranking")

        logger.info(f"[Stage 6-KV] Keyword validation complete - {len(validation_results)} solutions validated")

    def _apply_keyword_pivot(
        self, ranked_solutions, all_scores, validation_results, validated_names,
        winner_score=None, withheld_note: str | None = None,
    ) -> None:
        """Winner change after keyword validation (extracted from
        `_run_integrated_keyword_validation` — run-quality fixes §3, 2026-07-30, so the
        guard and rationale are testable against the real code instead of a drifting
        test replica).

        USER-SELECTION GUARD: when the current winner was explicitly picked by a human
        (interactive flow / catalog seed — `state._user_selected_solutions`, stamped in
        worker/tasks.py for exactly this purpose), the pivot must NOT silently override
        it: an advisory note is appended and the keyword favorite becomes the lead
        runner-up. NOTE: `score_source == 'interactive'` is NOT the discriminator — the
        headless per-cell tournament stamps it too (`_build_headless_selection`), and
        headless runs must keep pivoting.

        Rationale honesty: `build_pivot_rationale` computes the actual composite-vs-
        demand attribution instead of the old unconditional "overtaken due to weaker
        keyword demand evidence" claim (false whenever the composite term or the novelty
        tiebreak drove the flip).

        `winner_score` is the auto-pick-eligible leader (`choose_auto_pick`), which is
        `ranked_solutions[0]` unless the rerank leader was red-team killed; `withheld_note`
        carries the citable reason and is appended so the flip is never misattributed to
        keyword demand. Defaults preserve the plain rerank-leader behaviour for callers that
        pass neither."""
        from ..utils.score_helpers import build_keyword_advisory_note, build_pivot_rationale

        new_winner_score = winner_score if winner_score is not None else ranked_solutions[0]
        new_winner = new_winner_score.solution_name
        original_winner = self.state.solution_selection.selected_solution_name
        original_winner_score = next(
            (s for s in all_scores if s.solution_name == original_winner), None
        )
        new_winner_validation = next(
            (v for v in validation_results if v.solution_name == new_winner), None
        )

        user_selected = getattr(self.state, "_user_selected_solutions", None) or set()
        if original_winner in user_selected:
            new_adj = new_winner_score.adjusted_composite_score or 0.0
            orig_adj = (
                original_winner_score.adjusted_composite_score
                if original_winner_score else None
            ) or 0.0
            advisory = build_keyword_advisory_note(new_winner, new_adj, orig_adj)
            rationale = self.state.solution_selection.selection_rationale or ""
            self.state.solution_selection.selection_rationale = (
                f"{rationale}\n\n{advisory}".strip()
            )
            runner_ups = list(self.state.solution_selection.runner_up_solutions or [])
            if new_winner not in runner_ups:
                runner_ups.insert(0, new_winner)
            self.state.solution_selection.runner_up_solutions = runner_ups
            logger.info(
                f"[Stage 6-KV] Keyword validation favors '{new_winner}' but "
                f"'{original_winner}' is user-selected — keeping the user's pick, "
                "advisory appended"
            )
            return

        logger.warning(
            f"[Stage 6-KV] Winner changed after keyword validation: "
            f"{original_winner} → {new_winner}"
        )
        self.state.solution_selection.selected_solution_name = new_winner

        new_winner_solution = find_solution_by_name(
            new_winner, self.state.idea_generation.solution_ideas
        )

        # Preserve the strategic selector's original rationale before
        # mutating — the pivot APPENDS keyword evidence, never replaces
        # the original multi-criteria reasoning.
        original_rationale = self.state.solution_selection.selection_rationale
        self.state.solution_selection.original_selection_reasoning = original_rationale

        # Lead with the NEW winner's keyword-driven rationale — do NOT prepend the
        # dethroned solution's text (it would surface as a contradictory rationale in the
        # report). The original reasoning is preserved verbatim in original_selection_reasoning.
        self.state.solution_selection.selection_rationale = build_pivot_rationale(
            new_winner_score,
            original_winner_score,
            new_winner_validation,
            orig_name=original_winner,
            orig_validated=original_winner in (validated_names or set()),
        )
        if withheld_note:
            # Honest attribution: the flip was (also) the auto-pick guard walking past a
            # red-team-killed leader, not purely keyword demand.
            self.state.solution_selection.selection_rationale = (
                f"{self.state.solution_selection.selection_rationale}\n\n{withheld_note}"
            )
            logger.warning(f"[Stage 6-KV] Auto-pick guard: {withheld_note}")

        # Refresh selection_criteria_scores to describe the NEW winner
        # (they previously kept describing the dethroned original).
        from ..models.solution_selection import SelectionCriteriaScore
        pivot_note = "Carried from Stage 5 scoring after keyword-validation pivot"
        self.state.solution_selection.selection_criteria_scores = [
            SelectionCriteriaScore(criterion=criterion, score=score, justification=pivot_note)
            for criterion, score in [
                ("market_fit", new_winner_score.market_fit_score),
                ("technical_feasibility", new_winner_score.technical_feasibility_score),
                ("competitive_advantage", new_winner_score.competitive_advantage_score),
                ("seo_growth_potential", new_winner_score.seo_growth_potential_score),
            ]
            if score is not None
        ]

        # Update recommended_focus
        if new_winner_solution:
            self.state.solution_selection.recommended_focus = (
                self._build_recommended_focus(
                    solution=new_winner_solution,
                    keyword_validation=new_winner_validation,
                )
            )
        else:
            logger.warning(
                f"[Stage 6-KV] Could not find solution '{new_winner}' in idea_generation - "
                f"recommended_focus not updated"
            )

        # Update runner_up_solutions to reflect new ranking after pivot
        new_runner_ups = []
        for score in ranked_solutions:  # rank order, minus the new winner itself
            if score.solution_name == new_winner:
                continue
            if score.solution_name not in new_runner_ups:
                new_runner_ups.append(score.solution_name)
            if len(new_runner_ups) >= 3:  # Keep top 3 runner-ups
                break

        # Add original winner if not already in list (it should be a runner-up now)
        if original_winner not in new_runner_ups:
            new_runner_ups.insert(0, original_winner)
            if len(new_runner_ups) > 3:
                new_runner_ups = new_runner_ups[:3]

        # Preserve user-selected solutions in runner_up_solutions (interactive mode)
        if user_selected:
            new_winner = self.state.solution_selection.selected_solution_name
            for name in user_selected:
                if name != new_winner and name not in new_runner_ups:
                    new_runner_ups.append(name)

        self.state.solution_selection.runner_up_solutions = new_runner_ups
        logger.info(f"[Stage 6-KV] Updated runner-ups after pivot: {new_runner_ups}")

    def _build_recommended_focus(
        self,
        solution: "BaseSolutionIdea",
        keyword_validation: "CrewKeywordValidationResult | None" = None,
    ) -> str:
        """Build a recommended_focus string from solution data (no LLM call).

        Constructs 1-4 sentences depending on available data:
        - Sentence 1 (always): Core focus from solution name, project_type, value_proposition
        - Sentence 2 (if features): MVP priorities from core_features[:3]
        - Sentence 3 (if keyword_validation): Demand signal, volume, top keywords or geographic opportunities
        - Sentence 4 (if pain points): Primary pain point anchor for messaging
        """
        sentences = []

        # Sentence 1: Core focus (always present)
        project_type = solution.project_type or "SaaS tool"
        sentences.append(
            f"Focus on building {solution.solution_name} as a {project_type} "
            f"that delivers: {solution.value_proposition}."
        )

        # Sentence 2: MVP feature priorities
        features = [f for f in (solution.core_features or []) if f and f.strip()]
        if features:
            if len(features) == 1:
                sentences.append(f"Prioritize the core feature: {features[0]}.")
            else:
                top_features = features[:3]
                sentences.append(
                    f"Prioritize MVP features: {', '.join(top_features)}."
                )

        # Sentence 3: Keyword demand evidence
        if keyword_validation is not None:
            top_kw = keyword_validation.top_keywords or []
            geo_kw = keyword_validation.top_geographic_keywords or []
            kw_names = [k.get("keyword", "") for k in top_kw[:3] if k.get("keyword")]

            if kw_names or geo_kw:
                parts = []
                if kw_names:
                    parts.append(f"top keywords: {', '.join(kw_names)}")
                if geo_kw:
                    parts.append(f"geographic opportunities: {', '.join(geo_kw[:2])}")
                sentences.append(
                    f"Keyword validation shows {keyword_validation.demand_signal} demand "
                    f"({keyword_validation.total_volume:,} monthly searches) with "
                    f"{'; '.join(parts)}."
                )
            else:
                sentences.append(
                    f"Keyword validation shows {keyword_validation.demand_signal} demand "
                    f"with {keyword_validation.total_volume:,} monthly searches."
                )

        # Sentence 4: Pain point anchor
        pain_points = [p for p in (solution.pain_points_addressed or []) if p and p.strip()]
        if pain_points:
            sentences.append(
                f"Anchor messaging around the primary pain point: {pain_points[0]}."
            )

        return " ".join(sentences)

    def _derive_keyword_context_from_seo(self, seo_report) -> dict:
        """Derive keyword context from SEO strategy report for stages 8-11.

        Extracts keyword-validation-equivalent fields from the comprehensive
        SEO strategy report so downstream crews can use richer data.
        """
        import math
        import re

        all_keywords = []
        for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
            tier_kws = getattr(seo_report, tier_attr, None) or []
            all_keywords.extend(tier_kws)

        # Geo keywords: extract actual keyword strings from tier 3 groups
        geo_keywords = []
        for group in (getattr(seo_report, 'tier_3_geographic_groups', None) or []):
            for entry in (getattr(group, 'keywords', None) or []):
                kw_str = getattr(entry, 'keyword', None) or getattr(entry, 'term', None)
                if kw_str:
                    geo_keywords.append(kw_str)
        # Fallback: use region names if no keyword entries
        if not geo_keywords:
            for group in (getattr(seo_report, 'tier_3_geographic_groups', None) or []):
                geo_keywords.append(group.region_name)

        # Top keywords sorted by volume
        top_keywords = sorted(all_keywords, key=lambda k: k.search_volume, reverse=True)[:15]
        top_kw_dicts = [{"keyword": k.keyword, "volume": k.search_volume} for k in top_keywords]

        # Avg competition: parse number from "LOW (30)" format, fallback to keyword_difficulty
        competitions = []
        for k in all_keywords:
            comp = getattr(k, 'competition', None)
            if comp and isinstance(comp, str):
                match = re.search(r'\((\d+)\)', comp)
                if match:
                    competitions.append(int(match.group(1)))
                    continue
            kd = getattr(k, 'keyword_difficulty', None)
            if kd is not None:
                competitions.append(int(kd))
        avg_competition = sum(competitions) / len(competitions) if competitions else 50.0

        total_volume = seo_report.total_monthly_volume or 0
        keyword_count = seo_report.total_keywords_analyzed or 0

        # Demand signal based on total volume
        if total_volume >= 5000:
            demand_signal = "strong"
        elif total_volume >= 2000:
            demand_signal = "moderate"
        else:
            demand_signal = "weak"

        # keyword_demand_score: logarithmic scale to avoid always being 1.0
        if total_volume > 0:
            keyword_demand_score = min(math.log10(total_volume) / 6.0, 1.0)  # 1M = 1.0
        else:
            keyword_demand_score = 0.0

        # Derive validation_signals equivalent from SEO data
        validation_signals = {
            "has_search_demand": total_volume > 1000,
            "keyword_diversity": keyword_count >= 5,
            "high_volume_presence": any(k.search_volume > 500 for k in all_keywords) if all_keywords else False,
            "average_volume_per_keyword": total_volume / keyword_count if keyword_count > 0 else 0,
        }

        return {
            "total_volume": total_volume,
            "keyword_count": keyword_count,
            "demand_signal": demand_signal,
            "avg_competition": avg_competition,
            "top_keywords": top_kw_dicts,
            "geo_keywords": geo_keywords,
            "keyword_demand_score": keyword_demand_score,
            "validation_signals": validation_signals,
        }

    def _analyze_traffic_monetization(self, solution_name: str) -> dict:
        """
        Helper method to analyze traffic monetization for a single solution (thread-safe).

        Creates a new TrafficMonetizationCrew instance per call for thread safety.

        Args:
            solution_name: Name of the solution to analyze

        Returns:
            Dict with 'solution_name', 'result' (TrafficMonetizationResult), and 'usage_metrics'
        """
        logger.info(f"[Parallel] Starting traffic monetization for: {solution_name}")

        # Find full solution object
        solution = find_solution_by_name(
            solution_name,
            self.state.idea_generation.solution_ideas
        )

        if not solution:
            logger.warning(f"[Parallel] Solution '{solution_name}' not found in idea generation")
            return {
                "solution_name": solution_name,
                "result": None,
                "usage_metrics": None
            }

        # Create new TrafficMonetizationCrew instance for thread safety
        traffic_crew = TrafficMonetizationCrew()

        try:
            # Run traffic monetization analysis
            result = traffic_crew.analyze(
                selected_solution=solution,
                keyword_validation_results=None,
                competitive_analysis=self.state.competitive_analysis,
                niche_description=self.niche_description,
                seo_strategy_report=self.state.seo_strategy_report
            )

            if result:
                logger.info(f"[Parallel] Traffic monetization complete for {solution_name}: {result.monetization_model}")
            else:
                logger.warning(f"[Parallel] Traffic monetization failed for {solution_name}")

            return {
                "solution_name": solution_name,
                "result": result,
                "usage_metrics": traffic_crew.usage_metrics
            }

        except Exception as e:
            logger.error(f"[Parallel] Error analyzing {solution_name}: {str(e)}")
            return {
                "solution_name": solution_name,
                "result": None,
                "usage_metrics": None
            }

    def stage_8_traffic_monetization(self):
        """
        Stage 8: Traffic Monetization Analysis (Parallel)

        For traffic-based project types (directory, aggregator, comparison-tool),
        provides traffic monetization strategy instead of SaaS pricing.
        Runs in parallel for ~50% time savings.

        Uses keyword validation data to estimate:
        - Traffic potential (monthly pageviews)
        - Ad revenue (CPM by niche)
        - Affiliate revenue opportunities
        - Sponsored listing potential
        """
        logger.info("=" * 80)
        logger.info("STAGE 8: Traffic Monetization Analysis (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(8, "Traffic Monetization", "running")

        # Traffic-based project types that use this crew
        traffic_types = ['directory', 'aggregator', 'comparison-tool']

        # Check prerequisites
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 8] No solution ideas - skipping traffic monetization")
            self.state.current_stage = 9
            self._skip_stage(8, "Traffic Monetization", "No solution ideas for traffic analysis")
            return

        if not self.state.seo_strategy_report:
            logger.warning("[Stage 8] No SEO strategy report - skipping traffic monetization")
            self.state.current_stage = 9
            self._skip_stage(8, "Traffic Monetization", "No SEO data for traffic estimation")
            return

        # Get solutions to analyze (same top N as keyword validation)
        if not self.state.solution_selection or not self.state.solution_selection.all_solution_scores:
            logger.warning("[Stage 8] No solution scores - skipping traffic monetization")
            self.state.current_stage = 9
            self._skip_stage(8, "Traffic Monetization", "No solution scores for traffic analysis")
            return

        all_scores = self.state.solution_selection.all_solution_scores
        top_n_scores = sorted(
            all_scores,
            key=lambda s: s.composite_score,
            reverse=True
        )[:settings.top_solutions_for_validation]
        top_n_scores = self._ensure_selected_in_topn(top_n_scores, all_scores)

        # Filter to traffic-based solutions only
        traffic_solutions = []
        for score in top_n_scores:
            solution = find_solution_by_name(
                score.solution_name,
                self.state.idea_generation.solution_ideas
            )
            if solution and solution.project_type in traffic_types:
                traffic_solutions.append((score, solution))
                logger.info(
                    f"[Stage 8] {solution.solution_name}: project_type='{solution.project_type}' "
                    f"→ Traffic monetization eligible"
                )

        if not traffic_solutions:
            logger.info(
                f"[Stage 8] No traffic-based solutions found in top {len(top_n_scores)} "
                f"(types: {traffic_types}). Skipping traffic monetization analysis."
            )
            self.state.current_stage = 9
            self._skip_stage(8, "Traffic Monetization", "Not applicable \u2014 SaaS revenue model")
            return

        logger.info(f"[Stage 8] Analyzing {len(traffic_solutions)} traffic-based solutions (PARALLEL)")

        # Initialize results list (support resume)
        traffic_results = []
        already_analyzed = set()
        if self.state.traffic_monetization_results:
            traffic_results = list(self.state.traffic_monetization_results)
            already_analyzed = {r.solution_name for r in traffic_results}
            logger.info(f"[Stage 8] Resuming - {len(already_analyzed)} solutions already analyzed")

        # Filter solutions that need analysis
        solutions_to_analyze = [
            solution.solution_name
            for score, solution in traffic_solutions
            if solution.solution_name not in already_analyzed
        ]

        if not solutions_to_analyze:
            logger.info("[Stage 8] All solutions already analyzed - skipping")
            self.checkpoint_mgr.save_stage(
                "stage_8_traffic_monetization",
                [r.model_dump() for r in traffic_results]
            )
            self._mark_stage_complete(8)
            return

        logger.info(f"[Stage 8] Analyzing {len(solutions_to_analyze)} solutions in parallel (max_workers=2)")

        # Run traffic monetization in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all traffic monetization tasks
            futures = {
                executor.submit(self._analyze_traffic_monetization, solution_name): solution_name
                for solution_name in solutions_to_analyze
            }

            # Collect results as they complete
            for future in as_completed(futures):
                solution_name = futures[future]
                try:
                    result_dict = future.result()
                    result = result_dict["result"]
                    usage_metrics = result_dict["usage_metrics"]

                    # Record crew cost
                    if usage_metrics:
                        self.cost_tracker.record_crew_usage(
                            stage=f"Stage 8 - Traffic Monetization ({solution_name})",
                            usage_metrics=usage_metrics,
                            model=settings.openai_model_name
                        )

                    if result:
                        traffic_results.append(result)
                        logger.info(
                            f"[Stage 8] Traffic monetization complete: {solution_name} "
                            f"({result.monetization_model}, {result.estimated_monthly_revenue_range})"
                        )

                        # Incremental checkpoint (thread-safe: append only)
                        self.state.traffic_monetization_results = traffic_results
                        self.checkpoint_mgr.save_stage(
                            "stage_8_traffic_monetization_partial",
                            [r.model_dump() for r in traffic_results]
                        )
                    else:
                        logger.warning(f"[Stage 8] Traffic monetization failed: {solution_name}")

                except Exception as e:
                    logger.error(f"[Stage 8] Traffic monetization error for {solution_name}: {e}")

        # Store final results
        self.state.traffic_monetization_results = traffic_results

        # Mark stage complete with tracking
        self._mark_stage_complete(8)

        # Save checkpoint
        if traffic_results:
            self.checkpoint_mgr.save_stage(
                "stage_8_traffic_monetization",
                [r.model_dump() for r in traffic_results]
            )

        logger.info(
            f"[Stage 8] Traffic Monetization Analysis Complete - "
            f"{len(traffic_results)}/{len(traffic_solutions)} solutions analyzed (PARALLEL)"
        )

    def stage_9_market_sizing(self):
        """
        Stage 9: Market Sizing & Validation

        Calculates TAM/SAM/SOM estimates and validates market attractiveness using:
        - Keyword search volumes (demand signals from keyword validation)
        - Pain point frequency (problem validation)
        - Competitive landscape (market saturation)
        - Selected solution positioning
        """
        logger.info("=" * 80)
        logger.info("STAGE 9: Market Sizing & Validation")
        logger.info("=" * 80)
        self._emit_progress(9, "Market Sizing", "running")

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 9] No solution selected - skipping market sizing")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "No solution selected for market sizing")
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 9] No pain point analysis - skipping market sizing")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "Insufficient data for market estimation")
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 9] No competitive analysis - skipping market sizing")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "No competitive data for market sizing")
            return

        # Check if we have idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 9] No solution ideas - skipping market sizing")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "No solution ideas for market sizing")
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 9] Selected solution '{selected_name}' not found")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "Selected solution not found")
            return

        # Initialize and run market sizing crew
        from ..crews import MarketSizingCrew

        logger.info(f"[Stage 9] Calculating TAM/SAM/SOM for: {selected_name}")

        market_sizing_crew = MarketSizingCrew()

        # Beachhead anchor: pass the SELECTED solution's own validated keyword set (the slice it serves)
        # so SAM/SOM anchor on its demand, with the SEO report kept as the follow-on reach ceiling (TAM).
        # Falls back to None (SEO-only) when validation is missing.
        selected_kv = next(
            (v for v in self.state.keyword_validation_results
             if v.solution_name == selected_name), None
        ) if self.state.keyword_validation_results else None
        # Pricing anchor (rec #3): ground the per-customer value on the Stage-7 pricing analysis (real
        # ARPU/LTV) rather than letting the LLM invent a number.
        selected_pricing = next(
            (p for p in self.state.pricing_strategies
             if p.solution_name == selected_name), None
        ) if self.state.pricing_strategies else None
        logger.info(
            f"[Stage 9] Demand anchor: {'solution keyword validation' if selected_kv else 'SEO report (no per-solution validation)'}; "
            f"pricing anchor: {'present' if selected_pricing else 'none (derive value from WTP)'}"
        )

        # Market-data handoff (utils/market_brief.py): same Phase-1 web-verified facts the
        # competitor/pricing/SEO crews receive.
        from ..utils.market_brief import build_market_brief
        _market_vars = build_market_brief(self.state, selected_solution)

        market_sizing_result = market_sizing_crew.analyze(
            selected_solution=selected_solution,
            keyword_validation=selected_kv,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description,
            seo_strategy_report=self.state.seo_strategy_report,
            pricing_strategy=selected_pricing,
            **_market_vars,
        )

        # Record crew cost
        if market_sizing_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 9 - Market Sizing",
                usage_metrics=market_sizing_crew.usage_metrics,
                model=settings.openai_model_name
            )

        # Check if analysis succeeded
        if not market_sizing_result:
            logger.warning("[Stage 9] Market sizing failed - continuing without market sizing data")
            self.state.current_stage = 10
            self._skip_stage(9, "Market Sizing", "Market sizing could not be completed")
            return

        # Store result
        self.state.market_sizing = market_sizing_result
        self.state.current_stage = 10

        # Mark stage complete with tracking
        self._mark_stage_complete(9)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_9_market_sizing", market_sizing_result)

        logger.info("[Stage 9] Market Sizing Complete")
        logger.info(f"  TAM: {market_sizing_result.total_addressable_market}")
        logger.info(f"  SAM: {market_sizing_result.serviceable_available_market}")
        logger.info(f"  SOM (Y1): {market_sizing_result.serviceable_obtainable_market_y1}")
        logger.info(f"  SOM (Y3): {market_sizing_result.serviceable_obtainable_market_y3}")
        logger.info(f"  Viability: {market_sizing_result.market_viability_verdict}")
        logger.info(f"  Entry Strategy: {market_sizing_result.recommended_entry_strategy}")

    def stage_10_solution_refinement(self):
        """
        Stage 10: Solution Refinement Using Keyword Insights

        Generates strategic recommendations for selected solution based on keyword validation:
        - Geographic market priorities
        - Category/positioning pivots
        - Feature prioritization
        - Content strategy direction
        """
        logger.info("=" * 80)
        logger.info("STAGE 10: Solution Refinement")
        logger.info("=" * 80)
        self._emit_progress(10, "Solution Refinement", "running")

        # Check if feature is enabled
        if not getattr(settings, 'solution_refinement_enabled', True):
            logger.info("[Stage 10] Solution refinement disabled - skipping")
            self.state.current_stage = 11
            self._skip_stage(10, "Solution Refinement", "Solution refinement disabled")
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 10] No solution selected - skipping refinement")
            self.state.current_stage = 11
            self._skip_stage(10, "Solution Refinement", "No solution selected for refinement")
            return

        # Check if we have SEO strategy report
        if not self.state.seo_strategy_report:
            logger.warning("[Stage 10] No SEO strategy report - skipping refinement")
            self.state.current_stage = 11
            self._skip_stage(10, "Solution Refinement", "No SEO data for refinement")
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 10] Selected solution '{selected_name}' not found")
            self.state.current_stage = 11
            self._skip_stage(10, "Solution Refinement", "Selected solution not found")
            return

        # Early exit if SEO demand is too weak
        seo_total_volume = self.state.seo_strategy_report.total_monthly_volume or 0
        if seo_total_volume < 2000:
            logger.warning(
                f"[Stage 10] Skipping refinement - weak SEO demand signal "
                f"({seo_total_volume} monthly volume)"
            )
            self.state.current_stage = 11
            self.checkpoint_mgr.save_stage("stage_10_solution_refinement", {"skipped": True, "reason": "weak_demand"})
            self._skip_stage(10, "Solution Refinement", "Low search demand \u2014 refinement skipped")
            return

        # Get composite score for context
        composite_score = next(
            (s.composite_score for s in self.state.solution_selection.all_solution_scores
             if s.solution_name == selected_name),
            0.0
        )

        # Initialize and run refinement crew
        logger.info(f"[Stage 10] Refining strategy for: {selected_name}")
        refinement_crew = SolutionRefinementCrew()

        refinement = refinement_crew.refine(
            selected_solution=selected_solution,
            seo_strategy_report=self.state.seo_strategy_report,
            composite_score=composite_score,
            allowed_project_types=self.state.allowed_project_types
        )

        # Record crew cost
        if refinement_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 10 - Solution Refinement",
                usage_metrics=refinement_crew.usage_metrics,
                model=settings.openai_model_name
            )

        if refinement:
            # Store refinement in state
            self.state.solution_refinement = refinement

            # Phase 2.3: Merge refinements inline to selected solution (prevents data loss)
            # This ensures downstream stages (SEO, Report) have access to strategic refinements
            # without needing to query solution_refinement separately
            if selected_solution:
                # Find index of selected solution in idea_generation
                for idx, idea in enumerate(self.state.idea_generation.solution_ideas):
                    if idea.solution_name == selected_name:
                        # Merge available refinement fields into solution
                        # Note: We add refinement data as new fields, not replacing existing ones
                        if hasattr(idea, 'geographic_priorities') or hasattr(idea, '__dict__'):
                            # Store refinement metadata in solution's extra fields if model allows
                            # Or add to strategic_notes if available
                            if hasattr(idea, 'strategic_notes') and idea.strategic_notes is not None:
                                idea.strategic_notes = (
                                    f"{idea.strategic_notes}\n\n"
                                    f"**Stage 10 Refinements:**\n"
                                    f"- Geographic priorities: {', '.join(refinement.geographic_priorities[:3])}\n"
                                    f"- Category pivot: {refinement.category_pivot_recommendation or 'None'}\n"
                                    f"- Key insight: {refinement.strategic_insights[0] if refinement.strategic_insights else 'N/A'}"
                                )
                            logger.info(f"[Stage 10] Merged refinements into solution '{selected_name}'")
                        break

            logger.info(
                f"[Stage 10] Refinement complete:\n"
                f"  - Geographic priorities: {', '.join(refinement.geographic_priorities[:3])}\n"
                f"  - Category pivot: {refinement.category_pivot_recommendation or 'None'}\n"
                f"  - Feature priorities: {len(refinement.feature_priorities)} recommendations\n"
                f"  - Strategic insights: {len(refinement.strategic_insights)} insights"
            )

            # Update stage first, then checkpoint (Pattern A - safer for resume)
            self.state.current_stage = 11

            # Mark stage complete with tracking
            self._mark_stage_complete(10)

            self.checkpoint_mgr.save_stage("stage_10_solution_refinement", refinement.model_dump())
        else:
            logger.warning("[Stage 10] Refinement failed - proceeding without refinement data")
            # Update stage first, then checkpoint (Pattern A - safer for resume)
            self.state.current_stage = 11

            # Mark stage complete with tracking (used fallback since refinement failed)
            self._skip_stage(10, "Solution Refinement", "Refinement failed")

            self.checkpoint_mgr.save_stage("stage_10_solution_refinement", {"skipped": True, "reason": "refinement_failed"})

    def stage_11_trend_longevity(self):
        """
        Stage 11: Trend Longevity & Market Momentum Analysis

        Analyzes keyword trends, discussion activity, and competitive momentum to assess:
        - Market timing (Growing, Stable, Declining)
        - Trend sustainability (Sustainable, Risky, Fad)
        - Optimal entry timing (Enter Now, Monitor & Wait, Missed Window)
        """
        logger.info("=" * 80)
        logger.info("STAGE 11: Trend Longevity & Market Momentum Analysis")
        logger.info("=" * 80)
        self._emit_progress(11, "Trend Analysis", "running")

        # Aggregate keyword trends from enriched keywords
        trend_summary = self._aggregate_keyword_trends()
        if trend_summary:
            logger.info(f"[Stage 11] Keyword trend summary: {trend_summary['trend_distribution']}")
            logger.info(f"[Stage 11] Market momentum: {trend_summary['market_momentum']}")
            logger.info(f"[Stage 11] Rising volume %: {trend_summary['rising_volume_pct']:.1f}%")

        # Check if we have required data - create fallback if missing
        def _create_minimal_trend_fallback(reason: str) -> "TrendLongevityResult":
            """Create minimal fallback trend result when full analysis cannot run."""
            from ..models.research_state import TrendLongevityResult
            logger.warning(f"[Stage 11] ⚠️ Creating minimal trend analysis due to: {reason}")
            return TrendLongevityResult(
                is_fallback=True,
                trend_direction="Stable",  # Conservative default (valid Literal)
                trend_confidence="Low",
                momentum_score=0.5,  # Neutral
                keyword_volume_trend="Stable",  # Conservative default (valid Literal)
                volume_growth_rate="Insufficient data",
                trend_duration="Unknown",
                discussion_frequency_trend="Stable",  # Conservative default (valid Literal)
                discussion_recency="Unknown",
                community_growth_indicators=["Trend analysis unavailable - insufficient data"],
                new_entrants_trend="Stable",  # Conservative default (valid Literal)
                competitive_activity_level="Low",  # Conservative default (valid Literal)
                seasonal_pattern="Unknown",
                peak_periods=None,
                market_maturity="Emerging",  # Conservative default (valid Literal)
                longevity_verdict="Risky",  # Conservative default (valid Literal)
                longevity_rationale=f"Trend analysis could not be completed: {reason}. Manual market research recommended.",
                trend_reversal_risks=["Data insufficient for trend analysis"],
                timing_recommendation="Monitor & Wait",
                data_sources_analyzed=["Limited - fallback mode"],
                analysis_timeframe="N/A"
            )

        if not self.state.seo_strategy_report:
            logger.warning("[Stage 11] No SEO strategy report - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("Missing SEO strategy data")
            self.state.current_stage = 12
            self._mark_stage_complete(11, used_fallback=True)
            self.checkpoint_mgr.save_stage("stage_11_trend_longevity", self.state.trend_longevity.model_dump())
            return

        if not self.state.social_content:
            logger.warning("[Stage 11] No social content - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("Missing social content data")
            self.state.current_stage = 12
            self._mark_stage_complete(11, used_fallback=True)
            self.checkpoint_mgr.save_stage("stage_11_trend_longevity", self.state.trend_longevity.model_dump())
            return

        # Get selected solution's keyword validation
        selected_name = self.state.solution_selection.selected_solution_name if self.state.solution_selection else None
        if not selected_name:
            logger.warning("[Stage 11] No solution selected - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("No solution selected")
            self.state.current_stage = 12
            self._mark_stage_complete(11, used_fallback=True)
            self.checkpoint_mgr.save_stage("stage_11_trend_longevity", self.state.trend_longevity.model_dump())
            return

        # Derive keyword context from SEO report for trend analysis
        seo_context = self._derive_keyword_context_from_seo(self.state.seo_strategy_report)

        # Initialize and run trend longevity crew
        from ..crews import TrendLongevityCrew

        logger.info(f"[Stage 11] Analyzing market trends for: {self.niche_description}")

        # Get top enriched keywords with monthly trend data for detailed analysis
        top_enriched_keywords = None
        if self.state.seo_enriched_keywords:
            # Pass top 20 keywords sorted by volume (with their monthly_searches)
            sorted_keywords = sorted(
                self.state.seo_enriched_keywords,
                key=lambda x: x.get('search_volume', 0),
                reverse=True
            )[:20]
            top_enriched_keywords = sorted_keywords
            logger.info(f"[Stage 11] Passing {len(top_enriched_keywords)} enriched keywords with monthly trends")

        trend_crew = TrendLongevityCrew()

        trend_result = trend_crew.analyze(
            keyword_validation=None,
            social_content=self.state.social_content,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description,
            enriched_keywords_trends=trend_summary,  # Aggregated 12-month trend summary
            top_enriched_keywords=top_enriched_keywords,  # Per-keyword monthly trend data
            selected_solution_name=selected_name,
            seo_strategy_report=self.state.seo_strategy_report,
        )

        # Record crew cost
        if trend_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 11 - Trend Longevity",
                usage_metrics=trend_crew.usage_metrics,
                model=settings.openai_model_name
            )

        # Check if analysis succeeded
        if not trend_result:
            logger.warning("[Stage 11] Trend analysis failed - continuing without trend data")
            self.state.current_stage = 12
            self._skip_stage(11, "Trend Analysis", "Trend analysis could not be completed")
            return

        # Store result
        self.state.trend_longevity = trend_result
        self.state.current_stage = 12

        # Mark stage complete with tracking (fallback if used minimal trend)
        used_fallback = trend_result.trend_direction == "Unknown"
        self._mark_stage_complete(11, used_fallback=used_fallback)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_11_trend_longevity", trend_result)

        logger.info("[Stage 11] Trend Longevity Analysis Complete")
        logger.info(f"  Trend Direction: {trend_result.trend_direction}")
        logger.info(f"  Momentum Score: {trend_result.momentum_score:.2f}")
        logger.info(f"  Longevity Verdict: {trend_result.longevity_verdict}")
        logger.info(f"  Market Maturity: {trend_result.market_maturity}")
        logger.info(f"  Timing Recommendation: {trend_result.timing_recommendation}")

    def stage_12_refine_seo_scores(self):
        """
        Stage 12: Refine SEO Scores Based on Actual Keyword Data

        Updates the selected solution's SEO metrics using real keyword data discovered
        in Stage 6. Provides market-validated adjustments to architectural estimates.

        Refinement includes:
        - seo_scalability_score: Adjusted for keyword volume, Tier 1 count, competition
        - estimated_cac_organic: Adjusted for keyword difficulty and market volume
        - programmatic_seo_opportunity: Enhanced with quantitative page count estimates

        Original estimates are preserved in base fields for comparison.
        """
        logger.info("=" * 80)
        logger.info("STAGE 12: Refine SEO Scores with Keyword Data")
        logger.info("=" * 80)
        self._emit_progress(12, "SEO Score Refinement", "running")

        # Check if refinement is enabled
        if not settings.seo_refinement_enabled:
            logger.info("SEO refinement disabled - skipping Stage 12")
            self.state.current_stage = 13
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": "SEO refinement disabled in settings"})
            self._skip_stage(12, "SEO Score Refinement", "SEO score refinement disabled")
            return

        # Skip if no SEO strategy or no solution selection
        if not self.state.seo_strategy_report or not self.state.solution_selection:
            logger.info("No SEO strategy or solution selection - skipping refinement")
            self.state.current_stage = 13
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": "No SEO strategy or solution selection"})
            self._skip_stage(12, "SEO Score Refinement", "No SEO strategy data for refinement")
            return

        # Skip if no idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.info("No solution ideas available - skipping refinement")
            self.state.current_stage = 13
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": "No solution ideas"})
            self._skip_stage(12, "SEO Score Refinement", "No solution ideas for SEO refinement")
            return

        # Get selected solution
        selected_solution_name = self.state.solution_selection.selected_solution_name
        selected_solution = next(
            (sol for sol in self.state.idea_generation.solution_ideas
             if sol.solution_name == selected_solution_name),
            None
        )

        if not selected_solution:
            logger.warning(f"Selected solution '{selected_solution_name}' not found - skipping refinement")
            self.state.current_stage = 13
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            self._skip_stage(12, "SEO Score Refinement", "Selected solution not found for refinement")
            return

        # Check if solution has SEO fields to refine
        if selected_solution.seo_scalability_score is None:
            logger.info("Solution has no SEO scores to refine - skipping")
            self.state.current_stage = 13
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": "Solution has no SEO scores to refine"})
            self._skip_stage(12, "SEO Score Refinement", "Solution has no SEO scores to refine")
            return

        logger.info(f"Refining SEO scores for: {selected_solution_name}")

        seo_report = self.state.seo_strategy_report

        # Extract keyword data
        total_monthly_volume = seo_report.total_monthly_volume
        tier1_keywords = seo_report.tier_1_keywords if seo_report.tier_1_keywords else []
        tier1_count = len(tier1_keywords)

        # Collect ALL tiered keywords for competition calculation
        all_tiered_keywords = []
        for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
            tier_kws = getattr(seo_report, tier_attr, None) or []
            all_tiered_keywords.extend(tier_kws)
        total_keyword_count = getattr(seo_report, 'total_keywords_analyzed', 0) or 0

        logger.info(
            f"  Keyword data: {total_monthly_volume:,} monthly volume, "
            f"{tier1_count} Tier 1 keywords, {len(all_tiered_keywords)} total tiered keywords"
        )

        try:
            # 1. REFINE SEO SCALABILITY SCORE
            refined_scalability = refine_scalability_score(
                base_score=selected_solution.seo_scalability_score,
                project_type=selected_solution.project_type,
                total_volume=total_monthly_volume,
                tier1_count=tier1_count,
                all_tiered_keywords=all_tiered_keywords,
                total_keyword_count=total_keyword_count,
            )

            # 2. REFINE CAC ORGANIC
            refined_cac = refine_cac_organic(
                base_cac_str=selected_solution.estimated_cac_organic,
                tier1_keywords=tier1_keywords,
                total_volume=total_monthly_volume
            )

            # 3. REFINE PROGRAMMATIC SEO OPPORTUNITY (calculates page count)
            refined_programmatic_result = refine_programmatic_opportunity(
                original_assessment=selected_solution.programmatic_seo_opportunity,
                seo_report=seo_report,
                tier1_count=tier1_count
            )

            # Extract page count from programmatic refinement
            page_count = refined_programmatic_result.get('page_count', 0)
            refined_programmatic = refined_programmatic_result.get('assessment', '')

            # SEO-realism cap on the refined score (downgrade-only). Pages are NOW known, so
            # Rule B engages here (in addition to A). Stage 12 runs AFTER ranking is locked,
            # so capping the selected solution's displayed/verdict SEO cannot reorder anything.
            refined_seo_score = refined_scalability['score']
            from ..utils.seo_helpers import cap_seo_realism_score
            _capped, _note = cap_seo_realism_score(
                refined_seo_score,
                project_type=getattr(selected_solution, "project_type", None),
                data_access_model=getattr(selected_solution, "data_access_model", None),
                estimated_indexable_pages=page_count,
                require_saas_for_gating=settings.seo_cap_require_saas_for_gating,
                gated_saas_ceiling=settings.seo_cap_gated_saas_ceiling,
                thin_pages_threshold=settings.seo_cap_thin_pages_threshold,
                thin_pages_ceiling=settings.seo_cap_thin_pages_ceiling,
                high_score_min_pages=settings.seo_cap_high_score_min_pages,
                moderate_pages_ceiling=settings.seo_cap_moderate_pages_ceiling,
            )
            if _note:
                logger.info(f"[Stage 12][SEO-REALISM] {selected_solution_name}: "
                            f"{refined_seo_score:.2f} -> {_capped:.2f} ({_note})")
                refined_seo_score = _capped

            # Update CAC metadata with page count
            refined_cac['metadata']['estimated_year1_pages'] = page_count

            # Create SEO enrichment object (unified enrichment pattern)
            # This will be merged with base solution in report generator
            scalability_meta = refined_scalability['metadata']
            cac_meta = refined_cac['metadata']

            from ..models.solution_idea import SEORefinementMetadata, SolutionSEORefinement

            seo_enrichment = SolutionSEORefinement(
                solution_name=selected_solution_name,
                seo_scalability_score_refined=refined_seo_score,
                estimated_cac_organic_refined=refined_cac['cac_range'],
                programmatic_seo_opportunity_refined=refined_programmatic,
                estimated_indexable_pages=page_count,
                seo_refinement_metadata=SEORefinementMetadata(
                    baseline_volume_used=scalability_meta.get('baseline_volume'),
                    volume_multiplier=scalability_meta.get('volume_multiplier'),
                    tier1_multiplier=scalability_meta.get('tier1_multiplier'),
                    competition_modifier=scalability_meta.get('competition_modifier'),
                    base_cac=cac_meta.get('base_cac'),
                    difficulty_multiplier=cac_meta.get('difficulty_multiplier'),
                    volume_discount=cac_meta.get('volume_discount'),
                    estimated_year1_pages=cac_meta.get('estimated_year1_pages'),
                    keyword_evidence_floor=scalability_meta.get('keyword_evidence_floor'),
                    floor_applied=scalability_meta.get('floor_applied'),
                    floor_reason=scalability_meta.get('floor_reason'),
                    min_competition_modifier_applied=scalability_meta.get('min_competition_modifier_applied'),
                )
            )

            # Store enrichment in state (for report generator access)
            self.state.seo_enrichment = seo_enrichment

            # Phase 2.4: Merge SEO enrichment inline to selected solution (prevents data loss)
            # This ensures downstream stages and reports have direct access to refined scores
            # without needing to query seo_enrichment separately
            for idx, idea in enumerate(self.state.idea_generation.solution_ideas):
                if idea.solution_name == selected_solution_name:
                    # Store original values for comparison (if not already stored)
                    if not hasattr(idea, '_original_seo_scalability_score'):
                        idea._original_seo_scalability_score = idea.seo_scalability_score
                        idea._original_estimated_cac_organic = idea.estimated_cac_organic
                        idea._original_programmatic_seo_opportunity = idea.programmatic_seo_opportunity

                    # Apply refined values inline (seo already SEO-realism-capped above)
                    idea.seo_scalability_score = refined_seo_score
                    idea.estimated_cac_organic = refined_cac['cac_range']
                    idea.programmatic_seo_opportunity = refined_programmatic
                    from ..utils.idea_tags import refresh_tag_facets
                    idea.tags = refresh_tag_facets(idea)

                    logger.info(f"[Stage 12] Merged SEO refinements into solution '{selected_solution_name}'")
                    break

            logger.info("[OK] SEO scores refined:")
            logger.info(
                f"  Scalability: {selected_solution.seo_scalability_score:.2f} → "
                f"{refined_scalability['score']:.2f} "
                f"({'+' if refined_scalability['score'] > selected_solution.seo_scalability_score else ''}"
                f"{(refined_scalability['score'] - selected_solution.seo_scalability_score):.2f})"
            )
            logger.info(
                f"  CAC Organic: {selected_solution.estimated_cac_organic} → "
                f"{refined_cac['cac_range']}"
            )
            logger.info(
                f"  Programmatic Pages: {refined_cac['metadata'].get('estimated_year1_pages', 'N/A')} estimated"
            )

            # Update stage first, then checkpoint (Pattern A - safer for resume)
            self.state.current_stage = 13

            # Mark stage complete with tracking
            self._mark_stage_complete(12)

            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", self.state.seo_enrichment)

        except Exception as e:
            logger.error(f"SEO refinement failed: {e}")
            logger.warning("Continuing with original estimates")
            # Still update stage even on failure (Pattern A - safer for resume)
            self.state.current_stage = 13

            # Mark stage complete with tracking (used fallback since refinement failed)
            self._mark_stage_complete(12, used_fallback=True)
            self.checkpoint_mgr.save_stage("stage_12_seo_refinement", {"skipped": True, "reason": str(e)})

    def stage_13_research_data_sources(self):
        """
        Stage 13: Targeted Data Source Research

        For the SELECTED solution ONLY (if requires_data_aggregation), conduct deep
        research on data sources using search tools. Informed by SEO priorities and
        competitive insights.
        """
        logger.info("=" * 80)
        logger.info("STAGE 13: Data Source Research")
        logger.info("=" * 80)
        self._emit_progress(13, "Data Source Research", "running")

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.info("No solution selected - skipping data source research")
            self.state.data_source_research = None
            self.state.current_stage = 14
            self._skip_stage(13, "Data Source Research", "No solution selected")
            self.checkpoint_mgr.save_stage("stage_13_data_sources", {"skipped": True, "reason": "No solution selected"})
            return

        # Get the selected solution (with fuzzy matching fallback)
        selected_solution_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_solution_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.warning(
                f"Selected solution '{selected_solution_name}' not found - skipping data source research. "
                f"Available solutions: {[sol.solution_name for sol in self.state.idea_generation.solution_ideas]}"
            )
            self.state.data_source_research = None
            self.state.current_stage = 14
            self._skip_stage(13, "Data Source Research", f"Selected solution '{selected_solution_name}' not found")
            self.checkpoint_mgr.save_stage("stage_13_data_sources", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        # Only run if solution requires data aggregation
        if not selected_solution.requires_data_aggregation:
            logger.info(
                f"Solution '{selected_solution_name}' doesn't require data aggregation - "
                f"skipping data source research"
            )
            self.state.data_source_research = None
            self.state.current_stage = 14
            self._skip_stage(13, "Data Source Research", "Solution doesn't require data aggregation")
            self.checkpoint_mgr.save_stage("stage_13_data_sources", {"skipped": True, "reason": "Solution doesn't require data aggregation"})
            return

        logger.info(
            f"Researching data sources for '{selected_solution_name}' "
            f"(requires_data_aggregation=True)"
        )

        # Get competitive landscape for selected solution
        competitive_landscape = None
        if self.state.competitive_analysis:
            competitive_landscape = next(
                (cl for cl in self.state.competitive_analysis.solution_landscapes
                 if cl.solution_name == selected_solution_name),
                None
            )

        # Initialize DataSourceResearchCrew
        from ..crews.data_source_crew import DataSourceResearchCrew

        data_crew = DataSourceResearchCrew(
            solution=selected_solution,
            competitive_landscape=competitive_landscape,
            seo_strategy=self.state.seo_strategy_report,
            niche_description=self.niche_description
        )

        # Run targeted data source research
        try:
            logger.info(f"Starting data source discovery for {selected_solution_name}...")
            data_source_research = data_crew.research()
            self.state.data_source_research = data_source_research

            # Downgrade-only reconcile: if Stage-13's verified primary source is HARDER to
            # access than the ideation critic estimated, lower the selected solution's
            # surfaced data_feasibility (never raise) and record the estimate→verified delta
            # as a data-quality risk. Non-gating (annotate-only).
            try:
                from ..crews.data_source_crew import reconcile_data_feasibility
                primary = (data_source_research.primary_data_sources or [])
                verified_access = primary[0].access_model if primary else None
                new_score, new_access, caveat = reconcile_data_feasibility(
                    getattr(selected_solution, "data_feasibility_score", None),
                    getattr(selected_solution, "data_access_model", None),
                    verified_access,
                )
                if caveat:
                    selected_solution.data_feasibility_score = new_score
                    selected_solution.data_access_model = new_access
                    if data_source_research.data_quality_risks is None:
                        data_source_research.data_quality_risks = []
                    data_source_research.data_quality_risks.append(caveat)
                    logger.info(f"[Stage 13] {caveat}")
            except Exception as e:
                logger.warning(f"[Stage 13] data-feasibility reconcile skipped: {str(e)[:120]}")

            # Record crew cost
            if data_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 13 - Data Sources",
                    usage_metrics=data_crew.usage_metrics,
                    model=settings.openai_model_name
                )

            logger.info(
                f"[OK] Data source research complete: "
                f"{len(data_source_research.primary_data_sources)} primary sources, "
                f"{len(data_source_research.fallback_sources) if data_source_research.fallback_sources else 0} fallback sources"
            )

            # Log key findings
            if data_source_research.estimated_monthly_cost:
                logger.info(f"  Estimated monthly cost: {data_source_research.estimated_monthly_cost}")

        except Exception as e:
            logger.error(f"Data source research failed: {e}")
            self.state.data_source_research = None
            logger.warning("Continuing to final report without data source research")

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 14

        # Mark stage complete with tracking
        self._mark_stage_complete(13)

        # Checkpoint: Save data source research
        if self.state.data_source_research:
            self.checkpoint_mgr.save_stage("stage_13_data_sources", self.state.data_source_research)

    def stage_14_generate_report(self):
        """
        Stage 14: Final Report Generation

        Hybrid approach: Python data assembly (80%) + optional LLM strategic synthesis (20%).
        Cost: ~$0.02-0.05 per report (vs $0.10-0.30 previously).
        Speed: ~2-3 seconds (vs 5-15 seconds previously).

        Delegates all report generation logic to ReportGenerator class.
        """
        # Systemic-LLM halt point: never assemble a final report on a breaker-tripped run.
        from ..utils.llm_service import LLMService as _LLMSvc
        _LLMSvc.raise_if_systemic()
        logger.info("=" * 80)
        logger.info("STAGE 10: Final Report Generation (Hybrid Python + LLM)")
        logger.info("=" * 80)
        self._emit_progress(14, "Report Generation", "running")

        from datetime import datetime

        from ..report.report_generator import ReportGenerator

        try:
            # Delegate to ReportGenerator for all report generation logic.
            # Pass the cost tracker so Stage-14 LLM calls are recorded.
            report_generator = ReportGenerator(self.state, cost_tracker=self.cost_tracker)
            final_report = report_generator.generate_report()

            self.state.final_report = final_report

            # Finalize the cost summary BEFORE saving the raw-state file below, so the
            # persisted JSON actually contains it (all recording is complete here,
            # including the Stage-14 report calls). Previously this ran after the save.
            self.state.cost_summary = self.cost_tracker.get_summary()

        except Exception as e:
            logger.error(f"Failed to generate final report: {e}")
            raise  # Let the error propagate up

        # Save outputs
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save structured final report (using model_dump_json for better performance)
        report_filename = f"final_report_{timestamp}.json"
        report_filepath = output_dir / report_filename
        with open(report_filepath, "w", encoding="utf-8") as f:
            f.write(final_report.model_dump_json(indent=2))
        logger.info(f"[OK] Final report saved to: {report_filepath}")

        # Save complete raw state for reference (using model_dump_json for better performance)
        raw_filename = f"research_state_raw_{timestamp}.json"
        raw_filepath = output_dir / raw_filename
        with open(raw_filepath, "w", encoding="utf-8") as f:
            f.write(self.state.model_dump_json(indent=2))
        logger.info(f"[OK] Raw research state saved to: {raw_filepath}")

        # Store report paths
        self.report_path = str(report_filepath)
        self.raw_state_path = str(raw_filepath)

        # Mark stage complete with tracking (final stage)
        self._mark_stage_complete(14)

        # Log pipeline completion summary
        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Stages completed: {sorted(self.state.completed_stages)}")
        if self.state.fallback_stages:
            logger.warning(f"  Stages with fallback data: {sorted(self.state.fallback_stages)}")
        logger.info("=" * 80)

        # Log cost summary (state.cost_summary was already assigned above, before the
        # file saves, so the persisted raw-state JSON includes it).
        if settings.cost_logging_enabled:
            self.cost_tracker.log_summary()

    # NOTE: Score refinement methods moved to utils/score_refinement.py
    # - refine_scalability_score
    # - refine_cac_organic
    # - refine_programmatic_opportunity

    def kickoff(self, *args, **kwargs):
        """Not an execution path. ResearchFlow has NO CrewAI @start/@listen graph — every stage
        runs through the `_execute_remaining_stages` sequential driver (via run_with_resume),
        which owns the prerequisite/skip/checkpoint-gating logic the listener graph lacked. The
        Flow base class is retained only for its structured-state container (self.state). This
        override makes an accidental kickoff() a loud, clear failure instead of a silent no-op."""
        raise NotImplementedError(
            "ResearchFlow does not execute via kickoff(); use run_with_resume() / "
            "_execute_remaining_stages(). ResearchFlow has no CrewAI @start/@listen graph."
        )
