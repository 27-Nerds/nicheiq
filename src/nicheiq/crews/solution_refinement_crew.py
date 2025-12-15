"""
SolutionRefinementCrew - Stage 8.85: Solution Refinement Based on Keyword Insights
Single-agent crew for strategic refinement of selected solution using keyword validation data.
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.solution_idea import SolutionIdea
from ..models.solution_refinement import SolutionRefinement


@CrewBase
class SolutionRefinementCrew:
    """
    Specialized crew for refining solution strategy based on keyword validation insights.

    Architecture:
    - Single agent: Strategic Advisor
    - Single task: Refine solution strategy using keyword demand signals
    - Output: SolutionRefinement with geographic priorities, category pivots, feature prioritization
    """

    agents_config = "config/solution_refinement_agents.yaml"
    tasks_config = "config/solution_refinement_tasks.yaml"

    def __init__(self):
        """Initialize SolutionRefinementCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def strategic_advisor(self) -> Agent:
        """
        Strategic advisor agent that analyzes keyword validation data.

        Uses keyword insights to recommend:
        - Geographic market priorities
        - Category/positioning pivots
        - Feature prioritization
        - Content strategy direction
        """
        return Agent(
            config=self.agents_config["strategic_advisor"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.5,  # Balanced creativity for strategic thinking
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def refine_solution_strategy_task(self) -> Task:
        """
        Task: Refine solution strategy using keyword validation insights.

        Analyzes keyword demand data to provide actionable strategic recommendations
        across geographic expansion, category positioning, feature priorities, and content strategy.
        """
        return Task(
            config=self.tasks_config["refine_solution_strategy"],
            agent=self.strategic_advisor(),
            output_pydantic=SolutionRefinement,
            guardrail=self._validate_refinement_output,
        )

    def _validate_refinement_output(self, task_output) -> tuple[bool, Any]:
        """
        Validate solution refinement output meets CRITICAL RULES.

        Checks:
        - geographic_priorities has at least 1 item
        - feature_priorities has 1-10 items (model enforces, but double-check)
        - strategic_insights has 3-8 items (model enforces, but double-check)
        - content_strategy_preview is substantive (>100 chars)

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic
            if result is None:
                return (False, "Solution refinement returned None pydantic output")

            # Validate geographic_priorities
            if not result.geographic_priorities or len(result.geographic_priorities) == 0:
                return (False, "geographic_priorities cannot be empty - must have at least 1 market")

            # Validate feature_priorities bounds
            if len(result.feature_priorities) < 1:
                return (False, "feature_priorities must have at least 1 entry")
            if len(result.feature_priorities) > 10:
                return (False, f"feature_priorities exceeds max 10, got {len(result.feature_priorities)}")

            # Validate strategic_insights bounds
            if len(result.strategic_insights) < 3:
                return (False, f"strategic_insights must have at least 3 entries, got {len(result.strategic_insights)}")
            if len(result.strategic_insights) > 8:
                return (False, f"strategic_insights exceeds max 8, got {len(result.strategic_insights)}")

            # Validate content_strategy_preview is substantive
            if len(result.content_strategy_preview) < 100:
                return (False, f"content_strategy_preview too short ({len(result.content_strategy_preview)} chars). Must be substantive (100+ chars).")

            logger.info(
                f"✓ Refinement guardrail passed: "
                f"{len(result.geographic_priorities)} geo priorities, "
                f"{len(result.feature_priorities)} feature priorities, "
                f"{len(result.strategic_insights)} insights"
            )
            return (True, result)

        except Exception as e:
            return (False, f"Refinement validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the refinement crew.

        Single-agent, single-task crew optimized for strategic analysis.
        """
        return Crew(
            agents=[self.strategic_advisor()],
            tasks=[self.refine_solution_strategy_task()],
            verbose=True,
        )

    def refine(
        self,
        selected_solution: SolutionIdea,
        keyword_validation: CrewKeywordValidationResult,
        composite_score: float,
        allowed_project_types: list[str] | None = None
    ) -> SolutionRefinement | None:
        """
        Execute refinement crew to generate strategic recommendations.

        Args:
            selected_solution: The selected solution from Stage 8.75/8.8
            keyword_validation: Validation results with validated_count, total_volume, etc.
            composite_score: Original composite score from Stage 8.75
            allowed_project_types: Optional project type constraints from user

        Returns:
            SolutionRefinement object with strategic recommendations, or None if refinement fails
        """
        # Early exit if demand signal is too weak
        demand_signal = keyword_validation.demand_signal
        if demand_signal == "weak" and keyword_validation.total_volume < 2000:
            logger.warning(
                f"Skipping refinement for {selected_solution.solution_name} - "
                f"weak demand signal ({keyword_validation.total_volume} monthly volume)"
            )
            return None

        logger.info(f"[Stage 8.85] Refining strategy for: {selected_solution.solution_name}")

        # Prepare inputs for the refinement task
        top_keywords_str = ", ".join([
            f"{kw.get('keyword', 'N/A')} ({kw.get('volume', 0)}/mo)"
            for kw in keyword_validation.top_keywords[:5]
        ])

        geo_keywords_str = ", ".join(keyword_validation.top_geographic_keywords)

        inputs = {
            "solution_name": selected_solution.solution_name,
            "solution_description": selected_solution.description,
            "core_features": ", ".join(selected_solution.core_features[:5]) if selected_solution.core_features else "Not specified",
            "target_personas": ", ".join(selected_solution.target_personas[:3]) if selected_solution.target_personas else "General users",
            "validated_keyword_count": keyword_validation.validated_count,
            "total_monthly_volume": keyword_validation.total_volume,
            "keyword_demand_score": keyword_validation.keyword_demand_score,
            "top_keywords": top_keywords_str,
            "top_geographic_keywords": geo_keywords_str,
            "demand_signal": demand_signal,
            "avg_competition": keyword_validation.avg_competition,
            "composite_score": composite_score,
            "validation_signals": keyword_validation.validation_signals,
            "allowed_project_types": ', '.join(allowed_project_types) if allowed_project_types else "All types allowed"
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                logger.info(
                    f"[Stage 8.85] Refinement completed:\n"
                    f"  - Geographic priorities: {', '.join(result.pydantic.geographic_priorities[:3])}\n"
                    f"  - Category pivot: {result.pydantic.category_pivot_recommendation or 'None'}\n"
                    f"  - Feature priorities: {len(result.pydantic.feature_priorities)} recommendations\n"
                    f"  - Strategic insights: {len(result.pydantic.strategic_insights)} insights"
                )
                return result.pydantic
            else:
                logger.error("[Stage 8.85] Refinement failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8.85] Refinement error: {str(e)}")
            return None

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            CrewAI UsageMetrics object or None if no execution yet
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
