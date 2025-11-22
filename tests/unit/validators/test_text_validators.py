"""
Unit tests for text validators.

Tests TextValidator methods for keyword matching, truncation,
and text processing operations.
"""

import pytest

from nicheiq.validators import TextValidator


class TestHasScoreKeywords:
    """Test word-boundary keyword matching."""

    def test_finds_market_fit(self):
        """Test detection of 'market fit' phrase."""
        text = "The solution shows strong market fit with users."
        assert TextValidator.has_score_keywords(text) is True

    def test_finds_competitive(self):
        """Test detection of 'competitive' keyword."""
        text = "Analysis shows competitive advantage in pricing."
        assert TextValidator.has_score_keywords(text) is True

    def test_finds_feasibility(self):
        """Test detection of 'feasibility' keyword."""
        text = "Technical feasibility is high given existing tools."
        assert TextValidator.has_score_keywords(text) is True

    def test_finds_seo(self):
        """Test detection of 'seo' keyword."""
        text = "SEO potential is excellent for this niche."
        assert TextValidator.has_score_keywords(text) is True

    def test_finds_score(self):
        """Test detection of 'score' keyword."""
        text = "The overall score is 0.85 indicating strong fit."
        assert TextValidator.has_score_keywords(text) is True

    def test_false_positive_underscore(self):
        """Test that 'underscore' does NOT match 'score'."""
        text = "Use underscore for variable names."
        assert TextValidator.has_score_keywords(text) is False

    def test_false_positive_seems_optimized(self):
        """Test that 'seems optimized' does NOT match 'seo'."""
        text = "The code seems optimized for performance."
        assert TextValidator.has_score_keywords(text) is False

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert TextValidator.has_score_keywords("MARKET FIT") is True
        assert TextValidator.has_score_keywords("Market Fit") is True
        assert TextValidator.has_score_keywords("market fit") is True

    def test_empty_text(self):
        """Test empty text returns False."""
        assert TextValidator.has_score_keywords("") is False
        assert TextValidator.has_score_keywords(None) is False

    def test_no_keywords_found(self):
        """Test text with no keywords returns False."""
        text = "This is a regular sentence with no special words."
        assert TextValidator.has_score_keywords(text) is False


class TestHasNumericScore:
    """Test numeric score pattern matching."""

    def test_finds_valid_scores(self):
        """Test detection of valid score patterns."""
        assert TextValidator.has_numeric_score("Score: 0.85") is True
        assert TextValidator.has_numeric_score("Rating is 0.72") is True
        assert TextValidator.has_numeric_score("Perfect 1.00 match") is True
        assert TextValidator.has_numeric_score("Low score of 0.00") is True

    def test_rejects_invalid_scores(self):
        """Test rejection of invalid score patterns."""
        # Out of range
        assert TextValidator.has_numeric_score("Value: 2.50") is False
        assert TextValidator.has_numeric_score("Score: -0.50") is False

        # Wrong format
        assert TextValidator.has_numeric_score("Score: 0.8") is False  # One decimal
        assert TextValidator.has_numeric_score("Score: .85") is False  # No leading digit
        assert TextValidator.has_numeric_score("Score: 85") is False  # No decimal

    def test_empty_text(self):
        """Test empty text returns False."""
        assert TextValidator.has_numeric_score("") is False
        assert TextValidator.has_numeric_score(None) is False


class TestTruncateAtWordBoundary:
    """Test word-aware truncation."""

    def test_short_text_unchanged(self):
        """Test text shorter than max_length is unchanged."""
        text = "Short text"
        result = TextValidator.truncate_at_word_boundary(text, max_length=100)
        assert result == text

    def test_truncate_at_space(self):
        """Test truncation at word boundary."""
        text = "This is a long piece of text that needs truncation"
        result = TextValidator.truncate_at_word_boundary(text, max_length=20)

        # Should end with "..." and be <= 20 chars
        assert result.endswith("...")
        assert len(result) <= 20

        # Should not break mid-word
        assert not result[:-3].endswith(("pie", "tex"))  # Not breaking "piece" or "text"

    def test_no_spaces_truncates_at_limit(self):
        """Test truncation when no word boundaries found."""
        text = "Verylongtextwithoutanyspacesinit"
        result = TextValidator.truncate_at_word_boundary(text, max_length=20)

        assert result.endswith("...")
        assert len(result) == 20

    def test_custom_suffix(self):
        """Test custom truncation suffix."""
        text = "This is a long piece of text"
        result = TextValidator.truncate_at_word_boundary(
            text,
            max_length=20,
            suffix=" [more]",
        )

        assert result.endswith(" [more]")
        assert len(result) <= 20

    def test_empty_text(self):
        """Test empty text handling."""
        assert TextValidator.truncate_at_word_boundary("", max_length=100) == ""
        assert TextValidator.truncate_at_word_boundary(None, max_length=100) is None

    def test_exact_max_length(self):
        """Test text exactly at max_length."""
        text = "Exactly twenty chars"  # 20 chars
        result = TextValidator.truncate_at_word_boundary(text, max_length=20)

        # Should be unchanged (no truncation needed)
        assert result == text


class TestExtractSolutionNameBase:
    """Test solution name extraction."""

    def test_simple_name(self):
        """Test simple solution name without formatting."""
        assert TextValidator.extract_solution_name_base("ReliabilityRank") == "reliabilityrank"

    def test_name_with_colon(self):
        """Test name with colon separator."""
        name = "ReliabilityRank: Appliance Brand & Model Reliability Index"
        assert TextValidator.extract_solution_name_base(name) == "reliabilityrank"

    def test_name_with_dash(self):
        """Test name with dash separator."""
        name = "PetCareHub - Pet Health Platform"
        assert TextValidator.extract_solution_name_base(name) == "petcarehub"

    def test_name_with_spaces(self):
        """Test name with spaces."""
        name = "My Solution Name"
        # Takes everything before punctuation, removes spaces
        assert TextValidator.extract_solution_name_base(name) == "mysolutionname"

    def test_empty_name(self):
        """Test empty name handling."""
        assert TextValidator.extract_solution_name_base("") == ""
        assert TextValidator.extract_solution_name_base(None) == ""

    def test_name_with_special_chars(self):
        """Test name with special characters."""
        name = "AI-Powered@Solution#1"
        # Removes all non-alphanumeric
        assert TextValidator.extract_solution_name_base(name) == "aipoweredsolution1"


class TestValidateKeywordDensity:
    """Test keyword density validation."""

    def test_low_density_passes(self):
        """Test low keyword density passes validation."""
        # 1 keyword / 40+ words = ~2.5% density (below 3% threshold)
        text = "This is a very long piece of text content with only one single keyword occurrence that has many many more additional words here to properly reduce the overall density well below the three percent validation threshold for passing."
        keywords = ["keyword"]

        passes, density, warning = TextValidator.validate_keyword_density(text, keywords)

        assert passes is True
        assert density < 0.03
        assert warning is None

    def test_high_density_fails(self):
        """Test high keyword density fails validation."""
        text = "keyword keyword keyword keyword text"
        keywords = ["keyword"]

        passes, density, warning = TextValidator.validate_keyword_density(text, keywords)

        assert passes is False
        assert density > 0.03
        assert "exceeds" in warning

    def test_custom_max_density(self):
        """Test custom max density threshold."""
        text = "keyword keyword text text text"  # 40% density
        keywords = ["keyword"]

        # Should pass with higher threshold
        passes, _, _ = TextValidator.validate_keyword_density(
            text,
            keywords,
            max_density=0.50,
        )
        assert passes is True

        # Should fail with lower threshold
        passes, _, _ = TextValidator.validate_keyword_density(
            text,
            keywords,
            max_density=0.30,
        )
        assert passes is False

    def test_multiple_keywords(self):
        """Test density calculation with multiple keywords."""
        text = "seo optimization and seo strategy for better seo"
        keywords = ["seo", "optimization", "strategy"]

        passes, density, _ = TextValidator.validate_keyword_density(text, keywords)

        # 5 keyword occurrences / 9 total words = 55%
        assert density > 0.5
        assert passes is False

    def test_empty_text(self):
        """Test empty text handling."""
        passes, density, warning = TextValidator.validate_keyword_density(
            "",
            ["keyword"],
        )

        assert passes is True
        assert density == 0.0
        assert warning is None

    def test_empty_keywords(self):
        """Test empty keywords list."""
        passes, density, warning = TextValidator.validate_keyword_density(
            "Some text here",
            [],
        )

        assert passes is True
        assert density == 0.0
        assert warning is None

    def test_case_insensitive_matching(self):
        """Test keyword matching is case-insensitive."""
        text = "SEO optimization and Seo strategy for better sEo"
        keywords = ["seo"]

        _, density, _ = TextValidator.validate_keyword_density(text, keywords)

        # All 3 "seo" variants should be counted
        # 3 occurrences / 9 words = 33%
        assert density > 0.3
