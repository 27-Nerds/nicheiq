"""
DataSourceResearchCrew - Stage 9.75: Targeted Data Source Research
Deep research on data sources, APIs, and integrations for the SELECTED solution only.
"""

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveLandscape
from ..models.data_source import (
    DataImplementationPlan,
    DataSourceResearchResult,
    SourceEvaluationReport,
)
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
        competitive_landscape: CompetitiveLandscape | None,
        seo_strategy: SEOStrategyReport | None,
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
        Output: SourceEvaluationReport with priority tiers and quality metrics.
        """
        return Task(
            config=self.tasks_config["evaluate_data_sources"],
            agent=self.data_quality_analyst(),
            context=[self.discover_data_sources_task()],
            output_pydantic=SourceEvaluationReport,
        )

    @task
    def create_data_roadmap_task(self) -> Task:
        """
        Task: Create implementation roadmap for data integration.
        Output: DataImplementationPlan (implementation fields only, Python will merge with Task 2).
        """
        return Task(
            config=self.tasks_config["create_data_roadmap"],
            agent=self.data_quality_analyst(),
            context=[self.discover_data_sources_task(), self.evaluate_data_sources_task()],
            output_pydantic=DataImplementationPlan,
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

            # Python merge: Extract all task outputs and merge Task 2 + Task 3
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if len(task_outputs) < 3:
                logger.error(f"Expected 3 task outputs, got {len(task_outputs)}")
                raise ValueError("Incomplete task execution in data source crew")

            # Task 1: discover_data_sources (string output, not used)
            evaluation_output = task_outputs[1].pydantic  # Task 2: SourceEvaluationReport
            implementation_output = task_outputs[2].pydantic  # Task 3: DataImplementationPlan

            logger.info(
                f"Python merge: Combining evaluation ({len(evaluation_output.high_priority_sources)} HIGH priority sources) "
                f"with implementation plan ({len(implementation_output.implementation_phases)} phases)"
            )

            # Convert Task 2 evaluation sources to primary/fallback DataSource objects
            from ..models.data_source import DataSource

            primary_sources = []
            for src in evaluation_output.high_priority_sources:
                primary_sources.append(DataSource(
                    provider=src.provider,
                    url=src.url,
                    access_model="TBD",  # Not in EvaluatedDataSource, placeholder
                    integration_complexity=src.quality_metrics.integration_complexity.lower(),
                    priority="HIGH",
                    priority_rationale=src.priority_rationale,
                    cost_estimate=src.mvp_cost_estimate or "Cost estimate TBD",
                    coverage=src.quality_metrics.coverage_score,
                    update_frequency=src.quality_metrics.freshness,
                    data_quality_notes=src.quality_metrics.quality_assessment,
                ))

            fallback_sources = []
            for src in evaluation_output.medium_priority_sources + evaluation_output.low_priority_sources:
                fallback_sources.append(DataSource(
                    provider=src.provider,
                    url=src.url,
                    access_model="TBD",
                    integration_complexity=src.quality_metrics.integration_complexity.lower(),
                    priority="MEDIUM" if src in evaluation_output.medium_priority_sources else "LOW",
                    priority_rationale=src.priority_rationale,
                    cost_estimate=src.mvp_cost_estimate or "Cost estimate TBD",
                    coverage=src.quality_metrics.coverage_score,
                    update_frequency=src.quality_metrics.freshness,
                    data_quality_notes=src.quality_metrics.quality_assessment,
                ))

            # Extract data quality risks from evaluation
            data_quality_risks = []
            for src in evaluation_output.high_priority_sources + evaluation_output.medium_priority_sources:
                data_quality_risks.extend(src.identified_risks)

            # Create final result by merging all components
            result = DataSourceResearchResult(
                solution_name=self.solution.solution_name,
                primary_data_sources=primary_sources,
                fallback_sources=fallback_sources if fallback_sources else None,
                source_evaluation=evaluation_output,  # Preserve full evaluation
                implementation_phases=implementation_output.implementation_phases,
                data_partnerships_needed=implementation_output.data_partnerships_needed,
                estimated_monthly_cost=implementation_output.estimated_monthly_cost,
                data_quality_risks=data_quality_risks if data_quality_risks else None,
                implementation_roadmap=implementation_output.implementation_roadmap,
                competitive_data_insights=implementation_output.competitive_data_insights,
                seo_aligned_priorities=implementation_output.seo_aligned_priorities,
            )

            logger.info(
                f"[OK] Python merge complete: {len(result.primary_data_sources)} primary sources, "
                f"{len(result.fallback_sources) if result.fallback_sources else 0} fallback sources"
            )

            logger.info(
                f"Data source research complete: "
                f"{len(result.primary_data_sources)} primary sources discovered"
            )
            return result

        except Exception as e:
            logger.error(f"Data source research failed: {e}")
            raise
