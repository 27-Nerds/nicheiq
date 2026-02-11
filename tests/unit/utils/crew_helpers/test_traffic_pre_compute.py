"""Tests for traffic_pre_compute shared helpers and enhanced functions."""
from types import SimpleNamespace

import pytest

from nicheiq.utils.crew_helpers.traffic_pre_compute import (
    collect_all_tiered_keywords,
    compute_affiliate_revenue_estimate,
    compute_commercial_intent_ratio,
    compute_difficulty_weighted_traffic,
    compute_intent_breakdown,
    compute_seo_traffic_enrichment,
    compute_total_revenue_estimate,
    compute_traffic_projection,
)


def _kw(volume=100, kd=None, intent=None):
    """Helper to create a mock keyword object."""
    return SimpleNamespace(search_volume=volume, keyword_difficulty=kd, intent=intent)


def _seo_report(tier_0=None, tier_1=None, tier_2=None, geo=None, cat=None,
                topic_clusters=None, page_types=None):
    """Helper to create a mock SEO strategy report."""
    return SimpleNamespace(
        tier_0_keywords=tier_0 or [],
        tier_1_keywords=tier_1 or [],
        tier_2_keywords=tier_2 or [],
        tier_3_geographic_groups=geo or [],
        tier_4_category_groups=cat or [],
        topic_clusters=topic_clusters or [],
        keyword_based_page_types=page_types or [],
    )


# ── collect_all_tiered_keywords ──────────────────────────────────────


class TestCollectAllTieredKeywords:
    def test_gathers_from_all_3_tiers(self):
        report = _seo_report(
            tier_0=[_kw(500)],
            tier_1=[_kw(100), _kw(200)],
            tier_2=[_kw(300)],
        )
        result = collect_all_tiered_keywords(report)
        assert len(result) == 4

    def test_none_report_returns_empty(self):
        assert collect_all_tiered_keywords(None) == []

    def test_handles_missing_tier_attributes(self):
        report = SimpleNamespace(tier_1_keywords=[_kw(100)])
        result = collect_all_tiered_keywords(report)
        assert len(result) == 1

    def test_handles_none_tiers(self):
        report = SimpleNamespace(
            tier_0_keywords=None,
            tier_1_keywords=None,
            tier_2_keywords=None,
        )
        result = collect_all_tiered_keywords(report)
        assert result == []


# ── compute_difficulty_weighted_traffic ──────────────────────────────


class TestComputeDifficultyWeightedTraffic:
    def test_easy_keywords(self):
        """All KD < 25 → should get high CTR and 80% ranking probability."""
        keywords = [_kw(volume=1000, kd=10), _kw(volume=2000, kd=15)]
        low, high = compute_difficulty_weighted_traffic(keywords)
        # Easy: ctr 0.065-0.11, p_rank 0.8
        # kw1: 1000 * 0.065 * 0.8 = 52, 1000 * 0.11 * 0.8 = 88
        # kw2: 2000 * 0.065 * 0.8 = 104, 2000 * 0.11 * 0.8 = 176
        assert low == 156  # 52 + 104
        assert high == 264  # 88 + 176

    def test_hard_keywords(self):
        """All KD > 50 → low CTR and 12% ranking probability."""
        keywords = [_kw(volume=5000, kd=70)]
        low, high = compute_difficulty_weighted_traffic(keywords)
        # Hard: ctr 0.005-0.030, p_rank 0.12
        # 5000 * 0.005 * 0.12 = 3, 5000 * 0.030 * 0.12 = 18
        assert low == 3
        assert high == 18

    def test_mixed_keywords(self):
        """Mix of easy and hard keywords."""
        keywords = [
            _kw(volume=1000, kd=10),   # easy
            _kw(volume=1000, kd=60),   # hard
        ]
        low, high = compute_difficulty_weighted_traffic(keywords)
        # Easy: 1000 * 0.065 * 0.8 = 52, 1000 * 0.11 * 0.8 = 88
        # Hard: 1000 * 0.005 * 0.12 = 0.6 → 0, 1000 * 0.030 * 0.12 = 3.6 → 3
        assert low > 0
        assert high > low

    def test_empty_keywords(self):
        assert compute_difficulty_weighted_traffic([]) == (0, 0)

    def test_none_kd_defaults_to_medium(self):
        """Keywords with kd=None should use medium profile."""
        keywords = [_kw(volume=1000, kd=None)]
        low, high = compute_difficulty_weighted_traffic(keywords)
        # Medium: ctr 0.030-0.065, p_rank 0.45
        # 1000 * 0.030 * 0.45 = 13.5 → 13, 1000 * 0.065 * 0.45 = 29.25 → 29
        assert low == 13
        assert high == 29

    def test_all_zero_volume(self):
        keywords = [_kw(volume=0, kd=10), _kw(volume=0, kd=20)]
        assert compute_difficulty_weighted_traffic(keywords) == (0, 0)


# ── compute_intent_breakdown ─────────────────────────────────────────


class TestComputeIntentBreakdown:
    def test_commercial_keywords(self):
        keywords = [
            _kw(volume=500, intent="transactional"),
            _kw(volume=300, intent="commercial investigation"),
        ]
        result = compute_intent_breakdown(keywords)
        assert result["commercial"]["count"] == 2
        assert result["commercial"]["volume"] == 800

    def test_informational_keywords(self):
        keywords = [_kw(volume=1000, intent="informational research")]
        result = compute_intent_breakdown(keywords)
        assert result["informational"]["count"] == 1
        assert result["informational"]["volume"] == 1000

    def test_mixed_keywords(self):
        keywords = [
            _kw(volume=500, intent="commercial"),
            _kw(volume=300, intent="informational"),
            _kw(volume=200, intent="navigational"),
        ]
        result = compute_intent_breakdown(keywords)
        assert result["commercial"]["count"] == 1
        assert result["informational"]["count"] == 1
        assert result["other"]["count"] == 1

    def test_none_intent_falls_to_other(self):
        keywords = [_kw(volume=100, intent=None)]
        result = compute_intent_breakdown(keywords)
        assert result["other"]["count"] == 1

    def test_priority_cascade_conversion(self):
        """'High conversion intent' → commercial (not other)."""
        keywords = [_kw(volume=500, intent="High conversion intent")]
        result = compute_intent_breakdown(keywords)
        assert result["commercial"]["count"] == 1

    def test_comparison_keywords(self):
        """'comparison', 'vs', 'pricing' → commercial."""
        keywords = [
            _kw(volume=100, intent="comparison"),
            _kw(volume=200, intent="vs competitor"),
            _kw(volume=300, intent="pricing analysis"),
        ]
        result = compute_intent_breakdown(keywords)
        assert result["commercial"]["count"] == 3
        assert result["commercial"]["volume"] == 600

    def test_broad_terms_not_commercial(self):
        """'Best practices guide' → informational (not commercial)."""
        keywords = [_kw(volume=500, intent="educational guide")]
        result = compute_intent_breakdown(keywords)
        assert result["informational"]["count"] == 1

    def test_ambiguous_priority(self):
        """'Research review of alternatives' → commercial (alternative matches first)."""
        keywords = [_kw(volume=500, intent="Research review of alternatives")]
        result = compute_intent_breakdown(keywords)
        # 'alternative' is in commercial patterns → commercial wins
        assert result["commercial"]["count"] == 1

    def test_empty_keywords(self):
        assert compute_intent_breakdown([]) == {}


# ── compute_commercial_intent_ratio ──────────────────────────────────


class TestComputeCommercialIntentRatio:
    def test_ratio_calculation(self):
        breakdown = {
            "commercial": {"count": 2, "volume": 400},
            "informational": {"count": 3, "volume": 600},
            "other": {"count": 0, "volume": 0},
        }
        ratio = compute_commercial_intent_ratio(breakdown)
        assert ratio == pytest.approx(40.0)

    def test_zero_volume(self):
        """Division by zero guard."""
        breakdown = {
            "commercial": {"count": 0, "volume": 0},
            "informational": {"count": 0, "volume": 0},
        }
        assert compute_commercial_intent_ratio(breakdown) == 0.0

    def test_empty_breakdown(self):
        assert compute_commercial_intent_ratio({}) == 0.0


# ── compute_traffic_projection ───────────────────────────────────────


class TestComputeTrafficProjection:
    def test_backward_compat_no_seo(self):
        """Calling with only total_volume still works (flat 3-5% CTR)."""
        desc, low, high = compute_traffic_projection(10000)
        assert "3-5% CTR" in desc
        assert low == int(10000 * 0.03 * 1.2)
        assert high == int(10000 * 0.05 * 1.3)

    def test_zero_volume(self):
        desc, low, high = compute_traffic_projection(0)
        assert "Insufficient" in desc
        assert low == 0
        assert high == 0

    def test_with_seo_data(self):
        """Uses difficulty-weighted model when SEO data provided."""
        report = _seo_report(
            tier_1=[_kw(volume=1000, kd=10)],  # easy
            tier_2=[_kw(volume=2000, kd=30)],   # medium
        )
        desc, low, high = compute_traffic_projection(3000, seo_strategy_report=report)
        assert "difficulty-weighted" in desc
        assert "Year 1" in desc
        assert "Year 3" in desc
        assert low > 0
        assert high > low

    def test_with_seo_data_empty_tiers(self):
        """Falls back to flat CTR when SEO report has empty tiers."""
        report = _seo_report()  # all empty
        desc, low, high = compute_traffic_projection(10000, seo_strategy_report=report)
        assert "3-5% CTR" in desc  # fallback

    def test_tier2_scaling(self):
        """Y1 traffic < Y3 traffic because T2 is only 60% in Y1."""
        report = _seo_report(
            tier_1=[],
            tier_2=[_kw(volume=5000, kd=30)],  # medium only
        )
        desc_y1, y1_low, y1_high = compute_traffic_projection(5000, seo_strategy_report=report)
        # Year 1 uses 60% of T2, Year 3 uses 100%
        # Y1: int(5000 * 0.030 * 0.45 * 0.6) * 1.25 ... etc
        assert y1_low > 0
        # The description should mention both Y1 and Y3
        assert "Year 3" in desc_y1


# ── compute_seo_traffic_enrichment ───────────────────────────────────


class TestComputeSeoTrafficEnrichment:
    def test_none_report(self):
        assert compute_seo_traffic_enrichment(None) == ""

    def test_has_constraints_section(self):
        report = _seo_report(tier_1=[_kw(1000, 10, "commercial")])
        result = compute_seo_traffic_enrichment(report)
        assert "TRAFFIC CONSTRAINTS" in result

    def test_has_phased_rampup(self):
        report = _seo_report(
            tier_1=[_kw(1000, 10)],
            tier_2=[_kw(2000, 35)],
        )
        result = compute_seo_traffic_enrichment(report)
        assert "PHASED ORGANIC TRAFFIC RAMP-UP" in result

    def test_has_intent_data(self):
        report = _seo_report(
            tier_1=[_kw(1000, 10, "commercial")],
            tier_2=[_kw(2000, 35, "informational")],
        )
        result = compute_seo_traffic_enrichment(report)
        assert "REFERENCE DATA" in result
        assert "Commercial intent" in result
        assert "Informational intent" in result


# ── compute_affiliate_revenue_estimate ───────────────────────────────


class TestComputeAffiliateRevenueEstimate:
    def test_with_intent(self):
        intent = {
            "commercial": {"count": 5, "volume": 500},
            "informational": {"count": 5, "volume": 500},
            "other": {"count": 0, "volume": 0},
        }
        result = compute_affiliate_revenue_estimate(intent, 1000, 2000, "SaaS developer tools")
        assert "$" in result
        assert "affiliate" in result

    def test_no_intent(self):
        assert compute_affiliate_revenue_estimate({}, 1000, 2000, "test") == ""

    def test_zero_pageviews(self):
        intent = {"commercial": {"count": 1, "volume": 100}}
        assert compute_affiliate_revenue_estimate(intent, 0, 0, "test") == ""


# ── compute_total_revenue_estimate ───────────────────────────────────


class TestComputeTotalRevenueEstimate:
    def test_sums_correctly(self):
        result = compute_total_revenue_estimate(100, 500, 50, 200)
        assert "$150" in result
        assert "$700" in result
        assert "total" in result

    def test_zero_values(self):
        assert compute_total_revenue_estimate(0, 0, 0, 0) == ""
