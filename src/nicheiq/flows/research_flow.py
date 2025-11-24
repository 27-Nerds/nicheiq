"""
ResearchFlow - Main orchestration flow for the 10-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

import json
import time
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
from ..utils.token_monitor import ContentTokenMonitor
from ..utils.validation import KeywordRelevanceValidator
from .checkpoint_manager import CheckpointManager


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

        # Initialize checkpoint manager
        self.checkpoint_mgr = CheckpointManager(
            niche_description=niche_description,
            state=self.state,
            allowed_project_types=allowed_project_types
        )

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
            return self._execute_remaining_stages()

        # No checkpoint or resume failed - run normal flow
        logger.info("Starting fresh research run")
        self.kickoff()

        # Generate final report path
        if self.state.final_report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"final_report_{timestamp}.json"
            return str(settings.output_dir / report_filename)

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

        # Calculate confidence score (0-1)
        confidence_score = (
            (high_severity / max(total_count, 1)) * 0.25 +  # 25%: High severity distribution
            (high_wtp / max(total_count, 1)) * 0.20 +        # 20%: WTP signal strength
            (min(quote_density / 10, 1.0)) * 0.20 +          # 20%: Quote density (target: 10+)
            (cross_platform_count / max(total_count, 1)) * 0.15 +  # 15%: Cross-platform validation
            source_coverage * 0.10 +                         # 10%: Source attribution
            (high_opportunity / max(total_count, 1)) * 0.10  # 10%: High-opportunity %
        )

        # Tier classification with detailed logging
        logger.info("=" * 60)
        logger.info("PAIN POINT QUALITY ASSESSMENT")
        logger.info("=" * 60)
        logger.info(f"Total pain points: {total_count}")
        logger.info(f"Severity distribution: {high_severity} high | {medium_severity} medium | {total_count - high_severity - medium_severity} low")
        logger.info(f"WTP signal: {high_wtp} high | {medium_wtp} medium")
        logger.info(f"Quote density: {quote_density:.1f} quotes/pain point (target: ≥10 for GOLD)")
        logger.info(f"Cross-platform validation: {cross_platform_count}/{total_count} pain points ({cross_platform_count/total_count*100:.0f}%)")
        logger.info(f"Source attribution coverage: {source_coverage*100:.0f}%")
        logger.info(f"High-opportunity pain points: {high_opportunity} ({high_opportunity/total_count*100:.0f}%)")
        logger.info(f"Overall confidence score: {confidence_score:.2f}")

        # GOLD tier: Exceptional quality for high-confidence pipeline
        if (
            high_severity >= 5 and
            quote_density >= 10 and
            cross_platform_count >= 3 and
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
            if current <= 7 and self._validate_stage_prerequisites(7):
                logger.info("Executing Unified Solution Pipeline (Stages 7-8.75)...")
                self.stages_7_through_8_75_unified_solution_pipeline()
            elif current <= 7:
                logger.info("Skipping Stages 7-8.75 (Unified Solution Pipeline) - prerequisites not met")
                # Skip all solution stages if prerequisites not met
                self.state.current_stage = 9

            # Stage 8.7: Only run if not already completed (listener stage)
            if current <= 8.7 and "stage_8_7_pricing_validation" not in completed_stages:
                if self._validate_stage_prerequisites(8.7):
                    self.stage_8_7_pricing_validation()
                else:
                    logger.info("Skipping Stage 8.7 (Pricing Validation) - prerequisites not met")
            elif "stage_8_7_pricing_validation" in completed_stages:
                logger.info("Skipping Stage 8.7 (Pricing Validation) - already completed")

            # Stage 8.6: Only run if not already completed (listener stage)
            if current <= 8.6 and "stage_8_6_market_sizing" not in completed_stages:
                if self._validate_stage_prerequisites(8.6):
                    self.stage_8_6_market_sizing()
                else:
                    logger.info("Skipping Stage 8.6 (Market Sizing) - prerequisites not met")
            elif "stage_8_6_market_sizing" in completed_stages:
                logger.info("Skipping Stage 8.6 (Market Sizing) - already completed")

            # Stage 8.8: Only run if not already completed
            if current <= 8.8 and "stage_8_8_keyword_validation" not in completed_stages:
                if self._validate_stage_prerequisites(8.8):
                    self.stage_8_8_keyword_validation()
                else:
                    logger.info("Skipping Stage 8.8 (Keyword Validation) - prerequisites not met")
            elif "stage_8_8_keyword_validation" in completed_stages:
                logger.info("Skipping Stage 8.8 (Keyword Validation) - already completed")

            # Stage 8.85: Only run if not already completed
            if current <= 8.85 and "stage_8_85_solution_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(8.85):
                    self.stage_8_85_solution_refinement()
                else:
                    logger.info("Skipping Stage 8.85 (Solution Refinement) - prerequisites not met")
            elif "stage_8_85_solution_refinement" in completed_stages:
                logger.info("Skipping Stage 8.85 (Solution Refinement) - already completed")

            if current <= 9 and self._validate_stage_prerequisites(9):
                self.stage_9_generate_seo_strategy()
            elif current <= 9:
                logger.info("Skipping Stage 9 (SEO Strategy) - prerequisites not met")

            # Stage 9.2: Only run if not already completed (listener stage)
            if current <= 9.2 and "stage_9_2_trend_longevity" not in completed_stages:
                if self._validate_stage_prerequisites(9.2):
                    self.stage_9_2_trend_longevity()
                else:
                    logger.info("Skipping Stage 9.2 (Trend Longevity) - prerequisites not met")
            elif "stage_9_2_trend_longevity" in completed_stages:
                logger.info("Skipping Stage 9.2 (Trend Longevity) - already completed")

            # Stage 9.5: Only run if not already completed (listener stage)
            if current <= 9.5 and "stage_9_5_seo_refinement" not in completed_stages:
                if self._validate_stage_prerequisites(9.5):
                    self.stage_9_5_refine_seo_scores()
                else:
                    logger.info("Skipping Stage 9.5 (SEO Refinement) - prerequisites not met")
            elif "stage_9_5_seo_refinement" in completed_stages:
                logger.info("Skipping Stage 9.5 (SEO Refinement) - already completed")

            # Stage 9.75: Only run if not already completed (listener stage)
            if current <= 9.75 and "stage_9_75_data_sources" not in completed_stages:
                if self._validate_stage_prerequisites(9.75):
                    self.stage_9_75_research_data_sources()
                else:
                    logger.info("Skipping Stage 9.75 (Data Source Research) - prerequisites not met")
            elif "stage_9_75_data_sources" in completed_stages:
                logger.info("Skipping Stage 9.75 (Data Source Research) - already completed")

            if current <= 10:
                self.stage_10_generate_report()

            # Generate final report path
            if self.state.final_report:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"final_report_{timestamp}.json"
                return str(settings.output_dir / report_filename)

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
            logger.warning("Proceeding without structured niche context")

        self.state.current_stage = 5

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
        context: NicheContext = LLMService.invoke_structured(
            prompt=prompt,
            output_model=NicheContext,
            temperature=0.5,
            timeout=120,
            model_name=settings.openai_model_name
        )

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

        # Search Reddit
        logger.info("Searching Reddit for relevant discussions...")
        reddit_results = []
        for search_query in self.state.search_queries:  # Use all generated queries
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
        unique_reddit_results = []
        for result in reddit_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_reddit_results.append(result)

        logger.info(f"[OK] Found {len(unique_reddit_results)} unique Reddit results from {len(self.state.search_queries)} queries")

        # Validate relevance using cheap model (gpt-4o-mini) with parallel processing
        logger.info("Validating Reddit thread relevance...")
        from ..utils.validation import ThreadRelevanceValidator
        validator = ThreadRelevanceValidator()
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

        # Search Twitter
        twitter_urls = []
        twitter_threads = []

        if settings.enable_twitter:
            logger.info("Searching Twitter/X for relevant discussions...")
            twitter_results = []
            for search_query in self.state.search_queries:  # Use all generated queries
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

            logger.info(f"[OK] Found {len(unique_twitter_results)} unique Twitter results from {len(self.state.search_queries)} queries")

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
            logger.info("Twitter collection disabled (ENABLE_TWITTER=false) - skipping Twitter search and collection")
            # Collect Reddit content only
            logger.info("Collecting Reddit posts and comments...")
            reddit_posts = self.reddit_tool.collect_posts(reddit_urls)
            twitter_threads = []
            logger.info(f"[OK] Collected {len(reddit_posts)} quality Reddit posts")

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

        # Checkpoint: Save social content
        self.checkpoint_mgr.save_stage("stage_5_social_content", self.state.social_content)

    @listen(stage_5_search_and_discover)
    def stage_6_analyze_pain_points(self):
        """
        Stage 6: Pain Point Analysis

        Uses PainPointCrew to analyze social content and extract validated pain points.
        """
        logger.info("=" * 80)
        logger.info("STAGE 6: Pain Point Analysis")
        logger.info("=" * 80)

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

        # Initialize and run PainPointCrew
        pain_point_crew = PainPointCrew(
            reddit_posts=self.state.social_content.reddit_posts,
            twitter_threads=self.state.social_content.twitter_threads,
            niche_description=self.niche_description,
            market_segments=self.state.niche_context.market_segments,
            industry_boundaries=self.state.niche_context.industry_boundaries
        )

        logger.info("Running pain point analysis crew...")
        self.state.pain_point_analysis = pain_point_crew.analyze()

        logger.info(f"[OK] Identified {len(self.state.pain_point_analysis.pain_points)} pain points")
        logger.info(f"[OK] Total mentions: {self.state.pain_point_analysis.total_mentions}")
        # Ensure top_categories contains strings
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
            logger.error("Pain point quality insufficient for pipeline - stopping execution")
            logger.error("Recommendation: Expand social content collection or refine niche focus")
            self.state.errors.append(
                f"Stage 6 quality gate failed: {quality_tier} tier (confidence: {confidence_score:.2f})"
            )
            # Save checkpoint with error state
            self.checkpoint_mgr.save_stage("stage_6_pain_points", self.state.pain_point_analysis)
            return  # Stop pipeline execution

        # Quality tier acceptable - proceed with pipeline
        logger.info(f"✅ Quality gate passed - proceeding with {quality_tier} tier data (confidence: {confidence_score:.2f})")

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 6.5

        # Checkpoint: Save pain point analysis
        self.checkpoint_mgr.save_stage("stage_6_pain_points", self.state.pain_point_analysis)

    @listen(stage_6_analyze_pain_points)
    def stage_6_5_audience_mapping(self):
        """
        Stage 6.5: Audience & Influence Mapping

        Analyzes social media discussions to identify:
        - Distinct audience segments with characteristics
        - Key influencers and community hubs
        - Common vocabulary and messaging frameworks
        - Optimal marketing channels and content strategy
        """
        logger.info("=" * 80)
        logger.info("STAGE 6.5: Audience & Influence Mapping")
        logger.info("=" * 80)

        # Check if we have required data
        if not self.state.social_content:
            logger.warning("[Stage 6.5] No social content - skipping audience mapping")
            self.state.current_stage = 7
            return

        if not self.state.pain_point_analysis:
            logger.warning("[Stage 6.5] No pain point analysis - skipping audience mapping")
            self.state.current_stage = 7
            return

        # Initialize and run audience mapping crew
        from ..crews import AudienceMappingCrew

        logger.info(f"[Stage 6.5] Analyzing audience segments for: {self.niche_description}")

        audience_crew = AudienceMappingCrew()

        audience_result = audience_crew.analyze(
            social_content=self.state.social_content,
            pain_point_analysis=self.state.pain_point_analysis,
            niche_description=self.niche_description
        )

        # Check if analysis succeeded
        if not audience_result:
            logger.warning("[Stage 6.5] Audience mapping failed - continuing without audience data")
            self.state.current_stage = 7
            return

        # Store result
        self.state.audience_mapping = audience_result
        self.state.current_stage = 7

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_6_5_audience_mapping", audience_result)

        logger.info("[Stage 6.5] Audience Mapping Complete")
        logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
        logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
        logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
        logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
        logger.info(f"  Recommended Channels: {', '.join(audience_result.recommended_channels[:3])}")

    @listen(stage_6_5_audience_mapping)
    def stages_7_through_8_75_unified_solution_pipeline(self):
        """
        Stages 7-8.75: Unified Solution Pipeline (CrewAI Best Practice)

        Consolidates stages using UnifiedSolutionCrew with context chaining:
        - Stage 7: Solution Ideation (brainstorm + evaluate + refine)
        - Stage 8: Competitive Analysis (research + gap analysis)
        - Stage 8.5: Competitive Refinement (enhance with insights)
        - Stage 8.75: Solution Selection (strategic scoring and selection)

        Benefits:
        - Automatic field preservation via output_pydantic + context
        - No manual data formatting between stages
        - Guardrails prevent data loss
        - Follows CrewAI documentation best practices
        """
        logger.info("=" * 80)
        logger.info("STAGES 7-8.75: Unified Solution Pipeline")
        logger.info("=" * 80)

        # Prerequisites check
        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            logger.warning("No pain points available. Skipping solution pipeline.")
            self.state.current_stage = 9
            self.checkpoint_mgr.save_stage("stages_7_8_75_unified", {"skipped": True, "reason": "No pain points available"})
            return

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
            logger.warning(
                "No high or medium priority pain points available - skipping solution pipeline"
            )
            self.state.current_stage = 9
            self.checkpoint_mgr.save_stage("stages_7_8_75_unified", {"skipped": True, "reason": "No high/medium priority pain points"})
            return

        logger.info(
            f"Pain point quality check: {len(high_priority)} high-priority, "
            f"{len(medium_priority)} medium-priority pain points"
        )

        try:
            # Initialize UnifiedSolutionCrew
            unified_crew = UnifiedSolutionCrew(
                pain_point_analysis=self.state.pain_point_analysis,
                social_content=self.state.social_content,
                allowed_project_types=self.allowed_project_types,
                niche_context=self.state.niche_context,
                checkpoint_mgr=self.checkpoint_mgr
            )

            # Execute complete pipeline (4 tasks in sequence with context chaining)
            logger.info("Executing unified solution pipeline (4-task flow)...")
            refined_solutions, competitive_analysis, solution_selection = unified_crew.execute_pipeline()

            # Save results to state
            self.state.idea_generation = refined_solutions
            self.state.competitive_analysis = competitive_analysis
            self.state.solution_selection = solution_selection

            # Log results
            logger.info("[OK] Solution Pipeline Complete:")
            logger.info(f"  - Generated {len(refined_solutions.solution_ideas)} solutions")
            logger.info(f"  - Analyzed {len(competitive_analysis.solution_landscapes)} competitive landscapes")
            logger.info(f"  - Selected: {solution_selection.selected_solution_name}")

            # Update stage (continue to keyword validation)
            self.state.current_stage = 8.8

            # Checkpoints: Save all intermediate outputs
            self.checkpoint_mgr.save_stage("stage_7_solutions", self.state.idea_generation)
            self.checkpoint_mgr.save_stage("stage_8_competitive", self.state.competitive_analysis)
            self.checkpoint_mgr.save_stage("stage_8_5_refinement", self.state.idea_generation)
            self.checkpoint_mgr.save_stage("stage_8_75_solution_selection", self.state.solution_selection)

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
            all_enriched.extend(relevant_suggestions)
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

    @listen(stages_7_through_8_75_unified_solution_pipeline)
    def stage_8_7_pricing_validation(self):
        """
        Stage 8.7: Pricing Strategy Validation

        Validates monetization strategy by determining optimal pricing based on:
        - Competitor pricing benchmarks from competitive analysis
        - Pain point willingness-to-pay (WTP) scores
        - Selected solution features and positioning
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.7: Pricing Strategy Validation")
        logger.info("=" * 80)

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.7] No solution selected - skipping pricing validation")
            self.state.current_stage = 8.8
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 8.7] No pain point analysis - skipping pricing validation")
            self.state.current_stage = 8.8
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 8.7] No competitive analysis - skipping pricing validation")
            self.state.current_stage = 8.8
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 8.7] Selected solution '{selected_name}' not found")
            self.state.current_stage = 8.8
            return

        # Initialize and run pricing strategy crew
        from ..crews import PricingStrategyCrew

        logger.info(f"[Stage 8.7] Analyzing pricing strategy for: {selected_name}")

        pricing_crew = PricingStrategyCrew()

        pricing_result = pricing_crew.analyze(
            selected_solution=selected_solution,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description
        )

        # Check if analysis succeeded
        if not pricing_result:
            logger.warning("[Stage 8.7] Pricing analysis failed - continuing without pricing data")
            self.state.current_stage = 8.8
            return

        # Store result
        self.state.pricing_strategy = pricing_result
        self.state.current_stage = 8.8

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_8_7_pricing_validation", pricing_result)

        logger.info("[Stage 8.7] Pricing Strategy Validation Complete")
        logger.info(f"  Recommended Pricing: Starter {pricing_result.recommended_starter_price}, Pro {pricing_result.recommended_pro_price}")
        logger.info(f"  Estimated ARPU: {pricing_result.estimated_arpu}")
        logger.info(f"  LTV/CAC Ratio: {pricing_result.ltv_to_cac_ratio}")

    @listen(stage_8_7_pricing_validation)
    def stage_8_6_market_sizing(self):
        """
        Stage 8.6: Market Sizing & Validation

        Calculates TAM/SAM/SOM estimates and validates market attractiveness using:
        - Keyword search volumes (demand signals)
        - Pain point frequency (problem validation)
        - Competitive landscape (market saturation)
        - Selected solution positioning
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.6: Market Sizing & Validation")
        logger.info("=" * 80)

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.6] No solution selected - skipping market sizing")
            self.state.current_stage = 8.8
            return

        # Check if we have pain point analysis
        if not self.state.pain_point_analysis:
            logger.warning("[Stage 8.6] No pain point analysis - skipping market sizing")
            self.state.current_stage = 8.8
            return

        # Check if we have competitive analysis
        if not self.state.competitive_analysis:
            logger.warning("[Stage 8.6] No competitive analysis - skipping market sizing")
            self.state.current_stage = 8.8
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 8.6] Selected solution '{selected_name}' not found")
            self.state.current_stage = 8.8
            return

        # Initialize and run market sizing crew
        from ..crews import MarketSizingCrew

        logger.info(f"[Stage 8.6] Calculating TAM/SAM/SOM for: {selected_name}")

        market_sizing_crew = MarketSizingCrew()

        # Get keyword validation for selected solution if available (optional - Stage 8.8 may not have run yet)
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
            logger.info("[Stage 8.6] Keyword validation not yet available - will calculate market size from pain points and competitive analysis")

        market_sizing_result = market_sizing_crew.analyze(
            selected_solution=selected_solution,
            keyword_validation=keyword_validation,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description
        )

        # Check if analysis succeeded
        if not market_sizing_result:
            logger.warning("[Stage 8.6] Market sizing failed - continuing without market sizing data")
            self.state.current_stage = 8.8
            return

        # Store result
        self.state.market_sizing = market_sizing_result
        self.state.current_stage = 8.8

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
    def stage_8_8_keyword_validation(self):
        """
        Stage 8.8: Quick Keyword Validation for Top 3 Solutions

        Validates keyword demand for top 3 solutions using hybrid seed generation
        (10 programmatic + 10 LLM seeds) to inform final selection decision.

        Adjusts composite scores based on actual market search behavior.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.8: Keyword Demand Validation")
        logger.info("=" * 80)

        # Check if feature is enabled
        if not getattr(settings, 'keyword_validation_enabled', True):
            logger.info("[Stage 8.8] Keyword validation disabled - skipping")
            self.state.current_stage = 8.85
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.8] No solution selected - skipping keyword validation")
            self.state.current_stage = 8.85
            return

        # Get top 3 solutions from all_solution_scores
        all_scores = self.state.solution_selection.all_solution_scores
        if not all_scores or len(all_scores) < 1:
            logger.warning("[Stage 8.8] No solution scores available - skipping")
            self.state.current_stage = 8.85
            return

        # Sort by composite score and take top 3
        top_3_scores = sorted(all_scores, key=lambda s: s.composite_score, reverse=True)[:3]

        logger.info(f"[Stage 8.8] Validating keyword demand for top {len(top_3_scores)} solutions")

        # Validate keywords for each solution
        validation_results = []

        for idx, solution_score in enumerate(top_3_scores, 1):
            solution_name = solution_score.solution_name
            logger.info(f"[Stage 8.8] ({idx}/{len(top_3_scores)}) Validating: {solution_name}")

            # Find the full solution object
            solution = find_solution_by_name(
                solution_name,
                self.state.idea_generation.solution_ideas
            )

            if not solution:
                logger.warning(f"[Stage 8.8] Solution '{solution_name}' not found in idea generation")
                continue

            # Initialize seed generator for this solution
            seed_generator = SeedGenerator(
                state=self.state,
                niche_context=self.state.niche_context if hasattr(self.state, 'niche_context') else None,
                pain_point_analysis=self.state.pain_point_analysis if hasattr(self.state, 'pain_point_analysis') else None
            )

            # Adaptive keyword generation with pivot strategies
            # Try up to 4 attempts with different strategies until relevant keywords found
            accumulated_good_keywords = []
            best_relevance_score = 0.0
            best_validation_result = None
            max_attempts = getattr(settings, 'keyword_pivot_max_attempts', 4)
            relevance_threshold = getattr(settings, 'keyword_relevance_threshold', 0.6)
            # Cache for keyword validation across attempts (avoids re-validating same keywords)
            keyword_validation_cache: dict[str, tuple] = {}

            for attempt in range(1, max_attempts + 1):
                logger.info(f"[Stage 8.8] Attempt {attempt}/{max_attempts} for {solution_name}")

                # Generate seeds with current strategy
                seeds = seed_generator.generate_seeds_with_strategy(solution, attempt, count=20)

                if not seeds:
                    logger.warning(f"[Stage 8.8] Attempt {attempt}: No seeds generated - skipping")
                    continue

                logger.debug(f"[Stage 8.8] Attempt {attempt} seeds ({len(seeds)}): {seeds[:5]}...")

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
                    validation_cache=keyword_validation_cache
                )

                # Accumulate good keywords across attempts
                if good_keywords:
                    accumulated_good_keywords.extend(good_keywords)
                    logger.info(
                        f"[Stage 8.8] Attempt {attempt}: Found {len(good_keywords)} good keywords "
                        f"(total accumulated: {len(accumulated_good_keywords)})"
                    )

                # Track best result
                if relevance_score > best_relevance_score:
                    best_relevance_score = relevance_score
                    best_validation_result = validation_result
                    logger.info(
                        f"[Stage 8.8] Attempt {attempt}: New best relevance score: {relevance_score:.2f}"
                    )

                # Check if we have good enough keywords
                if relevance_score >= relevance_threshold:
                    logger.info(
                        f"[Stage 8.8] Attempt {attempt}: SUCCESS - relevance {relevance_score:.2f} "
                        f">= threshold {relevance_threshold:.2f}"
                    )
                    break
                else:
                    logger.warning(
                        f"[Stage 8.8] Attempt {attempt}: PIVOT needed - relevance {relevance_score:.2f} "
                        f"< threshold {relevance_threshold:.2f}. Issues: {', '.join(issues)}"
                    )

                    # If this is the last attempt, accept what we have
                    if attempt == max_attempts:
                        logger.warning(
                            f"[Stage 8.8] Max attempts reached - proceeding with best result "
                            f"(relevance: {best_relevance_score:.2f})"
                        )

            # Use best validation result
            if best_validation_result:
                # Enhance with accumulated keywords metadata
                best_validation_result["attempts_made"] = attempt
                best_validation_result["best_relevance_score"] = best_relevance_score
                best_validation_result["accumulated_keywords_count"] = len(accumulated_good_keywords)

                # Convert dict to Pydantic object for type safety
                validation_obj = CrewKeywordValidationResult(**best_validation_result)
                validation_results.append(validation_obj)

                logger.info(
                    f"[Stage 8.8] Final result for {solution_name}: "
                    f"{attempt} attempts, relevance={best_relevance_score:.2f}, "
                    f"{len(accumulated_good_keywords)} good keywords accumulated"
                )
            else:
                logger.error(f"[Stage 8.8] All attempts failed for {solution_name} - no validation result")

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
                    f"[Stage 8.8] {solution_score.solution_name} not in top-3 validation set - "
                    f"preserving existing scores (composite: {solution_score.composite_score:.2f})"
                )
                # If the solution had no keyword scores, set to base composite score
                if solution_score.adjusted_composite_score is None:
                    solution_score.adjusted_composite_score = solution_score.composite_score

        # Re-score solutions using keyword demand
        logger.info("[Stage 8.8] Re-scoring solutions with keyword demand data")

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
                        f"[Stage 8.8] {solution_score.solution_name}: "
                        f"base={base_score:.2f}, keyword_demand={keyword_multiplier:.2f}, "
                        f"adjusted={solution_score.adjusted_composite_score:.2f}"
                    )
                    break

        # Re-rank solutions by adjusted score (only validated solutions)
        ranked_solutions = sorted(
            [s for s in all_scores if s.adjusted_composite_score is not None],
            key=lambda s: s.adjusted_composite_score or 0.0,
            reverse=True
        )

        if ranked_solutions:
            new_winner = ranked_solutions[0].solution_name
            original_winner = self.state.solution_selection.selected_solution_name

            if new_winner != original_winner:
                logger.warning(
                    f"[Stage 8.8] Winner changed after keyword validation: "
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
            else:
                logger.info(f"[Stage 8.8] Winner confirmed by keyword validation: {new_winner}")

        # Update stage and checkpoint
        self.state.current_stage = 8.85
        self.checkpoint_mgr.save_stage("stage_8_8_keyword_validation", validation_results)

        logger.info(f"[Stage 8.8] Keyword validation complete - {len(validation_results)} solutions validated")

    @listen(stage_8_8_keyword_validation)
    def stage_8_85_solution_refinement(self):
        """
        Stage 8.85: Solution Refinement Using Keyword Insights

        Generates strategic recommendations for selected solution based on keyword validation:
        - Geographic market priorities
        - Category/positioning pivots
        - Feature prioritization
        - Content strategy direction
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.85: Solution Refinement")
        logger.info("=" * 80)

        # Check if feature is enabled
        if not getattr(settings, 'solution_refinement_enabled', True):
            logger.info("[Stage 8.85] Solution refinement disabled - skipping")
            self.state.current_stage = 9
            return

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.warning("[Stage 8.85] No solution selected - skipping refinement")
            self.state.current_stage = 9
            return

        # Check if we have keyword validation results
        if not self.state.keyword_validation_results:
            logger.warning("[Stage 8.85] No keyword validation results - skipping refinement")
            self.state.current_stage = 9
            return

        # Get selected solution
        selected_name = self.state.solution_selection.selected_solution_name
        selected_solution = find_solution_by_name(
            selected_name,
            self.state.idea_generation.solution_ideas
        )

        if not selected_solution:
            logger.error(f"[Stage 8.85] Selected solution '{selected_name}' not found")
            self.state.current_stage = 9
            return

        # Get keyword validation for selected solution
        keyword_validation = next(
            (v for v in self.state.keyword_validation_results if v.solution_name == selected_name),
            None
        )

        if not keyword_validation:
            logger.warning(f"[Stage 8.85] No keyword validation found for {selected_name}")
            self.state.current_stage = 9
            return

        # Early exit if demand is too weak
        if keyword_validation.demand_signal == "weak" and keyword_validation.total_volume < 2000:
            logger.warning(
                f"[Stage 8.85] Skipping refinement - weak demand signal "
                f"({keyword_validation.total_volume} monthly volume)"
            )
            self.state.current_stage = 9
            self.checkpoint_mgr.save_stage("stage_8_85_solution_refinement", {"skipped": True, "reason": "weak_demand"})
            return

        # Get composite score for context
        composite_score = next(
            (s.composite_score for s in self.state.solution_selection.all_solution_scores
             if s.solution_name == selected_name),
            0.0
        )

        # Initialize and run refinement crew
        logger.info(f"[Stage 8.85] Refining strategy for: {selected_name}")
        refinement_crew = SolutionRefinementCrew()

        refinement = refinement_crew.refine(
            selected_solution=selected_solution,
            keyword_validation=keyword_validation,
            composite_score=composite_score
        )

        if refinement:
            # Store refinement in state
            self.state.solution_refinement = refinement

            logger.info(
                f"[Stage 8.85] Refinement complete:\n"
                f"  - Geographic priorities: {', '.join(refinement.geographic_priorities[:3])}\n"
                f"  - Category pivot: {refinement.category_pivot_recommendation or 'None'}\n"
                f"  - Feature priorities: {len(refinement.feature_priorities)} recommendations\n"
                f"  - Strategic insights: {len(refinement.strategic_insights)} insights"
            )

            # Save to checkpoint
            self.checkpoint_mgr.save_stage("stage_8_85_solution_refinement", refinement.model_dump())
        else:
            logger.warning("[Stage 8.85] Refinement failed - proceeding without refinement data")
            self.checkpoint_mgr.save_stage("stage_8_85_solution_refinement", {"skipped": True, "reason": "refinement_failed"})

        # Update stage
        self.state.current_stage = 9

    @listen(stage_8_85_solution_refinement)
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

        # Initialize SEOStrategyCrew with SELECTED solution
        seo_crew = SEOStrategyCrew(
            niche=self.niche_description,
            selected_solution=selected_solution,
            selection_rationale=self.state.solution_selection.selection_rationale,
            competitive_analysis=self.state.competitive_analysis,
            pain_points=self.state.pain_point_analysis,
            niche_context=self.state.niche_context,
        )

        # Check for existing sub-phase checkpoints (enables partial resume)
        completed_stages = self.checkpoint_mgr.get_completed_stages()
        has_9_5a = "stage_9_5a_seed_expansion" in completed_stages
        has_9_5b = "stage_9_5b_bulk_validation" in completed_stages
        has_9_5c = "stage_9_5c_enrichment" in completed_stages

        # Phase 9.5a: Conceptual keyword expansion (SEO crew)
        logger.info(f"Phase 9.5a: Conceptual keyword expansion for {selected_solution_name}...")
        try:
            # Resume from checkpoint if available
            if has_9_5a and self.state.stage_9_5a_expanded_keywords:
                from ..models.seo_strategy import ExpandedKeywordList
                logger.info("✓ Resuming from Phase 9.5a checkpoint")
                expanded_keywords = ExpandedKeywordList(**self.state.stage_9_5a_expanded_keywords)
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

            # Resume from checkpoint if available
            if has_9_5b and self.state.stage_9_5b_validation_results:
                logger.info("✓ Resuming from Phase 9.5b checkpoint")
                quality_validated = self.state.stage_9_5b_validation_results.get("validated_keywords", [])
                min_volume = self.state.stage_9_5b_validation_results.get("threshold_used", 500)
            else:
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

            # Resume from checkpoint if available
            if has_9_5c and self.state.stage_9_5c_enriched_keywords:
                logger.info("✓ Resuming from Phase 9.5c checkpoint")
                enriched_keywords = self.state.stage_9_5c_enriched_keywords
            else:
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
            self.state.seo_strategy_report = None
            logger.warning("Continuing to final report without SEO strategy")

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 9.5

        # Checkpoint: Save SEO strategy
        if self.state.seo_strategy_report:
            self.checkpoint_mgr.save_stage("stage_9_seo_strategy", self.state.seo_strategy_report)

    @listen(stage_9_generate_seo_strategy)
    def stage_9_2_trend_longevity(self):
        """
        Stage 9.2: Trend Longevity & Market Momentum Analysis

        Analyzes keyword trends, discussion activity, and competitive momentum to assess:
        - Market timing (Growing, Stable, Declining)
        - Trend sustainability (Sustainable, Risky, Fad)
        - Optimal entry timing (Enter Now, Monitor & Wait, Missed Window)
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.2: Trend Longevity & Market Momentum Analysis")
        logger.info("=" * 80)

        # Check if we have required data
        if not self.state.keyword_validation_results:
            logger.warning("[Stage 9.2] No keyword validation data - skipping trend analysis")
            self.state.current_stage = 9.5
            return

        if not self.state.social_content:
            logger.warning("[Stage 9.2] No social content - skipping trend analysis")
            self.state.current_stage = 9.5
            return

        # Get selected solution's keyword validation
        selected_name = self.state.solution_selection.selected_solution_name if self.state.solution_selection else None
        if not selected_name:
            logger.warning("[Stage 9.2] No solution selected - skipping trend analysis")
            self.state.current_stage = 9.5
            return

        # Find keyword validation for selected solution
        keyword_validation = next(
            (v for v in self.state.keyword_validation_results if v.solution_name == selected_name),
            None
        )

        if not keyword_validation:
            logger.warning(f"[Stage 9.2] No keyword validation for {selected_name} - skipping trend analysis")
            self.state.current_stage = 9.5
            return

        # Initialize and run trend longevity crew
        from ..crews import TrendLongevityCrew

        logger.info(f"[Stage 9.2] Analyzing market trends for: {self.niche_description}")

        trend_crew = TrendLongevityCrew()

        trend_result = trend_crew.analyze(
            keyword_validation=keyword_validation,
            social_content=self.state.social_content,
            pain_point_analysis=self.state.pain_point_analysis,
            competitive_analysis=self.state.competitive_analysis,
            niche_description=self.niche_description
        )

        # Check if analysis succeeded
        if not trend_result:
            logger.warning("[Stage 9.2] Trend analysis failed - continuing without trend data")
            self.state.current_stage = 9.5
            return

        # Store result
        self.state.trend_longevity = trend_result
        self.state.current_stage = 9.5

        # Save checkpoint
        self.checkpoint_mgr.save_stage("stage_9_2_trend_longevity", trend_result)

        logger.info("[Stage 9.2] Trend Longevity Analysis Complete")
        logger.info(f"  Trend Direction: {trend_result.trend_direction}")
        logger.info(f"  Momentum Score: {trend_result.momentum_score:.2f}")
        logger.info(f"  Longevity Verdict: {trend_result.longevity_verdict}")
        logger.info(f"  Market Maturity: {trend_result.market_maturity}")
        logger.info(f"  Timing Recommendation: {trend_result.timing_recommendation}")

    @listen(stage_9_2_trend_longevity)
    def stage_9_5_refine_seo_scores(self):
        """
        Stage 9.5: Refine SEO Scores Based on Actual Keyword Data

        Updates the selected solution's SEO metrics using real keyword data discovered
        in Stage 9. Provides market-validated adjustments to architectural estimates.

        Refinement includes:
        - seo_scalability_score: Adjusted for keyword volume, Tier 1 count, competition
        - estimated_cac_organic: Adjusted for keyword difficulty and market volume
        - programmatic_seo_opportunity: Enhanced with quantitative page count estimates

        Original estimates are preserved in base fields for comparison.
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.5: Refine SEO Scores with Keyword Data")
        logger.info("=" * 80)

        # Check if refinement is enabled
        if not settings.seo_refinement_enabled:
            logger.info("SEO refinement disabled - skipping Stage 9.5")
            self.state.current_stage = 9.75
            self.checkpoint_mgr.save_stage("stage_9_5_seo_refinement", {"skipped": True, "reason": "SEO refinement disabled in settings"})
            return

        # Skip if no SEO strategy or no solution selection
        if not self.state.seo_strategy_report or not self.state.solution_selection:
            logger.info("No SEO strategy or solution selection - skipping refinement")
            self.state.current_stage = 9.75
            self.checkpoint_mgr.save_stage("stage_9_5_seo_refinement", {"skipped": True, "reason": "No SEO strategy or solution selection"})
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
            self.state.current_stage = 9.75
            self.checkpoint_mgr.save_stage("stage_9_5_seo_refinement", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        # Check if solution has SEO fields to refine
        if selected_solution.seo_scalability_score is None:
            logger.info("Solution has no SEO scores to refine - skipping")
            self.state.current_stage = 9.75
            self.checkpoint_mgr.save_stage("stage_9_5_seo_refinement", {"skipped": True, "reason": "Solution has no SEO scores to refine"})
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

            # Store enrichment in state (will be merged in Stage 10)
            self.state.seo_enrichment = seo_enrichment

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

            # Save checkpoint
            self.checkpoint_mgr.save_stage("stage_9_5_seo_refinement", self.state.seo_enrichment)

        except Exception as e:
            logger.error(f"SEO refinement failed: {e}")
            logger.warning("Continuing with original estimates")

        self.state.current_stage = 9.75

    @listen(stage_9_5_refine_seo_scores)
    def stage_9_75_research_data_sources(self):
        """
        Stage 9.75: Targeted Data Source Research

        For the SELECTED solution ONLY (if requires_data_aggregation), conduct deep
        research on data sources using search tools. Informed by SEO priorities and
        competitive insights.
        """
        logger.info("=" * 80)
        logger.info("STAGE 9.75: Data Source Research")
        logger.info("=" * 80)

        # Check if we have solution selection
        if not self.state.solution_selection:
            logger.info("No solution selected - skipping data source research")
            self.state.data_source_research = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_75_data_sources", {"skipped": True, "reason": "No solution selected"})
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
            self.checkpoint_mgr.save_stage("stage_9_75_data_sources", {"skipped": True, "reason": f"Selected solution '{selected_solution_name}' not found"})
            return

        # Only run if solution requires data aggregation
        if not selected_solution.requires_data_aggregation:
            logger.info(
                f"Solution '{selected_solution_name}' doesn't require data aggregation - "
                f"skipping data source research"
            )
            self.state.data_source_research = None
            self.state.current_stage = 10
            self.checkpoint_mgr.save_stage("stage_9_75_data_sources", {"skipped": True, "reason": "Solution doesn't require data aggregation"})
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

        # Checkpoint: Save data source research
        if self.state.data_source_research:
            self.checkpoint_mgr.save_stage("stage_9_75_data_sources", self.state.data_source_research)

    @listen(stage_9_75_research_data_sources)
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
