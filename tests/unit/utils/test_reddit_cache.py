"""Tests for RedditThreadCache."""

import json
import re
from datetime import datetime, timezone

import pytest
import requests
import responses

from nicheiq.models.social_content import RedditComment, RedditPost
from nicheiq.utils.reddit_cache import RedditThreadCache

# Backend endpoints (matched by URL suffix so the test doesn't depend on the resolved backend host).
_BATCH_LOOKUP = re.compile(r".+/reddit-threads/batch-lookup$")
_STORE = re.compile(r".+/reddit-threads$")

_FOUND_POST = {
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
    @responses.activate
    def test_all_hits(self, cache):
        responses.add(responses.POST, _BATCH_LOOKUP,
                      json={"found": {"abc123": _FOUND_POST}, "missing": []}, status=200)

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 1
        assert urls[0] in result
        assert result[urls[0]].post_id == "abc123"

    @responses.activate
    def test_all_misses(self, cache):
        responses.add(responses.POST, _BATCH_LOOKUP, json={"found": {}, "missing": ["abc123"]}, status=200)

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 0

    @responses.activate
    def test_partial_hits(self, cache):
        responses.add(responses.POST, _BATCH_LOOKUP,
                      json={"found": {"abc123": _FOUND_POST}, "missing": ["xyz789"]}, status=200)

        urls = [
            "https://www.reddit.com/r/SaaS/comments/abc123/test/",
            "https://www.reddit.com/r/SaaS/comments/xyz789/other/",
        ]
        result = cache.batch_get(urls)

        assert len(result) == 1
        assert urls[0] in result
        assert urls[1] not in result

    @responses.activate
    def test_network_error_returns_empty(self, cache):
        responses.add(responses.POST, _BATCH_LOOKUP,
                      body=requests.exceptions.ConnectionError("Connection refused"))

        urls = ["https://www.reddit.com/r/SaaS/comments/abc123/test/"]
        result = cache.batch_get(urls)

        assert len(result) == 0

    @responses.activate
    def test_5xx_returns_empty(self, cache):
        responses.add(responses.POST, _BATCH_LOOKUP, json={}, status=500)

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
    @responses.activate
    def test_store_success(self, cache):
        responses.add(responses.POST, _STORE, json={}, status=200)

        post = _make_post()
        cache.store_post(post)

        assert len(responses.calls) == 1
        payload = json.loads(responses.calls[0].request.body)
        assert payload["postId"] == "abc123"
        assert payload["subreddit"] == "SaaS"

    @responses.activate
    def test_store_network_error_no_raise(self, cache):
        responses.add(responses.POST, _STORE,
                      body=requests.exceptions.ConnectionError("Connection refused"))

        post = _make_post()
        cache.store_post(post)  # Should not raise

    @responses.activate
    def test_store_4xx_logs_error(self, cache):
        responses.add(responses.POST, _STORE, body="Bad request", status=400)

        post = _make_post()
        cache.store_post(post)  # Should not raise

    @responses.activate
    def test_store_with_comments(self, cache):
        responses.add(responses.POST, _STORE, json={}, status=200)

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

        assert len(responses.calls) == 1
        payload = json.loads(responses.calls[0].request.body)
        assert payload["comments"] is not None
        assert len(payload["comments"]) == 1
