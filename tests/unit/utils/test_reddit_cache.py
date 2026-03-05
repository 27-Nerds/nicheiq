"""Tests for RedditThreadCache."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from nicheiq.models.social_content import RedditComment, RedditPost
from nicheiq.utils.reddit_cache import RedditThreadCache


@pytest.fixture
def cache():
    return RedditThreadCache()


class TestExtractPostId:
    def test_standard_url(self, cache):
        url = "https://www.reddit.com/r/SaaS/comments/abc123/my_post_title/"
        assert cache._extract_post_id(url) == "abc123"

    def test_old_reddit_url(self, cache):
        url = "https://old.reddit.com/r/startups/comments/xyz789/some_title/"
        assert cache._extract_post_id(url) == "xyz789"

    def test_short_url(self, cache):
        url = "https://www.reddit.com/r/test/comments/a1b2c3/"
        assert cache._extract_post_id(url) == "a1b2c3"

    def test_invalid_url_no_comments(self, cache):
        url = "https://www.reddit.com/r/SaaS/"
        assert cache._extract_post_id(url) is None

    def test_invalid_url_not_reddit(self, cache):
        url = "https://example.com/something"
        assert cache._extract_post_id(url) is None

    def test_url_with_query_params(self, cache):
        url = "https://www.reddit.com/r/SaaS/comments/abc123/title/?sort=top"
        assert cache._extract_post_id(url) == "abc123"


def _make_post(post_id: str = "abc123", score: int = 50, num_comments: int = 10) -> RedditPost:
    return RedditPost(
        post_id=post_id,
        title="Test post",
        selftext="Test body",
        author="testuser",
        subreddit="SaaS",
        score=score,
        num_comments=num_comments,
        created_utc=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
        url=f"https://www.reddit.com/r/SaaS/comments/{post_id}/test/",
        comments=[],
    )


class TestBatchGet:
    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_all_hits(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "found": {
                "abc123": {
                    "postId": "abc123",
                    "url": "https://www.reddit.com/r/SaaS/comments/abc123/test/",
                    "title": "Test",
                    "selftext": "Body",
                    "author": "user",
                    "subreddit": "SaaS",
                    "score": 50,
                    "numComments": 10,
                    "comments": None,
                    "redditCreatedAt": "2025-01-15T10:00:00+00:00",
                }
            },
            "missing": [],
        }
        mock_post.return_value = mock_resp

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 1
        assert urls[0] in result
        assert result[urls[0]].post_id == "abc123"

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_all_misses(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"found": {}, "missing": ["abc123"]}
        mock_post.return_value = mock_resp

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 0

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_partial_hits(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "found": {
                "abc123": {
                    "postId": "abc123",
                    "url": "https://www.reddit.com/r/SaaS/comments/abc123/test/",
                    "title": "Test",
                    "selftext": "Body",
                    "author": "user",
                    "subreddit": "SaaS",
                    "score": 50,
                    "numComments": 10,
                    "comments": None,
                    "redditCreatedAt": "2025-01-15T10:00:00+00:00",
                }
            },
            "missing": ["xyz789"],
        }
        mock_post.return_value = mock_resp

        urls = [
            "https://www.reddit.com/r/SaaS/comments/abc123/test/",
            "https://www.reddit.com/r/SaaS/comments/xyz789/other/",
        ]
        result = cache.batch_get(urls)

        assert len(result) == 1
        assert urls[0] in result
        assert urls[1] not in result

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_network_error_returns_empty(self, mock_post, cache):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("Connection refused")

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 0

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_5xx_returns_empty(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 0

    def test_empty_urls(self, cache):
        result = cache.batch_get([])
        assert len(result) == 0

    def test_invalid_urls_no_post_ids(self, cache):
        result = cache.batch_get(["https://example.com"])
        assert len(result) == 0


class TestStorePost:
    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_store_success(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        post = _make_post()
        cache.store_post(post)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["postId"] == "abc123"
        assert payload["subreddit"] == "SaaS"

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_store_network_error_no_raise(self, mock_post, cache):
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("Connection refused")

        post = _make_post()
        # Should not raise
        cache.store_post(post)

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_store_4xx_logs_error(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        mock_post.return_value = mock_resp

        post = _make_post()
        # Should not raise
        cache.store_post(post)

    @patch("nicheiq.utils.reddit_cache.requests.post")
    def test_store_with_comments(self, mock_post, cache):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        post = _make_post()
        post = RedditPost(
            post_id="abc123",
            title="Test",
            selftext="Body",
            author="user",
            subreddit="SaaS",
            score=50,
            num_comments=1,
            created_utc=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            url="https://www.reddit.com/r/SaaS/comments/abc123/test/",
            comments=[
                RedditComment(
                    comment_id="c1",
                    author="commenter",
                    body="This is a substantial test comment with enough length.",
                    score=5,
                    created_utc=datetime(2025, 1, 15, 11, 0, tzinfo=timezone.utc),
                    is_submitter=False,
                    replies=[],
                )
            ],
        )
        cache.store_post(post)

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["comments"] is not None
        assert len(payload["comments"]) == 1
