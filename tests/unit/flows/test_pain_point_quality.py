"""Tests for _validate_pain_point_quality tier classification in ResearchFlow."""

import math
from unittest.mock import patch

import pytest

from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult


def _make_pain_point(
    severity: float = 0.8,
    wtp: float = 0.5,
    opportunity: OpportunityLevel = OpportunityLevel.HIGH,
    num_quotes: int = 10,
    platforms: list[str] | None = None,
    num_source_ids: int | None = None,
) -> PainPoint:
    """Helper to create a PainPoint with configurable fields."""
    if platforms is None:
        platforms = ["Reddit"]
    if num_source_ids is None:
        num_source_ids = num_quotes
    quotes = [f"Quote text number {i} with enough words" for i in range(num_quotes)]
    source_ids = [f"post_{i}" for i in range(num_source_ids)]
    return PainPoint(
        title="Test Pain Point",
        description="A test pain point description",
        mention_count=50,
        severity_score=severity,
        willingness_to_pay=wtp,
        opportunity_level=opportunity,
        representative_quotes=quotes,
        source_platforms=platforms,
        categories=["TestCategory"],
        source_post_ids=source_ids,
    )


def _make_analysis(pain_points: list[PainPoint]) -> PainPointAnalysisResult:
    """Helper to create a PainPointAnalysisResult."""
    return PainPointAnalysisResult(
        niche="Test Niche",
        pain_points=pain_points,
        total_mentions=sum(pp.mention_count for pp in pain_points),
        top_categories=["TestCategory"],
        analysis_summary="Test summary",
    )


def _validate(analysis, enable_twitter=True, enable_reddit=True):
    """Run _validate_pain_point_quality with mocked settings."""
    from nicheiq.flows.research_flow import ResearchFlow

    flow = ResearchFlow.__new__(ResearchFlow)
    with patch("nicheiq.flows.research_flow.settings") as mock_settings:
        mock_settings.enable_twitter = enable_twitter
        mock_settings.enable_reddit = enable_reddit
        return flow._validate_pain_point_quality(analysis)


# =============================================================================
# GOLD tier tests
# =============================================================================


class TestGoldTier:
    def test_gold_tier_with_strong_data(self):
        """7 PPs, 5 high severity, quote_density=9, dual-platform → GOLD."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(5)
        ] + [
            _make_pain_point(severity=0.5, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(2)
        ]
        analysis = _make_analysis(pps)
        tier, score = _validate(analysis)
        assert tier == "GOLD"
        assert 0.0 <= score <= 1.0

    def test_gold_tier_single_platform_skips_source_coverage(self):
        """5 PPs, 3 high severity, quote_density=9, single-platform, source_coverage=0.4 → GOLD."""
        # With 5 PPs: gold_severity_min = max(2, ceil(5*0.6)) = 3
        # gold_opportunity_min = max(1, ceil(5*0.4)) = 2
        pps = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit"], num_source_ids=4)
            for _ in range(3)
        ] + [
            _make_pain_point(
                severity=0.4, num_quotes=9, platforms=["Reddit"],
                opportunity=OpportunityLevel.MEDIUM, num_source_ids=0,
            )
            for _ in range(2)
        ]
        analysis = _make_analysis(pps)
        # Single platform: source_coverage gate skipped, cross_platform gate skipped
        tier, score = _validate(analysis, enable_twitter=False)
        assert tier == "GOLD"


# =============================================================================
# SILVER tier tests
# =============================================================================


class TestSilverTier:
    def test_silver_tier_moderate_data(self):
        """5 PPs, 2 high severity, quote_density=6, source_coverage=0.8 → SILVER."""
        # silver_severity_min = max(1, ceil(5*0.4)) = 2
        pps = [
            _make_pain_point(severity=0.8, num_quotes=6, platforms=["Reddit"])
            for _ in range(2)
        ] + [
            _make_pain_point(
                severity=0.4, num_quotes=6, platforms=["Reddit"],
                opportunity=OpportunityLevel.LOW,
            )
            for _ in range(3)
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        assert tier == "SILVER"

    def test_silver_tier_combined_severity(self):
        """5 PPs, 1 high + 2 medium (combined=3 >= ceil(5*0.6)=3), quote_density=6 → SILVER."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=6, platforms=["Reddit"]),
            _make_pain_point(severity=0.6, num_quotes=6, platforms=["Reddit"],
                             opportunity=OpportunityLevel.MEDIUM),
            _make_pain_point(severity=0.6, num_quotes=6, platforms=["Reddit"],
                             opportunity=OpportunityLevel.MEDIUM),
            _make_pain_point(severity=0.3, num_quotes=6, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
            _make_pain_point(severity=0.3, num_quotes=6, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        assert tier == "SILVER"

    def test_silver_single_platform_skips_source_coverage(self):
        """5 PPs, 2 high, quote_density=6, source_coverage=0.3, single-platform → SILVER."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=6, platforms=["Reddit"], num_source_ids=1)
            for _ in range(2)
        ] + [
            _make_pain_point(
                severity=0.3, num_quotes=6, platforms=["Reddit"],
                opportunity=OpportunityLevel.LOW, num_source_ids=0,
            )
            for _ in range(3)
        ]
        # source_coverage = 2/5 = 0.4, below 0.70 threshold, but single_platform bypasses it
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, enable_twitter=False)
        assert tier == "SILVER"


# =============================================================================
# BRONZE tier tests
# =============================================================================


class TestBronzeTier:
    def test_bronze_tier_minimum_viable(self):
        """3 PPs, 1 high, quote_density=4, source_coverage=0.6 → BRONZE."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=4, platforms=["Reddit"]),
            _make_pain_point(severity=0.4, num_quotes=4, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
            _make_pain_point(severity=0.3, num_quotes=4, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        # source_coverage = 3/3 = 1.0 (all have source_post_ids), quote_density=4
        # silver_severity_min = max(1, ceil(3*0.4)) = 2; only 1 high → not SILVER via severity
        # silver_combined_min = max(2, ceil(3*0.6)) = 2; high+med = 1+0 = 1 < 2 → not SILVER combined
        # BRONZE: total>=2 ✓, quote_density>=3 ✓, source_coverage>=0.50 ✓
        assert tier == "BRONZE"

    def test_bronze_single_platform(self):
        """3 PPs, 1 high, quote_density=4, source_coverage=0.2, single-platform → BRONZE."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=4, platforms=["Reddit"], num_source_ids=4),
            _make_pain_point(severity=0.3, num_quotes=4, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW, num_source_ids=0),
            _make_pain_point(severity=0.3, num_quotes=4, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW, num_source_ids=0),
        ]
        # source_coverage = 1/3 ≈ 0.33, below 0.50 but single_platform bypasses
        # Only 1 high severity, silver_severity_min = max(1, ceil(3*0.4)) = 2 → not SILVER
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis, enable_twitter=False)
        assert tier == "BRONZE"


# =============================================================================
# INSUFFICIENT tier tests
# =============================================================================


class TestInsufficientTier:
    def test_insufficient_low_quote_density(self):
        """3 PPs, quote_density=1 → INSUFFICIENT."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=1, platforms=["Reddit"]),
            _make_pain_point(severity=0.5, num_quotes=1, platforms=["Reddit"],
                             opportunity=OpportunityLevel.MEDIUM),
            _make_pain_point(severity=0.3, num_quotes=1, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        assert tier == "INSUFFICIENT"

    def test_insufficient_too_few_pain_points(self):
        """1 PP with low quote density → INSUFFICIENT (can't reach BRONZE total_count>=2)."""
        pps = [
            _make_pain_point(severity=0.9, num_quotes=2, platforms=["Reddit"],
                             opportunity=OpportunityLevel.LOW),
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        # total_count=1 < 2 (BRONZE floor), quote_density=2 < 5 (SILVER), so INSUFFICIENT
        assert tier == "INSUFFICIENT"

    def test_insufficient_empty_pain_points(self):
        """0 PPs → INSUFFICIENT."""
        analysis = _make_analysis([])
        tier, score = _validate(analysis)
        assert tier == "INSUFFICIENT"
        assert score == 0.0


# =============================================================================
# Percentage threshold scaling tests
# =============================================================================


class TestPercentageThresholds:
    def test_percentage_thresholds_scale_with_count(self):
        """10 PPs, 5 high → needs ceil(10*0.6)=6 for GOLD → falls to SILVER."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(5)
        ] + [
            _make_pain_point(severity=0.4, num_quotes=9, platforms=["Reddit", "Twitter"],
                             opportunity=OpportunityLevel.LOW)
            for _ in range(5)
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        # gold_severity_min = max(2, ceil(10*0.6)) = 6; only 5 high → not GOLD
        # silver_severity_min = max(1, ceil(10*0.4)) = 4; 5 >= 4 → SILVER (if other criteria met)
        assert tier == "SILVER"

    def test_percentage_thresholds_small_count(self):
        """3 PPs, 2 high → max(2, ceil(3*0.6)=2) → GOLD if other criteria met."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(2)
        ] + [
            _make_pain_point(severity=0.4, num_quotes=9, platforms=["Reddit", "Twitter"],
                             opportunity=OpportunityLevel.LOW)
        ]
        analysis = _make_analysis(pps)
        tier, _ = _validate(analysis)
        # gold_severity_min = max(2, ceil(3*0.6)) = 2 → 2 >= 2 ✓
        # gold_opportunity_min = max(1, ceil(3*0.4)) = 2 → high_opportunity=2 ✓
        # quote_density = 9 >= 8 ✓
        # cross_platform (dual mode): 3 >= 3 ✓
        # source_coverage = 3/3 = 1.0 >= 0.90 ✓
        assert tier == "GOLD"


# =============================================================================
# Confidence score tests
# =============================================================================


class TestConfidenceScore:
    def test_confidence_score_single_platform_no_cross_platform_weight(self):
        """Verify cross_platform weight=0 in single-platform mode."""
        pps = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit"])
            for _ in range(5)
        ]
        analysis = _make_analysis(pps)
        _, score = _validate(analysis, enable_twitter=False)
        # In single-platform mode, cross_platform weight is 0.0
        # All other weights sum to 1.0 (0.25+0.20+0.30+0.0+0.15+0.10)
        assert 0.0 < score <= 1.0

        # Compare with a case where we artificially give cross-platform data
        # but keep single-platform mode — cross_platform should still be 0
        pps_cross = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(5)
        ]
        analysis_cross = _make_analysis(pps_cross)
        _, score_cross = _validate(analysis_cross, enable_twitter=False)
        # Score should be identical since cross_platform weight is 0
        assert abs(score - score_cross) < 0.01

    def test_confidence_score_dual_platform(self):
        """Verify cross_platform weight=0.15 in dual-platform mode."""
        # All single-platform pain points
        pps_single = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit"])
            for _ in range(5)
        ]
        analysis_single = _make_analysis(pps_single)
        _, score_single = _validate(analysis_single)

        # Same but all cross-platform
        pps_cross = [
            _make_pain_point(severity=0.8, num_quotes=9, platforms=["Reddit", "Twitter"])
            for _ in range(5)
        ]
        analysis_cross = _make_analysis(pps_cross)
        _, score_cross = _validate(analysis_cross)

        # Cross-platform version should score higher due to 0.15 cross_platform weight
        assert score_cross > score_single
        # The difference should be approximately 0.15 (cross_platform_count/total * 0.15)
        assert abs(score_cross - score_single - 0.15) < 0.05
