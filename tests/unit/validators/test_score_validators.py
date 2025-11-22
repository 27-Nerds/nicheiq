"""
Unit tests for score validators.

Tests VerdictValidator and ScoreThresholds with various scenarios,
edge cases, and custom threshold configurations.
"""

import pytest

from nicheiq.validators import ScoreThresholds, VerdictValidator


class TestScoreThresholds:
    """Test ScoreThresholds model validation."""

    def test_default_values(self):
        """Test default threshold values match production config."""
        thresholds = ScoreThresholds()

        # Market validation
        assert thresholds.market_validation_strong_volume == 100_000
        assert thresholds.market_validation_strong_pain_points == 10
        assert thresholds.market_validation_moderate_volume == 30_000
        assert thresholds.market_validation_moderate_pain_points == 5

        # Verdict thresholds
        assert thresholds.verdict_go_avg_score == 0.75
        assert thresholds.verdict_go_min_individual_score == 0.7
        assert thresholds.verdict_conditional_avg_score == 0.60
        assert thresholds.verdict_conditional_min_individual_score == 0.55

        # Pain point & competitive
        assert thresholds.pain_point_high_priority_threshold == 0.7
        assert thresholds.competitive_intensity_low_threshold == 3
        assert thresholds.competitive_intensity_high_threshold == 8

        # Score defaults
        assert thresholds.score_accessor_default_fallback == 0.5

    def test_custom_values(self):
        """Test custom threshold configuration."""
        thresholds = ScoreThresholds(
            verdict_go_avg_score=0.80,
            verdict_go_min_individual_score=0.75,
            market_validation_strong_volume=150_000,
        )

        assert thresholds.verdict_go_avg_score == 0.80
        assert thresholds.verdict_go_min_individual_score == 0.75
        assert thresholds.market_validation_strong_volume == 150_000

    def test_score_validation_constraints(self):
        """Test that score fields enforce 0.0-1.0 range."""
        # Valid scores
        ScoreThresholds(verdict_go_avg_score=0.0)
        ScoreThresholds(verdict_go_avg_score=1.0)
        ScoreThresholds(verdict_go_avg_score=0.5)

        # Invalid scores
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            ScoreThresholds(verdict_go_avg_score=-0.1)

        with pytest.raises(ValueError, match="less than or equal to 1"):
            ScoreThresholds(verdict_go_avg_score=1.1)


class TestVerdictValidator:
    """Test VerdictValidator logic."""

    def test_go_verdict_all_thresholds_met(self):
        """Test Go verdict when all thresholds exceeded."""
        validator = VerdictValidator()

        verdict, rationale = validator.validate_go_verdict(
            avg_score=0.80,
            market_fit=0.75,
            tech_feasibility=0.72,
        )

        assert verdict == "Go"
        assert "0.80" in rationale
        assert "0.75" in rationale
        assert "0.72" in rationale

    def test_go_verdict_boundary_case(self):
        """Test Go verdict at exact threshold boundary."""
        validator = VerdictValidator()

        # Exactly at threshold (should pass)
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.75,  # Exactly at threshold
            market_fit=0.7,  # Exactly at threshold
            tech_feasibility=0.7,
        )

        assert verdict == "Go"

    def test_conditional_verdict(self):
        """Test Conditional verdict when Go thresholds not met."""
        validator = VerdictValidator()

        verdict, rationale = validator.validate_go_verdict(
            avg_score=0.65,  # Between conditional and go
            market_fit=0.60,
            tech_feasibility=0.58,
        )

        assert verdict == "Conditional"
        assert "0.65" in rationale

    def test_nogo_verdict(self):
        """Test No-Go verdict when all thresholds missed."""
        validator = VerdictValidator()

        verdict, rationale = validator.validate_go_verdict(
            avg_score=0.45,
            market_fit=0.40,
            tech_feasibility=0.38,
        )

        assert verdict == "No-Go"
        assert "0.45" in rationale

    def test_custom_thresholds(self):
        """Test verdict calculation with custom thresholds."""
        # More conservative thresholds
        thresholds = ScoreThresholds(
            verdict_go_avg_score=0.85,
            verdict_go_min_individual_score=0.80,
        )
        validator = VerdictValidator(thresholds)

        # These scores would be "Go" with default thresholds
        verdict, _ = validator.validate_go_verdict(
            avg_score=0.78,
            market_fit=0.75,
            tech_feasibility=0.72,
        )

        # But with conservative thresholds, should be Conditional or No-Go
        assert verdict in ["Conditional", "No-Go"]

    def test_market_validation_strong(self):
        """Test STRONG market validation level."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=150_000,
            pain_point_count=12,
        )

        assert level == "STRONG"

    def test_market_validation_moderate(self):
        """Test MODERATE market validation level."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=50_000,  # Between moderate and strong
            pain_point_count=7,
        )

        assert level == "MODERATE"

    def test_market_validation_weak(self):
        """Test WEAK market validation level."""
        validator = VerdictValidator()

        level = validator.validate_market_validation_level(
            total_volume=10_000,
            pain_point_count=2,
        )

        assert level == "WEAK"

    def test_competitive_intensity_low(self):
        """Test Low competitive intensity."""
        validator = VerdictValidator()

        intensity = validator.classify_competitive_intensity(competitor_count=2)

        assert intensity == "Low"

    def test_competitive_intensity_medium(self):
        """Test Medium competitive intensity."""
        validator = VerdictValidator()

        intensity = validator.classify_competitive_intensity(competitor_count=5)

        assert intensity == "Medium"

    def test_competitive_intensity_high(self):
        """Test High competitive intensity."""
        validator = VerdictValidator()

        intensity = validator.classify_competitive_intensity(competitor_count=10)

        assert intensity == "High"

    def test_competitive_intensity_boundaries(self):
        """Test competitive intensity at threshold boundaries."""
        validator = VerdictValidator()

        # At low threshold (3) - should be Medium
        assert validator.classify_competitive_intensity(3) == "Medium"

        # Just below low threshold - should be Low
        assert validator.classify_competitive_intensity(2) == "Low"

        # At high threshold (8) - should be High
        assert validator.classify_competitive_intensity(8) == "High"

        # Just below high threshold - should be Medium
        assert validator.classify_competitive_intensity(7) == "Medium"

    def test_high_priority_pain_point(self):
        """Test high priority pain point classification."""
        validator = VerdictValidator()

        # High priority (>= 0.7)
        assert validator.is_high_priority_pain_point(0.8) is True
        assert validator.is_high_priority_pain_point(0.7) is True

        # Not high priority
        assert validator.is_high_priority_pain_point(0.69) is False
        assert validator.is_high_priority_pain_point(0.5) is False

    @pytest.mark.parametrize(
        "avg_score,market_fit,tech_feasibility,expected_verdict",
        [
            # Strong Go cases
            (0.90, 0.85, 0.88, "Go"),
            (0.75, 0.70, 0.70, "Go"),  # Boundary
            # Conditional cases
            (0.65, 0.60, 0.58, "Conditional"),
            (0.60, 0.55, 0.55, "Conditional"),  # Boundary
            # No-Go cases
            (0.50, 0.45, 0.48, "No-Go"),
            (0.30, 0.25, 0.28, "No-Go"),
            # Edge case: high avg but low individual
            (0.80, 0.50, 0.90, "No-Go"),  # market_fit too low even for Conditional (< 0.55)
        ],
    )
    def test_verdict_parametrized(
        self,
        avg_score,
        market_fit,
        tech_feasibility,
        expected_verdict,
    ):
        """Test verdict calculation with parametrized inputs."""
        validator = VerdictValidator()

        verdict, _ = validator.validate_go_verdict(
            avg_score=avg_score,
            market_fit=market_fit,
            tech_feasibility=tech_feasibility,
        )

        assert verdict == expected_verdict
