"""
SolutionRefinementCrew - Stage 10: Solution Refinement Based on Keyword Insights
Single-agent crew for strategic refinement of selected solution using keyword validation data.
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_crew_llm
from ..models.solution_idea import SolutionIdea
from ..models.solution_refinement import SolutionRefinement
from ..utils.validation.crew_guardrails import validate_solution_refinement


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
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.5,  # Balanced creativity for strategic thinking (ignored for reasoning models)
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
        return SafeTask(
            config=self.tasks_config["refine_solution_strategy"],
            agent=self.strategic_advisor(),
            output_pydantic=SolutionRefinement,
            guardrail=validate_solution_refinement,
            guardrail_max_retries=2,
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
        seo_strategy_report,
        composite_score: float,
        allowed_project_types: list[str] | None = None
    ) -> SolutionRefinement | None:
        """
        Execute refinement crew to generate strategic recommendations.

        Args:
            selected_solution: The selected solution from Stage 5
            seo_strategy_report: SEOStrategyReport with comprehensive keyword data
            composite_score: Original composite score from Stage 5
            allowed_project_types: Optional project type constraints from user

        Returns:
            SolutionRefinement object with strategic recommendations, or None if refinement fails
        """
        import math
        import re

        # Derive keyword context from SEO strategy report
        all_keywords = []
        for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
            tier_kws = getattr(seo_strategy_report, tier_attr, None) or []
            all_keywords.extend(tier_kws)

        total_volume = seo_strategy_report.total_monthly_volume or 0
        keyword_count = seo_strategy_report.total_keywords_analyzed or 0

        # Demand signal based on total volume
        if total_volume >= 5000:
            demand_signal = "strong"
        elif total_volume >= 2000:
            demand_signal = "moderate"
        else:
            demand_signal = "weak"

        # Early exit if demand signal is too weak
        if demand_signal == "weak" and total_volume < 2000:
            logger.warning(
                f"Skipping refinement for {selected_solution.solution_name} - "
                f"weak demand signal ({total_volume} monthly volume)"
            )
            return None

        # Avg competition: parse from tier keyword competition strings
        competitions = []
        for k in all_keywords:
            comp = getattr(k, 'competition', None)
            if comp and isinstance(comp, str):
                match = re.search(r'\((\d+)\)', comp)
                if match:
                    competitions.append(int(match.group(1)))
                    continue
            kd = getattr(k, 'keyword_difficulty', None)
            if kd is not None:
                competitions.append(int(kd))
        avg_competition = sum(competitions) / len(competitions) if competitions else 50.0

        # keyword_demand_score: logarithmic scale
        if total_volume > 0:
            keyword_demand_score = min(math.log10(total_volume) / 6.0, 1.0)
        else:
            keyword_demand_score = 0.0

        # Top keywords sorted by volume
        top_keywords = sorted(all_keywords, key=lambda k: k.search_volume, reverse=True)[:5]
        top_keywords_str = ", ".join([
            f"{kw.keyword} ({kw.search_volume}/mo)"
            for kw in top_keywords
        ])

        # Geographic keywords from tier 3
        geo_keywords = []
        for group in (getattr(seo_strategy_report, 'tier_3_geographic_groups', None) or []):
            for entry in (getattr(group, 'keywords', None) or []):
                kw_str = getattr(entry, 'keyword', None) or getattr(entry, 'term', None)
                if kw_str:
                    geo_keywords.append(kw_str)
        if not geo_keywords:
            for group in (getattr(seo_strategy_report, 'tier_3_geographic_groups', None) or []):
                geo_keywords.append(group.region_name)
        geo_keywords_str = ", ".join(geo_keywords[:10])

        # Validation signals derived from SEO data
        validation_signals = {
            "has_search_demand": total_volume > 1000,
            "keyword_diversity": keyword_count >= 5,
            "high_volume_presence": any(k.search_volume > 500 for k in all_keywords) if all_keywords else False,
            "average_volume_per_keyword": total_volume / keyword_count if keyword_count > 0 else 0,
        }

        logger.info(f"[Stage 10] Refining strategy for: {selected_solution.solution_name}")

        inputs = {
            "solution_name": selected_solution.solution_name,
            "solution_description": selected_solution.description,
            "core_features": ", ".join(selected_solution.core_features[:5]) if selected_solution.core_features else "Not specified",
            "target_personas": ", ".join(selected_solution.target_personas[:3]) if selected_solution.target_personas else "General users",
            "validated_keyword_count": keyword_count,
            "total_monthly_volume": total_volume,
            "keyword_demand_score": keyword_demand_score,
            "top_keywords": top_keywords_str,
            "top_geographic_keywords": geo_keywords_str,
            "demand_signal": demand_signal,
            "avg_competition": avg_competition,
            "composite_score": composite_score,
            "validation_signals": validation_signals,
            "allowed_project_types": ', '.join(allowed_project_types) if allowed_project_types else "All types allowed"
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                logger.info(
                    f"[Stage 10] Refinement completed:\n"
                    f"  - Geographic priorities: {', '.join(result.pydantic.geographic_priorities[:3])}\n"
                    f"  - Category pivot: {result.pydantic.category_pivot_recommendation or 'None'}\n"
                    f"  - Feature priorities: {len(result.pydantic.feature_priorities)} recommendations\n"
                    f"  - Strategic insights: {len(result.pydantic.strategic_insights)} insights"
                )
                return result.pydantic
            else:
                logger.error("[Stage 10] Refinement failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 10] Refinement error: {str(e)}")
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
