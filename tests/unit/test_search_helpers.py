"""
Tests for search helper utilities.
"""

from unittest.mock import patch, MagicMock

import pytest
from nicheiq.utils.search_helpers import SearchHelper
from nicheiq.models.research_state import SearchResultItem


class TestBuildRedditQuery:
    """Tests for build_reddit_query method."""

    def test_reddit_query_without_subreddit(self):
        """Test building Reddit query without specific subreddit."""
        query = SearchHelper.build_reddit_query("AI tools for content creators")
        assert query == "site:reddit.com AI tools for content creators"

    def test_reddit_query_with_subreddit(self):
        """Test building Reddit query with specific subreddit."""
        query = SearchHelper.build_reddit_query(
            "best project management tools",
            subreddit="productivity"
        )
        assert query == "site:reddit.com/r/productivity best project management tools"

    def test_reddit_query_preserves_special_characters(self):
        """Test that special characters in query are preserved."""
        query = SearchHelper.build_reddit_query("C++ vs Rust", subreddit="programming")
        assert query == "site:reddit.com/r/programming C++ vs Rust"


class TestBuildTwitterQuery:
    """Tests for build_twitter_query method."""

    def test_twitter_query_includes_both_domains(self):
        """Test that Twitter query includes both twitter.com and x.com."""
        query = SearchHelper.build_twitter_query("startup founder problems")
        assert "(site:twitter.com OR site:x.com)" in query
        assert "startup founder problems" in query

    def test_twitter_query_format(self):
        """Test exact format of Twitter query."""
        query = SearchHelper.build_twitter_query("test query")
        assert query == "(site:twitter.com OR site:x.com) test query"


class TestExtractResultsFromSerper:
    """Tests for extract_results_from_serper method."""

    def test_extract_reddit_submissions_only(self):
        """Test that only Reddit submission URLs (/comments/) are extracted."""
        search_results = {
            "organic": [
                {
                    "link": "https://reddit.com/r/test/comments/abc123/title",
                    "title": "Test post",
                    "snippet": "Test snippet"
                },
                {
                    "link": "https://reddit.com/r/test",  # Subreddit page (exclude)
                    "title": "Subreddit",
                    "snippet": "Subreddit page"
                },
                {
                    "link": "https://reddit.com/r/test/about",  # About page (exclude)
                    "title": "About",
                    "snippet": "About page"
                }
            ]
        }

        results = SearchHelper.extract_results_from_serper(search_results, "reddit.com")

        assert len(results) == 1
        assert results[0].url == "https://reddit.com/r/test/comments/abc123/title"
        assert results[0].title == "Test post"
        assert results[0].snippet == "Test snippet"

    def test_extract_twitter_status_urls_only(self):
        """Test that only Twitter status URLs (/status/) are extracted."""
        search_results = {
            "organic": [
                {
                    "link": "https://twitter.com/user/status/123456789",
                    "title": "Tweet 1",
                    "snippet": "Tweet content"
                },
                {
                    "link": "https://x.com/user/status/987654321",
                    "title": "Tweet 2",
                    "snippet": "X.com tweet"
                },
                {
                    "link": "https://twitter.com/user",  # Profile page (exclude)
                    "title": "Profile",
                    "snippet": "User profile"
                },
                {
                    "link": "https://twitter.com/i/web/status/111",  # Has /status/ so will be included
                    "title": "Share",
                    "snippet": "Share link"
                }
            ]
        }

        # Test with twitter.com domain
        results_twitter = SearchHelper.extract_results_from_serper(search_results, "twitter.com")
        # Should get 2 results (both have /status/ and twitter.com domain)
        assert len(results_twitter) == 2
        assert all("/status/" in r.url for r in results_twitter)

        # Test with x.com domain
        results_x = SearchHelper.extract_results_from_serper(search_results, "x.com")
        assert len(results_x) == 1
        assert "/status/" in results_x[0].url

    def test_deduplication_by_url(self):
        """Test that duplicate URLs are removed while preserving order."""
        search_results = {
            "organic": [
                {
                    "link": "https://reddit.com/r/test/comments/abc123/title",
                    "title": "First occurrence",
                    "snippet": "Snippet 1"
                },
                {
                    "link": "https://reddit.com/r/test/comments/def456/other",
                    "title": "Different post",
                    "snippet": "Snippet 2"
                },
                {
                    "link": "https://reddit.com/r/test/comments/abc123/title",  # Duplicate
                    "title": "Second occurrence (should be ignored)",
                    "snippet": "Snippet 3"
                }
            ]
        }

        results = SearchHelper.extract_results_from_serper(search_results, "reddit.com")

        assert len(results) == 2
        # First occurrence should be kept
        assert results[0].title == "First occurrence"
        assert results[1].title == "Different post"

    def test_empty_search_results(self):
        """Test handling of empty search results."""
        search_results = {"organic": []}
        results = SearchHelper.extract_results_from_serper(search_results, "reddit.com")
        assert results == []

    def test_invalid_search_results_type(self):
        """Test handling of invalid search results type."""
        # Not a dict
        results = SearchHelper.extract_results_from_serper("invalid", "reddit.com")
        assert results == []

        # Dict without 'organic' key
        results = SearchHelper.extract_results_from_serper({"other_key": []}, "reddit.com")
        assert results == []

    def test_missing_fields_in_results(self):
        """Test handling of results with missing fields."""
        search_results = {
            "organic": [
                {
                    "link": "https://reddit.com/r/test/comments/abc123/title"
                    # Missing title and snippet
                },
                {
                    "title": "No link",
                    "snippet": "No link in this result"
                    # Missing link - should be skipped
                }
            ]
        }

        results = SearchHelper.extract_results_from_serper(search_results, "reddit.com")

        # First result should be included with empty title/snippet
        assert len(results) == 1
        assert results[0].url == "https://reddit.com/r/test/comments/abc123/title"
        assert results[0].title == ""
        assert results[0].snippet == ""

    def test_other_domain_no_filtering(self):
        """Test that other domains don't apply Reddit/Twitter filtering."""
        search_results = {
            "organic": [
                {
                    "link": "https://example.com/any/path",
                    "title": "Example",
                    "snippet": "No filtering"
                },
                {
                    "link": "https://example.com/another/path",
                    "title": "Example 2",
                    "snippet": "Also included"
                }
            ]
        }

        results = SearchHelper.extract_results_from_serper(search_results, "example.com")

        # All results should be included (no /comments/ or /status/ filtering)
        assert len(results) == 2


class TestExtractUrlsFromSerper:
    """Tests for extract_urls_from_serper method."""

    def test_extract_reddit_urls_only_submissions(self):
        """Test that only Reddit submission URLs are extracted."""
        search_results = {
            "organic": [
                {"link": "https://reddit.com/r/test/comments/abc123/title"},
                {"link": "https://reddit.com/r/test"},  # Subreddit (exclude)
                {"link": "https://reddit.com/r/test/comments/def456/another"}
            ]
        }

        urls = SearchHelper.extract_urls_from_serper(search_results, "reddit.com")

        assert len(urls) == 2
        assert "https://reddit.com/r/test/comments/abc123/title" in urls
        assert "https://reddit.com/r/test/comments/def456/another" in urls

    def test_extract_twitter_urls_only_status(self):
        """Test that only Twitter status URLs are extracted."""
        search_results = {
            "organic": [
                {"link": "https://twitter.com/user/status/123"},
                {"link": "https://x.com/user/status/456"},
                {"link": "https://twitter.com/user"}  # Profile (exclude)
            ]
        }

        urls_twitter = SearchHelper.extract_urls_from_serper(search_results, "twitter.com")
        urls_x = SearchHelper.extract_urls_from_serper(search_results, "x.com")

        assert len(urls_twitter) == 1
        assert len(urls_x) == 1

    def test_url_deduplication(self):
        """Test that duplicate URLs are removed."""
        search_results = {
            "organic": [
                {"link": "https://reddit.com/r/test/comments/abc123/title"},
                {"link": "https://reddit.com/r/test/comments/def456/other"},
                {"link": "https://reddit.com/r/test/comments/abc123/title"}  # Duplicate
            ]
        }

        urls = SearchHelper.extract_urls_from_serper(search_results, "reddit.com")

        assert len(urls) == 2
        assert urls[0] == "https://reddit.com/r/test/comments/abc123/title"
        assert urls[1] == "https://reddit.com/r/test/comments/def456/other"

    def test_empty_results_returns_empty_list(self):
        """Test that empty search results return empty list."""
        search_results = {"organic": []}
        urls = SearchHelper.extract_urls_from_serper(search_results, "reddit.com")
        assert urls == []

    def test_invalid_input_returns_empty_list(self):
        """Test that invalid input returns empty list."""
        urls = SearchHelper.extract_urls_from_serper("invalid", "reddit.com")
        assert urls == []

    def test_missing_link_field_skipped(self):
        """Test that results without 'link' field are skipped."""
        search_results = {
            "organic": [
                {"link": "https://reddit.com/r/test/comments/abc123/title"},
                {"title": "No link"},  # Missing link
                {"link": "https://reddit.com/r/test/comments/def456/other"}
            ]
        }

        urls = SearchHelper.extract_urls_from_serper(search_results, "reddit.com")

        # Only 2 URLs (middle result skipped)
        assert len(urls) == 2


# ===================================================================
# Date-filtered Serper search
# ===================================================================

class TestSerperSearchWithDateFilter:
    """Tests for serper_search_with_date_filter static method."""

    def _mock_serper_response(self, mock_post, json_return=None):
        """Helper to set up a standard mock response."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = json_return or {"organic": []}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        return mock_resp

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_tbs_included_in_payload(self, mock_post):
        """tbs param must be included in the POST payload."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test query", tbs="qdr:y")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["tbs"] == "qdr:y"
        assert payload["q"] == "test query"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_tbs_day_variant(self, mock_post):
        """tbs=qdr:d for last-day results."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test", tbs="qdr:d")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["tbs"] == "qdr:d"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_tbs_month_variant(self, mock_post):
        """tbs=qdr:m for last-month results."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test", tbs="qdr:m")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["tbs"] == "qdr:m"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_response_compatible_with_extract(self, mock_post):
        """Response can be parsed by extract_results_from_serper."""
        self._mock_serper_response(mock_post, {
            "organic": [{
                "link": "https://reddit.com/r/test/comments/abc123/title",
                "title": "Fresh post",
                "snippet": "Recent discussion",
            }]
        })

        result = SearchHelper.serper_search_with_date_filter("site:reddit.com test")
        items = SearchHelper.extract_results_from_serper(result, "reddit.com")
        assert len(items) == 1
        assert items[0].title == "Fresh post"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_custom_n_results(self, mock_post):
        """n_results parameter controls num in payload."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test", n_results=5)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["num"] == 5

    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_api_key_from_environment(self, mock_post):
        """API key must be set in headers from environment."""
        self._mock_serper_response(mock_post)

        with patch.dict("os.environ", {"SERPER_API_KEY": "test-key-123"}):
            SearchHelper.serper_search_with_date_filter("test")

        headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
        assert headers["X-API-KEY"] == "test-key-123"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_empty_response(self, mock_post):
        """Empty organic results return valid dict."""
        self._mock_serper_response(mock_post)
        result = SearchHelper.serper_search_with_date_filter("test")
        assert result == {"organic": []}

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_missing_organic_key(self, mock_post):
        """Response without organic key still returns the dict."""
        self._mock_serper_response(mock_post, {"searchParameters": {"q": "test"}})
        result = SearchHelper.serper_search_with_date_filter("test")
        assert "searchParameters" in result

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_http_error_raises(self, mock_post):
        """HTTP errors (4xx, 5xx) should raise."""
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("429 Too Many Requests")
        mock_post.return_value = mock_resp

        with pytest.raises(req.exceptions.HTTPError):
            SearchHelper.serper_search_with_date_filter("test")

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_timeout_raises(self, mock_post):
        """Timeout should raise."""
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout("Connection timed out")

        with pytest.raises(req.exceptions.Timeout):
            SearchHelper.serper_search_with_date_filter("test")

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_default_tbs_is_year(self, mock_post):
        """Default tbs should be qdr:y (last year)."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test")

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["tbs"] == "qdr:y"

    @patch.dict("os.environ", {"SERPER_API_KEY": "test-key"})
    @patch("nicheiq.utils.search_helpers.requests.post")
    def test_posts_to_correct_url(self, mock_post):
        """Must POST to the Serper search endpoint."""
        self._mock_serper_response(mock_post)
        SearchHelper.serper_search_with_date_filter("test")

        url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url")
        assert url == "https://google.serper.dev/search"
