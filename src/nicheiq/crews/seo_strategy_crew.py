"""
SEOStrategyCrew - Stage 9: Integrated Keyword Research + SEO Strategy
Multi-agent crew that performs keyword expansion and develops comprehensive SEO strategy.
"""

from typing import List, Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.seo_strategy import ExpandedKeywordList, SEOStrategyReport
from ..models.solution_idea import IdeaGenerationResult
from ..tools.dataforseo_tool import DataForSEOExpandTool, DataForSEOSearchVolumeTool


@CrewBase
class SEOStrategyCrew:
    """
    Specialized crew for integrated keyword research and SEO strategy development.
    Performs keyword expansion using DataForSEO and creates actionable SEO implementation plan.

    Architecture:
    - 3 agents working in pipeline
    - Keyword Strategist expands seed keywords and creates tiered opportunity structure
    - Content Strategist develops content and cluster plan
    - SEO Specialist creates technical roadmap and implementation plan
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(
        self,
        niche: str,
        selected_solution: 'SolutionIdea',
        selection_rationale: str,
        competitive_analysis: CompetitiveAnalysisResult,
        pain_points: Optional[PainPointAnalysisResult] = None,
    ):
        """
        Initialize SEOStrategyCrew with SELECTED solution focus.

        The keyword_strategist agent will:
        1. Generate seed keywords specifically for the selected solution
        2. Expand seeds using DataForSEO tool
        3. Analyze and create tiered strategy focused on this solution

        Args:
            niche: The niche/market area being researched
            selected_solution: THE SINGLE SOLUTION to focus SEO strategy on (from Stage 8.5)
            selection_rationale: Why this solution was selected over alternatives
            competitive_analysis: Competitive landscape from Stage 8
            pain_points: Optional pain point analysis from Stage 6
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.niche = niche
        self.selected_solution = selected_solution
        self.selection_rationale = selection_rationale
        self.competitive_analysis = competitive_analysis
        self.pain_points = pain_points

        # Initialize search tool for competitive keyword research
        self.search_tool = SerperDevTool()

        # Initialize DataForSEO tools for keyword expansion and search volume
        self.dataforseo_expand_tool = DataForSEOExpandTool()
        self.dataforseo_volume_tool = DataForSEOSearchVolumeTool()

        # Initialize knowledge sources for keyword research
        self.knowledge_sources = []

        # Add pain point knowledge source if available (for user language)
        if pain_points and pain_points.pain_points:
            pain_point_content = self._prepare_pain_point_keywords_content()

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.pain_point_knowledge = StringKnowledgeSource(
                content=pain_point_content,
                chunk_size=1000,     # Smaller chunks for focused keyword extraction
                chunk_overlap=150    # Moderate overlap
            )
            self.knowledge_sources.append(self.pain_point_knowledge)
            logger.info(
                f"Pain point keyword knowledge source created ({len(pain_point_content)} chars) "
                f"for user language extraction"
            )

        # Add competitive intelligence if available (for alternative keywords)
        competitive_landscape = self._find_solution_landscape()
        if competitive_landscape and competitive_landscape.competitors:
            comp_content = self._prepare_competitive_keywords_content(competitive_landscape)

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.competitive_knowledge = StringKnowledgeSource(
                content=comp_content,
                chunk_size=800,      # Tight chunks for specific competitor data
                chunk_overlap=100
            )
            self.knowledge_sources.append(self.competitive_knowledge)
            logger.info(
                f"Competitive keyword knowledge source created ({len(comp_content)} chars) "
                f"with {len(competitive_landscape.competitors)} competitors"
            )

        logger.info(
            f"SEOStrategyCrew initialized for selected solution: {selected_solution.solution_name}"
            f"{' with ' + str(len(self.knowledge_sources)) + ' knowledge source(s)' if self.knowledge_sources else ''}"
        )

    def _find_solution_landscape(self) -> Optional['CompetitiveLandscape']:
        """
        Find competitive landscape for the selected solution.

        Returns:
            CompetitiveLandscape for selected solution, or None if not found
        """
        for landscape in self.competitive_analysis.solution_landscapes:
            if landscape.solution_name == self.selected_solution.solution_name:
                return landscape
        return None

    def _prepare_pain_point_keywords_content(self) -> str:
        """
        Format pain points for keyword research with focus on user language.

        Extracts actual user phrasing from pain point quotes to identify
        natural search language patterns for keyword generation.

        Returns:
            Formatted string with pain point user language for keyword mining
        """
        formatted = []

        for pp in self.pain_points.pain_points:
            # Extract user language patterns for keywords
            formatted.append(f"""[PAIN POINT LANGUAGE FOR KEYWORDS]
[PROBLEM: {pp.title}]

**User Problem Description:**
{pp.description}

**Actual User Phrasing (All Quotes for Keyword Mining):**
{chr(10).join(f'- {quote}' for quote in pp.representative_quotes)}

**Keyword Signals:**
- Severity: {pp.severity_score:.2f} ({"high" if pp.severity_score >= 0.7 else "medium" if pp.severity_score >= 0.4 else "low"})
- User intent: {pp.willingness_to_pay:.2f} WTP indicates {"commercial intent" if pp.willingness_to_pay >= 0.6 else "informational intent"}
- Categories: {', '.join(pp.categories if pp.categories else ['N/A'])}
- Platforms: {', '.join(pp.source_platforms if pp.source_platforms else ['N/A'])}
""")

        return "\n\n---\n\n".join(formatted)

    def _prepare_competitive_keywords_content(self, landscape: 'CompetitiveLandscape') -> str:
        """
        Format competitive data for alternative keyword generation.

        Args:
            landscape: Competitive landscape for selected solution

        Returns:
            Formatted string with competitor data for keyword alternatives
        """
        formatted = [f"""[COMPETITIVE KEYWORDS FOR: {landscape.solution_name}]

**Direct Competitors ({len(landscape.competitors)}):**
{chr(10).join(f'- {c.name}: {c.description}' for c in landscape.competitors)}

**Market Gaps (Alternative Positioning Keywords):**
{chr(10).join(f'- {gap}' for gap in landscape.market_gaps)}

**Differentiation Opportunities (Unique Keyword Angles):**
{chr(10).join(f'- {opp}' for opp in landscape.differentiation_opportunities)}

**Recommended Positioning:**
{landscape.recommended_positioning}
"""]

        return "\n".join(formatted)

    @agent
    def keyword_strategist(self) -> Agent:
        """
        Agent responsible for expanding seed keywords using DataForSEO and creating tiered opportunity structure.
        Uses DataForSEO tools to expand keywords and analyze search metrics.
        Identifies quick wins (Tier 1) vs long-term plays (Tier 4).

        Uses low temperature (0.2) for data-driven keyword analysis.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["keyword_strategist"],
            tools=[self.dataforseo_expand_tool, self.dataforseo_volume_tool, self.search_tool],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.0,  # Zero temperature for precise data extraction (no creativity needed)
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
    def content_strategist(self) -> Agent:
        """
        Agent responsible for content strategy and topic clustering.
        Creates content recommendations aligned with keyword opportunities.

        Uses moderate temperature (0.5) for balanced creative strategy with structure.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["content_strategist"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.5,  # Moderate temperature for creative content ideas with structured output
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def seo_specialist(self) -> Agent:
        """
        Agent responsible for technical SEO and implementation roadmap.
        Provides URL structure, schema markup, and phased implementation plan.

        Uses low-moderate temperature (0.3) for precise technical recommendations.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["seo_specialist"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,  # Low-moderate temperature for technical precision
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def expand_keywords_conceptually_task(self) -> Task:
        """
        Task: Phase 9.5a - Conceptual keyword expansion without DataForSEO.

        Output: ExpandedKeywordList with 100-200 conceptual keywords organized by topic clusters.
        """
        return Task(
            config=self.tasks_config["expand_keywords_conceptually"],
            agent=self.content_strategist(),  # Use content strategist for strategic thinking
            output_pydantic=ExpandedKeywordList,
        )

    @task
    def create_strategy_from_enriched_task(self) -> Task:
        """
        Task: Phase 9.5c - Create SEO strategy from pre-enriched keywords.

        Output: SEOStrategyReport with data-driven strategy based on real keyword volumes.
        """
        return Task(
            config=self.tasks_config["create_strategy_from_enriched_keywords"],
            agent=self.seo_specialist(),  # Single agent for strategy synthesis
            output_pydantic=SEOStrategyReport,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the SEOStrategyCrew with all agents, tasks, and optional knowledge sources.

        If knowledge sources are available (pain points and/or competitive data),
        they are attached at crew level for keyword research and content strategy.

        Returns:
            Configured Crew instance with optional knowledge sources
        """
        crew_config = {
            "agents": self.agents,
            "tasks": self.tasks,
            "verbose": True,
            "process_type": "sequential",
        }

        # Add knowledge sources and embedder if available
        if self.knowledge_sources:
            crew_config["knowledge_sources"] = self.knowledge_sources
            crew_config["embedder"] = {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"  # Cost-effective embeddings
                }
            }

        return Crew(**crew_config)

    def expand_keywords_phase_1(self) -> ExpandedKeywordList:
        """
        Execute Phase 9.5a: Conceptual Keyword Expansion.

        Runs ONLY the conceptual expansion task without DataForSEO.
        Returns 100-200 strategic keywords organized by topic clusters.

        Returns:
            ExpandedKeywordList with conceptual keywords for Phase 9.5b enrichment
        """
        logger.info(f"Starting Phase 9.5a: Conceptual keyword expansion for: {self.selected_solution.solution_name}")

        try:
            # Format pain points context
            pain_points_context = ""
            if self.pain_points and self.pain_points.pain_points:
                pain_points_context = "\n".join([
                    f"**{pp.title}** (Severity: {pp.severity_score}/10, Mentions: {pp.mention_count})\n"
                    f"- Problem: {pp.description}\n"
                    f"- User Quote: {pp.representative_quotes[0] if pp.representative_quotes else 'N/A'}\n"
                    for pp in self.pain_points.pain_points[:10]
                ])

            # Format competitive context
            competitive_context = ""
            found_landscape = False

            for landscape in self.competitive_analysis.solution_landscapes:
                if landscape.solution_name == self.selected_solution.solution_name:
                    competitive_context = f"""**Competitive Landscape for {landscape.solution_name}:**
- **Intensity:** {landscape.competitive_intensity}
- **Competitors ({len(landscape.competitors)}):** {', '.join(c.name for c in landscape.competitors[:5])}
- **Market Gaps:** {', '.join(landscape.market_gaps[:3])}
- **Differentiation Opportunities:** {', '.join(landscape.differentiation_opportunities[:3])}
- **Recommended Positioning:** {landscape.recommended_positioning}"""
                    found_landscape = True
                    logger.info(f"✓ Found competitive landscape for {landscape.solution_name}")
                    break

            if not found_landscape:
                logger.warning(f"No competitive landscape found for '{self.selected_solution.solution_name}'")
                competitive_context = "[NO COMPETITIVE DATA AVAILABLE - Skip competitor keywords or note as insufficient data]"

            # Create a single-task crew for conceptual expansion
            expansion_crew = Crew(
                agents=[self.content_strategist()],
                tasks=[self.expand_keywords_conceptually_task()],
                verbose=True,
                process_type="sequential",
            )

            # Execute with focused context
            crew_output = expansion_crew.kickoff(inputs={
                "niche": self.niche,
                "selected_solution_name": self.selected_solution.solution_name,
                "selected_solution_value_prop": self.selected_solution.value_proposition,
                "selected_solution_personas": ', '.join(str(p) for p in (self.selected_solution.target_personas[:3] if self.selected_solution.target_personas else [])),
                "selected_solution_features": ', '.join(str(f) for f in (self.selected_solution.core_features[:5] if self.selected_solution.core_features else [])),
                "selected_solution_pain_points": ', '.join(str(p) for p in (self.selected_solution.pain_points_addressed[:3] if self.selected_solution.pain_points_addressed else [])),
                "competitive_context": competitive_context,
            })

            # Extract the Pydantic model
            result = crew_output.pydantic
            logger.info(
                f"Phase 9.5a complete: {len(result.keywords)} conceptual keywords generated, "
                f"{len(result.topic_clusters)} topic clusters identified"
            )
            return result

        except Exception as e:
            logger.error(f"Phase 9.5a conceptual expansion failed: {e}")
            raise

    def create_strategy_from_enriched(
        self,
        enriched_keywords: list,
        topic_clusters: list
    ) -> SEOStrategyReport:
        """
        Execute Phase 9.5c: Create SEO strategy from pre-enriched keywords.

        This method receives keywords that have already been enriched with DataForSEO
        data (search volumes, competition) and creates a comprehensive strategy.

        Args:
            enriched_keywords: List of dicts from DataForSEO with volumes/competition
            topic_clusters: List of TopicCluster objects from Phase 9.5a

        Returns:
            SEOStrategyReport with data-driven strategy
        """
        logger.info(f"Starting Phase 9.5c: Creating strategy from {len(enriched_keywords)} enriched keywords")

        try:
            # Format enriched keywords for task input
            enriched_keywords_formatted = []
            for k in enriched_keywords:
                # Format competition as string with label and index
                # e.g., "LOW (23)", "MEDIUM (54)", "HIGH (78)"
                competition_index = k.get("competition_index", 0)
                if competition_index < 30:
                    comp_label = "LOW" if competition_index >= 15 else "VERY LOW"
                elif competition_index < 60:
                    comp_label = "MEDIUM"
                elif competition_index < 80:
                    comp_label = "HIGH"
                else:
                    comp_label = "VERY HIGH"

                competition_str = f"{comp_label} ({competition_index})"

                formatted = {
                    "keyword": k.get("keyword", ""),
                    "search_volume": k.get("search_volume", 0),
                    "competition": competition_str,
                }
                # Include monthly_searches if available
                if k.get("monthly_searches"):
                    formatted["monthly_searches"] = k.get("monthly_searches")
                enriched_keywords_formatted.append(formatted)

            # Format topic clusters summary
            topic_clusters_summary = "\n".join([
                f"- **{c.name}** (Priority {c.strategic_importance}/5): {c.description}"
                for c in topic_clusters
            ])

            # Create a single-task crew for strategy creation from enriched data
            strategy_crew = Crew(
                agents=[self.seo_specialist()],  # Single specialist agent
                tasks=[self.create_strategy_from_enriched_task()],
                verbose=True,
                process_type="sequential",
            )

            # Execute with enriched keywords
            crew_output = strategy_crew.kickoff(inputs={
                "niche": self.niche,
                "selected_solution_name": self.selected_solution.solution_name,
                "enriched_keywords": enriched_keywords_formatted,
                "enriched_keywords_count": len(enriched_keywords),
                "topic_clusters_summary": topic_clusters_summary,
            })

            # Extract the Pydantic model
            result = crew_output.pydantic
            logger.info(
                f"Phase 9.5c complete: SEO strategy created with "
                f"{len(result.tier_1_keywords) if result.tier_1_keywords else 0} Tier 1 keywords, "
                f"{len(result.topic_clusters) if result.topic_clusters else 0} topic clusters"
            )
            return result

        except Exception as e:
            logger.error(f"Phase 9.5c strategy creation from enriched keywords failed: {e}")
            raise