"""
Unit tests for ReportConsistencyValidator.

Tests cross-section consistency validation and reconciliation
for FinalReport objects.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.models.executive_summary import CorePainPoint
from nicheiq.validators.report_consistency import (
    ConsistencyWarning,
    ReportConsistencyValidator,
)


def _make_report(
    dashboard_keyword_count=166,
    dashboard_search_volume=125000,
    dashboard_competitor_count=8,
    dashboard_high_severity_pp=5,
    dashboard_confidence=0.805,
    dashboard_verdict="Go",
    seo_total_keywords=166,
    seo_total_search_volume=125000,
    seo_core_search_volume=None,
    competitive_competitor_count=8,
    pp_high_severity_count=5,
    analytics_selection_confidence=0.805,
    analytics_recommendation="Go",
    analytics_opportunity_score=0.82,
    include_dashboard=True,
    include_seo=True,
    include_competitive=True,
    include_pain_point=True,
    include_market=True,
):
    """Create a mock FinalReport with configurable section values."""
    report = MagicMock()

    if include_dashboard:
        dashboard = MagicMock()
        km = MagicMock()
        km.total_keyword_count = dashboard_keyword_count
        km.total_keyword_search_volume = dashboard_search_volume
        km.primary_competitor_count = dashboard_competitor_count
        km.high_severity_pain_points = dashboard_high_severity_pp
        dashboard.key_metrics = km
        dashboard.confidence_score = dashboard_confidence
        verdict_obj = MagicMock()
        verdict_obj.verdict = dashboard_verdict
        dashboard.go_no_go_verdict = verdict_obj
        report.executive_dashboard = dashboard
    else:
        report.executive_dashboard = None

    if include_seo:
        seo = MagicMock()
        seo.total_keywords = seo_total_keywords
        seo.total_search_volume = seo_total_search_volume
        seo.core_search_volume = seo_core_search_volume
        report.seo_analytics = seo
    else:
        report.seo_analytics = None

    if include_competitive:
        comp = MagicMock()
        comp.competitor_count = competitive_competitor_count
        report.competitive_analytics = comp
    else:
        report.competitive_analytics = None

    if include_pain_point:
        pp = MagicMock()
        pp.high_severity_count = pp_high_severity_count
        report.pain_point_analytics = pp
    else:
        report.pain_point_analytics = None

    if include_market:
        ma = MagicMock()
        ma.selection_confidence = analytics_selection_confidence
        ma.recommendation = analytics_recommendation
        ma.overall_opportunity_score = analytics_opportunity_score
        report.market_analytics = ma
    else:
        report.market_analytics = None

    report.data_quality_summary = None
    report.selected_solution_details = None

    return report


def _make_state(
    market_timing=None,
    trend_direction=None,
    longevity_verdict=None,
    timing_recommendation=None,
    market_growth_rate=None,
    volume_growth_rate=None,
    include_market_sizing=True,
    include_trend=True,
):
    """Create a mock ResearchState with configurable market/trend data."""
    state = MagicMock()

    if include_market_sizing and market_timing is not None:
        ms = MagicMock()
        ms.market_timing_assessment = market_timing
        ms.market_growth_rate = market_growth_rate
        state.market_sizing = ms
    else:
        state.market_sizing = None

    if include_trend and (trend_direction is not None or longevity_verdict is not None):
        tl = MagicMock()
        tl.trend_direction = trend_direction
        tl.longevity_verdict = longevity_verdict
        tl.timing_recommendation = timing_recommendation
        tl.volume_growth_rate = volume_growth_rate
        state.trend_longevity = tl
    else:
        state.trend_longevity = None

    return state


# ======================================================================
# Exact Match Checks
# ======================================================================


class TestValidateExactMatches:
    """Test detection of exact-match field mismatches."""

    def test_keyword_count_mismatch_detected(self):
        report = _make_report(
            dashboard_keyword_count=166,
            seo_total_keywords=178,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        kw_warnings = [w for w in warnings if "keyword count" in w.message.lower()]
        assert len(kw_warnings) == 1
        assert kw_warnings[0].severity == "WARNING"
        assert kw_warnings[0].expected_value == "166"
        assert kw_warnings[0].actual_value == "178"

    def test_keyword_count_match_no_warning(self):
        report = _make_report(
            dashboard_keyword_count=166,
            seo_total_keywords=166,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        kw_warnings = [w for w in warnings if "keyword count" in w.message.lower()]
        assert len(kw_warnings) == 0

    def test_search_volume_km_gt_core_is_info(self):
        """Expected: KeyMetrics total > core (includes extra tiers) → INFO."""
        report = _make_report(
            dashboard_search_volume=200000,
            seo_total_search_volume=130000,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        vol_warnings = [w for w in warnings if "search volume" in w.message.lower() and w.field_path == "seo_analytics.core_search_volume"]
        assert len(vol_warnings) == 1
        assert vol_warnings[0].severity == "INFO"

    def test_competitor_count_mismatch_detected(self):
        report = _make_report(
            dashboard_competitor_count=8,
            competitive_competitor_count=10,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        comp_warnings = [w for w in warnings if "competitor count" in w.message.lower()]
        assert len(comp_warnings) == 1

    def test_pain_point_count_mismatch_detected(self):
        report = _make_report(
            dashboard_high_severity_pp=5,
            pp_high_severity_count=7,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        pp_warnings = [w for w in warnings if "pain point" in w.message.lower()]
        assert len(pp_warnings) == 1

    def test_confidence_score_mismatch_detected(self):
        report = _make_report(
            dashboard_confidence=0.805,
            analytics_selection_confidence=0.790,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        conf_warnings = [w for w in warnings if "confidence" in w.message.lower()]
        assert len(conf_warnings) == 1

    def test_all_matches_returns_empty(self):
        report = _make_report()  # All defaults match
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        # Only exact-match warnings (verdict/recommendation same = no info warning)
        exact_warnings = [w for w in warnings if w.severity in ("ERROR", "WARNING")]
        assert len(exact_warnings) == 0


# ======================================================================
# Reconcile Exact Matches
# ======================================================================


class TestReconcileExactMatches:
    """Test that reconciliation overwrites analytics with dashboard values."""

    def test_keyword_count_reconciled_to_dashboard(self):
        report = _make_report(
            dashboard_keyword_count=166,
            seo_total_keywords=178,
        )
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report)
        assert report.seo_analytics.total_keywords == 166
        assert any("total_keywords" in f for f in fixes)

    def test_competitor_count_reconciled(self):
        report = _make_report(
            dashboard_competitor_count=8,
            competitive_competitor_count=10,
        )
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report)
        assert report.competitive_analytics.competitor_count == 8
        assert any("competitor_count" in f for f in fixes)

    def test_reconcile_returns_fix_descriptions(self):
        report = _make_report(
            dashboard_keyword_count=166,
            seo_total_keywords=178,
            dashboard_competitor_count=8,
            competitive_competitor_count=10,
        )
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report)
        # keyword count + competitor count (volume no longer reconciled)
        assert len(fixes) == 2

    def test_reconcile_no_changes_when_consistent(self):
        report = _make_report()  # All match
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report)
        assert len(fixes) == 0


# ======================================================================
# Market Timing vs Trend Direction
# ======================================================================


class TestMarketTimingVsTrend:
    """Test detection of market_sizing timing vs trend_longevity direction contradictions."""

    def test_growth_vs_declining_warns(self):
        report = _make_report()
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "market timing" in w.message.lower()]
        assert len(timing_warnings) == 1
        assert timing_warnings[0].severity == "WARNING"

    def test_growth_vs_growing_no_warning(self):
        report = _make_report()
        state = _make_state(market_timing="Growth", trend_direction="Growing")
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "market timing" in w.message.lower()]
        assert len(timing_warnings) == 0

    def test_mature_vs_declining_warns(self):
        report = _make_report()
        state = _make_state(market_timing="Mature", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "maturity" in w.message.lower()]
        assert len(timing_warnings) == 1

    def test_missing_market_sizing_no_crash(self):
        report = _make_report()
        state = _make_state(include_market_sizing=False, trend_direction="Declining")
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "timing" in w.message.lower()]
        assert len(timing_warnings) == 0

    def test_missing_trend_longevity_no_crash(self):
        report = _make_report()
        state = _make_state(market_timing="Growth", include_trend=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "timing" in w.message.lower()]
        assert len(timing_warnings) == 0

    def test_both_missing_no_crash(self):
        report = _make_report()
        state = _make_state(include_market_sizing=False, include_trend=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        timing_warnings = [w for w in warnings if "timing" in w.message.lower()]
        assert len(timing_warnings) == 0


# ======================================================================
# Trend Internal Coherence
# ======================================================================


class TestTrendInternalCoherence:
    """Test detection of contradictions within trend_longevity data."""

    def test_sustainable_plus_missed_window_warns(self):
        report = _make_report()
        state = _make_state(
            trend_direction="Stable",
            longevity_verdict="Sustainable",
            timing_recommendation="Missed Window",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) >= 1

    def test_sustainable_plus_declining_warns(self):
        report = _make_report()
        state = _make_state(
            trend_direction="Declining",
            longevity_verdict="Sustainable",
            timing_recommendation="Enter Now",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) >= 1

    def test_risky_plus_declining_no_warning(self):
        """Risky + Declining is internally consistent."""
        report = _make_report()
        state = _make_state(
            trend_direction="Declining",
            longevity_verdict="Risky",
            timing_recommendation="Monitor & Wait",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) == 0

    def test_sustainable_plus_growing_no_warning(self):
        """Sustainable + Growing is internally consistent."""
        report = _make_report()
        state = _make_state(
            trend_direction="Growing",
            longevity_verdict="Sustainable",
            timing_recommendation="Enter Now",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) == 0

    def test_fad_plus_missed_window_no_warning(self):
        """Fad + Missed Window is internally consistent."""
        report = _make_report()
        state = _make_state(
            trend_direction="Declining",
            longevity_verdict="Fad",
            timing_recommendation="Missed Window",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) == 0

    def test_missing_trend_data_no_crash(self):
        report = _make_report()
        state = _make_state(include_trend=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        coherence_warnings = [w for w in warnings if "coherence" in w.message.lower()]
        assert len(coherence_warnings) == 0


# ======================================================================
# Verdict vs Recommendation
# ======================================================================


class TestVerdictVsRecommendation:
    """Test documentation of verdict vs recommendation differences."""

    def test_go_vs_go_no_warning(self):
        report = _make_report(dashboard_verdict="Go", analytics_recommendation="Go")
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        verdict_warnings = [w for w in warnings if "verdict" in w.message.lower() and "recommendation" in w.message.lower()]
        assert len(verdict_warnings) == 0

    def test_conditional_vs_go_info_severity(self):
        report = _make_report(
            dashboard_verdict="Conditional",
            analytics_recommendation="Go",
            analytics_opportunity_score=0.82,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        verdict_warnings = [w for w in warnings if "verdict" in w.message.lower() and "recommendation" in w.message.lower()]
        assert len(verdict_warnings) == 1
        assert verdict_warnings[0].severity == "INFO"

    def test_nogo_vs_conditional_info_severity(self):
        report = _make_report(
            dashboard_verdict="No-Go",
            analytics_recommendation="Conditional",
            analytics_opportunity_score=0.65,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        verdict_warnings = [w for w in warnings if "verdict" in w.message.lower() and "recommendation" in w.message.lower()]
        assert len(verdict_warnings) == 1
        assert verdict_warnings[0].severity == "INFO"


# ======================================================================
# None Section Handling
# ======================================================================


class TestNoneSectionHandling:
    """Test that missing report sections don't cause crashes."""

    def test_no_executive_dashboard(self):
        report = _make_report(include_dashboard=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert isinstance(warnings, list)

    def test_no_market_analytics(self):
        report = _make_report(include_market=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert isinstance(warnings, list)

    def test_no_seo_analytics(self):
        report = _make_report(include_seo=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert isinstance(warnings, list)

    def test_no_competitive_analytics(self):
        report = _make_report(include_competitive=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert isinstance(warnings, list)

    def test_no_pain_point_analytics(self):
        report = _make_report(include_pain_point=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert isinstance(warnings, list)

    def test_all_sections_none_returns_empty(self):
        report = _make_report(
            include_dashboard=False,
            include_seo=False,
            include_competitive=False,
            include_pain_point=False,
            include_market=False,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        assert warnings == []

    def test_partial_sections_still_validates_available(self):
        """With only dashboard and seo, should still check keyword count."""
        report = _make_report(
            dashboard_keyword_count=166,
            seo_total_keywords=178,
            include_competitive=False,
            include_pain_point=False,
            include_market=False,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        kw_warnings = [w for w in warnings if "keyword count" in w.message.lower()]
        assert len(kw_warnings) == 1


# ======================================================================
# Core Pain Point Coverage
# ======================================================================


def _make_report_with_pain_coverage(
    core_pain_point=None,
    pain_points_addressed=None,
    include_dashboard=True,
    include_solution_details=True,
):
    """Create a mock report for core pain point coverage tests."""
    report = _make_report()

    if include_dashboard:
        if core_pain_point is not None:
            if isinstance(core_pain_point, str):
                report.executive_dashboard.core_pain_point = CorePainPoint(
                    title=core_pain_point,
                    severity_score=0.8,
                    willingness_to_pay_score=0.7,
                    representative_quote="Test quote",
                    source_platform="Test platform",
                )
            else:
                report.executive_dashboard.core_pain_point = core_pain_point
        else:
            report.executive_dashboard.core_pain_point = None
    else:
        report.executive_dashboard = None

    if include_solution_details:
        solution = MagicMock()
        solution.pain_points_addressed = pain_points_addressed
        report.selected_solution_details = solution
    else:
        report.selected_solution_details = None

    return report


class TestCorePainPointCoverage:
    """Test detection of core pain point not addressed by selected solution."""

    def test_core_pain_point_present_no_warning(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["High Setup Costs", "Poor Documentation", "Slow Onboarding"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_core_pain_point_missing_warns(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["Poor Documentation", "Slow Onboarding"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 1
        assert coverage_warnings[0].severity == "WARNING"
        assert "High Setup Costs" in coverage_warnings[0].expected_value

    def test_case_insensitive_match_info(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["high setup costs", "Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 1
        assert coverage_warnings[0].severity == "INFO"

    def test_substring_match_info(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["Addressing High Setup Costs for SMBs", "Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 1
        assert coverage_warnings[0].severity == "INFO"

    def test_no_dashboard_no_crash(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["Poor Documentation"],
            include_dashboard=False,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_no_solution_details_no_crash(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=None,
            include_solution_details=False,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_no_core_pain_point_no_crash(self):
        report = _make_report_with_pain_coverage(
            core_pain_point=None,
            pain_points_addressed=["Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_empty_pain_points_addressed_warns(self):
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=[],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 1
        assert coverage_warnings[0].severity == "WARNING"

    def test_numbered_prefix_stripped_for_match(self):
        """'1. High Setup Costs' should match 'High Setup Costs' with no WARNING."""
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["1. High Setup Costs", "2. Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_numbered_prefix_parenthesis(self):
        """'3) High Setup Costs' should match 'High Setup Costs' with no WARNING."""
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["3) High Setup Costs", "4) Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0

    def test_numbered_prefix_case_insensitive(self):
        """'1. high setup costs' vs 'High Setup Costs' should match at INFO level at most."""
        report = _make_report_with_pain_coverage(
            core_pain_point="High Setup Costs",
            pain_points_addressed=["1. high setup costs", "2. Poor Documentation"],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        # Should be at most INFO (case-insensitive match), never WARNING
        for w in coverage_warnings:
            assert w.severity != "WARNING"

    def test_pydantic_model_title_extracted(self):
        """A real CorePainPoint Pydantic object should match by its .title field."""
        core = CorePainPoint(
            title="Burnout and Mental Health Struggles",
            severity_score=0.9,
            willingness_to_pay_score=0.6,
            representative_quote="I'm so burned out",
            source_platform="Reddit r/burnout",
        )
        report = _make_report_with_pain_coverage(
            core_pain_point=core,
            pain_points_addressed=[
                "Burnout and Mental Health Struggles",
                "Lack of Work-Life Balance",
            ],
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        coverage_warnings = [w for w in warnings if "core pain point" in w.message.lower()]
        assert len(coverage_warnings) == 0


# ======================================================================
# Reconcile Market Timing vs Trend Direction
# ======================================================================


def _make_report_with_market_sizing(market_timing="Growth", market_growth_rate="15%"):
    """Create a mock report with market_sizing for reconciliation tests."""
    report = _make_report()
    ms = MagicMock()
    ms.market_timing_assessment = market_timing
    ms.market_growth_rate = market_growth_rate
    report.market_sizing = ms
    return report


class TestReconcileMarketTimingVsTrend:
    """Test reconciliation of market_timing_assessment vs trend_direction contradictions."""

    def test_growth_declining_downgrades_to_mature(self):
        """Growth + Declining → downgrade to Mature."""
        report = _make_report_with_market_sizing(market_timing="Growth")
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Mature"
        assert any("Growth" in f and "Mature" in f for f in fixes)

    def test_growth_declining_nullifies_growth_rate(self):
        """Growth + Declining → market_growth_rate set to None."""
        report = _make_report_with_market_sizing(market_timing="Growth", market_growth_rate="15%")
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_growth_rate is None
        assert any("market_growth_rate" in f and "nullified" in f for f in fixes)

    def test_growth_growing_no_change(self):
        """Growth + Growing → no reconciliation needed."""
        report = _make_report_with_market_sizing(market_timing="Growth")
        state = _make_state(market_timing="Growth", trend_direction="Growing")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Growth"
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0

    def test_early_declining_no_change(self):
        """Early + Declining → no reconciliation (only Growth triggers downgrade)."""
        report = _make_report_with_market_sizing(market_timing="Early")
        state = _make_state(market_timing="Early", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Early"
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0

    def test_mature_declining_no_change(self):
        """Mature + Declining → no reconciliation (already Mature)."""
        report = _make_report_with_market_sizing(market_timing="Mature")
        state = _make_state(market_timing="Mature", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Mature"
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0

    def test_missing_trend_data_no_change(self):
        """No trend_longevity → no reconciliation."""
        report = _make_report_with_market_sizing(market_timing="Growth")
        state = _make_state(market_timing="Growth", include_trend=False)
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Growth"
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0

    def test_missing_market_sizing_no_change(self):
        """No market_sizing on report → no reconciliation."""
        report = _make_report()
        report.market_sizing = None
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0

    def test_growth_declining_growth_rate_already_none(self):
        """Growth + Declining with growth_rate already None → only timing fix, no growth_rate fix."""
        report = _make_report_with_market_sizing(market_timing="Growth", market_growth_rate=None)
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Mature"
        growth_rate_fixes = [f for f in fixes if "market_growth_rate" in f]
        assert len(growth_rate_fixes) == 0

    def test_reconcile_integrates_market_timing_fixes(self):
        """reconcile() returns market timing fixes alongside exact-match fixes."""
        report = _make_report_with_market_sizing(market_timing="Growth")
        # Also add a keyword count mismatch
        report.seo_analytics.total_keywords = 999
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert any("total_keywords" in f for f in fixes)
        assert any("market_timing" in f for f in fixes)

    def test_cascading_revalidation(self):
        """After reconciling Growth→Mature, the 'Growth + Declining' warning should be gone,
        but 'Mature + Declining' maturity concern warning should remain.

        In production, report.market_sizing and state.market_sizing are the same
        Pydantic object (revalidate_instances='never'), so mutation is visible
        to re-validation. We simulate this by sharing the mock object.
        """
        report = _make_report_with_market_sizing(market_timing="Growth")
        state = _make_state(market_timing="Growth", trend_direction="Declining")
        # Share the same market_sizing object so mutation propagates
        state.market_sizing = report.market_sizing
        validator = ReportConsistencyValidator()
        fixes, remaining = validator.reconcile(report, state)

        # The "market timing contradiction" warning for Growth+Declining should be gone
        growth_declining_warnings = [
            w for w in remaining
            if "market timing contradiction" in w.message.lower()
        ]
        assert len(growth_declining_warnings) == 0

        # But "maturity concern" for Mature+Declining should now appear
        maturity_warnings = [
            w for w in remaining
            if "maturity concern" in w.message.lower()
        ]
        assert len(maturity_warnings) == 1

    def test_growth_stable_no_change(self):
        """Growth + Stable → no reconciliation needed."""
        report = _make_report_with_market_sizing(market_timing="Growth")
        state = _make_state(market_timing="Growth", trend_direction="Stable")
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report, state)
        assert report.market_sizing.market_timing_assessment == "Growth"
        timing_fixes = [f for f in fixes if "market_timing" in f]
        assert len(timing_fixes) == 0


# ======================================================================
# Volume Ratio-Aware Checks (Bug #13 fix)
# ======================================================================


class TestVolumeRatioAwareChecks:
    """Test ratio-aware volume validation between KeyMetrics and SEOAnalytics.

    With SEO-primary data, KeyMetrics carries total SEO volume (all tiers),
    while core_search_volume is Tier 0-2 only. km_vol >= core_vol is expected.
    """

    def test_volume_km_gt_core_is_info(self):
        """Expected: KeyMetrics total > core (includes Tier 3-4) → INFO."""
        report = _make_report(
            dashboard_search_volume=200000,
            seo_total_search_volume=125000,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        vol_warnings = [w for w in warnings if "volume" in w.message.lower() and w.field_path == "seo_analytics.core_search_volume"]
        assert len(vol_warnings) == 1
        assert vol_warnings[0].severity == "INFO"

    def test_volume_km_lt_core_is_warning(self):
        """KeyMetrics < core = stale/legacy data → WARNING."""
        report = _make_report(
            dashboard_search_volume=15000,
            seo_total_search_volume=125000,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        vol_warnings = [w for w in warnings if "volume" in w.message.lower() and w.field_path == "seo_analytics.core_search_volume"]
        assert len(vol_warnings) == 1
        assert vol_warnings[0].severity == "WARNING"
        assert "less than" in vol_warnings[0].message.lower()

    def test_volume_unusually_high_ratio_is_warning(self):
        """KeyMetrics > 5x core → WARNING (Tier 3-4 inflation)."""
        report = _make_report(
            dashboard_search_volume=700000,
            seo_total_search_volume=125000,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        vol_warnings = [w for w in warnings if "volume" in w.message.lower() and w.field_path == "seo_analytics.core_search_volume"]
        assert len(vol_warnings) == 1
        assert vol_warnings[0].severity == "WARNING"
        assert "unusually high" in vol_warnings[0].message.lower()

    def test_volume_equal_no_warning(self):
        """KeyMetrics == core → no warning at all."""
        report = _make_report(
            dashboard_search_volume=125000,
            seo_total_search_volume=125000,
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report)
        vol_warnings = [w for w in warnings if "volume" in w.message.lower() and w.field_path == "seo_analytics.core_search_volume"]
        assert len(vol_warnings) == 0

    def test_volume_no_longer_reconciled(self):
        """reconcile() should NOT overwrite seo_analytics.total_search_volume."""
        report = _make_report(
            dashboard_search_volume=200000,
            seo_total_search_volume=125000,
        )
        validator = ReportConsistencyValidator()
        fixes, _ = validator.reconcile(report)
        # Volume should NOT have been reconciled
        assert report.seo_analytics.total_search_volume == 125000
        vol_fixes = [f for f in fixes if "total_search_volume" in f]
        assert len(vol_fixes) == 0


# ======================================================================
# Verdict vs Market Viability (Bug #21 fix)
# ======================================================================


def _make_state_with_viability(
    market_viability_verdict=None,
    recommended_entry_strategy=None,
    **kwargs,
):
    """Create a mock state with market_sizing viability fields."""
    state = _make_state(**kwargs)
    if market_viability_verdict is not None:
        if state.market_sizing is None:
            ms = MagicMock()
            state.market_sizing = ms
        state.market_sizing.market_viability_verdict = market_viability_verdict
        state.market_sizing.recommended_entry_strategy = recommended_entry_strategy
    else:
        if state.market_sizing is not None:
            state.market_sizing.market_viability_verdict = None
            state.market_sizing.recommended_entry_strategy = None
    return state


class TestViabilityVsVerdictConsistencyCheck:
    """Test _check_verdict_vs_viability consistency checks."""

    def test_go_weak_emits_warning(self):
        """Go verdict + Weak viability → WARNING."""
        report = _make_report(dashboard_verdict="Go")
        state = _make_state_with_viability(
            market_viability_verdict="Weak",
            recommended_entry_strategy="Enter",
            market_timing="Growth",
            trend_direction="Growing",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        viability_warnings = [
            w for w in warnings
            if "viability" in w.message.lower() and w.severity == "WARNING"
        ]
        assert len(viability_warnings) >= 1

    def test_go_reconsider_emits_warning(self):
        """Go verdict + Reconsider entry → WARNING."""
        report = _make_report(dashboard_verdict="Go")
        state = _make_state_with_viability(
            market_viability_verdict="Moderate",
            recommended_entry_strategy="Reconsider",
            market_timing="Growth",
            trend_direction="Growing",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        entry_warnings = [
            w for w in warnings
            if "entry strategy" in w.message.lower() and w.severity == "WARNING"
        ]
        assert len(entry_warnings) >= 1

    def test_conditional_weak_no_warning(self):
        """Conditional verdict + Weak viability → no viability WARNING (already Conditional)."""
        report = _make_report(dashboard_verdict="Conditional")
        state = _make_state_with_viability(
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
            market_timing="Growth",
            trend_direction="Growing",
        )
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        viability_warnings = [
            w for w in warnings
            if "viability" in w.message.lower() and w.severity == "WARNING"
        ]
        assert len(viability_warnings) == 0

    def test_missing_market_sizing_no_warning(self):
        """None market_sizing → no viability check."""
        report = _make_report(dashboard_verdict="Go")
        state = _make_state(include_market_sizing=False, include_trend=False)
        validator = ReportConsistencyValidator()
        warnings = validator.validate(report, state)
        viability_warnings = [
            w for w in warnings
            if "viability" in w.message.lower()
        ]
        assert len(viability_warnings) == 0
