"""Tests for market sizing pre-computation helpers."""
import pytest
from unittest.mock import MagicMock

from nicheiq.utils.crew_helpers.market_sizing_pre_compute import (
    compute_strive_pre_check,
    compute_saturation_level,
    compute_tam_seed,
    compute_wtp_stats,
)


class TestComputeStrivePreCheck:
    """Tests for compute_strive_pre_check()."""

    def test_all_criteria_met(self):
        """All 3 deterministic criteria met."""
        result = compute_strive_pre_check(150_000, 100, 10)
        assert "3/3" in result
        assert "Searchable" in result and "YES" in result

    def test_no_criteria_met(self):
        """No criteria met (low volume, low mentions, wrong competitor count)."""
        result = compute_strive_pre_check(5_000, 10, 25)
        assert "0/3" in result

    def test_partial_criteria(self):
        """Only searchable met."""
        result = compute_strive_pre_check(200_000, 10, 0)
        assert "1/3" in result

    @pytest.mark.parametrize("volume,expected", [
        (99_999, "NO"),
        (100_000, "YES"),
        (100_001, "YES"),
    ])
    def test_searchable_threshold_boundary(self, volume, expected):
        result = compute_strive_pre_check(volume, 0, 0)
        assert f"Searchable (100K+ volume): {expected}" in result

    @pytest.mark.parametrize("mentions,expected", [
        (49, "NO"),
        (50, "YES"),
    ])
    def test_talked_about_threshold_boundary(self, mentions, expected):
        """Threshold comes from settings.strive_talked_about_min_mentions (default 50)."""
        result = compute_strive_pre_check(0, mentions, 0)
        assert f"Talked About (50+ unique discussions): {expected}" in result

    def test_talked_about_threshold_settings_backed(self, monkeypatch):
        """The threshold must follow the setting, not a hardcoded 50."""
        from nicheiq.config.settings import settings

        monkeypatch.setattr(settings, "strive_talked_about_min_mentions", 30)
        result = compute_strive_pre_check(0, 35, 0)
        assert "Talked About (30+ unique discussions): YES" in result

    @pytest.mark.parametrize("competitors,expected", [
        (4, "NO"),
        (5, "YES"),
        (15, "YES"),
        (16, "NO"),
    ])
    def test_rivalry_threshold_boundary(self, competitors, expected):
        result = compute_strive_pre_check(0, 0, competitors)
        assert f"Rivalry (5-15 competitors): {expected}" in result


class TestComputeSaturationLevel:
    @pytest.mark.parametrize("count,expected", [
        (0, "Low"), (4, "Low"),
        (5, "Medium"), (15, "Medium"),
        (16, "High"), (100, "High"),
    ])
    def test_saturation_thresholds(self, count, expected):
        assert compute_saturation_level(count) == expected


class TestComputeTamSeed:
    def test_positive_volume(self):
        result = compute_tam_seed(10_000)
        assert "$6,000,000" in result  # 10000 * 50 * 12

    def test_zero_volume(self):
        result = compute_tam_seed(0)
        assert "No keyword data" in result

    def test_negative_volume(self):
        result = compute_tam_seed(-500)
        assert "No keyword data" in result


class TestComputeWtpStats:
    def test_none_analysis(self):
        result = compute_wtp_stats(None)
        assert result["avg_wtp"] == "0.00"
        assert result["high_severity_count"] == 0

    def test_empty_pain_points(self):
        mock = MagicMock()
        mock.pain_points = []
        result = compute_wtp_stats(mock)
        assert result["avg_wtp"] == "0.00"

    def test_mixed_pain_points(self):
        pp1 = MagicMock(severity_score=0.8, willingness_to_pay=0.6)
        pp2 = MagicMock(severity_score=0.5, willingness_to_pay=0.3)
        mock = MagicMock()
        mock.pain_points = [pp1, pp2]
        result = compute_wtp_stats(mock)
        assert result["high_severity_count"] == 1  # only pp1 >= 0.7
        assert result["high_wtp_count"] == 1  # only pp1 >= 0.5
        assert result["avg_wtp"] == "0.45"  # (0.6+0.3)/2
