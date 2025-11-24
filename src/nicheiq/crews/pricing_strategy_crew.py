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
from ..models.research_state import PricingStrategyResult


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
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,  # Low temperature for consistent pricing analysis
                api_key=settings.openai_api_key
            ),
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

    def _extract_competitor_pricing(self, competitive_analysis) -> str:
        """
        Extract competitor pricing information from competitive analysis.

        Returns:
            Formatted string with competitor pricing data
        """
        if not competitive_analysis or not competitive_analysis.key_competitors:
            return "No competitor pricing data available."

        pricing_info = []
        for competitor in competitive_analysis.key_competitors[:10]:  # Top 10
            pricing_str = f"- {competitor.competitor_name}"

            # Add positioning
            if hasattr(competitor, 'positioning') and competitor.positioning:
                pricing_str += f" ({competitor.positioning})"

            # Add pricing if available
            if hasattr(competitor, 'pricing_model') and competitor.pricing_model:
                pricing_str += f": {competitor.pricing_model}"

            # Add estimated pricing tiers
            if hasattr(competitor, 'estimated_pricing') and competitor.estimated_pricing:
                pricing_str += f" - {competitor.estimated_pricing}"

            pricing_info.append(pricing_str)

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
            wtp_str = f"- {pain_point.pain_point_title}"

            if hasattr(pain_point, 'severity_score'):
                wtp_str += f" (Severity: {pain_point.severity_score:.2f})"

            if hasattr(pain_point, 'willingness_to_pay_score'):
                wtp_str += f" - WTP Score: {pain_point.willingness_to_pay_score:.2f}"

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
        niche_description: str
    ) -> PricingStrategyResult | None:
        """
        Execute pricing strategy crew to generate pricing recommendations.

        Args:
            selected_solution: Selected solution from Stage 8.75 (SolutionIdea)
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            competitive_analysis: Competitive analysis from Stage 8 (CompetitiveAnalysisResult)
            niche_description: Niche description for context

        Returns:
            PricingStrategyResult with recommended pricing strategy, or None if analysis fails
        """
        logger.info("[Stage 8.7] Starting Pricing Strategy Validation...")
        logger.info(f"  Solution: {selected_solution.idea_name}")
        logger.info(f"  Analyzing competitor pricing and WTP scores...")

        # Extract data for task inputs
        competitor_pricing = self._extract_competitor_pricing(competitive_analysis)
        wtp_scores = self._extract_wtp_scores(pain_point_analysis)
        solution_features = self._format_solution_features(selected_solution)

        # Prepare inputs for the pricing analysis task
        inputs = {
            "solution_name": selected_solution.idea_name,
            "solution_description": selected_solution.description,
            "solution_features": solution_features,
            "competitor_pricing": competitor_pricing,
            "wtp_scores": wtp_scores,
            "niche_description": niche_description,
            "market_fit_score": f"{selected_solution.market_fit_score:.2f}",
            "differentiation_score": f"{selected_solution.differentiation_score:.2f}"
        }

        try:
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)

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
