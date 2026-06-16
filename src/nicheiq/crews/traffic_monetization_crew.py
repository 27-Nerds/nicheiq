"""
Traffic Monetization Crew (Stage 8).

For directories, aggregators, and comparison tools that monetize via
traffic (ads, affiliates) rather than subscriptions.

Routes from research_flow.py when:
    project_type in ['directory', 'aggregator', 'comparison-tool']
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_llm_kwargs
from ..models.research_state import TrafficMonetizationResult
from ..utils.validation.crew_guardrails import validate_traffic_monetization
from ..utils.crew_helpers import (
    collect_all_tiered_keywords,
    compute_ad_revenue_estimate,
    compute_affiliate_revenue_estimate,
    compute_commercial_intent_ratio,
    compute_intent_breakdown,
    compute_seo_traffic_enrichment,
    compute_total_revenue_estimate,
    compute_traffic_projection,
    match_niche_to_cpm,
)


@CrewBase
class TrafficMonetizationCrew:
    """
    Crew for analyzing traffic-based monetization strategies.

    Used for project types: directory, aggregator, comparison-tool

    Analyzes:
    - Traffic potential from keyword search volumes
    - Display ad revenue (CPM/RPM by niche)
    - Affiliate program opportunities
    - Sponsored listing/lead gen potential (B2B)

    Outputs:
    - Traffic projections (monthly pageviews)
    - Ad revenue estimates (CPM, networks)
    - Affiliate revenue estimates (programs, commissions)
    - B2B monetization options (sponsored, lead gen)
    - Total revenue projection with scaling strategy
    """

    agents_config = "config/traffic_monetization_agents.yaml"
    tasks_config = "config/traffic_monetization_tasks.yaml"

    def __init__(self):
        """Initialize TrafficMonetizationCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def traffic_monetization_analyst(self) -> Agent:
        """
        Traffic Monetization Analyst agent.

        Specializes in publisher revenue, display ads, affiliate marketing,
        and traffic-based monetization strategies.
        """
        return Agent(
            config=self.agents_config["traffic_monetization_analyst"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.openai_model_name,
                temperature=0.4,  # Balanced for creative revenue suggestions (ignored for reasoning models)
            )),
            verbose=True,
        )

    @task
    def traffic_monetization_analysis_task(self) -> Task:
        """
        Main traffic monetization analysis task.

        Analyzes keyword volumes, niche CPM rates, and affiliate opportunities
        to recommend optimal traffic monetization strategy.
        """
        return SafeTask(
            config=self.tasks_config["traffic_monetization_analysis"],
            agent=self.traffic_monetization_analyst(),
            output_pydantic=TrafficMonetizationResult,
            guardrail=self._traffic_guardrail,
            guardrail_max_retries=2,
        )

    def _traffic_guardrail(self, task_output):
        """Bound guardrail wrapper: passes the evidence-based traffic ceiling
        (set in analyze() when SEO data exists) so pageview claims are clamped."""
        return validate_traffic_monetization(
            task_output,
            traffic_ceiling_y1_high=getattr(self, '_seo_traffic_ceiling_y1_high', None),
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the traffic monetization crew.

        Single-agent, single-task crew optimized for traffic monetization analysis.
        """
        return Crew(
            agents=[self.traffic_monetization_analyst()],
            tasks=[self.traffic_monetization_analysis_task()],
            verbose=True,
        )

    def _format_keyword_data(self, keyword_validation_results, solution_name: str, seo_strategy_report=None) -> str:
        """
        Format keyword data for traffic estimation.

        Prefers SEO strategy report data when available (comprehensive).
        Falls back to keyword_validation_results for backward compatibility.

        Args:
            keyword_validation_results: List of CrewKeywordValidationResult (may be None)
            solution_name: Name of solution to find keyword data for
            seo_strategy_report: Optional SEOStrategyReport with comprehensive keyword data

        Returns:
            Formatted string with keyword volumes and metrics
        """
        # Primary path: use SEO strategy report
        if seo_strategy_report:
            all_keywords = []
            for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
                tier_kws = getattr(seo_strategy_report, tier_attr, None) or []
                all_keywords.extend(tier_kws)

            total_volume = seo_strategy_report.total_monthly_volume or 0
            keyword_count = seo_strategy_report.total_keywords_analyzed or 0

            if total_volume >= 5000:
                demand_signal = "strong"
            elif total_volume >= 2000:
                demand_signal = "moderate"
            else:
                demand_signal = "weak"

            lines = [
                f"**Total Search Volume:** {total_volume:,} searches/month (SEO strategy data)",
                f"**Analyzed Keywords:** {keyword_count}",
                f"**Demand Signal:** {demand_signal}",
                "",
                "**Top Keywords by Volume:**"
            ]

            top_keywords = sorted(all_keywords, key=lambda k: k.search_volume, reverse=True)[:15]
            for kw in top_keywords:
                lines.append(f"  - {kw.keyword}: {kw.search_volume:,}/month")

            if all_keywords:
                volumes = [kw.search_volume for kw in all_keywords]
                avg_volume = sum(volumes) / len(volumes) if volumes else 0
                high_volume_count = len([v for v in volumes if v >= 1000])
                lines.append("")
                lines.append(f"**Distribution:** {high_volume_count} high-volume keywords (1,000+/month), avg volume: {avg_volume:,.0f}")

            return "\n".join(lines)

        # Fallback: use keyword validation results
        if not keyword_validation_results:
            return "No keyword data available."

        for validation in keyword_validation_results:
            if validation.solution_name == solution_name:
                lines = [
                    f"**Total Search Volume:** {validation.total_volume:,} searches/month",
                    f"**Validated Keywords:** {validation.validated_count}",
                    f"**Demand Signal:** {validation.demand_signal}",
                    "",
                    "**Top Keywords by Volume:**"
                ]

                top_keywords = sorted(
                    validation.top_keywords,
                    key=lambda x: x.get('volume', 0),
                    reverse=True
                )[:15]

                for kw in top_keywords:
                    keyword = kw.get('keyword', 'N/A')
                    volume = kw.get('volume', 0)
                    lines.append(f"  - {keyword}: {volume:,}/month")

                if validation.top_keywords:
                    volumes = [kw.get('volume', 0) for kw in validation.top_keywords]
                    avg_volume = sum(volumes) / len(volumes) if volumes else 0
                    high_volume_count = len([v for v in volumes if v >= 1000])
                    lines.append("")
                    lines.append(f"**Distribution:** {high_volume_count} high-volume keywords (1,000+/month), avg volume: {avg_volume:,.0f}")

                return "\n".join(lines)

        return f"No keyword data found for solution: {solution_name}"

    def _format_competitor_analysis(self, competitive_analysis, solution_name: str) -> str:
        """
        Extract competitor monetization strategies.

        Args:
            competitive_analysis: CompetitiveAnalysisResult from Stage 7.2
            solution_name: Name of solution to find competitors for

        Returns:
            Formatted string with competitor monetization data
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitor data available."

        # Find landscape for this solution
        for landscape in competitive_analysis.solution_landscapes:
            if landscape.solution_name == solution_name:
                lines = ["**Competitor Monetization Strategies:**"]

                for comp in (landscape.competitors or [])[:8]:
                    comp_name = comp.name
                    pricing_model = comp.pricing_model or "Unknown"
                    comp_type = getattr(comp, 'competitor_type', 'N/A')

                    lines.append(f"  - {comp_name} ({comp_type}): {pricing_model}")

                    # Add description if available
                    if comp.description:
                        desc = comp.description[:100] + "..." if len(comp.description) > 100 else comp.description
                        lines.append(f"    Description: {desc}")

                # Add pricing insights from landscape
                if hasattr(landscape, 'pricing_insights') and landscape.pricing_insights:
                    lines.append("")
                    lines.append(f"**Pricing Insights:** {landscape.pricing_insights}")

                # Add market gaps
                if hasattr(landscape, 'market_gaps') and landscape.market_gaps:
                    lines.append("")
                    lines.append("**Market Gaps:**")
                    for gap in landscape.market_gaps[:3]:
                        lines.append(f"  - {gap}")

                return "\n".join(lines)

        return f"No competitor landscape found for solution: {solution_name}"

    def analyze(
        self,
        selected_solution,
        keyword_validation_results,
        competitive_analysis,
        niche_description: str,
        seo_strategy_report=None
    ) -> TrafficMonetizationResult | None:
        """
        Execute traffic monetization analysis.

        Args:
            selected_solution: SolutionIdea with project_type in [directory, aggregator, comparison-tool]
            keyword_validation_results: List of CrewKeywordValidationResult from keyword validation
            competitive_analysis: CompetitiveAnalysisResult from Stage 7.2
            niche_description: Niche description for context
            seo_strategy_report: Optional SEOStrategyReport for enriched traffic data

        Returns:
            TrafficMonetizationResult with traffic-based monetization strategy, or None if analysis fails
        """
        logger.info("[Stage 8] Starting Traffic Monetization Analysis...")
        logger.info(f"  Solution: {selected_solution.solution_name}")
        logger.info(f"  Project Type: {selected_solution.project_type}")
        logger.info(f"  Analyzing traffic potential and monetization channels...")

        # Format keyword data for traffic estimation
        keyword_data = self._format_keyword_data(
            keyword_validation_results,
            selected_solution.solution_name,
            seo_strategy_report=seo_strategy_report
        )
        logger.debug(f"  Keyword data formatted: {len(keyword_data)} chars")

        # Format competitor analysis
        competitor_info = self._format_competitor_analysis(
            competitive_analysis,
            selected_solution.solution_name
        )
        logger.debug(f"  Competitor info formatted: {len(competitor_info)} chars")

        # Pre-compute deterministic traffic and monetization values
        # Prefer SEO strategy report volume (comprehensive) over keyword validation
        total_volume = 0
        if seo_strategy_report:
            total_volume = seo_strategy_report.total_monthly_volume or 0
        elif keyword_validation_results:
            for validation in keyword_validation_results:
                if validation.solution_name == selected_solution.solution_name:
                    total_volume = validation.total_volume or 0
                    break

        traffic_projection, total_low, total_high = compute_traffic_projection(
            total_volume, seo_strategy_report=seo_strategy_report
        )
        cpm_low, cpm_high, cpm_vertical = match_niche_to_cpm(niche_description)
        suggested_cpm = f"${cpm_low}-${cpm_high} CPM ({cpm_vertical} vertical)"
        ad_revenue_estimate = compute_ad_revenue_estimate(total_low, total_high, cpm_low, cpm_high)

        # Set unconditional defaults for all template variables FIRST
        seo_enrichment = ""
        seo_traffic_ceiling_y1 = "N/A (no SEO data)"
        seo_commercial_intent_pct = "N/A (no SEO data)"
        affiliate_revenue_estimate = ""
        total_revenue_estimate = ""

        # Override with real values if SEO data available
        if seo_strategy_report:
            seo_enrichment = compute_seo_traffic_enrichment(seo_strategy_report)
            logger.debug(f"  SEO enrichment added: {len(seo_enrichment)} chars")

            # Extract focused input keys from SEO data
            tier_1 = getattr(seo_strategy_report, "tier_1_keywords", None) or []
            tier_2 = getattr(seo_strategy_report, "tier_2_keywords", None) or []
            from ..utils.crew_helpers import compute_difficulty_weighted_traffic
            t1_low, t1_high = compute_difficulty_weighted_traffic(tier_1)
            t2_low, t2_high = compute_difficulty_weighted_traffic(tier_2)
            # Apply the SAME 1.25 content-compounding multiplier the report-time
            # projection uses — otherwise the final (code-overridden) numbers
            # exceed the ceiling the LLM was told to respect.
            compound = 1.25
            y1_low = int((t1_low + t2_low * 0.6) * compound)
            y1_high = int((t1_high + t2_high * 0.6) * compound)
            seo_traffic_ceiling_y1 = f"{y1_low:,}-{y1_high:,} visits/mo"
            self._seo_traffic_ceiling_y1_high = y1_high  # for the guardrail clamp

            all_keywords = collect_all_tiered_keywords(seo_strategy_report)
            intent = compute_intent_breakdown(all_keywords)
            commercial_pct = compute_commercial_intent_ratio(intent)
            seo_commercial_intent_pct = f"{commercial_pct:.0f}%"

            # Affiliate and total revenue estimates
            affiliate_revenue_estimate = compute_affiliate_revenue_estimate(
                intent, total_low, total_high, niche_description
            )
            # Parse ad revenue numbers for total
            ad_rev_low = int(total_low * cpm_low / 1000) if total_low > 0 else 0
            ad_rev_high = int(total_high * cpm_high / 1000) if total_high > 0 else 0
            # Parse affiliate revenue numbers
            aff_rev_low = 0
            aff_rev_high = 0
            if affiliate_revenue_estimate:
                import re as _re
                aff_match = _re.findall(r'\$([0-9,]+)', affiliate_revenue_estimate)
                if len(aff_match) >= 2:
                    aff_rev_low = int(aff_match[0].replace(',', ''))
                    aff_rev_high = int(aff_match[1].replace(',', ''))
            total_revenue_estimate = compute_total_revenue_estimate(
                ad_rev_low, ad_rev_high, aff_rev_low, aff_rev_high
            )

        # Prepare inputs for the task
        inputs = {
            "solution_name": selected_solution.solution_name,
            "project_type": selected_solution.project_type or "directory",
            "solution_description": selected_solution.description or "No description provided",
            "niche_description": niche_description,
            "keyword_data": keyword_data,
            "competitor_analysis": competitor_info,
            "traffic_projection": traffic_projection,
            "suggested_cpm": suggested_cpm,
            "ad_revenue_estimate": ad_revenue_estimate,
            "seo_enrichment": seo_enrichment,
            "seo_traffic_ceiling_y1": seo_traffic_ceiling_y1,
            "seo_commercial_intent_pct": seo_commercial_intent_pct,
            "affiliate_revenue_estimate": affiliate_revenue_estimate,
            "total_revenue_estimate": total_revenue_estimate,
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                traffic_result = result.pydantic
                logger.info("[Stage 8] Traffic Monetization Analysis Complete")
                logger.info(f"  Monetization Model: {traffic_result.monetization_model}")
                logger.info(f"  Est. Monthly Pageviews: {traffic_result.estimated_monthly_pageviews}")
                logger.info(f"  Est. Monthly Revenue: {traffic_result.estimated_monthly_revenue_range}")
                logger.info(f"  Confidence: {traffic_result.monetization_confidence}")
                return traffic_result
            else:
                logger.error("[Stage 8] Traffic monetization analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8] Traffic monetization analysis error: {str(e)}")
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
