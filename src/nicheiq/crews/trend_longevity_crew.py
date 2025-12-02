"""
Trend Longevity Analysis Crew (Stage 9.2).

Analyzes keyword trends, discussion momentum, and competitive activity to assess
market timing, trend sustainability, and longevity. Determines if the market is
growing, stable, or declining, and whether now is the right time to enter.
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import TrendLongevityResult
from ..models.social_content import SocialContentCollection


@CrewBase
class TrendLongevityCrew:
    """
    Crew for trend longevity and market momentum analysis in Stage 9.2.

    Analyzes:
    - Keyword search volume trends over time
    - Social media discussion frequency and recency
    - Competitive landscape activity (new entrants, exits)
    - Seasonal patterns and market maturity

    Outputs:
    - Trend direction and momentum score
    - Longevity verdict (Sustainable, Risky, Fad)
    - Timing recommendation (Enter Now, Monitor & Wait, Missed Window)
    - Risk factors for trend reversal
    """

    agents_config = "config/trend_longevity_agents.yaml"
    tasks_config = "config/trend_longevity_tasks.yaml"

    def __init__(self):
        """Initialize TrendLongevityCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def trend_analyst(self) -> Agent:
        """
        Trend Analysis Specialist agent.

        Analyzes market momentum, trend sustainability, and timing
        using keyword trends, social signals, and competitive activity.
        """
        return Agent(
            config=self.agents_config["trend_analyst"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,  # Low-medium temperature for trend analysis
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def trend_longevity_analysis_task(self) -> Task:
        """
        Main trend longevity and momentum analysis task.

        Analyzes keyword trends, discussion momentum, and competitive activity
        to determine market timing and trend sustainability.
        """
        return Task(
            config=self.tasks_config["trend_longevity_analysis"],
            agent=self.trend_analyst(),
            output_pydantic=TrendLongevityResult,
            guardrail=self._validate_trend_output,
        )

    def _validate_trend_output(self, task_output) -> tuple[bool, Any]:
        """
        Validate trend longevity output meets CRITICAL RULES.

        Checks:
        - Trend direction is one of expected values
        - Longevity verdict matches trend data
        - Momentum score in valid range (0.0-1.0)
        - Required enum fields populated

        Args:
            task_output: Task output from CrewAI

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic

            # Validate trend direction
            valid_directions = ["Growing", "Stable", "Declining"]
            if result.trend_direction not in valid_directions:
                return (False, f"Trend direction must be one of: {valid_directions}, got '{result.trend_direction}'")

            # Validate trend confidence
            valid_confidence = ["High", "Medium", "Low"]
            if result.trend_confidence not in valid_confidence:
                return (False, f"Trend confidence must be one of: {valid_confidence}, got '{result.trend_confidence}'")

            # Validate momentum score range
            if not (0.0 <= result.momentum_score <= 1.0):
                return (False, f"Momentum score must be 0.0-1.0, got {result.momentum_score}")

            # Validate keyword volume trend
            valid_volume_trends = ["Increasing", "Stable", "Decreasing"]
            if result.keyword_volume_trend not in valid_volume_trends:
                return (False, f"Keyword volume trend must be one of: {valid_volume_trends}, got '{result.keyword_volume_trend}'")

            # Validate discussion frequency trend
            valid_discussion_trends = ["Increasing", "Stable", "Decreasing"]
            if result.discussion_frequency_trend not in valid_discussion_trends:
                return (False, f"Discussion frequency trend must be one of: {valid_discussion_trends}, got '{result.discussion_frequency_trend}'")

            # Validate longevity verdict
            valid_verdicts = ["Sustainable", "Risky", "Fad"]
            if result.longevity_verdict not in valid_verdicts:
                return (False, f"Longevity verdict must be one of: {valid_verdicts}, got '{result.longevity_verdict}'")

            # Validate timing recommendation
            valid_timing = ["Enter Now", "Monitor & Wait", "Missed Window"]
            if result.timing_recommendation not in valid_timing:
                return (False, f"Timing recommendation must be one of: {valid_timing}, got '{result.timing_recommendation}'")

            # Validate market maturity
            valid_maturity = ["Emerging", "Growth", "Mature"]
            if result.market_maturity not in valid_maturity:
                return (False, f"Market maturity must be one of: {valid_maturity}, got '{result.market_maturity}'")

            # Validate momentum score aligns with trend direction (FAIL instead of warn)
            if result.trend_direction == "Growing" and result.momentum_score < 0.6:
                return (False, f"Inconsistent: trend_direction='Growing' requires momentum_score >= 0.6, got {result.momentum_score}. Either lower momentum_score or change trend_direction to 'Stable'.")
            elif result.trend_direction == "Declining" and result.momentum_score > 0.4:
                return (False, f"Inconsistent: trend_direction='Declining' requires momentum_score <= 0.4, got {result.momentum_score}. Either raise momentum_score or change trend_direction to 'Stable'.")

            return (True, result)
        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the trend longevity crew.

        Single-agent, single-task crew optimized for trend analysis.
        """
        return Crew(
            agents=[self.trend_analyst()],
            tasks=[self.trend_longevity_analysis_task()],
            verbose=True,
        )

    def analyze(
        self,
        keyword_validation: CrewKeywordValidationResult,
        social_content: SocialContentCollection,
        pain_point_analysis: PainPointAnalysisResult,
        competitive_analysis: CompetitiveAnalysisResult,
        niche_description: str,
        enriched_keywords_trends: dict | None = None,
        top_enriched_keywords: list[dict] | None = None
    ) -> TrendLongevityResult | None:
        """
        Execute trend longevity crew to analyze market momentum and timing.

        Args:
            keyword_validation: Keyword validation data from Stage 8.5 (search volumes)
            social_content: Social media discussions from Stage 5 (discussion trends)
            pain_point_analysis: Pain point data from Stage 6 (problem validation recency)
            competitive_analysis: Competitive landscape from Stage 7-8.75 (new entrants)
            niche_description: Niche description for context
            enriched_keywords_trends: Aggregated trend data from Stage 9.5c monthly_searches
                Contains: trend_distribution, rising_volume_pct, top_seasonal_keywords,
                top_evergreen_keywords, market_momentum
            top_enriched_keywords: Top 20 keywords with their 12-month monthly_searches arrays
                for per-keyword trend analysis

        Returns:
            TrendLongevityResult with trend analysis and timing recommendation, or None if analysis fails
        """
        logger.info("[Stage 9.5] Starting Trend Longevity Analysis...")
        logger.info(f"  Niche: {niche_description}")

        # Extract keyword trend signals (now enhanced with actual 12-month trend data)
        keyword_signals = self._format_keyword_trends(keyword_validation, enriched_keywords_trends)

        # Add per-keyword monthly trends if available
        if top_enriched_keywords:
            keyword_signals += self._format_keyword_monthly_trends(top_enriched_keywords)

        # Extract social discussion trends
        discussion_signals = self._format_discussion_trends(social_content, pain_point_analysis)

        # Extract competitive momentum
        competitive_signals = self._format_competitive_momentum(competitive_analysis)

        # Prepare inputs for trend analysis task
        inputs = {
            "niche_description": niche_description,
            "keyword_trend_data": keyword_signals,
            "discussion_trend_data": discussion_signals,
            "competitive_momentum_data": competitive_signals,
            "total_keyword_volume": keyword_validation.total_volume if keyword_validation else 0,
            "validated_keyword_count": keyword_validation.validated_count if keyword_validation else 0,
            "discussion_count": (
                len(social_content.reddit_posts) + len(social_content.twitter_threads)
                if social_content else 0
            ),
            "competitor_count": (
                sum(len(l.competitors or []) for l in competitive_analysis.solution_landscapes)
                if competitive_analysis and competitive_analysis.solution_landscapes else 0
            ),
        }

        try:
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)

            if result and result.pydantic:
                trend_result = result.pydantic
                logger.info("[Stage 9.2] Trend Longevity Analysis Complete")
                logger.info(f"  Trend Direction: {trend_result.trend_direction}")
                logger.info(f"  Momentum Score: {trend_result.momentum_score:.2f}")
                logger.info(f"  Longevity Verdict: {trend_result.longevity_verdict}")
                logger.info(f"  Timing Recommendation: {trend_result.timing_recommendation}")
                return trend_result
            else:
                logger.error("[Stage 9.2] Trend analysis failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 9.2] Trend analysis error: {str(e)}")
            return None

    def _format_keyword_trends(
        self,
        keyword_validation: CrewKeywordValidationResult | None,
        enriched_keywords_trends: dict | None = None
    ) -> str:
        """Format keyword trend signals for analysis with actual 12-month data."""
        if not keyword_validation:
            return "No keyword validation data available."

        signals = []
        signals.append(f"**Total Monthly Search Volume:** {keyword_validation.total_volume:,} searches")
        signals.append(f"**Validated Keywords:** {keyword_validation.validated_count}")
        signals.append(f"**Demand Signal:** {keyword_validation.demand_signal}")

        if keyword_validation.top_keywords:
            signals.append("\n**Top Keywords (for trend context):**")
            for kw in keyword_validation.top_keywords[:5]:
                keyword_text = kw.get('keyword', 'N/A')
                volume = kw.get('volume', 0)
                signals.append(f"- {keyword_text}: {volume:,}/month")

        # Add ACTUAL 12-month trend data if available
        if enriched_keywords_trends:
            signals.append("\n" + "=" * 50)
            signals.append("**ACTUAL 12-MONTH TREND DATA (from DataForSEO):**")
            signals.append("=" * 50)

            # Trend distribution (calculated from monthly_searches)
            trend_dist = enriched_keywords_trends.get("trend_distribution", {})
            if trend_dist:
                total_kw = sum(trend_dist.values())
                signals.append(f"\n**Keyword Trend Distribution ({total_kw} keywords analyzed):**")
                signals.append(f"- Rising keywords: {trend_dist.get('rising', 0)} ({trend_dist.get('rising', 0)/max(total_kw, 1)*100:.0f}%)")
                signals.append(f"- Stable keywords: {trend_dist.get('stable', 0)} ({trend_dist.get('stable', 0)/max(total_kw, 1)*100:.0f}%)")
                signals.append(f"- Declining keywords: {trend_dist.get('declining', 0)} ({trend_dist.get('declining', 0)/max(total_kw, 1)*100:.0f}%)")
                signals.append(f"- Unknown trend: {trend_dist.get('unknown', 0)}")

            # Market momentum (derived from trend distribution)
            market_momentum = enriched_keywords_trends.get("market_momentum", "Unknown")
            signals.append(f"\n**Market Momentum (data-derived):** {market_momentum}")

            # Rising volume percentage
            rising_vol_pct = enriched_keywords_trends.get("rising_volume_pct", 0)
            signals.append(f"**Volume in Rising Keywords:** {rising_vol_pct:.1f}% of total search volume")

            # Evergreen keywords (low seasonality + not declining)
            evergreen = enriched_keywords_trends.get("top_evergreen_keywords", [])
            if evergreen:
                signals.append(f"\n**Evergreen Keywords (low seasonality, stable/rising):**")
                for kw in evergreen[:5]:
                    signals.append(f"- {kw}")

            # Seasonal keywords (high seasonality)
            seasonal = enriched_keywords_trends.get("top_seasonal_keywords", [])
            if seasonal:
                signals.append(f"\n**Seasonal Keywords (high volume variation):**")
                for kw in seasonal[:5]:
                    signals.append(f"- {kw}")

            signals.append("\n**IMPORTANT:** Use the above ACTUAL trend data to inform your trend_direction and momentum_score.")
            signals.append("This data is calculated from 12 months of historical search volumes, NOT inferred.")

        else:
            # Fallback: No actual trend data available
            signals.append("\n**Note:** No 12-month historical data available. Trend direction must be inferred from current volumes, discussion recency, and competitive activity.")

        return "\n".join(signals)

    def _format_discussion_trends(
        self,
        social_content: SocialContentCollection | None,
        pain_point_analysis: PainPointAnalysisResult | None
    ) -> str:
        """Format social discussion trend signals for analysis."""
        if not social_content:
            return "No social content data available."

        signals = []
        reddit_count = len(social_content.reddit_posts) if social_content.reddit_posts else 0
        twitter_count = len(social_content.twitter_threads) if social_content.twitter_threads else 0
        signals.append(f"**Total Discussions Analyzed:** {reddit_count + twitter_count}")
        signals.append(f"- Reddit posts: {reddit_count}")
        signals.append(f"- Twitter threads: {twitter_count}")

        # Analyze discussion recency from timestamps
        if social_content.reddit_posts:
            from datetime import datetime, timedelta, timezone

            signals.append("\n**Discussion Recency (Reddit sample with timestamps):**")
            now = datetime.now(timezone.utc)

            for post in social_content.reddit_posts[:5]:
                title = getattr(post, 'title', 'Untitled')[:60]
                created = getattr(post, 'created_utc', None)

                age_label = ""
                if created:
                    days_ago = (now - created).days
                    if days_ago < 30:
                        age_label = f" [Recent: {days_ago}d ago]"
                    elif days_ago < 180:
                        months_ago = days_ago // 30
                        age_label = f" [Moderate: {months_ago}mo ago]"
                    else:
                        years_ago = days_ago // 365
                        if years_ago >= 2:
                            age_label = f" [Dated: {years_ago}yr ago]"
                        else:
                            age_label = f" [Dated: {days_ago}d ago]"

                signals.append(f"- {title}{age_label}")

        if pain_point_analysis and pain_point_analysis.pain_points:
            signals.append(f"\n**Pain Point Validation:** {len(pain_point_analysis.pain_points)} pain points identified")
            signals.append(f"**Total Mentions:** {pain_point_analysis.total_mentions}")

        return "\n".join(signals)

    def _format_competitive_momentum(self, competitive_analysis: CompetitiveAnalysisResult | None) -> str:
        """Format competitive momentum signals for analysis."""
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitive analysis data available."

        signals = []

        # Count total competitors across all solution landscapes
        total_competitors = sum(
            len(landscape.competitors or [])
            for landscape in competitive_analysis.solution_landscapes
        )
        signals.append(f"**Total Competitors:** {total_competitors}")

        # Count market gaps across all landscapes
        total_gaps = sum(
            len(landscape.market_gaps)
            for landscape in competitive_analysis.solution_landscapes
        )
        if total_gaps > 0:
            signals.append(f"\n**Market Gaps Identified:** {total_gaps}")
            signals.append("(Indicates room for new entrants)")

        # Sample competitors from first landscape
        first_landscape = competitive_analysis.solution_landscapes[0]
        if first_landscape.competitors:
            signals.append("\n**Sample Competitors (for maturity assessment):**")
            for comp in first_landscape.competitors[:5]:
                signals.append(f"- {comp.name}")

        return "\n".join(signals)

    def _format_keyword_monthly_trends(self, top_enriched_keywords: list[dict] | None) -> str:
        """Format per-keyword monthly search trends for detailed analysis."""
        if not top_enriched_keywords:
            return ""

        signals = []
        signals.append("\n\n**Individual Keyword 12-Month Trends (Top 10):**")

        for kw in top_enriched_keywords[:10]:
            keyword = kw.get('keyword', 'N/A')
            volume = kw.get('search_volume', 0)
            monthly = kw.get('monthly_searches', [])

            # Format monthly trend as sparkline-style summary
            if monthly and len(monthly) >= 2:
                # Compare first 3 months vs last 3 months to determine trend
                first_3_avg = (
                    sum(m.get('search_volume', 0) for m in monthly[:3]) / 3
                    if len(monthly) >= 3 else monthly[0].get('search_volume', 0)
                )
                last_3_avg = (
                    sum(m.get('search_volume', 0) for m in monthly[-3:]) / 3
                    if len(monthly) >= 3 else monthly[-1].get('search_volume', 0)
                )

                if last_3_avg > first_3_avg * 1.1:
                    trend_arrow = "↑ Rising"
                elif last_3_avg < first_3_avg * 0.9:
                    trend_arrow = "↓ Declining"
                else:
                    trend_arrow = "→ Stable"

                signals.append(f"- {keyword}: {volume:,}/mo ({trend_arrow})")
            else:
                signals.append(f"- {keyword}: {volume:,}/mo")

        return "\n".join(signals)
