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
from ..utils.helpers import SearchHelper, generate_competitive_queries
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

    def _find_solution_by_name(self, solution_name: str, solution_list: list) -> Optional['SolutionIdea']:
        """
        Find solution by name with fuzzy matching fallback.

        Handles cases where LLM returns shortened names (e.g., "PaperPath" instead of
        "PaperPath (Global Paperwork Aggregator)").

        Args:
            solution_name: Name to search for (may be shortened)
            solution_list: List of SolutionIdea objects to search

        Returns:
            Matching SolutionIdea or None if no match found
        """
        # Try exact match first
        exact_match = next(
            (sol for sol in solution_list if sol.solution_name == solution_name),
            None
        )

        if exact_match:
            return exact_match

        # Try fuzzy match: case-insensitive substring search
        # (handles "PaperPath" matching "PaperPath (Global Paperwork Aggregator)")
        logger.warning(
            f"Exact match failed for solution name '{solution_name}'. "
            f"Attempting fuzzy match..."
        )

        search_name_lower = solution_name.lower()
        for solution in solution_list:
            if search_name_lower in solution.solution_name.lower():
                logger.warning(
                    f"✓ Fuzzy match found: '{solution_name}' → '{solution.solution_name}'"
                )
                return solution

        # No match found
        logger.error(
            f"No match found for solution '{solution_name}' in available solutions: "
            f"{[sol.solution_name for sol in solution_list]}"
        )
        return None

    def _format_pain_points_for_keywords(self) -> str:
        """Format top pain points for keyword context."""
        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            return "No pain points available"

        formatted = []
        # Use top 10 pain points
        top_pain_points = sorted(
            self.state.pain_point_analysis.pain_points,
            key=lambda p: p.severity_score,
            reverse=True
        )[:10]

        for i, pp in enumerate(top_pain_points, 1):
            formatted.append(
                f"{i}. {pp.pain_point_title} (Severity: {pp.severity_score}/10)\n"
                f"   User language: {pp.user_quotes[:2] if pp.user_quotes else []}"
            )

        return "\n".join(formatted)

    def _format_solutions_for_keywords(self) -> str:
        """Format solution ideas for keyword context."""
        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            return "No solutions available"

        formatted = []
        for i, idea in enumerate(self.state.idea_generation.solution_ideas, 1):
            features = ", ".join(idea.core_features[:3]) if idea.core_features else "N/A"
            formatted.append(
                f"{i}. {idea.solution_name}\n"
                f"   Value Prop: {idea.value_proposition}\n"
                f"   Core Features: {features}"
            )

        return "\n".join(formatted)

    def _format_competitors_for_keywords(self) -> str:
        """Format competitive landscape for keyword context."""
        if not self.state.competitive_analysis:
            return "No competitive analysis available"

        formatted = []
        for landscape in self.state.competitive_analysis.solution_landscapes:
            competitors = ", ".join([c.competitor_name for c in landscape.competitors[:5]])
            formatted.append(
                f"Solution: {landscape.solution_idea}\n"
                f"Competitors: {competitors}\n"
                f"Gaps: {', '.join(landscape.competitive_gaps[:2])}"
            )

        return "\n\n".join(formatted)

    def _format_data_source_research(self, data_source_research) -> str:
        """Format data source research results for final report prompt."""
        if not data_source_research:
            return "No data source research conducted (solution doesn't require data aggregation OR stage was skipped)"

        formatted = []
        formatted.append(f"**Primary Data Sources ({len(data_source_research['primary_sources'])}):**")

        for i, ds in enumerate(data_source_research['primary_sources'], 1):
            formatted.append(f"\n{i}. **{ds['provider']}** ({ds['priority']} priority)")
            if ds['url']:
                formatted.append(f"   - URL: {ds['url']}")
            formatted.append(f"   - Access Model: {ds['access_model']}")
            if ds['cost_estimate']:
                formatted.append(f"   - Cost: {ds['cost_estimate']}")
            if ds['coverage']:
                formatted.append(f"   - Coverage: {ds['coverage']}")
            formatted.append(f"   - Integration Complexity: {ds['integration_complexity']}")
            if ds['priority_rationale']:
                formatted.append(f"   - Priority Rationale: {ds['priority_rationale']}")

        formatted.append(f"\n\n**Fallback Sources Available:** {data_source_research['fallback_sources_count']}")

        if data_source_research['estimated_monthly_cost']:
            formatted.append(f"\n**Estimated Monthly Cost:** {data_source_research['estimated_monthly_cost']}")

        if data_source_research['data_quality_risks']:
            formatted.append(f"\n\n**Data Quality Risks:**")
            for risk in data_source_research['data_quality_risks'][:5]:
                formatted.append(f"- {risk}")

        if data_source_research['implementation_roadmap']:
            formatted.append(f"\n\n**Implementation Roadmap:**\n{data_source_research['implementation_roadmap'][:300]}...")

        if data_source_research['seo_aligned_priorities']:
            formatted.append(f"\n\n**SEO-Aligned Priorities:**\n{data_source_research['seo_aligned_priorities'][:200]}...")

        return "\n".join(formatted)

    def _format_refined_seo_scores(self, solution) -> str:
        """Format refined SEO scores with comparison to originals."""
        if not solution:
            return "No solution details available"

        if not hasattr(solution, 'seo_scalability_score_refined') or solution.seo_scalability_score_refined is None:
            return "SEO refinement not performed (no keyword data available)"

        # Calculate changes
        scalability_change = solution.seo_scalability_score_refined - solution.seo_scalability_score
        scalability_pct = (scalability_change / solution.seo_scalability_score) * 100 if solution.seo_scalability_score > 0 else 0

        formatted = f"""
**SEO Scalability Score:**
- Original (Architectural): {solution.seo_scalability_score:.2f}
- Refined (Market-Based): {solution.seo_scalability_score_refined:.2f}
- Change: {scalability_pct:+.1f}% ({'+' if scalability_change > 0 else ''}{scalability_change:.2f})

**Estimated CAC Organic:**
- Original: {solution.estimated_cac_organic}
- Refined: {solution.estimated_cac_organic_refined}

**Programmatic SEO Opportunity (Enhanced):**
{solution.programmatic_seo_opportunity_refined}

**Refinement Metadata:**
{json.dumps(solution.seo_refinement_metadata if isinstance(solution.seo_refinement_metadata, dict) else solution.seo_refinement_metadata.model_dump(), indent=2) if solution.seo_refinement_metadata else 'N/A'}
"""
        return formatted

    def _format_solution_details(self, solution) -> str:
        """Format complete solution details for final report prompt."""
        if not solution:
            return "No solution details available"

        formatted = []
        formatted.append(f"**Solution Name:** {solution.solution_name}")
        formatted.append(f"\n**Description:** {solution.description}")
        formatted.append(f"\n**Value Proposition:** {solution.value_proposition}")

        if solution.pain_points_addressed:
            formatted.append(f"\n**Pain Points Addressed:**")
            for i, pain_point in enumerate(solution.pain_points_addressed, 1):
                formatted.append(f"  {i}. {pain_point}")

        if solution.core_features:
            formatted.append(f"\n**Core Features:**")
            for i, feature in enumerate(solution.core_features, 1):
                formatted.append(f"  {i}. {feature}")

        if solution.target_personas:
            formatted.append(f"\n**Target User Personas:**")
            for i, persona in enumerate(solution.target_personas, 1):
                formatted.append(f"  {i}. {persona}")

        if solution.technical_approach:
            formatted.append(f"\n**Technical Approach:** {solution.technical_approach}")

        if solution.differentiation_factors:
            formatted.append(f"\n**Differentiation Factors:**")
            for i, factor in enumerate(solution.differentiation_factors, 1):
                formatted.append(f"  {i}. {factor}")

        if solution.technical_feasibility_score is not None:
            formatted.append(f"\n**Technical Feasibility Score:** {solution.technical_feasibility_score:.2f}/1.0")

        if solution.market_fit_score is not None:
            formatted.append(f"**Market Fit Score:** {solution.market_fit_score:.2f}/1.0")

        if solution.estimated_development_time:
            formatted.append(f"\n**Estimated Development Time:** {solution.estimated_development_time}")

        if solution.pricing_strategy:
            formatted.append(f"\n**Pricing Strategy:** {solution.pricing_strategy}")

        if solution.requires_data_aggregation:
            formatted.append(f"\n**Data Aggregation Required:** Yes")
            if solution.data_sources:
                formatted.append(f"**Data Sources:** {', '.join(solution.data_sources)}")

        return "\n".join(formatted)

    def _format_competitive_landscape(self, context: dict) -> str:
        """Format competitive landscape for the selected solution."""
        if "selected_solution_competitors" not in context:
            return "No competitive analysis available for selected solution."

        competitors = context.get("selected_solution_competitors", [])
        if not competitors:
            return "No direct competitors identified for this solution."

        formatted = []
        formatted.append(f"**Competitive Intensity:** {context.get('selected_solution_competitive_intensity', 'Unknown')}")
        formatted.append(f"\n**Recommended Positioning:** {context.get('selected_solution_positioning', 'N/A')}")
        formatted.append(f"\n**Pricing Insights:** {context.get('selected_solution_pricing_insights', 'N/A')}")

        formatted.append(f"\n\n**Identified Competitors ({len(competitors)}):**")
        for i, comp in enumerate(competitors[:5], 1):  # Top 5 competitors
            formatted.append(f"\n{i}. **{comp['name']}** ({comp['type']} competitor)")
            if comp['url']:
                formatted.append(f"   - URL: {comp['url']}")
            formatted.append(f"   - Description: {comp['description']}")
            if comp['features']:
                formatted.append(f"   - Key Features: {', '.join(comp['features'][:3])}")
            if comp['pricing']:
                formatted.append(f"   - Pricing: {comp['pricing']}")
            if comp['strengths']:
                formatted.append(f"   - Strengths: {', '.join(comp['strengths'][:2])}")
            if comp['weaknesses']:
                formatted.append(f"   - Weaknesses: {', '.join(comp['weaknesses'][:2])}")

        if context.get("selected_solution_market_gaps"):
            formatted.append(f"\n\n**Market Gaps (Opportunities):**")
            for i, gap in enumerate(context["selected_solution_market_gaps"][:3], 1):
                formatted.append(f"{i}. {gap}")

        if context.get("selected_solution_differentiation"):
            formatted.append(f"\n\n**Differentiation Opportunities:**")
            for i, diff in enumerate(context["selected_solution_differentiation"][:3], 1):
                formatted.append(f"{i}. {diff}")

        return "\n".join(formatted)

    # NOTE: _generate_seed_keywords_with_llm() method was REMOVED (deprecated)
    # Seed generation is now handled by SEOStrategyCrew agent in Stage 9

    def _generate_keyword_clusters(self, keywords):
        """Generate keyword clusters by grouping similar keywords."""
        from ..models.keyword_data import KeywordCluster
        from collections import defaultdict

        # Group keywords by common root words
        clusters_dict = defaultdict(list)

        for kw in keywords:
            # Extract primary term (first 1-2 words)
            words = kw.keyword.lower().split()
            if len(words) >= 2:
                # Use first 2 words as cluster key
                cluster_key = ' '.join(words[:2])
            elif len(words) == 1:
                cluster_key = words[0]
            else:
                continue

            clusters_dict[cluster_key].append(kw)

        # Convert to KeywordCluster objects (keep clusters with 2+ keywords)
        clusters = []
        for cluster_name, cluster_keywords in clusters_dict.items():
            if len(cluster_keywords) >= 2:
                total_volume = sum(kw.search_volume for kw in cluster_keywords)
                avg_comp = sum(kw.competition for kw in cluster_keywords) / len(cluster_keywords)

                # Assess opportunity based on volume and competition
                if total_volume > 5000 and avg_comp < 0.5:
                    assessment = "High opportunity cluster with strong search volume and low competition"
                elif total_volume > 1000:
                    assessment = "Medium opportunity cluster with moderate search demand"
                else:
                    assessment = "Lower volume cluster, suitable for niche targeting"

                clusters.append(
                    KeywordCluster(
                        cluster_name=cluster_name.title(),
                        keywords=cluster_keywords,
                        total_search_volume=total_volume,
                        avg_competition=avg_comp,
                        opportunity_assessment=assessment,
                    )
                )

        # Sort by total search volume
        clusters.sort(key=lambda c: c.total_search_volume, reverse=True)

        # Return top 10 clusters
        return clusters[:10]

    def _identify_long_tail_keywords(self, keywords):
        """Identify long-tail keyword opportunities (3+ words, lower competition)."""
        from ..models.keyword_data import OpportunityLevel

        long_tail = []
        for kw in keywords:
            word_count = len(kw.keyword.split())
            # Long-tail: 3+ words, decent volume (100+), lower competition (<0.6)
            if (
                word_count >= 3
                and kw.search_volume >= 100
                and kw.competition < 0.6
                and kw.opportunity_level in [OpportunityLevel.HIGH, OpportunityLevel.MEDIUM]
            ):
                long_tail.append(kw)

        # Sort by opportunity score (volume / competition ratio)
        long_tail.sort(
            key=lambda k: k.search_volume / max(k.competition, 0.1), reverse=True
        )

        # Return top 20 long-tail opportunities
        return long_tail[:20]

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
        selected_solution = self._find_solution_by_name(
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
        selected_solution = self._find_solution_by_name(
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

    def _generate_research_metadata(self) -> Optional["ResearchMetadata"]:
        """
        Generate research metadata section with social content collection statistics.

        Returns:
            ResearchMetadata object with Reddit/Twitter stats, subreddit breakdown, and collection info
        """
        from ..models.research_state import ResearchMetadata, SubredditBreakdown

        if not self.state.social_content:
            return None

        try:
            # Count Reddit posts and comments
            reddit_posts_analyzed = len(self.state.social_content.reddit_posts)
            reddit_comments_analyzed = sum(len(post.comments) for post in self.state.social_content.reddit_posts)

            # Count Twitter threads
            twitter_threads_analyzed = len(self.state.social_content.twitter_threads)

            # Calculate subreddit breakdown (top 10)
            subreddit_counts: Dict[str, int] = {}
            for post in self.state.social_content.reddit_posts:
                subreddit_counts[post.subreddit] = subreddit_counts.get(post.subreddit, 0) + 1

            top_subreddits = [
                SubredditBreakdown(name=name, post_count=count)
                for name, count in sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            # Calculate data size (rough estimate from JSON serialization)
            social_content_json = self.state.social_content.model_dump_json()
            data_size_mb = len(social_content_json.encode('utf-8')) / (1024 * 1024)

            return ResearchMetadata(
                reddit_posts_analyzed=reddit_posts_analyzed,
                reddit_comments_analyzed=reddit_comments_analyzed,
                twitter_threads_analyzed=twitter_threads_analyzed,
                top_subreddits=top_subreddits,
                collection_date=self.state.social_content.collection_timestamp,
                data_size_mb=round(data_size_mb, 2)
            )
        except Exception as e:
            logger.warning(f"Failed to generate research metadata: {e}")
            return None

    def _generate_alternative_solutions(self) -> Optional[List["AlternativeSolution"]]:
        """
        Generate alternative solution summaries for runner-up solutions.

        Returns:
            List of AlternativeSolution objects (top 2 runner-ups with full details)
        """
        from ..models.research_state import AlternativeSolution

        if not self.state.solution_selection or not self.state.idea_generation:
            return None

        try:
            # Get runner-up solution names
            runner_up_names = self.state.solution_selection.runner_up_solutions or []
            if not runner_up_names:
                return None

            # Find full solution details from idea_generation stage
            all_solutions = {idea.solution_name: idea for idea in self.state.idea_generation.solution_ideas}

            # Build score lookup map from all_solution_scores
            score_map = {}
            if self.state.solution_selection.all_solution_scores:
                score_map = {
                    scores.solution_name: scores
                    for scores in self.state.solution_selection.all_solution_scores
                }

            alternative_solutions = []
            for runner_up_name in runner_up_names[:2]:  # Top 2 runners-up
                if runner_up_name not in all_solutions:
                    logger.warning(f"Runner-up solution '{runner_up_name}' not found in idea generation results")
                    continue

                solution = all_solutions[runner_up_name]

                # Get scores from all_solution_scores if available
                scores = score_map.get(runner_up_name)

                # Generate 2-3 paragraph summary
                summary = f"""**Overview:** {solution.description}

**Key Features:** {', '.join(solution.core_features[:5])}

**Target Users:** This solution is best suited for {', '.join(solution.target_personas[:2])}.
It differentiates through {solution.differentiation_factors[0] if solution.differentiation_factors else 'unique positioning'}.

**Technical Approach:** {solution.technical_approach}
"""

                # Use scores from SolutionSelection if available, otherwise fall back to solution fields
                if scores:
                    market_fit = scores.market_fit_score
                    technical_feasibility = scores.technical_feasibility_score
                    competitive_advantage = scores.competitive_advantage_score
                    seo_growth = scores.seo_growth_potential_score
                else:
                    # Fallback to solution fields if all_solution_scores not populated
                    market_fit = solution.market_fit_score or 0.0
                    technical_feasibility = solution.technical_feasibility_score or 0.0
                    competitive_advantage = solution.market_fit_score or 0.7  # Use market_fit as proxy
                    seo_growth = solution.seo_scalability_score or 0.0

                # Determine pivot trigger based on solution characteristics
                pivot_trigger = f"Pivot to {runner_up_name} if: "
                if market_fit > 0.9:
                    pivot_trigger += "user research reveals significantly higher demand for this specific pain point, "
                if seo_growth > 0.85:
                    pivot_trigger += "SEO keyword volume for this solution is 2x higher than primary choice, "
                if technical_feasibility > 0.9:
                    pivot_trigger += "faster time-to-market is critical and this solution has simpler tech requirements"

                alternative_solutions.append(AlternativeSolution(
                    solution_name=solution.solution_name,
                    summary=summary.strip(),
                    market_fit_score=market_fit,
                    technical_feasibility_score=technical_feasibility,
                    competitive_advantage_score=competitive_advantage,
                    seo_growth_potential_score=seo_growth,
                    key_differentiator=solution.differentiation_factors[0] if solution.differentiation_factors else "Unique market positioning",
                    best_suited_for=solution.target_personas[0] if solution.target_personas else "Target user segment",
                    pivot_trigger=pivot_trigger.rstrip(", ")
                ))

            return alternative_solutions if alternative_solutions else None
        except Exception as e:
            logger.warning(f"Failed to generate alternative solutions: {e}")
            return None

    def _generate_competitive_landscape_matrix(self) -> Optional["CompetitiveLandscapeMatrix"]:
        """
        Generate cross-solution competitive analysis showing competitor overlap and patterns.

        Returns:
            CompetitiveLandscapeMatrix with competitor overlap and intensity analysis
        """
        from ..models.research_state import CompetitiveLandscapeMatrix, CompetitorMatrixEntry, CompetitiveIntensityEntry

        if not self.state.competitive_analysis:
            return None

        try:
            # Collect all solution names
            all_solutions = [landscape.solution_name for landscape in self.state.competitive_analysis.solution_landscapes]

            # Build competitor overlap map
            competitor_appearances: Dict[str, Dict[str, Any]] = {}
            competitive_intensity_list: List[CompetitiveIntensityEntry] = []

            for landscape in self.state.competitive_analysis.solution_landscapes:
                # Track competitive intensity
                competitive_intensity_list.append(
                    CompetitiveIntensityEntry(
                        solution_name=landscape.solution_name,
                        intensity=landscape.competitive_intensity
                    )
                )

                # Track competitor appearances
                for competitor in landscape.competitors:
                    if competitor.name not in competitor_appearances:
                        competitor_appearances[competitor.name] = {
                            "solutions": [],
                            "type": competitor.competitor_type,
                            "threat_level": "medium"  # default
                        }
                    competitor_appearances[competitor.name]["solutions"].append(landscape.solution_name)

            # Create competitor matrix entries (only multi-solution competitors)
            competitor_overlap = [
                CompetitorMatrixEntry(
                    competitor_name=name,
                    solutions_competed=data["solutions"],
                    competitor_type=data["type"],
                    threat_level=data["threat_level"]
                )
                for name, data in competitor_appearances.items()
                if len(data["solutions"]) > 1  # Only show competitors in multiple solution spaces
            ]

            # Sort by number of solutions competed (most versatile competitors first)
            competitor_overlap.sort(key=lambda x: len(x.solutions_competed), reverse=True)

            # Generate market insight
            intensity_counts = {}
            for entry in competitive_intensity_list:
                intensity_counts[entry.intensity] = intensity_counts.get(entry.intensity, 0) + 1

            market_insight = f"Analyzed {len(all_solutions)} solution concepts across the competitive landscape. "
            if intensity_counts:
                market_insight += f"Competitive intensity distribution: {', '.join(f'{k}: {v}' for k, v in intensity_counts.items())}. "
            if competitor_overlap:
                market_insight += f"{len(competitor_overlap)} competitors appear across multiple solution spaces, indicating platform players with broad market coverage. "
                top_competitor = competitor_overlap[0]
                market_insight += f"Most versatile competitor: {top_competitor.competitor_name} (competes in {len(top_competitor.solutions_competed)} solution categories)."

            return CompetitiveLandscapeMatrix(
                all_solutions_analyzed=all_solutions,
                competitor_overlap=competitor_overlap,
                competitive_intensity_by_solution=competitive_intensity_list,
                market_insight=market_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate competitive landscape matrix: {e}")
            return None

    def _generate_evidence_appendix(self) -> Optional["EvidenceAppendix"]:
        """
        Generate evidence appendix with top Reddit threads and pain point quote sources.

        Returns:
            EvidenceAppendix with traceability from pain points to original posts
        """
        from ..models.research_state import EvidenceAppendix, TopRedditThread, PainPointEvidence, QuoteSource

        if not self.state.social_content or not self.state.pain_point_analysis:
            return None

        try:
            # Extract top 10 Reddit threads by engagement score
            reddit_posts = sorted(
                self.state.social_content.reddit_posts,
                key=lambda p: p.score,
                reverse=True
            )[:10]

            top_reddit_threads = [
                TopRedditThread(
                    post_id=post.post_id,
                    title=post.title,
                    subreddit=post.subreddit,
                    score=post.score,
                    num_comments=post.num_comments,
                    url=post.url,
                    key_insight=f"High-engagement discussion ({post.score} score, {post.num_comments} comments) in r/{post.subreddit}"
                )
                for post in reddit_posts
            ]

            # Create post ID to metadata mapping
            post_metadata: Dict[str, Dict[str, Any]] = {}
            for post in self.state.social_content.reddit_posts:
                post_metadata[post.post_id] = {
                    "subreddit": post.subreddit,
                    "score": post.score,
                    "url": post.url
                }
            for thread in self.state.social_content.twitter_threads:
                post_metadata[thread.thread_id] = {
                    "subreddit": "Twitter",  # Use "Twitter" as platform indicator
                    "score": thread.original_tweet.likes,
                    "url": thread.original_tweet.url
                }

            # Map pain points to source posts
            pain_point_quote_sources = []
            for pain_point in self.state.pain_point_analysis.pain_points:
                quotes_with_sources = []
                # Match quotes to source posts using source_post_ids if available
                source_ids = pain_point.source_post_ids if hasattr(pain_point, 'source_post_ids') else []

                for i, quote in enumerate(pain_point.representative_quotes[:3]):  # Top 3 quotes
                    source_id = source_ids[i] if i < len(source_ids) else "unknown"
                    metadata = post_metadata.get(source_id, {"subreddit": "Unknown", "score": 0})

                    quotes_with_sources.append(QuoteSource(
                        quote=quote[:200] + "..." if len(quote) > 200 else quote,  # Truncate long quotes
                        post_id=source_id,
                        subreddit=metadata["subreddit"],
                        score=str(metadata["score"])
                    ))

                pain_point_quote_sources.append(PainPointEvidence(
                    pain_point_title=pain_point.title,
                    quotes_with_sources=quotes_with_sources
                ))

            return EvidenceAppendix(
                top_reddit_threads=top_reddit_threads,
                pain_point_quote_sources=pain_point_quote_sources
            )
        except Exception as e:
            logger.warning(f"Failed to generate evidence appendix: {e}")
            return None

    def _generate_data_infrastructure_roadmap(self) -> Optional["DataInfrastructureRoadmap"]:
        """
        Generate 3-phase data infrastructure implementation roadmap with cost projections.

        Returns:
            DataInfrastructureRoadmap with phased implementation plan and cost scaling insight
        """
        from ..models.research_state import DataInfrastructureRoadmap, DataInfrastructurePhase

        if not self.state.data_source_research:
            return None

        try:
            data_research = self.state.data_source_research

            # Extract implementation roadmap phases from existing data
            phases = []

            # NEW: Use structured implementation_phases if available
            if data_research.implementation_phases:
                phases = [
                    DataInfrastructurePhase(
                        phase_number=phase.phase_number,
                        phase_name=phase.phase_name,
                        timeline=phase.timeline,
                        data_sources=phase.data_sources,
                        estimated_monthly_cost=phase.estimated_monthly_cost,
                        key_risks=phase.fallback_strategies[:3] if phase.fallback_strategies else []
                    )
                    for phase in data_research.implementation_phases
                ]
            # FALLBACK: Parse implementation roadmap text if available
            elif data_research.implementation_roadmap:
                roadmap_text = data_research.implementation_roadmap
                # Extract phases from formatted text (simple parsing)
                phase_texts = roadmap_text.split("Phase ")
                for i, phase_text in enumerate(phase_texts[1:], start=1):  # Skip first empty split
                    lines = phase_text.strip().split("\n")
                    phase_name_line = lines[0] if lines else f"Phase {i}"

                    # Extract phase name (e.g., "1 (Months 1-3): Launch MVP..." -> "MVP")
                    if ":" in phase_name_line:
                        phase_name_full = phase_name_line.split(":", 1)[1].strip()
                        phase_name = phase_name_full.split()[0] if phase_name_full else f"Phase {i}"
                        timeline_match = phase_name_line.split("(")[1].split(")")[0] if "(" in phase_name_line else f"Months {i*3-2}-{i*3}"
                    else:
                        phase_name = f"Phase {i}"
                        timeline_match = f"Months {i*3-2}-{i*3}"

                    # Extract data sources mentioned in phase text
                    data_sources = []
                    for source in data_research.primary_data_sources[:3]:  # Top 3 sources
                        if source.provider.lower() in phase_text.lower():
                            data_sources.append(source.provider)

                    phases.append(DataInfrastructurePhase(
                        phase_number=i,
                        phase_name=phase_name if phase_name != f"Phase {i}" else ["MVP", "Growth", "Scale"][i-1] if i <= 3 else f"Phase {i}",
                        timeline=timeline_match,
                        data_sources=data_sources if data_sources else [s.provider for s in data_research.primary_data_sources[:2]],
                        estimated_monthly_cost=data_research.estimated_monthly_cost.split(";")[i-1].strip() if ";" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost,
                        key_risks=[risk.strip() for risk in data_research.data_quality_risks[:2]] if data_research.data_quality_risks else []
                    ))

            # If parsing failed, create default 3-phase structure
            if len(phases) < 3:
                phases = [
                    DataInfrastructurePhase(
                        phase_number=1,
                        phase_name="MVP",
                        timeline="Months 1-3",
                        data_sources=[s.provider for s in data_research.primary_data_sources[:2]],
                        estimated_monthly_cost=data_research.estimated_monthly_cost.split(";")[0] if ";" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost.split("/")[0] if "/" in data_research.estimated_monthly_cost else data_research.estimated_monthly_cost,
                        key_risks=[data_research.data_quality_risks[0]] if data_research.data_quality_risks else []
                    ),
                    DataInfrastructurePhase(
                        phase_number=2,
                        phase_name="Growth",
                        timeline="Months 4-6",
                        data_sources=[s.provider for s in data_research.primary_data_sources],
                        estimated_monthly_cost="Scale with usage",
                        key_risks=[data_research.data_quality_risks[1]] if len(data_research.data_quality_risks) > 1 else []
                    ),
                    DataInfrastructurePhase(
                        phase_number=3,
                        phase_name="Scale",
                        timeline="Months 7-12",
                        data_sources=[s.provider for s in data_research.primary_data_sources] + [s.provider for s in data_research.fallback_sources[:1]],
                        estimated_monthly_cost="High volume - implement cost optimization",
                        key_risks=[data_research.data_quality_risks[2]] if len(data_research.data_quality_risks) > 2 else ["Cost scaling at high volume"]
                    )
                ]

            # Generate cost scaling insight
            cost_scaling_insight = f"Data infrastructure costs start at {phases[0].estimated_monthly_cost} during MVP, " \
                                   f"scaling with user growth. {data_research.data_quality_risks[0] if data_research.data_quality_risks else 'Monitor API rate limits and implement fallback strategies'} " \
                                   f"Critical mitigation: Implement tiered data source strategy with free/low-cost sources for baseline features, " \
                                   f"premium APIs for advanced personalization. Monitor unit economics to prevent cost spiral at scale."

            return DataInfrastructureRoadmap(
                phases=phases[:3],  # Ensure exactly 3 phases
                cost_scaling_insight=cost_scaling_insight
            )
        except Exception as e:
            logger.warning(f"Failed to generate data infrastructure roadmap: {e}")
            return None

    def _generate_decision_framework(self) -> Optional["DecisionFramework"]:
        """
        Generate go/no-go criteria and pivot triggers for decision-making.

        Returns:
            DecisionFramework with actionable criteria based on research findings
        """
        from ..models.research_state import DecisionFramework, DecisionCriterion, PivotTrigger

        if not self.state.pain_point_analysis or not self.state.solution_selection:
            return None

        try:
            # Generate go criteria based on research findings
            go_criteria = [
                DecisionCriterion(
                    criterion_type="go",
                    condition="Validate 3+ high-severity pain points (severity >0.7) from Reddit threads with score >20",
                    rationale="Confirms real user demand with social validation signals"
                ),
                DecisionCriterion(
                    criterion_type="go",
                    condition="At least 2 identified competitors have <$10M funding or are bootstrapped",
                    rationale="Indicates beatable competitive landscape without dominant well-funded players"
                ),
            ]

            # Add SEO-related go criterion if available
            if self.state.seo_strategy_report:
                go_criteria.append(DecisionCriterion(
                    criterion_type="go",
                    condition="Top 10 target keywords show >10k monthly combined search volume with competition <60",
                    rationale="Validates organic acquisition channel viability and CAC estimates"
                ))

            # Add data sourcing go criterion if applicable
            if self.state.data_source_research:
                go_criteria.append(DecisionCriterion(
                    criterion_type="go",
                    condition="Secure 2+ core data sources with confirmed API access or free tier availability",
                    rationale="De-risks technical feasibility and MVP launch timeline"
                ))

            # Generate no-go criteria
            no_go_criteria = [
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="Pain point validation shows <5 discussions total or <10 total mentions across all pain points",
                    rationale="Insufficient market signal indicates weak demand or poor niche-market fit"
                ),
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="Competitive analysis reveals 3+ direct competitors with >$50M funding each",
                    rationale="Over-saturated market with well-capitalized incumbents makes differentiation extremely difficult"
                ),
                DecisionCriterion(
                    criterion_type="no-go",
                    condition="SEO keyword research shows <5k monthly search volume for top 10 keywords combined",
                    rationale="Insufficient organic demand makes customer acquisition cost prohibitively high"
                ),
            ]

            # Add data sourcing no-go criterion if applicable
            if self.state.data_source_research:
                no_go_criteria.append(DecisionCriterion(
                    criterion_type="no-go",
                    condition="Data source costs exceed $5k/month at 10k users, breaking unit economics",
                    rationale="Unsustainable cost structure prevents profitable scaling"
                ))

            # Generate pivot triggers based on alternative solutions
            pivot_triggers = []
            if self.state.solution_selection.runner_up_solutions:
                for runner_up_name in self.state.solution_selection.runner_up_solutions[:2]:
                    pivot_triggers.append(PivotTrigger(
                        trigger_condition=f"User interviews reveal {runner_up_name} pain points are 2x more frequently mentioned than selected solution pain points",
                        pivot_to_solution=runner_up_name,
                        rationale="Market demand signal stronger for alternative approach, justifies strategic pivot"
                    ))

            # Add generic pivot trigger
            pivot_triggers.append(PivotTrigger(
                trigger_condition="MVP validation shows <10% conversion from landing page to signup after 100+ visitors",
                pivot_to_solution=self.state.solution_selection.runner_up_solutions[0] if self.state.solution_selection.runner_up_solutions else "Alternative approach",
                rationale="Low conversion indicates value proposition mismatch, warrants testing alternative solution framing"
            ))

            return DecisionFramework(
                go_criteria=go_criteria,
                no_go_criteria=no_go_criteria,
                pivot_triggers=pivot_triggers
            )
        except Exception as e:
            logger.warning(f"Failed to generate decision framework: {e}")
            return None

    @listen(stage_9_75_research_data_sources)
    def stage_10_generate_report(self):
        """
        Stage 10: Final Report Generation

        Synthesizes all research findings into a comprehensive FinalReport using LLM.
        """
        logger.info("=" * 80)
        logger.info("STAGE 10: Final Report Generation")
        logger.info("=" * 80)

        from datetime import datetime

        # Prepare synthesis context from all stages
        synthesis_context = self._prepare_synthesis_context()

        # Create synthesis prompt
        synthesis_prompt = self._create_synthesis_prompt(synthesis_context)

        # Generate FinalReport using LLM with structured output
        logger.info("Generating comprehensive final report with LLM synthesis...")
        try:
            final_report = self._generate_final_report_with_llm(synthesis_prompt)

            # Add the comprehensive SEO strategy
            if self.state.seo_strategy_report:
                final_report.seo_strategy = self.state.seo_strategy_report
                logger.info("[OK] SEO strategy integrated into final report")

            # Add the data source research results
            if self.state.data_source_research:
                final_report.data_source_research = self.state.data_source_research
                logger.info("[OK] Data source research integrated into final report")

            # Generate enhanced report sections (Phase 3 - data preservation and traceability)
            logger.info("Generating enhanced report sections...")

            final_report.research_metadata = self._generate_research_metadata()
            if final_report.research_metadata:
                logger.info(f"[OK] Research metadata generated: {final_report.research_metadata.reddit_posts_analyzed} Reddit posts, {final_report.research_metadata.twitter_threads_analyzed} Twitter threads")

            final_report.alternative_solutions = self._generate_alternative_solutions()
            if final_report.alternative_solutions:
                logger.info(f"[OK] Alternative solutions generated: {len(final_report.alternative_solutions)} runner-up solutions detailed")

            final_report.competitive_landscape_matrix = self._generate_competitive_landscape_matrix()
            if final_report.competitive_landscape_matrix:
                logger.info(f"[OK] Competitive landscape matrix generated: {len(final_report.competitive_landscape_matrix.competitor_overlap)} multi-solution competitors identified")

            final_report.evidence_appendix = self._generate_evidence_appendix()
            if final_report.evidence_appendix:
                logger.info(f"[OK] Evidence appendix generated: {len(final_report.evidence_appendix.top_reddit_threads)} top threads, {len(final_report.evidence_appendix.pain_point_quote_sources)} pain points with source attribution")

            final_report.data_infrastructure_roadmap = self._generate_data_infrastructure_roadmap()
            if final_report.data_infrastructure_roadmap:
                logger.info(f"[OK] Data infrastructure roadmap generated: {len(final_report.data_infrastructure_roadmap.phases)}-phase implementation plan")

            final_report.decision_framework = self._generate_decision_framework()
            if final_report.decision_framework:
                logger.info(f"[OK] Decision framework generated: {len(final_report.decision_framework.go_criteria)} go criteria, {len(final_report.decision_framework.no_go_criteria)} no-go criteria, {len(final_report.decision_framework.pivot_triggers)} pivot triggers")

            # Content categorization from Stage 6 Task 1
            if self.state.pain_point_analysis and self.state.pain_point_analysis.content_categorization:
                final_report.content_categorization = self.state.pain_point_analysis.content_categorization
                logger.info(
                    f"[OK] Content categorization included: "
                    f"{len(final_report.content_categorization.theme_categories)} theme categories, "
                    f"{len(final_report.content_categorization.user_segments)} user segments"
                )

            self.state.final_report = final_report
            logger.info("[OK] Final report synthesis complete with enhanced sections")
        except Exception as e:
            logger.error(f"Failed to generate final report with LLM: {e}")
            logger.warning("Falling back to basic report generation")
            final_report = self._generate_fallback_report()
            self.state.final_report = final_report

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
        self._display_executive_summary(final_report)

        # Store report paths
        self.report_path = str(report_filepath)
        self.raw_state_path = str(raw_filepath)

    def _prepare_synthesis_context(self) -> dict:
        """Extract key data from all stages for synthesis."""
        context = {
            "niche": self.niche_description,
            "research_pain_points": [],  # RENAMED: Make distinction clear
            "solutions": [],
            "competitors": [],
            "keywords": {},
        }

        # Extract RESEARCH-DISCOVERED pain points (from Stage 6 social media analysis)
        # These are validated findings from actual user discussions, NOT solution assumptions
        if self.state.pain_point_analysis:
            context["research_pain_points"] = [
                {
                    "title": pp.title,
                    "description": pp.description,
                    "severity": pp.severity_score,  # EXACT score, no rounding
                    "wtp": pp.willingness_to_pay,  # EXACT score, no rounding
                    "opportunity": pp.opportunity_level.value,
                    "mention_count": pp.mention_count,
                }
                for pp in self.state.pain_point_analysis.pain_points[:10]  # Top 10
            ]
            context["pain_points_summary"] = self.state.pain_point_analysis.analysis_summary
            context["total_pain_points_validated"] = len(self.state.pain_point_analysis.pain_points)
            # Note: Analyst extraction count is only visible during crew execution via logs,
            # not stored in final state. The validation check in PainPointCrew.analyze() logs any discrepancies.

        # Extract solution selection (Stage 8.5)
        if self.state.solution_selection:
            context["selected_solution"] = self.state.solution_selection.selected_solution_name
            context["selection_rationale"] = self.state.solution_selection.selection_rationale
            context["runner_up_solutions"] = self.state.solution_selection.runner_up_solutions
            context["selection_scores"] = self.state.solution_selection.selection_criteria_scores
            context["recommended_focus"] = self.state.solution_selection.recommended_focus

        # Extract COMPLETE selected solution details (NEW - for detailed description)
        context["selected_solution_full_details"] = None
        if self.state.solution_selection and self.state.idea_generation:
            selected_name = self.state.solution_selection.selected_solution_name
            for sol in self.state.idea_generation.solution_ideas:
                if sol.solution_name == selected_name:
                    context["selected_solution_full_details"] = sol
                    break

        # Extract solutions (for reference)
        if self.state.idea_generation:
            context["solutions"] = [
                {
                    "name": sol.solution_name,
                    "value_prop": sol.value_proposition,
                    "features": sol.core_features[:5],  # Top 5 features
                    "market_fit": sol.market_fit_score,
                    "feasibility": sol.technical_feasibility_score,
                    "requires_data": sol.requires_data_aggregation,
                    "data_sources": sol.data_sources if sol.data_sources else [],
                }
                for sol in self.state.idea_generation.solution_ideas[:3]  # Top 3
            ]

        # Extract competitive insights
        if self.state.competitive_analysis:
            context["top_opportunities"] = self.state.competitive_analysis.top_opportunities
            context["strategic_recommendations"] = (
                self.state.competitive_analysis.strategic_recommendations
            )
            context["competitor_count"] = sum(
                len(landscape.competitors)
                for landscape in self.state.competitive_analysis.solution_landscapes
            )

            # Extract competitors for the SELECTED solution
            if self.state.solution_selection:
                selected_name = self.state.solution_selection.selected_solution_name
                for landscape in self.state.competitive_analysis.solution_landscapes:
                    if landscape.solution_name == selected_name:
                        context["selected_solution_competitors"] = [
                            {
                                "name": comp.name,
                                "url": comp.url,
                                "type": comp.competitor_type.value,
                                "description": comp.description,
                                "features": comp.key_features,
                                "pricing": comp.pricing_model,
                                "strengths": comp.strengths if comp.strengths else [],
                                "weaknesses": comp.weaknesses if comp.weaknesses else [],
                            }
                            for comp in (landscape.competitors if landscape.competitors else [])
                        ]
                        context["selected_solution_market_gaps"] = landscape.market_gaps
                        context["selected_solution_differentiation"] = landscape.differentiation_opportunities
                        context["selected_solution_competitive_intensity"] = landscape.competitive_intensity
                        context["selected_solution_positioning"] = landscape.recommended_positioning
                        context["selected_solution_pricing_insights"] = landscape.pricing_insights
                        break

        # Extract keyword validation
        if self.state.keyword_validation:
            context["keywords"] = {
                "total_market_size": self.state.keyword_validation.overall_market_size,
                "market_assessment": self.state.keyword_validation.market_assessment,
                "total_keywords": sum(
                    r.total_keywords_analyzed for r in self.state.keyword_validation.reports
                ),
                "high_opportunity_count": sum(
                    len(r.high_opportunity_keywords)
                    for r in self.state.keyword_validation.reports
                ),
            }

        # Extract data source research (Stage 9.75)
        if self.state.data_source_research:
            context["data_source_research"] = {
                "primary_sources": [
                    {
                        "provider": ds.provider,
                        "url": ds.url,
                        "access_model": ds.access_model,
                        "cost_estimate": ds.cost_estimate,
                        "coverage": ds.coverage,
                        "integration_complexity": ds.integration_complexity,
                        "priority": ds.priority,
                        "priority_rationale": ds.priority_rationale,
                    }
                    for ds in self.state.data_source_research.primary_data_sources
                ],
                "fallback_sources_count": len(self.state.data_source_research.fallback_sources) if self.state.data_source_research.fallback_sources else 0,
                "estimated_monthly_cost": self.state.data_source_research.estimated_monthly_cost,
                "data_quality_risks": self.state.data_source_research.data_quality_risks,
                "implementation_roadmap": self.state.data_source_research.implementation_roadmap,
                "seo_aligned_priorities": self.state.data_source_research.seo_aligned_priorities,
            }
        else:
            context["data_source_research"] = None

        return context

    def _create_synthesis_prompt(self, context: dict) -> str:
        """Create comprehensive synthesis prompt for final report generation."""
        return f"""You are a strategic market research analyst creating a comprehensive final report with an SEO-FIRST, organic acquisition focus.

**RESEARCH PHILOSOPHY:**
This analysis prioritizes solutions with LOW customer acquisition costs (CAC) through organic channels.
Solutions were evaluated on their ability to generate indexable content programmatically (directories, aggregators)
vs requiring manual content marketing (traditional SaaS). The goal is identifying bootstrappable, SEO-scalable opportunities.

**Research Context:**
Niche: {context['niche']}

**SELECTED SOLUTION (Primary Focus):**
- Solution: {context.get('selected_solution', 'Not selected')}
- Selection Rationale: {context.get('selection_rationale', 'N/A')}
- Runner-ups: {', '.join(context.get('runner_up_solutions', []))}
- Recommended Focus: {context.get('recommended_focus', 'N/A')}

**COMPLETE SELECTED SOLUTION DETAILS:**
{self._format_solution_details(context.get('selected_solution_full_details'))}

**RESEARCH-DISCOVERED Pain Points (Stage 6 - Social Media Analysis):**
{json.dumps(context.get('research_pain_points', []), indent=2)}

Pain Points Summary: {context.get('pain_points_summary', 'N/A')}
Total Pain Points Validated: {context.get('total_pain_points_validated', 0)}

**CRITICAL: Research vs Solution Pain Points:**
The pain points listed above are RESEARCH-DISCOVERED from actual user discussions (Stage 6).
These are validated findings from Reddit/Twitter analysis, NOT assumptions made during solution ideation.

DO NOT confuse these with "pain_points_addressed" in the solution details - those are the solution creator's
assumptions about what pain points a solution COULD address. Only use research-discovered pain points for
the "top_pain_points" field in the final report.

**Note on Pain Point Validation Process:**
Pain points were extracted by an analyst agent and then scored by a validator agent using strict 1:1 mapping.
The validator ONLY added severity/WTP scores - it did not add, remove, or merge pain points. Any discrepancies
between extraction and validation counts are logged during execution for quality assurance.

**Solutions Developed (All Evaluated):**
{json.dumps(context.get('solutions', []), indent=2)}

**Competitive Intelligence (All Solutions):**
- Top Opportunities: {', '.join(str(o) for o in context.get('top_opportunities', [])[:5])}
- Total Competitors Analyzed: {context.get('competitor_count', 0)}
- Strategic Recommendations: {context.get('strategic_recommendations', 'N/A')}

**Competitive Analysis for SELECTED SOLUTION:**
{self._format_competitive_landscape(context)}

**Keyword Validation:**
- Total Search Volume: {context.get('keywords', {}).get('total_market_size', 0):,}
- Total Keywords Analyzed: {context.get('keywords', {}).get('total_keywords', 0)}
- High Opportunity Keywords: {context.get('keywords', {}).get('high_opportunity_count', 0)}
- Market Assessment: {context.get('keywords', {}).get('market_assessment', 'N/A')}

**Data Source Research (Stage 9.75):**
{self._format_data_source_research(context.get('data_source_research'))}

**REFINED SEO SCORES (Stage 9.5 - Post-Keyword Discovery):**
{self._format_refined_seo_scores(context.get('selected_solution_full_details'))}

**IMPORTANT NOTE ON SEO SCORES:**
When generating the estimated_cac_breakdown section (requirement #19), use the REFINED scores if available
(seo_scalability_score_refined, estimated_cac_organic_refined). Fall back to original scores only if
refinement data is not present.

Show both original and refined estimates to demonstrate the impact of keyword research:
- "Initial estimate (architectural): {{original_score}}"
- "Refined estimate (market-based): {{refined_score}}"
- "Change: {{percentage}}% increase/decrease"

This transparency shows how actual keyword data validates or adjusts the architectural estimates.

**Your Task:**
Generate a comprehensive final report focused on the SELECTED SOLUTION with the following sections:

1. **executive_summary**:
   - 4-6 sentences synthesizing the entire research
   - Highlight the selected solution and why it was chosen
   - Key findings, market opportunity, recommended direction
   - Make it compelling and actionable

2. **selected_solution_name**:
   - The name of the selected solution (string): "{context.get('selected_solution', 'Unknown')}"

3. **selection_rationale**:
   - Copy the selection rationale from above (2-3 paragraphs explaining WHY this solution was selected)

4. **runner_up_solutions**:
   - List of alternative solution names that were considered (strings)

5. **selection_criteria_scores**:
   - Dictionary of scores from the selection process: {context.get('selection_scores', {})}
   - Copy these exact scores as a dictionary (e.g., {{"market_fit": 0.85, "technical_feasibility": 0.92, ...}})

6. **recommended_focus**:
   - Strategic focus recommendation: {context.get('recommended_focus', 'N/A')}
   - Copy this exact recommendation (string)

7. **selected_solution_details**:
   - Copy the COMPLETE SolutionIdea object from the COMPLETE SELECTED SOLUTION DETAILS section above
   - This should include ALL fields: solution_name, value_proposition, problem_it_solves, core_features,
     target_user_personas, unique_selling_points, technical_feasibility_score, market_fit_score,
     development_complexity, monetization_strategy, pricing_model, requires_data_aggregation,
     data_sources, implementation_risks, differentiation_strategy
   - Simply reference the structured data - DO NOT regenerate or modify it

8. **solution_user_journey**:
   - Create a step-by-step user workflow (5-8 numbered steps) explaining HOW users interact with the solution
   - Use markdown format with clear numbering
   - Start from problem discovery -> solution access -> key interactions -> outcome
   - Example format:
     1. User realizes they have [problem]
     2. User discovers solution via [discovery method]
     3. User signs up and [onboarding action]
     4. User performs [key action 1]
     5. User achieves [outcome]
   - Make this concrete and specific to the selected solution

9. **solution_implementation_overview**:
   - Provide a high-level implementation plan (2-3 paragraphs, markdown format)
   - Cover: Phase 1 (MVP), Phase 2 (Enhancement), Phase 3 (Scale)
   - Include approximate timeline for each phase
   - Identify key dependencies and technical milestones
   - Keep this strategic, not deeply technical

10. **mvp_scope_definition**:
    - Create a detailed MVP scope with three sections (markdown format):
      * **Must-Have Features for MVP Launch**: 4-6 critical features needed for minimum viable product
      * **Post-MVP Features**: 3-5 features to add after initial validation
      * **Success Criteria**: 3-4 measurable metrics to determine MVP success
    - Base this on the core_features from selected_solution_details above
    - Be specific about what ships in v1 vs what waits

11. **top_pain_points**:
    - List of 5-7 most critical RESEARCH-DISCOVERED pain point titles (just the titles as strings)
    - Use ONLY the pain points from "RESEARCH-DISCOVERED Pain Points" section above
    - DO NOT include pain points from solution.pain_points_addressed (those are solution assumptions, not research)
    - Focus on high-opportunity, high-severity points from actual user research

12. **recommended_solutions**:
   - List with the SELECTED SOLUTION as first item, followed by 1-2 runner-ups (strings)
   - This maintains backward compatibility while prioritizing the selection

13. **market_validation**:
   - 3-4 sentences on overall market viability
   - Include search volume, competition analysis, demand signals
   - Clear verdict: Strong/Moderate/Weak opportunity

14. **pain_points_summary**:
   - 2-3 paragraph summary of pain point analysis
   - Include severity insights, WTP signals, top categories
   - Reference specific pain points by name

15. **solutions_summary**:
   - 2-3 paragraph summary of solution ideas
   - Include market fit scores, differentiation strategies
   - Reference specific solutions by name

16. **competitive_summary**:
   - 2-3 paragraph summary of competitive landscape
   - Include positioning opportunities, key gaps, number of competitors identified
   - **CRITICAL**: Only include competitive intensity labels if explicitly provided in selected_solution_competitive_intensity
     (If value is null/None, describe competitive landscape WITHOUT intensity labels - just describe competitors and gaps)
   - Reference specific competitors and opportunities by name

17. **data_sourcing_recommendations**:
   - 200-400 word strategy for solutions requiring data aggregation
   - Reference the ACTUAL data sources discovered in Stage 9.75 (shown in Data Source Research section above)
   - Summarize the primary sources, fallback options, and cost estimates
   - Include data quality considerations and implementation roadmap insights
   - If no data source research was conducted (solution does not require data aggregation), state: "This solution does not require external data aggregation"
   - DO NOT invent or hallucinate data sources - only reference what was discovered in Stage 9.75

18. **acquisition_strategy_summary**:
   - 2-3 paragraph overview of customer acquisition strategy emphasizing organic channels
   - Paragraph 1: Content Generation Mechanism - Explain HOW the product architecture creates indexable pages
     * For directories: User submissions create unique listing pages
     * For aggregators: Data combinations create comparison/category pages
     * For SaaS: Blog content, integration pages (limited programmatic SEO)
     * Reference the content_generation_model and programmatic_seo_opportunity from selected_solution_details
   - Paragraph 2: Discovery Patterns - What search queries will users use to find the solution?
     * Reference the organic_discovery_queries from selected_solution_details
     * Explain the search intent behind these queries
     * **CRITICAL**: Use EXACT page count from seo_refinement_metadata.estimated_year1_pages if available
       (DO NOT estimate or make up page counts - use actual calculated value from keyword research)
   - Paragraph 3: Scaling Strategy - How will organic acquisition scale?
     * User-generated content loops (directories, marketplaces)
     * Data refresh cycles (aggregators)
     * Content marketing investment (SaaS)
     * Reference the seo_scalability_score from selected_solution_details
   - Use data from COMPLETE SELECTED SOLUTION DETAILS section above
   - Be specific to the selected solution's architecture and project type

19. **estimated_cac_breakdown**:
   - Create a markdown-formatted CAC breakdown comparing organic vs paid acquisition
   - **CRITICAL: Use EXACT CAC values from selected_solution_details - DO NOT estimate, round, or modify them**
   - Format as a structured comparison (can use markdown table or bullet list):

     **Organic Acquisition (SEO/Content):**
     - Estimated CAC: [Use EXACT value from estimated_cac_organic or estimated_cac_organic_refined if available]
     - Channels: Programmatic SEO pages, organic search, content marketing
     - Rationale: [Explain based on project type and keyword data]
     - Scalability: [Reference seo_scalability_score - High/Medium/Limited]

     **Paid Acquisition (Ads/PPC):**
     - Estimated CAC: [Use EXACT value from estimated_cac_paid - DO NOT change the range (e.g., if it says $150-300, use $150-300, NOT $50-100)]
     - Channels: Google Ads, social media ads, retargeting
     - Rationale: [Explain based on keyword competition and niche]

     **CAC Advantage:**
     - Cost Ratio: [Calculate X:1 advantage - e.g., "$15 organic vs $200 paid = 13:1 advantage"]
     - Strategic Implication: [Explain why this matters for bootstrapping, profitability, scaling]
     - Recommendation: [Lead with organic or hybrid approach?]

   - Use data from estimated_cac_organic, estimated_cac_paid, and seo_scalability_score in selected_solution_details
   - Reference keyword search volumes from Keyword Validation section for market size context
   - Be specific with numbers, not vague ranges

20. **next_steps**:
   - List of 5-8 concrete action items
   - Prioritized and sequenced logically
   - Include validation, MVP development, marketing tactics

**CRITICAL ANTI-HALLUCINATION RULE FOR SEO STRATEGY:**

The SEO strategy has already been generated separately by the SEO Strategy Crew and will be
attached to your report AFTER generation. You MUST set the seo_strategy field to null.

**DO NOT:**
- [X] Generate keywords, search volumes, or competition metrics
- [X] Create tier_1_keywords, tier_2_keywords, or any keyword lists
- [X] Invent any SEO data or metrics
- [X] Fill in the seo_strategy field with ANY data

**YOU MUST:**
- [OK] Set seo_strategy = null (it will be added separately)
- [OK] Mention in market_validation that "Quantitative keyword data was handled by the SEO Strategy Crew"
- [OK] Reference SEO potential qualitatively in next_steps if appropriate

**IMPORTANT:** Any SEO keywords or metrics you generate will be WRONG. The real data comes from
DataForSEO API and is handled separately. Leave seo_strategy as null.

Provide strategic depth and actionable insights. Be specific, not generic."""

    def _generate_final_report_with_llm(self, prompt: str) -> FinalReport:
        """Generate FinalReport using LLM with structured output."""
        from langchain_openai import ChatOpenAI

        # Use LangChain directly for structured output (CrewAI's LLM wrapper doesn't support response_format)
        # Moderate temperature (0.5) for balanced synthesis - structured reporting with strategic insights
        structured_llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.5,
            api_key=settings.openai_api_key
        ).with_structured_output(FinalReport)

        # Generate structured FinalReport
        final_report = structured_llm.invoke(prompt)

        return final_report

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

    def _generate_fallback_report(self) -> FinalReport:
        """Generate basic FinalReport without LLM if synthesis fails."""
        from datetime import datetime

        # Extract top pain points
        top_pain_points = []
        pain_points_summary = "No pain point analysis available."
        if self.state.pain_point_analysis:
            top_pain_points = [
                pp.title
                for pp in sorted(
                    self.state.pain_point_analysis.pain_points,
                    key=lambda x: (x.severity_score + x.willingness_to_pay) / 2,
                    reverse=True,
                )[:5]
            ]
            pain_points_summary = (
                f"Identified {len(self.state.pain_point_analysis.pain_points)} pain points. "
                f"Top categories: {', '.join(self.state.pain_point_analysis.top_categories[:3])}. "
                f"Analysis summary: {self.state.pain_point_analysis.analysis_summary}"
            )

        # Extract recommended solutions
        recommended_solutions = []
        solutions_summary = "No solution ideas generated."
        if self.state.idea_generation:
            recommended_solutions = [
                sol.solution_name for sol in self.state.idea_generation.solution_ideas[:3]
            ]
            solutions_summary = (
                f"Generated {len(self.state.idea_generation.solution_ideas)} solution concepts. "
                f"Market insights: {self.state.idea_generation.market_insights}"
            )

        # Extract competitive summary
        competitive_summary = "No competitive analysis available."
        if self.state.competitive_analysis:
            competitive_summary = (
                f"Analyzed {len(self.state.competitive_analysis.solution_landscapes)} solution landscapes. "
                f"{self.state.competitive_analysis.strategic_recommendations}"
            )

        # Extract solution selection (Stage 8.5)
        selected_solution_name = "No solution selected"
        selection_rationale = "Solution selection was not completed. Review recommended solutions and perform manual selection."
        runner_up_solutions = []
        selection_criteria_scores = []  # Must be list, not dict
        recommended_focus = "To be determined after solution selection"

        if self.state.solution_selection:
            selected_solution_name = self.state.solution_selection.selected_solution_name
            selection_rationale = self.state.solution_selection.selection_rationale
            runner_up_solutions = self.state.solution_selection.runner_up_solutions
            selection_criteria_scores = self.state.solution_selection.selection_criteria_scores
            recommended_focus = self.state.solution_selection.recommended_focus

        # Get SEO strategy (should already be generated)
        if not self.state.seo_strategy_report:
            # Generate minimal SEO strategy if missing
            from ..models.seo_strategy import SEOStrategyReport
            seo_strategy = SEOStrategyReport(
                total_keywords_analyzed=0,
                total_monthly_volume=0,
                key_findings=["SEO strategy generation failed - manual keyword research required"],
                tier_1_keywords=[],
                tier_1_quick_win_strategy="SEO strategy generation failed. Conduct manual keyword research.",
                content_strategy="Develop content strategy after completing keyword research.",
                technical_seo_recommendations="Standard technical SEO best practices apply.",
                competitive_positioning="Conduct keyword research to identify competitive opportunities.",
                implementation_roadmap="1. Complete keyword research\n2. Develop SEO strategy\n3. Implement content plan",
                key_metrics_to_track=["Keyword research completion", "Initial rankings"],
                long_term_strategy="Year 1: Establish SEO foundation and baseline metrics",
                conclusion_bottom_line="Complete keyword research to enable comprehensive SEO strategy.",
                competitive_advantages=["To be determined after keyword research"],
                critical_success_factors=["Complete keyword research"],
                expected_timeline="TBD - awaiting keyword research",
                next_steps_checklist=["⬜ Complete keyword research", "⬜ Develop SEO strategy"],
            )
        else:
            seo_strategy = self.state.seo_strategy_report

        return FinalReport(
            niche=self.niche_description,
            executive_summary=f"Market research completed for {self.niche_description}. "
            f"Identified {len(top_pain_points)} high-priority pain points and "
            f"{len(recommended_solutions)} viable solution concepts. "
            f"Selected solution: {selected_solution_name}.",
            selected_solution_name=selected_solution_name,
            selection_rationale=selection_rationale,
            runner_up_solutions=runner_up_solutions,
            selection_criteria_scores=selection_criteria_scores,
            recommended_focus=recommended_focus,
            top_pain_points=top_pain_points if top_pain_points else ["No pain points identified"],
            pain_points_summary=pain_points_summary,
            recommended_solutions=recommended_solutions
            if recommended_solutions
            else ["No solutions generated"],
            solutions_summary=solutions_summary,
            competitive_summary=competitive_summary,
            competitive_analysis=self.state.competitive_analysis,
            market_validation="Research data collected. Review detailed findings for market assessment.",
            seo_strategy=seo_strategy,
            data_source_research=self.state.data_source_research,
            data_sourcing_recommendations="Review solution requirements and identify necessary data sources for implementation.",
            next_steps=[
                "Review detailed research findings",
                "Validate top pain points with target users",
                "Develop MVP for recommended solution",
                "Implement SEO strategy",
                "Set up data sourcing infrastructure",
            ],
            generated_at=datetime.utcnow(),
        )

    def _display_executive_summary(self, report: FinalReport):
        """Display formatted executive summary to console."""
        logger.info("\n" + "=" * 80)
        logger.info("RESEARCH COMPLETE - FINAL REPORT")
        logger.info("=" * 80)
        logger.info(f"\nNiche: {report.niche}\n")
        logger.info("EXECUTIVE SUMMARY:")
        logger.info(report.executive_summary)
        logger.info(f"\n{'=' * 80}")
        logger.info("TOP PAIN POINTS:")
        for i, pp in enumerate(report.top_pain_points, 1):
            logger.info(f"  {i}. {pp}")
        logger.info(f"\n{'=' * 80}")
        logger.info("RECOMMENDED SOLUTIONS:")
        for i, sol in enumerate(report.recommended_solutions, 1):
            logger.info(f"  {i}. {sol}")
        logger.info(f"\n{'=' * 80}")
        logger.info("MARKET VALIDATION:")
        logger.info(report.market_validation)
        logger.info(f"\n{'=' * 80}")
        logger.info("NEXT STEPS:")
        for i, step in enumerate(report.next_steps, 1):
            logger.info(f"  {i}. {step}")
        logger.info("=" * 80)

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
