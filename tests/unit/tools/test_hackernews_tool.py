"""Tests for Hacker News collector tool."""

import re
from datetime import datetime, timezone

import responses

from nicheiq.models.social_content import SocialPost
from nicheiq.tools.hackernews_tool import _VALID_STORY_ID, HackerNewsCollectorTool

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
    def test_end_to_end(self, monkeypatch):
        """Search → filter → collect in one call."""
        responses.add(responses.GET, _SEARCH, json=SEARCH_RESPONSE, status=200)
        responses.add(responses.GET, _ITEM, json=ITEM_RESPONSE, status=200)
        monkeypatch.setattr(
            "nicheiq.utils.validation.thread_validator.ThreadRelevanceValidator.validate_batch_parallel",
            lambda _self, *, search_results, **_kwargs: [(search_results[0], 3)],
        )

        tool = HackerNewsCollectorTool()
        posts = tool.search_and_collect(
            queries=["saas pricing"],
            niche_description="SaaS pricing tools for indie hackers",
            min_points=5,
            min_hn_comments=3,
        )
        assert len(posts) == 1
        assert posts[0].platform == "hackernews"


class TestStrictSemanticGate:
    GAZA_COLLISION = {
        "objectID": "42716440",
        "title": "Israel, Hamas reach ceasefire deal to end 15 months of war in Gaza",
        "url": "https://www.reuters.com/world/middle-east/gaza-ceasefire/",
        "points": 463,
        "num_comments": 438,
        "created_at_i": 1736972809,
    }
    RELEVANT_STORY = {
        "objectID": "50000001",
        "title": "Ask HN: How do freelance bookkeepers manage month-end close?",
        "url": "https://news.ycombinator.com/item?id=50000001",
        "points": 80,
        "num_comments": 35,
        "created_at_i": 1736972809,
    }
    NICHE = "Freelance bookkeepers managing month-end close across multiple clients"

    def test_exact_gaza_title_is_a_lexical_candidate_but_semantic_gate_drops_it(
        self, monkeypatch
    ):
        tool = HackerNewsCollectorTool()
        monkeypatch.setattr(
            tool,
            "_search_algolia",
            lambda *_args, **_kwargs: [self.GAZA_COLLISION, self.RELEVANT_STORY],
        )

        candidates = tool.search_stories(
            queries=["month end close"],
            niche_description=self.NICHE,
            min_points=1,
            min_comments=1,
        )
        assert [story["objectID"] for story in candidates] == ["42716440", "50000001"]

        monkeypatch.setattr(
            HackerNewsCollectorTool,
            "search_stories",
            lambda _self, **_kwargs: candidates,
        )

        def validate(_self, *, search_results, **_kwargs):
            assert _kwargs["fail_open"] is False
            return [(search_results[0], 0), (search_results[1], 3)]

        monkeypatch.setattr(
            "nicheiq.utils.validation.thread_validator.ThreadRelevanceValidator.validate_batch_parallel",
            validate,
        )

        fetched: list[str] = []

        def fetch(_self, story_id, story_meta=None, relevance_grade=None):
            fetched.append(story_id)
            return SocialPost(
                post_id=story_id,
                platform="hackernews",
                title=story_meta["title"],
                body="Month-end close workflow details.",
                author="bookkeeper",
                url=story_meta["url"],
                score=story_meta["points"],
                num_responses=story_meta["num_comments"],
                created_utc=datetime.now(timezone.utc),
                relevance_grade=relevance_grade,
            )

        monkeypatch.setattr(HackerNewsCollectorTool, "_fetch_story", fetch)

        result = tool.search_relevant_and_collect(
            queries=["month end close"],
            niche_description=self.NICHE,
            min_points=1,
            min_hn_comments=1,
        )

        assert result.candidate_count == 2
        assert result.relevant_count == 1
        assert fetched == ["50000001"]
        assert [post.post_id for post in result.posts] == ["50000001"]
        assert result.posts[0].relevance_grade == 3

    def test_validator_failure_fails_closed_before_comment_fetch(self, monkeypatch):
        tool = HackerNewsCollectorTool()
        monkeypatch.setattr(
            HackerNewsCollectorTool,
            "search_stories",
            lambda _self, **_kwargs: [self.RELEVANT_STORY],
        )

        def fail(_self, **_kwargs):
            raise RuntimeError("validator unavailable")

        monkeypatch.setattr(
            "nicheiq.utils.validation.thread_validator.ThreadRelevanceValidator.validate_batch_parallel",
            fail,
        )
        fetched = []
        monkeypatch.setattr(
            HackerNewsCollectorTool,
            "_fetch_story",
            lambda *args, **kwargs: fetched.append((args, kwargs)),
        )

        result = tool.search_relevant_and_collect(
            queries=["month end close"],
            niche_description=self.NICHE,
        )

        assert result.candidate_count == 1
        assert result.relevant_count == 0
        assert result.posts == []
        assert fetched == []
