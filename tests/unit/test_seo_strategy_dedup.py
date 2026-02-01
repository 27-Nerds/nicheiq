"""
Tests for cross-tier keyword deduplication in SEOStrategyCrew.
"""

import logging

import pytest

from nicheiq.crews.seo_strategy_crew import SEOStrategyCrew
from nicheiq.models.seo_strategy import (
    CategoryKeywordEntry,
    CategoryKeywordGroup,
    GeographicKeywordEntry,
    GeographicKeywordGroup,
    KeywordAnalysisResult,
    TieredKeyword,
)


# ==================================================================================
# Helpers
# ==================================================================================

def _kw(keyword: str, volume: int = 100, tier: int | None = None) -> TieredKeyword:
    """Create a TieredKeyword for testing."""
    return TieredKeyword(
        keyword=keyword,
        search_volume=volume,
        competition="MEDIUM (50)",
        strategy="test strategy",
        tier=tier,
    )


def _geo_entry(keyword: str, volume: int = 100) -> GeographicKeywordEntry:
    return GeographicKeywordEntry(
        city="TestCity",
        keyword=keyword,
        search_volume=volume,
    )


def _cat_entry(keyword_name: str, volume: int = 100) -> CategoryKeywordEntry:
    return CategoryKeywordEntry(
        keyword_name=keyword_name,
        search_volume=volume,
    )


def _geo_group(entries: list[GeographicKeywordEntry]) -> GeographicKeywordGroup:
    return GeographicKeywordGroup(
        region_name="Test Region",
        total_volume=sum(e.search_volume for e in entries),
        competition_level="LOW",
        keywords=entries,
        strategy_notes="test notes",
    )


def _cat_group(entries: list[CategoryKeywordEntry]) -> CategoryKeywordGroup:
    return CategoryKeywordGroup(
        category_name="Test Category",
        total_volume=sum(e.search_volume for e in entries),
        keywords=entries,
        strategy_recommendation="test recommendation",
    )


def _make_analysis(**kwargs) -> KeywordAnalysisResult:
    """Create a KeywordAnalysisResult with defaults for required fields."""
    defaults = dict(
        tier_1_keywords=[_kw("default tier1 kw")],
        tier_1_quick_win_strategy="default strategy",
        total_keywords_analyzed=10,
        total_monthly_volume=1000,
        key_findings=["finding 1"],
        competitive_positioning="positioning text",
    )
    defaults.update(kwargs)
    return KeywordAnalysisResult(**defaults)


# ==================================================================================
# Tests
# ==================================================================================


class TestSourceSideDedup:
    """Tests for _deduplicate_across_tiers on SEOStrategyCrew."""

    def test_cross_tier_dedup_preserves_priority(self):
        """Keyword in T0+T1 → kept in T0 only."""
        analysis = _make_analysis(
            tier_0_keywords=[_kw("premium kw", volume=5000, tier=0)],
            tier_1_keywords=[_kw("premium kw", volume=5000, tier=1), _kw("unique t1", tier=1)],
        )
        result = SEOStrategyCrew._deduplicate_across_tiers(analysis)

        assert len(result.tier_0_keywords) == 1
        assert result.tier_0_keywords[0].keyword == "premium kw"
        # T1 should only have the unique keyword
        assert len(result.tier_1_keywords) == 1
        assert result.tier_1_keywords[0].keyword == "unique t1"

    def test_cross_tier_dedup_geographic_internal(self):
        """Duplicate within a geographic group → one entry."""
        geo = _geo_group([
            _geo_entry("local beer"),
            _geo_entry("local beer"),
        ])
        analysis = _make_analysis(
            tier_3_geographic_groups=[geo],
        )
        result = SEOStrategyCrew._deduplicate_across_tiers(analysis)

        assert len(result.tier_3_geographic_groups) == 1
        assert len(result.tier_3_geographic_groups[0].keywords) == 1

    def test_cross_tier_dedup_category_internal(self):
        """Duplicate within a category group → one entry."""
        cat = _cat_group([
            _cat_entry("doc translation"),
            _cat_entry("doc translation"),
        ])
        analysis = _make_analysis(
            tier_4_category_groups=[cat],
        )
        result = SEOStrategyCrew._deduplicate_across_tiers(analysis)

        assert len(result.tier_4_category_groups) == 1
        assert len(result.tier_4_category_groups[0].keywords) == 1

    def test_cross_tier_dedup_returns_new_object(self):
        """Input not mutated."""
        original = _make_analysis(
            tier_0_keywords=[_kw("shared kw")],
            tier_1_keywords=[_kw("shared kw"), _kw("only t1")],
        )
        original_t1_len = len(original.tier_1_keywords)

        result = SEOStrategyCrew._deduplicate_across_tiers(original)

        # Original should be unchanged
        assert len(original.tier_1_keywords) == original_t1_len
        assert result is not original

    def test_cross_tier_dedup_stats_correct(self):
        """Stats dict reports correct removal counts."""
        from loguru import logger

        analysis = _make_analysis(
            tier_0_keywords=[_kw("dup1"), _kw("dup2")],
            tier_1_keywords=[_kw("dup1"), _kw("dup2"), _kw("unique")],
        )

        messages = []
        sink_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
        try:
            SEOStrategyCrew._deduplicate_across_tiers(analysis)
        finally:
            logger.remove(sink_id)

        assert any("removed 2 duplicates" in m for m in messages)

    def test_cross_tier_dedup_untiered_keywords(self):
        """Untiered keyword matching T1 keyword → removed from untiered."""
        analysis = _make_analysis(
            tier_1_keywords=[_kw("overlap kw")],
            untiered_keywords=[_kw("overlap kw", tier=5), _kw("truly untiered", tier=5)],
        )
        result = SEOStrategyCrew._deduplicate_across_tiers(analysis)

        assert len(result.tier_1_keywords) == 1
        assert len(result.untiered_keywords) == 1
        assert result.untiered_keywords[0].keyword == "truly untiered"

    def test_cross_tier_dedup_none_tiers(self):
        """None tiers handled gracefully."""
        analysis = _make_analysis(
            tier_0_keywords=None,
            tier_2_keywords=None,
            tier_3_geographic_groups=None,
            tier_4_category_groups=None,
            untiered_keywords=None,
        )
        result = SEOStrategyCrew._deduplicate_across_tiers(analysis)

        assert result.tier_0_keywords is None
        assert result.tier_2_keywords is None
        assert result.tier_3_geographic_groups is None
        assert result.tier_4_category_groups is None
