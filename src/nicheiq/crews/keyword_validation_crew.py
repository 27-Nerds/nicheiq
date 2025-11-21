"""
Keyword Validation Crew for Stage 8.8 - Agent-Based Keyword Demand Validation.

This crew validates market demand for solution concepts using adaptive keyword
research strategies. Uses DataForSEO tools for expansion/validation and applies
semantic relevance filtering.
"""

import logging

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI

from ..config.settings import settings
from ..models.keyword_data import KeywordAttemptResult
from ..tools.dataforseo_tool import DataForSEOExpandTool, DataForSEOSearchVolumeTool

logger = logging.getLogger(__name__)

@CrewBase
class KeywordValidationCrew:
    """
    Crew for validating keyword demand using adaptive research strategies.

    Implements 2-strategy approach:
    1. Hybrid strategy (programmatic + LLM seeds)
    2. Competitor alternative strategy

    Uses Flow-level pivot logic (not agent decisions) for reliability.
    """

    agents_config = "config/keyword_validation_agents.yaml"
    tasks_config = "config/keyword_validation_tasks.yaml"

    def __init__(
        self,
        solution: any,
        niche_context: any,
        pain_points: any | None = None,
        competitive_analysis: any | None = None,
    ):
        """
        Initialize crew with solution and context data.

        Args:
            solution: SolutionIdea object to validate
            niche_context: NicheContext object
            pain_points: Optional PainPointAnalysis object
            competitive_analysis: Optional CompetitiveAnalysis object
        """
        self.solution = solution
        self.niche_context = niche_context
        self.pain_points = pain_points
        self.competitive_analysis = competitive_analysis

        # Format context for task inputs
        self.solution_name = solution.solution_name
        self.project_type = solution.project_type or "saas"
        self.solution_description = solution.description
        self.value_proposition = solution.value_proposition
        self.core_features = ", ".join(solution.core_features[:5]) if solution.core_features else "N/A"
        self.target_personas = ", ".join(solution.target_personas[:3]) if solution.target_personas else "N/A"

        # Format pain points
        self.pain_points_formatted = self._format_pain_points()

        # Format niche context
        self.niche_description = niche_context.niche_description if niche_context else "N/A"
        self.market_segments = ", ".join(niche_context.market_segments[:5]) if niche_context and niche_context.market_segments else "N/A"

        # Format competitors
        self.competitor_names = self._format_competitors()

        logger.info(f"[KeywordValidationCrew] Initialized for solution: {self.solution_name}")

    def _format_pain_points(self) -> str:
        """Format pain points for task input."""
        if not self.pain_points or not hasattr(self.pain_points, 'pain_points'):
            return "N/A"

        pain_points = self.pain_points.pain_points if self.pain_points.pain_points else []
        if not pain_points:
            return "N/A"

        # Get top N pain points by severity (configurable)
        sorted_pps = sorted(
            [p for p in pain_points if p is not None],
            key=lambda p: getattr(p, 'severity_score', 0),
            reverse=True
        )[:settings.keyword_validation_top_pain_points]

        formatted = []
        for pp in sorted_pps:
            if hasattr(pp, 'title') and pp.title:
                formatted.append(f"- {pp.title}")

        return "\n".join(formatted) if formatted else "N/A"

    def _format_competitors(self) -> str:
        """Format competitor names for task input."""
        competitors = []

        # Try to get from solution's competitive landscape
        if hasattr(self.solution, 'competitive_landscape') and self.solution.competitive_landscape:
            if (hasattr(self.solution.competitive_landscape, 'competitors') and
                self.solution.competitive_landscape.competitors is not None):
                competitors = [
                    c.name for c in self.solution.competitive_landscape.competitors[:settings.keyword_validation_top_competitors]
                    if c is not None and hasattr(c, 'name') and c.name
                ]

        # Fallback to competitive_analysis if available
        if not competitors and self.competitive_analysis:
            if hasattr(self.competitive_analysis, 'competitors') and self.competitive_analysis.competitors:
                competitors = [
                    c.name for c in self.competitive_analysis.competitors[:settings.keyword_validation_top_competitors]
                    if c is not None and hasattr(c, 'name') and c.name
                ]

        return ", ".join(competitors) if competitors else "N/A"

    @agent
    def keyword_analyst(self) -> Agent:
        """Create keyword demand analyst agent with configurable LLM."""
        return Agent(
            config=self.agents_config["keyword_demand_analyst"],
            llm=ChatOpenAI(
                model=settings.keyword_research_llm,
                temperature=settings.keyword_validation_temperature,
                api_key=settings.openai_api_key
            ),
            tools=[
                DataForSEOExpandTool(),
                DataForSEOSearchVolumeTool()
            ],
            verbose=True
        )

    def _validate_strategy_output(self, task_output, strategy_name: str) -> tuple:
        """
        Shared validation logic for all strategy outputs.

        Validates:
        - Relevance score is within bounds (0.0-1.0)
        - Minimum keyword count (5+)
        - Quality flag is set correctly
        - Keyword count consistency (list length matches total_keywords)
        - SUCCESS flag has sufficient keywords (≥20)

        Args:
            task_output: CrewAI task output
            strategy_name: Strategy name for logging (e.g., "Hybrid", "Competitor")

        Returns:
            tuple: (success: bool, result_or_error: any)
        """
        try:
            result = task_output.pydantic

            # Validate relevance score bounds
            if not (0.0 <= result.avg_relevance_score <= 1.0):
                return (False, f"Invalid relevance score: {result.avg_relevance_score}")

            # Validate keyword count consistency
            if len(result.keywords) != result.total_keywords:
                return (False,
                    f"Keyword count mismatch: {len(result.keywords)} keywords in list vs "
                    f"{result.total_keywords} in total_keywords field")

            # Validate minimum keywords (warning only, not failure)
            if result.total_keywords < 5:
                logger.warning(
                    f"[Guardrail] {strategy_name} strategy found only "
                    f"{result.total_keywords} keywords (min: 5)"
                )
                # Don't fail - weak demand signal is valid (< 5 keywords acceptable)
                # Note: SUCCESS flag requires ≥20 keywords (validated at line 186)

            # Validate quality flag
            if result.quality_flag not in ["SUCCESS", "INSUFFICIENT"]:
                return (False, f"Invalid quality_flag: {result.quality_flag}")

            # Validate SUCCESS flag has sufficient keywords
            if result.quality_flag == "SUCCESS" and result.total_keywords < 20:
                return (False,
                    f"SUCCESS flag requires ≥20 keywords, got {result.total_keywords}")

            logger.info(
                f"[Guardrail] {strategy_name} strategy passed: "
                f"{result.total_keywords} keywords, "
                f"relevance={result.avg_relevance_score:.2f}, "
                f"flag={result.quality_flag}"
            )

            return (True, result)

        except Exception as e:
            logger.error(f"[Guardrail] Validation error: {e}", exc_info=True)
            return (False, f"Validation error: {str(e)}")

    def _validate_hybrid_output(self, task_output) -> tuple:
        """Guardrail for hybrid strategy task output."""
        return self._validate_strategy_output(task_output, "Hybrid")

    def _validate_competitor_output(self, task_output) -> tuple:
        """Guardrail for competitor strategy task output."""
        return self._validate_strategy_output(task_output, "Competitor")

    @task
    def hybrid_strategy_task(self) -> Task:
        """Task for hybrid keyword research strategy."""
        return Task(
            config=self.tasks_config["hybrid_strategy"],
            agent=self.keyword_analyst(),
            output_pydantic=KeywordAttemptResult,
            guardrail=self._validate_hybrid_output
        )

    @task
    def competitor_strategy_task(self) -> Task:
        """Task for competitor alternative keyword research strategy."""
        return Task(
            config=self.tasks_config["competitor_strategy"],
            agent=self.keyword_analyst(),
            output_pydantic=KeywordAttemptResult,
            guardrail=self._validate_competitor_output
        )

    @crew
    def crew(self) -> Crew:
        """Create the keyword validation crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True
        )

    def run_hybrid_strategy(self) -> KeywordAttemptResult:
        """
        Run hybrid keyword research strategy.

        Returns:
            KeywordAttemptResult with quality_flag indicating success/failure
        """
        logger.info(f"[KeywordValidationCrew] Running hybrid strategy for {self.solution_name}")

        # Create crew with only hybrid task
        crew = Crew(
            agents=[self.keyword_analyst()],
            tasks=[self.hybrid_strategy_task()],
            verbose=True
        )

        # Kickoff with formatted inputs
        inputs = {
            "solution_name": self.solution_name,
            "project_type": self.project_type,
            "solution_description": self.solution_description,
            "value_proposition": self.value_proposition,
            "core_features": self.core_features,
            "target_personas": self.target_personas,
            "pain_points_formatted": self.pain_points_formatted,
            "niche_description": self.niche_description,
            "market_segments": self.market_segments
        }

        # Calculate actual count (0 if "N/A")
        pain_points_count = (
            0 if self.pain_points_formatted == "N/A"
            else len(self.pain_points_formatted.splitlines())
        )

        logger.debug(
            f"[KeywordValidationCrew] Hybrid inputs: "
            f"pain_points={pain_points_count} items, "
            f"market_segments={self.market_segments}"
        )

        crew_output = crew.kickoff(inputs=inputs)
        result = crew_output.pydantic

        logger.info(
            f"[KeywordValidationCrew] Hybrid strategy complete: "
            f"{result.total_keywords} keywords, relevance={result.avg_relevance_score:.2f}"
        )

        return result

    def run_competitor_strategy(self) -> KeywordAttemptResult:
        """
        Run competitor alternative keyword research strategy.

        Returns:
            KeywordAttemptResult with quality_flag indicating success/failure
        """
        logger.info(f"[KeywordValidationCrew] Running competitor strategy for {self.solution_name}")

        # Create crew with only competitor task
        crew = Crew(
            agents=[self.keyword_analyst()],
            tasks=[self.competitor_strategy_task()],
            verbose=True
        )

        # Kickoff with formatted inputs
        inputs = {
            "solution_name": self.solution_name,
            "project_type": self.project_type,
            "solution_description": self.solution_description,
            "competitor_names": self.competitor_names,
            "niche_description": self.niche_description
        }

        logger.debug(
            f"[KeywordValidationCrew] Competitor inputs: "
            f"competitors={self.competitor_names}"
        )

        crew_output = crew.kickoff(inputs=inputs)
        result = crew_output.pydantic

        logger.info(
            f"[KeywordValidationCrew] Competitor strategy complete: "
            f"{result.total_keywords} keywords, relevance={result.avg_relevance_score:.2f}"
        )

        return result
