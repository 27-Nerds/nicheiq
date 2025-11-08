"""
DataSourceResearchCrew - Stage 9.75: Targeted Data Source Research
Deep research on data sources, APIs, and integrations for the SELECTED solution only.
"""

from typing import List, Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveLandscape
from ..models.data_source import DataSourceResearchResult
from ..models.seo_strategy import SEOStrategyReport
from ..models.solution_idea import SolutionIdea


@CrewBase
class DataSourceResearchCrew:
    """
    Specialized crew for researching data sources for the selected solution.
    Uses search tools to discover and validate actual APIs, databases, and providers.

    Architecture:
    - 2 agents working in pipeline
    - data_source_researcher: Searches for and discovers actual data sources
    - data_quality_analyst: Evaluates quality, cost, and integration complexity
    """

    agents_config = "config/data_source_agents.yaml"
    tasks_config = "config/data_source_tasks.yaml"

    def __init__(
        self,
        solution: SolutionIdea,
        competitive_landscape: Optional[CompetitiveLandscape],
        seo_strategy: Optional[SEOStrategyReport],
        niche_description: str
    ):
        """
        Initialize DataSourceResearchCrew.

        Args:
            solution: The selected solution to research data sources for
            competitive_landscape: Competitive analysis (what data do competitors use?)
            seo_strategy: SEO strategy (what keywords/content need data support?)
            niche_description: Original niche description for context
        """
        self.solution = solution
        self.competitive_landscape = competitive_landscape
        self.seo_strategy = seo_strategy
        self.niche_description = niche_description

        # Initialize search tool for data source discovery
        self.search_tool = SerperDevTool()

        logger.info(
            f"DataSourceResearchCrew initialized for solution: {solution.solution_name}"
        )

    @agent
    def data_source_researcher(self) -> Agent:
        """
        Agent responsible for discovering actual data sources via search.
        Finds APIs, databases, data providers, and aggregation services.

        Uses low temperature (0.2) for factual research and data gathering.
        """
        return Agent(
            config=self.agents_config["data_source_researcher"],
            tools=[self.search_tool],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,  # Low temperature for consistent factual research
                api_key=settings.openai_api_key
            ),
            verbose=True,
            function_calling_llm=ChatOpenAI(
                model=settings.function_calling_llm,
                temperature=0.1,  # Low temperature for reliable searches
                api_key=settings.openai_api_key
            ),
        )

    @agent
    def data_quality_analyst(self) -> Agent:
        """
        Agent responsible for evaluating data source quality, cost, and feasibility.
        Assesses coverage, freshness, integration complexity, and prioritization.
        """
        return Agent(
            config=self.agents_config["data_quality_analyst"],
            verbose=True,
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,
                api_key=settings.openai_api_key
            ),
        )

    @task
    def discover_data_sources_task(self) -> Task:
        """
        Task: Search for and discover actual data sources.
        Output: List of discovered APIs, databases, and providers with URLs.
        """
        return Task(
            config=self.tasks_config["discover_data_sources"],
            agent=self.data_source_researcher(),
        )

    @task
    def evaluate_data_sources_task(self) -> Task:
        """
        Task: Evaluate discovered data sources for quality, cost, and feasibility.
        Output: Prioritized data sources with quality assessments.
        """
        return Task(
            config=self.tasks_config["evaluate_data_sources"],
            agent=self.data_quality_analyst(),
            context=[self.discover_data_sources_task()],
        )

    @task
    def create_data_roadmap_task(self) -> Task:
        """
        Task: Create implementation roadmap for data integration.
        Output: DataSourceResearchResult with phased approach.
        """
        return Task(
            config=self.tasks_config["create_data_roadmap"],
            agent=self.data_quality_analyst(),
            context=[self.discover_data_sources_task(), self.evaluate_data_sources_task()],
            output_pydantic=DataSourceResearchResult,
        )

    @crew
    def crew(self) -> Crew:
        """Create the data source research crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
        )

    def research(self) -> DataSourceResearchResult:
        """
        Execute data source research for the selected solution.

        Returns:
            DataSourceResearchResult with prioritized data sources and roadmap
        """
        try:
            logger.info("Starting data source research...")

            # Prepare competitive insights
            competitive_data_notes = "No competitive data available"
            if self.competitive_landscape and self.competitive_landscape.competitors:
                competitor_names = [c.name for c in self.competitive_landscape.competitors[:3]]
                competitive_data_notes = f"Competitors identified: {', '.join(competitor_names)}"

            # Prepare SEO insights
            seo_priorities = "No SEO data available"
            if self.seo_strategy and self.seo_strategy.tier_1_keywords:
                top_keywords = [kw.keyword for kw in self.seo_strategy.tier_1_keywords[:3]]
                seo_priorities = f"High-priority keywords: {', '.join(top_keywords)}"

            # Execute crew with inputs
            crew_output = self.crew().kickoff(inputs={
                "solution_name": self.solution.solution_name,
                "solution_description": self.solution.description,
                "solution_features": ', '.join(self.solution.core_features if self.solution.core_features else []),
                "requires_data_aggregation": str(self.solution.requires_data_aggregation),
                "existing_data_sources": ', '.join(self.solution.data_sources if self.solution.data_sources else ['None specified']),
                "niche_description": self.niche_description,
                "competitive_data_notes": competitive_data_notes,
                "seo_priorities": seo_priorities,
            })

            # Extract the Pydantic model from CrewOutput
            result = crew_output.pydantic
            logger.info(
                f"Data source research complete: "
                f"{len(result.primary_data_sources)} primary sources discovered"
            )
            return result

        except Exception as e:
            logger.error(f"Data source research failed: {e}")
            raise
