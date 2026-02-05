"""
Tests for PRAW native Reddit search supplement.

Ensures search_subreddits() uses PRAW's subreddit.search() with time_filter
to find very recent posts that Google hasn't indexed yet.
"""

import re
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nicheiq.tools.reddit_tool import RedditCollectorTool


# ---------------------------------------------------------------------------
# Helper: mock PRAW submission objects
# ---------------------------------------------------------------------------

def _mock_submission(post_id="abc123", title="Test post", permalink="/r/test/comments/abc123/test_post/"):
    """Create a mock PRAW Submission."""
    sub = MagicMock()
    sub.id = post_id
    sub.title = title
    sub.permalink = permalink
    return sub


# ===================================================================
# A. Subreddit extraction regex
# ===================================================================

class TestExtractSubredditsFromUrls:
    """Extract subreddit names from Reddit URLs for targeted PRAW search."""

    def test_standard_comments_url(self):
        """Extract subreddit from /r/sub/comments/... URL."""
        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/my_post/"]
        result = RedditCollectorTool.extract_subreddits_from_urls(urls)
        assert "SaaS" in result

    def test_short_share_url(self):
        """Extract subreddit from /r/sub/s/... URL."""
        urls = ["https://www.reddit.com/r/startups/s/abc123"]
        result = RedditCollectorTool.extract_subreddits_from_urls(urls)
        assert "startups" in result

    def test_dedup_subreddits(self):
        """Multiple URLs from same subreddit produce one entry."""
        urls = [
            "https://www.reddit.com/r/SaaS/comments/abc/post1/",
            "https://www.reddit.com/r/SaaS/comments/def/post2/",
            "https://www.reddit.com/r/startups/comments/ghi/post3/",
        ]
        result = RedditCollectorTool.extract_subreddits_from_urls(urls)
        assert len(result) == 2
        assert "SaaS" in result
        assert "startups" in result

    def test_no_match_returns_empty(self):
        """Non-Reddit URLs return empty list."""
        urls = ["https://twitter.com/user/status/123"]
        result = RedditCollectorTool.extract_subreddits_from_urls(urls)
        assert result == []

    def test_empty_input(self):
        """Empty input returns empty list."""
        result = RedditCollectorTool.extract_subreddits_from_urls([])
        assert result == []

    def test_max_5_subreddits(self):
        """Returns at most 5 subreddits (top by frequency)."""
        urls = [
            f"https://www.reddit.com/r/sub{i}/comments/abc/post/"
            for i in range(10)
        ]
        result = RedditCollectorTool.extract_subreddits_from_urls(urls)
        assert len(result) <= 5


# ===================================================================
# B. search_subreddits method
# ===================================================================

class TestSearchSubreddits:
    """Tests for the PRAW native search method."""

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_returns_search_result_items(self, mock_client_fn):
        """Results should be SearchResultItem objects."""
        from nicheiq.models.research_state import SearchResultItem

        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = [_mock_submission()]

        tool = RedditCollectorTool()
        results = tool.search_subreddits(
            queries=["AI tools"],
            subreddits=["SaaS"],
        )
        assert len(results) >= 1
        assert isinstance(results[0], SearchResultItem)

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_url_format_normalized(self, mock_client_fn):
        """URLs should be normalized to https://www.reddit.com{permalink}."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = [
            _mock_submission(permalink="/r/SaaS/comments/abc123/test/")
        ]

        tool = RedditCollectorTool()
        results = tool.search_subreddits(queries=["test"], subreddits=["SaaS"])
        assert results[0].url == "https://www.reddit.com/r/SaaS/comments/abc123/test/"

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_skips_already_collected(self, mock_client_fn):
        """Already collected URLs should be skipped."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = [
            _mock_submission(permalink="/r/SaaS/comments/abc123/test/"),
            _mock_submission(post_id="def456", permalink="/r/SaaS/comments/def456/other/"),
        ]

        tool = RedditCollectorTool()
        results = tool.search_subreddits(
            queries=["test"],
            subreddits=["SaaS"],
            already_collected_urls={"https://www.reddit.com/r/SaaS/comments/abc123/test/"},
        )
        assert len(results) == 1
        assert "def456" in results[0].url

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_default_time_filter(self, mock_client_fn):
        """Default time_filter should be 'month'."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = []

        tool = RedditCollectorTool()
        tool.search_subreddits(queries=["test"], subreddits=["SaaS"])

        mock_sub.search.assert_called_once()
        call_kwargs = mock_sub.search.call_args
        assert call_kwargs.kwargs.get("time_filter") == "month" or \
               (len(call_kwargs.args) > 1 and call_kwargs.args[1] == "month") or \
               call_kwargs[1].get("time_filter") == "month"

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_custom_time_filter(self, mock_client_fn):
        """Custom time_filter is passed through."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = []

        tool = RedditCollectorTool()
        tool.search_subreddits(
            queries=["test"], subreddits=["SaaS"], time_filter="week",
        )

        call_kwargs = mock_sub.search.call_args
        # Check time_filter is "week"
        assert "week" in str(call_kwargs)

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_praw_exception_handled(self, mock_client_fn):
        """PRAW exceptions should be caught per-query, not crash."""
        import praw.exceptions
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.side_effect = praw.exceptions.PRAWException("API error")

        tool = RedditCollectorTool()
        results = tool.search_subreddits(queries=["test"], subreddits=["SaaS"])
        assert results == []

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_circuit_breaker_after_3_failures(self, mock_client_fn):
        """After 3 consecutive failures, remaining queries should be skipped."""
        import praw.exceptions
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.side_effect = praw.exceptions.PRAWException("fail")

        tool = RedditCollectorTool()
        # 5 queries, but should stop after 3 consecutive failures
        results = tool.search_subreddits(
            queries=["q1", "q2", "q3", "q4", "q5"],
            subreddits=["SaaS"],
        )
        assert results == []
        # Should have been called 3 times (circuit breaker trips)
        assert mock_sub.search.call_count == 3

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_empty_queries(self, mock_client_fn):
        """Empty query list returns empty results."""
        tool = RedditCollectorTool()
        results = tool.search_subreddits(queries=[], subreddits=["SaaS"])
        assert results == []

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_empty_subreddits(self, mock_client_fn):
        """Empty subreddit list returns empty results."""
        tool = RedditCollectorTool()
        results = tool.search_subreddits(queries=["test"], subreddits=[])
        assert results == []

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_dedup_across_queries(self, mock_client_fn):
        """Same post found by multiple queries should only appear once."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        # Same submission returned for both queries
        same_sub = _mock_submission()
        mock_sub.search.return_value = [same_sub]

        tool = RedditCollectorTool()
        results = tool.search_subreddits(
            queries=["query1", "query2"],
            subreddits=["SaaS"],
        )
        assert len(results) == 1

    @patch.object(RedditCollectorTool, '_get_reddit_client')
    def test_max_results_per_query(self, mock_client_fn):
        """max_results_per_query limits results from each search call."""
        mock_reddit = MagicMock()
        mock_client_fn.return_value = mock_reddit
        mock_sub = MagicMock()
        mock_reddit.subreddit.return_value = mock_sub
        mock_sub.search.return_value = []

        tool = RedditCollectorTool()
        tool.search_subreddits(
            queries=["test"], subreddits=["SaaS"], max_results_per_query=5,
        )

        call_kwargs = mock_sub.search.call_args
        assert "limit" in str(call_kwargs) or call_kwargs.kwargs.get("limit") == 5
