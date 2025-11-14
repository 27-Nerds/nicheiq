"""
ResearchFlow - Main orchestration flow for the 10-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import asyncio
import json
import time
from datetime import datetime, timedelta

from crewai.flow.flow import Flow, listen, start
from crewai.llm import LLM
from crewai_tools import SerperDevTool
from loguru import logger
from pydantic import ValidationError

from ..config.settings import settings
from ..crews import PainPointCrew, SEOStrategyCrew, UnifiedSolutionCrew
from ..models.research_state import FinalReport, ResearchState
from ..tools.reddit_tool import RedditCollectorTool
from ..tools.twitter_tool import TwitterCollectorTool
from ..utils.helpers import SearchHelper, generate_competitive_queries, find_solution_by_name
from .checkpoint_manager import CheckpointManager


class ResearchFlow(Flow[ResearchState]):
    """
    Main research flow orchestrating all 10 stages of the NicheIQ pipeline.

    Stages:
    1-4: Niche Input & Validation (Flow)
    5: Search & Discover (Flow + SerperDevTool)
    6: Pain Point Analysis (PainPointCrew)
    7-8.75: Unified Solution Pipeline (UnifiedSolutionCrew - ideation, competitive analysis, refinement, selection)
    9: Integrated Keyword Research + SEO Strategy (SEOStrategyCrew + DataForSEO)
    10: Final Report Generation (Flow)
    """

    def __init__(self, niche_description: str, allowed_project_types: Optional[List[str]] = None):
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

    def resume_from_checkpoint(self, checkpoint_path: Optional[Path] = None) -> bool:
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
            9: lambda: (
                self.state.solution_selection is not None and
                self.state.idea_generation is not None
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

    def _execute_remaining_stages(self) -> str:
        """
        Execute remaining stages after checkpoint resume.
        Manually calls stage methods based on current_stage.
        Validates prerequisites before executing each stage to prevent cascade failures.
        """
        current = self.state.current_stage
        logger.info(f"Executing stages from {current} onwards...")

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

            # Stages 7-8.75 now handled by unified solution pipeline
            if current <= 7 and self._validate_stage_prerequisites(7):
                logger.info("Executing Unified Solution Pipeline (Stages 7-8.75)...")
                self.stages_7_through_8_75_unified_solution_pipeline()
            elif current <= 7:
                logger.info("Skipping Stages 7-8.75 (Unified Solution Pipeline) - prerequisites not met")
                # Skip all solution stages if prerequisites not met
                self.state.current_stage = 9

            if current <= 9 and self._validate_stage_prerequisites(9):
                self.stage_9_generate_seo_strategy()
            elif current <= 9:
                logger.info("Skipping Stage 9 (SEO Strategy) - prerequisites not met")

            if current <= 9.5 and self._validate_stage_prerequisites(9.5):
                self.stage_9_5_refine_seo_scores()
            elif current <= 9.5:
                logger.info("Skipping Stage 9.5 (SEO Refinement) - prerequisites not met")

            if current <= 9.75 and self._validate_stage_prerequisites(9.75):
                self.stage_9_75_research_data_sources()
            elif current <= 9.75:
                logger.info("Skipping Stage 9.75 (Data Source Research) - prerequisites not met")

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
            logger.info(f"  - Industry boundaries defined")
        except Exception as e:
            logger.error(f"Failed to generate niche context with LLM: {e}")
            logger.warning("Proceeding without structured niche context")

        self.state.current_stage = 5

    def _generate_niche_context(self, niche_input: str):
        """Generate structured NicheContext using LLM with structured output."""
        from ..models.research_state import NicheContext
        from langchain_openai import ChatOpenAI

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

        # Use LangChain's ChatOpenAI directly for structured outputs
        # Moderate temperature (0.5) for balanced understanding + structured strategy
        structured_llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.5,
            api_key=settings.openai_api_key
        ).with_structured_output(NicheContext)

        # Generate structured output
        context = structured_llm.invoke(prompt)

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
        from ..utils.helpers import QueryGenerator
        query_gen = QueryGenerator()

        logger.info(f"Generating {settings.num_search_queries} strategic search queries...")
        queries = query_gen.generate_queries(
            self.niche_description,
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

        # Validate relevance using cheap model (gpt-4o-mini)
        logger.info("Validating Reddit thread relevance...")
        from ..utils.helpers import ThreadRelevanceValidator
        validator = ThreadRelevanceValidator()
        validated_reddit = validator.validate_batch(
            niche_description=self.niche_description,
            search_results=unique_reddit_results,
            batch_size=10
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

            # Validate relevance using cheap model (gpt-4o-mini)
            logger.info("Validating Twitter thread relevance...")
            validated_twitter = validator.validate_batch(
                niche_description=self.niche_description,
                search_results=unique_twitter_results,
                batch_size=10
            )

            # Filter to relevant results only
            twitter_urls = [result.url for result, is_relevant in validated_twitter if is_relevant]
            filtered_count = len(unique_twitter_results) - len(twitter_urls)
            logger.info(f"[OK] Filtered {filtered_count} irrelevant threads, kept {len(twitter_urls)} relevant Twitter discussions")

            # Collect Twitter content
            logger.info("Collecting Twitter threads...")
            # Direct synchronous call (nest_asyncio applied in main.py allows nested event loops)
            twitter_threads = self.twitter_tool.collect_threads(twitter_urls)
            logger.info(f"[OK] Collected {len(twitter_threads)} quality Twitter threads")
        else:
            logger.info("Twitter collection disabled (ENABLE_TWITTER=false) - skipping Twitter search and collection")

        # Collect Reddit content
        logger.info("Collecting Reddit posts and comments...")
        reddit_posts = self.reddit_tool.collect_posts(reddit_urls)
        logger.info(f"[OK] Collected {len(reddit_posts)} quality Reddit posts")

        # Store in social_content collection
        from ..models.social_content import SocialContentCollection
        self.state.social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=twitter_threads
        )

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
            niche_description=self.niche_description
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

        # Update stage first, then checkpoint (so resume skips this stage)
        self.state.current_stage = 7

        # Checkpoint: Save pain point analysis
        self.checkpoint_mgr.save_stage("stage_6_pain_points", self.state.pain_point_analysis)

    @listen(stage_6_analyze_pain_points)
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
                f"No high or medium priority pain points available - skipping solution pipeline"
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
                allowed_project_types=self.allowed_project_types
            )

            # Execute complete pipeline (4 tasks in sequence with context chaining)
            logger.info("Executing unified solution pipeline (4-task flow)...")
            refined_solutions, competitive_analysis, solution_selection = unified_crew.execute_pipeline()

            # Save results to state
            self.state.idea_generation = refined_solutions
            self.state.competitive_analysis = competitive_analysis
            self.state.solution_selection = solution_selection

            # Log results
            logger.info(f"[OK] Solution Pipeline Complete:")
            logger.info(f"  - Generated {len(refined_solutions.solution_ideas)} solutions")
            logger.info(f"  - Analyzed {len(competitive_analysis.solution_landscapes)} competitive landscapes")
            logger.info(f"  - Selected: {solution_selection.selected_solution_name}")

            # Update stage first (skip to SEO strategy)
            self.state.current_stage = 9

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
    ) -> list:
        """
        Phase 9.5c: Iteratively enrich keywords with DataForSEO using VALIDATED seeds.

        Uses VALIDATED seeds (pre-filtered by get_search_volume in Phase 9.5b) instead of
        raw conceptual keywords to maximize success rate and reduce API waste.

        Args:
            conceptual_keywords: Full list of ConceptualKeyword objects for cluster coverage calculation
            validated_seeds: Pre-validated keywords with search volume (from Phase 9.5b bulk validation)
            topic_clusters: List of TopicCluster objects from Phase 9.5a

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

            # Merge and deduplicate
            all_enriched.extend(suggestions)
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
            topic_clusters: List of TopicCluster objects
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
            topic_clusters: List of TopicCluster objects
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
            topic_clusters: List of TopicCluster objects
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
        )

        # Phase 9.5a: Conceptual keyword expansion (SEO crew)
        logger.info(f"Phase 9.5a: Conceptual keyword expansion for {selected_solution_name}...")
        try:
            expanded_keywords = seo_crew.expand_keywords_phase_1()
            logger.info(
                f"✓ Conceptual expansion complete: {len(expanded_keywords.keywords)} keywords, "
                f"{len(expanded_keywords.topic_clusters)} clusters"
            )

            # Phase 9.5b: Bulk validation with DataForSEO (NEW)
            logger.info("Phase 9.5b: Bulk validation of conceptual keywords with DataForSEO...")

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
            enriched_keywords = self._iterative_keyword_enrichment(
                conceptual_keywords=expanded_keywords.keywords,
                validated_seeds=quality_validated,
                topic_clusters=expanded_keywords.topic_clusters,
            )
            logger.info(f"✓ Enrichment complete: {len(enriched_keywords)} keywords with search data")

            # Generate comprehensive SEO strategy using 4-task multitask flow
            # Task 1: Keyword Analysis & Tiering
            # Task 2: Content & Technical Strategy
            # Task 3: Implementation Planning
            # Task 4: Final Synthesis
            logger.info(f"Creating final SEO strategy (4-task flow) for {selected_solution_name}...")
            seo_strategy = seo_crew.create_strategy_multitask(
                enriched_keywords=enriched_keywords,
                topic_clusters=expanded_keywords.topic_clusters
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

            # Validate tiering coverage (adaptive, no fixed target)
            if input_count > 20:
                if utilization < 0.3:  # Less than 30% tiered (very low coverage)
                    logger.warning(
                        f"⚠️ Low tiering coverage: {total_tiered}/{input_count} tiered ({utilization:.1%})"
                    )
                    logger.warning(
                        f"This suggests either: (1) Filtering was too aggressive (check STEP 0), "
                        f"or (2) Tier 3/4 grouping was incomplete. Review key_findings for details."
                    )
                elif utilization >= 0.6:  # 60%+ tiered (good coverage after filtering)
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
            refined_scalability = self._refine_scalability_score(
                base_score=selected_solution.seo_scalability_score,
                project_type=selected_solution.project_type,
                total_volume=total_monthly_volume,
                tier1_count=tier1_count,
                tier1_keywords=tier1_keywords
            )

            # 2. REFINE CAC ORGANIC
            refined_cac = self._refine_cac_organic(
                base_cac_str=selected_solution.estimated_cac_organic,
                tier1_keywords=tier1_keywords,
                total_volume=total_monthly_volume
            )

            # 3. REFINE PROGRAMMATIC SEO OPPORTUNITY (calculates page count)
            refined_programmatic_result = self._refine_programmatic_opportunity(
                original_assessment=selected_solution.programmatic_seo_opportunity,
                seo_report=seo_report,
                tier1_count=tier1_count
            )

            # Extract page count from programmatic refinement
            page_count = refined_programmatic_result.get('page_count', 0)
            refined_programmatic = refined_programmatic_result.get('assessment', '')

            # Update CAC metadata with page count
            refined_cac['metadata']['estimated_year1_pages'] = page_count

            # Update solution with refined scores
            selected_solution.seo_scalability_score_refined = refined_scalability['score']
            selected_solution.estimated_cac_organic_refined = refined_cac['cac_range']
            selected_solution.programmatic_seo_opportunity_refined = refined_programmatic
            selected_solution.estimated_indexable_pages = page_count  # Total potential indexable pages

            # Flatten metadata structure to match SEORefinementMetadata Pydantic model
            scalability_meta = refined_scalability['metadata']
            cac_meta = refined_cac['metadata']

            from ..models.solution_idea import SEORefinementMetadata
            selected_solution.seo_refinement_metadata = SEORefinementMetadata(
                baseline_volume_used=scalability_meta.get('baseline_volume'),
                volume_multiplier=scalability_meta.get('volume_multiplier'),
                tier1_multiplier=scalability_meta.get('tier1_multiplier'),
                competition_modifier=scalability_meta.get('competition_modifier'),
                base_cac=cac_meta.get('base_cac'),
                difficulty_multiplier=cac_meta.get('difficulty_multiplier'),
                volume_discount=cac_meta.get('volume_discount'),
                estimated_year1_pages=cac_meta.get('estimated_year1_pages')
            )

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
            report_generator = ReportGenerator(self.state, self.niche_description)
            final_report = report_generator.generate_report()

            self.state.final_report = final_report

        except Exception as e:
            logger.error(f"Failed to generate final report: {e}")
            raise  # Let the error propagate up

        # Save outputs
        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save structured final report
        report_filename = f"final_report_{timestamp}.json"
        report_filepath = output_dir / report_filename
        with open(report_filepath, "w", encoding="utf-8") as f:
            json.dump(final_report.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"[OK] Final report saved to: {report_filepath}")

        # Save complete raw state for reference
        raw_filename = f"research_state_raw_{timestamp}.json"
        raw_filepath = output_dir / raw_filename
        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(self.state.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"[OK] Raw research state saved to: {raw_filepath}")

        # Display executive summary
        from ..report.report_generator import ReportGenerator
        report_generator._display_executive_summary(final_report)

        # Store report paths
        self.report_path = str(report_filepath)
        self.raw_state_path = str(raw_filepath)

    def _refine_scalability_score(
        self,
        base_score: float,
        project_type: Optional[str],
        total_volume: int,
        tier1_count: int,
        tier1_keywords: list
    ) -> dict:
        """
        Refine SEO scalability score based on keyword data.

        Args:
            base_score: Original seo_scalability_score from Stage 7
            project_type: Project type (directory, aggregator, saas, etc.)
            total_volume: Total monthly search volume
            tier1_count: Number of Tier 1 (quick win) keywords
            tier1_keywords: List of TieredKeyword objects for Tier 1

        Returns:
            dict with 'score' (float) and 'metadata' (dict)
        """
        # Determine baseline volume by project type
        baselines = settings.seo_refinement_volume_baselines
        baseline_volume = baselines.get(project_type, 30_000)

        # Calculate volume multiplier (20% range, capped)
        volume_ratio = total_volume / baseline_volume if baseline_volume > 0 else 1.0
        volume_multiplier = min(settings.seo_refinement_max_volume_boost, max(0.8, volume_ratio))

        # Calculate Tier 1 multiplier (1% per keyword, max 20%)
        tier1_boost = min(settings.seo_refinement_max_tier1_boost, tier1_count * 0.01)
        tier1_multiplier = 1.0 + tier1_boost

        # Calculate competition modifier from Tier 1 keywords
        if tier1_keywords:
            competition_scores = []
            for kw in tier1_keywords:
                # Parse competition string like "LOW (30)" or "MEDIUM (53)"
                comp_str = kw.competition
                if '(' in comp_str:
                    try:
                        comp_value = int(comp_str.split('(')[1].replace(')', ''))
                        competition_scores.append(comp_value / 100.0)  # Normalize to 0-1
                    except (ValueError, IndexError):
                        pass

            avg_competition = sum(competition_scores) / len(competition_scores) if competition_scores else 0.5
            competition_modifier = 1.0 - avg_competition  # Lower competition = higher score
        else:
            competition_modifier = 0.5  # Neutral if no data

        # Calculate refined score
        refined_score = base_score * volume_multiplier * tier1_multiplier * competition_modifier
        refined_score = min(1.0, refined_score)  # Cap at 1.0

        metadata = {
            'baseline_volume': baseline_volume,
            'volume_multiplier': round(volume_multiplier, 3),
            'tier1_multiplier': round(tier1_multiplier, 3),
            'competition_modifier': round(competition_modifier, 3),
            'change': round(refined_score - base_score, 3)
        }

        return {
            'score': round(refined_score, 2),
            'metadata': metadata
        }

    def _refine_cac_organic(
        self,
        base_cac_str: Optional[str],
        tier1_keywords: list,
        total_volume: int
    ) -> dict:
        """
        Refine organic CAC estimate based on keyword difficulty and volume.

        Args:
            base_cac_str: Original CAC string like "$15-30 per customer"
            tier1_keywords: List of TieredKeyword objects for Tier 1
            total_volume: Total monthly search volume

        Returns:
            dict with 'cac_range' (str) and 'metadata' (dict)
        """
        if not base_cac_str:
            return {'cac_range': 'N/A', 'metadata': {'estimated_year1_pages': 0}}

        # Parse base CAC (extract midpoint)
        import re
        matches = re.findall(r'\$?(\d+)', base_cac_str)
        if len(matches) >= 2:
            base_cac = (int(matches[0]) + int(matches[1])) / 2
        elif len(matches) == 1:
            base_cac = int(matches[0])
        else:
            base_cac = 100  # Fallback

        # Calculate average Tier 1 difficulty
        if tier1_keywords:
            competition_scores = []
            for kw in tier1_keywords:
                comp_str = kw.competition
                if '(' in comp_str:
                    try:
                        comp_value = int(comp_str.split('(')[1].replace(')', ''))
                        competition_scores.append(comp_value)
                    except (ValueError, IndexError):
                        pass

            avg_difficulty = sum(competition_scores) / len(competition_scores) if competition_scores else 50
        else:
            avg_difficulty = 50  # Neutral

        difficulty_multiplier = 1.0 + (avg_difficulty / 100)

        # Calculate volume discount (economies of scale)
        volume_discount = max(
            settings.seo_refinement_volume_discount_floor,
            1.0 - (total_volume / 1_000_000)
        )

        # Calculate refined CAC
        refined_cac = base_cac * difficulty_multiplier * volume_discount

        # Create range (±20%)
        cac_low = int(refined_cac * 0.8 / 5) * 5  # Round to nearest $5
        cac_high = int(refined_cac * 1.2 / 5) * 5

        metadata = {
            'base_cac': base_cac,
            'difficulty_multiplier': round(difficulty_multiplier, 3),
            'volume_discount': round(volume_discount, 3),
            'avg_tier1_difficulty': round(avg_difficulty, 1),
            'estimated_year1_pages': 0  # Will be updated by _refine_programmatic_opportunity
        }

        return {
            'cac_range': f"${cac_low}-{cac_high}",
            'metadata': metadata
        }

    def _refine_programmatic_opportunity(
        self,
        original_assessment: Optional[str],
        seo_report,
        tier1_count: int
    ) -> dict:
        """
        Refine programmatic SEO opportunity with quantitative page count estimates.

        Args:
            original_assessment: Original qualitative assessment from Stage 7
            seo_report: SEOStrategyReport from Stage 9
            tier1_count: Number of Tier 1 keywords

        Returns:
            dict with 'assessment' (str) and 'page_count' (int)
        """
        # Calculate estimated page count
        page_count = 0

        # Tier 1 landing pages
        page_count += tier1_count

        # Geographic/category pages (Tier 3/4)
        if hasattr(seo_report, 'tier_3_geographic_groups') and seo_report.tier_3_geographic_groups:
            page_count += len(seo_report.tier_3_geographic_groups)

        if hasattr(seo_report, 'tier_4_category_groups') and seo_report.tier_4_category_groups:
            page_count += len(seo_report.tier_4_category_groups)

        # Topic cluster pages (pillar + supporting)
        if hasattr(seo_report, 'topic_clusters') and seo_report.topic_clusters:
            posts_per_cluster = 4  # Average pillar + 3 supporting posts
            page_count += len(seo_report.topic_clusters) * posts_per_cluster

        # Keyword-based page types
        if hasattr(seo_report, 'keyword_based_page_types') and seo_report.keyword_based_page_types:
            for page_type in seo_report.keyword_based_page_types:
                if hasattr(page_type, 'estimated_page_count'):
                    page_count += page_type.estimated_page_count

        # Build refined assessment
        refined = f"""**Refined Assessment (Based on Keyword Research):**

This solution can generate approximately **{page_count} indexable pages** in Year 1, comprising:

- **{tier1_count} Tier 1 landing pages** targeting quick-win keywords
"""

        if hasattr(seo_report, 'tier_3_geographic_groups') and seo_report.tier_3_geographic_groups:
            geo_count = len(seo_report.tier_3_geographic_groups)
            refined += f"- **{geo_count} geographic pages** for regional targeting\n"

        if hasattr(seo_report, 'tier_4_category_groups') and seo_report.tier_4_category_groups:
            cat_count = len(seo_report.tier_4_category_groups)
            refined += f"- **{cat_count} category pages** for vertical segmentation\n"

        if hasattr(seo_report, 'topic_clusters') and seo_report.topic_clusters:
            cluster_count = len(seo_report.topic_clusters)
            cluster_pages = cluster_count * 4
            refined += f"- **{cluster_pages} content pieces** across {cluster_count} topic clusters\n"

        refined += f"\n**Total Estimated Year 1 SEO Footprint:** {page_count} pages\n\n"
        refined += f"**Original Architectural Analysis:**\n{original_assessment or 'N/A'}"

        return {
            'assessment': refined,
            'page_count': page_count
        }

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
