"""
ResearchFlow - Main orchestration flow for the 10-stage market research pipeline.
Combines Flow-based orchestration with specialized Crews for complex analysis.
"""

from pathlib import Path
from typing import List, Optional
import asyncio
import json

from crewai.flow.flow import Flow, listen, start
from crewai.llm import LLM
from crewai_tools import SerperDevTool
from loguru import logger
from pydantic import ValidationError

from ..config.settings import settings
from ..crews import CompetitiveCrew, IdeaGenerationCrew, PainPointCrew, SEOStrategyCrew
from ..models.research_state import FinalReport, ResearchState
from ..tools.reddit_tool import RedditCollectorTool
from ..tools.twitter_tool import TwitterCollectorTool
from ..utils.helpers import SearchHelper, generate_competitive_queries


class ResearchFlow(Flow[ResearchState]):
    """
    Main research flow orchestrating all 10 stages of the NicheIQ pipeline.

    Stages:
    1-4: Niche Input & Validation (Flow)
    5: Search & Discover (Flow + SerperDevTool)
    6: Pain Point Analysis (PainPointCrew)
    7: Solution Ideation (IdeaGenerationCrew)
    8: Competitive Analysis (CompetitiveCrew)
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

        logger.info(f"ResearchFlow initialized for niche: {niche_description[:100]}...")

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

        self.state.current_stage = 6

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

        self.state.current_stage =7

    @listen(stage_6_analyze_pain_points)
    def stage_7_generate_ideas(self):
        """
        Stage 7: Solution Ideation

        Uses IdeaGenerationCrew to generate and refine SaaS solution concepts.
        """
        logger.info("=" * 80)
        logger.info("STAGE 7: Solution Ideation")
        logger.info("=" * 80)

        if not self.state.pain_point_analysis or not self.state.pain_point_analysis.pain_points:
            logger.warning("No pain points available. Skipping solution ideation.")
            self.state.current_stage =8
            return

        # ANTI-HALLUCINATION CHECK: Verify pain point quality for solution generation
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
                f"No high or medium priority pain points available "
                f"({len(self.state.pain_point_analysis.pain_points)} total pain points all scored too low) "
                f"- skipping solution ideation to prevent hallucinated solutions"
            )
            self.state.current_stage = 8
            return

        if len(high_priority) < 2 and len(medium_priority) < 3:
            logger.warning(
                f"Insufficient high-quality pain points for robust solution generation "
                f"({len(high_priority)} high-priority, {len(medium_priority)} medium-priority) "
                f"- solution quality may be limited"
            )

        logger.info(
            f"Pain point quality check: {len(high_priority)} high-priority, "
            f"{len(medium_priority)} medium-priority pain points"
        )

        # Initialize and run IdeaGenerationCrew
        idea_crew = IdeaGenerationCrew(
            pain_point_analysis=self.state.pain_point_analysis,
            allowed_project_types=self.allowed_project_types
        )

        logger.info("Running solution ideation crew...")
        self.state.idea_generation = idea_crew.generate_ideas()

        logger.info(f"[OK] Generated {len(self.state.idea_generation.solution_ideas)} solution concepts")

        # Log solution summaries
        for i, idea in enumerate(self.state.idea_generation.solution_ideas, 1):
            logger.info(f"  {i}. {idea.solution_name}: {idea.value_proposition}")
            logger.info(f"     Target: {idea.target_personas[0] if idea.target_personas else 'N/A'}")

        self.state.current_stage =8

    @listen(stage_7_generate_ideas)
    def stage_8_analyze_competition(self):
        """
        Stage 8: Competitive Analysis

        Uses CompetitiveCrew to research competitors and identify opportunities.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8: Competitive Analysis")
        logger.info("=" * 80)

        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("No solution ideas available. Skipping competitive analysis.")
            self.state.current_stage =9
            return

        # ANTI-HALLUCINATION CHECK: Verify solution detail completeness
        incomplete_solutions = []
        for idea in self.state.idea_generation.solution_ideas:
            if (not idea.value_proposition or len(idea.value_proposition) < 20 or
                not idea.core_features or len(idea.core_features) < 2 or
                not idea.target_personas or len(idea.target_personas) < 1):
                incomplete_solutions.append(idea.solution_name)

        if len(incomplete_solutions) == len(self.state.idea_generation.solution_ideas):
            logger.warning(
                f"All {len(incomplete_solutions)} solution ideas lack sufficient detail "
                f"(missing value prop, features, or personas) - skipping competitive analysis "
                f"to prevent hallucinated competitor research"
            )
            self.state.current_stage = 9
            return

        if incomplete_solutions:
            logger.warning(
                f"{len(incomplete_solutions)} solutions have incomplete details: "
                f"{', '.join(incomplete_solutions[:3])} - competitive analysis may be limited"
            )

        complete_solutions = len(self.state.idea_generation.solution_ideas) - len(incomplete_solutions)
        logger.info(f"Solution detail check: {complete_solutions} complete solutions ready for competitive analysis")

        # Initialize and run CompetitiveCrew with optional social content for competitor intelligence
        competitive_crew = CompetitiveCrew(
            solution_ideas=self.state.idea_generation,
            social_content=self.state.social_content  # Pass for competitor intelligence
        )

        logger.info("Running competitive analysis crew...")
        self.state.competitive_analysis = competitive_crew.analyze_competition(
            parallel=True,
            max_workers=4  # Increased from default 2 for better parallelization
        )

        logger.info(f"[OK] Analyzed {len(self.state.competitive_analysis.solution_landscapes)} competitive landscapes")
        logger.info(f"[OK] Identified {len(self.state.competitive_analysis.top_opportunities)} key opportunities")

        # Log top opportunities
        if self.state.competitive_analysis.top_opportunities:
            logger.info("[OK] Top differentiation opportunities:")
            for opp in self.state.competitive_analysis.top_opportunities[:3]:
                logger.info(f"  - {opp}")

        self.state.current_stage = 8.5

    @listen(stage_8_analyze_competition)
    def stage_8_5_refine_with_competitive_insights(self):
        """
        Stage 8.5: Competitive Refinement

        Enhances solution ideas with competitive intelligence before selection.
        Uses competitive gaps and positioning opportunities to strengthen solutions.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.5: Competitive Refinement")
        logger.info("=" * 80)

        if not self.state.competitive_analysis or not self.state.idea_generation:
            logger.warning("Missing competitive analysis or solutions - skipping refinement")
            self.state.current_stage = 8.75
            return

        # Initialize IdeaGenerationCrew with original pain points
        from ..crews.idea_generation_crew import IdeaGenerationCrew

        idea_crew = IdeaGenerationCrew(
            pain_point_analysis=self.state.pain_point_analysis,
            allowed_project_types=self.allowed_project_types
        )

        # Enhance solutions with competitive insights
        logger.info("Refining solutions with competitive intelligence...")
        refined_ideas = idea_crew.refine_with_competition(
            original_ideas=self.state.idea_generation,
            competitive_analysis=self.state.competitive_analysis
        )

        # Update state with refined solutions
        self.state.idea_generation = refined_ideas

        logger.info(
            f"[OK] Refined {len(refined_ideas.solution_ideas)} solutions "
            f"with competitive positioning"
        )

        self.state.current_stage = 8.75

    @listen(stage_8_5_refine_with_competitive_insights)
    def stage_8_75_select_solution(self):
        """
        Stage 8.75: Solution Selection

        Selects ONE solution from Stage 7 to focus on for SEO strategy and implementation.
        Uses competitive analysis + pain points + market fit to make strategic selection decision.
        """
        logger.info("=" * 80)
        logger.info("STAGE 8.75: Solution Selection")
        logger.info("=" * 80)

        if not self.state.idea_generation or not self.state.idea_generation.solution_ideas:
            logger.warning("No solution ideas available. Skipping solution selection.")
            self.state.current_stage = 9
            return

        # Get all solutions with their competitive landscapes
        solutions = self.state.idea_generation.solution_ideas
        competitive_landscapes = (
            self.state.competitive_analysis.solution_landscapes
            if self.state.competitive_analysis
            else []
        )

        logger.info(f"Evaluating {len(solutions)} solution candidates...")

        # If only one solution, auto-select it
        if len(solutions) == 1:
            solution = solutions[0]
            logger.info(f"Only one solution available - auto-selecting: {solution.solution_name}")

            # Find competitive landscape for context
            landscape = next(
                (l for l in competitive_landscapes if l.solution_name == solution.solution_name),
                None
            )

            from ..models.solution_selection import SolutionSelection, SelectionCriteriaScore

            # Build rationale with competitive context if available
            rationale = f"Auto-selected {solution.solution_name} as the only generated solution. "
            rationale += f"This solution addresses validated pain points with a clear value proposition: {solution.value_proposition}"

            if landscape:
                rationale += f"\n\nCompetitive Analysis: {landscape.competitive_intensity} competitive intensity "
                rationale += f"with {len(landscape.competitors)} identified competitors. "
                if landscape.market_gaps:
                    rationale += f"Key market gaps identified: {', '.join(landscape.market_gaps[:2])}. "
                if landscape.recommended_positioning:
                    rationale += f"Recommended positioning: {landscape.recommended_positioning}"

            self.state.solution_selection = SolutionSelection(
                selected_solution_name=solution.solution_name,
                selection_rationale=rationale,
                selection_criteria_scores=[
                    SelectionCriteriaScore(criterion="market_fit", score=solution.market_fit_score or 0.75),
                    SelectionCriteriaScore(criterion="technical_feasibility", score=solution.technical_feasibility_score or 0.75),
                    SelectionCriteriaScore(criterion="competitive_advantage", score=0.65),  # Default moderate score
                    SelectionCriteriaScore(criterion="seo_growth_potential", score=0.70),  # Default moderate score
                ],
                runner_up_solutions=[],
                recommended_focus=landscape.recommended_positioning if landscape and landscape.recommended_positioning else "Validate MVP with early adopter segment before scaling",
            )
            self.state.current_stage = 9
            return

        # Multiple solutions - run LLM selection
        logger.info("Analyzing solutions and making strategic selection...")

        try:
            # Build selection prompt with comprehensive context
            selection_prompt = self._create_solution_selection_prompt(
                solutions=solutions,
                competitive_landscapes=competitive_landscapes,
                pain_points=self.state.pain_point_analysis,
            )

            # Use LLM with structured output to make selection
            selection = self._select_solution_with_llm(selection_prompt)
            self.state.solution_selection = selection

            logger.info(f"[OK] Selected Solution: {selection.selected_solution_name}")
            logger.info(f"  Selection Rationale: {selection.selection_rationale[:150]}...")

            if selection.runner_up_solutions:
                logger.info(f"  Runner-ups: {', '.join(selection.runner_up_solutions)}")

            logger.info(f"  Recommended Focus: {selection.recommended_focus}")

        except Exception as e:
            logger.error(f"Solution selection failed: {e}")
            # Fallback: select first solution
            logger.warning("Falling back to first solution as default selection")

            from ..models.solution_selection import SolutionSelection, SelectionCriteriaScore
            solution = solutions[0]
            self.state.solution_selection = SolutionSelection(
                selected_solution_name=solution.solution_name,
                selection_rationale=(
                    f"Default selection of {solution.solution_name} due to selection process failure. "
                    "Manual review recommended."
                ),
                selection_criteria_scores=[],  # Empty list instead of dict for fallback case
                runner_up_solutions=[s.solution_name for s in solutions[1:]],
                recommended_focus="To be determined after manual review",
            )

        self.state.current_stage = 9

    def _create_solution_selection_prompt(
        self,
        solutions: list,
        competitive_landscapes: list,
        pain_points,
    ) -> str:
        """Create comprehensive prompt for solution selection."""

        # Format solutions with their competitive context
        solutions_analysis = []
        for i, solution in enumerate(solutions, 1):
            # Find matching competitive landscape
            landscape = next(
                (l for l in competitive_landscapes if l.solution_name == solution.solution_name),
                None
            )

            solutions_analysis.append(f"""
**Solution {i}: {solution.solution_name}**

**Value Proposition:** {solution.value_proposition}

**Market Fit Score:** {solution.market_fit_score if solution.market_fit_score is not None else 'N/A'}
**Technical Feasibility:** {solution.technical_feasibility_score if solution.technical_feasibility_score is not None else 'N/A'}

**Target Personas:** {', '.join(str(p) for p in (solution.target_personas[:2] if solution.target_personas else ['Not specified']))}

**Core Features:** {', '.join(str(f) for f in (solution.core_features[:5] if solution.core_features else ['None']))}

**Pain Points Addressed:** {', '.join(str(p) for p in (solution.pain_points_addressed[:3] if solution.pain_points_addressed else ['None']))}

**Competitive Context:**
{f"- Intensity: {landscape.competitive_intensity}" if landscape else "No competitive analysis available"}
{f"- Competitors Found: {len(landscape.competitors)}" if landscape else ""}
{f"- Top Competitors: {', '.join(c.name for c in landscape.competitors[:3])}" if landscape and landscape.competitors else ""}
{f"- Market Gaps: {', '.join(str(g) for g in landscape.market_gaps[:3])}" if landscape and landscape.market_gaps else ""}
{f"- Differentiation Opportunities: {', '.join(str(d) for d in landscape.differentiation_opportunities[:3])}" if landscape and landscape.differentiation_opportunities else ""}
{f"- Recommended Positioning: {landscape.recommended_positioning}" if landscape and landscape.recommended_positioning else ""}

**Data Requirements:** {'Requires data aggregation' if solution.requires_data_aggregation else 'No external data required'}
{f"Data Sources: {', '.join(str(ds) for ds in solution.data_sources[:3])}" if solution.data_sources else ""}
""")

        # Get pain point priorities
        high_priority_pps = []
        if pain_points and pain_points.pain_points:
            sorted_pps = sorted(
                pain_points.pain_points,
                key=lambda p: (p.severity_score + p.willingness_to_pay) / 2,
                reverse=True
            )[:5]
            high_priority_pps = [
                f"- {pp.title} (Severity: {pp.severity_score:.1f}, WTP: {pp.willingness_to_pay:.1f})"
                for pp in sorted_pps
            ]

        return f"""You are a strategic product advisor selecting which solution to focus on for MVP development and SEO strategy.

**NICHE:** {self.niche_description}

**HIGH-PRIORITY PAIN POINTS:**
{chr(10).join(high_priority_pps) if high_priority_pps else "No pain points available"}

**SOLUTION CANDIDATES:**
{chr(10).join(solutions_analysis)}

**YOUR TASK:**
Select ONE solution to focus on based on these weighted criteria:

1. **Market Fit (25%):** How directly does it address high-severity, high-WTP pain points?
   - Alignment with top pain points
   - Willingness to pay indicators from user discussions

2. **Competitive Advantage (25%):** Does it have clear differentiation and viable positioning?
   - **CRITICAL: Analyze competitive intensity for each solution**
   - Market gaps that can be exploited
   - Differentiation opportunities identified in competitive analysis
   - Whether recommended positioning is strong and defensible
   - Lower competition = higher score (e.g., "LOW" intensity better than "HIGH")

3. **Technical Feasibility (25%):** Can it be built in 3-6 months with reasonable complexity?
   - Development timeline estimate
   - Data sourcing complexity (if requires_data_aggregation)
   - Technical risk factors

4. **Organic Acquisition Potential (25%):** Can it attract customers organically with low CAC?
   - **CRITICAL: Prioritize solutions with programmatic SEO potential**
   - Architecture that naturally generates indexable content (directories, aggregators > SaaS)
   - Estimated CAC organic vs CAC paid ratio (lower organic CAC = higher score)
   - SEO scalability score from solution evaluation
   - Content generation model (self-generating > programmatic > manual)
   - Keyword opportunity potential from competitive analysis

**COMPETITIVE ANALYSIS USAGE:**
- **Prioritize solutions with clearer differentiation opportunities**
- **Favor solutions in markets with identified gaps**
- **Consider competitive intensity** - "LOW" or "MEDIUM" intensity markets may offer faster traction than "HIGH" intensity
- **Leverage recommended positioning** - solutions with stronger positioning strategies score higher
- **Count competitors** - fewer direct competitors = easier market entry

**SEO-FIRST DECISION FRAMEWORK:**
When comparing solutions with similar market fit and technical feasibility, use SEO potential as the tiebreaker:

- **Directories/Aggregators (SEO Score 0.8-1.0):** Favor these heavily - each listing/data point = new indexable page
  * Example: 100 listings = 100 unique landing pages targeting long-tail keywords
  * CAC advantage: $15-40 organic vs $200-350 paid (5-12x cost reduction)

- **Comparison Tools/Marketplaces (SEO Score 0.5-0.7):** Good programmatic opportunities
  * Example: N tools = N² comparison pages, seller profiles create natural content
  * CAC advantage: $50-150 organic vs $200-350 paid (2-4x cost reduction)

- **Traditional SaaS (SEO Score 0.2-0.4):** Only choose if significantly stronger on other dimensions
  * Limited to blog/guides, requires sustained content marketing investment
  * CAC disadvantage: $200-400 organic, $300-600 paid (minimal cost advantage)

**Decision Rules:**
1. If two solutions have similar market fit (±0.1), favor the one with higher SEO scalability
2. A directory/aggregator with 0.7 market fit may outperform a SaaS with 0.8 market fit due to 5-12x lower CAC
3. Prioritize solutions where organic_acquisition_potential ≥ 0.6 unless other factors are exceptional

**SELECTION OUTPUT:**
- **selected_solution_name:** The name of the chosen solution (MUST match one of the solution names exactly)
- **selection_rationale:** 2-3 paragraphs explaining WHY this solution was selected:
  * Which pain points it addresses best (reference specific pain point titles and scores)
  * **Its competitive advantages and positioning** (reference competitive intensity, gaps, differentiation opportunities)
  * Why it's more viable than alternatives (compare competitive landscapes)
  * What makes it the best focus for initial SEO strategy
- **selection_criteria_scores:** List of SelectionCriteriaScore objects with these criteria:
  * market_fit (0-1 scale)
  * competitive_advantage (0-1 scale) - **CRITICAL: Base this on competitive landscape data**
  * technical_feasibility (0-1 scale)
  * organic_acquisition_potential (0-1 scale) - **CRITICAL: Use SEO scalability score and CAC analysis**
- **runner_up_solutions:** Other viable solutions in priority order (just names as strings)
- **recommended_focus:** Strategic focus recommendation incorporating competitive positioning
  * Examples: "Target [market gap] starting with [segment]", "Differentiate via [opportunity] in [geographic market]", "Niche dominance in [vertical] by leveraging [competitive advantage]"

**IMPORTANT:**
- Be strategic and data-driven
- **Weight competitive landscape heavily** - a solution with great market fit but overwhelming competition may be less viable than one with good market fit and clear differentiation
- Focus on maximizing early traction and sustainable competitive positioning
- Reference specific data points from competitive analysis in your rationale"""

    def _select_solution_with_llm(self, prompt: str):
        """Use LLM with structured output to select solution."""
        from langchain_openai import ChatOpenAI
        from ..models.solution_selection import SolutionSelection

        logger.info("Generating solution selection with LLM (structured output)...")

        structured_llm = ChatOpenAI(
            model=settings.openai_model_name,
            temperature=0.3,  # Lower temperature for more consistent analytical decisions
            api_key=settings.openai_api_key
        ).with_structured_output(SolutionSelection)

        selection = structured_llm.invoke(prompt)

        logger.info(f"[OK] Solution selection complete: {selection.selected_solution_name}")

        return selection

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
{json.dumps(solution.seo_refinement_metadata, indent=2) if solution.seo_refinement_metadata else 'N/A'}
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

    @listen(stage_8_75_select_solution)
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
            return

        # Check if we have required data
        if not self.state.idea_generation:
            logger.warning("Insufficient data for SEO strategy - skipping")
            self.state.seo_strategy_report = None
            self.state.current_stage = 10
            return

        # Get the selected solution
        selected_solution_name = self.state.solution_selection.selected_solution_name
        selected_solution = next(
            (sol for sol in self.state.idea_generation.solution_ideas
             if sol.solution_name == selected_solution_name),
            None
        )

        if not selected_solution:
            logger.error(f"Selected solution '{selected_solution_name}' not found in solution ideas!")
            self.state.seo_strategy_report = None
            self.state.current_stage = 10
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

        # Generate comprehensive SEO strategy
        # Crew will: generate seeds FOR THIS SOLUTION -> expand with DataForSEO -> analyze -> create strategy
        logger.info(f"Starting integrated keyword research + SEO strategy for {selected_solution_name}...")
        try:
            seo_strategy = seo_crew.create_strategy()
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

        self.state.current_stage = 9.5

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
            return

        # Skip if no SEO strategy or no solution selection
        if not self.state.seo_strategy_report or not self.state.solution_selection:
            logger.info("No SEO strategy or solution selection - skipping refinement")
            self.state.current_stage = 9.75
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
            return

        # Check if solution has SEO fields to refine
        if selected_solution.seo_scalability_score is None:
            logger.info("Solution has no SEO scores to refine - skipping")
            self.state.current_stage = 9.75
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
            selected_solution.seo_refinement_metadata = {
                'scalability_refinement': refined_scalability['metadata'],
                'cac_refinement': refined_cac['metadata'],
                'timestamp': datetime.utcnow().isoformat()
            }

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
            return

        # Get the selected solution
        selected_solution_name = self.state.solution_selection.selected_solution_name
        selected_solution = next(
            (sol for sol in self.state.idea_generation.solution_ideas
             if sol.solution_name == selected_solution_name),
            None
        )

        if not selected_solution:
            logger.warning("Selected solution not found - skipping data source research")
            self.state.data_source_research = None
            self.state.current_stage = 10
            return

        # Only run if solution requires data aggregation
        if not selected_solution.requires_data_aggregation:
            logger.info(
                f"Solution '{selected_solution_name}' doesn't require data aggregation - "
                f"skipping data source research"
            )
            self.state.data_source_research = None
            self.state.current_stage = 10
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

        self.state.current_stage = 10

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

            self.state.final_report = final_report
            logger.info("[OK] Final report synthesis complete")
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
            "pain_points": [],
            "solutions": [],
            "competitors": [],
            "keywords": {},
        }

        # Extract pain points
        if self.state.pain_point_analysis:
            context["pain_points"] = [
                {
                    "title": pp.title,
                    "description": pp.description,
                    "severity": pp.severity_score,
                    "wtp": pp.willingness_to_pay,
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

**Pain Points Discovered:**
{json.dumps(context.get('pain_points', []), indent=2)}

Pain Points Summary: {context.get('pain_points_summary', 'N/A')}
Total Pain Points Validated: {context.get('total_pain_points_validated', 0)}

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
    - List of 5-7 most critical pain point titles (just the titles as strings)
    - Focus on high-opportunity, high-severity points that the SELECTED SOLUTION addresses

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
   - Include positioning opportunities, key gaps, competitive intensity
   - Reference specific competitors and opportunities

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
     * Estimate potential page count in year 1 (e.g., "100 listings = 100 unique landing pages")
   - Paragraph 3: Scaling Strategy - How will organic acquisition scale?
     * User-generated content loops (directories, marketplaces)
     * Data refresh cycles (aggregators)
     * Content marketing investment (SaaS)
     * Reference the seo_scalability_score from selected_solution_details
   - Use data from COMPLETE SELECTED SOLUTION DETAILS section above
   - Be specific to the selected solution's architecture and project type

19. **estimated_cac_breakdown**:
   - Create a markdown-formatted CAC breakdown comparing organic vs paid acquisition
   - Format as a structured comparison (can use markdown table or bullet list):

     **Organic Acquisition (SEO/Content):**
     - Estimated CAC: [Use estimated_cac_organic from selected_solution_details]
     - Channels: Programmatic SEO pages, organic search, content marketing
     - Rationale: [Explain based on project type - directories $15-30, aggregators $20-40, comparison $50-100, SaaS $200-400]
     - Scalability: [Reference seo_scalability_score - High/Medium/Limited]

     **Paid Acquisition (Ads/PPC):**
     - Estimated CAC: [Use estimated_cac_paid from selected_solution_details]
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
