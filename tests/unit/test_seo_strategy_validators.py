"""
Tests for SEO strategy model validators.
"""

import pytest
import logging
from nicheiq.models.seo_strategy import TieredKeyword, ConceptualKeyword


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
