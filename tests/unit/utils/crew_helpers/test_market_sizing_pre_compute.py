"""Tests for market_sizing_pre_compute enhanced enrichment."""
from types import SimpleNamespace

from nicheiq.utils.crew_helpers.market_sizing_pre_compute import (
    compute_seo_market_enrichment,
)


def _kw(volume=100, kd=None, intent=None):
    """Helper to create a mock keyword object."""
    return SimpleNamespace(search_volume=volume, keyword_difficulty=kd, intent=intent)


def _seo_report(tier_0=None, tier_1=None, tier_2=None, geo=None, cat=None,
                topic_clusters=None):
    """Helper to create a mock SEO strategy report."""
    return SimpleNamespace(
        tier_0_keywords=tier_0 or [],
        tier_1_keywords=tier_1 or [],
        tier_2_keywords=tier_2 or [],
        tier_3_geographic_groups=geo or [],
        tier_4_category_groups=cat or [],
        topic_clusters=topic_clusters or [],
        keyword_based_page_types=[],
    )


class TestComputeSeoMarketEnrichment:
    def test_none_report(self):
        assert compute_seo_market_enrichment(None) == ""

    def test_has_difficulty_weighted_som(self):
        report = _seo_report(
            tier_1=[_kw(1000, 10)],
            tier_2=[_kw(2000, 35)],
        )
        result = compute_seo_market_enrichment(report)
        assert "DIFFICULTY-WEIGHTED DEMAND ANALYSIS" in result
        assert "Traffic Ceiling Y1" in result
        assert "Traffic Ceiling Y3" in result

    def test_has_commercial_viability(self):
        report = _seo_report(
            tier_1=[_kw(1000, 10, "commercial")],
            tier_2=[_kw(500, 30, "informational")],
        )
        result = compute_seo_market_enrichment(report)
        assert "COMMERCIAL VIABILITY" in result
        assert "Commercial Intent Ratio" in result

    def test_has_tam_expansion(self):
        geo = [SimpleNamespace(
            region_name="US",
            keywords=[_kw(500)],
            competition_level="Medium",
        )]
        cat = [SimpleNamespace(
            group_name="Adjacent",
            keywords=[_kw(300)],
            competition_level="Low",
        )]
        report = _seo_report(
            tier_1=[_kw(1000, 10)],
            tier_2=[_kw(1000, 30)],
            geo=geo,
            cat=cat,
        )
        result = compute_seo_market_enrichment(report)
        assert "TAM EXPANSION" in result
        assert "Geographic expansion" in result
        assert "Category expansion" in result

    def test_backward_compat_none_tiers(self):
        """Handles None tiers gracefully."""
        report = SimpleNamespace(
            tier_0_keywords=None,
            tier_1_keywords=None,
            tier_2_keywords=None,
            tier_3_geographic_groups=None,
            tier_4_category_groups=None,
            topic_clusters=None,
            keyword_based_page_types=None,
        )
        result = compute_seo_market_enrichment(report)
        assert "DIFFICULTY-WEIGHTED DEMAND ANALYSIS" in result
        # Should not crash, should produce some output
        assert "Traffic Ceiling Y1: 0-0" in result
