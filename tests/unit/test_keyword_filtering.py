"""
Tests for keyword filtering and relevance validation utilities.
"""

import pytest
from unittest.mock import MagicMock
from nicheiq.utils.keyword_filtering import (
    filter_single_word_keywords,
    check_keyword_relevance
)


class TestFilterSingleWordKeywords:
    """Tests for filter_single_word_keywords function."""

    def test_filter_basic_single_words(self):
        """Test filtering single-word keywords."""
        keywords = [
            {"keyword": "software", "search_volume": 1000},
            {"keyword": "project management", "search_volume": 500},
            {"keyword": "tools", "search_volume": 800},
            {"keyword": "best software", "search_volume": 300},
        ]

        result = filter_single_word_keywords(keywords, "Test")

        # Should keep only multi-word keywords
        assert len(result) == 2
        assert result[0]["keyword"] == "project management"
        assert result[1]["keyword"] == "best software"

    def test_filter_hyphenated_keywords(self):
        """Test that hyphenated keywords count as multi-word."""
        keywords = [
            {"keyword": "co-working", "search_volume": 500},
            {"keyword": "software", "search_volume": 1000},
            {"keyword": "user-friendly", "search_volume": 300},
        ]

        result = filter_single_word_keywords(keywords, "Test")

        # Hyphenated keywords should be kept (count as 2 words)
        assert len(result) == 2
        assert result[0]["keyword"] == "co-working"
        assert result[1]["keyword"] == "user-friendly"

    def test_filter_slash_separated_keywords(self):
        """Test that slash-separated keywords count as multi-word."""
        keywords = [
            {"keyword": "B2B/B2C", "search_volume": 500},
            {"keyword": "SaaS/PaaS", "search_volume": 300},
            {"keyword": "cloud", "search_volume": 1000},
        ]

        result = filter_single_word_keywords(keywords, "Test")

        # Slash-separated keywords should be kept
        assert len(result) == 2
        assert result[0]["keyword"] == "B2B/B2C"
        assert result[1]["keyword"] == "SaaS/PaaS"

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty list."""
        result = filter_single_word_keywords([], "Test")
        assert result == []

    def test_all_single_words_returns_empty(self):
        """Test that list of only single words returns empty."""
        keywords = [
            {"keyword": "software", "search_volume": 1000},
            {"keyword": "tools", "search_volume": 800},
            {"keyword": "apps", "search_volume": 600},
        ]

        result = filter_single_word_keywords(keywords, "Test")
        assert result == []

    def test_all_multi_words_returns_all(self):
        """Test that list of only multi-word keywords returns all."""
        keywords = [
            {"keyword": "project management", "search_volume": 1000},
            {"keyword": "best software", "search_volume": 800},
            {"keyword": "top tools", "search_volume": 600},
        ]

        result = filter_single_word_keywords(keywords, "Test")
        assert len(result) == 3

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        keywords = [
            {"keyword": "  software  ", "search_volume": 1000},
            {"keyword": "  project management  ", "search_volume": 500},
        ]

        result = filter_single_word_keywords(keywords, "Test")

        # Should strip whitespace and still correctly identify single vs multi-word
        assert len(result) == 1
        assert result[0]["keyword"] == "  project management  "

    def test_missing_keyword_field_handled(self):
        """Test that missing 'keyword' field is handled gracefully."""
        keywords = [
            {"search_volume": 1000},  # No keyword field
            {"keyword": "project management", "search_volume": 500},
        ]

        result = filter_single_word_keywords(keywords, "Test")

        # Should handle missing keyword field (treat as empty string = 0 words)
        assert len(result) == 1
        assert result[0]["keyword"] == "project management"


class TestCheckKeywordRelevance:
    """Tests for check_keyword_relevance function (integration tests)."""

    @pytest.fixture(autouse=True)
    def _stub_semantic_validator(self, monkeypatch):
        """Criterion-3 semantic relevance calls a live LLM (KeywordRelevanceValidator.validate_batch
        → LLMService.invoke_structured). These tests assert only loose, volume-driven bounds, so stub
        the validator to return no semantic matches (semantic_score 0.0) — deterministic and hermetic."""
        from nicheiq.utils.validation import keyword_validator
        monkeypatch.setattr(
            keyword_validator.KeywordRelevanceValidator, "validate_batch",
            lambda self, *a, **k: [],
        )

    def test_empty_keywords_returns_zero_score(self):
        """Test that empty keyword list returns 0.0 score."""
        mock_solution = MagicMock()

        score, good_kws, issues = check_keyword_relevance([], mock_solution)

        assert score == 0.0
        assert good_kws == []
        assert "no_keywords_generated" in issues

    def test_low_volume_ratio_affects_score(self):
        """Test that low volume ratio affects the overall score."""
        # Use multi-word keywords to avoid pre-filtering
        keywords = [
            {"keyword": "low volume one", "search_volume": 5},
            {"keyword": "low volume two", "search_volume": 3},
            {"keyword": "low volume three", "search_volume": 8},
            {"keyword": "low volume four", "search_volume": 2},
            {"keyword": "good volume keyword", "search_volume": 100},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "Test"
        mock_solution.description = "Test description"

        score, good_kws, issues = check_keyword_relevance(keywords, mock_solution)

        # With 80% low volume keywords, score should be reduced
        assert score < 0.5
        # Should have issues (either low_search_volume or semantic_mismatch)
        assert len(issues) > 0

    def test_null_search_volume_validation_failure(self):
        """Test that keywords with missing search_volume field are detected as validation failures."""
        keywords = [
            {"keyword": "missing volume one"},  # No search_volume field
            {"keyword": "missing volume two"},  # No search_volume field
            {"keyword": "good keyword here", "search_volume": 100},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "Test"
        mock_solution.description = "Test description"

        score, good_kws, issues = check_keyword_relevance(keywords, mock_solution)

        # Should detect validation failure
        # Note: Function treats missing volume as 0, which counts as "low volume"
        assert score < 1.0  # Score should be reduced
        assert len(issues) > 0  # Should have some issues

    def test_none_search_volume_handled_gracefully(self):
        """Test that keywords with None search_volume are handled without crash."""
        keywords = [
            {"keyword": "none volume one", "search_volume": None},  # Explicit None
            {"keyword": "none volume two", "search_volume": None},  # Explicit None
            {"keyword": "good keyword here", "search_volume": 100},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "Test"
        mock_solution.description = "Test description"

        # Should not crash with TypeError
        score, good_kws, issues = check_keyword_relevance(keywords, mock_solution)

        # Should treat None as 0 (low volume)
        assert score < 1.0
        assert len(issues) > 0

    def test_high_volume_keywords_pass(self):
        """Test that keywords with good volume get higher scores."""
        keywords = [
            {"keyword": "project management software", "search_volume": 500},
            {"keyword": "task tracking tools", "search_volume": 300},
            {"keyword": "team collaboration platform", "search_volume": 400},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "ProjectPro"
        mock_solution.description = "Project management software"

        score, good_kws, issues = check_keyword_relevance(keywords, mock_solution)

        # With all high volume keywords, volume score component should be good
        assert score > 0.3

    def test_niche_context_passed_to_validator(self):
        """Test that niche context is passed to semantic validator."""
        keywords = [
            {"keyword": "project management", "search_volume": 500},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "ProjectPro"
        mock_solution.description = "Project management software"

        mock_niche = MagicMock()
        mock_niche.niche_description = "Project management tools"

        # Just verify it doesn't crash with niche_context
        score, good_kws, issues = check_keyword_relevance(
            keywords, mock_solution, niche_context=mock_niche
        )

        # Should complete without errors
        assert isinstance(score, float)
        assert isinstance(good_kws, list)
        assert isinstance(issues, list)

    def test_validation_cache_parameter_accepted(self):
        """Test that validation_cache parameter is accepted."""
        keywords = [
            {"keyword": "test keyword phrase", "search_volume": 100},
        ]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "Test"
        mock_solution.description = "Test description"

        validation_cache = {}

        # Should accept cache parameter
        score, good_kws, issues = check_keyword_relevance(
            keywords, mock_solution, validation_cache=validation_cache
        )

        # Should complete without errors
        assert isinstance(score, float)

    def test_returns_three_element_tuple(self):
        """Test that function returns tuple of (score, keywords, issues)."""
        keywords = [{"keyword": "test phrase", "search_volume": 100}]
        mock_solution = MagicMock()
        mock_solution.project_type = "saas"
        mock_solution.solution_name = "Test"
        mock_solution.description = "Test"

        result = check_keyword_relevance(keywords, mock_solution)

        # Should return 3-element tuple
        assert isinstance(result, tuple)
        assert len(result) == 3
        score, good_kws, issues = result
        assert isinstance(score, float)
        assert isinstance(good_kws, list)
        assert isinstance(issues, list)
