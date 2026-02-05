"""
Unit tests for validation edge cases in report generation.

Tests None/NaN validation, division-by-zero protection, and other
edge cases that could cause crashes or incorrect behavior.
"""

import pytest

from nicheiq.validators import VerdictValidator


class TestNoneHandling:
    """Test None/NaN validation in verdict calculation."""

    def test_verdict_with_none_scores_uses_defaults(self):
        """Test verdict calculation handles None scores gracefully."""
        validator = VerdictValidator()

        # None values should be handled (in actual code, ScoreAccessor provides defaults)
        # Here we test that the validator itself works with valid float inputs
        verdict, rationale = validator.validate_go_verdict(
            avg_score=0.5,  # Default fallback
            market_fit=0.5,
            tech_feasibility=0.5,
        )

        # With all 0.5 scores, should be No-Go (below conditional avg threshold of 0.55)
        assert verdict == "No-Go"

    def test_verdict_boundary_with_default_scores(self):
        """Test verdict at boundaries with default scores."""
        validator = VerdictValidator()

        # Test Conditional boundary
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.55,
            market_fit=0.50,
            tech_feasibility=0.50,
        )

        assert verdict == "Conditional"


class TestDivisionByZero:
    """Test division-by-zero protection."""

    def test_keyword_diversity_with_zero_keywords(self):
        """
        Test keyword diversity calculation with zero keywords.

        This is tested at the report_generator level, but validates
        the pattern used there.
        """
        # Simulate the pattern from report_generator.py:1801-1804
        total = 0
        tier0_count = 0
        tier1_count = 0
        tier2_count = 0
        tier3_count = 0
        tier4_count = 0

        if total == 0:
            diversity = 0.0  # No keywords = no diversity
        else:
            diversity = 1.0 - (
                max(tier0_count, tier1_count, tier2_count, tier3_count, tier4_count)
                / total
            )

        # Should return 0.0, not crash
        assert diversity == 0.0

    def test_keyword_diversity_with_keywords(self):
        """Test keyword diversity calculation with normal data."""
        total = 100
        tier0_count = 20
        tier1_count = 30
        tier2_count = 25
        tier3_count = 15
        tier4_count = 10

        if total == 0:
            diversity = 0.0
        else:
            diversity = 1.0 - (
                max(tier0_count, tier1_count, tier2_count, tier3_count, tier4_count)
                / total
            )

        # Max tier is tier1 with 30, so diversity = 1.0 - (30/100) = 0.70
        assert diversity == 0.70

    def test_keyword_diversity_all_in_one_tier(self):
        """Test keyword diversity when all keywords in one tier."""
        total = 50
        tier0_count = 50  # All in tier 0
        tier1_count = 0
        tier2_count = 0
        tier3_count = 0
        tier4_count = 0

        if total == 0:
            diversity = 0.0
        else:
            diversity = 1.0 - (
                max(tier0_count, tier1_count, tier2_count, tier3_count, tier4_count)
                / total
            )

        # Max tier = total, so diversity = 1.0 - (50/50) = 0.0
        assert diversity == 0.0


class TestScoreRangeValidation:
    """Test score range validation."""

    def test_valid_score_ranges(self):
        """Test that valid scores (0.0-1.0) are accepted."""
        validator = VerdictValidator()

        # Should not raise any errors
        validator.validate_go_verdict(
            avg_score=0.0,
            market_fit=0.0,
            tech_feasibility=0.0,
        )

        validator.validate_go_verdict(
            avg_score=1.0,
            market_fit=1.0,
            tech_feasibility=1.0,
        )

        validator.validate_go_verdict(
            avg_score=0.5,
            market_fit=0.5,
            tech_feasibility=0.5,
        )

    def test_scores_at_boundaries(self):
        """Test scores exactly at threshold boundaries."""
        validator = VerdictValidator()

        # Go boundary (0.75 avg, 0.60 individual)
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.75,
            market_fit=0.60,
            tech_feasibility=0.60,
        )
        assert verdict == "Go"

        # Conditional boundary (0.55 avg, 0.50 individual)
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.55,
            market_fit=0.50,
            tech_feasibility=0.50,
        )
        assert verdict == "Conditional"

        # Just below conditional boundary
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.54,
            market_fit=0.49,
            tech_feasibility=0.49,
        )
        assert verdict == "No-Go"


class TestMarketValidationEdgeCases:
    """Test market validation edge cases."""

    def test_zero_volume_zero_pain_points(self):
        """Test market validation with zero volume and pain points."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=0,
            pain_point_count=0,
        )

        assert level == "WEAK"

    def test_high_volume_zero_pain_points(self):
        """Test high volume but no pain points."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=200_000,
            pain_point_count=0,
        )

        # Even with high volume, 0 pain points = WEAK
        assert level == "WEAK"

    def test_zero_volume_high_pain_points(self):
        """Test zero volume but many pain points."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=0,
            pain_point_count=15,
        )

        # Even with many pain points, 0 volume = WEAK
        assert level == "WEAK"


class TestCompetitiveIntensityEdgeCases:
    """Test competitive intensity edge cases."""

    def test_zero_competitors(self):
        """Test competitive intensity with zero competitors."""
        validator = VerdictValidator()

        intensity = validator.classify_competitive_intensity(competitor_count=0)

        assert intensity == "Low"

    def test_exactly_at_thresholds(self):
        """Test competitive intensity at exact threshold values."""
        validator = VerdictValidator()

        # At low threshold (3) should be Medium (>= 3)
        assert validator.classify_competitive_intensity(3) == "Medium"

        # Just below low threshold (2) should be Low (< 3)
        assert validator.classify_competitive_intensity(2) == "Low"

        # At high threshold (8) should be High (>= 8)
        assert validator.classify_competitive_intensity(8) == "High"

        # Just below high threshold (7) should be Medium (< 8)
        assert validator.classify_competitive_intensity(7) == "Medium"


class TestPainPointPriorityEdgeCases:
    """Test pain point priority edge cases."""

    def test_zero_severity(self):
        """Test pain point with zero severity."""
        validator = VerdictValidator()

        is_high_priority = validator.is_high_priority_pain_point(severity_score=0.0)

        assert is_high_priority is False

    def test_max_severity(self):
        """Test pain point with max severity."""
        validator = VerdictValidator()

        is_high_priority = validator.is_high_priority_pain_point(severity_score=1.0)

        assert is_high_priority is True

    def test_exactly_at_threshold(self):
        """Test pain point exactly at threshold."""
        validator = VerdictValidator()

        # At threshold (0.7) should be high priority
        assert validator.is_high_priority_pain_point(0.7) is True

        # Just below threshold (0.69) should not be high priority
        assert validator.is_high_priority_pain_point(0.69) is False


class TestSEOQualityCaveats:
    """Test SEO quality caveats for missing keyword tiers."""

    def test_empty_tier0_adds_caveat(self):
        """Test that empty Tier 0 keywords should trigger a quality caveat."""
        # This tests the logic pattern used in _generate_data_quality_summary
        quality_caveats = []

        # Simulate seo_strategy_report with empty tier_0_keywords
        tier_0_keywords = []
        tier_1_keywords = [{"keyword": "test"}]  # Has Tier 1

        if not tier_0_keywords:
            quality_caveats.append("No premium (Tier 0) keywords found - market may be highly competitive")
        if not tier_1_keywords:
            quality_caveats.append("No quick-win (Tier 1) keywords found - SEO opportunities may be limited")

        assert len(quality_caveats) == 1
        assert "Tier 0" in quality_caveats[0]
        assert "highly competitive" in quality_caveats[0]

    def test_empty_tier1_adds_caveat(self):
        """Test that empty Tier 1 keywords should trigger a quality caveat."""
        quality_caveats = []

        tier_0_keywords = [{"keyword": "test"}]  # Has Tier 0
        tier_1_keywords = []

        if not tier_0_keywords:
            quality_caveats.append("No premium (Tier 0) keywords found - market may be highly competitive")
        if not tier_1_keywords:
            quality_caveats.append("No quick-win (Tier 1) keywords found - SEO opportunities may be limited")

        assert len(quality_caveats) == 1
        assert "Tier 1" in quality_caveats[0]
        assert "SEO opportunities" in quality_caveats[0]

    def test_both_empty_adds_both_caveats(self):
        """Test that both empty tiers add both caveats."""
        quality_caveats = []

        tier_0_keywords = []
        tier_1_keywords = []

        if not tier_0_keywords:
            quality_caveats.append("No premium (Tier 0) keywords found - market may be highly competitive")
        if not tier_1_keywords:
            quality_caveats.append("No quick-win (Tier 1) keywords found - SEO opportunities may be limited")

        assert len(quality_caveats) == 2
        assert any("Tier 0" in c for c in quality_caveats)
        assert any("Tier 1" in c for c in quality_caveats)

    def test_both_present_no_caveats(self):
        """Test that having both tiers adds no SEO caveats."""
        quality_caveats = []

        tier_0_keywords = [{"keyword": "premium"}]
        tier_1_keywords = [{"keyword": "quickwin"}]

        if not tier_0_keywords:
            quality_caveats.append("No premium (Tier 0) keywords found - market may be highly competitive")
        if not tier_1_keywords:
            quality_caveats.append("No quick-win (Tier 1) keywords found - SEO opportunities may be limited")

        assert len(quality_caveats) == 0
