"""
CompetitiveCrew - Stage 8: Competitive Analysis
Multi-agent crew for researching competitors and identifying market opportunities.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult, CompetitiveLandscape
from ..models.solution_idea import IdeaGenerationResult, SolutionIdea
from ..models.social_content import SocialContentCollection, RedditPost, TwitterThread


class CachedSerperDevTool(SerperDevTool):
    """
    Wrapper around SerperDevTool that caches search results within a session.

    Reduces redundant API calls when multiple solutions have overlapping competitors
    in the same niche. Cache is session-scoped (cleared between research runs).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._hits = 0
        self._misses = 0

    def run(self, search_query: str, **kwargs):
        """Execute search with caching."""
        # Normalize query for cache key
        cache_key = search_query.strip().lower()

        if cache_key in self._cache:
            self._hits += 1
            logger.debug(f"Cache hit for: {search_query[:50]}... (hits: {self._hits}, misses: {self._misses})")
            return self._cache[cache_key]

        # Cache miss - execute actual search
        self._misses += 1
        logger.debug(f"Cache miss for: {search_query[:50]}... (hits: {self._hits}, misses: {self._misses})")
        result = super().run(search_query, **kwargs)
        self._cache[cache_key] = result

        return result

    def get_cache_stats(self):
        """Return cache performance statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self._cache)
        }


@CrewBase
class CompetitiveCrew:
    """
    Specialized crew for competitive intelligence and market analysis.
    Maps competitive landscape and identifies differentiation opportunities.

    Architecture:
    - 2 agents working in pipeline
    - Researcher discovers and profiles competitors
    - Analyst identifies gaps and positioning strategies
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(
        self,
        solution_ideas: IdeaGenerationResult,
        social_content: Optional[SocialContentCollection] = None
    ):
        """
        Initialize CompetitiveCrew with refined solution ideas and optional social content.

        Args:
            solution_ideas: Results from IdeaGenerationCrew
            social_content: Optional social content for competitor intelligence from user discussions
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.solution_ideas = solution_ideas

        # Initialize search tool for competitive research with caching
        self.search_tool = CachedSerperDevTool()

        # Initialize knowledge sources for competitor intelligence
        self.knowledge_sources = []

        # Cache crew instance to avoid re-embedding knowledge sources in parallel mode
        self._crew_instance = None

        # Create filtered knowledge source if social content is provided
        if social_content and (social_content.reddit_posts or social_content.twitter_threads):
            competitor_intel = self._prepare_competitor_intelligence(social_content)

            if competitor_intel:
                from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

                self.competitor_knowledge = StringKnowledgeSource(
                    content=competitor_intel,
                    chunk_size=1000,     # Smaller chunks for focused competitor mentions
                    chunk_overlap=150    # Moderate overlap for context
                )
                self.knowledge_sources.append(self.competitor_knowledge)
                logger.info(
                    f"Competitor intelligence knowledge source created ({len(competitor_intel)} chars) "
                    f"from {len(social_content.reddit_posts)} Reddit posts and "
                    f"{len(social_content.twitter_threads)} Twitter threads"
                )

        logger.info(
            f"CompetitiveCrew initialized with {len(solution_ideas.solution_ideas)} "
            f"solution concepts{' and competitor intelligence' if self.knowledge_sources else ''}"
        )

    def _prepare_competitor_intelligence(self, social_content: SocialContentCollection) -> str:
        """
        Extract competitor and tool mentions from social discussions.

        Filters content to focus on:
        - Existing tools/platforms users mention
        - Alternative solutions and workarounds
        - Competitor comparisons and switching behavior
        - Pricing and value discussions

        Args:
            social_content: Reddit and Twitter discussions from research

        Returns:
            Formatted string with filtered competitor intelligence, or empty if none found
        """
        # Keywords indicating competitor/tool mentions
        competitor_indicators = [
            # Usage patterns
            "using", "used", "tried", "currently use", "switched from", "switched to",
            # Comparisons and alternatives
            "alternative", "instead of", "compared to", "better than", "worse than",
            "vs", "versus", "comparison",
            # Commercial indicators
            "pricing", "pay for", "subscription", "free version", "paid plan",
            "cost", "expensive", "cheap", "affordable", "worth",
            # Product types
            "tool", "platform", "software", "app", "service", "product", "solution"
        ]

        filtered_content = []
        total_filtered = 0

        # Filter Reddit posts
        for post in social_content.reddit_posts:
            post_text = f"{post.title} {post.selftext}".lower()

            # Check if post mentions tools/competitors
            if any(indicator in post_text for indicator in competitor_indicators):
                formatted = f"""[REDDIT - r/{post.subreddit}]
[SCORE: {post.score}]

### {post.title}

{post.selftext if post.selftext else '[No content]'}

---
## Top Comments (Competitor Mentions):

"""
                # Include comments mentioning tools (no limits with RAG)
                comment_count = 0
                for comment in post.comments:  # Check ALL comments (was 30)
                    if any(indicator in comment.body.lower() for indicator in competitor_indicators):
                        # Include full comment body (no truncation with RAG)
                        formatted += f"- [{comment.score} pts] {comment.body}\n"
                        comment_count += 1
                        # No max limit - RAG handles large datasets efficiently

                # Only add if we found relevant comments or selftext
                if comment_count > 0 or any(indicator in post.selftext.lower() for indicator in competitor_indicators):
                    filtered_content.append(formatted)
                    total_filtered += 1

        # Filter Twitter threads
        for thread in social_content.twitter_threads:
            thread_text = thread.original_tweet.text.lower()

            if any(indicator in thread_text for indicator in competitor_indicators):
                formatted = f"""[TWITTER - @{thread.original_tweet.author_username}]
[ENGAGEMENT: {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs]

## Original Tweet:

{thread.original_tweet.text}

---
## Replies (Competitor Mentions):

"""
                # Include replies mentioning tools (no limits with RAG)
                reply_count = 0
                for reply in thread.replies:  # Check ALL replies (was 50)
                    if any(indicator in reply.text.lower() for indicator in competitor_indicators):
                        # Include full reply text (no truncation with RAG)
                        formatted += f"- @{reply.author_username} [{reply.likes}❤️]: {reply.text}\n"
                        reply_count += 1
                        # No max limit - RAG handles large datasets efficiently

                # Only add if we found relevant replies or original tweet mentions competitors
                if reply_count > 0 or any(indicator in thread_text for indicator in competitor_indicators):
                    filtered_content.append(formatted)
                    total_filtered += 1

        if filtered_content:
            logger.debug(
                f"Filtered competitor intelligence: {total_filtered} discussions "
                f"({len(filtered_content)} total pieces) mentioning existing tools/alternatives"
            )
            return "\n\n===\n\n".join(filtered_content)
        else:
            logger.info("No competitor mentions found in social discussions")
            return ""

    @agent
    def competitive_researcher(self) -> Agent:
        """
        Agent responsible for discovering and profiling competitors.
        Uses search tools to find existing solutions and alternatives.

        Uses low temperature (0.3) for factual research with structured output.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["competitive_researcher"],
            tools=[self.search_tool],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,  # Low temperature for consistent factual research
                api_key=settings.openai_api_key
            ),
            verbose=True,
            function_calling_llm=ChatOpenAI(
                model=settings.function_calling_llm,
                temperature=0.1,  # Low temperature for reliable tool calls
                api_key=settings.openai_api_key
            ),
        )

    @agent
    def competitive_analyst(self) -> Agent:
        """
        Agent responsible for analyzing competitive landscape.
        Identifies gaps, opportunities, and differentiation strategies.

        Uses moderate temperature (0.4) for analytical + strategic insights.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["competitive_analyst"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate temperature for strategic analysis with structure
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def research_competitors_task(self) -> Task:
        """
        Task: Research existing competitors and alternative solutions.

        Output: Comprehensive competitive landscape mapping.
        """
        return Task(
            config=self.tasks_config["research_competitors"],
            agent=self.competitive_researcher(),
        )

    @task
    def analyze_competitive_landscape_task(self) -> Task:
        """
        Task: Analyze competitive research to identify opportunities.

        Depends on: research_competitors_task
        Output: Strategic analysis with gaps and differentiation strategies.
        """
        return Task(
            config=self.tasks_config["analyze_competitive_landscape"],
            agent=self.competitive_analyst(),
            context=[self.research_competitors_task()],
            output_pydantic=CompetitiveAnalysisResult,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the CompetitiveCrew with all agents, tasks, and optional knowledge sources.

        If competitor intelligence knowledge sources are available, they are attached
        at crew level so agents can access user discussions about existing tools.

        IMPORTANT: Crew instance is cached to prevent duplicate embeddings when analyzing
        multiple solutions in parallel. Knowledge sources are embedded only once.

        Returns:
            Configured Crew instance with optional knowledge sources
        """
        # Return cached instance if available (prevents re-embedding in parallel mode)
        if self._crew_instance is not None:
            logger.debug("Reusing cached crew instance (avoiding duplicate embeddings)")
            return self._crew_instance

        crew_config = {
            "agents": self.agents,
            "tasks": self.tasks,
            "verbose": True,
            "process_type": "sequential",
        }

        # Add knowledge sources if available
        if self.knowledge_sources:
            crew_config["knowledge_sources"] = self.knowledge_sources
            crew_config["embedder"] = {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"  # Cost-effective embeddings
                }
            }

        # Create and cache the crew instance
        self._crew_instance = Crew(**crew_config)
        logger.debug("Created and cached new crew instance")

        return self._crew_instance

    def _analyze_single_solution(self, idea: SolutionIdea, index: int, total: int) -> CompetitiveLandscape:
        """
        Analyze a single solution's competitive landscape.

        Args:
            idea: Solution idea to analyze
            index: Current solution number (1-based)
            total: Total number of solutions

        Returns:
            CompetitiveLandscape for this solution
        """
        logger.info(f"[{index}/{total}] Researching solution: {idea.solution_name}")
        logger.debug(f"  Value Proposition: {idea.value_proposition}")

        # Format single solution for crew input
        solution_data = (
            f"### Solution: {idea.solution_name}\n"
            f"**Value Proposition:** {idea.value_proposition}\n"
            f"**Description:** {idea.description}\n"
            f"**Target Users:** {'; '.join(str(p) for p in (idea.target_personas[:2] if idea.target_personas else ['Not specified']))}\n"
            f"**Key Features:** {', '.join(str(f) for f in (idea.core_features[:5] if idea.core_features else ['Not specified']))}\n"
            f"**Pain Points Solved:** {', '.join(str(p) for p in (idea.pain_points_addressed if idea.pain_points_addressed else ['Not specified']))}"
        )

        # Execute crew for this single solution
        crew_output = self.crew().kickoff(inputs={
            "solution_count": 1,
            "market_insights": self.solution_ideas.market_insights,
            "recommended_solution": f"Focus on {idea.solution_name}",
            "solutions_list": solution_data
        })

        # Extract the Pydantic model from CrewOutput
        single_result = crew_output.pydantic

        # Return the landscape for this solution
        if single_result.solution_landscapes:
            landscape = single_result.solution_landscapes[0]

            # VALIDATION: Verify landscape solution_name matches input solution name
            if landscape.solution_name != idea.solution_name:
                # Try fuzzy matching: case-insensitive substring search
                search_name_lower = landscape.solution_name.lower()
                idea_name_lower = idea.solution_name.lower()

                if (search_name_lower in idea_name_lower or idea_name_lower in search_name_lower):
                    logger.warning(
                        f"⚠️ [{index}/{total}] Competitive analysis renamed solution: "
                        f"'{landscape.solution_name}' → '{idea.solution_name}' (corrected)"
                    )
                    landscape.solution_name = idea.solution_name
                else:
                    logger.error(
                        f"❌ [{index}/{total}] Landscape solution name '{landscape.solution_name}' does not match "
                        f"input solution '{idea.solution_name}' - correcting to input name"
                    )
                    # Force correction even without fuzzy match
                    landscape.solution_name = idea.solution_name

            competitors_found = len(landscape.competitors)
            logger.info(f"[{index}/{total}] ✓ Completed {idea.solution_name}: {competitors_found} competitor(s) identified")
            return landscape
        else:
            logger.warning(f"[{index}/{total}] ✗ No landscape data returned for {idea.solution_name}")
            # Return empty landscape
            return CompetitiveLandscape(
                solution_name=idea.solution_name,
                competitors=[],
                market_gaps=["Analysis incomplete"],
                differentiation_opportunities=["Further research needed"],
                competitive_intensity="Unknown - analysis incomplete",
                recommended_positioning="Requires additional research",
                pricing_insights="Insufficient data"
            )

    def analyze_competition(self, parallel: bool = True, max_workers: int = 2) -> CompetitiveAnalysisResult:
        """
        Execute competitive analysis workflow.

        Args:
            parallel: If True, analyze solutions in parallel (default: True)
            max_workers: Maximum parallel workers (default: 2, conservative for API limits)

        Returns:
            CompetitiveAnalysisResult with landscape and opportunities
        """
        total_solutions = len(self.solution_ideas.solution_ideas)
        mode = "parallel" if parallel and total_solutions > 1 else "sequential"
        logger.info(f"Starting competitive analysis for {total_solutions} solution(s) in {mode} mode...")

        if not self.solution_ideas.solution_ideas:
            logger.warning("No solution ideas provided for competitive analysis")
            return CompetitiveAnalysisResult(
                solution_landscapes=[],
                top_opportunities=[],
                strategic_recommendations="No solution ideas available for competitive analysis"
            )

        try:
            # PRE-INITIALIZE crew to embed knowledge sources ONCE before parallel processing
            # This prevents duplicate embedding errors when multiple threads access crew simultaneously
            logger.debug("Pre-initializing crew and knowledge sources...")
            _ = self.crew()  # Triggers embedding on first call, then cached
            logger.debug("Crew pre-initialized successfully")

            all_landscapes = []

            if parallel and total_solutions > 1:
                # Parallel processing with ThreadPoolExecutor
                logger.info(f"Using parallel processing with {max_workers} worker(s)")

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all solutions for analysis
                    future_to_solution = {
                        executor.submit(
                            self._analyze_single_solution,
                            idea,
                            i,
                            total_solutions
                        ): idea
                        for i, idea in enumerate(self.solution_ideas.solution_ideas, 1)
                    }

                    # Collect results as they complete
                    for future in as_completed(future_to_solution):
                        solution_idea = future_to_solution[future]
                        try:
                            landscape = future.result()
                            all_landscapes.append(landscape)
                        except Exception as e:
                            logger.error(f"Failed to analyze {solution_idea.solution_name}: {e}")
                            # Add a placeholder landscape for failed analysis
                            all_landscapes.append(CompetitiveLandscape(
                                solution_name=solution_idea.solution_name,
                                competitors=[],
                                market_gaps=[f"Analysis failed: {str(e)}"],
                                differentiation_opportunities=["Retry recommended"],
                                competitive_intensity="Unknown - analysis failed",
                                recommended_positioning="Analysis incomplete",
                                pricing_insights="Analysis failed"
                            ))
            else:
                # Sequential processing (original behavior)
                logger.info("Using sequential processing")

                for i, idea in enumerate(self.solution_ideas.solution_ideas, 1):
                    landscape = self._analyze_single_solution(idea, i, total_solutions)
                    all_landscapes.append(landscape)

            # Aggregate insights across all solutions
            logger.info("Generating cross-solution strategic insights...")

            # Collect all differentiation opportunities from individual solutions
            all_opportunities = []
            for landscape in all_landscapes:
                all_opportunities.extend(landscape.differentiation_opportunities)

            # Take top 5 unique opportunities
            top_opportunities = list(dict.fromkeys(all_opportunities))[:5]

            # Generate strategic recommendations summary
            total_competitors = sum(len(l.competitors) for l in all_landscapes)
            strategic_recommendations = (
                f"Analyzed {len(all_landscapes)} solution(s) across the competitive landscape. "
                f"Total of {total_competitors} competitors identified. "
                f"Key insights: {' '.join(all_landscapes[0].market_gaps[:2]) if all_landscapes and all_landscapes[0].market_gaps else 'Market validation needed.'}"
            )

            result = CompetitiveAnalysisResult(
                solution_landscapes=all_landscapes,
                top_opportunities=top_opportunities if top_opportunities else ["Further market research recommended"],
                strategic_recommendations=strategic_recommendations
            )

            # Log cache performance statistics
            cache_stats = self.search_tool.get_cache_stats()
            logger.info(
                f"Competitive analysis complete: {len(result.solution_landscapes)} "
                f"landscape(s) analyzed, {len(result.top_opportunities)} top opportunities identified"
            )
            logger.info(
                f"Search cache performance: {cache_stats['hits']} hits, {cache_stats['misses']} misses, "
                f"{cache_stats['hit_rate']} hit rate ({cache_stats['cache_size']} cached queries)"
            )
            return result

        except Exception as e:
            logger.error(f"Competitive analysis failed: {e}")
            raise
