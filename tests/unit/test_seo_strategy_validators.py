"""
Tests for SEO strategy model validators.
"""

import pytest
import logging
from nicheiq.models.seo_strategy import (
    TieredKeyword,
    ConceptualKeyword,
    Tier0LightResult,
    Tier1LightResult,
    LightweightKeywordSelection,
    CategoryLightResult,
    ContentStrategyResultLight,
    ContentStrategyResult,
)


class TestTieredKeywordValidator:
    """Tests for TieredKeyword field validators."""

    def test_valid_keyword_short(self):
        """Test that short keywords (1-2 words) are accepted."""
        keyword = TieredKeyword(
            keyword="seo tools",
            search_volume=1000,
            competition="LOW (25)",
            strategy="Target users looking for SEO software solutions"
        )

        assert keyword.keyword == "seo tools"

    def test_valid_keyword_medium_length(self):
        """Test that medium keywords (3-5 words) are accepted."""
        keyword = TieredKeyword(
            keyword="best project management software",
            search_volume=500,
            competition="MEDIUM (50)",
            strategy="Target comparison shoppers looking for solutions"
        )

        assert keyword.keyword == "best project management software"

    def test_keyword_stripped_of_whitespace(self):
        """Test that keywords are stripped of leading/trailing whitespace."""
        keyword = TieredKeyword(
            keyword="  project management  ",
            search_volume=1000,
            competition="MEDIUM (50)",
            strategy="Target project managers"
        )

        # Whitespace should be stripped
        assert keyword.keyword == "project management"

    def test_long_keyword_accepted(self):
        """Test that long keywords (6+ words) are accepted by TieredKeyword."""
        keyword = TieredKeyword(
            keyword="best free project management software for small teams",  # 8 words
            search_volume=100,
            competition="HIGH (75)",
            strategy="Target budget-conscious small team managers"
        )

        # Long keywords are accepted without validation error
        assert keyword.keyword == "best free project management software for small teams"

    def test_very_long_keyword_accepted(self):
        """Test that very long keywords are accepted by TieredKeyword."""
        long_keyword = " ".join(["word"] * 12)  # 12 words
        keyword = TieredKeyword(
            keyword=long_keyword,
            search_volume=50,
            competition="LOW (20)",
            strategy="Generic targeting strategy"
        )

        # Very long keywords are accepted
        assert keyword.keyword == long_keyword.strip()

    def test_keyword_with_hyphens(self):
        """Test that hyphenated keywords are counted correctly."""
        keyword = TieredKeyword(
            keyword="user-friendly project management",  # 3 words
            search_volume=200,
            competition="MEDIUM (45)",
            strategy="Target UX-conscious project managers"
        )

        assert keyword.keyword == "user-friendly project management"

    def test_keyword_with_special_characters(self):
        """Test keywords with special characters."""
        keyword = TieredKeyword(
            keyword="C++ programming tools",  # 3 words
            search_volume=300,
            competition="LOW (30)",
            strategy="Target C++ developers"
        )

        assert keyword.keyword == "C++ programming tools"

    def test_empty_keyword_accepted(self):
        """Test that empty keyword is accepted (but stripped to empty)."""
        keyword = TieredKeyword(
            keyword="",
            search_volume=100,
            competition="LOW (20)",
            strategy="Test strategy"
        )
        # TieredKeyword accepts empty strings (just strips them)
        assert keyword.keyword == ""

    def test_optional_intent_field(self):
        """Test that intent field is optional."""
        # Without intent
        keyword1 = TieredKeyword(
            keyword="test keyword",
            search_volume=100,
            competition="LOW (20)",
            strategy="Basic targeting strategy"
        )
        assert keyword1.intent is None

        # With intent
        keyword2 = TieredKeyword(
            keyword="test keyword",
            search_volume=100,
            competition="LOW (20)",
            strategy="Basic targeting strategy",
            intent="High conversion intent"
        )
        assert keyword2.intent == "High conversion intent"

    def test_keyword_internal_whitespace_preserved(self):
        """Test that keywords with internal multiple spaces are preserved after strip."""
        keyword = TieredKeyword(
            keyword="project  management  software",  # Extra internal spaces
            search_volume=100,
            competition="LOW (20)",
            strategy="Test strategy"
        )

        # Internal whitespace should be preserved (only leading/trailing stripped)
        assert keyword.keyword == "project  management  software"


class TestConceptualKeywordValidator:
    """Tests for ConceptualKeyword field validators."""

    def test_valid_keyword_short(self):
        """Test that short keywords (1-3 words) are accepted without warning."""
        keyword = ConceptualKeyword(
            keyword="seo tools",
            cluster="SEO Software",
            priority=1,
            rationale="Core market keyword"
        )

        assert keyword.keyword == "seo tools"

    def test_valid_keyword_medium_length(self):
        """Test that medium keywords (3-5 words) are accepted without warning."""
        keyword = ConceptualKeyword(
            keyword="best project management software",
            cluster="Project Management",
            priority=2,
            rationale="High-intent comparison keyword"
        )

        assert keyword.keyword == "best project management software"

    def test_long_keyword_logs_warning(self, caplog):
        """Test that long keywords (6+ words) log warning but are still accepted."""
        with caplog.at_level(logging.WARNING):
            keyword = ConceptualKeyword(
                keyword="best free project management software for small teams",  # 8 words
                cluster="Project Management",
                priority=3,
                rationale="Targeted long-tail keyword"
            )

            # Keyword should still be accepted
            assert keyword.keyword == "best free project management software for small teams"

            # Check that warning was logged
            assert "has 8 words" in caplog.text
            assert "recommended: 1-5 words" in caplog.text

    def test_very_long_keyword_logs_warning(self, caplog):
        """Test that very long keywords (10+ words) log warning."""
        with caplog.at_level(logging.WARNING):
            long_keyword = " ".join(["word"] * 12)  # 12 words
            keyword = ConceptualKeyword(
                keyword=long_keyword,
                cluster="Test Cluster",
                priority=5
            )

            assert keyword.keyword == long_keyword
            assert "has 12 words" in caplog.text

    def test_optional_rationale_field(self):
        """Test that rationale field is optional."""
        # Without rationale
        keyword1 = ConceptualKeyword(
            keyword="test keyword",
            cluster="Test Cluster",
            priority=3
        )
        assert keyword1.rationale is None

        # With rationale
        keyword2 = ConceptualKeyword(
            keyword="test keyword",
            cluster="Test Cluster",
            priority=3,
            rationale="Strategic importance explanation"
        )
        assert keyword2.rationale == "Strategic importance explanation"

    def test_priority_range_validation(self):
        """Test that priority must be 1-5."""
        # Valid priorities
        for priority in [1, 2, 3, 4, 5]:
            keyword = ConceptualKeyword(
                keyword="test",
                cluster="Test",
                priority=priority
            )
            assert keyword.priority == priority

        # Invalid priorities
        with pytest.raises(ValueError):
            ConceptualKeyword(
                keyword="test",
                cluster="Test",
                priority=0  # Too low
            )

        with pytest.raises(ValueError):
            ConceptualKeyword(
                keyword="test",
                cluster="Test",
                priority=6  # Too high
            )


class TestTier0LightResultEmptyKeywords:
    """Tests for Tier0LightResult graceful degradation with empty keywords."""

    def test_empty_tier_0_keywords_accepted(self):
        """Test that empty tier_0_keywords list is accepted (graceful degradation)."""
        result = Tier0LightResult(
            tier_0_keywords=[],
            tier_0_strategy="No premium keywords found in this niche."
        )
        assert result.tier_0_keywords == []
        assert "No premium keywords" in result.tier_0_strategy

    def test_default_values_when_no_keywords(self):
        """Test that default values are used when instantiated without args."""
        result = Tier0LightResult()
        assert result.tier_0_keywords == []
        assert "No Tier 0 premium keywords identified" in result.tier_0_strategy

    def test_with_keywords_still_works(self):
        """Test that normal case with keywords still works."""
        result = Tier0LightResult(
            tier_0_keywords=[
                LightweightKeywordSelection(
                    keyword="best seo tools",
                    strategy="Target high-intent users"
                )
            ],
            tier_0_strategy="Focus on premium SEO tool keywords."
        )
        assert len(result.tier_0_keywords) == 1
        assert result.tier_0_keywords[0].keyword == "best seo tools"

    def test_custom_strategy_with_empty_keywords(self):
        """Test custom strategy message when no keywords found."""
        result = Tier0LightResult(
            tier_0_keywords=[],
            tier_0_strategy="Market is highly competitive - no Tier 0 opportunities."
        )
        assert result.tier_0_keywords == []
        assert "highly competitive" in result.tier_0_strategy


class TestTier1LightResultEmptyKeywords:
    """Tests for Tier1LightResult graceful degradation with empty keywords."""

    def test_empty_tier_1_keywords_accepted(self):
        """Test that empty tier_1_keywords list is accepted (graceful degradation)."""
        result = Tier1LightResult(
            tier_1_keywords=[],
            tier_1_quick_win_strategy="No quick-win keywords found."
        )
        assert result.tier_1_keywords == []

    def test_default_values_when_no_keywords(self):
        """Test that default values are used when instantiated without args."""
        result = Tier1LightResult()
        assert result.tier_1_keywords == []
        assert "No Tier 1 quick win keywords identified" in result.tier_1_quick_win_strategy

    def test_with_keywords_still_works(self):
        """Test that normal case with keywords still works."""
        result = Tier1LightResult(
            tier_1_keywords=[
                LightweightKeywordSelection(
                    keyword="project management app",
                    strategy="Target SMB market"
                )
            ],
            tier_1_quick_win_strategy="Focus on mid-opportunity keywords."
        )
        assert len(result.tier_1_keywords) == 1
        assert result.tier_1_keywords[0].keyword == "project management app"


# --- Shared helpers for content strategy tests ---

_CONTENT_STRATEGY_TEXT = "A" * 100  # Meets min_length=100
_TECH_SEO_TEXT = "B" * 50  # Meets min_length=50


def _make_page_type_dict(name: str, keywords: list[str]) -> dict:
    """Helper to build a minimal KeywordBasedPageTypeLight dict."""
    return {
        "page_type_name": name,
        "url_pattern": f"/{name.lower().replace(' ', '-')}/",
        "target_keyword_cluster": "Tier 1",
        "example_keywords": keywords,
        "primary_intent": "informational",
        "priority": "P0",
        "seo_optimization_notes": "Target these keywords.",
    }


def _make_full_page_type_dict(name: str, keywords: list[str]) -> dict:
    """Helper to build a minimal KeywordBasedPageType dict (full-weight)."""
    return _make_page_type_dict(name, keywords)


class TestCategoryLightResultValidator:
    """Tests for CategoryLightResult pre-validation filter."""

    def test_empty_group_filtered_out(self):
        """Groups with empty keywords list are removed."""
        result = CategoryLightResult(**{
            "tier_4_category_groups": [
                {
                    "category_name": "Good Group",
                    "keywords": [{"keyword_name": "seo tools"}],
                    "strategy_recommendation": "Target SEO.",
                },
                {
                    "category_name": "Empty Group",
                    "keywords": [],
                    "strategy_recommendation": "Nothing here.",
                },
            ],
            "category_strategy_notes": "Some notes.",
        })
        assert result.tier_4_category_groups is not None
        assert len(result.tier_4_category_groups) == 1
        assert result.tier_4_category_groups[0].category_name == "Good Group"

    def test_all_empty_groups_become_none(self):
        """When all groups have empty keywords, field becomes None."""
        result = CategoryLightResult(**{
            "tier_4_category_groups": [
                {
                    "category_name": "Empty A",
                    "keywords": [],
                    "strategy_recommendation": "Nothing.",
                },
                {
                    "category_name": "Empty B",
                    "keywords": [],
                    "strategy_recommendation": "Also nothing.",
                },
            ],
        })
        assert result.tier_4_category_groups is None

    def test_missing_keywords_key_filtered(self):
        """Groups missing the keywords key entirely are filtered out."""
        result = CategoryLightResult(**{
            "tier_4_category_groups": [
                {
                    "category_name": "No Keywords Key",
                    "strategy_recommendation": "Oops.",
                },
            ],
        })
        assert result.tier_4_category_groups is None

    def test_valid_groups_unchanged(self):
        """Valid groups pass through without modification."""
        result = CategoryLightResult(**{
            "tier_4_category_groups": [
                {
                    "category_name": "Group A",
                    "keywords": [{"keyword_name": "kw1"}],
                    "strategy_recommendation": "Strategy A.",
                },
                {
                    "category_name": "Group B",
                    "keywords": [{"keyword_name": "kw2"}],
                    "strategy_recommendation": "Strategy B.",
                },
            ],
        })
        assert result.tier_4_category_groups is not None
        assert len(result.tier_4_category_groups) == 2

    def test_none_input_unchanged(self):
        """None tier_4_category_groups stays None."""
        result = CategoryLightResult(**{
            "tier_4_category_groups": None,
        })
        assert result.tier_4_category_groups is None


class TestContentStrategyResultLightValidator:
    """Tests for ContentStrategyResultLight pre-validation filter."""

    def test_page_type_with_empty_keywords_filtered(self):
        """Page types with empty example_keywords are removed."""
        result = ContentStrategyResultLight(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_page_type_dict("Good Type", ["kw1", "kw2"]),
                _make_page_type_dict("Bad Type", []),
            ],
        })
        assert result.keyword_based_page_types is not None
        assert len(result.keyword_based_page_types) == 1
        assert result.keyword_based_page_types[0].page_type_name == "Good Type"

    def test_page_type_with_single_keyword_filtered(self):
        """Page types with only 1 keyword (< min_length=2) are filtered."""
        result = ContentStrategyResultLight(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_page_type_dict("Okay", ["kw1", "kw2", "kw3"]),
                _make_page_type_dict("Too Few", ["only_one"]),
            ],
        })
        assert result.keyword_based_page_types is not None
        assert len(result.keyword_based_page_types) == 1

    def test_all_invalid_become_none(self):
        """When all page types have < 2 keywords, field becomes None."""
        result = ContentStrategyResultLight(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_page_type_dict("Empty", []),
                _make_page_type_dict("Single", ["one"]),
            ],
        })
        assert result.keyword_based_page_types is None

    def test_valid_page_types_unchanged(self):
        """Valid page types pass through without modification."""
        result = ContentStrategyResultLight(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_page_type_dict("Type A", ["kw1", "kw2"]),
                _make_page_type_dict("Type B", ["kw3", "kw4", "kw5"]),
            ],
        })
        assert result.keyword_based_page_types is not None
        assert len(result.keyword_based_page_types) == 2

    def test_none_page_types_unchanged(self):
        """None keyword_based_page_types stays None."""
        result = ContentStrategyResultLight(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": None,
        })
        assert result.keyword_based_page_types is None


class TestContentStrategyResultValidator:
    """Tests for ContentStrategyResult pre-validation filter (full-weight model)."""

    def test_page_type_with_empty_keywords_filtered(self):
        """Page types with empty example_keywords are removed."""
        result = ContentStrategyResult(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_full_page_type_dict("Good A", ["kw1", "kw2"]),
                _make_full_page_type_dict("Good B", ["kw3", "kw4"]),
                _make_full_page_type_dict("Bad", []),
            ],
        })
        assert result.keyword_based_page_types is not None
        assert len(result.keyword_based_page_types) == 2

    def test_single_valid_becomes_none_due_to_min_length(self):
        """Field becomes None when < 2 valid page types remain (field min_length=2)."""
        result = ContentStrategyResult(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_full_page_type_dict("Only One", ["kw1", "kw2"]),
                _make_full_page_type_dict("Bad", []),
            ],
        })
        # Only 1 valid item remains, but field requires min_length=2, so set to None
        assert result.keyword_based_page_types is None

    def test_all_invalid_become_none(self):
        """When all page types are invalid, field becomes None."""
        result = ContentStrategyResult(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_full_page_type_dict("Empty", []),
                _make_full_page_type_dict("Single", ["one"]),
            ],
        })
        assert result.keyword_based_page_types is None

    def test_valid_page_types_unchanged(self):
        """Valid page types with >= 2 items pass through unchanged."""
        result = ContentStrategyResult(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": [
                _make_full_page_type_dict("Type A", ["kw1", "kw2"]),
                _make_full_page_type_dict("Type B", ["kw3", "kw4", "kw5"]),
                _make_full_page_type_dict("Type C", ["kw6", "kw7"]),
            ],
        })
        assert result.keyword_based_page_types is not None
        assert len(result.keyword_based_page_types) == 3

    def test_none_page_types_unchanged(self):
        """None keyword_based_page_types stays None."""
        result = ContentStrategyResult(**{
            "content_strategy": _CONTENT_STRATEGY_TEXT,
            "technical_seo_recommendations": _TECH_SEO_TEXT,
            "keyword_based_page_types": None,
        })
        assert result.keyword_based_page_types is None
