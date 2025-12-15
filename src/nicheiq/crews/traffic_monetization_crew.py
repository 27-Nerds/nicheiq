"""
Traffic Monetization Crew (Stage 8.55).

For directories, aggregators, and comparison tools that monetize via
traffic (ads, affiliates) rather than subscriptions.

Routes from research_flow.py when:
    project_type in ['directory', 'aggregator', 'comparison-tool']
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.research_state import TrafficMonetizationResult


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
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Balanced for creative revenue suggestions
                api_key=settings.openai_api_key
            ),
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
            guardrail=self._validate_traffic_output,
        )

    def _validate_traffic_output(self, task_output) -> tuple[bool, Any]:
        """
        Validate traffic monetization output meets requirements.

        Checks:
        - Monetization model is valid
        - Confidence level is valid
        - Revenue estimates contain dollar sign
        - Required lists are populated

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic
            if result is None:
                return (False, "Traffic analysis returned None pydantic output")

            # Validate monetization model
            valid_models = ["Ad-Supported", "Affiliate", "Hybrid-Traffic", "Lead-Gen"]
            if result.monetization_model not in valid_models:
                return (False, f"Invalid monetization_model: '{result.monetization_model}'. Must be one of: {valid_models}")

            # Validate confidence level
            valid_confidence = ["High", "Medium", "Low"]
            if result.monetization_confidence not in valid_confidence:
                return (False, f"Invalid monetization_confidence: '{result.monetization_confidence}'. Must be one of: {valid_confidence}")

            # Validate revenue estimates contain dollar sign
            if "$" not in result.estimated_monthly_revenue_range:
                return (False, f"estimated_monthly_revenue_range missing $ symbol: '{result.estimated_monthly_revenue_range}'")
            if "$" not in result.estimated_annual_revenue_range:
                return (False, f"estimated_annual_revenue_range missing $ symbol: '{result.estimated_annual_revenue_range}'")
            if "$" not in result.estimated_monthly_ad_revenue:
                return (False, f"estimated_monthly_ad_revenue missing $ symbol: '{result.estimated_monthly_ad_revenue}'")
            if "$" not in result.estimated_cpm_rate:
                return (False, f"estimated_cpm_rate missing $ symbol: '{result.estimated_cpm_rate}'")

            # Validate required lists are populated
            if not result.recommended_ad_networks or len(result.recommended_ad_networks) == 0:
                return (False, "recommended_ad_networks cannot be empty")
            if not result.recommended_affiliate_programs or len(result.recommended_affiliate_programs) == 0:
                return (False, "recommended_affiliate_programs cannot be empty")

            # Validate traffic_source_breakdown is a dict with values
            if not result.traffic_source_breakdown or len(result.traffic_source_breakdown) == 0:
                return (False, "traffic_source_breakdown cannot be empty")

            logger.info(f"✓ Traffic monetization guardrail passed: {result.monetization_model} model, {result.monetization_confidence} confidence")
            return (True, result)

        except Exception as e:
            return (False, f"Traffic validation error: {str(e)}")

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

        # Prepare inputs for the task
        inputs = {
            "solution_name": selected_solution.solution_name,
            "project_type": selected_solution.project_type or "directory",
            "solution_description": selected_solution.description or "No description provided",
            "niche_description": niche_description,
            "keyword_data": keyword_data,
            "competitor_analysis": competitor_info,
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
