"""
ResearchFlow - Main orchestration flow for the 10-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from crewai.flow.flow import Flow, listen, start

if TYPE_CHECKING:
    from ..models.research_state import NicheContext
from crewai_tools import SerperDevTool
from loguru import logger

from ..config.settings import settings
from ..crews import PainPointCrew, SEOStrategyCrew, UnifiedSolutionCrew
from ..crews.solution_refinement_crew import SolutionRefinementCrew
from ..crews.traffic_monetization_crew import TrafficMonetizationCrew
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.research_state import ResearchState
from ..tools.reddit_tool import RedditCollectorTool
from ..tools.twitter_tool import TwitterCollectorTool
from ..utils.helpers import find_solution_by_name
from ..utils.keyword_filtering import check_keyword_relevance
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


class ResearchFlow(Flow[ResearchState]):
    """
    Main research flow orchestrating all 10 stages of the NicheIQ pipeline.

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

    def __init__(self, niche_description: str, allowed_project_types: list[str | None] = None):
        """
        Initialize ResearchFlow with niche description.

        Args:
            niche_description: User's niche area description
            allowed_project_types: Optional list of allowed project types (saas, directory, aggregator, comparison-tool, marketplace)
        """
        super().__init__()

        # Store niche description for use in flow methods
        self.niche_description = niche_description
        self.allowed_project_types = allowed_project_types

        # Initialize tools
        self.search_tool = SerperDevTool()
        self.reddit_tool = RedditCollectorTool()
        self.twitter_tool = TwitterCollectorTool()

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
            allowed_project_types=allowed_project_types
        )

        # Optional progress callback for web worker integration
        # Can be set after initialization: flow.progress_callback = callback
        # Callback signature: (stage_num: float, stage_name: str, status: str) -> None
        self.progress_callback = None

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

    def _emit_progress(self, stage_num: float, stage_name: str | None, status: str) -> None:
        """
        Emit progress update via callback if set.

        Used for web worker integration to publish real-time updates via Redis.

        Args:
            stage_num: Stage number (e.g., 1, 5, 6.5, 8.5)
            stage_name: Human-readable stage name (None to let callback look it up)
            status: 'running', 'completed', or 'failed'
        """
        if self.progress_callback:
            try:
                self.progress_callback(stage_num, stage_name, status)
            except Exception as e:
                logger.warning(f"Progress callback failed for stage {stage_num}: {e}")

    def resume_from_checkpoint(self, checkpoint_path: Path | None = None) -> bool:
        """
        Resume research flow from checkpoint.

        Args:
            checkpoint_path: Explicit checkpoint folder path, or None to auto-detect

        Returns:
            True if resumed successfully, False otherwise
        """
        if not settings.checkpoint_enabled:
            logger.warning("Checkpointing is disabled - cannot resume")
            return False

        # Find checkpoint
        checkpoint = checkpoint_path or self.checkpoint_mgr.find_latest_checkpoint()
        if not checkpoint:
            logger.info("No checkpoint found for this niche")
            return False

        # Load checkpoint
        if not self.checkpoint_mgr.load_checkpoint_folder(checkpoint):
            return False

        # Cleanup old checkpoints
        self.checkpoint_mgr.cleanup_old_checkpoints()

        logger.info(f"Resume from stage {self.state.current_stage}")
        return True

    def run_with_resume(self, auto_resume: bool = True) -> str:
        """
        Execute research pipeline with checkpoint resume support.

        Args:
            auto_resume: If True, automatically resume from latest checkpoint if available

        Returns:
            Path to final report
        """
        # Try to resume from checkpoint
        if auto_resume and self.resume_from_checkpoint():
            logger.info("Resuming from checkpoint - skipping completed stages")

            # Emit progress for the stage we're resuming from
            # Pass None for stage_name - the callback will look it up from STAGE_NAMES
            self._emit_progress(self.state.current_stage, None, "running")

            return self._execute_remaining_stages()

        # No checkpoint or resume failed - run normal flow
        logger.info("Starting fresh research run")
        self.kickoff()

        # Return the actual report path stored during stage 10
        if hasattr(self, 'report_path') and self.report_path:
            return self.report_path

        return ""

    def _validate_stage_prerequisites(self, stage_num: float) -> bool:
        """
        Validate that required data exists before executing a stage.

        Args:
            stage_num: Stage number to validate prerequisites for

        Returns:
            True if prerequisites are met, False if stage should be skipped
        """
        prerequisites = {
            6: lambda: (
                self.state.social_content is not None and
                (bool(self.state.social_content.reddit_posts) or bool(self.state.social_content.twitter_threads))
            ),
            6.5: lambda: (
                self.state.social_content is not None and
                self.state.pain_point_analysis is not None
            ),
            7: lambda: (
                self.state.pain_point_analysis is not None and
                bool(self.state.pain_point_analysis.pain_points)
            ),
            8: lambda: (
                self.state.idea_generation is not None and
                bool(self.state.idea_generation.solution_ideas)
            ),
            8.5: lambda: (
                self.state.competitive_analysis is not None and
                self.state.idea_generation is not None
            ),
            8.55: lambda: (
                self.state.keyword_validation_results is not None and
                self.state.idea_generation is not None
            ),
            8.75: lambda: (
                self.state.idea_generation is not None and
                bool(self.state.idea_generation.solution_ideas)
            ),
            8.7: lambda: (
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            8.6: lambda: (
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            8.8: lambda: (
                getattr(settings, 'keyword_validation_enabled', True) and
                self.state.solution_selection is not None and
                bool(getattr(self.state.solution_selection, 'all_solution_scores', []))
            ),
            8.85: lambda: (
                getattr(settings, 'solution_refinement_enabled', True) and
                self.state.solution_selection is not None and
                self.state.keyword_validation_results is not None
            ),
            9: lambda: (
                self.state.solution_selection is not None and
                self.state.idea_generation is not None
            ),
            9.2: lambda: (
                self.state.keyword_validation_results is not None and
                self.state.social_content is not None and
                self.state.solution_selection is not None and
                self.state.pain_point_analysis is not None and
                self.state.competitive_analysis is not None
            ),
            9.5: lambda: (
                settings.seo_refinement_enabled and
                self.state.seo_strategy_report is not None and
                self.state.solution_selection is not None
            ),
            9.75: lambda: (
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

        # Trend direction thresholds
        if trend_pct > 15:
            trend_direction = "rising"
        elif trend_pct < -15:
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
            "is_evergreen": is_evergreen
        }

    def _aggregate_keyword_trends(self) -> dict | None:
        """
        Aggregate per-keyword trends into market-level summary for Stage 9.5.

        Uses enriched keywords from Stage 9.5c to calculate:
        - Distribution of rising/stable/declining keywords
        - Percentage of search volume from rising keywords
        - Lists of seasonal and evergreen keywords
        - Overall market momentum assessment

        Returns:
            Dict with trend_distribution, rising_volume_pct, seasonal/evergreen keywords,
            market_momentum, or None if no enriched keywords available
        """
        enriched_keywords = self.state.stage_9_5c_enriched_keywords
        if not enriched_keywords:
            logger.debug("[_aggregate_keyword_trends] No enriched keywords available")
            return None

        trends = {"rising": 0, "stable": 0, "declining": 0, "unknown": 0}
        total_volume = 0
        rising_volume = 0
        seasonal_keywords = []
        evergreen_keywords = []

        for kw in enriched_keywords:
            monthly_searches = kw.get("monthly_searches", [])
            metrics = self._calculate_trend_metrics(monthly_searches)
            trends[metrics["trend_direction"]] += 1
            vol = kw.get("search_volume", 0)
            total_volume += vol

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

        # Determine market momentum
        if trends["rising"] > trends["declining"] * 1.5:
            market_momentum = "Growing"
        elif trends["declining"] > trends["rising"] * 1.5:
            market_momentum = "Declining"
        else:
            market_momentum = "Stable"

        return {
            "trend_distribution": trends,
            "rising_volume_pct": (rising_volume / total_volume * 100) if total_volume else 0,
            "total_keywords_analyzed": len(enriched_keywords),
            "top_seasonal_keywords": [kw["keyword"] for kw in seasonal_keywords[:5]],
            "top_evergreen_keywords": [kw["keyword"] for kw in evergreen_keywords[:10]],
            "evergreen_count": len(evergreen_keywords),
            "seasonal_count": len(seasonal_keywords),
            "market_momentum": market_momentum
        }

    def _validate_pain_point_quality(self, analysis) -> tuple[str, float]:
        """
        Validate pain point analysis quality and return tier classification.

        Implements tiered quality gates to ensure pipeline proceeds with sufficient data:
        - GOLD: High-quality pain points with strong evidence and cross-platform validation
        - SILVER: Medium-quality pain points with adequate supporting data
        - BRONZE: Minimum viable pain points with basic evidence
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

        # Calculate quality metrics
        pain_points = analysis.pain_points
        total_count = len(pain_points)

        # Severity distribution
        high_severity = len([pp for pp in pain_points if pp.severity_score >= 0.7])
        medium_severity = len([pp for pp in pain_points if 0.5 <= pp.severity_score < 0.7])

        # WTP (Willingness-to-Pay) signal strength
        high_wtp = len([pp for pp in pain_points if pp.willingness_to_pay >= 0.7])
        medium_wtp = len([pp for pp in pain_points if 0.5 <= pp.willingness_to_pay < 0.7])

        # Quote evidence density (average quotes per pain point)
        quote_density = sum(len(pp.representative_quotes) for pp in pain_points) / total_count if total_count > 0 else 0

        # Cross-platform validation (pain points found on multiple platforms)
        cross_platform_count = 0
        for pp in pain_points:
            if pp.source_platforms and len(pp.source_platforms) > 1:
                cross_platform_count += 1

        # Source attribution coverage (% of pain points with source_post_ids)
        sourced_count = len([pp for pp in pain_points if pp.source_post_ids])
        source_coverage = sourced_count / total_count if total_count > 0 else 0

        # High-opportunity pain points
        high_opportunity = len([pp for pp in pain_points if pp.opportunity_level.value == "high"])

        # Determine if single-platform mode (either Twitter or Reddit disabled)
        single_platform_mode = not settings.enable_twitter or not settings.enable_reddit

        # Adjust weights based on platform availability
        if single_platform_mode:
            # Redistribute cross-platform 15% weight to other metrics
            # Quote density gets +10% (most impactful for single-source validation)
            # Source attribution gets +5% (verifiable without cross-platform)
            weights = {
                "high_severity": 0.25,
                "high_wtp": 0.20,
                "quote_density": 0.30,  # 20% + 10% redistributed
                "cross_platform": 0.0,   # N/A in single-platform mode
                "source_coverage": 0.15, # 10% + 5% redistributed
                "high_opportunity": 0.10
            }
        else:
            weights = {
                "high_severity": 0.25,
                "high_wtp": 0.20,
                "quote_density": 0.20,
                "cross_platform": 0.15,
                "source_coverage": 0.10,
                "high_opportunity": 0.10
            }

        # Calculate confidence score (0-1)
        confidence_score = (
            (high_severity / max(total_count, 1)) * weights["high_severity"] +
            (high_wtp / max(total_count, 1)) * weights["high_wtp"] +
            (min(quote_density / 10, 1.0)) * weights["quote_density"] +
            (cross_platform_count / max(total_count, 1)) * weights["cross_platform"] +
            source_coverage * weights["source_coverage"] +
            (high_opportunity / max(total_count, 1)) * weights["high_opportunity"]
        )

        # Tier classification with detailed logging
        logger.info("=" * 60)
        logger.info("PAIN POINT QUALITY ASSESSMENT")
        logger.info("=" * 60)
        logger.info(f"Total pain points: {total_count}")
        logger.info(f"Severity distribution: {high_severity} high | {medium_severity} medium | {total_count - high_severity - medium_severity} low")
        logger.info(f"WTP signal: {high_wtp} high | {medium_wtp} medium")
        logger.info(f"Quote density: {quote_density:.1f} quotes/pain point (target: ≥10 for GOLD)")
        if single_platform_mode:
            logger.info("Platform mode: Single-platform (Twitter disabled) - cross-platform metric skipped")
        else:
            logger.info(f"Cross-platform validation: {cross_platform_count}/{total_count} pain points ({cross_platform_count/total_count*100:.0f}%)")
        logger.info(f"Source attribution coverage: {source_coverage*100:.0f}%")
        logger.info(f"High-opportunity pain points: {high_opportunity} ({high_opportunity/total_count*100:.0f}%)")
        logger.info(f"Overall confidence score: {confidence_score:.2f}")

        # GOLD tier: Exceptional quality for high-confidence pipeline
        gold_cross_platform_ok = single_platform_mode or cross_platform_count >= 3
        if (
            high_severity >= 5 and
            quote_density >= 10 and
            gold_cross_platform_ok and
            source_coverage >= 0.90 and
            high_opportunity >= 3
        ):
            tier = "GOLD"
            logger.info(f"✅ Quality Tier: {tier} (Exceptional - High confidence for pipeline)")

        # SILVER tier: Good quality for reliable pipeline
        elif (
            (high_severity >= 3 or (high_severity + medium_severity) >= 5) and
            quote_density >= 5 and
            source_coverage >= 0.70
        ):
            tier = "SILVER"
            logger.info(f"✅ Quality Tier: {tier} (Good - Reliable for pipeline)")

        # BRONZE tier: Minimum viable quality
        elif (
            total_count >= 2 and
            quote_density >= 3 and
            source_coverage >= 0.50
        ):
            tier = "BRONZE"
            logger.warning(f"⚠️  Quality Tier: {tier} (Minimum Viable - Proceed with caution)")
            logger.warning("    Consider expanding social content collection for better insights")

        # INSUFFICIENT: Below minimum threshold
        else:
            tier = "INSUFFICIENT"
            logger.error(f"❌ Quality Tier: {tier} (Insufficient - Should not proceed)")
            logger.error("    Recommendation: Expand social content collection or adjust niche focus")
            logger.error(f"    Gaps: quote_density={quote_density:.1f} (need ≥3), source_coverage={source_coverage*100:.0f}% (need ≥50%)")

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

        # Track completion timestamp
        stage_key = str(stage)
        self.state.stage_completion_timestamps[stage_key] = datetime.now()

        # Track fallback usage
        if used_fallback and stage not in self.state.fallback_stages:
            self.state.fallback_stages.append(stage)
            self.state.fallback_stages.sort()
            logger.warning(f"[Stage Tracking] Stage {stage} used fallback data")

        # Emit progress callback for web worker integration
        stage_names = {
            1: "Niche Validation",
            5: "Search & Discovery",
            6: "Pain Point Analysis",
            6.5: "Audience Mapping",
            7: "Solution Pipeline",
            8: "Pricing Validation",
            8.5: "Keyword Validation",
            8.55: "Traffic Monetization",
            8.6: "Market Sizing",
            8.7: "Solution Refinement",
            9: "SEO Strategy",
            9.5: "Trend Analysis",
            9.6: "SEO Score Refinement",
            9.7: "Data Source Research",
            10: "Report Generation",
        }
        stage_name = stage_names.get(stage, f"Stage {stage}")
        self._emit_progress(stage, stage_name, "completed")

    def _map_pain_points_to_segments(self, audience_result) -> None:
        """
        Map pain points to audience segments based on keyword matching.

        Phase 3: Enriches PainPoint.affected_segments by matching pain point
        categories and keywords against audience segment primary concerns.

        This enables:
        - Understanding which segments experience which pain points
        - Solution targeting based on segment-pain alignment
        - Marketing messaging specific to segment needs

        Args:
            audience_result: AudienceMappingResult from Stage 6.5
        """
        if not self.state.pain_point_analysis:
            return

        # Build lookup: lowercase keywords from segments → segment names
        segment_keyword_map: dict[str, list[str]] = {}
        for segment in audience_result.audience_segments:
            segment_name = segment.segment_name
            # Use primary_concerns as matching keywords
            for concern in (segment.pain_point_alignment or []):
                keywords = concern.lower().split()
                for keyword in keywords:
                    if len(keyword) > 3:  # Skip short words
                        if keyword not in segment_keyword_map:
                            segment_keyword_map[keyword] = []
                        if segment_name not in segment_keyword_map[keyword]:
                            segment_keyword_map[keyword].append(segment_name)

        # Map pain points to segments
        mapped_count = 0
        for pain_point in self.state.pain_point_analysis.pain_points:
            matching_segments = set()

            # Match against pain point title and categories
            title_words = pain_point.title.lower().split()
            categories = [c.lower() for c in (pain_point.categories or [])]

            # Check title keywords
            for word in title_words:
                if word in segment_keyword_map:
                    matching_segments.update(segment_keyword_map[word])

            # Check category keywords
            for cat in categories:
                cat_words = cat.split()
                for word in cat_words:
                    if word in segment_keyword_map:
                        matching_segments.update(segment_keyword_map[word])

            # Update affected_segments
            if matching_segments:
                pain_point.affected_segments = list(matching_segments)
                mapped_count += 1

        if mapped_count > 0:
            logger.info(
                f"[Stage 6.5] Mapped {mapped_count}/{len(self.state.pain_point_analysis.pain_points)} "
                f"pain points to audience segments"
            )

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
            "stage_5_discussions": (5, "Search & Discovery"),
            "stage_6_pain_points": (6, "Pain Point Analysis"),
            "stage_6_5_audience_mapping": (6.5, "Audience Mapping"),
            "stage_7_6_selection": (7, "Solution Pipeline"),
            "stage_8_pricing": (8, "Pricing Validation"),
            "stage_8_5_keyword_validation": (8.5, "Keyword Validation"),
            "stage_8_55_traffic_monetization": (8.55, "Traffic Monetization"),
            "stage_8_6_market_sizing": (8.6, "Market Sizing"),
            "stage_8_7_solution_refinement": (8.7, "Solution Refinement"),
            "stage_9_seo_strategy": (9, "SEO Strategy"),
            "stage_9_5_trend_longevity": (9.5, "Trend Analysis"),
            "stage_9_6_seo_refinement": (9.6, "SEO Score Refinement"),
            "stage_9_7_data_sources": (9.7, "Data Source Research"),
            "stage_10_report": (10, "Report Generation"),
        }

        for checkpoint_name in completed_stages:
            if checkpoint_name in stage_mapping:
                stage_num, stage_name = stage_mapping[checkpoint_name]
                logger.info(f"[Resume] Replaying completed status for stage {stage_num}: {stage_name}")
                self._emit_progress(stage_num, stage_name, "completed")

    def _execute_remaining_stages(self) -> str:
        """
        Execute remaining stages after checkpoint resume.
        Manually calls stage methods based on current_stage.
        Validates prerequisites before executing each stage to prevent cascade failures.
        """
        current = self.state.current_stage
        logger.info(f"Executing stages from {current} onwards...")

        # Get list of completed stages to avoid re-running listener stages
        completed_stages = self.checkpoint_mgr.get_completed_stages()

        # Replay progress for stages completed in previous runs
        # This syncs the backend database with checkpoint state
        self._replay_completed_stages_progress(completed_stages)

        # Stage mapping: (stage_number, method_name)
        # We need to execute stages >= current_stage
        try:
            if current <= 1:
                self.stage_1_validate_niche()

            if current <= 5:
                self.stage_5_search_and_discover()

            if current <= 6 and self._validate_stage_prerequisites(6):
                self.stage_6_analyze_pain_points()
            elif current <= 6:
                logger.info("Skipping Stage 6 (Pain Point Analysis) - prerequisites not met")

            # Stage 6.5: Only run if not already completed (listener stage)
            if current <= 6.5 and "stage_6_5_audience_mapping" not in completed_stages:
                if self._validate_stage_prerequisites(6.5):
                    self.stage_6_5_audience_mapping()
                else:
                    logger.info("Skipping Stage 6.5 (Audience Mapping) - prerequisites not met")
            elif "stage_6_5_audience_mapping" in completed_stages:
                logger.info("Skipping Stage 6.5 (Audience Mapping) - already completed")

            # Stages 7-8.75 now handled by unified solution pipeline
            if "stage_7_6_selection" not in completed_stages:
                if self._validate_stage_prerequisites(7):
                    logger.info("Executing Unified Solution Pipeline (Stages 7-8.75)...")
                    self.stage_7_unified_solution_pipeline()
                    # Refresh completed_stages so subsequent stages see Stage 7 checkpoint
                    completed_stages = self.checkpoint_mgr.get_completed_stages()
                else:
                    logger.info("Skipping Stages 7-8.75 (Unified Solution Pipeline) - prerequisites not met")
                    # Skip all solution stages if prerequisites not met
                    self.state.current_stage = 9
            else:
                logger.info("Skipping Stages 7-8.75 (Unified Solution Pipeline) - already completed")

            # Stage 8: Only run if not already completed (listener stage)
            # NOTE: Don't use `current <= 8` check because Stage 8 sets current_stage = 8.5
            # before Stage 8.5 runs. Use checkpoint status as the primary check.
            if "stage_8_pricing_validation" not in completed_stages:
                # Only run if Stage 7 (unified pipeline) has completed
                if "stage_7_6_selection" in completed_stages:
                    if self._validate_stage_prerequisites(8):
                        self.stage_8_pricing_validation()
                        # Refresh completed_stages so subsequent stages see this checkpoint
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 8 (Pricing Validation) - prerequisites not met")
                else:
                    logger.info("Skipping Stage 8 (Pricing Validation) - awaiting Stage 7")
            else:
                logger.info("Skipping Stage 8 (Pricing Validation) - already completed")

            # Stage 8.5: Keyword Validation (runs after Stage 8)
            # NOTE: Don't use `current <= 8.5` check because Stage 8 already set current_stage = 8.5.
            # Stage 8.5 executes AFTER 8 via @listen, so use checkpoint status.
            if "stage_8_5_keyword_validation" not in completed_stages:
                # Only run if Stage 8 has completed (8.5 listens to 8)
                if "stage_8_pricing_validation" in completed_stages:
                    if self._validate_stage_prerequisites(8.5):
                        self.stage_8_5_keyword_validation()
                        # Refresh completed_stages so subsequent stages see this checkpoint
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 8.5 (Keyword Validation) - prerequisites not met")
                else:
                    logger.info("Skipping Stage 8.5 (Keyword Validation) - awaiting Stage 8")
            else:
                logger.info("Skipping Stage 8.5 (Keyword Validation) - already completed")

            # Stage 8.55: Traffic Monetization (runs after Stage 8.5 for directory/aggregator types)
            if "stage_8_55_traffic_monetization" not in completed_stages:
                # Only run if Stage 8.5 has completed
                if "stage_8_5_keyword_validation" in completed_stages:
                    if self._validate_stage_prerequisites(8.55):
                        self.stage_8_55_traffic_monetization()
                        # Refresh completed_stages so subsequent stages see this checkpoint
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 8.55 (Traffic Monetization) - prerequisites not met")
                else:
                    logger.info("Skipping Stage 8.55 (Traffic Monetization) - awaiting Stage 8.5")
            else:
                logger.info("Skipping Stage 8.55 (Traffic Monetization) - already completed")

            # Stage 8.6: Market Sizing (runs after Stage 8.55, now has keyword data and traffic analysis)
            if "stage_8_6_market_sizing" not in completed_stages:
                # Only run if Stage 8.55 has completed (which runs after 8.5)
                if "stage_8_55_traffic_monetization" in completed_stages or "stage_8_5_keyword_validation" in completed_stages:
                    if self._validate_stage_prerequisites(8.6):
                        self.stage_8_6_market_sizing()
                        # Refresh completed_stages so subsequent stages see this checkpoint
                        completed_stages = self.checkpoint_mgr.get_completed_stages()
                    else:
                        logger.info("Skipping Stage 8.6 (Market Sizing) - prerequisites not met")
                else:
                    logger.info("Skipping Stage 8.6 (Market Sizing) - awaiting Stage 8.5")
            else:
                logger.info("Skipping Stage 8.6 (Market Sizing) - already completed")

            # Stage 8.7: Only run if not already completed
            if current <= 8.7 and "stage_8_7_solution_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(8.7):
                    self.stage_8_7_solution_refinement()
                    # Refresh completed_stages so subsequent stages see this checkpoint
                    completed_stages = self.checkpoint_mgr.get_completed_stages()
                else:
                    logger.info("Skipping Stage 8.7 (Solution Refinement) - prerequisites not met")
            elif "stage_8_7_solution_refinement" in completed_stages:
                logger.info("Skipping Stage 8.7 (Solution Refinement) - already completed")

            if current <= 9 and "stage_9_seo_strategy" not in completed_stages:
                if self._validate_stage_prerequisites(9):
                    self.stage_9_generate_seo_strategy()
                else:
                    logger.info("Skipping Stage 9 (SEO Strategy) - prerequisites not met")
            elif "stage_9_seo_strategy" in completed_stages:
                logger.info("Skipping Stage 9 (SEO Strategy) - already completed")

            # Stage 9.5: Only run if not already completed (listener stage)
            if current <= 9.5 and "stage_9_5_trend_longevity" not in completed_stages:
                if self._validate_stage_prerequisites(9.5):
                    self.stage_9_5_trend_longevity()
                else:
                    logger.info("Skipping Stage 9.5 (Trend Longevity) - prerequisites not met")
            elif "stage_9_5_trend_longevity" in completed_stages:
                logger.info("Skipping Stage 9.5 (Trend Longevity) - already completed")

            # Stage 9.6: Only run if not already completed (listener stage)
            if current <= 9.6 and "stage_9_6_seo_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(9.6):
                    self.stage_9_6_refine_seo_scores()
                else:
                    logger.info("Skipping Stage 9.6 (SEO Refinement) - prerequisites not met")
            elif "stage_9_6_seo_refinement" in completed_stages:
                logger.info("Skipping Stage 9.6 (SEO Refinement) - already completed")

            # Stage 9.7: Only run if not already completed (listener stage)
            if current <= 9.7 and "stage_9_7_data_sources" not in completed_stages:
                if self._validate_stage_prerequisites(9.7):
                    self.stage_9_7_research_data_sources()
                else:
                    logger.info("Skipping Stage 9.7 (Data Source Research) - prerequisites not met")
            elif "stage_9_7_data_sources" in completed_stages:
                logger.info("Skipping Stage 9.7 (Data Source Research) - already completed")

            if current <= 10:
                self.stage_10_generate_report()

            # Return the actual report path stored during stage 10
            if hasattr(self, 'report_path') and self.report_path:
                return self.report_path

        except Exception as e:
            logger.error(f"Error during stage execution: {e}")
            self.state.errors.append(f"Resume execution failed: {str(e)}")
            raise

        return ""

    # ========== STAGE METHODS ==========

    @start()
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

        self.state.current_stage = 5
        self._mark_stage_complete(1)

        # Checkpoint: Save niche context for resume
        self.checkpoint_mgr.save_stage("stage_1_niche_context", self.state.niche_context)

    def _generate_niche_context(self, niche_input: str) -> "NicheContext":
        """Generate structured NicheContext using LLM with structured output."""
        from ..models.research_state import NicheContext
        from ..utils.llm_service import LLMService

        prompt = f"""You are a market research analyst analyzing a niche market.

**Niche Input:** {niche_input}

**Your Task:**
Generate a structured analysis of this niche with the following:

1. **niche_description**:
   - 2-3 sentence refined description of this niche
   - Clarify what this market encompasses
   - Make it specific and actionable

2. **market_segments**:
   - List 3-7 distinct market segments within this niche
   - Be specific (e.g., "Small e-commerce businesses with 10-50 employees" not just "small businesses")
   - Focus on segments that might have different needs or buying patterns

3. **industry_boundaries**:
   - 2-3 sentences defining what is IN scope vs OUT of scope for this niche
   - Clarify adjacent markets or related areas that are NOT part of this niche
   - Help focus the research on the right target market

Be specific and actionable. Provide strategic insights.

Return a valid JSON object with this structure:
{{
  "niche_description": "...",
  "market_segments": ["segment 1", "segment 2", "..."],
  "industry_boundaries": "..."
}}"""

        # Use centralized LLM service for structured output
        # Moderate temperature (0.5) for balanced understanding + structured strategy
        context, usage = LLMService.invoke_structured(
            prompt=prompt,
            output_model=NicheContext,
            temperature=0.5,
            timeout=120,
            model_name=settings.openai_model_name
        )

        # Record cost if tracker is available
        if hasattr(self, 'cost_tracker') and self.cost_tracker:
            self.cost_tracker.record_llm_usage("Stage 1 - Niche Context", usage.to_dict())

        # Add niche_input to the context
        context.niche_input = niche_input
        return context

    @listen(stage_1_validate_niche)
    def stage_5_search_and_discover(self):
        """
        Stage 5: Search & Discover

        Uses SerperDevTool to find relevant social discussions on Reddit and Twitter.
        """
        logger.info("=" * 80)
        logger.info("STAGE 5: Search & Discover")
        logger.info("=" * 80)
        self._emit_progress(5, "Search & Discovery", "running")

        # Generate strategic search queries
        from ..utils.generation import QueryGenerator
        query_gen = QueryGenerator()

        logger.info(f"Generating {settings.num_search_queries} strategic search queries...")
        queries = query_gen.generate_queries(
            niche_description=self.niche_description,
            niche_context=self.state.niche_context,
            num_queries=settings.num_search_queries
        )

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

        # Initialize thread relevance validator (used for both Reddit and Twitter)
        from ..utils.validation import ThreadRelevanceValidator
        validator = ThreadRelevanceValidator()

        # Search Reddit (conditional)
        reddit_urls = []
        unique_reddit_results = []

        if settings.enable_reddit:
            # Filter to Reddit-applicable queries (platform: reddit or both)
            reddit_queries = [q for q in self.state.search_queries if q.platform in ("reddit", "both")]
            logger.info(f"Searching Reddit for relevant discussions ({len(reddit_queries)}/{len(self.state.search_queries)} queries)...")
            reddit_results = []
            for search_query in reddit_queries:
                try:
                    results = self.search_tool.run(
                        search_query=f"site:reddit.com {search_query.query}"
                    )
                    search_items = SearchHelper.extract_results_from_serper(results, "reddit.com")
                    reddit_results.extend(search_items)
                except Exception as e:
                    logger.error(f"Reddit search failed for '{search_query.query}': {e}")

            # Deduplicate results by URL
            seen_urls = set()
            for result in reddit_results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_reddit_results.append(result)

            logger.info(f"[OK] Found {len(unique_reddit_results)} unique Reddit results from {len(reddit_queries)} queries")

            # Validate relevance using cheap model (gpt-4o-mini) with parallel processing
            logger.info("Validating Reddit thread relevance...")
            validated_reddit = validator.validate_batch_parallel(
                niche_description=self.niche_description,
                search_results=unique_reddit_results,
                batch_size=10
                # max_workers defaults to settings.thread_validation_max_workers (2)
            )

            # Filter to relevant results only
            reddit_urls = [result.url for result, is_relevant in validated_reddit if is_relevant]
            filtered_count = len(unique_reddit_results) - len(reddit_urls)
            logger.info(f"[OK] Filtered {filtered_count} irrelevant threads, kept {len(reddit_urls)} relevant Reddit discussions")
        else:
            logger.info("Reddit collection disabled (ENABLE_REDDIT=false) - skipping Reddit search")

        # Search Twitter
        twitter_urls = []
        twitter_threads = []

        if settings.enable_twitter:
            # Filter to Twitter-applicable queries (platform: twitter or both)
            twitter_queries = [q for q in self.state.search_queries if q.platform in ("twitter", "both")]
            logger.info(f"Searching Twitter/X for relevant discussions ({len(twitter_queries)}/{len(self.state.search_queries)} queries)...")
            twitter_results = []
            for search_query in twitter_queries:
                try:
                    results = self.search_tool.run(
                        search_query=f"(site:twitter.com OR site:x.com) {search_query.query}"
                    )
                    # Extract both twitter.com and x.com results
                    twitter_results_1 = SearchHelper.extract_results_from_serper(results, "twitter.com")
                    twitter_results_2 = SearchHelper.extract_results_from_serper(results, "x.com")
                    twitter_results.extend(twitter_results_1 + twitter_results_2)
                except Exception as e:
                    logger.error(f"Twitter search failed for '{search_query.query}': {e}")

            # Deduplicate results by URL
            seen_urls = set()
            unique_twitter_results = []
            for result in twitter_results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    unique_twitter_results.append(result)

            logger.info(f"[OK] Found {len(unique_twitter_results)} unique Twitter results from {len(twitter_queries)} queries")

            # Validate relevance using cheap model (gpt-4o-mini) with parallel processing
            logger.info("Validating Twitter thread relevance...")
            validated_twitter = validator.validate_batch_parallel(
                niche_description=self.niche_description,
                search_results=unique_twitter_results,
                batch_size=10
                # max_workers defaults to settings.thread_validation_max_workers (2)
            )

            # Filter to relevant results only
            twitter_urls = [result.url for result, is_relevant in validated_twitter if is_relevant]
            filtered_count = len(unique_twitter_results) - len(twitter_urls)
            logger.info(f"[OK] Filtered {filtered_count} irrelevant threads, kept {len(twitter_urls)} relevant Twitter discussions")

            # Collect Reddit and Twitter content in parallel
            if settings.enable_reddit:
                logger.info("Collecting Reddit and Twitter content in parallel...")
                from ..utils.parallel_collection import ParallelCollector

                collection_tasks = [
                    ("reddit", lambda: self.reddit_tool.collect_posts(reddit_urls)),
                    ("twitter", lambda: self.twitter_tool.collect_threads(twitter_urls))
                ]

                results = ParallelCollector.collect_parallel(collection_tasks, max_workers=2)
                reddit_posts = results.get("reddit", [])
                twitter_threads = results.get("twitter", [])

                logger.info(f"[OK] Parallel collection completed:")
                logger.info(f"    - Reddit: {len(reddit_posts)} quality posts")
                logger.info(f"    - Twitter: {len(twitter_threads)} quality threads")
            else:
                # Twitter only (Reddit disabled)
                logger.info("Collecting Twitter threads (Reddit disabled)...")
                reddit_posts = []
                twitter_threads = self.twitter_tool.collect_threads(twitter_urls)
                logger.info(f"[OK] Collected {len(twitter_threads)} quality Twitter threads")
        elif settings.enable_reddit:
            logger.info("Twitter collection disabled (ENABLE_TWITTER=false) - skipping Twitter search")
            # Collect Reddit content only
            logger.info("Collecting Reddit posts and comments...")
            reddit_posts = self.reddit_tool.collect_posts(reddit_urls)
            twitter_threads = []
            logger.info(f"[OK] Collected {len(reddit_posts)} quality Reddit posts")
        else:
            # Both disabled
            logger.warning("Both Reddit and Twitter collection disabled - no social content will be collected")
            reddit_posts = []
            twitter_threads = []

        # Hard stop if no social content collected from either platform
        if len(reddit_posts) == 0 and len(twitter_threads) == 0:
            logger.error("=" * 80)
            logger.error("PIPELINE STOPPED: No social content collected from either platform")
            logger.error("Cannot proceed without data. Possible causes:")
            logger.error("  - Twitter rate limiting (most common)")
            logger.error("  - Reddit API issues")
            logger.error("  - No relevant content found for niche")
            logger.error("=" * 80)
            raise ValueError("No social content collected from either Reddit or Twitter. Cannot proceed with research pipeline.")

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

            # Log combined estimate
            total_chars = reddit_char_count + twitter_char_count
            # Rough token estimate (1 token ≈ 4 chars)
            estimated_tokens = total_chars // 4
            logger.info(
                f"Stage 5 - Total collected content: ~{total_chars:,} characters "
                f"(~{estimated_tokens:,} tokens estimated)"
            )

        # Store in social_content collection
        from ..models.social_content import SocialContentCollection
        self.state.social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=twitter_threads
        )

        # Track filtering statistics (Phase 2.5: Data quality transparency)
        # This enables understanding of false negative rates in URL filtering
        reddit_searched = len(unique_reddit_results)
        reddit_relevant = len(reddit_urls)
        twitter_searched = len(unique_twitter_results) if settings.enable_twitter else 0
        twitter_relevant = len(twitter_urls) if settings.enable_twitter else 0

        self.state.filtering_stats = {
            "reddit_urls_searched": reddit_searched,
            "reddit_urls_relevant": reddit_relevant,
            "reddit_filtering_rate": (reddit_searched - reddit_relevant) / reddit_searched if reddit_searched > 0 else 0,
            "twitter_urls_searched": twitter_searched,
            "twitter_urls_relevant": twitter_relevant,
            "twitter_filtering_rate": (twitter_searched - twitter_relevant) / twitter_searched if twitter_searched > 0 else 0,
            "total_urls_searched": reddit_searched + twitter_searched,
            "total_urls_relevant": reddit_relevant + twitter_relevant,
            "overall_filtering_rate": (
                (reddit_searched + twitter_searched - reddit_relevant - twitter_relevant) /
                (reddit_searched + twitter_searched)
            ) if (reddit_searched + twitter_searched) > 0 else 0,
        }
        logger.info(
            f"[Filtering Stats] Reddit: {reddit_relevant}/{reddit_searched} relevant "
            f"({self.state.filtering_stats['reddit_filtering_rate']*100:.1f}% filtered)"
        )
        if settings.enable_twitter:
            logger.info(
                f"[Filtering Stats] Twitter: {twitter_relevant}/{twitter_searched} relevant "
                f"({self.state.filtering_stats['twitter_filtering_rate']*100:.1f}% filtered)"
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
            self.state.errors.append(f"Stage 5: Insufficient social content quality ({quality_tier})")

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 6

        # Mark stage complete with tracking
        self._mark_stage_complete(5, used_fallback=(quality_tier == "INSUFFICIENT"))

        # Checkpoint: Save social content
        self.checkpoint_mgr.save_stage("stage_5_social_content", self.state.social_content)

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
            niche_description=self.niche_description,
            market_segments=self.state.niche_context.market_segments,
            industry_boundaries=self.state.niche_context.industry_boundaries
        )

        result = pain_point_crew.analyze()
        logger.info(f"[Parallel] PainPointCrew complete: {len(result.pain_points) if result else 0} pain points")

        return {
            "result": result,
            "usage_metrics": pain_point_crew.usage_metrics
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

        audience_crew = AudienceMappingCrew(
            reddit_posts=self.state.social_content.reddit_posts if self.state.social_content else [],
            twitter_threads=self.state.social_content.twitter_threads if self.state.social_content else [],
            niche_description=self.niche_description
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

        return {
            "result": result,
            "usage_metrics": audience_crew.usage_metrics
        }

    @listen(stage_5_search_and_discover)
    def stage_6_analyze_pain_points(self):
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
        self._emit_progress(6, "Pain Point Analysis", "running")

        if not self.state.social_content or (not self.state.social_content.reddit_posts and not self.state.social_content.twitter_threads):
            logger.warning("No social content collected. Skipping pain point analysis.")
            self.state.current_stage = 7
            self.checkpoint_mgr.save_stage("stage_6_pain_points", {"skipped": True, "reason": "No social content collected"})
            return

        # ANTI-HALLUCINATION CHECK: Verify content quality
        total_discussions = len(self.state.social_content.reddit_posts) + len(self.state.social_content.twitter_threads)
        total_comments = sum(len(post.comments) for post in self.state.social_content.reddit_posts)
        total_replies = sum(len(thread.replies) for thread in self.state.social_content.twitter_threads)
        total_engagement = total_comments + total_replies

        if total_discussions < 3:
            logger.warning(
                f"Insufficient social content quality ({total_discussions} discussions, minimum 3 required) "
                f"- skipping pain point analysis to prevent hallucination"
            )
            self.state.current_stage = 7
            self.checkpoint_mgr.save_stage("stage_6_pain_points", {"skipped": True, "reason": f"Insufficient content quality: {total_discussions} discussions < 3 minimum"})
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
        logger.info("[Stage 6] Running PainPointCrew and AudienceMappingCrew in PARALLEL...")

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
                        logger.info("[Parallel] PainPointCrew finished successfully")
                    else:  # audience
                        audience_result = result_dict["result"]
                        audience_usage = result_dict["usage_metrics"]
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
                logger.info(f"  - {pp.title} (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay:.2f})")

        # Quality Gate: Validate pain point analysis quality
        quality_tier, confidence_score = self._validate_pain_point_quality(self.state.pain_point_analysis)
        self.state.pain_point_quality_tier = quality_tier
        self.state.pain_point_confidence_score = confidence_score

        # Decision: Proceed based on quality tier
        if quality_tier == "INSUFFICIENT":
            logger.warning("Pain point quality insufficient - stopping pipeline (intentional quality gate)")
            logger.warning("Recommendation: Expand social content collection or refine niche focus")
            self.state.errors.append(
                f"Stage 6 quality gate failed: {quality_tier} tier (confidence: {confidence_score:.2f})"
            )
            # Save checkpoint with current state
            self.checkpoint_mgr.save_stage("stage_6_pain_points", self.state.pain_point_analysis)

            # Calculate metrics for the stop details
            pain_points = self.state.pain_point_analysis.pain_points if self.state.pain_point_analysis else []
            total_count = len(pain_points)
            quote_density = sum(len(pp.representative_quotes) for pp in pain_points) / total_count if total_count > 0 else 0
            sourced_count = len([pp for pp in pain_points if pp.source_post_ids])
            source_coverage = sourced_count / total_count if total_count > 0 else 0

            raise QualityGateStopException(
                stage=6,
                reason="INSUFFICIENT_DATA",
                details={
                    "qualityTier": quality_tier,
                    "confidenceScore": confidence_score,
                    "metrics": {
                        "painPointCount": total_count,
                        "quoteDensity": round(quote_density, 2),
                        "sourceCoverage": round(source_coverage, 2),
                    },
                    "recommendation": "Expand social content collection or refine niche focus"
                }
            )

        # Quality tier acceptable - proceed with pipeline
        logger.info(f"Quality gate passed - proceeding with {quality_tier} tier data (confidence: {confidence_score:.2f})")

        # Mark Stage 6 complete
        is_fallback = (quality_tier == "BRONZE" and settings.enable_twitter)
        self._mark_stage_complete(6, used_fallback=is_fallback)

        # Checkpoint: Save pain point analysis
        self.checkpoint_mgr.save_stage("stage_6_pain_points", self.state.pain_point_analysis)

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

            # Mark Stage 6.5 complete
            self._mark_stage_complete(6.5)

            # Checkpoint: Save audience mapping
            self.checkpoint_mgr.save_stage("stage_6_5_audience_mapping", audience_result)

            logger.info("[Stage 6.5] Audience Mapping Complete (parallel)")
            logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
            logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
            logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
            logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
            logger.info(f"  Recommended Channels: {', '.join(audience_result.recommended_channels[:3])}")
        else:
            logger.warning("[Stage 6.5] Audience mapping failed (parallel) - continuing without audience data")

        # Update stage - both 6 and 6.5 are now complete
        self.state.current_stage = 7
        self._emit_progress(6.5, "Audience Mapping", "completed")

        logger.info("[Stage 6] Parallel execution complete - PainPointCrew + AudienceMappingCrew")

    @listen(stage_6_analyze_pain_points)
    def stage_6_5_audience_mapping(self):
        """
        Stage 6.5: Audience & Influence Mapping (Pass-through)

        NOTE: Audience mapping now runs in parallel with Stage 6 for performance.
        This method is a pass-through that verifies results are available.

        If audience mapping failed in parallel execution, this stage can retry sequentially.
        """
        # Check if audience mapping was already completed in parallel
        if self.state.audience_mapping:
            logger.info("[Stage 6.5] Audience mapping already completed (parallel execution)")
            self.state.current_stage = 7
            return

        # Fallback: Run sequentially if parallel execution failed
        logger.info("=" * 80)
        logger.info("STAGE 6.5: Audience & Influence Mapping (Sequential Fallback)")
        logger.info("=" * 80)
        self._emit_progress(6.5, "Audience Mapping", "running")

        # Check if we have required data
        if not self.state.social_content:
            logger.warning("[Stage 6.5] No social content - skipping audience mapping")
            self.state.current_stage = 7
            return

        if not self.state.pain_point_analysis:
            logger.warning("[Stage 6.5] No pain point analysis - skipping audience mapping")
            self.state.current_stage = 7
            return

        # Run audience mapping crew sequentially (fallback)
        logger.info(f"[Stage 6.5] Running AudienceMappingCrew sequentially (fallback)...")

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
            logger.warning("[Stage 6.5] Audience mapping failed - continuing without audience data")
            self.state.current_stage = 7
            return

        # Store result
        self.state.audience_mapping = audience_result
        self.state.current_stage = 7

        # Post-processing: Map pain points to audience segments
        if self.state.pain_point_analysis and audience_result.audience_segments:
            self._map_pain_points_to_segments(audience_result)

        # Mark stage complete with tracking
        self._mark_stage_complete(6.5)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_6_5_audience_mapping", audience_result)

        logger.info("[Stage 6.5] Audience Mapping Complete (fallback)")
        logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
        logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
        logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
        logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
        logger.info(f"  Recommended Channels: {', '.join(audience_result.recommended_channels[:3])}")

    @listen(stage_6_5_audience_mapping)
    def stage_7_unified_solution_pipeline(self):
        """
        Stage 7: Unified Solution Pipeline (CrewAI Best Practice)

        Consolidates stages using UnifiedSolutionCrew with context chaining:
        - Task 7.1: Solution Ideation (brainstorm + evaluate + refine)
        - Task 7.2: Competitive Analysis (research + gap analysis)
        - Task 7.3: Competitive Refinement (enhance with insights)
        - Task 7.4: Solution Selection (strategic scoring and selection)

        Benefits:
        - Automatic field preservation via output_pydantic + context
        - No manual data formatting between stages
        - Guardrails prevent data loss
        - Follows CrewAI documentation best practices
        """
        logger.info("=" * 80)
        logger.info("STAGES 7-8.75: Unified Solution Pipeline")
        logger.info("=" * 80)
        self._emit_progress(7, "Solution Pipeline", "running")

        # Prerequisites check
        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            error_msg = "No pain points available - cannot proceed with solution pipeline"
            logger.error(error_msg)
            self.checkpoint_mgr.save_stage("stage_7_skipped", {"skipped": True, "reason": "No pain points available"})
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
            self.checkpoint_mgr.save_stage("stage_7_skipped", {"skipped": True, "reason": "No high/medium priority pain points"})
            raise RuntimeError(f"Stage 7 failed: {error_msg}")

        logger.info(
            f"Pain point quality check: {len(high_priority)} high-priority, "
            f"{len(medium_priority)} medium-priority pain points"
        )

        try:
            # Initialize UnifiedSolutionCrew with audience intelligence from Stage 6.5
            unified_crew = UnifiedSolutionCrew(
                pain_point_analysis=self.state.pain_point_analysis,
                social_content=self.state.social_content,
                allowed_project_types=self.allowed_project_types,
                niche_context=self.state.niche_context,
                audience_mapping=self.state.audience_mapping,
                checkpoint_mgr=self.checkpoint_mgr
            )

            # Execute complete pipeline (6 tasks in sequence with context chaining)
            logger.info("Executing unified solution pipeline (6-task flow)...")
            (
                refined_solutions,
                competitive_analysis,
                solution_selection,
                competitive_enhancements,
            ) = unified_crew.execute_pipeline()

            # Record crew cost
            if unified_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 7 - Unified Solution Pipeline",
                    usage_metrics=unified_crew.usage_metrics,
                    model=settings.brainstorm_llm
                )

            # Save results to state
            self.state.idea_generation = refined_solutions
            self.state.competitive_analysis = competitive_analysis
            self.state.solution_selection = solution_selection
            self.state.competitive_enhancements = competitive_enhancements  # Preserves overall_competitive_insights

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

                    # Track fallback for visibility
                    if not hasattr(self.state, 'fallback_stages'):
                        self.state.fallback_stages = []
                    self.state.fallback_stages.append(7.4)
                else:
                    logger.error(
                        "⚠️ Fallback failed - no solutions available in idea_generation. "
                        "Pipeline will proceed with invalid selection name."
                    )

            # Log results
            logger.info("[OK] Solution Pipeline Complete:")
            logger.info(f"  - Generated {len(refined_solutions.solution_ideas)} solutions")
            logger.info(f"  - Analyzed {len(competitive_analysis.solution_landscapes)} competitive landscapes")
            logger.info(f"  - Selected: {solution_selection.selected_solution_name}")

            # Update stage (continue to keyword validation)
            self.state.current_stage = 8.8

            # Mark stage complete with tracking
            self._mark_stage_complete(7)

            # Checkpoints saved internally by UnifiedSolutionCrew.execute_pipeline()
            # All 6 task outputs checkpointed: stage_7_1 through stage_7_6
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
    ) -> list:
        """
        Phase 9.5c: Iteratively enrich keywords with DataForSEO using VALIDATED seeds.

        Uses VALIDATED seeds (pre-filtered by get_search_volume in Phase 9.5b) instead of
        raw conceptual keywords to maximize success rate and reduce API waste.

        NEW: Adds LLM-based relevance validation after expansion to filter out irrelevant
        keywords (e.g., "find my device", "discover card", "dental labs").

        Args:
            conceptual_keywords: Full list of ConceptualKeyword objects for cluster coverage calculation
            validated_seeds: Pre-validated keywords with search volume (from Phase 9.5b bulk validation)
            topic_clusters: List of ConceptualTopicCluster objects from Phase 9.5a
            selected_solution: Selected SolutionIdea for relevance validation (optional)
            niche_context: NicheContext for relevance validation (optional)

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

        # Initialize with pre-validated keywords
        all_enriched = validated_seeds.copy()
        seeds_used = set()
        # Track enriched keyword strings for deduplication across rounds
        enriched_keyword_strings = {kw['keyword'].lower() for kw in all_enriched}
        max_rounds = settings.keyword_enrichment_max_rounds

        logger.info(f"Starting with {len(all_enriched)} pre-validated keywords from bulk validation")

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
            logger.info(f"[Round {round_num}] Validating {len(suggestions)} expanded keywords...")
            validation_results = validator.validate_batch_parallel(
                keywords=suggestions,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type,
                batch_size=settings.keyword_validation_batch_size,
                threshold=settings.keyword_relevance_threshold
                # max_workers defaults to settings.keyword_validation_max_workers (3)
            )

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
                and coverage >= settings.keyword_enrichment_min_coverage
            ):
                logger.info(f"✓ Enrichment target reached after {round_num} rounds")
                break

        logger.info(
            f"Enrichment complete: {len(all_enriched)} keywords discovered, "
            f"{len(quality_keywords)} with volume >= {settings.keyword_enrichment_min_volume}"
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

        NOTE: As of Phase 9.5b redesign, conceptual_keywords contains only
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

        # Run pricing analysis
        pricing_result = pricing_crew.analyze(
            selected_solution=solution,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description,
            allowed_project_types=self.state.allowed_project_types
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

    @listen(stage_7_unified_solution_pipeline)
    def stage_8_pricing_validation(self):
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
        self._emit_progress(8, "Pricing Validation", "running")

        # Check if we have solution selection with scores
        if not self.state.solution_selection:
            logger.warning("[Stage 8] No solution selected - skipping pricing validation")
            self.state.current_stage = 8.5
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 8] No pain point analysis - skipping pricing validation")
            self.state.current_stage = 8.5
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 8] No competitive analysis - skipping pricing validation")
            self.state.current_stage = 8.5
            return

        # Check if we have idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 8] No solution ideas - skipping pricing validation")
            self.state.current_stage = 8.5
            return

        # Get top N solutions from all_solution_scores (like keyword validation)
        all_scores = self.state.solution_selection.all_solution_scores
        if not all_scores or len(all_scores) < 1:
            logger.warning("[Stage 8] No solution scores available - skipping")
            self.state.current_stage = 8.5
            return

        # Sort by composite score and take top N (configurable)
        top_n_scores = sorted(all_scores, key=lambda s: s.composite_score, reverse=True)[:settings.top_solutions_for_validation]

        logger.info(f"[Stage 8] Analyzing pricing for top {len(top_n_scores)} solutions (PARALLEL)")

        # Resume support: track already validated solutions
        pricing_results = []
        already_validated = set()
        if self.state.pricing_strategies:
            pricing_results = list(self.state.pricing_strategies)
            already_validated = {p.solution_name for p in pricing_results}
            if already_validated:
                logger.info(f"[Stage 8] Resuming - {len(already_validated)} solutions already validated: {already_validated}")

        # Filter solutions that need validation
        solutions_to_validate = [
            solution_score.solution_name
            for solution_score in top_n_scores
            if solution_score.solution_name not in already_validated
        ]

        if not solutions_to_validate:
            logger.info("[Stage 8] All solutions already validated - skipping")
            self.state.current_stage = 8.5
            self._mark_stage_complete(8)
            return

        logger.info(f"[Stage 8] Validating {len(solutions_to_validate)} solutions in parallel (max_workers=2)")

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
                        logger.info(f"[Stage 8] Pricing validation complete: {solution_name}")

                        # Incremental checkpoint (thread-safe: append only)
                        self.state.pricing_strategies = pricing_results
                        self.checkpoint_mgr.save_stage(
                            "stage_8_pricing_validation",
                            [p.model_dump() for p in pricing_results]
                        )
                    else:
                        logger.warning(f"[Stage 8] Pricing validation failed: {solution_name}")

                except Exception as e:
                    logger.error(f"[Stage 8] Pricing validation error for {solution_name}: {e}")

        # Store final results
        self.state.pricing_strategies = pricing_results
        self.state.current_stage = 8.5

        # Mark stage complete with tracking
        self._mark_stage_complete(8)

        logger.info(f"[Stage 8] Pricing Strategy Validation Complete - {len(pricing_results)}/{len(top_n_scores)} solutions analyzed (PARALLEL)")

    def _validate_solution_keywords(self, solution_name: str, audience_vocab: list | None) -> dict:
        """
        Helper method to validate keywords for a single solution (thread-safe).

        Creates new SeedGenerator instance per call for thread safety.

        Args:
            solution_name: Name of the solution to validate
            audience_vocab: Audience vocabulary from Stage 6.5

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
        seed_generator = SeedGenerator(
            state=self.state,
            niche_context=self.state.niche_context if hasattr(self.state, 'niche_context') else None,
            pain_point_analysis=self.state.pain_point_analysis if hasattr(self.state, 'pain_point_analysis') else None,
            audience_vocabulary=audience_vocab
        )

        # Adaptive keyword generation with pivot strategies
        accumulated_good_keywords = []
        accumulated_keyword_strings = set()
        best_relevance_score = 0.0
        best_validation_result = None
        max_attempts = getattr(settings, 'keyword_pivot_max_attempts', 4)
        relevance_threshold = getattr(settings, 'keyword_relevance_threshold', 0.6)
        keyword_validation_cache: dict[str, tuple] = {}
        final_attempt = 0

        for attempt in range(1, max_attempts + 1):
            final_attempt = attempt
            logger.info(f"[Parallel] {solution_name} - Attempt {attempt}/{max_attempts}")

            # Generate seeds with current strategy
            seeds = seed_generator.generate_seeds_with_strategy(solution, attempt, count=20)

            if not seeds:
                logger.warning(f"[Parallel] {solution_name} - Attempt {attempt}: No seeds generated")
                continue

            # Validate seeds with DataForSEO
            validation_result = seed_generator.validate_seeds_with_dataforseo(seeds, solution_name)

            # Quick expansion for relevance testing
            expanded_keywords = seed_generator.expand_seeds_quick(
                seeds,
                target_size=getattr(settings, 'keyword_quick_expansion_size', 50)
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

        # Return result
        if best_validation_result:
            best_validation_result["attempts_made"] = final_attempt
            best_validation_result["best_relevance_score"] = best_relevance_score
            best_validation_result["accumulated_keywords_count"] = len(accumulated_good_keywords)
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

    @listen(stage_8_pricing_validation)
    def stage_8_5_keyword_validation(self):
        """
        Stage 8.5: Quick Keyword Validation for Top N Solutions (Parallel Execution)

        Validates keyword demand for top N solutions in parallel for ~50% time savings.
        Each solution's keyword validation (including adaptive pivot strategies) runs independently.

        Adjusts composite scores based on actual market search behavior.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.5: Keyword Demand Validation (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(8.5, "Keyword Validation", "running")

        # Check if feature is enabled
        if not getattr(settings, 'keyword_validation_enabled', True):
            logger.info("[Stage 8.5] Keyword validation disabled - skipping")
            self.state.current_stage = 8.6
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.5] No solution selected - skipping keyword validation")
            self.state.current_stage = 8.6
            return

        # Get top N solutions from all_solution_scores (configurable)
        all_scores = self.state.solution_selection.all_solution_scores
        if not all_scores or len(all_scores) < 1:
            logger.warning("[Stage 8.5] No solution scores available - skipping")
            self.state.current_stage = 8.6
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
                logger.info(f"[Stage 8.5] Added selected solution '{selected_name}' to validation set")

        logger.info(f"[Stage 8.5] Validating keyword demand for {len(top_n_scores)} solutions (PARALLEL)")

        # Resume support: Load existing validation results
        validation_results = []
        already_validated = set()
        if self.state.keyword_validation_results:
            validation_results = list(self.state.keyword_validation_results)
            already_validated = {v.solution_name for v in validation_results}
            if already_validated:
                logger.info(f"[Stage 8.5] Resuming - {len(already_validated)} solutions already validated")

        # Extract audience vocabulary for keyword grounding
        audience_vocab = (
            self.state.audience_mapping.common_vocabulary
            if self.state.audience_mapping else None
        )
        if audience_vocab:
            logger.info(f"[Stage 8.5] Using {len(audience_vocab)} audience vocabulary terms")

        # Filter solutions that need validation
        solutions_to_validate = [
            solution_score.solution_name
            for solution_score in top_n_scores
            if solution_score.solution_name not in already_validated
        ]

        if not solutions_to_validate:
            logger.info("[Stage 8.5] All solutions already validated - skipping to post-processing")
        else:
            logger.info(f"[Stage 8.5] Validating {len(solutions_to_validate)} solutions in parallel (max_workers=2)")

            # Run keyword validation in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit all keyword validation tasks
                futures = {
                    executor.submit(self._validate_solution_keywords, solution_name, audience_vocab): solution_name
                    for solution_name in solutions_to_validate
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    solution_name = futures[future]
                    try:
                        result_dict = future.result()
                        validation_result = result_dict["validation_result"]

                        if validation_result:
                            # Convert dict to Pydantic object
                            validation_obj = CrewKeywordValidationResult(**validation_result)
                            validation_results.append(validation_obj)

                            logger.info(
                                f"[Stage 8.5] Keyword validation complete: {solution_name} "
                                f"({result_dict['attempts_made']} attempts, relevance={result_dict['best_relevance_score']:.2f})"
                            )

                            # Incremental checkpoint (thread-safe: append only)
                            self.state.keyword_validation_results = validation_results
                            self.checkpoint_mgr.save_stage(
                                "stage_8_5_keyword_validation_partial",
                                [v.model_dump() for v in validation_results]
                            )
                        else:
                            logger.warning(f"[Stage 8.5] Keyword validation failed: {solution_name}")

                    except Exception as e:
                        logger.error(f"[Stage 8.5] Keyword validation error for {solution_name}: {e}")

        # Store validation results in state
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
                    f"[Stage 8.5] {solution_score.solution_name} not in top-3 validation set - "
                    f"preserving existing scores (composite: {solution_score.composite_score:.2f})"
                )
                # If the solution had no keyword scores, set to base composite score
                if solution_score.adjusted_composite_score is None:
                    solution_score.adjusted_composite_score = solution_score.composite_score

        # Re-score solutions using keyword demand
        logger.info("[Stage 8.5] Re-scoring solutions with keyword demand data")

        for validation in validation_results:
            # Find corresponding solution score
            for solution_score in all_scores:
                if solution_score.solution_name == validation.solution_name:
                    # Store keyword demand score
                    solution_score.keyword_demand_score = validation.keyword_demand_score

                    # Calculate adjusted composite score
                    base_score = solution_score.composite_score
                    keyword_multiplier = validation.keyword_demand_score
                    solution_score.adjusted_composite_score = base_score * keyword_multiplier

                    logger.info(
                        f"[Stage 8.5] {solution_score.solution_name}: "
                        f"base={base_score:.2f}, keyword_demand={keyword_multiplier:.2f}, "
                        f"adjusted={solution_score.adjusted_composite_score:.2f}"
                    )
                    break

        # Re-rank solutions by adjusted score (ONLY validated solutions)
        # Bug fix: Previously included non-validated solutions which kept raw composite_score
        # as adjusted_composite_score, giving them unfair advantage over validated ones
        ranked_solutions = sorted(
            [s for s in all_scores if s.solution_name in validated_names],
            key=lambda s: s.adjusted_composite_score or 0.0,
            reverse=True
        )

        if ranked_solutions:
            new_winner = ranked_solutions[0].solution_name
            original_winner = self.state.solution_selection.selected_solution_name

            if new_winner != original_winner:
                logger.warning(
                    f"[Stage 8.5] Winner changed after keyword validation: "
                    f"{original_winner} → {new_winner}"
                )
                self.state.solution_selection.selected_solution_name = new_winner

                # Update rationale
                self.state.solution_selection.selection_rationale += (
                    f"\n\n**Keyword Validation Update:** "
                    f"Final selection updated to {new_winner} based on stronger keyword demand "
                    f"(demand score: {ranked_solutions[0].keyword_demand_score or 0.0:.2f} vs "
                    f"{next((s.keyword_demand_score for s in all_scores if s.solution_name == original_winner), None) or 0.0:.2f} "
                    f"for {original_winner})."
                )

                # Update runner_up_solutions to reflect new ranking after pivot
                new_runner_ups = []
                for score in ranked_solutions[1:]:  # Skip position 0 (new winner)
                    if score.solution_name not in new_runner_ups:
                        new_runner_ups.append(score.solution_name)
                    if len(new_runner_ups) >= 3:  # Keep top 3 runner-ups
                        break

                # Add original winner if not already in list (it should be a runner-up now)
                if original_winner not in new_runner_ups:
                    new_runner_ups.insert(0, original_winner)
                    if len(new_runner_ups) > 3:
                        new_runner_ups = new_runner_ups[:3]

                self.state.solution_selection.runner_up_solutions = new_runner_ups
                logger.info(f"[Stage 8.5] Updated runner-ups after pivot: {new_runner_ups}")
            else:
                logger.info(f"[Stage 8.5] Winner confirmed by keyword validation: {new_winner}")

        # Update stage and checkpoint
        self.state.current_stage = 8.6

        # Mark stage complete with tracking
        self._mark_stage_complete(8.5)

        # Save keyword validation results
        self.checkpoint_mgr.save_stage("stage_8_5_keyword_validation", validation_results)

        # FIX: Also save modified solution_selection to checkpoint (mutations happened above)
        # This ensures winner changes and rationale updates survive resume
        if self.state.solution_selection:
            self.checkpoint_mgr.save_stage(
                "stage_7_6_selection",
                self.state.solution_selection.model_dump()
            )
            logger.debug("[Stage 8.5] Updated solution_selection checkpoint after keyword re-ranking")

        logger.info(f"[Stage 8.5] Keyword validation complete - {len(validation_results)} solutions validated")

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
                keyword_validation_results=self.state.keyword_validation_results,
                competitive_analysis=self.state.competitive_analysis,
                niche_description=self.niche_description
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

    @listen(stage_8_5_keyword_validation)
    def stage_8_55_traffic_monetization(self):
        """
        Stage 8.55: Traffic Monetization Analysis (Parallel Execution)

        For traffic-based project types (directory, aggregator, comparison-tool),
        provides traffic monetization strategy instead of SaaS pricing.
        Runs in parallel for ~50% time savings.

        Uses keyword data from Stage 8.5 to estimate:
        - Traffic potential (monthly pageviews)
        - Ad revenue (CPM by niche)
        - Affiliate revenue opportunities
        - Sponsored listing potential
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.55: Traffic Monetization Analysis (PARALLEL)")
        logger.info("=" * 80)
        self._emit_progress(8.55, "Traffic Monetization", "running")

        # Traffic-based project types that use this crew
        traffic_types = ['directory', 'aggregator', 'comparison-tool']

        # Check prerequisites
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 8.55] No solution ideas - skipping traffic monetization")
            return

        if not self.state.keyword_validation_results:
            logger.warning("[Stage 8.55] No keyword validation results - skipping traffic monetization")
            return

        # Get solutions to analyze (same top N as Stage 8.5)
        if not self.state.solution_selection or not self.state.solution_selection.all_solution_scores:
            logger.warning("[Stage 8.55] No solution scores - skipping traffic monetization")
            return

        all_scores = self.state.solution_selection.all_solution_scores
        top_n_scores = sorted(
            all_scores,
            key=lambda s: s.composite_score,
            reverse=True
        )[:settings.top_solutions_for_validation]

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
                    f"[Stage 8.55] {solution.solution_name}: project_type='{solution.project_type}' "
                    f"→ Traffic monetization eligible"
                )

        if not traffic_solutions:
            logger.info(
                f"[Stage 8.55] No traffic-based solutions found in top {len(top_n_scores)} "
                f"(types: {traffic_types}). Skipping traffic monetization analysis."
            )
            return

        logger.info(f"[Stage 8.55] Analyzing {len(traffic_solutions)} traffic-based solutions (PARALLEL)")

        # Initialize results list (support resume)
        traffic_results = []
        already_analyzed = set()
        if self.state.traffic_monetization_results:
            traffic_results = list(self.state.traffic_monetization_results)
            already_analyzed = {r.solution_name for r in traffic_results}
            logger.info(f"[Stage 8.55] Resuming - {len(already_analyzed)} solutions already analyzed")

        # Filter solutions that need analysis
        solutions_to_analyze = [
            solution.solution_name
            for score, solution in traffic_solutions
            if solution.solution_name not in already_analyzed
        ]

        if not solutions_to_analyze:
            logger.info("[Stage 8.55] All solutions already analyzed - skipping")
            self._mark_stage_complete(8.55)
            return

        logger.info(f"[Stage 8.55] Analyzing {len(solutions_to_analyze)} solutions in parallel (max_workers=2)")

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
                            stage=f"Stage 8.55 - Traffic Monetization ({solution_name})",
                            usage_metrics=usage_metrics,
                            model=settings.openai_model_name
                        )

                    if result:
                        traffic_results.append(result)
                        logger.info(
                            f"[Stage 8.55] Traffic monetization complete: {solution_name} "
                            f"({result.monetization_model}, {result.estimated_monthly_revenue_range})"
                        )

                        # Incremental checkpoint (thread-safe: append only)
                        self.state.traffic_monetization_results = traffic_results
                        self.checkpoint_mgr.save_stage(
                            "stage_8_55_traffic_monetization_partial",
                            [r.model_dump() for r in traffic_results]
                        )
                    else:
                        logger.warning(f"[Stage 8.55] Traffic monetization failed: {solution_name}")

                except Exception as e:
                    logger.error(f"[Stage 8.55] Traffic monetization error for {solution_name}: {e}")

        # Store final results
        self.state.traffic_monetization_results = traffic_results

        # Mark stage complete with tracking
        self._mark_stage_complete(8.55)

        # Save checkpoint
        if traffic_results:
            self.checkpoint_mgr.save_stage(
                "stage_8_55_traffic_monetization",
                [r.model_dump() for r in traffic_results]
            )

        logger.info(
            f"[Stage 8.55] Traffic Monetization Analysis Complete - "
            f"{len(traffic_results)}/{len(traffic_solutions)} solutions analyzed (PARALLEL)"
        )

    @listen(stage_8_55_traffic_monetization)
    def stage_8_6_market_sizing(self):
        """
        Stage 8.6: Market Sizing & Validation

        Calculates TAM/SAM/SOM estimates and validates market attractiveness using:
        - Keyword search volumes (demand signals from Stage 8.5)
        - Pain point frequency (problem validation)
        - Competitive landscape (market saturation)
        - Selected solution positioning
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.6: Market Sizing & Validation")
        logger.info("=" * 80)
        self._emit_progress(8.6, "Market Sizing", "running")

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.6] No solution selected - skipping market sizing")
            self.state.current_stage = 8.7
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 8.6] No pain point analysis - skipping market sizing")
            self.state.current_stage = 8.7
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 8.6] No competitive analysis - skipping market sizing")
            self.state.current_stage = 8.7
            return

        # Check if we have idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("[Stage 8.6] No solution ideas - skipping market sizing")
            self.state.current_stage = 8.7
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 8.6] Selected solution '{selected_name}' not found")
            self.state.current_stage = 8.7
            return

        # Initialize and run market sizing crew
        from ..crews import MarketSizingCrew

        logger.info(f"[Stage 8.6] Calculating TAM/SAM/SOM for: {selected_name}")

        market_sizing_crew = MarketSizingCrew()

        # Get keyword validation for selected solution (Stage 8.5 runs before this)
        keyword_validation = None
        if hasattr(self.state, 'keyword_validation_results') and self.state.keyword_validation_results:
            # Find keyword validation for the selected solution
            keyword_validation = next(
                (v for v in self.state.keyword_validation_results if v.solution_name == selected_name),
                None
            )
            if keyword_validation:
                logger.info(f"[Stage 8.6] Using keyword validation data for {selected_name}")
            else:
                logger.info(f"[Stage 8.6] No keyword validation data found for {selected_name} - will use pain point and competitive data only")
        else:
            logger.info("[Stage 8.6] Keyword validation data not available - will calculate market size from pain points and competitive analysis")

        market_sizing_result = market_sizing_crew.analyze(
            selected_solution=selected_solution,
            keyword_validation=keyword_validation,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description
        )

        # Record crew cost
        if market_sizing_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 8.6 - Market Sizing",
                usage_metrics=market_sizing_crew.usage_metrics,
                model=settings.openai_model_name
            )

        # Check if analysis succeeded
        if not market_sizing_result:
            logger.warning("[Stage 8.6] Market sizing failed - continuing without market sizing data")
            self.state.current_stage = 8.7
            return

        # Store result
        self.state.market_sizing = market_sizing_result
        self.state.current_stage = 8.7

        # Mark stage complete with tracking
        self._mark_stage_complete(8.6)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_8_6_market_sizing", market_sizing_result)

        logger.info("[Stage 8.6] Market Sizing Complete")
        logger.info(f"  TAM: {market_sizing_result.total_addressable_market}")
        logger.info(f"  SAM: {market_sizing_result.serviceable_available_market}")
        logger.info(f"  SOM (Y1): {market_sizing_result.serviceable_obtainable_market_y1}")
        logger.info(f"  SOM (Y3): {market_sizing_result.serviceable_obtainable_market_y3}")
        logger.info(f"  Viability: {market_sizing_result.market_viability_verdict}")
        logger.info(f"  Entry Strategy: {market_sizing_result.recommended_entry_strategy}")

    @listen(stage_8_6_market_sizing)
    def stage_8_7_solution_refinement(self):
        """
        Stage 8.7: Solution Refinement Using Keyword Insights

        Generates strategic recommendations for selected solution based on keyword validation:
        - Geographic market priorities
        - Category/positioning pivots
        - Feature prioritization
        - Content strategy direction
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.7: Solution Refinement")
        logger.info("=" * 80)
        self._emit_progress(8.7, "Solution Refinement", "running")

        # Check if feature is enabled
        if not getattr(settings, 'solution_refinement_enabled', True):
            logger.info("[Stage 8.7] Solution refinement disabled - skipping")
            self.state.current_stage = 9
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.7] No solution selected - skipping refinement")
            self.state.current_stage = 9
            return

        # Check if we have keyword validation results
        if not self.state.keyword_validation_results:
            logger.warning("[Stage 8.7] No keyword validation results - skipping refinement")
            self.state.current_stage = 9
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 8.7] Selected solution '{selected_name}' not found")
            self.state.current_stage = 9
            return

        # Get keyword validation for selected solution
        keyword_validation = next(
            (v for v in self.state.keyword_validation_results if v.solution_name == selected_name),
            None
        )

        if not keyword_validation:
            logger.warning(f"[Stage 8.7] No keyword validation found for {selected_name}")
            self.state.current_stage = 9
            return

        # Early exit if demand is too weak
        if keyword_validation.demand_signal == "weak" and keyword_validation.total_volume < 2000:
            logger.warning(
                f"[Stage 8.7] Skipping refinement - weak demand signal "
                f"({keyword_validation.total_volume} monthly volume)"
            )
            self.state.current_stage = 9
            self.checkpoint_mgr.save_stage("stage_8_7_solution_refinement", {"skipped": True, "reason": "weak_demand"})
            return

        # Get composite score for context
        composite_score = next(
            (s.composite_score for s in self.state.solution_selection.all_solution_scores
             if s.solution_name == selected_name),
            0.0
        )

        # Initialize and run refinement crew
        logger.info(f"[Stage 8.7] Refining strategy for: {selected_name}")
        refinement_crew = SolutionRefinementCrew()

        refinement = refinement_crew.refine(
            selected_solution=selected_solution,
            keyword_validation=keyword_validation,
            composite_score=composite_score,
            allowed_project_types=self.state.allowed_project_types
        )

        # Record crew cost
        if refinement_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 8.7 - Solution Refinement",
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
                                    f"**Stage 8.7 Refinements:**\n"
                                    f"- Geographic priorities: {', '.join(refinement.geographic_priorities[:3])}\n"
                                    f"- Category pivot: {refinement.category_pivot_recommendation or 'None'}\n"
                                    f"- Key insight: {refinement.strategic_insights[0] if refinement.strategic_insights else 'N/A'}"
                                )
                            logger.info(f"[Stage 8.7] Merged refinements into solution '{selected_name}'")
                        break

            logger.info(
                f"[Stage 8.7] Refinement complete:\n"
                f"  - Geographic priorities: {', '.join(refinement.geographic_priorities[:3])}\n"
                f"  - Category pivot: {refinement.category_pivot_recommendation or 'None'}\n"
                f"  - Feature priorities: {len(refinement.feature_priorities)} recommendations\n"
                f"  - Strategic insights: {len(refinement.strategic_insights)} insights"
            )

            # Update stage first, then checkpoint (Pattern A - safer for resume)
            self.state.current_stage = 9

            # Mark stage complete with tracking
            self._mark_stage_complete(8.7)

            self.checkpoint_mgr.save_stage("stage_8_7_solution_refinement", refinement.model_dump())
        else:
            logger.warning("[Stage 8.7] Refinement failed - proceeding without refinement data")
            # Update stage first, then checkpoint (Pattern A - safer for resume)
            self.state.current_stage = 9

            # Mark stage complete with tracking (used fallback since refinement failed)
            self._mark_stage_complete(8.7, used_fallback=True)

            self.checkpoint_mgr.save_stage("stage_8_7_solution_refinement", {"skipped": True, "reason": "refinement_failed"})

    @listen(stage_8_7_solution_refinement)
    def stage_9_generate_seo_strategy(self):
        """
        Stage 9: Integrated Keyword Research + SEO Strategy Development

        SEOStrategyCrew performs complete workflow FOR THE SELECTED SOLUTION:
        1. Generates seed keywords specifically for selected solution
        2. Expands keywords using DataForSEO API
        3. Analyzes and creates tiered SEO strategy
        """
        logger.info("=" * 80)
        logger.info("STAGE 9: Integrated Keyword Research + SEO Strategy")
        logger.info("=" * 80)
        self._emit_progress(9, "SEO Strategy", "running")

        # Early exit if SEO strategy already exists from checkpoint
        if self.state.seo_strategy_report is not None:
            logger.info("✓ SEO strategy already loaded from checkpoint - skipping Stage 9")
            self._emit_progress(9, "SEO Strategy", "completed")
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("No solution selected - skipping SEO strategy")
            self.state.seo_strategy_report = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_seo_strategy", {"skipped": True, "reason": "No solution selected"})
            return

        # Check if we have required data
        if not self.state.idea_generation:
            logger.warning("Insufficient data for SEO strategy - skipping")
            self.state.seo_strategy_report = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_seo_strategy", {"skipped": True, "reason": "Insufficient data for SEO strategy"})
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
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_seo_strategy", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        logger.info(f"Generating SEO strategy for selected solution: {selected_solution_name}")

        # Initialize SEOStrategyCrew with SELECTED solution and audience vocabulary
        seo_crew = SEOStrategyCrew(
            niche=self.niche_description,
            selected_solution=selected_solution,
            selection_rationale=self.state.solution_selection.selection_rationale,
            competitive_analysis=self.state.competitive_analysis,
            pain_points=self.state.pain_point_analysis,
            niche_context=self.state.niche_context,
            allowed_project_types=self.state.allowed_project_types,
            audience_mapping=self.state.audience_mapping,
        )

        # Check for existing sub-phase checkpoints (enables partial resume)
        completed_stages = self.checkpoint_mgr.get_completed_stages()
        has_9_5a = "stage_9_5a_seed_expansion" in completed_stages
        has_9_5b = "stage_9_5b_bulk_validation" in completed_stages
        has_9_5c = "stage_9_5c_enrichment" in completed_stages

        # Phase 9.5a: Conceptual keyword expansion (SEO crew)
        logger.info(f"Phase 9.5a: Conceptual keyword expansion for {selected_solution_name}...")
        try:
            # Resume from checkpoint if available (with validation)
            if has_9_5a and self.state.stage_9_5a_expanded_keywords:
                from ..models.seo_strategy import ExpandedKeywordList
                try:
                    expanded_keywords = ExpandedKeywordList(**self.state.stage_9_5a_expanded_keywords)
                    # Validate restored data has required content
                    if not expanded_keywords.keywords or len(expanded_keywords.keywords) < 5:
                        raise ValueError(f"Restored 9.5a checkpoint has insufficient keywords ({len(expanded_keywords.keywords) if expanded_keywords.keywords else 0})")
                    logger.info(f"✓ Resuming from Phase 9.5a checkpoint ({len(expanded_keywords.keywords)} keywords)")
                except Exception as e:
                    logger.warning(f"⚠️ Phase 9.5a checkpoint invalid: {e}. Re-running expansion...")
                    expanded_keywords = seo_crew.expand_keywords_phase_1()
            else:
                expanded_keywords = seo_crew.expand_keywords_phase_1()
            logger.info(
                f"✓ Conceptual expansion complete: {len(expanded_keywords.keywords)} keywords, "
                f"{len(expanded_keywords.topic_clusters)} clusters"
            )

            # Checkpoint 9.5a: Save expanded keywords
            self.state.stage_9_5a_expanded_keywords = expanded_keywords.model_dump(mode='json')
            self.checkpoint_mgr.save_stage("stage_9_5a_seed_expansion", self.state.stage_9_5a_expanded_keywords)
            logger.info("✓ Phase 9.5a checkpoint saved: seed_expansion")

            # Phase 9.5b: Bulk validation with DataForSEO (NEW)
            logger.info("Phase 9.5b: Bulk validation of conceptual keywords with DataForSEO...")

            # Resume from checkpoint if available (with validation)
            resume_9_5b = False
            if has_9_5b and self.state.stage_9_5b_validation_results:
                quality_validated = self.state.stage_9_5b_validation_results.get("validated_keywords", [])
                min_volume = self.state.stage_9_5b_validation_results.get("threshold_used", 500)
                # Validate restored data
                if quality_validated and len(quality_validated) >= 1:
                    logger.info(f"✓ Resuming from Phase 9.5b checkpoint ({len(quality_validated)} validated keywords)")
                    resume_9_5b = True
                else:
                    logger.warning("⚠️ Phase 9.5b checkpoint has no validated keywords. Re-running validation...")

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
                    f"✓ Validation complete: {len(quality_validated)}/{len(conceptual_keyword_strings)} "
                    f"keywords have volume >= {min_volume}"
                )

                # Fallback: If too few validated keywords, lower threshold and retry filter
                if len(quality_validated) < 20:
                    logger.warning(
                        f"⚠️ Only {len(quality_validated)} keywords meet volume threshold. "
                        f"Lowering to {min_volume // 5} to find more seeds..."
                    )
                    quality_validated = [
                        kw for kw in validated_keywords
                        if kw.get('search_volume', 0) >= (min_volume // 5)
                    ]
                    logger.info(f"With lowered threshold: {len(quality_validated)} validated keywords")

                # Checkpoint 9.5b: Save validation results
                self.state.stage_9_5b_validation_results = {
                    "validated_keywords": quality_validated,
                    "original_count": len(conceptual_keyword_strings),
                    "passed_count": len(quality_validated),
                    "threshold_used": min_volume
                }
                self.checkpoint_mgr.save_stage("stage_9_5b_bulk_validation", self.state.stage_9_5b_validation_results)
                logger.info("✓ Phase 9.5b checkpoint saved: bulk_validation")

            # Absolute minimum check
            if len(quality_validated) < 5:
                logger.error(
                    f"❌ Bulk validation failed: Only {len(quality_validated)} keywords have search volume. "
                    f"Niche may be too specific or DataForSEO has insufficient data."
                )
                logger.warning("Skipping SEO strategy generation - insufficient keyword data")
                self.state.current_stage = 9.5
                self.checkpoint_mgr.save_stage("stage_9_seo_strategy", {
                    "skipped": True,
                    "reason": f"Insufficient validated keywords ({len(quality_validated)} < 5)"
                })
                return

            # Phase 9.5c: Iterative DataForSEO enrichment (programmatic)
            logger.info(
                f"Phase 9.5c: Iterative keyword enrichment with {len(quality_validated)} "
                f"validated seeds..."
            )

            # Resume from checkpoint if available (with validation)
            resume_9_5c = False
            if has_9_5c and self.state.stage_9_5c_enriched_keywords:
                enriched_keywords = self.state.stage_9_5c_enriched_keywords
                # Validate restored data has sufficient keywords
                if enriched_keywords and len(enriched_keywords) >= 5:
                    logger.info(f"✓ Resuming from Phase 9.5c checkpoint ({len(enriched_keywords)} enriched keywords)")
                    resume_9_5c = True
                else:
                    logger.warning(f"⚠️ Phase 9.5c checkpoint has insufficient keywords ({len(enriched_keywords) if enriched_keywords else 0}). Re-running enrichment...")

            if not resume_9_5c:
                enriched_keywords = self._iterative_keyword_enrichment(
                    conceptual_keywords=expanded_keywords.keywords,
                    validated_seeds=quality_validated,
                    topic_clusters=expanded_keywords.topic_clusters,
                    selected_solution=selected_solution,
                    niche_context=self.state.niche_context,
                )
                # Checkpoint 9.5c: Save enriched keywords
                self.state.stage_9_5c_enriched_keywords = enriched_keywords
                self.checkpoint_mgr.save_stage("stage_9_5c_enrichment", enriched_keywords)
                logger.info("✓ Phase 9.5c checkpoint saved: enrichment")

            logger.info(f"✓ Enrichment complete: {len(enriched_keywords)} keywords with search data")

            # Quality Gate: Validate keyword enrichment coverage
            total_expanded = len(expanded_keywords.keywords) if hasattr(expanded_keywords, 'keywords') else len(quality_validated)
            total_enriched = len(enriched_keywords)
            enrichment_coverage = total_enriched / total_expanded if total_expanded > 0 else 0.0

            logger.info("=" * 60)
            logger.info("KEYWORD ENRICHMENT COVERAGE ASSESSMENT")
            logger.info("=" * 60)
            logger.info(f"Total keywords expanded (Phase 9.5a): {total_expanded}")
            logger.info(f"Validated seeds (Phase 9.5b): {len(quality_validated)}")
            logger.info(f"Final enriched keywords (Phase 9.5c): {total_enriched}")
            logger.info(f"Enrichment coverage: {enrichment_coverage:.1%}")

            if enrichment_coverage < settings.keyword_enrichment_min_coverage:
                logger.warning(
                    f"⚠️  LOW ENRICHMENT COVERAGE: {enrichment_coverage:.1%} < threshold {settings.keyword_enrichment_min_coverage:.1%}"
                )
                logger.warning(
                    "Possible causes: (1) Niche/solution mismatch, (2) Too aggressive filtering, (3) Limited search demand"
                )
                logger.warning(
                    f"Recommendation: Review relevance validator thresholds or expand seed generation strategy"
                )
            elif enrichment_coverage >= settings.keyword_enrichment_target_coverage:
                logger.info(
                    f"✅ EXCELLENT COVERAGE: {enrichment_coverage:.1%} ≥ target {settings.keyword_enrichment_target_coverage:.1%}"
                )
                logger.info("Strong keyword-solution alignment - high confidence in SEO strategy")
            else:
                logger.info(
                    f"✓ Acceptable coverage: {enrichment_coverage:.1%} (between min {settings.keyword_enrichment_min_coverage:.1%} and target {settings.keyword_enrichment_target_coverage:.1%})"
                )

            logger.info("=" * 60)

            # Generate comprehensive SEO strategy using 4-task multitask flow
            # Task 1: Keyword Analysis & Tiering
            # Task 2: Content & Technical Strategy
            # Task 3: Implementation Planning
            # Task 4: Final Synthesis
            logger.info(f"Creating final SEO strategy (4-task flow) for {selected_solution_name}...")
            seo_strategy = seo_crew.create_strategy_multitask(
                enriched_keywords=enriched_keywords,
                expanded_keywords=expanded_keywords
            )

            # Record crew cost
            if seo_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 9 - SEO Strategy",
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

            self.state.seo_strategy_report = seo_strategy

            # Extract seed keywords from SEO strategy report
            if seo_strategy.seed_keywords_generated:
                self.state.seed_keywords = seo_strategy.seed_keywords_generated
                logger.info(f"[OK] Captured {len(seo_strategy.seed_keywords_generated)} seed keywords")

            logger.info(
                f"[OK] SEO strategy complete for {selected_solution_name}: "
                f"{seo_strategy.total_keywords_analyzed} keywords analyzed, "
                f"{len(seo_strategy.tier_1_keywords)} Tier 1 keywords, "
                f"{len(seo_strategy.topic_clusters) if seo_strategy.topic_clusters else 0} topic clusters"
            )
        except Exception as e:
            logger.error(f"SEO strategy generation failed: {e}")
            raise RuntimeError(f"Stage 9 failed: SEO strategy generation failed - {e}") from e

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 9.5

        # Mark stage complete with tracking
        self._mark_stage_complete(9)

        # Checkpoint: Save SEO strategy
        if self.state.seo_strategy_report:
            self.checkpoint_mgr.save_stage("stage_9_seo_strategy", self.state.seo_strategy_report)

    @listen(stage_9_generate_seo_strategy)
    def stage_9_5_trend_longevity(self):
        """
        Stage 9.5: Trend Longevity & Market Momentum Analysis

        Analyzes keyword trends, discussion activity, and competitive momentum to assess:
        - Market timing (Growing, Stable, Declining)
        - Trend sustainability (Sustainable, Risky, Fad)
        - Optimal entry timing (Enter Now, Monitor & Wait, Missed Window)
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.5: Trend Longevity & Market Momentum Analysis")
        logger.info("=" * 80)
        self._emit_progress(9.5, "Trend Analysis", "running")

        # Aggregate keyword trends from enriched keywords
        trend_summary = self._aggregate_keyword_trends()
        if trend_summary:
            logger.info(f"[Stage 9.5] Keyword trend summary: {trend_summary['trend_distribution']}")
            logger.info(f"[Stage 9.5] Market momentum: {trend_summary['market_momentum']}")
            logger.info(f"[Stage 9.5] Rising volume %: {trend_summary['rising_volume_pct']:.1f}%")

        # Check if we have required data - create fallback if missing
        def _create_minimal_trend_fallback(reason: str) -> "TrendLongevityResult":
            """Create minimal fallback trend result when full analysis cannot run."""
            from ..models.research_state import TrendLongevityResult
            logger.warning(f"[Stage 9.5] ⚠️ Creating minimal trend analysis due to: {reason}")
            return TrendLongevityResult(
                trend_direction="Stable",  # Conservative default (valid Literal)
                trend_confidence="Low",
                momentum_score=0.5,  # Neutral
                keyword_volume_trend="Stable",  # Conservative default (valid Literal)
                volume_growth_rate="Insufficient data",
                trend_duration="Unknown",
                discussion_frequency_trend="Stable",  # Conservative default (valid Literal)
                discussion_recency="Unknown",
                community_growth_indicators=["Trend analysis unavailable - insufficient data"],
                new_entrants_trend="Unknown",
                competitive_activity_level="Unknown",
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

        if not self.state.keyword_validation_results:
            logger.warning("[Stage 9.5] No keyword validation data - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("Missing keyword validation data")
            self.state.current_stage = 9.6
            return

        if not self.state.social_content:
            logger.warning("[Stage 9.5] No social content - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("Missing social content data")
            self.state.current_stage = 9.6
            return

        # Get selected solution's keyword validation
        selected_name = self.state.solution_selection.selected_solution_name if self.state.solution_selection else None
        if not selected_name:
            logger.warning("[Stage 9.5] No solution selected - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback("No solution selected")
            self.state.current_stage = 9.6
            return

        # Find keyword validation for selected solution
        keyword_validation = next(
            (v for v in self.state.keyword_validation_results if v.solution_name == selected_name),
            None
        )

        if not keyword_validation:
            logger.warning(f"[Stage 9.5] No keyword validation for {selected_name} - creating fallback trend analysis")
            self.state.trend_longevity = _create_minimal_trend_fallback(f"No keyword validation for {selected_name}")
            self.state.current_stage = 9.6
            return

        # Initialize and run trend longevity crew
        from ..crews import TrendLongevityCrew

        logger.info(f"[Stage 9.5] Analyzing market trends for: {self.niche_description}")

        # Get top enriched keywords with monthly trend data for detailed analysis
        top_enriched_keywords = None
        if self.state.stage_9_5c_enriched_keywords:
            # Pass top 20 keywords sorted by volume (with their monthly_searches)
            sorted_keywords = sorted(
                self.state.stage_9_5c_enriched_keywords,
                key=lambda x: x.get('search_volume', 0),
                reverse=True
            )[:20]
            top_enriched_keywords = sorted_keywords
            logger.info(f"[Stage 9.5] Passing {len(top_enriched_keywords)} enriched keywords with monthly trends")

        trend_crew = TrendLongevityCrew()

        trend_result = trend_crew.analyze(
            keyword_validation=keyword_validation,
            social_content=self.state.social_content,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description,
            enriched_keywords_trends=trend_summary,  # Aggregated 12-month trend summary
            top_enriched_keywords=top_enriched_keywords  # Per-keyword monthly trend data
        )

        # Record crew cost
        if trend_crew.usage_metrics:
            self.cost_tracker.record_crew_usage(
                stage="Stage 9.5 - Trend Longevity",
                usage_metrics=trend_crew.usage_metrics,
                model=settings.openai_model_name
            )

        # Check if analysis succeeded
        if not trend_result:
            logger.warning("[Stage 9.5] Trend analysis failed - continuing without trend data")
            self.state.current_stage = 9.6
            return

        # Store result
        self.state.trend_longevity = trend_result
        self.state.current_stage = 9.6

        # Mark stage complete with tracking (fallback if used minimal trend)
        used_fallback = trend_result.trend_direction == "Unknown"
        self._mark_stage_complete(9.5, used_fallback=used_fallback)

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_9_5_trend_longevity", trend_result)

        logger.info("[Stage 9.5] Trend Longevity Analysis Complete")
        logger.info(f"  Trend Direction: {trend_result.trend_direction}")
        logger.info(f"  Momentum Score: {trend_result.momentum_score:.2f}")
        logger.info(f"  Longevity Verdict: {trend_result.longevity_verdict}")
        logger.info(f"  Market Maturity: {trend_result.market_maturity}")
        logger.info(f"  Timing Recommendation: {trend_result.timing_recommendation}")

    @listen(stage_9_5_trend_longevity)
    def stage_9_6_refine_seo_scores(self):
        """
        Stage 9.6: Refine SEO Scores Based on Actual Keyword Data

        Updates the selected solution's SEO metrics using real keyword data discovered
        in Stage 9. Provides market-validated adjustments to architectural estimates.

        Refinement includes:
        - seo_scalability_score: Adjusted for keyword volume, Tier 1 count, competition
        - estimated_cac_organic: Adjusted for keyword difficulty and market volume
        - programmatic_seo_opportunity: Enhanced with quantitative page count estimates

        Original estimates are preserved in base fields for comparison.
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.6: Refine SEO Scores with Keyword Data")
        logger.info("=" * 80)
        self._emit_progress(9.6, "SEO Score Refinement", "running")

        # Check if refinement is enabled
        if not settings.seo_refinement_enabled:
            logger.info("SEO refinement disabled - skipping Stage 9.6")
            self.state.current_stage = 9.7
            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", {"skipped": True, "reason": "SEO refinement disabled in settings"})
            return

        # Skip if no SEO strategy or no solution selection
        if not self.state.seo_strategy_report or not self.state.solution_selection:
            logger.info("No SEO strategy or solution selection - skipping refinement")
            self.state.current_stage = 9.7
            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", {"skipped": True, "reason": "No SEO strategy or solution selection"})
            return

        # Skip if no idea generation
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.info("No solution ideas available - skipping refinement")
            self.state.current_stage = 9.7
            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", {"skipped": True, "reason": "No solution ideas"})
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
            self.state.current_stage = 9.7
            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        # Check if solution has SEO fields to refine
        if selected_solution.seo_scalability_score is None:
            logger.info("Solution has no SEO scores to refine - skipping")
            self.state.current_stage = 9.7
            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", {"skipped": True, "reason": "Solution has no SEO scores to refine"})
            return

        logger.info(f"Refining SEO scores for: {selected_solution_name}")

        seo_report = self.state.seo_strategy_report

        # Extract keyword data
        total_monthly_volume = seo_report.total_monthly_volume
        tier1_keywords = seo_report.tier_1_keywords if seo_report.tier_1_keywords else []
        tier1_count = len(tier1_keywords)

        logger.info(
            f"  Keyword data: {total_monthly_volume:,} monthly volume, "
            f"{tier1_count} Tier 1 keywords"
        )

        try:
            # 1. REFINE SEO SCALABILITY SCORE
            refined_scalability = refine_scalability_score(
                base_score=selected_solution.seo_scalability_score,
                project_type=selected_solution.project_type,
                total_volume=total_monthly_volume,
                tier1_count=tier1_count,
                tier1_keywords=tier1_keywords
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

            # Update CAC metadata with page count
            refined_cac['metadata']['estimated_year1_pages'] = page_count

            # Create SEO enrichment object (unified enrichment pattern)
            # This will be merged with base solution in report generator
            scalability_meta = refined_scalability['metadata']
            cac_meta = refined_cac['metadata']

            from ..models.solution_idea import SEORefinementMetadata, SolutionSEORefinement

            seo_enrichment = SolutionSEORefinement(
                solution_name=selected_solution_name,
                seo_scalability_score_refined=refined_scalability['score'],
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
                    estimated_year1_pages=cac_meta.get('estimated_year1_pages')
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

                    # Apply refined values inline
                    idea.seo_scalability_score = refined_scalability['score']
                    idea.estimated_cac_organic = refined_cac['cac_range']
                    idea.programmatic_seo_opportunity = refined_programmatic

                    logger.info(f"[Stage 9.6] Merged SEO refinements into solution '{selected_solution_name}'")
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
            self.state.current_stage = 9.7

            # Mark stage complete with tracking
            self._mark_stage_complete(9.6)

            self.checkpoint_mgr.save_stage("stage_9_6_seo_refinement", self.state.seo_enrichment)

        except Exception as e:
            logger.error(f"SEO refinement failed: {e}")
            logger.warning("Continuing with original estimates")
            # Still update stage even on failure (Pattern A - safer for resume)
            self.state.current_stage = 9.7

            # Mark stage complete with tracking (used fallback since refinement failed)
            self._mark_stage_complete(9.6, used_fallback=True)

    @listen(stage_9_6_refine_seo_scores)
    def stage_9_7_research_data_sources(self):
        """
        Stage 9.7: Targeted Data Source Research

        For the SELECTED solution ONLY (if requires_data_aggregation), conduct deep
        research on data sources using search tools. Informed by SEO priorities and
        competitive insights.
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.7: Data Source Research")
        logger.info("=" * 80)
        self._emit_progress(9.7, "Data Source Research", "running")

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.info("No solution selected - skipping data source research")
            self.state.data_source_research = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_7_data_sources", {"skipped": True, "reason": "No solution selected"})
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
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_7_data_sources", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        # Only run if solution requires data aggregation
        if not selected_solution.requires_data_aggregation:
            logger.info(
                f"Solution '{selected_solution_name}' doesn't require data aggregation - "
                f"skipping data source research"
            )
            self.state.data_source_research = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_7_data_sources", {"skipped": True, "reason": "Solution doesn't require data aggregation"})
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

            # Record crew cost
            if data_crew.usage_metrics:
                self.cost_tracker.record_crew_usage(
                    stage="Stage 9.7 - Data Sources",
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
        self.state.current_stage = 10

        # Mark stage complete with tracking
        self._mark_stage_complete(9.7)

        # Checkpoint: Save data source research
        if self.state.data_source_research:
            self.checkpoint_mgr.save_stage("stage_9_7_data_sources", self.state.data_source_research)

    @listen(stage_9_7_research_data_sources)
    def stage_10_generate_report(self):
        """
        Stage 10: Final Report Generation

        Hybrid approach: Python data assembly (80%) + optional LLM strategic synthesis (20%).
        Cost: ~$0.02-0.05 per report (vs $0.10-0.30 previously).
        Speed: ~2-3 seconds (vs 5-15 seconds previously).

        Delegates all report generation logic to ReportGenerator class.
        """
        logger.info("=" * 80)
        logger.info("STAGE 10: Final Report Generation (Hybrid Python + LLM)")
        logger.info("=" * 80)
        self._emit_progress(10, "Report Generation", "running")

        from datetime import datetime

        from ..report.report_generator import ReportGenerator

        try:
            # Delegate to ReportGenerator for all report generation logic
            report_generator = ReportGenerator(self.state)
            final_report = report_generator.generate_report()

            self.state.final_report = final_report

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
        self._mark_stage_complete(10)

        # Log pipeline completion summary
        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Stages completed: {sorted(self.state.completed_stages)}")
        if self.state.fallback_stages:
            logger.warning(f"  Stages with fallback data: {sorted(self.state.fallback_stages)}")
        logger.info("=" * 80)

        # Log cost summary
        if settings.cost_logging_enabled:
            self.cost_tracker.log_summary()

        # Store cost summary in state for report
        cost_summary = self.cost_tracker.get_summary()
        self.state.cost_summary = cost_summary

    # NOTE: Score refinement methods moved to utils/score_refinement.py
    # - refine_scalability_score
    # - refine_cac_organic
    # - refine_programmatic_opportunity

    def run_research(self) -> str:
        """
        Execute the complete research pipeline.

        Returns:
            Path to the generated report file
        """
        logger.info("Starting NicheIQ Research Pipeline...")
        logger.info(f"Niche: {self.niche_description}")

        try:
            # Kick off the flow
            self.kickoff()

            logger.info("[OK] Research pipeline completed successfully")
            return self.report_path

        except Exception as e:
            logger.error(f"Research pipeline failed: {e}")
            raise
