"""
Pricing Strategy Validation Crew (Stage 7).

Validates monetization strategy by determining optimal pricing based on:
- Competitor pricing benchmarks
- Pain point willingness-to-pay (WTP) scores
- Selected solution features and positioning
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..utils.content_security import prompt_field
from ..utils.llm_service import build_crew_llm
from ..utils.market_brief import parse_market_wallet_line
from ..utils.niche_difficulty import (
    ZERO_PRICE_PRICING_MODELS,
    has_zero_price_prescription,
    wallet_reading_shows_verified_prices,
    zero_price_model_contradicts_wallet,
)
from ..utils.validation.crew_guardrails import validate_pricing_strategy
from ..models.competitor import find_landscape_for_solution
from ..models.research_state import PricingStrategyResult
from ..utils.crew_helpers import (
    compute_wtp_summary,
    compute_cac_range,
    format_idea_cac,
    format_market_sizing_summary,
    format_audience_budget_sensitivity,
    format_solution_rank_context,
)


@CrewBase
class PricingStrategyCrew:
    """
    Crew for validating pricing strategy in Stage 7.

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
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.3,  # Low temperature for consistent pricing analysis (ignored for reasoning models)
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
        return SafeTask(
            config=self.tasks_config["pricing_strategy_analysis"],
            agent=self.pricing_analyst(),
            output_pydantic=PricingStrategyResult,
            guardrail=self._pricing_guardrail,
            guardrail_max_retries=2,
        )

    def _pricing_guardrail(self, task_output):
        """Bound guardrail wrapper: passes the pre-computed CAC anchor (set in
        analyze()) so the numeric ratio cross-check can run, then applies the wallet contract."""
        ok, payload = validate_pricing_strategy(
            task_output,
            suggested_cac_range=getattr(self, '_suggested_cac_range', None),
        )
        if not ok:
            return (ok, payload)
        return self._wallet_contract_guardrail(task_output, payload)

    def _wallet_contract_guardrail(self, task_output, payload):
        """Reject a zero-price `pricing_model` OR `pricing_rationale` in a niche whose prices
        this run VERIFIED.

        Stage 7 is where the report NAMES the money model, and until D1 round 16 nothing validated
        that field against the wallet: the prompt gates could be tightened indefinitely and the
        crew could still return `Ad-Supported-Free` in the same report that quotes the incumbents'
        monthly prices. Rejecting here (rather than after kickoff) is what gives the model a fresh
        call to correct itself — a guardrail cannot repair output, only refuse it.
        """
        wallet_class, wallet_evidence = getattr(self, "_wallet_reading", ("", ""))
        candidate = getattr(task_output, "pydantic", None) or payload
        reason = self._wallet_contract_violation(
            self._pricing_model_of(task_output, payload),
            getattr(candidate, "pricing_rationale", None),
            wallet_class,
            wallet_evidence,
        )
        if reason is None:
            return (True, payload)
        logger.warning(f"[Stage 7] rejecting pricing output: {reason}")
        return (False, reason)

    @staticmethod
    def _wallet_contract_violation(
        pricing_model: str | None,
        pricing_rationale: str | None,
        wallet_class: str,
        wallet_evidence: str,
    ) -> str | None:
        """The reason this pricing output contradicts the niche's verified wallet, or None.

        Two report-visible money outputs, one reading. `pricing_model` is a closed `Literal`, so
        it is checked as a value; `pricing_rationale` is the prose paragraph rendered under it,
        and nothing scanned it at all — a run could be forced onto `Freemium` by the field
        contract and still tell the reader, in the paragraph right beneath, to give the product
        away. Both use the polarity-blind detector's own question: does this RECOMMEND a shape in
        which this audience does not pay?
        """
        if zero_price_model_contradicts_wallet(pricing_model, wallet_class, wallet_evidence):
            return (
                f"pricing_model '{pricing_model}' puts the price at zero for this audience, but "
                f"this niche's wallet reading is '{wallet_class}' with verified prices "
                f"({wallet_evidence!r}). Somebody in this market pays today, so a zero-price "
                "model contradicts the report's own evidence. Choose a model with a price on at "
                "least one tier and justify it against those verified prices; if traffic "
                "monetization genuinely belongs alongside the paid tier, use Hybrid."
            )
        rationale = pricing_rationale if isinstance(pricing_rationale, str) else ""
        # THE TWO HALVES MUST AGREE. The field half permits every model that keeps a price on some
        # tier — `Freemium` above all — so the paragraph beneath it is allowed to say "free tier"
        # and the prose half must not reject the prose form of the choice the field form passed.
        # Where the model is field-permitted, only a rationale that RULES OUT the audience paying
        # ("a free tool funded by affiliate links rather than a monthly subscription") contradicts
        # anything; a bare zero-price object does not. Without this the modal legitimate outcome —
        # a priced model whose paragraph mentions its own free tier — was refused, `analyze()`
        # returned None, and the solution silently lost its pricing section.
        field_gate_permits_the_model = (
            (pricing_model or "").strip() not in ZERO_PRICE_PRICING_MODELS
        )
        if (
            rationale.strip()
            and wallet_reading_shows_verified_prices(wallet_class, wallet_evidence)
            and has_zero_price_prescription(
                rationale, rejection_only=field_gate_permits_the_model
            )
        ):
            return (
                "pricing_rationale recommends a shape in which this audience does not pay, but "
                f"this niche's wallet reading is '{wallet_class}' with verified prices "
                f"({wallet_evidence!r}). The paragraph is rendered to the reader directly under "
                "the pricing model, so it contradicts the report's own evidence just as the "
                "field would. Justify the priced model against those verified prices instead: "
                f"{prompt_field(rationale)!r}"
            )
        return None

    @staticmethod
    def _pricing_model_of(task_output, payload) -> str:
        """The chosen `pricing_model`, wherever this guardrail's predecessor left it.

        `validate_pricing_strategy` hands back the raw payload it was given on success, so the
        parsed object is read from the task output first and the payload only as a fallback.
        """
        for candidate in (getattr(task_output, "pydantic", None), payload):
            model = getattr(candidate, "pricing_model", None)
            if isinstance(model, str) and model.strip():
                return model.strip()
        return ""

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

        # Find the landscape for the selected solution (case-insensitive, with fallback)
        landscape = find_landscape_for_solution(competitive_analysis, selected_solution_name)
        if not landscape:
            return "No competitor pricing data available."

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
                pricing_str += f" ({prompt_field(competitor.description)})"

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

            if hasattr(pain_point, 'commercial_intent'):
                wtp_str += f" - WTP Score: {pain_point.commercial_intent:.2f}"

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

    def _extract_competitive_context(self, competitive_analysis, solution_name: str) -> str:
        """
        Extract competitive intensity and market gaps from competitive landscape.

        Returns:
            Formatted string with competitive intensity + market gaps
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "Competitive context not available"

        landscape = None
        for l in competitive_analysis.solution_landscapes:
            if solution_name and l.solution_name == solution_name:
                landscape = l
                break
        if not landscape:
            landscape = competitive_analysis.solution_landscapes[0]

        parts: list[str] = []
        if landscape.competitive_intensity:
            parts.append(f"Intensity: {landscape.competitive_intensity}")
        if landscape.market_gaps:
            gaps = "; ".join(landscape.market_gaps[:5])
            parts.append(f"Market Gaps: {gaps}")

        return " | ".join(parts) if parts else "Competitive context not available"

    def _format_target_personas(self, selected_solution) -> str:
        """
        Format solution target_personas list for template injection.

        Returns:
            Formatted bullet list or fallback text
        """
        personas = getattr(selected_solution, "target_personas", None)
        if not personas:
            return "Target personas not specified"
        return "\n".join(f"- {p}" for p in personas)

    def analyze(
        self,
        selected_solution,
        pain_point_analysis,
        competitive_analysis,
        niche_description: str,
        allowed_project_types: list[str] | None = None,
        market_sizing=None,
        audience_mapping=None,
        solution_scores: list | None = None,
        market_brief: str = "",
        market_incumbent_table: str = "",
        market_wallet_line: str = "",
    ) -> PricingStrategyResult | None:
        """
        Execute pricing strategy crew to generate pricing recommendations.

        Args:
            selected_solution: Selected solution from Stage 75 (SolutionIdea)
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            competitive_analysis: Competitive analysis from Stage 8 (CompetitiveAnalysisResult)
            niche_description: Niche description for context
            allowed_project_types: Optional project type constraints from user
            market_sizing: Optional market sizing result from Stage 9
            audience_mapping: Optional audience mapping result from Stage 6.5
            solution_scores: Optional list of SolutionScores from keyword validation
            market_brief: Phase-1 web-verified parity findings + substitute-pressure context
                (utils/market_brief.py); '' when unavailable => no-op interpolation.
            market_incumbent_table: Phase-1 web-verified incumbent pricing rows; '' when unavailable.
            market_wallet_line: Phase-1 niche wallet-class signal; '' when unavailable.

        Returns:
            PricingStrategyResult with recommended pricing strategy, or None if analysis fails
        """
        logger.info("[Stage 7] Starting Pricing Strategy Validation...")
        logger.info(f"  Solution: {selected_solution.solution_name}")
        logger.info("  Analyzing competitor pricing and WTP scores...")

        # Extract data for task inputs
        competitor_pricing = self._extract_competitor_pricing(competitive_analysis, selected_solution.solution_name)
        wtp_scores = self._extract_wtp_scores(pain_point_analysis)
        solution_features = self._format_solution_features(selected_solution)

        # Pre-compute deterministic values
        wtp_summary, avg_wtp = compute_wtp_summary(pain_point_analysis)
        mfs = selected_solution.market_fit_score if hasattr(selected_solution, 'market_fit_score') else None
        suggested_cac_range = compute_cac_range(mfs)
        self._suggested_cac_range = suggested_cac_range  # for the guardrail's ratio cross-check
        # The wallet reading the guardrail validates `pricing_model` against. Parsed back out of
        # the rendered line because that string is the only form of the reading this crew is given.
        self._wallet_reading = parse_market_wallet_line(market_wallet_line)

        # The idea's OWN CAC — the only value ltv_to_cac_ratio may divide by. Blank on a
        # rebuilt idea by design (unified_solution_crew._UNGROUNDABLE_ON_REBUILD); the task
        # YAML then requires "Not computable" rather than a ratio built on the market-fit
        # benchmark band above (the 2026-08 8ef396eb defect).
        idea_cac_estimate = format_idea_cac(selected_solution)

        # New data formatting
        project_type = getattr(selected_solution, "project_type", None) or "Not specified"
        value_proposition = getattr(selected_solution, "value_proposition", None) or "Not specified"
        target_personas = self._format_target_personas(selected_solution)
        competitive_intensity = self._extract_competitive_context(competitive_analysis, selected_solution.solution_name)
        market_sizing_summary = format_market_sizing_summary(market_sizing)
        audience_budget_sensitivity = format_audience_budget_sensitivity(audience_mapping)
        solution_rank_context = format_solution_rank_context(solution_scores, selected_solution.solution_name)

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
            "idea_cac_estimate": idea_cac_estimate,
            # New template variables
            "project_type": project_type,
            "value_proposition": value_proposition,
            "target_personas": target_personas,
            "competitive_intensity": competitive_intensity,
            "market_sizing_summary": market_sizing_summary,
            "audience_budget_sensitivity": audience_budget_sensitivity,
            "solution_rank_context": solution_rank_context,
            # Market-data handoff (utils/market_brief.py): Phase-1 web-verified parity findings +
            # incumbent pricing rows + niche wallet signal. Empty strings when unavailable => no-op.
            "market_brief": market_brief,
            "market_incumbent_table": market_incumbent_table,
            "market_wallet_line": market_wallet_line,
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                pricing_result = result.pydantic
                wallet_class, wallet_evidence = self._wallet_reading
                violation = self._wallet_contract_violation(
                    getattr(pricing_result, "pricing_model", None),
                    getattr(pricing_result, "pricing_rationale", None),
                    wallet_class,
                    wallet_evidence,
                )
                if violation:
                    # The guardrail above refuses this and retries; reaching here means the
                    # retries were exhausted or the guardrail was bypassed. Publishing it would
                    # put "free forever" in the same report as the market's own price list, so
                    # Stage 7 is dropped instead. A missing pricing section is recoverable; a
                    # report that contradicts itself about money is the finding.
                    logger.error(
                        f"[Stage 7] discarding the pricing result rather than publishing the "
                        f"contradiction: {violation}"
                    )
                    return None
                logger.info("[Stage 7] Pricing Strategy Validation Complete")
                logger.info(f"  Recommended Starter: {pricing_result.recommended_starter_price}")
                logger.info(f"  Recommended Pro: {pricing_result.recommended_pro_price}")
                logger.info(f"  Estimated ARPU: {pricing_result.estimated_arpu}")
                logger.info(f"  Pricing Confidence: {pricing_result.pricing_confidence}")
                return pricing_result
            else:
                logger.error("[Stage 7] Pricing analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 7] Pricing analysis error: {str(e)}")
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
