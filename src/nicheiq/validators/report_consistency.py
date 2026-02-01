"""
Cross-section consistency validation for final reports.

Detects and optionally reconciles contradictions between report sections
that compute similar metrics independently (e.g., executive dashboard vs
market analytics).

Design:
- validate() is read-only: detects issues, returns structured warnings
- reconcile() applies safe automatic fixes + returns remaining warnings
- Never mutates trend data or LLM-generated narrative
"""

from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field


class ConsistencyWarning(BaseModel):
    """A single cross-section inconsistency detected in a report."""

    field_path: str = Field(
        description="Dot-separated path to the problematic field, e.g. 'market_analytics.recommendation'"
    )
    severity: Literal["ERROR", "WARNING", "INFO"] = Field(
        description="ERROR: data corruption, WARNING: likely bug, INFO: documented difference"
    )
    message: str = Field(
        description="Human-readable description of the inconsistency"
    )
    expected_value: Optional[str] = Field(
        default=None,
        description="The expected/authoritative value (from dashboard)"
    )
    actual_value: Optional[str] = Field(
        default=None,
        description="The actual value found (in the inconsistent section)"
    )


class ReportConsistencyValidator:
    """
    Detects and reconciles cross-section inconsistencies in FinalReport.

    The executive dashboard is treated as the authoritative source for
    exact-match fields (keyword counts, competitor counts, etc.) because
    it is computed first from the enriched solution.
    """

    def validate(self, report, state=None) -> list[ConsistencyWarning]:
        """
        Detect inconsistencies without mutation. Returns structured warnings.

        Args:
            report: FinalReport instance
            state: Optional ResearchState for trend/market_sizing cross-checks

        Returns:
            List of ConsistencyWarning objects (empty = all consistent)
        """
        warnings: list[ConsistencyWarning] = []

        warnings.extend(self._check_exact_matches(report))
        warnings.extend(self._check_market_timing_vs_trend(report, state))
        warnings.extend(self._check_trend_internal_coherence(report, state))
        warnings.extend(self._check_verdict_vs_recommendation(report))
        warnings.extend(self._check_core_pain_point_coverage(report))

        return warnings

    def reconcile(self, report, state=None) -> tuple[list[str], list[ConsistencyWarning]]:
        """
        Apply automatic fixes, then return remaining warnings.

        Safe fixes: overwrite analytics values with dashboard values
        when exact-match fields differ. Never touches verdicts or narratives.

        Args:
            report: FinalReport instance (will be mutated)
            state: Optional ResearchState

        Returns:
            Tuple of (fixes_applied: list[str], remaining_warnings: list[ConsistencyWarning])
        """
        fixes: list[str] = []

        # Reconcile exact-match fields
        fixes.extend(self._reconcile_exact_matches(report))

        # Re-validate to find remaining (non-reconcilable) warnings
        remaining = self.validate(report, state)

        return fixes, remaining

    # ------------------------------------------------------------------
    # Check: Exact-match fields between dashboard and analytics
    # ------------------------------------------------------------------

    def _check_exact_matches(self, report) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []

        dashboard = report.executive_dashboard
        if not dashboard:
            return warnings

        km = dashboard.key_metrics

        # Keyword count: dashboard.key_metrics.total_keyword_count vs seo_analytics.total_keywords
        if report.seo_analytics and km:
            if km.total_keyword_count != report.seo_analytics.total_keywords:
                warnings.append(ConsistencyWarning(
                    field_path="seo_analytics.total_keywords",
                    severity="WARNING",
                    message=(
                        f"Keyword count mismatch: dashboard shows {km.total_keyword_count}, "
                        f"seo_analytics shows {report.seo_analytics.total_keywords}"
                    ),
                    expected_value=str(km.total_keyword_count),
                    actual_value=str(report.seo_analytics.total_keywords),
                ))

            # Search volume
            if km.total_keyword_search_volume != report.seo_analytics.total_search_volume:
                warnings.append(ConsistencyWarning(
                    field_path="seo_analytics.total_search_volume",
                    severity="WARNING",
                    message=(
                        f"Search volume mismatch: dashboard shows {km.total_keyword_search_volume}, "
                        f"seo_analytics shows {report.seo_analytics.total_search_volume}"
                    ),
                    expected_value=str(km.total_keyword_search_volume),
                    actual_value=str(report.seo_analytics.total_search_volume),
                ))

        # Competitor count: dashboard vs competitive_analytics
        if report.competitive_analytics and km:
            if km.primary_competitor_count != report.competitive_analytics.competitor_count:
                warnings.append(ConsistencyWarning(
                    field_path="competitive_analytics.competitor_count",
                    severity="WARNING",
                    message=(
                        f"Competitor count mismatch: dashboard shows {km.primary_competitor_count}, "
                        f"competitive_analytics shows {report.competitive_analytics.competitor_count}"
                    ),
                    expected_value=str(km.primary_competitor_count),
                    actual_value=str(report.competitive_analytics.competitor_count),
                ))

        # Pain point count: dashboard.high_severity vs pain_point_analytics.high_severity_count
        if report.pain_point_analytics and km:
            if km.high_severity_pain_points != report.pain_point_analytics.high_severity_count:
                warnings.append(ConsistencyWarning(
                    field_path="pain_point_analytics.high_severity_count",
                    severity="WARNING",
                    message=(
                        f"High-severity pain point count mismatch: dashboard shows {km.high_severity_pain_points}, "
                        f"pain_point_analytics shows {report.pain_point_analytics.high_severity_count}"
                    ),
                    expected_value=str(km.high_severity_pain_points),
                    actual_value=str(report.pain_point_analytics.high_severity_count),
                ))

        # Confidence score: dashboard.confidence_score vs market_analytics.selection_confidence
        if report.market_analytics and dashboard:
            if abs(dashboard.confidence_score - report.market_analytics.selection_confidence) > 1e-6:
                warnings.append(ConsistencyWarning(
                    field_path="market_analytics.selection_confidence",
                    severity="WARNING",
                    message=(
                        f"Confidence score mismatch: dashboard shows {dashboard.confidence_score:.3f}, "
                        f"market_analytics shows {report.market_analytics.selection_confidence:.3f}"
                    ),
                    expected_value=f"{dashboard.confidence_score:.3f}",
                    actual_value=f"{report.market_analytics.selection_confidence:.3f}",
                ))

        return warnings

    # ------------------------------------------------------------------
    # Check: Market timing (Stage 8.6) vs trend direction (Stage 9.5)
    # ------------------------------------------------------------------

    def _check_market_timing_vs_trend(self, report, state=None) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []

        if not state:
            return warnings

        market_sizing = getattr(state, 'market_sizing', None)
        trend_longevity = getattr(state, 'trend_longevity', None)

        if not market_sizing or not trend_longevity:
            return warnings

        timing = getattr(market_sizing, 'market_timing_assessment', None)
        trend_dir = getattr(trend_longevity, 'trend_direction', None)

        if not timing or not trend_dir:
            return warnings

        # Growth timing + Declining trend = contradiction
        if timing == "Growth" and trend_dir == "Declining":
            warnings.append(ConsistencyWarning(
                field_path="market_sizing.market_timing_assessment",
                severity="WARNING",
                message=(
                    f"Market timing contradiction: Stage 8.6 assessed market as '{timing}' "
                    f"but Stage 9.5 trend analysis shows '{trend_dir}' direction. "
                    f"Stage 8.6 uses snapshot data; Stage 9.5 uses 12-month historical trends."
                ),
                expected_value=trend_dir,
                actual_value=timing,
            ))

        # Mature timing + Declining trend = also notable
        if timing == "Mature" and trend_dir == "Declining":
            warnings.append(ConsistencyWarning(
                field_path="market_sizing.market_timing_assessment",
                severity="WARNING",
                message=(
                    f"Market maturity concern: Stage 8.6 assessed market as '{timing}' "
                    f"and Stage 9.5 confirms '{trend_dir}' direction. "
                    f"This combination suggests a contracting market."
                ),
                expected_value=trend_dir,
                actual_value=timing,
            ))

        return warnings

    # ------------------------------------------------------------------
    # Check: Trend internal coherence (longevity vs direction/timing)
    # ------------------------------------------------------------------

    def _check_trend_internal_coherence(self, report, state=None) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []

        if not state:
            return warnings

        trend = getattr(state, 'trend_longevity', None)
        if not trend:
            return warnings

        longevity = getattr(trend, 'longevity_verdict', None)
        direction = getattr(trend, 'trend_direction', None)
        timing = getattr(trend, 'timing_recommendation', None)

        if not longevity or not direction:
            return warnings

        # "Sustainable" + "Missed Window" is contradictory
        if longevity == "Sustainable" and timing == "Missed Window":
            warnings.append(ConsistencyWarning(
                field_path="trend_longevity.longevity_verdict",
                severity="WARNING",
                message=(
                    f"Trend coherence issue: longevity is '{longevity}' but timing is '{timing}'. "
                    f"A sustainable market should not have a 'Missed Window' recommendation."
                ),
            ))

        # "Sustainable" + "Declining" is contradictory
        if longevity == "Sustainable" and direction == "Declining":
            warnings.append(ConsistencyWarning(
                field_path="trend_longevity.longevity_verdict",
                severity="WARNING",
                message=(
                    f"Trend coherence issue: longevity is '{longevity}' but trend direction is '{direction}'. "
                    f"A declining market is unlikely to be sustainable long-term."
                ),
            ))

        return warnings

    # ------------------------------------------------------------------
    # Check: Verdict (trend-adjusted) vs Recommendation (score-based)
    # ------------------------------------------------------------------

    def _check_verdict_vs_recommendation(self, report) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []

        dashboard = report.executive_dashboard
        analytics = report.market_analytics

        if not dashboard or not analytics:
            return warnings

        verdict = dashboard.go_no_go_verdict.verdict
        recommendation = analytics.recommendation

        if verdict != recommendation:
            warnings.append(ConsistencyWarning(
                field_path="market_analytics.recommendation",
                severity="INFO",
                message=(
                    f"Verdict/recommendation difference: executive dashboard verdict is '{verdict}' "
                    f"(trend-adjusted) while market_analytics recommendation is '{recommendation}' "
                    f"(score-based on overall_opportunity_score={analytics.overall_opportunity_score:.2f}). "
                    f"This is expected when trend data adjusts the score-based verdict."
                ),
                expected_value=verdict,
                actual_value=recommendation,
            ))

        return warnings

    # ------------------------------------------------------------------
    # Check: Core pain point covered by selected solution
    # ------------------------------------------------------------------

    def _check_core_pain_point_coverage(self, report) -> list[ConsistencyWarning]:
        """Check that the #1 core pain point appears in the selected solution's pain_points_addressed."""
        warnings: list[ConsistencyWarning] = []

        dashboard = getattr(report, 'executive_dashboard', None)
        if not dashboard:
            return warnings

        core_pain_point = getattr(dashboard, 'core_pain_point', None)
        if not core_pain_point:
            return warnings

        solution_details = getattr(report, 'selected_solution_details', None)
        if not solution_details:
            return warnings

        addressed = getattr(solution_details, 'pain_points_addressed', None)
        if addressed is None:
            return warnings

        core_title = str(core_pain_point)

        if len(addressed) == 0:
            warnings.append(ConsistencyWarning(
                field_path="selected_solution_details.pain_points_addressed",
                severity="WARNING",
                message=(
                    f"Core pain point '{core_title}' is not addressed by the selected solution: "
                    f"pain_points_addressed is empty."
                ),
                expected_value=core_title,
                actual_value="(empty list)",
            ))
            return warnings

        # 3-level match hierarchy
        addressed_titles = [str(t) for t in addressed]

        # Level 1: exact match
        if core_title in addressed_titles:
            return warnings

        # Level 2: case-insensitive
        core_lower = core_title.lower()
        for title in addressed_titles:
            if core_lower == title.lower():
                warnings.append(ConsistencyWarning(
                    field_path="selected_solution_details.pain_points_addressed",
                    severity="INFO",
                    message=(
                        f"Core pain point '{core_title}' found via case-insensitive match "
                        f"as '{title}' in pain_points_addressed."
                    ),
                    expected_value=core_title,
                    actual_value=title,
                ))
                return warnings

        # Level 3: containment
        for title in addressed_titles:
            title_lower = title.lower()
            if core_lower in title_lower or title_lower in core_lower:
                warnings.append(ConsistencyWarning(
                    field_path="selected_solution_details.pain_points_addressed",
                    severity="INFO",
                    message=(
                        f"Core pain point '{core_title}' found via substring match "
                        f"as '{title}' in pain_points_addressed."
                    ),
                    expected_value=core_title,
                    actual_value=title,
                ))
                return warnings

        # No match at any level
        truncated = ", ".join(addressed_titles)
        if len(truncated) > 200:
            truncated = truncated[:200] + "..."

        warnings.append(ConsistencyWarning(
            field_path="selected_solution_details.pain_points_addressed",
            severity="WARNING",
            message=(
                f"Core pain point '{core_title}' (the #1 pain point by severity+WTP) "
                f"is not in the selected solution's pain_points_addressed list. "
                f"The recommended solution does not claim to address the top problem."
            ),
            expected_value=core_title,
            actual_value=truncated,
        ))

        return warnings

    # ------------------------------------------------------------------
    # Reconciliation: overwrite analytics with dashboard values
    # ------------------------------------------------------------------

    def _reconcile_exact_matches(self, report) -> list[str]:
        fixes: list[str] = []

        dashboard = report.executive_dashboard
        if not dashboard:
            return fixes

        km = dashboard.key_metrics

        # Keyword count
        if report.seo_analytics and km:
            if km.total_keyword_count != report.seo_analytics.total_keywords:
                old = report.seo_analytics.total_keywords
                report.seo_analytics.total_keywords = km.total_keyword_count
                fixes.append(
                    f"seo_analytics.total_keywords: {old} → {km.total_keyword_count}"
                )

            if km.total_keyword_search_volume != report.seo_analytics.total_search_volume:
                old = report.seo_analytics.total_search_volume
                report.seo_analytics.total_search_volume = km.total_keyword_search_volume
                fixes.append(
                    f"seo_analytics.total_search_volume: {old} → {km.total_keyword_search_volume}"
                )

        # Competitor count
        if report.competitive_analytics and km:
            if km.primary_competitor_count != report.competitive_analytics.competitor_count:
                old = report.competitive_analytics.competitor_count
                report.competitive_analytics.competitor_count = km.primary_competitor_count
                fixes.append(
                    f"competitive_analytics.competitor_count: {old} → {km.primary_competitor_count}"
                )

        # Pain point count
        if report.pain_point_analytics and km:
            if km.high_severity_pain_points != report.pain_point_analytics.high_severity_count:
                old = report.pain_point_analytics.high_severity_count
                report.pain_point_analytics.high_severity_count = km.high_severity_pain_points
                fixes.append(
                    f"pain_point_analytics.high_severity_count: {old} → {km.high_severity_pain_points}"
                )

        # Confidence score
        if report.market_analytics and dashboard:
            if abs(dashboard.confidence_score - report.market_analytics.selection_confidence) > 1e-6:
                old = report.market_analytics.selection_confidence
                report.market_analytics.selection_confidence = dashboard.confidence_score
                fixes.append(
                    f"market_analytics.selection_confidence: {old:.3f} → {dashboard.confidence_score:.3f}"
                )

        return fixes
