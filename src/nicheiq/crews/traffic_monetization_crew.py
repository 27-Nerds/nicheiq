"""
Traffic Monetization Crew (Stage 8.55).

For directories, aggregators, and comparison tools that monetize via
traffic (ads, affiliates) rather than subscriptions.

Routes from research_flow.py when:
    project_type in ['directory', 'aggregator', 'comparison-tool']
"""

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..utils.llm_service import build_llm_kwargs
from ..models.research_state import TrafficMonetizationResult
from ..utils.crew_helpers import (
    compute_traffic_projection,
    match_niche_to_cpm,
    compute_ad_revenue_estimate,
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
        return Task(
            config=self.tasks_config["traffic_monetization_analysis"],
            agent=self.traffic_monetization_analyst(),
            output_pydantic=TrafficMonetizationResult,
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

    def _format_keyword_data(self, keyword_validation_results, solution_name: str) -> str:
        """
        Format keyword validation results for traffic estimation.

        Args:
            keyword_validation_results: List of CrewKeywordValidationResult from Stage 8.5
            solution_name: Name of solution to find keyword data for

        Returns:
            Formatted string with keyword volumes and metrics
        """
        if not keyword_validation_results:
            return "No keyword data available."

        # Find validation result for this solution
        for validation in keyword_validation_results:
            if validation.solution_name == solution_name:
                lines = [
                    f"**Total Search Volume:** {validation.total_volume:,} searches/month",
                    f"**Validated Keywords:** {validation.validated_count}",
                    f"**Demand Signal:** {validation.demand_signal}",
                    "",
                    "**Top Keywords by Volume:**"
                ]

                # Add top keywords
                top_keywords = sorted(
                    validation.top_keywords,
                    key=lambda x: x.get('volume', 0),
                    reverse=True
                )[:15]

                for kw in top_keywords:
                    keyword = kw.get('keyword', 'N/A')
                    volume = kw.get('volume', 0)
                    lines.append(f"  - {keyword}: {volume:,}/month")

                # Add keyword distribution insight
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
        niche_description: str
    ) -> TrafficMonetizationResult | None:
        """
        Execute traffic monetization analysis.

        Args:
            selected_solution: SolutionIdea with project_type in [directory, aggregator, comparison-tool]
            keyword_validation_results: List of CrewKeywordValidationResult from Stage 8.5
            competitive_analysis: CompetitiveAnalysisResult from Stage 7.2
            niche_description: Niche description for context

        Returns:
            TrafficMonetizationResult with traffic-based monetization strategy, or None if analysis fails
        """
        logger.info("[Stage 8.55] Starting Traffic Monetization Analysis...")
        logger.info(f"  Solution: {selected_solution.solution_name}")
        logger.info(f"  Project Type: {selected_solution.project_type}")
        logger.info(f"  Analyzing traffic potential and monetization channels...")

        # Format keyword data for traffic estimation
        keyword_data = self._format_keyword_data(
            keyword_validation_results,
            selected_solution.solution_name
        )
        logger.debug(f"  Keyword data formatted: {len(keyword_data)} chars")

        # Format competitor analysis
        competitor_info = self._format_competitor_analysis(
            competitive_analysis,
            selected_solution.solution_name
        )
        logger.debug(f"  Competitor info formatted: {len(competitor_info)} chars")

        # Pre-compute deterministic traffic and monetization values
        total_volume = 0
        if keyword_validation_results:
            for validation in keyword_validation_results:
                if validation.solution_name == selected_solution.solution_name:
                    total_volume = validation.total_volume or 0
                    break

        traffic_projection, total_low, total_high = compute_traffic_projection(total_volume)
        cpm_low, cpm_high, cpm_vertical = match_niche_to_cpm(niche_description)
        suggested_cpm = f"${cpm_low}-${cpm_high} CPM ({cpm_vertical} vertical)"
        ad_revenue_estimate = compute_ad_revenue_estimate(total_low, total_high, cpm_low, cpm_high)

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
        }

        try:
            # Execute crew
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                traffic_result = result.pydantic
                logger.info("[Stage 8.55] Traffic Monetization Analysis Complete")
                logger.info(f"  Monetization Model: {traffic_result.monetization_model}")
                logger.info(f"  Est. Monthly Pageviews: {traffic_result.estimated_monthly_pageviews}")
                logger.info(f"  Est. Monthly Revenue: {traffic_result.estimated_monthly_revenue_range}")
                logger.info(f"  Confidence: {traffic_result.monetization_confidence}")
                return traffic_result
            else:
                logger.error("[Stage 8.55] Traffic monetization analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 8.55] Traffic monetization analysis error: {str(e)}")
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
