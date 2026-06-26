"""Tests for pricing pre-computation helpers."""
import pytest
from unittest.mock import MagicMock

from nicheiq.utils.crew_helpers.pricing_pre_compute import (
    compute_wtp_summary,
    compute_cac_range,
    format_market_sizing_summary,
    format_audience_budget_sensitivity,
    format_solution_rank_context,
)


class TestComputeWtpSummary:
    def test_none_analysis(self):
        summary, avg = compute_wtp_summary(None)
        assert summary == "No WTP data available"
        assert avg == "0.00"

    def test_high_wtp_premium(self):
        """Average >= 0.70 should map to Premium tolerance."""
        pp1 = MagicMock(commercial_intent=0.8)
        pp2 = MagicMock(commercial_intent=0.9)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, avg = compute_wtp_summary(mock)
        assert "Premium" in summary
        assert avg == "0.85"

    def test_mid_wtp_market_rate(self):
        """Average 0.50-0.69 should map to Market Rate."""
        pp1 = MagicMock(commercial_intent=0.5)
        pp2 = MagicMock(commercial_intent=0.6)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, _ = compute_wtp_summary(mock)
        assert "Market Rate" in summary

    def test_low_wtp_discount(self):
        """Average 0.30-0.49 should map to Discount."""
        pp1 = MagicMock(commercial_intent=0.3)
        pp2 = MagicMock(commercial_intent=0.4)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, _ = compute_wtp_summary(mock)
        assert "Discount" in summary

    def test_very_low_wtp_free(self):
        """Average < 0.30 should map to Free/Near-Free."""
        pp1 = MagicMock(commercial_intent=0.1)
        pp2 = MagicMock(commercial_intent=0.2)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, _ = compute_wtp_summary(mock)
        assert "Free" in summary


class TestComputeCacRange:
    @pytest.mark.parametrize("score,expected_substring", [
        (0.80, "$15-30"),
        (0.76, "$15-30"),
        (0.75, "$30-60"),
        (0.60, "$30-60"),
        (0.59, "$60-120"),
        (0.10, "$60-120"),
    ])
    def test_cac_thresholds(self, score, expected_substring):
        result = compute_cac_range(score)
        assert expected_substring in result

    def test_none_score(self):
        result = compute_cac_range(None)
        assert "Cannot estimate" in result


class TestFormatMarketSizingSummary:
    def test_none_returns_fallback(self):
        result = format_market_sizing_summary(None)
        assert result == "Market sizing data not available"

    def test_full_data(self):
        ms = MagicMock()
        ms.total_addressable_market = "$2.5B"
        ms.serviceable_available_market = "$800M"
        ms.serviceable_obtainable_market_y1 = "$2M"
        ms.market_growth_rate = "15-20% CAGR"
        ms.market_timing_assessment = "Growth"
        ms.market_viability_verdict = "Strong"
        result = format_market_sizing_summary(ms)
        assert "TAM: $2.5B" in result
        assert "SAM: $800M" in result
        assert "SOM Y1: $2M" in result
        assert "Growth: 15-20% CAGR" in result
        assert "Timing: Growth" in result
        assert "Viability: Strong" in result

    def test_partial_data(self):
        ms = MagicMock()
        ms.total_addressable_market = "$1B"
        ms.serviceable_available_market = "$200M"
        ms.serviceable_obtainable_market_y1 = "$500K"
        ms.market_growth_rate = None
        ms.market_timing_assessment = None
        ms.market_viability_verdict = "Moderate"
        result = format_market_sizing_summary(ms)
        assert "TAM: $1B" in result
        assert "Viability: Moderate" in result
        assert "Growth:" not in result
        assert "Timing:" not in result

    def test_all_empty_fields(self):
        ms = MagicMock()
        ms.total_addressable_market = ""
        ms.serviceable_available_market = ""
        ms.serviceable_obtainable_market_y1 = ""
        ms.market_growth_rate = None
        ms.market_timing_assessment = None
        ms.market_viability_verdict = ""
        result = format_market_sizing_summary(ms)
        assert result == "Market sizing data incomplete"


class TestFormatAudienceBudgetSensitivity:
    def test_none_returns_fallback(self):
        result = format_audience_budget_sensitivity(None)
        assert result == "Audience data not available"

    def test_empty_segments(self):
        am = MagicMock()
        am.audience_segments = []
        result = format_audience_budget_sensitivity(am)
        assert result == "No audience segments defined"

    def test_with_segments(self):
        seg1 = MagicMock()
        seg1.segment_name = "Solo Founders"
        seg1.budget_sensitivity = "High"

        seg2 = MagicMock()
        seg2.segment_name = "Marketing Managers"
        seg2.budget_sensitivity = "Medium"

        am = MagicMock()
        am.audience_segments = [seg1, seg2]
        am.primary_target_segment = "Solo Founders"

        result = format_audience_budget_sensitivity(am)
        assert "Primary: Solo Founders" in result
        assert "Solo Founders (High sensitivity)" in result
        assert "Marketing Managers (Medium sensitivity)" in result

    def test_primary_not_specified(self):
        seg1 = MagicMock()
        seg1.segment_name = "Developers"
        seg1.budget_sensitivity = "Low"

        am = MagicMock()
        am.audience_segments = [seg1]
        am.primary_target_segment = None

        result = format_audience_budget_sensitivity(am)
        assert "Primary: Not specified" in result


class TestFormatSolutionRankContext:
    def test_none_returns_fallback(self):
        result = format_solution_rank_context(None, "SomeSolution")
        assert result == "Solution ranking data not available"

    def test_empty_list(self):
        result = format_solution_rank_context([], "SomeSolution")
        assert result == "Solution ranking data not available"

    def test_solution_not_found(self):
        s = MagicMock()
        s.solution_name = "OtherSolution"
        result = format_solution_rank_context([s], "MySolution")
        assert "not found" in result

    def test_ranked_solution_with_keyword_demand(self):
        s = MagicMock()
        s.solution_name = "MySolution"
        s.rank = 1
        s.composite_score = 0.82
        s.keyword_demand_score = 0.75

        result = format_solution_rank_context([s], "MySolution")
        assert "Rank: #1 of 1" in result
        assert "Composite: 0.82" in result
        assert "Keyword Demand: 0.75 (Strong)" in result

    def test_moderate_keyword_demand(self):
        s = MagicMock()
        s.solution_name = "MySolution"
        s.rank = 2
        s.composite_score = 0.55
        s.keyword_demand_score = 0.50

        result = format_solution_rank_context([s], "MySolution")
        assert "Moderate" in result

    def test_weak_keyword_demand(self):
        s = MagicMock()
        s.solution_name = "MySolution"
        s.rank = 3
        s.composite_score = 0.40
        s.keyword_demand_score = 0.20

        result = format_solution_rank_context([s], "MySolution")
        assert "Weak" in result

    def test_no_keyword_demand(self):
        s = MagicMock()
        s.solution_name = "MySolution"
        s.rank = 1
        s.composite_score = 0.70
        s.keyword_demand_score = None

        result = format_solution_rank_context([s], "MySolution")
        assert "Rank: #1 of 1" in result
        assert "Composite: 0.70" in result
        assert "Keyword" not in result
