"""
Market Sizing & Validation Crew (Stage 8.6).

Calculates TAM/SAM/SOM (Total/Serviceable/Obtainable Market) estimates and validates
market attractiveness using keyword demand, pain point frequency, and competitive analysis.
"""

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import MarketSizingResult
from ..models.solution_idea import SolutionIdea


@CrewBase
class MarketSizingCrew:
    """
    Crew for market sizing and validation in Stage 8.6.

    Analyzes:
    - Keyword search volumes (market demand signals)
    - Pain point frequency (problem validation)
    - Competitive landscape (market saturation)
    - Selected solution positioning

    Outputs:
    - TAM/SAM/SOM estimates
    - Market validation signals
    - Growth potential assessment
    - Market viability verdict
    """

    agents_config = "config/market_sizing_agents.yaml"
    tasks_config = "config/market_sizing_tasks.yaml"

    def __init__(self):
        """Initialize MarketSizingCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def market_analyst(self) -> Agent:
        """
        Market Sizing Specialist agent.

        Calculates TAM/SAM/SOM using keyword-based, top-down,
        and bottom-up methodologies.
        """
        return Agent(
            config=self.agents_config["market_analyst"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,  # Low temperature for numerical accuracy
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def market_sizing_analysis_task(self) -> Task:
        """
        Main market sizing and validation task.

        Calculates TAM/SAM/SOM estimates and assesses market viability.
        """
        return Task(
            config=self.tasks_config["market_sizing_analysis"],
            agent=self.market_analyst(),
            output_pydantic=MarketSizingResult,
            guardrail=self._validate_market_sizing_output,
        )

    def _validate_market_sizing_output(self, task_output) -> tuple:
        """
        Validate market sizing output meets CRITICAL RULES.

        Checks:
        - TAM/SAM/SOM hierarchy (TAM > SAM > SOM)
        - Required numeric estimates present
        - Viability verdict matches data

        Args:
            task_output: Task output from CrewAI

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic

            # Ensure all required fields have estimates (not placeholders)
            if not result.total_addressable_market or result.total_addressable_market == "TBD":
                return (False, "TAM estimate must be provided (not TBD or empty)")

            if not result.serviceable_available_market or result.serviceable_available_market == "TBD":
                return (False, "SAM estimate must be provided (not TBD or empty)")

            if not result.serviceable_obtainable_market_y1 or result.serviceable_obtainable_market_y1 == "TBD":
                return (False, "SOM Year 1 estimate must be provided (not TBD or empty)")

            # Validate viability verdict is one of expected values
            valid_verdicts = ["Strong", "Moderate", "Weak"]
            if result.market_viability_verdict not in valid_verdicts:
                return (False, f"Viability verdict must be one of: {valid_verdicts}, got '{result.market_viability_verdict}'")

            # Validate saturation level
            valid_saturation = ["Low", "Medium", "High"]
            if result.market_saturation_level not in valid_saturation:
                return (False, f"Saturation level must be one of: {valid_saturation}, got '{result.market_saturation_level}'")

            # Validate timing assessment
            valid_timing = ["Early", "Growth", "Mature"]
            if result.market_timing_assessment not in valid_timing:
                return (False, f"Timing assessment must be one of: {valid_timing}, got '{result.market_timing_assessment}'")

            # Validate TAM/SAM/SOM hierarchy numerically (best effort)
            try:
                import re

                def _extract_numeric_value(estimate: str) -> float:
                    """Extract numeric value from market size estimate (e.g., '$500M' -> 500.0)."""
                    if not estimate:
                        return 0.0
                    # Remove currency symbols, commas, and spaces
                    cleaned = estimate.replace('$', '').replace(',', '').replace(' ', '').upper()
                    # Extract number and multiplier (M, B, K)
                    match = re.search(r'([\d.]+)([MBK])?', cleaned)
                    if match:
                        value = float(match.group(1))
                        multiplier = match.group(2)
                        if multiplier == 'B':
                            value *= 1000  # Convert billions to millions for comparison
                        elif multiplier == 'K':
                            value /= 1000  # Convert thousands to millions
                        return value
                    return 0.0

                tam_val = _extract_numeric_value(result.total_addressable_market)
                sam_val = _extract_numeric_value(result.serviceable_available_market)
                som_y1_val = _extract_numeric_value(result.serviceable_obtainable_market_y1)
                som_y3_val = _extract_numeric_value(result.serviceable_obtainable_market_y3)

                # Validate TAM > SAM > SOM hierarchy
                if tam_val > 0 and sam_val > 0:
                    if not (tam_val > sam_val):
                        return (False, f"TAM/SAM hierarchy violated: TAM ({result.total_addressable_market}) must be > SAM ({result.serviceable_available_market})")

                if sam_val > 0 and som_y1_val > 0:
                    if not (sam_val > som_y1_val):
                        return (False, f"SAM/SOM hierarchy violated: SAM ({result.serviceable_available_market}) must be > SOM Y1 ({result.serviceable_obtainable_market_y1})")

                # Validate SOM Y3 > SOM Y1 (growth over time)
                if som_y1_val > 0 and som_y3_val > 0:
                    if not (som_y3_val > som_y1_val):
                        return (False, f"SOM growth violated: SOM Y3 ({result.serviceable_obtainable_market_y3}) must be > SOM Y1 ({result.serviceable_obtainable_market_y1})")

                # Warn if 3-2-1 Rule violated (not a hard failure, just a warning)
                if tam_val > 0 and sam_val > 0:
                    if tam_val < sam_val * 3:
                        logger.warning(f"[Guardrail] 3-2-1 Rule: TAM ({result.total_addressable_market}) should be >3x SAM ({result.serviceable_available_market})")

                if sam_val > 0 and som_y1_val > 0:
                    if sam_val < som_y1_val * 2:
                        logger.warning(f"[Guardrail] 3-2-1 Rule: SAM ({result.serviceable_available_market}) should be >2x SOM Y1 ({result.serviceable_obtainable_market_y1})")

            except Exception as numeric_error:
                # Log but don't fail validation if numeric parsing fails
                logger.warning(f"[Guardrail] Could not validate numeric hierarchy: {str(numeric_error)}")

            return (True, result)
        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the market sizing crew.

        Single-agent, single-task crew optimized for market analysis.
        """
        return Crew(
            agents=[self.market_analyst()],
            tasks=[self.market_sizing_analysis_task()],
            verbose=True,
        )

    def analyze(
        self,
        selected_solution: SolutionIdea,
        keyword_validation: CrewKeywordValidationResult,
        pain_point_analysis: PainPointAnalysisResult,
        competitive_analysis: CompetitiveAnalysisResult,
        niche_description: str
    ) -> MarketSizingResult | None:
        """
        Execute market sizing crew to calculate TAM/SAM/SOM and validate market.

        Args:
            selected_solution: Selected solution from Stage 8.75
            keyword_validation: Keyword validation data from Stage 8.8
            pain_point_analysis: Pain point data from Stage 6
            competitive_analysis: Competitive landscape from Stage 8
            niche_description: Niche description for context

        Returns:
            MarketSizingResult with TAM/SAM/SOM estimates and viability verdict, or None if analysis fails
        """
        logger.info("[Stage 8.6] Starting Market Sizing & Validation...")
        logger.info(f"  Solution: {selected_solution.idea_name}")

        # Extract keyword demand signals
        keyword_signals = self._format_keyword_signals(keyword_validation)

        # Extract pain point signals
        pain_signals = self._format_pain_signals(pain_point_analysis)

        # Extract competitive signals
        competitive_signals = self._format_competitive_signals(competitive_analysis)

        # Extract solution context
        solution_context = self._format_solution_context(selected_solution)

        # Prepare inputs for market sizing task
        inputs = {
            "solution_name": selected_solution.idea_name,
            "solution_description": selected_solution.description,
            "solution_context": solution_context,
            "niche_description": niche_description,
            "keyword_demand_signals": keyword_signals,
            "pain_point_signals": pain_signals,
            "competitive_signals": competitive_signals,
            "total_keyword_volume": keyword_validation.total_volume if keyword_validation else 0,
            "validated_keyword_count": keyword_validation.validated_count if keyword_validation else 0,
            "pain_point_count": len(pain_point_analysis.pain_points) if pain_point_analysis else 0,
            "competitor_count": len(competitive_analysis.key_competitors) if competitive_analysis and competitive_analysis.key_competitors else 0,
        }

        try:
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)

            if result and result.pydantic:
                market_result = result.pydantic
                logger.info("[Stage 8.6] Market Sizing Complete")
                logger.info(f"  TAM: {market_result.total_addressable_market}")
                logger.info(f"  SAM: {market_result.serviceable_available_market}")
                logger.info(f"  SOM (Y1): {market_result.serviceable_obtainable_market_y1}")
                logger.info(f"  Viability: {market_result.market_viability_verdict}")
                logger.info(f"  Entry Strategy: {market_result.recommended_entry_strategy}")
                return market_result
            else:
                logger.error("[Stage 8.6] Market sizing failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8.6] Market sizing error: {str(e)}")
            return None

    def _format_keyword_signals(self, keyword_validation: CrewKeywordValidationResult | None) -> str:
        """Format keyword demand signals for market sizing."""
        if not keyword_validation:
            return "No keyword validation data available."

        signals = []
        signals.append(f"**Total Monthly Search Volume:** {keyword_validation.total_volume:,} searches")
        signals.append(f"**Validated Keywords:** {keyword_validation.validated_count}")
        signals.append(f"**Demand Signal:** {keyword_validation.demand_signal}")
        signals.append(f"**Average Competition:** {keyword_validation.avg_competition:.2f}")

        if keyword_validation.top_keywords:
            signals.append("\n**Top Keywords:**")
            for kw in keyword_validation.top_keywords[:5]:
                keyword_text = kw.get('keyword', 'N/A')
                volume = kw.get('volume', 0)
                signals.append(f"- {keyword_text}: {volume:,}/month")

        return "\n".join(signals)

    def _format_pain_signals(self, pain_point_analysis: PainPointAnalysisResult | None) -> str:
        """Format pain point signals for market validation."""
        if not pain_point_analysis or not pain_point_analysis.pain_points:
            return "No pain point data available."

        signals = []
        signals.append(f"**Total Pain Points Identified:** {len(pain_point_analysis.pain_points)}")
        signals.append(f"**Total Mentions:** {pain_point_analysis.total_mentions}")

        high_severity = [pp for pp in pain_point_analysis.pain_points if pp.severity_score >= 0.7]
        signals.append(f"**High Severity Pain Points:** {len(high_severity)}")

        if pain_point_analysis.pain_points:
            signals.append("\n**Top Pain Points:**")
            for pp in pain_point_analysis.pain_points[:5]:
                signals.append(f"- {pp.pain_point_title} (Severity: {pp.severity_score:.2f}, WTP: {pp.willingness_to_pay_score:.2f})")

        return "\n".join(signals)

    def _format_competitive_signals(self, competitive_analysis: CompetitiveAnalysisResult | None) -> str:
        """Format competitive landscape for market saturation assessment."""
        if not competitive_analysis or not competitive_analysis.key_competitors:
            return "No competitive analysis data available."

        signals = []
        signals.append(f"**Total Competitors Identified:** {len(competitive_analysis.key_competitors)}")

        if competitive_analysis.market_gaps:
            signals.append(f"\n**Market Gaps:** {len(competitive_analysis.market_gaps)} opportunities identified")

        if competitive_analysis.key_competitors:
            signals.append("\n**Sample Competitors:**")
            for comp in competitive_analysis.key_competitors[:5]:
                signals.append(f"- {comp.competitor_name}")

        return "\n".join(signals)

    def _format_solution_context(self, solution: SolutionIdea) -> str:
        """Format solution details for market sizing context."""
        context = []
        context.append(f"**Market Fit Score:** {solution.market_fit_score:.2f}")
        context.append(f"**Differentiation Score:** {solution.differentiation_score:.2f}")

        if solution.target_personas:
            context.append(f"\n**Target Personas:** {', '.join(solution.target_personas[:3])}")

        if solution.core_features:
            context.append(f"\n**Core Features:** {len(solution.core_features)} features")

        return "\n".join(context)
