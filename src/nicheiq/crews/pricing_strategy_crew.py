"""
Pricing Strategy Validation Crew (Stage 8.7).

Validates monetization strategy by determining optimal pricing based on:
- Competitor pricing benchmarks
- Pain point willingness-to-pay (WTP) scores
- Selected solution features and positioning
"""

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_llm_kwargs
from ..models.research_state import PricingStrategyResult
from ..utils.crew_helpers import compute_wtp_summary, compute_cac_range


@CrewBase
class PricingStrategyCrew:
    """
    Crew for validating pricing strategy in Stage 8.7.

    Analyzes:
    - Competitor pricing from competitive analysis
    - Pain point WTP scores from pain point analysis
    - Selected solution features and positioning

    Outputs:
    - Recommended pricing tiers (Starter, Pro, Enterprise)
    - ARPU and LTV estimates
    - Competitive positioning analysis
    - WTP validation
    """

    agents_config = "config/pricing_strategy_agents.yaml"
    tasks_config = "config/pricing_strategy_tasks.yaml"

    def __init__(self):
        """Initialize PricingStrategyCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def pricing_analyst(self) -> Agent:
        """
        Pricing Analyst agent.

        Specializes in SaaS pricing strategy, value-based pricing,
        and competitive pricing analysis.
        """
        return Agent(
            config=self.agents_config["pricing_analyst"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.3,  # Low temperature for consistent pricing analysis (ignored for reasoning models)
            )),
            verbose=True,
        )

    @task
    def pricing_strategy_analysis_task(self) -> Task:
        """
        Main pricing strategy analysis task.

        Analyzes competitor pricing, pain point WTP scores, and solution features
        to recommend optimal pricing strategy.
        """
        return Task(
            config=self.tasks_config["pricing_strategy_analysis"],
            agent=self.pricing_analyst(),
            output_pydantic=PricingStrategyResult,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the pricing strategy crew.

        Single-agent, single-task crew optimized for pricing analysis.
        """
        return Crew(
            agents=[self.pricing_analyst()],
            tasks=[self.pricing_strategy_analysis_task()],
            verbose=True,
        )

    def _extract_competitor_pricing(self, competitive_analysis, selected_solution_name: str = None) -> str:
        """
        Extract competitor pricing information from competitive analysis.

        Args:
            competitive_analysis: CompetitiveAnalysisResult with solution_landscapes
            selected_solution_name: Name of selected solution to find its landscape

        Returns:
            Formatted string with competitor pricing data
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitor pricing data available."

        # Find the landscape for the selected solution
        landscape = None
        for l in competitive_analysis.solution_landscapes:
            if selected_solution_name and l.solution_name == selected_solution_name:
                landscape = l
                break

        # Fallback to first landscape if not found
        if not landscape:
            landscape = competitive_analysis.solution_landscapes[0]

        if not landscape.competitors:
            # Use pricing_insights from landscape if available
            if landscape.pricing_insights:
                return f"**Pricing Insights:**\n{landscape.pricing_insights}"
            return "No competitor pricing data available."

        pricing_info = []
        for competitor in landscape.competitors[:10]:  # Top 10
            pricing_str = f"- {competitor.name}"

            # Add description
            if competitor.description:
                pricing_str += f" ({competitor.description[:50]}...)" if len(competitor.description) > 50 else f" ({competitor.description})"

            # Add pricing if available
            if competitor.pricing_model:
                pricing_str += f": {competitor.pricing_model}"

            pricing_info.append(pricing_str)

        # Add pricing insights from landscape
        if landscape.pricing_insights:
            pricing_info.append(f"\n**Pricing Insights:**\n{landscape.pricing_insights}")

        if not pricing_info:
            return "Competitors identified but pricing data not available."

        return "\n".join(pricing_info)

    def _extract_wtp_scores(self, pain_point_analysis) -> str:
        """
        Extract willingness-to-pay scores from pain point analysis.

        Returns:
            Formatted string with WTP data
        """
        if not pain_point_analysis or not pain_point_analysis.pain_points:
            return "No willingness-to-pay data available."

        wtp_info = []
        for pain_point in pain_point_analysis.pain_points[:10]:  # Top 10
            wtp_str = f"- {pain_point.title}"

            if hasattr(pain_point, 'severity_score'):
                wtp_str += f" (Severity: {pain_point.severity_score:.2f})"

            if hasattr(pain_point, 'willingness_to_pay'):
                wtp_str += f" - WTP Score: {pain_point.willingness_to_pay:.2f}"

            wtp_info.append(wtp_str)

        if not wtp_info:
            return "Pain points identified but WTP scores not available."

        return "\n".join(wtp_info)

    def _format_solution_features(self, selected_solution) -> str:
        """
        Format solution core features for pricing analysis.

        Returns:
            Formatted string with solution features
        """
        features = []

        # Core features
        if hasattr(selected_solution, 'core_features') and selected_solution.core_features:
            features.append("Core Features:")
            for feature in selected_solution.core_features:
                features.append(f"  - {feature}")

        # Differentiation factors
        if hasattr(selected_solution, 'differentiation') and selected_solution.differentiation:
            features.append("\nDifferentiation:")
            features.append(f"  {selected_solution.differentiation}")

        # Competitive advantages
        if hasattr(selected_solution, 'competitive_advantage') and selected_solution.competitive_advantage:
            features.append("\nCompetitive Advantages:")
            for advantage in selected_solution.competitive_advantage:
                features.append(f"  - {advantage}")

        return "\n".join(features) if features else "Features not detailed."

    def analyze(
        self,
        selected_solution,
        pain_point_analysis,
        competitive_analysis,
        niche_description: str,
        allowed_project_types: list[str] | None = None
    ) -> PricingStrategyResult | None:
        """
        Execute pricing strategy crew to generate pricing recommendations.

        Args:
            selected_solution: Selected solution from Stage 8.75 (SolutionIdea)
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            competitive_analysis: Competitive analysis from Stage 8 (CompetitiveAnalysisResult)
            niche_description: Niche description for context
            allowed_project_types: Optional project type constraints from user

        Returns:
            PricingStrategyResult with recommended pricing strategy, or None if analysis fails
        """
        logger.info("[Stage 8.7] Starting Pricing Strategy Validation...")
        logger.info(f"  Solution: {selected_solution.solution_name}")
        logger.info(f"  Analyzing competitor pricing and WTP scores...")

        # Extract data for task inputs
        competitor_pricing = self._extract_competitor_pricing(competitive_analysis, selected_solution.solution_name)
        wtp_scores = self._extract_wtp_scores(pain_point_analysis)
        solution_features = self._format_solution_features(selected_solution)

        # Pre-compute deterministic values
        wtp_summary, avg_wtp = compute_wtp_summary(pain_point_analysis)
        mfs = selected_solution.market_fit_score if hasattr(selected_solution, 'market_fit_score') else None
        suggested_cac_range = compute_cac_range(mfs)

        # Prepare inputs for the pricing analysis task
        inputs = {
            "solution_name": selected_solution.solution_name,
            "solution_description": selected_solution.description,
            "solution_features": solution_features,
            "competitor_pricing": competitor_pricing,
            "wtp_scores": wtp_scores,
            "niche_description": niche_description,
            "market_fit_score": f"{selected_solution.market_fit_score:.2f}",
            "allowed_project_types": ', '.join(allowed_project_types) if allowed_project_types else "All types allowed",
            "wtp_summary": wtp_summary,
            "avg_wtp": avg_wtp,
            "suggested_cac_range": suggested_cac_range,
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                pricing_result = result.pydantic
                logger.info("[Stage 8.7] Pricing Strategy Validation Complete")
                logger.info(f"  Recommended Starter: {pricing_result.recommended_starter_price}")
                logger.info(f"  Recommended Pro: {pricing_result.recommended_pro_price}")
                logger.info(f"  Estimated ARPU: {pricing_result.estimated_arpu}")
                logger.info(f"  Pricing Confidence: {pricing_result.pricing_confidence}")
                return pricing_result
            else:
                logger.error("[Stage 8.7] Pricing analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8.7] Pricing analysis error: {str(e)}")
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
