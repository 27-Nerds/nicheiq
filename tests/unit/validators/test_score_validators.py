"""
Unit tests for score validators.

Tests VerdictValidator and ScoreThresholds with various scenarios,
edge cases, and custom threshold configurations.
"""

import pytest

from nicheiq.validators import (
    ConfidenceAdjuster,
    ConfidenceThresholds,
    ScoreThresholds,
    VerdictValidator,
)


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

        # Confidence thresholds (composed)
        assert isinstance(thresholds.confidence, ConfidenceThresholds)
        assert thresholds.confidence.pain_point_bronze == 0.85
        assert thresholds.confidence.floor == 0.10

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


# ==============================================================================
# Trend Downgrade Tests
# ==============================================================================

class TestTrendDowngradeRules:
    """Test each trend downgrade rule in isolation."""

    def _base_kwargs(self, **overrides):
        """Return default 'healthy' trend kwargs, with overrides."""
        defaults = dict(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Growing",
            momentum_score=0.8,
            timing_recommendation="Enter Now",
            longevity_verdict="Sustainable",
            market_maturity="Growth",
        )
        defaults.update(overrides)
        return defaults

    def test_rule1_declining_missed_window_caps_conditional(self):
        """Rule 1: Declining + Missed Window → cap Go at Conditional, risk >= Medium."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                trend_direction="Declining",
                timing_recommendation="Missed Window",
            )
        )
        assert v == "Conditional"
        assert r == "Medium"
        assert tc is not None
        assert "Declining" in tc
        assert "Missed Window" in tc

    def test_rule1_conditional_stays_conditional(self):
        """Rule 1: Conditional stays Conditional (not downgraded to No-Go)."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Conditional",
                risk_level="Medium",
                trend_direction="Declining",
                timing_recommendation="Missed Window",
            )
        )
        assert v == "Conditional"
        assert r == "Medium"

    def test_rule1_nogo_stays_nogo(self):
        """Rule 1: No-Go is not changed."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="No-Go",
                risk_level="High",
                trend_direction="Declining",
                timing_recommendation="Missed Window",
            )
        )
        assert v == "No-Go"
        assert r == "High"

    def test_rule2_fad_caps_conditional(self):
        """Rule 2: Fad longevity → cap Go at Conditional, risk >= Medium."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                longevity_verdict="Fad",
            )
        )
        assert v == "Conditional"
        assert r == "Medium"
        assert tc is not None
        assert "Fad" in tc

    def test_rule2_fad_risk_already_high(self):
        """Rule 2: Fad with High risk stays High."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="High",
                longevity_verdict="Fad",
            )
        )
        assert v == "Conditional"
        assert r == "High"

    def test_rule3_declining_downgrades_go_only(self):
        """Rule 3: Declining trend downgrades Go→Conditional."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                trend_direction="Declining",
                timing_recommendation="Enter Now",  # not Missed Window, so rule 1 doesn't fire
                longevity_verdict="Sustainable",  # not Fad, so rule 2 doesn't fire
            )
        )
        assert v == "Conditional"
        assert tc is not None
        assert "Declining" in tc

    def test_rule3_conditional_not_downgraded(self):
        """Rule 3: Conditional is NOT downgraded to No-Go."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Conditional",
                risk_level="Medium",
                trend_direction="Declining",
                timing_recommendation="Enter Now",
                longevity_verdict="Sustainable",
            )
        )
        assert v == "Conditional"
        assert tc is None  # no change made

    def test_rule4_risky_downgrades_go_only(self):
        """Rule 4: Risky longevity downgrades Go→Conditional."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                trend_direction="Stable",  # not Declining, so rule 1/3 don't fire
                longevity_verdict="Risky",
            )
        )
        assert v == "Conditional"
        assert tc is not None
        assert "Risky" in tc

    def test_rule4_conditional_not_downgraded(self):
        """Rule 4: Conditional not downgraded from Risky longevity."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Conditional",
                risk_level="Medium",
                trend_direction="Stable",
                longevity_verdict="Risky",
            )
        )
        assert v == "Conditional"
        assert tc is None

    def test_rule5_monitor_wait_raises_risk_low_to_medium(self):
        """Rule 5: Monitor & Wait raises risk Low→Medium."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                timing_recommendation="Monitor & Wait",
            )
        )
        assert v == "Go"  # verdict unchanged (no declining/fad/risky)
        assert r == "Medium"
        assert tc is not None
        assert "Monitor & Wait" in tc

    def test_rule5_monitor_wait_raises_risk_medium_to_high(self):
        """Rule 5: Monitor & Wait raises risk Medium→High."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Conditional",
                risk_level="Medium",
                timing_recommendation="Monitor & Wait",
            )
        )
        assert v == "Conditional"
        assert r == "High"
        assert tc is not None

    def test_rule5_already_high_stays_high(self):
        """Rule 5: Already High risk stays High."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="No-Go",
                risk_level="High",
                timing_recommendation="Monitor & Wait",
            )
        )
        assert r == "High"
        assert tc is None  # no actual change

    def test_rule5_additive_with_rule1(self):
        """Rule 5 is additive: Declining+Missed Window+Monitor&Wait shouldn't happen,
        but if timing is Monitor & Wait combined with declining, both rules can apply."""
        validator = VerdictValidator()
        # Rule 3 fires (declining but not missed window), then Rule 5 fires (monitor & wait)
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                trend_direction="Declining",
                timing_recommendation="Monitor & Wait",
                longevity_verdict="Sustainable",
            )
        )
        assert v == "Conditional"  # Rule 3
        assert r == "Medium"  # Rule 5
        assert tc is not None

    def test_rule1_takes_priority_over_rule2(self):
        """Rule 1 (Declining+Missed Window) takes priority over Rule 2 (Fad)."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                verdict="Go",
                risk_level="Low",
                trend_direction="Declining",
                timing_recommendation="Missed Window",
                longevity_verdict="Fad",
            )
        )
        assert "Declining" in tc
        assert "Missed Window" in tc


class TestNoDowngradeScenarios:
    """Test that healthy trends cause no verdict changes."""

    def _base_kwargs(self, **overrides):
        defaults = dict(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Growing",
            momentum_score=0.8,
            timing_recommendation="Enter Now",
            longevity_verdict="Sustainable",
            market_maturity="Growth",
        )
        defaults.update(overrides)
        return defaults

    def test_growing_enter_now_sustainable_no_change(self):
        """Growing + Enter Now + Sustainable = no downgrade."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(**self._base_kwargs())
        assert v == "Go"
        assert r == "Low"
        assert tc is None

    def test_stable_enter_now_sustainable_no_change(self):
        """Stable + Enter Now + Sustainable = no downgrade."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(trend_direction="Stable")
        )
        assert v == "Go"
        assert r == "Low"
        assert tc is None

    def test_growing_enter_now_risky_still_downgrades(self):
        """Growing + Enter Now + Risky → Rule 4 fires."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(longevity_verdict="Risky")
        )
        assert v == "Conditional"
        assert tc is not None

    @pytest.mark.parametrize(
        "verdict,risk",
        [("Go", "Low"), ("Conditional", "Medium"), ("No-Go", "High")],
    )
    def test_all_verdicts_unchanged_with_healthy_trends(self, verdict, risk):
        """All verdict levels unchanged with fully healthy trends."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(verdict=verdict, risk_level=risk)
        )
        assert v == verdict
        assert r == risk
        assert tc is None


class TestTrendDowngradeCustomThresholds:
    """Test disabling individual rules via ScoreThresholds flags."""

    def _base_kwargs(self, **overrides):
        defaults = dict(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Fad",
            market_maturity="Mature",
        )
        defaults.update(overrides)
        return defaults

    def test_disable_rule1(self):
        """Disabling rule 1 allows rule 2 (Fad) to fire instead."""
        thresholds = ScoreThresholds(trend_missed_window_caps_conditional=False)
        validator = VerdictValidator(thresholds)
        v, r, pc, tc = validator.apply_trend_downgrade(**self._base_kwargs())
        assert v == "Conditional"
        assert "Fad" in tc

    def test_disable_rule1_and_rule2(self):
        """Disabling rules 1+2 allows rule 3 (Declining) to fire."""
        thresholds = ScoreThresholds(
            trend_missed_window_caps_conditional=False,
            trend_fad_caps_conditional=False,
        )
        validator = VerdictValidator(thresholds)
        v, r, pc, tc = validator.apply_trend_downgrade(**self._base_kwargs())
        assert v == "Conditional"
        assert "Declining" in tc

    def test_disable_rules_1_2_3(self):
        """Disabling rules 1-3, rule 4 doesn't fire because longevity is Fad not Risky."""
        thresholds = ScoreThresholds(
            trend_missed_window_caps_conditional=False,
            trend_fad_caps_conditional=False,
            trend_declining_downgrades_go=False,
        )
        validator = VerdictValidator(thresholds)
        # Fad is not Risky, so rule 4 doesn't fire. Only rule 5 may fire.
        v, r, pc, tc = validator.apply_trend_downgrade(**self._base_kwargs())
        assert v == "Go"  # no rules 1-4 fired

    def test_disable_rule5(self):
        """Disabling rule 5 prevents risk raise from Monitor & Wait."""
        thresholds = ScoreThresholds(trend_monitor_wait_raises_risk=False)
        validator = VerdictValidator(thresholds)
        v, r, pc, tc = validator.apply_trend_downgrade(
            **self._base_kwargs(
                trend_direction="Growing",
                timing_recommendation="Monitor & Wait",
                longevity_verdict="Sustainable",
            )
        )
        assert v == "Go"
        assert r == "Low"
        assert tc is None

    def test_all_rules_disabled_no_change(self):
        """All rules disabled → no changes at all."""
        thresholds = ScoreThresholds(
            trend_missed_window_caps_conditional=False,
            trend_fad_caps_conditional=False,
            trend_declining_downgrades_go=False,
            trend_risky_downgrades_go=False,
            trend_monitor_wait_raises_risk=False,
        )
        validator = VerdictValidator(thresholds)
        v, r, pc, tc = validator.apply_trend_downgrade(**self._base_kwargs())
        assert v == "Go"
        assert r == "Low"
        assert tc is None


class TestTrendDowngradePrimaryConcern:
    """Verify primary_concern handling during trend downgrades."""

    def test_existing_concern_preserved(self):
        """Existing primary_concern is NOT overwritten by trend downgrade."""
        validator = VerdictValidator()
        existing_concern = "Low market fit score (0.58)"
        v, r, pc, tc = validator.apply_trend_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=existing_concern,
            trend_direction="Declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Sustainable",
            market_maturity="Mature",
        )
        assert pc == existing_concern
        assert tc is not None

    def test_concern_set_when_none(self):
        """primary_concern is set from trend when originally None."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Sustainable",
            market_maturity="Mature",
        )
        assert pc is not None
        assert "Declining" in pc
        assert tc is not None

    def test_no_concern_set_when_no_downgrade(self):
        """No primary_concern set when trend is healthy and no downgrade."""
        validator = VerdictValidator()
        v, r, pc, tc = validator.apply_trend_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Growing",
            momentum_score=0.8,
            timing_recommendation="Enter Now",
            longevity_verdict="Sustainable",
            market_maturity="Growth",
        )
        assert pc is None
        assert tc is None


# ==============================================================================
# Confidence Adjuster Tests
# ==============================================================================


# ==============================================================================
# Market Viability Downgrade Tests (Phase 3)
# ==============================================================================


class TestMarketViabilityDowngrade:
    """Test apply_market_viability_downgrade in isolation."""

    def test_weak_viability_floors_risk_medium(self):
        """Weak viability floors Low risk to Medium."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert v == "Go"
        assert r == "Medium"
        assert mvc is not None
        assert "Low\u2192Medium" in mvc

    def test_weak_viability_already_medium_no_change(self):
        """Weak viability with Medium risk stays Medium."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Medium",
            primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert v == "Go"
        assert r == "Medium"
        assert mvc is not None
        assert "no-op" in mvc

    def test_weak_viability_already_high_no_change(self):
        """Weak viability with High risk stays High."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="No-Go",
            risk_level="High",
            primary_concern="Low scores",
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert r == "High"
        assert mvc is not None
        assert "no-op" in mvc

    def test_weak_reconsider_same_as_weak_alone(self):
        """Weak + Reconsider produces same risk floor as Weak alone (no double-count)."""
        validator = VerdictValidator()
        v1, r1, _, mvc1 = validator.apply_market_viability_downgrade(
            verdict="Go", risk_level="Low", primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        v2, r2, _, mvc2 = validator.apply_market_viability_downgrade(
            verdict="Go", risk_level="Low", primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Enter",
        )
        assert r1 == r2 == "Medium"
        # Both should have context but with different entry strategy text
        assert "Reconsider" in mvc1
        assert "Enter" in mvc2

    def test_verdict_never_changes(self):
        """Verdict is never modified by market viability downgrade."""
        validator = VerdictValidator()
        for original_verdict in ["Go", "Conditional", "No-Go"]:
            v, r, pc, mvc = validator.apply_market_viability_downgrade(
                verdict=original_verdict,
                risk_level="Low",
                primary_concern=None,
                market_viability_verdict="Weak",
                recommended_entry_strategy="Reconsider",
            )
            assert v == original_verdict

    def test_case_insensitive_matching(self):
        """Case variants of 'Weak' are treated the same."""
        validator = VerdictValidator()
        for variant in ["weak", "WEAK", "Weak", " weak ", "  WEAK  "]:
            v, r, pc, mvc = validator.apply_market_viability_downgrade(
                verdict="Go", risk_level="Low", primary_concern=None,
                market_viability_verdict=variant,
                recommended_entry_strategy="Reconsider",
            )
            assert r == "Medium", f"Failed for variant '{variant}'"
            assert mvc is not None

    def test_moderate_go_informational_context(self):
        """Moderate viability + Go verdict sets informational context, no risk change."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            market_viability_verdict="Moderate",
            recommended_entry_strategy="Enter",
        )
        assert v == "Go"
        assert r == "Low"
        assert mvc is not None
        assert "Moderate" in mvc

    def test_moderate_conditional_no_context(self):
        """Moderate viability + Conditional verdict produces no context."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Conditional",
            risk_level="Medium",
            primary_concern=None,
            market_viability_verdict="Moderate",
            recommended_entry_strategy="Enter",
        )
        assert mvc is None

    def test_strong_no_change(self):
        """Strong viability produces no context and no risk change."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            market_viability_verdict="Strong",
            recommended_entry_strategy="Enter Now",
        )
        assert v == "Go"
        assert r == "Low"
        assert mvc is None

    def test_missing_data_no_change(self):
        """Empty/None viability strings produce no change."""
        validator = VerdictValidator()
        for viability in ["", None, "  "]:
            v, r, pc, mvc = validator.apply_market_viability_downgrade(
                verdict="Go", risk_level="Low", primary_concern=None,
                market_viability_verdict=viability or "",
                recommended_entry_strategy="",
            )
            assert r == "Low"
            assert mvc is None

    def test_primary_concern_set_when_none(self):
        """primary_concern is set from viability when originally None."""
        validator = VerdictValidator()
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert pc is not None
        assert "Weak" in pc
        assert "Reconsider" in pc

    def test_primary_concern_preserved(self):
        """Existing primary_concern is NOT overwritten."""
        validator = VerdictValidator()
        existing = "Low market fit score (0.58)"
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=existing,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert pc == existing

    def test_flag_disabled_no_change(self):
        """viability_weak_floors_risk_medium=False disables the floor."""
        thresholds = ScoreThresholds(viability_weak_floors_risk_medium=False)
        validator = VerdictValidator(thresholds)
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert r == "Low"
        assert mvc is None


class TestMarketViabilityInteractionWithTrend:
    """Test Phase 3 viability downgrade after Phase 2 trend downgrade."""

    def test_trend_raises_then_viability_floor_no_op(self):
        """Phase 2 raises Low→Medium, Phase 3 floor is no-op."""
        validator = VerdictValidator()
        # Phase 2: trend raises risk
        v, r, pc, tc = validator.apply_trend_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Sustainable",
            market_maturity="Mature",
        )
        assert r == "Medium"

        # Phase 3: viability floor is no-op (already Medium)
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict=v, risk_level=r, primary_concern=pc,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert v == "Conditional"
        assert r == "Medium"
        assert mvc is not None
        assert "no-op" in mvc

    def test_trend_caps_conditional_viability_floors_medium(self):
        """Phase 2 caps verdict at Conditional, Phase 3 floors risk to Medium."""
        validator = VerdictValidator()
        # Phase 2: trend caps verdict but leaves risk at Low (Rule 3)
        v, r, pc, tc = validator.apply_trend_downgrade(
            verdict="Go",
            risk_level="Low",
            primary_concern=None,
            trend_direction="Declining",
            momentum_score=0.3,
            timing_recommendation="Enter Now",
            longevity_verdict="Sustainable",
            market_maturity="Mature",
        )
        assert v == "Conditional"
        assert r == "Low"  # Rule 3 doesn't raise risk

        # Phase 3: viability floors risk
        v, r, pc, mvc = validator.apply_market_viability_downgrade(
            verdict=v, risk_level=r, primary_concern=pc,
            market_viability_verdict="Weak",
            recommended_entry_strategy="Reconsider",
        )
        assert v == "Conditional"
        assert r == "Medium"
        assert mvc is not None
        assert "Low\u2192Medium" in mvc


class TestConfidenceThresholds:
    """Test ConfidenceThresholds model validation."""

    def test_default_values(self):
        """Assert all defaults match specification."""
        t = ConfidenceThresholds()
        assert t.pain_point_silver == 0.95
        assert t.pain_point_bronze == 0.85
        assert t.pain_point_insufficient == 0.70
        assert t.social_minimal == 0.90
        assert t.social_insufficient == 0.75
        assert t.pp_confidence_low_threshold == 0.5
        assert t.pp_confidence_low_multiplier == 0.90
        assert t.pp_confidence_very_low_threshold == 0.3
        assert t.pp_confidence_very_low_multiplier == 0.80
        assert t.floor == 0.10

    def test_validation_constraints(self):
        """ge=0.0, le=1.0 enforced on all fields."""
        with pytest.raises(ValueError):
            ConfidenceThresholds(pain_point_bronze=-0.1)
        with pytest.raises(ValueError):
            ConfidenceThresholds(pain_point_bronze=1.1)
        with pytest.raises(ValueError):
            ConfidenceThresholds(floor=-0.01)
        with pytest.raises(ValueError):
            ConfidenceThresholds(social_minimal=1.5)


class TestConfidenceAdjusterQuality:
    """Test ConfidenceAdjuster with various quality signals."""

    def test_no_data_returns_base_score(self):
        """All None = base unchanged."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(0.80)
        assert result.adjusted_score == pytest.approx(0.80)
        assert result.quality_multiplier == pytest.approx(1.0)
        assert result.adjustment_notes == []

    def test_gold_excellent_no_penalty(self):
        """GOLD/EXCELLENT tiers → 1.0 multipliers, no change."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80,
            pain_point_quality_tier="GOLD",
            social_content_quality_tier="EXCELLENT",
        )
        assert result.adjusted_score == pytest.approx(0.80)
        assert result.quality_multiplier == pytest.approx(1.0)

    def test_bronze_applies_penalty(self):
        """BRONZE tier → 0.85x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, pain_point_quality_tier="BRONZE"
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.85)
        assert result.quality_multiplier == pytest.approx(0.85)

    def test_insufficient_pain_points(self):
        """INSUFFICIENT pain points → 0.70x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, pain_point_quality_tier="INSUFFICIENT"
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.70)

    def test_minimal_social(self):
        """MINIMAL social → 0.90x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, social_content_quality_tier="MINIMAL"
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.90)

    def test_insufficient_social(self):
        """INSUFFICIENT social → 0.75x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, social_content_quality_tier="INSUFFICIENT"
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.75)

    def test_bronze_and_minimal_compound(self):
        """BRONZE + MINIMAL compound: 0.85 * 0.90 = 0.765x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            1.0,
            pain_point_quality_tier="BRONZE",
            social_content_quality_tier="MINIMAL",
        )
        assert result.adjusted_score == pytest.approx(1.0 * 0.85 * 0.90)
        assert result.quality_multiplier == pytest.approx(0.85 * 0.90)

    def test_low_pp_confidence(self):
        """PP confidence 0.4 (< 0.5 threshold) → 0.90x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, pain_point_confidence_score=0.4
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.90)

    def test_very_low_pp_confidence(self):
        """PP confidence 0.2 (< 0.3 threshold) → 0.80x."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80, pain_point_confidence_score=0.2
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.80)

    def test_unknown_tier_no_crash(self):
        """Unknown tier returns 1.0 multiplier (no crash)."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80,
            pain_point_quality_tier="UNKNOWN_TIER",
            social_content_quality_tier="WEIRD_VALUE",
        )
        assert result.adjusted_score == pytest.approx(0.80)
        assert result.quality_multiplier == pytest.approx(1.0)

    def test_base_score_zero(self):
        """Base score 0.0 returns 0.0 with explanatory note."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.0,
            pain_point_quality_tier="BRONZE",
            social_content_quality_tier="MINIMAL",
        )
        assert result.adjusted_score == 0.0
        assert len(result.adjustment_notes) == 1
        assert "0.0" in result.adjustment_notes[0]

    def test_base_score_one_with_penalties(self):
        """1.0 * 0.70 * 0.75 = 0.525."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            1.0,
            pain_point_quality_tier="INSUFFICIENT",
            social_content_quality_tier="INSUFFICIENT",
        )
        assert result.adjusted_score == pytest.approx(1.0 * 0.70 * 0.75)

    def test_gold_with_low_pp_confidence(self):
        """Quality tier OK but PP confidence low → independent penalty."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80,
            pain_point_quality_tier="GOLD",
            social_content_quality_tier="GOOD",
            pain_point_confidence_score=0.4,
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.90)

    def test_insufficient_both_max_penalty(self):
        """INSUFFICIENT PP + INSUFFICIENT social + very low PP conf = extreme case."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.80,
            pain_point_quality_tier="INSUFFICIENT",
            social_content_quality_tier="INSUFFICIENT",
            pain_point_confidence_score=0.1,
        )
        expected = 0.80 * 0.70 * 0.75 * 0.80
        assert result.adjusted_score == pytest.approx(expected)

    def test_floor_prevents_near_zero(self):
        """Very low base + all penalties → clamped to floor."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.15,
            pain_point_quality_tier="INSUFFICIENT",
            social_content_quality_tier="INSUFFICIENT",
            pain_point_confidence_score=0.1,
        )
        # 0.15 * 0.70 * 0.75 * 0.80 = 0.063 → clamped to 0.10
        assert result.adjusted_score == pytest.approx(0.10)

    def test_bug_report_scenario(self):
        """Original bug report scenario: base 0.805, BRONZE PP, PP conf 0.51."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_confidence(
            0.805,
            pain_point_quality_tier="BRONZE",
            social_content_quality_tier="GOOD",
            pain_point_confidence_score=0.51,
        )
        # 0.805 * 0.85 (BRONZE) * 1.0 (GOOD) * 1.0 (PP conf 0.51 >= 0.5)
        expected = 0.805 * 0.85
        assert result.adjusted_score == pytest.approx(expected)


class TestConfidenceAdjusterCustomThresholds:
    """Test ConfidenceAdjuster with custom thresholds."""

    def test_custom_bronze_multiplier(self):
        """Override bronze multiplier works."""
        thresholds = ConfidenceThresholds(pain_point_bronze=0.50)
        adjuster = ConfidenceAdjuster(thresholds)
        result = adjuster.adjust_confidence(
            0.80, pain_point_quality_tier="BRONZE"
        )
        assert result.adjusted_score == pytest.approx(0.80 * 0.50)

    def test_disable_all_penalties(self):
        """All multipliers 1.0 = no change."""
        thresholds = ConfidenceThresholds(
            pain_point_silver=1.0,
            pain_point_bronze=1.0,
            pain_point_insufficient=1.0,
            social_minimal=1.0,
            social_insufficient=1.0,
            pp_confidence_low_multiplier=1.0,
            pp_confidence_very_low_multiplier=1.0,
        )
        adjuster = ConfidenceAdjuster(thresholds)
        result = adjuster.adjust_confidence(
            0.80,
            pain_point_quality_tier="INSUFFICIENT",
            social_content_quality_tier="INSUFFICIENT",
            pain_point_confidence_score=0.1,
        )
        assert result.adjusted_score == pytest.approx(0.80)

    def test_custom_floor(self):
        """Custom floor respected."""
        thresholds = ConfidenceThresholds(floor=0.25)
        adjuster = ConfidenceAdjuster(thresholds)
        result = adjuster.adjust_confidence(
            0.15,
            pain_point_quality_tier="INSUFFICIENT",
            social_content_quality_tier="INSUFFICIENT",
            pain_point_confidence_score=0.1,
        )
        # 0.15 * 0.70 * 0.75 * 0.80 = 0.063 → clamped to 0.25
        assert result.adjusted_score == pytest.approx(0.25)
