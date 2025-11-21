"""
SolutionRefinementCrew - Stage 8.85: Solution Refinement Based on Keyword Insights
Single-agent crew for strategic refinement of selected solution using keyword validation data.
"""

from typing import Optional

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.solution_refinement import SolutionRefinement
from ..models.solution_idea import SolutionIdea
from ..models.keyword_data import CrewKeywordValidationResult


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
        )

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
        composite_score: float
    ) -> Optional[SolutionRefinement]:
        """
        Execute refinement crew to generate strategic recommendations.

        Args:
            selected_solution: The selected solution from Stage 8.75/8.8
            keyword_validation: Validation results with validated_count, total_volume, etc.
            composite_score: Original composite score from Stage 8.75

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
            "validation_signals": keyword_validation.validation_signals
        }

        try:
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)

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
                logger.error(f"[Stage 8.85] Refinement failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8.85] Refinement error: {str(e)}")
            return None
