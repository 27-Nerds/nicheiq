"""Tests for Hacker News collector tool."""

import re

import responses

from nicheiq.tools.hackernews_tool import HackerNewsCollectorTool, _VALID_STORY_ID

# Algolia endpoints matched by URL suffix (search vs. item lookup).
_SEARCH = re.compile(r".*/api/v1/search.*")
_ITEM = re.compile(r".*/api/v1/items/.+")


# Fixture: Algolia search response
SEARCH_RESPONSE = {
    "hits": [
        {
            "objectID": "12345",
            "title": "Show HN: My SaaS pricing tool",
            "url": "https://example.com/pricing",
            "points": 150,
            "num_comments": 42,
            "created_at_i": 1704067200,  # 2024-01-01
            "author": "testuser",
        },
        {
            "objectID": "12346",
            "title": "Low quality post",
            "url": "https://example.com/low",
            "points": 2,
            "num_comments": 0,
            "created_at_i": 1704067200,
            "author": "spammer",
        },
    ]
}

# Fixture: Algolia item response (story with comments)
ITEM_RESPONSE = {
    "id": 12345,
    "title": "Show HN: My SaaS pricing tool",
    "url": "https://example.com/pricing",
    "author": "testuser",
    "points": 150,
    "text": "I built a tool for SaaS pricing optimization.",
    "created_at_i": 1704067200,
    "type": "story",
    "children": [
        {
            "id": 12347,
            "author": "commenter1",
            "text": "This is really useful for indie hackers who struggle with pricing their products.",
            "type": "comment",
            "created_at_i": 1704070800,
            "children": [
                {
                    "id": 12348,
                    "author": "commenter2",
                    "text": "Agreed, pricing is one of the hardest problems for solo founders.",
                    "type": "comment",
                    "created_at_i": 1704074400,
                    "children": [],
                }
            ],
        },
        {
            "id": 12349,
            "author": "commenter3",
            "text": "How does this compare to Stripe's pricing tools?",
            "type": "comment",
            "created_at_i": 1704074400,
            "children": [],
        },
    ],
}


class TestStoryIdValidation:
    def test_valid_alphanumeric(self):
        assert _VALID_STORY_ID.match("12345")
        assert _VALID_STORY_ID.match("abc123")

    def test_rejects_path_traversal(self):
        assert not _VALID_STORY_ID.match("../etc/passwd")
        assert not _VALID_STORY_ID.match("12345/../../")

    def test_rejects_special_chars(self):
        assert not _VALID_STORY_ID.match("123;rm -rf")
        assert not _VALID_STORY_ID.match("")


class TestSearchStories:
    @responses.activate
    def test_search_returns_filtered_stories(self):
        responses.add(responses.GET, _SEARCH, json=SEARCH_RESPONSE, status=200)

        tool = HackerNewsCollectorTool()
        stories = tool.search_stories(
            queries=["saas pricing"],
            min_points=5,
            min_comments=3,
        )
        # Only the first hit should pass quality filter (150 pts, 42 comments)
        assert len(stories) == 1
        assert stories[0]["objectID"] == "12345"

    @responses.activate
    def test_search_deduplicates_across_queries(self):
        responses.add(responses.GET, _SEARCH, json=SEARCH_RESPONSE, status=200)
        responses.add(responses.GET, _SEARCH, json=SEARCH_RESPONSE, status=200)

        tool = HackerNewsCollectorTool()
        stories = tool.search_stories(
            queries=["saas pricing", "saas pricing tools"],  # same results
            min_points=5,
            min_comments=3,
        )
        assert len(stories) == 1  # deduplicated by objectID

    @responses.activate
    def test_search_handles_api_error(self):
        responses.add(responses.GET, _SEARCH, body=Exception("Connection error"))

        tool = HackerNewsCollectorTool()
        stories = tool.search_stories(queries=["test"], min_points=1, min_comments=0)
        assert stories == []  # Graceful empty result


class TestCollectPosts:
    @responses.activate
    def test_collect_returns_social_posts(self):
        responses.add(responses.GET, _ITEM, json=ITEM_RESPONSE, status=200)

        tool = HackerNewsCollectorTool()
        posts = tool.collect_posts([{"objectID": "12345"}])

        assert len(posts) == 1
        post = posts[0]
        assert post.platform == "hackernews"
        assert post.post_id == "12345"
        assert post.title == "Show HN: My SaaS pricing tool"
        assert post.score == 150
        assert post.num_responses >= 2  # at least the top-level comments
        assert len(post.responses) == 2  # 2 top-level comments
        assert post.responses[0].replies  # First comment has a nested reply
        assert post.raw_engagement["points"] == 150

    @responses.activate
    def test_collect_rejects_invalid_story_id(self):
        tool = HackerNewsCollectorTool()
        posts = tool.collect_posts([{"objectID": "../etc/passwd"}])
        assert posts == []
        assert len(responses.calls) == 0  # no HTTP call made for invalid id


class TestSearchAndCollect:
    @responses.activate
    def test_end_to_end(self):
        """Search → filter → collect in one call."""
        responses.add(responses.GET, _SEARCH, json=SEARCH_RESPONSE, status=200)
        responses.add(responses.GET, _ITEM, json=ITEM_RESPONSE, status=200)

        tool = HackerNewsCollectorTool()
        posts = tool.search_and_collect(
            queries=["saas pricing"],
            min_points=5,
            min_hn_comments=3,
        )
        assert len(posts) == 1
        assert posts[0].platform == "hackernews"
