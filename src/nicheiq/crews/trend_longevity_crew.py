"""
Trend Longevity Analysis Crew (Stage 11).

Analyzes keyword trends, discussion momentum, and competitive activity to assess
market timing, trend sustainability, and longevity. Determines if the market is
growing, stable, or declining, and whether now is the right time to enter.

Deterministic fields (keyword_volume_trend, momentum_score, trend_direction, etc.)
are pre-computed in Python; the LLM only generates narrative/judgment fields via
TrendNarrativeOutput. Both are merged into the unchanged TrendLongevityResult.
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult, find_landscape_for_solution
from ..models.keyword_data import CrewKeywordValidationResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import TrendLongevityResult, TrendNarrativeOutput
from ..models.social_content import SocialContentCollection
from ..utils.llm_service import build_crew_llm
from ..utils.token_monitor import ContentTokenMonitor
from ..utils.validation.crew_guardrails import validate_trend_narrative
from ..utils.trend_scoring import compute_deterministic_signals, compute_timing

# Longevity ordering for the downgrade-only reconcile: better → worse.
_LONGEVITY_RANK = {"Sustainable": 3, "Risky": 2, "Fad": 1}


def reconcile_longevity_verdict(suggested: str, llm_verdict: str) -> str:
    """Downgrade-only reconcile of the LLM longevity verdict against the grounded suggestion.

    The Python score-first suggester (compute_longevity_suggestion) is grounded in real
    momentum/volume data and returns only {Sustainable, Risky, Undetermined} — never
    "Fad" (LLM-only). The LLM may make the verdict WORSE than the grounded suggestion but
    never BETTER (mirrors resolve_pain_point_scores / opportunity_level). "Undetermined"
    (or any unknown suggestion) does not participate — keep the LLM verdict.
    Ordering: Sustainable > Risky > Fad.
    """
    if suggested not in _LONGEVITY_RANK:
        return llm_verdict
    if _LONGEVITY_RANK.get(llm_verdict, 3) > _LONGEVITY_RANK[suggested]:
        return suggested  # LLM tried to raise above grounded → clamp down
    return llm_verdict


@CrewBase
class TrendLongevityCrew:
    """
    Crew for trend longevity and market momentum analysis in Stage 11.

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
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.3,  # Low-medium temperature for trend analysis (ignored for reasoning models)
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
        return SafeTask(
            config=self.tasks_config["trend_longevity_analysis"],
            agent=self.trend_analyst(),
            output_pydantic=TrendNarrativeOutput,
            guardrail=validate_trend_narrative,
            guardrail_max_retries=2,
        )

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

    # ── Main entry point ────────────────────────────────────────────

    def analyze(
        self,
        keyword_validation: CrewKeywordValidationResult | None,
        social_content: SocialContentCollection,
        pain_point_analysis: PainPointAnalysisResult,
        competitive_analysis: CompetitiveAnalysisResult,
        niche_description: str,
        enriched_keywords_trends: dict | None = None,
        top_enriched_keywords: list[dict] | None = None,
        selected_solution_name: str | None = None,
        seo_strategy_report=None,
    ) -> TrendLongevityResult | None:
        """
        Execute trend longevity crew to analyze market momentum and timing.

        Pre-computes deterministic fields in Python, then runs the LLM crew
        for narrative/judgment fields only (TrendNarrativeOutput). Merges both
        into the unchanged TrendLongevityResult.

        Args:
            keyword_validation: Keyword validation data (may be None when using SEO report)
            social_content: Social media discussions from Stage 5
            pain_point_analysis: Pain point data from Stage 6
            competitive_analysis: Competitive landscape from Stage 7-8.75
            niche_description: Niche description for context
            enriched_keywords_trends: Aggregated trend data from Phase 6c
            top_enriched_keywords: Top 20 keywords with 12-month monthly_searches
            selected_solution_name: Name of selected solution for scoping
            seo_strategy_report: Optional SEOStrategyReport for comprehensive keyword data

        Returns:
            TrendLongevityResult with trend analysis and timing recommendation,
            or None if analysis fails
        """
        logger.info("[Stage 11] Starting Trend Longevity Analysis...")
        logger.info(f"  Niche: {niche_description}")

        # 1. Pre-compute deterministic signals
        deterministic = compute_deterministic_signals(
            keyword_validation, social_content, competitive_analysis,
            enriched_keywords_trends,
            seo_strategy_report=seo_strategy_report,
        )
        logger.info(
            f"  Pre-computed: direction={deterministic['trend_direction']}, "
            f"momentum={deterministic['momentum_score']:.2f}, "
            f"suggested_verdict={deterministic['suggested_longevity_verdict']}"
        )

        # 2. Format raw data for LLM context (keep existing _format_* methods)
        keyword_signals = self._format_keyword_trends(keyword_validation, enriched_keywords_trends, seo_strategy_report=seo_strategy_report)
        if top_enriched_keywords:
            keyword_signals += self._format_keyword_monthly_trends(top_enriched_keywords)
        discussion_signals = self._format_discussion_trends(social_content, pain_point_analysis)
        competitive_signals = self._format_competitive_momentum(competitive_analysis, selected_solution_name)

        # Derive volume/count from SEO report when keyword_validation is None
        if keyword_validation:
            total_kw_volume = keyword_validation.total_volume or 0
            # graded_keyword_count, not validated_count (pre-2026-08 checkpoints stored
            # the unfiltered expansion pool size there).
            validated_kw_count = keyword_validation.graded_keyword_count
        elif seo_strategy_report:
            total_kw_volume = seo_strategy_report.total_monthly_volume or 0
            validated_kw_count = seo_strategy_report.total_keywords_analyzed or 0
        else:
            total_kw_volume = 0
            validated_kw_count = 0

        # 3. Build inputs: pre-computed values + raw data + counts
        inputs = {
            # Pre-computed values visible to LLM in prompt
            "keyword_volume_trend": deterministic["keyword_volume_trend"],
            "momentum_score": deterministic["momentum_score"],
            "trend_direction": deterministic["trend_direction"],
            "trend_confidence": deterministic["trend_confidence"],
            "seasonal_pattern": deterministic["seasonal_pattern"],
            "discussion_recency": deterministic["discussion_recency"],
            "discussion_frequency_trend": deterministic["discussion_frequency_trend"],
            "suggested_longevity_verdict": deterministic["suggested_longevity_verdict"],
            # Raw data for LLM context
            "keyword_trend_data": keyword_signals,
            "discussion_trend_data": discussion_signals,
            "competitive_momentum_data": competitive_signals,
            # Counts
            "niche_description": niche_description,
            "total_keyword_volume": total_kw_volume,
            "validated_keyword_count": validated_kw_count,
            "discussion_count": (
                len(social_content.reddit_posts) + len(social_content.twitter_threads) + len(social_content.generic_posts or [])
                if social_content else 0
            ),
            "competitor_count": (
                len(selected_landscape.competitors or [])
                if (selected_landscape := find_landscape_for_solution(competitive_analysis, selected_solution_name))
                else 0
            ),
        }

        try:
            # 4. Run crew (output_pydantic=TrendNarrativeOutput)
            crew_instance = self.crew()
            self._last_crew = crew_instance
            result = crew_instance.kickoff(inputs=inputs)

            if not result or not result.pydantic:
                logger.error("[Stage 11] Trend analysis failed - no Pydantic output")
                return None

            narrative: TrendNarrativeOutput = result.pydantic

            # 5. Downgrade-only reconcile of the LLM verdict against the grounded suggestion.
            suggested = deterministic["suggested_longevity_verdict"]
            reconciled = reconcile_longevity_verdict(suggested, narrative.longevity_verdict)
            if reconciled != narrative.longevity_verdict:
                logger.info(
                    f"[Stage 11] Downgrade-only reconcile: LLM '{narrative.longevity_verdict}' "
                    f"raised above grounded '{suggested}' → keeping '{reconciled}'."
                )
                narrative.longevity_verdict = reconciled

            # 6. Compute timing_recommendation (needs LLM's longevity_verdict)
            timing = compute_timing(
                deterministic["trend_direction"],
                narrative.longevity_verdict,
                deterministic["momentum_score"],
            )

            # 6b. Code-computed competitive/growth fields (previously LLM-estimated
            # from data the code already held — see audit finding B6):
            # - competitive_activity_level: deterministic competitor-count buckets
            # - volume_growth_rate: aggregate monthly-series growth (±20% + noise
            #   floor thresholds, same as per-keyword classification)
            # - new_entrants_trend: None — no competitor-age source data exists
            competitor_count = inputs["competitor_count"]
            if competitor_count > 15:
                competitive_activity_level = "High"
            elif competitor_count >= 5:
                competitive_activity_level = "Moderate"
            else:
                competitive_activity_level = "Low"
            volume_growth_rate = (
                (enriched_keywords_trends or {}).get("volume_growth_rate") or "Unknown"
            )

            # 7. Merge into TrendLongevityResult (UNCHANGED model)
            trend_result = TrendLongevityResult(
                # Python-computed (deterministic)
                keyword_volume_trend=deterministic["keyword_volume_trend"],
                momentum_score=deterministic["momentum_score"],
                trend_direction=deterministic["trend_direction"],
                trend_confidence=deterministic["trend_confidence"],
                seasonal_pattern=deterministic["seasonal_pattern"],
                discussion_recency=deterministic["discussion_recency"],
                discussion_frequency_trend=deterministic["discussion_frequency_trend"],
                timing_recommendation=timing,
                analysis_timeframe=deterministic["analysis_timeframe"],
                data_sources_analyzed=deterministic["data_sources_analyzed"],
                # Python-computed competitive/growth fields
                new_entrants_trend=None,  # no competitor-age source data
                competitive_activity_level=competitive_activity_level,
                volume_growth_rate=volume_growth_rate,
                # LLM-generated (narrative/judgment)
                market_maturity=narrative.market_maturity,
                longevity_verdict=narrative.longevity_verdict,
                longevity_rationale=narrative.longevity_rationale,
                trend_duration=narrative.trend_duration,
                peak_periods=narrative.peak_periods,
                community_growth_indicators=narrative.community_growth_indicators,
                trend_reversal_risks=narrative.trend_reversal_risks,
            )

            logger.info("[Stage 11] Trend Longevity Analysis Complete")
            logger.info(f"  Trend Direction: {trend_result.trend_direction}")
            logger.info(f"  Momentum Score: {trend_result.momentum_score:.2f}")
            logger.info(f"  Longevity Verdict: {trend_result.longevity_verdict}")
            logger.info(f"  Timing Recommendation: {trend_result.timing_recommendation}")
            return trend_result

        except Exception as e:
            logger.error(f"[Stage 11] Trend analysis error: {str(e)}")
            return None

    # ── Formatting helpers (unchanged) ──────────────────────────────

    def _format_keyword_trends(
        self,
        keyword_validation: CrewKeywordValidationResult | None,
        enriched_keywords_trends: dict | None = None,
        seo_strategy_report=None,
    ) -> str:
        """Format keyword trend signals for analysis with actual 12-month data.

        Uses SEO strategy report when keyword_validation is None.
        """
        # Derive volume/count from best available source
        if keyword_validation:
            total_volume = keyword_validation.total_volume or 0
            validated_count = keyword_validation.graded_keyword_count
            demand_signal = keyword_validation.demand_signal or "unknown"
            top_kw_lines = []
            if keyword_validation.top_keywords:
                for kw in keyword_validation.top_keywords[:5]:
                    keyword_text = kw.get('keyword', 'N/A')
                    volume = kw.get('volume', 0)
                    top_kw_lines.append(f"- {keyword_text}: {volume:,}/month")
        elif seo_strategy_report:
            total_volume = seo_strategy_report.total_monthly_volume or 0
            validated_count = seo_strategy_report.total_keywords_analyzed or 0
            if total_volume >= 5000:
                demand_signal = "strong"
            elif total_volume >= 2000:
                demand_signal = "moderate"
            else:
                demand_signal = "weak"

            all_keywords = []
            for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
                tier_kws = getattr(seo_strategy_report, tier_attr, None) or []
                all_keywords.extend(tier_kws)
            top_sorted = sorted(all_keywords, key=lambda k: k.search_volume, reverse=True)[:5]
            top_kw_lines = [f"- {kw.keyword}: {kw.search_volume:,}/month" for kw in top_sorted]
        else:
            return "No keyword data available."

        signals = []
        signals.append(f"**Total Monthly Search Volume:** {total_volume:,} searches")
        signals.append(f"**Analyzed Keywords:** {validated_count}")
        signals.append(f"**Demand Signal:** {demand_signal}")

        if top_kw_lines:
            signals.append("\n**Top Keywords (for trend context):**")
            signals.extend(top_kw_lines)

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
        generic_count = len(social_content.generic_posts) if social_content.generic_posts else 0
        signals.append(f"**Total Discussions Analyzed:** {reddit_count + twitter_count + generic_count}")
        signals.append(f"- Reddit posts: {reddit_count}")
        signals.append(f"- Twitter threads: {twitter_count}")
        if generic_count:
            signals.append(f"- Other sources (HN, YouTube): {generic_count}")

        # Analyze discussion recency from timestamps
        if social_content.reddit_posts:
            from datetime import datetime, timezone

            signals.append("\n**Discussion Recency (top 5 by discussion richness):**")
            now = datetime.now(timezone.utc)

            # Sort by discussion richness (pain_point_priority_score) to show best posts
            sorted_posts = sorted(
                social_content.reddit_posts,
                key=ContentTokenMonitor.pain_point_priority_score,
                reverse=True,
            )

            for post in sorted_posts[:5]:
                title = getattr(post, 'title', 'Untitled')[:60]
                created = getattr(post, 'created_utc', None)
                n_comments = len(post.comments) if post.comments else 0

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
                        if years_ago >= 1:
                            age_label = f" [Dated: {years_ago}yr ago]"
                        else:
                            age_label = f" [Dated: {days_ago}d ago]"

                signals.append(f"- {title} [{post.score} pts, {n_comments} comments]{age_label}")

            # Aggregate discussion quality metrics
            all_comment_counts = [
                len(p.comments) if p.comments else 0
                for p in social_content.reddit_posts
            ]
            total_comments = sum(all_comment_counts)
            avg_comments = total_comments / max(len(all_comment_counts), 1)
            rich_discussions = sum(1 for c in all_comment_counts if c >= 20)

            signals.append(f"\n**Discussion Quality Metrics:**")
            signals.append(f"- Total comments across all posts: {total_comments}")
            signals.append(f"- Average comments per post: {avg_comments:.1f}")
            signals.append(f"- Posts with 20+ comments (rich discussions): {rich_discussions}")

        if pain_point_analysis and pain_point_analysis.pain_points:
            signals.append(f"\n**Pain Point Validation:** {len(pain_point_analysis.pain_points)} pain points identified")
            signals.append(f"**Total Mentions:** {pain_point_analysis.total_mentions}")

        return "\n".join(signals)

    def _format_competitive_momentum(
        self,
        competitive_analysis: CompetitiveAnalysisResult | None,
        selected_solution_name: str | None = None,
    ) -> str:
        """Format competitive momentum signals for analysis.

        Scoped to the selected solution's landscape rather than aggregating
        across all landscapes.
        """
        if not competitive_analysis or not competitive_analysis.solution_landscapes:
            return "No competitive analysis data available."

        landscape = find_landscape_for_solution(competitive_analysis, selected_solution_name)
        if not landscape:
            return "No competitive analysis data available."

        signals = []

        competitor_count = len(landscape.competitors or [])
        signals.append(f"**Total Competitors:** {competitor_count}")

        if landscape.market_gaps:
            signals.append(f"\n**Market Gaps Identified:** {len(landscape.market_gaps)}")
            signals.append("(Indicates room for new entrants)")

        if landscape.competitors:
            signals.append("\n**Sample Competitors (for maturity assessment):**")
            for comp in landscape.competitors[:5]:
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
                # Sort newest-first to match _calculate_trend_metrics
                sorted_monthly = sorted(
                    monthly,
                    key=lambda x: (x.get('year', 0), x.get('month', 0)),
                    reverse=True
                )
                # Compare recent 3 months vs older 3 months
                recent_3_avg = (
                    sum(m.get('search_volume', 0) for m in sorted_monthly[:3]) / 3
                    if len(sorted_monthly) >= 3 else sorted_monthly[0].get('search_volume', 0)
                )
                older_3_avg = (
                    sum(m.get('search_volume', 0) for m in sorted_monthly[-3:]) / 3
                    if len(sorted_monthly) >= 3 else sorted_monthly[-1].get('search_volume', 0)
                )

                # Use symmetric thresholds aligned with _calculate_trend_metrics
                if older_3_avg > 0:
                    trend_pct = ((recent_3_avg - older_3_avg) / older_3_avg) * 100
                else:
                    trend_pct = 0

                # Low-volume noise floor
                if recent_3_avg < 50 and older_3_avg < 50:
                    trend_arrow = "→ Stable"
                elif trend_pct > 20:
                    trend_arrow = "↑ Rising"
                elif trend_pct < -20:
                    trend_arrow = "↓ Declining"
                else:
                    trend_arrow = "→ Stable"

                signals.append(f"- {keyword}: {volume:,}/mo ({trend_arrow})")
            else:
                signals.append(f"- {keyword}: {volume:,}/mo")

        return "\n".join(signals)

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
