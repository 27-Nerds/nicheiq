"""Tests for traffic monetization pre-computation helpers."""
import pytest

from nicheiq.utils.crew_helpers.traffic_pre_compute import (
    compute_traffic_projection,
    match_niche_to_cpm,
    compute_ad_revenue_estimate,
)


class TestComputeTrafficProjection:
    def test_positive_volume(self):
        projection, low, high = compute_traffic_projection(100_000)
        assert low > 0 and high > low
        assert "3,000" in projection  # 100k * 0.03
        assert "5,000" in projection  # 100k * 0.05

    def test_zero_volume(self):
        projection, low, high = compute_traffic_projection(0)
        assert "Insufficient" in projection
        assert low == 0 and high == 0

    def test_negative_volume(self):
        projection, low, high = compute_traffic_projection(-100)
        assert "Insufficient" in projection

    def test_math_correctness(self):
        """Verify exact math: organic = vol*CTR, total = organic*(1+direct)."""
        _, low, high = compute_traffic_projection(10_000)
        assert low == int(int(10_000 * 0.03) * 1.2)  # 360
        assert high == int(int(10_000 * 0.05) * 1.3)  # 650


class TestMatchNicheToCpm:
    @pytest.mark.parametrize("niche,expected_vertical", [
        ("personal finance tools", "Finance/Insurance"),
        ("legal document automation", "Legal"),
        ("fitness tracking app", "Health"),
        ("SaaS developer tools", "Technology/SaaS"),
        ("skincare routine planner", "Lifestyle/Beauty"),
        ("gaming community platform", "Entertainment"),
        ("pet grooming marketplace", "General"),
    ])
    def test_vertical_matching(self, niche, expected_vertical):
        _, _, vertical = match_niche_to_cpm(niche)
        assert vertical == expected_vertical

    def test_always_returns_valid_tuple(self):
        """Even unknown niches return valid CPM range."""
        low, high, vertical = match_niche_to_cpm("underwater basket weaving")
        assert low > 0 and high > low
        assert vertical == "General"

    def test_case_insensitive(self):
        _, _, v1 = match_niche_to_cpm("FINANCE tools")
        _, _, v2 = match_niche_to_cpm("finance tools")
        assert v1 == v2

    @pytest.mark.parametrize("niche,expected_vertical", [
        ("lawn care service", "General"),           # 'law' must not match 'lawn'
        ("biotech research", "General"),            # 'tech' must not match 'biotech'
        ("ai-powered analytics", "Technology/SaaS"),  # 'ai' word boundary with hyphen
        ("ai tools for devs", "Technology/SaaS"),     # 'ai' at word boundary
        ("compliance automation", "Legal"),          # 'compliance' still matches
    ])
    def test_word_boundary_matching(self, niche, expected_vertical):
        _, _, vertical = match_niche_to_cpm(niche)
        assert vertical == expected_vertical


class TestComputeAdRevenueEstimate:
    def test_positive_values(self):
        result = compute_ad_revenue_estimate(5000, 10000, 5, 15)
        assert "$25" in result  # 5000*5/1000
        assert "$150" in result  # 10000*15/1000

    def test_zero_traffic(self):
        result = compute_ad_revenue_estimate(0, 0, 5, 15)
        assert "Cannot estimate" in result
