"""Tests for pricing pre-computation helpers."""
import pytest
from unittest.mock import MagicMock

from nicheiq.utils.crew_helpers.pricing_pre_compute import (
    compute_wtp_summary,
    compute_cac_range,
)


class TestComputeWtpSummary:
    def test_none_analysis(self):
        summary, avg = compute_wtp_summary(None)
        assert summary == "No WTP data available"
        assert avg == "0.00"

    def test_high_wtp_premium(self):
        """Average >= 0.70 should map to Premium tolerance."""
        pp1 = MagicMock(willingness_to_pay=0.8)
        pp2 = MagicMock(willingness_to_pay=0.9)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, avg = compute_wtp_summary(mock)
        assert "Premium" in summary
        assert avg == "0.85"

    def test_mid_wtp_market_rate(self):
        """Average 0.50-0.69 should map to Market Rate."""
        pp1 = MagicMock(willingness_to_pay=0.5)
        pp2 = MagicMock(willingness_to_pay=0.6)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, _ = compute_wtp_summary(mock)
        assert "Market Rate" in summary

    def test_low_wtp_discount(self):
        """Average 0.30-0.49 should map to Discount."""
        pp1 = MagicMock(willingness_to_pay=0.3)
        pp2 = MagicMock(willingness_to_pay=0.4)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        summary, _ = compute_wtp_summary(mock)
        assert "Discount" in summary

    def test_very_low_wtp_free(self):
        """Average < 0.30 should map to Free/Near-Free."""
        pp1 = MagicMock(willingness_to_pay=0.1)
        pp2 = MagicMock(willingness_to_pay=0.2)
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
