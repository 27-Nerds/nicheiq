"""
Tests for utility functions.
"""

import pytest
from nicheiq.utils.helpers import SearchHelper


class TestSearchHelper:
    """Tests for SearchHelper utility."""

    def test_extract_urls_from_text(self):
        """Test URL extraction from text."""
        text = """
        Check out this post: https://reddit.com/r/saas/comments/abc123
        And this tweet: https://twitter.com/user/status/123456789
        Also see: https://example.com/page
        """

        urls = SearchHelper.extract_urls(text)

        assert len(urls) >= 2  # At least the Reddit and Twitter URLs
        assert any("reddit.com" in url for url in urls)
        assert any("twitter.com" in url for url in urls)

    def test_extract_reddit_urls(self):
        """Test extracting only Reddit URLs."""
        text = """
        https://reddit.com/r/saas/comments/abc123
        https://twitter.com/user/status/123456789
        https://old.reddit.com/r/startups/comments/def456
        """

        all_urls = SearchHelper.extract_urls(text)
        reddit_urls = [url for url in all_urls if "reddit.com" in url]

        assert len(reddit_urls) >= 2  # Both Reddit URLs

    def test_extract_twitter_urls(self):
        """Test extracting Twitter/X URLs."""
        text = """
        https://twitter.com/user/status/123
        https://x.com/user/status/456
        https://reddit.com/r/test
        """

        all_urls = SearchHelper.extract_urls(text)
        twitter_urls = [url for url in all_urls if "twitter.com" in url or "x.com" in url]

        assert len(twitter_urls) >= 2  # Both Twitter/X URLs

    def test_extract_urls_empty_input(self):
        """Test URL extraction with empty input."""
        urls = SearchHelper.extract_urls("")
        assert urls == []

    def test_extract_urls_no_urls(self):
        """Test URL extraction when no URLs present."""
        text = "This is some text without any URLs in it."
        urls = SearchHelper.extract_urls(text)
        assert urls == []


def test_generate_competitive_queries():
    """Test competitive query generation."""
    from nicheiq.utils.helpers import generate_competitive_queries

    solution_name = "Project Management Tool"
    queries = generate_competitive_queries(solution_name, num_queries=5)

    assert len(queries) <= 5
    assert all(isinstance(q, str) for q in queries)
    assert any("project management" in q.lower() for q in queries)


# Note: QueryGenerator tests are skipped as they require OpenAI API
# Integration tests should cover the full query generation workflow
@pytest.mark.skip(reason="Requires OpenAI API key")
class TestQueryGenerator:
    """Tests for LLM-based query generation (requires API)."""

    def test_query_generation(self):
        """Test generating queries from niche description."""
        from nicheiq.utils.helpers import QueryGenerator

        generator = QueryGenerator()
        queries = generator.generate_queries(
            niche_description="AI tools for content creators", num_queries=5
        )

        assert len(queries) <= 5
        assert all("query" in q for q in queries)
        assert all("type" in q for q in queries)
