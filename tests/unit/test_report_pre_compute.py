"""Tests for report generator pre-computation helpers."""
import pytest
from unittest.mock import MagicMock

from nicheiq.report.utils.report_pre_compute import (
    BUDGET_RANGES,
    compute_budget_range,
    compute_metric_calibration,
    format_pain_point_with_scores,
)


class TestComputeBudgetRange:
    @pytest.mark.parametrize("model,expected_contains", [
        ("Freemium", "$400"),
        ("Subscription", "$800"),
        ("Ad-Supported-Free", "$50"),
        ("Usage-Based", "$2,000"),
        ("Hybrid", "$400"),
        ("One-time", "$200"),
        ("Affiliate-Only", "$100"),
        ("Freemium-Lite", "$200"),
    ])
    def test_all_pricing_models_covered(self, model, expected_contains):
        result = compute_budget_range(model, 2)
        assert expected_contains in result

    def test_unknown_model_uses_default(self):
        result = compute_budget_range("UnknownModel", 2)
        assert "$400" in result  # default (400, 1500)

    def test_many_channels_multiplier(self):
        """4+ channels should increase budget by 1.5x."""
        base = compute_budget_range("Freemium", 2)
        scaled = compute_budget_range("Freemium", 5)
        # Freemium base is 400-1500, scaled is 600-2250
        assert "$600" in scaled

    def test_few_channels_no_multiplier(self):
        result = compute_budget_range("Freemium", 2)
        assert "$400" in result  # no multiplier applied


class TestComputeMetricCalibration:
    def test_with_keyword_data(self):
        result = compute_metric_calibration(100, 20)
        assert "Tier 1" in result
        assert "visitors" in result

    def test_zero_tier1_uses_default(self):
        result = compute_metric_calibration(100, 0)
        assert "conservative defaults" in result

    def test_zero_total_uses_default(self):
        result = compute_metric_calibration(0, 20)
        assert "conservative defaults" in result

    def test_floor_values_applied(self):
        """Even with tiny tier1 count, floor should be 50-200."""
        result = compute_metric_calibration(5, 1)
        assert "50-200" in result  # floor values


class TestFormatPainPointWithScores:
    def test_basic_formatting(self):
        pp = MagicMock()
        pp.title = "Data Export Issues"
        pp.description = "Users struggle with exporting data"
        pp.severity_score = 0.8
        pp.commercial_intent = 0.6
        pp.mention_count = 42
        result = format_pain_point_with_scores(pp)
        assert result.startswith("- Data Export Issues:")
        assert "Severity: 8.0/10" in result
        assert "WTP: 6.0/10" in result
        assert "Mentions: 42" in result

    def test_long_description_is_not_cut_at_a_guessed_width(self):
        """WAS: `assert "..." in result`, which pinned the `description[:200]` cut.

        That was a prose pin on a truncation artifact. This is a prompt input to the
        pain->solution mapping call and pain descriptions run a median well past 200, so the
        cut was deleting the mechanism the mapper is asked to reason about. The behaviour
        worth pinning is that the description arrives whole and the line stays parseable.
        Real PainPoint, not MagicMock: a mock would accept any field and hide a schema drift.
        """
        from nicheiq.models.pain_point import OpportunityLevel, PainPoint

        description = "Operators reconcile the closed period by hand. " * 8  # ~370 chars
        pp = PainPoint(
            title="Test",
            description=description,
            severity_score=0.5,
            commercial_intent=0.5,
            mention_count=10,
            opportunity_level=OpportunityLevel.MEDIUM,
            representative_quotes=["we caught it three weeks later"],
        )
        result = format_pain_point_with_scores(pp)
        assert description in result
        assert "…[truncated]" not in result
        assert result.split("- ", 1)[1].split(":", 1)[0] == "Test"

    def test_runaway_description_is_still_bounded_and_marked(self):
        """Removing the guessed limit does not remove the ceiling."""
        from nicheiq.models.pain_point import OpportunityLevel, PainPoint
        from nicheiq.utils.content_security import PROMPT_FIELD_MAX

        pp = PainPoint(
            title="Test",
            description="x" * (PROMPT_FIELD_MAX + 5_000),
            severity_score=0.5,
            commercial_intent=0.5,
            mention_count=10,
            opportunity_level=OpportunityLevel.MEDIUM,
            representative_quotes=["q"],
        )
        result = format_pain_point_with_scores(pp)
        assert "…[truncated]" in result
        assert len(result) < PROMPT_FIELD_MAX + 500

    def test_title_is_first_element(self):
        """Title must be between '- ' and ':' for JSON key extraction."""
        pp = MagicMock()
        pp.title = "Unique Title Here"
        pp.description = "desc"
        pp.severity_score = 0.5
        pp.commercial_intent = 0.5
        pp.mention_count = 5
        result = format_pain_point_with_scores(pp)
        # Extract title: everything between "- " and ":"
        title_part = result.split("- ", 1)[1].split(":", 1)[0]
        assert title_part == "Unique Title Here"


class TestFormatPainPointsForPrompt:
    """Tests for prompt_formatters.format_pain_points_for_prompt score scaling."""

    def test_scores_scaled_to_10(self):
        """Severity/WTP/Priority scores (0-1) must display as X.Y/10."""
        from nicheiq.report.utils.prompt_formatters import format_pain_points_for_prompt

        pp = MagicMock()
        pp.title = "Slow Onboarding"
        pp.description = "Users drop off during setup"
        pp.severity_score = 0.8
        pp.commercial_intent = 0.6

        result = format_pain_points_for_prompt([pp])
        assert "Severity: 8.0/10" in result
        assert "Willingness to Pay: 6.0/10" in result
        assert "Priority Score: 7.0/10" in result  # (0.8 + 0.6) / 2 * 10
        # Must NOT show raw 0-1 values
        assert "Severity: 0.8/10" not in result
        assert "Willingness to Pay: 0.6/10" not in result

    def test_empty_list_returns_fallback(self):
        from nicheiq.report.utils.prompt_formatters import format_pain_points_for_prompt

        result = format_pain_points_for_prompt([])
        assert "No pain points" in result


class TestBudgetRangesSync:
    def test_budget_ranges_covers_all_pricing_models(self):
        """BUDGET_RANGES keys must match PricingStrategyResult.pricing_model Literal values."""
        import typing
        from nicheiq.models.research_state import PricingStrategyResult

        literal_values = set(typing.get_args(
            PricingStrategyResult.model_fields["pricing_model"].annotation
        ))
        budget_keys = set(BUDGET_RANGES.keys())
        assert budget_keys == literal_values
