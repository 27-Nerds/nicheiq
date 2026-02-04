"""
Cross-section consistency validation for final reports.

Detects and optionally reconciles contradictions between report sections
that compute similar metrics independently (e.g., executive dashboard vs
market analytics).

Design:
- validate() is read-only: detects issues, returns structured warnings
- reconcile() applies safe automatic fixes + returns remaining warnings
- Reconciliation mutates report fields only; never mutates trend_longevity data
"""

import re
from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field


def _strip_numbering_prefix(text: str) -> str:
    """Strip leading numbering like '1. ', '3) ' from LLM-generated list items."""
    return re.sub(r'^\d+[\.\)]\s*', '', text)


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
        warnings.extend(self._check_verdict_vs_viability(report, state))
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

        # Reconcile market timing vs trend direction contradictions
        fixes.extend(self._reconcile_market_timing_vs_trend(report, state))

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

            # Search volume: KeyMetrics uses niche-relevant volume, SEOAnalytics uses full Stage 9 volume.
            # They intentionally differ. Use ratio-aware checks instead of exact match.
            if km.total_keyword_search_volume != report.seo_analytics.total_search_volume:
                seo_vol = report.seo_analytics.total_search_volume
                km_vol = km.total_keyword_search_volume
                if seo_vol > 0 and km_vol > seo_vol:
                    # Filtered > total = data corruption
                    ratio = km_vol / seo_vol
                    warnings.append(ConsistencyWarning(
                        field_path="seo_analytics.total_search_volume",
                        severity="ERROR",
                        message=(
                            f"Search volume anomaly: dashboard niche-relevant volume ({km_vol:,}) "
                            f"exceeds seo_analytics total volume ({seo_vol:,}) — ratio {ratio:.2f}. "
                            f"Filtered volume should not exceed total."
                        ),
                        expected_value=str(km_vol),
                        actual_value=str(seo_vol),
                    ))
                elif seo_vol > 0 and km_vol > 0 and (km_vol / seo_vol) < 0.05:
                    # Suspiciously low filter ratio
                    ratio = km_vol / seo_vol
                    warnings.append(ConsistencyWarning(
                        field_path="seo_analytics.total_search_volume",
                        severity="WARNING",
                        message=(
                            f"Suspiciously low volume filter ratio ({ratio:.1%}): "
                            f"dashboard niche-relevant volume ({km_vol:,}) vs "
                            f"seo_analytics total volume ({seo_vol:,}). "
                            f"Keyword filtering may be overly aggressive."
                        ),
                        expected_value=str(km_vol),
                        actual_value=str(seo_vol),
                    ))
                else:
                    # Expected: KeyMetrics = filtered, SEOAnalytics = total
                    warnings.append(ConsistencyWarning(
                        field_path="seo_analytics.total_search_volume",
                        severity="INFO",
                        message=(
                            f"Search volume difference (expected): dashboard shows niche-relevant "
                            f"volume {km_vol:,}, seo_analytics shows total Stage 9 volume {seo_vol:,}. "
                            f"KeyMetrics uses filtered volume; SEOAnalytics uses full keyword set."
                        ),
                        expected_value=str(km_vol),
                        actual_value=str(seo_vol),
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
    # Check: Go verdict vs Weak market viability
    # ------------------------------------------------------------------

    def _check_verdict_vs_viability(self, report, state=None) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []

        if not state:
            return warnings

        market_sizing = getattr(state, 'market_sizing', None)
        if not market_sizing:
            return warnings

        viability = getattr(market_sizing, 'market_viability_verdict', None)
        entry_strategy = getattr(market_sizing, 'recommended_entry_strategy', None)

        if not viability:
            return warnings

        dashboard = getattr(report, 'executive_dashboard', None)
        if not dashboard:
            return warnings

        verdict_obj = getattr(dashboard, 'go_no_go_verdict', None)
        if not verdict_obj:
            return warnings

        verdict = getattr(verdict_obj, 'verdict', None)
        if not verdict:
            return warnings

        # Normalize for comparison
        viability_norm = viability.strip().title()
        entry_norm = (entry_strategy or "").strip().title()

        # Only flag contradictions when verdict is Go
        if verdict != "Go":
            return warnings

        if viability_norm == "Weak":
            warnings.append(ConsistencyWarning(
                field_path="market_sizing.market_viability_verdict",
                severity="WARNING",
                message=(
                    f"Market viability contradiction: viability assessed as '{viability}' "
                    f"but verdict is '{verdict}'"
                ),
                expected_value="Moderate or Strong",
                actual_value=viability,
            ))

        if entry_norm == "Reconsider":
            warnings.append(ConsistencyWarning(
                field_path="market_sizing.recommended_entry_strategy",
                severity="WARNING",
                message=(
                    f"Entry strategy contradiction: recommended entry strategy is "
                    f"'{entry_strategy}' but verdict is '{verdict}'"
                ),
                expected_value="Enter or Proceed",
                actual_value=entry_strategy,
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

        core_title = getattr(core_pain_point, 'title', None) or str(core_pain_point)

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
        addressed_titles = [str(t).strip() for t in addressed]
        stripped_titles = [_strip_numbering_prefix(t) for t in addressed_titles]
        core_title = core_title.strip()

        # Level 1: exact match (raw or stripped)
        if core_title in addressed_titles or core_title in stripped_titles:
            return warnings

        # Level 2: case-insensitive (raw or stripped)
        core_lower = core_title.lower()
        for raw_title, stripped_title in zip(addressed_titles, stripped_titles):
            if core_lower == raw_title.lower() or core_lower == stripped_title.lower():
                warnings.append(ConsistencyWarning(
                    field_path="selected_solution_details.pain_points_addressed",
                    severity="INFO",
                    message=(
                        f"Core pain point '{core_title}' found via case-insensitive match "
                        f"as '{raw_title}' in pain_points_addressed."
                    ),
                    expected_value=core_title,
                    actual_value=raw_title,
                ))
                return warnings

        # Level 3: containment (raw or stripped)
        for raw_title, stripped_title in zip(addressed_titles, stripped_titles):
            raw_lower = raw_title.lower()
            stripped_lower = stripped_title.lower()
            if (core_lower in raw_lower or raw_lower in core_lower
                    or core_lower in stripped_lower or stripped_lower in core_lower):
                warnings.append(ConsistencyWarning(
                    field_path="selected_solution_details.pain_points_addressed",
                    severity="INFO",
                    message=(
                        f"Core pain point '{core_title}' found via substring match "
                        f"as '{raw_title}' in pain_points_addressed."
                    ),
                    expected_value=core_title,
                    actual_value=raw_title,
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

            # Search volume: intentionally NOT reconciled.
            # KeyMetrics uses niche-relevant (filtered) volume.
            # SEOAnalytics uses full Stage 9 volume for content strategy.

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

    # ------------------------------------------------------------------
    # Reconciliation: market_timing vs trend_direction
    # ------------------------------------------------------------------

    def _reconcile_market_timing_vs_trend(self, report, state=None) -> list[str]:
        """Reconcile market_timing_assessment when it contradicts trend_direction.

        If Stage 8.6 assessed "Growth" but Stage 9.5 shows "Declining",
        downgrade market_timing_assessment to "Mature" and nullify
        market_growth_rate (which was based on the now-contradicted snapshot).
        """
        fixes: list[str] = []

        if report.market_sizing is None:
            return fixes
        if state is None:
            return fixes

        trend_longevity = getattr(state, 'trend_longevity', None)
        if trend_longevity is None:
            return fixes

        timing = getattr(report.market_sizing, 'market_timing_assessment', None)
        trend_dir = getattr(trend_longevity, 'trend_direction', None)

        if not timing or not trend_dir:
            return fixes

        # Rule 1: Growth + Declining → downgrade to Mature
        if timing == "Growth" and trend_dir == "Declining":
            report.market_sizing.market_timing_assessment = "Mature"
            fixes.append(
                "market_sizing.market_timing_assessment: 'Growth' → 'Mature' "
                "(contradicted by Stage 9.5 trend_direction='Declining')"
            )

            # Rule 2: Nullify growth rate since it was based on contradicted snapshot
            growth_rate = getattr(report.market_sizing, 'market_growth_rate', None)
            if growth_rate is not None:
                report.market_sizing.market_growth_rate = None
                fixes.append(
                    "market_sizing.market_growth_rate: nullified "
                    "(based on contradicted 'Growth' assessment)"
                )

        return fixes
