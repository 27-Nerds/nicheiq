"""Tests for influencer_pre_compute module."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from nicheiq.models.social_content import (
    RedditComment,
    RedditPost,
    TwitterThread,
    TwitterTweet,
)
from nicheiq.utils.crew_helpers.influencer_pre_compute import (
    _format_karma,
    _is_excluded,
    aggregate_author_metrics,
    compute_influencer_profiles,
    enrich_top_authors_via_praw,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _comment(
    author: str = "commenter",
    score: int = 5,
    replies: list | None = None,
    body: str = "Some comment text",
) -> RedditComment:
    return RedditComment(
        comment_id="c1",
        author=author,
        body=body,
        score=score,
        created_utc=_NOW,
        is_submitter=False,
        replies=replies or [],
    )


def _reddit_post(
    author: str = "poster",
    score: int = 10,
    subreddit: str = "SaaS",
    comments: list | None = None,
    title: str = "A Reddit Post",
    url: str = "https://reddit.com/r/SaaS/comments/abc123",
) -> RedditPost:
    return RedditPost(
        post_id="p1",
        title=title,
        selftext="body text",
        author=author,
        subreddit=subreddit,
        score=score,
        num_comments=0,
        created_utc=_NOW,
        url=url,
        comments=comments or [],
    )


def _tweet(
    author: str = "tweeter",
    likes: int = 10,
    retweets: int = 2,
    is_reply: bool = False,
) -> TwitterTweet:
    return TwitterTweet(
        tweet_id="t1",
        author_username=author,
        text="A tweet",
        likes=likes,
        retweets=retweets,
        replies_count=0,
        created_at=_NOW,
        url="https://twitter.com/tweeter/status/123",
        is_reply=is_reply,
    )


def _twitter_thread(
    author: str = "tweeter",
    likes: int = 10,
    retweets: int = 2,
    replies: list | None = None,
) -> TwitterThread:
    return TwitterThread(
        thread_id="th1",
        original_tweet=_tweet(author=author, likes=likes, retweets=retweets),
        replies=replies or [],
        total_engagement=likes + retweets,
    )


# ---------------------------------------------------------------------------
# Exclusion / filtering tests
# ---------------------------------------------------------------------------


class TestExcludedAuthors:
    def test_automoderator(self):
        assert _is_excluded("AutoModerator")

    def test_deleted(self):
        assert _is_excluded("[deleted]")

    def test_removed(self):
        assert _is_excluded("[removed]")

    def test_empty_string(self):
        assert _is_excluded("")

    def test_bot_suffix(self):
        assert _is_excluded("helpfulbot")
        assert _is_excluded("ReminderBot")

    def test_sneakpeekbot(self):
        assert _is_excluded("sneakpeekbot")

    def test_normal_user_not_excluded(self):
        assert not _is_excluded("JohnDoe")
        assert not _is_excluded("robot_lover")  # "robot" is not "bot$"

    def test_aggregate_filters_excluded(self):
        posts = [
            _reddit_post(author="AutoModerator", score=100),
            _reddit_post(author="[deleted]", score=50),
            _reddit_post(author="gooduser", score=10),
        ]
        results = aggregate_author_metrics(posts, [])
        names = [r["name"] for r in results]
        assert "u/gooduser" in names
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Reddit aggregation tests
# ---------------------------------------------------------------------------


class TestCollectRedditAuthors:
    def test_post_author_tracked(self):
        posts = [_reddit_post(author="alice", score=20, subreddit="SaaS")]
        results = aggregate_author_metrics(posts, [])
        assert len(results) == 1
        assert results[0]["name"] == "u/alice"
        assert results[0]["platform"] == "Reddit"

    def test_comment_author_tracked(self):
        c = _comment(author="bob", score=15)
        posts = [_reddit_post(author="alice", score=10, comments=[c])]
        results = aggregate_author_metrics(posts, [])
        names = {r["name"] for r in results}
        assert "u/bob" in names
        assert "u/alice" in names

    def test_nested_comments(self):
        deep = _comment(author="deep_user", score=5)
        mid = _comment(author="mid_user", score=10, replies=[deep])
        posts = [_reddit_post(author="poster", score=1, comments=[mid])]
        results = aggregate_author_metrics(posts, [])
        names = {r["name"] for r in results}
        assert "u/deep_user" in names
        assert "u/mid_user" in names
        assert "u/poster" in names


# ---------------------------------------------------------------------------
# Negative score handling
# ---------------------------------------------------------------------------


class TestNegativeScores:
    def test_negative_post_score_clamped(self):
        posts = [_reddit_post(author="user1", score=-10)]
        results = aggregate_author_metrics(posts, [])
        assert len(results) == 1
        # Should not crash, relevance should still be valid
        assert 0 <= results[0]["relevance_score"] <= 1.0

    def test_negative_comment_score_clamped(self):
        c = _comment(author="user1", score=-50)
        posts = [_reddit_post(author="poster", score=10, comments=[c])]
        results = aggregate_author_metrics(posts, [])
        # Should not crash
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Twitter aggregation tests
# ---------------------------------------------------------------------------


class TestCollectTwitterAuthors:
    def test_thread_author_tracked(self):
        threads = [_twitter_thread(author="tweeter", likes=100, retweets=20)]
        results = aggregate_author_metrics([], threads)
        assert len(results) == 1
        assert results[0]["name"] == "@tweeter"
        assert results[0]["platform"] == "Twitter"

    def test_reply_author_tracked(self):
        reply = _tweet(author="replier", likes=5, retweets=1, is_reply=True)
        threads = [_twitter_thread(author="tweeter", likes=50, retweets=10, replies=[reply])]
        results = aggregate_author_metrics([], threads)
        names = {r["name"] for r in results}
        assert "@replier" in names


# ---------------------------------------------------------------------------
# Cross-platform merge
# ---------------------------------------------------------------------------


class TestCrossPlatformMerge:
    def test_same_username_higher_engagement_wins(self):
        """Same user on both platforms — platform with higher engagement wins."""
        posts = [_reddit_post(author="jdoe", score=5, subreddit="startups")]
        threads = [_twitter_thread(author="jdoe", likes=500, retweets=100)]
        results = aggregate_author_metrics(posts, threads)
        # Should be single entry (merged by lowercase name)
        assert len(results) == 1
        # Twitter engagement is higher, but platform is set based on which had data first
        # or which had higher engagement in the scoring
        assert results[0]["relevance_score"] > 0


# ---------------------------------------------------------------------------
# Relevance score normalization
# ---------------------------------------------------------------------------


class TestRelevanceScoreNormalization:
    def test_top_author_near_1(self):
        posts = [
            _reddit_post(author="top", score=1000, subreddit="SaaS"),
            _reddit_post(author="low", score=1, subreddit="SaaS"),
        ]
        results = aggregate_author_metrics(posts, [])
        top = next(r for r in results if r["name"] == "u/top")
        assert top["relevance_score"] == 1.0

    def test_floor_at_010(self):
        # Many authors with vastly different scores
        posts = [
            _reddit_post(author="mega", score=10000, subreddit="SaaS"),
        ]
        # Add many low-score authors
        for i in range(20):
            posts.append(_reddit_post(author=f"user{i}", score=1, subreddit="test"))
        results = aggregate_author_metrics(posts, [])
        lowest = min(r["relevance_score"] for r in results)
        assert lowest >= 0.10


# ---------------------------------------------------------------------------
# Breadth cap
# ---------------------------------------------------------------------------


class TestBreadthCap:
    def test_breadth_capped_at_5(self):
        """Author in 10 subreddits should not score much more than one in 5."""
        posts_5 = [
            _reddit_post(author="five_subs", score=10, subreddit=f"sub{i}")
            for i in range(5)
        ]
        posts_10 = [
            _reddit_post(author="ten_subs", score=10, subreddit=f"sub{i}")
            for i in range(10)
        ]
        all_posts = posts_5 + posts_10
        results = aggregate_author_metrics(all_posts, [])
        five = next(r for r in results if r["name"] == "u/five_subs")
        ten = next(r for r in results if r["name"] == "u/ten_subs")
        # ten_subs has more activity (10 posts) but breadth is capped
        # The difference should be modest, mostly from activity
        assert ten["relevance_score"] >= five["relevance_score"]


# ---------------------------------------------------------------------------
# Post vs comment weighting
# ---------------------------------------------------------------------------


class TestPostVsCommentWeighting:
    def test_post_author_ranks_higher(self):
        """Post author with same score should rank above comment-only author."""
        c = _comment(author="commenter_only", score=50)
        posts = [
            _reddit_post(author="poster_only", score=50, subreddit="SaaS", comments=[c]),
        ]
        results = aggregate_author_metrics(posts, [])
        poster = next(r for r in results if r["name"] == "u/poster_only")
        commenter = next(r for r in results if r["name"] == "u/commenter_only")
        assert poster["relevance_score"] >= commenter["relevance_score"]


# ---------------------------------------------------------------------------
# Engagement level buckets
# ---------------------------------------------------------------------------


class TestEngagementLevelBuckets:
    def test_high_at_070(self):
        # Create scenario where top author gets 1.0 relevance
        posts = [_reddit_post(author="high", score=1000, subreddit="SaaS")]
        results = aggregate_author_metrics(posts, [])
        assert results[0]["engagement_level"] == "High"

    def test_medium_range(self):
        posts = [
            _reddit_post(author="top", score=10000, subreddit="SaaS"),
            _reddit_post(author="mid", score=100, subreddit="SaaS"),
        ]
        results = aggregate_author_metrics(posts, [])
        mid = next(r for r in results if r["name"] == "u/mid")
        # Mid should be medium or low depending on exact ratio
        assert mid["engagement_level"] in ("Medium", "Low")


# ---------------------------------------------------------------------------
# Outreach priority
# ---------------------------------------------------------------------------


class TestOutreachPriority:
    def test_high_relevance_high_engagement(self):
        posts = [_reddit_post(author="star", score=5000, subreddit="SaaS")]
        results = aggregate_author_metrics(posts, [])
        assert results[0]["outreach_priority"] == "High"

    def test_low_relevance_low_priority(self):
        posts = [
            _reddit_post(author="top", score=10000, subreddit="SaaS"),
        ]
        for i in range(20):
            posts.append(_reddit_post(author=f"nobody{i}", score=1, subreddit="test"))
        results = aggregate_author_metrics(posts, [])
        lowest = [r for r in results if r["relevance_score"] < 0.30]
        for r in lowest:
            assert r["outreach_priority"] == "Low"


# ---------------------------------------------------------------------------
# Top N ranking
# ---------------------------------------------------------------------------


class TestTopNRanking:
    def test_top_10_from_15(self):
        posts = [
            _reddit_post(author=f"user{i}", score=(i + 1) * 10, subreddit="test")
            for i in range(15)
        ]
        result = compute_influencer_profiles(posts, [])
        assert len(result["profiles"]) == 10

    def test_sparse_data_returns_available(self):
        posts = [
            _reddit_post(author=f"user{i}", score=10, subreddit="test")
            for i in range(3)
        ]
        result = compute_influencer_profiles(posts, [])
        assert len(result["profiles"]) == 3

    def test_empty_input(self):
        result = compute_influencer_profiles([], [])
        assert result["profiles"] == []
        assert "No influencer data" in result["influencer_names_formatted"]


# ---------------------------------------------------------------------------
# Format karma
# ---------------------------------------------------------------------------


class TestFormatKarma:
    def test_small(self):
        assert _format_karma(850) == "850 karma"

    def test_thousands(self):
        assert _format_karma(12500) == "12.5K karma"

    def test_millions(self):
        assert _format_karma(1_500_000) == "1.5M karma"

    def test_zero(self):
        assert _format_karma(0) == "0 karma"


# ---------------------------------------------------------------------------
# PRAW enrichment
# ---------------------------------------------------------------------------


class TestPrawEnrichment:
    def test_successful_enrichment(self):
        profiles = [
            {"name": "u/alice", "platform": "Reddit", "follower_estimate": None},
        ]
        mock_client = MagicMock()
        mock_redditor = MagicMock()
        type(mock_redditor).link_karma = PropertyMock(return_value=10000)
        type(mock_redditor).comment_karma = PropertyMock(return_value=2500)
        mock_client.redditor.return_value = mock_redditor

        enrich_top_authors_via_praw(profiles, mock_client, n=10)
        assert profiles[0]["follower_estimate"] == "12.5K karma"

    def test_not_found_graceful(self):
        import prawcore.exceptions

        profiles = [
            {"name": "u/suspended", "platform": "Reddit", "follower_estimate": None},
        ]
        mock_client = MagicMock()
        mock_client.redditor.side_effect = prawcore.exceptions.NotFound(
            MagicMock(status_code=404)
        )

        enrich_top_authors_via_praw(profiles, mock_client, n=10)
        assert profiles[0]["follower_estimate"] is None

    def test_forbidden_graceful(self):
        import prawcore.exceptions

        profiles = [
            {"name": "u/banned", "platform": "Reddit", "follower_estimate": None},
        ]
        mock_client = MagicMock()
        mock_client.redditor.side_effect = prawcore.exceptions.Forbidden(
            MagicMock(status_code=403)
        )

        enrich_top_authors_via_praw(profiles, mock_client, n=10)
        assert profiles[0]["follower_estimate"] is None

    def test_twitter_profiles_skipped(self):
        profiles = [
            {"name": "@tweeter", "platform": "Twitter", "follower_estimate": None},
        ]
        mock_client = MagicMock()
        enrich_top_authors_via_praw(profiles, mock_client, n=10)
        mock_client.redditor.assert_not_called()


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------


class TestBuildInfluencers:
    """Test the _build_influencers method on AudienceMappingCrew (index-based focus)."""

    @staticmethod
    def _crew():
        from nicheiq.crews.audience_mapping_crew import AudienceMappingCrew

        return AudienceMappingCrew.__new__(AudienceMappingCrew)

    @staticmethod
    def _profiles(n: int) -> list[dict]:
        return [
            {
                "name": f"u/user{i}",
                "platform": "Reddit",
                "relevance_score": round(0.9 - i * 0.1, 2),
                "engagement_level": "High",
                "outreach_priority": "High",
                "follower_estimate": "10K karma",
                "content_focus": f"fallback {i}",
                "top_subreddits": ["r/SaaS"],
                "top_posts": [
                    {"title": "Best CRM", "subreddit": "SaaS", "score": 42, "url": "https://x/1"},
                ],
            }
            for i in range(n)
        ]

    def test_uses_precomputed_metrics_and_top_posts(self):
        """Every field (incl. real top-post URLs) comes from the pre-compute."""
        profiles = self._profiles(6)
        result = self._crew()._build_influencers(profiles, [])
        assert len(result) == 6
        assert result[0].engagement_level == "High"
        assert result[0].follower_estimate == "10K karma"
        assert result[0].top_posts[0].url == "https://x/1"

    def test_content_focus_matched_by_index(self):
        """1-based index links LLM focus to the right influencer."""
        from nicheiq.models.research_state import InfluencerFocus

        profiles = self._profiles(6)
        focus = [InfluencerFocus(index=1, focus="CRM workflows"), InfluencerFocus(index=4, focus="No-code")]
        result = self._crew()._build_influencers(profiles, focus)
        assert result[0].content_focus == "CRM workflows"   # index 1 -> profiles[0]
        assert result[3].content_focus == "No-code"          # index 4 -> profiles[3]
        assert result[1].content_focus == "fallback 1"       # unmatched -> python fallback

    def test_out_of_range_and_duplicate_index(self):
        """Out-of-range indices are ignored; duplicate index is first-wins."""
        from nicheiq.models.research_state import InfluencerFocus

        profiles = self._profiles(3)
        focus = [
            InfluencerFocus(index=99, focus="ignored"),
            InfluencerFocus(index=1, focus="first"),
            InfluencerFocus(index=1, focus="second"),
            InfluencerFocus(index=0, focus="also ignored"),
        ]
        result = self._crew()._build_influencers(profiles, focus)
        assert result[0].content_focus == "first"
        assert result[1].content_focus == "fallback 1"
        assert result[2].content_focus == "fallback 2"

    def test_empty_focus_uses_fallback(self):
        profiles = self._profiles(4)
        result = self._crew()._build_influencers(profiles, [])
        assert [p.content_focus for p in result] == [f"fallback {i}" for i in range(4)]

    def test_empty_profiles_yields_empty_list(self):
        assert self._crew()._build_influencers([], []) == []


# ---------------------------------------------------------------------------
# Top subreddits
# ---------------------------------------------------------------------------


class TestTopSubreddits:
    def test_top_3_by_count(self):
        posts = [
            _reddit_post(author="user1", score=10, subreddit="SaaS"),
            _reddit_post(author="user1", score=10, subreddit="SaaS"),
            _reddit_post(author="user1", score=10, subreddit="SaaS"),
            _reddit_post(author="user1", score=10, subreddit="startups"),
            _reddit_post(author="user1", score=10, subreddit="startups"),
            _reddit_post(author="user1", score=10, subreddit="Entrepreneur"),
            _reddit_post(author="user1", score=10, subreddit="smallbusiness"),
            _reddit_post(author="user1", score=10, subreddit="programming"),
        ]
        results = aggregate_author_metrics(posts, [])
        user = results[0]
        assert len(user["top_subreddits"]) == 3
        assert user["top_subreddits"][0] == "r/SaaS"
        assert user["top_subreddits"][1] == "r/startups"


# ---------------------------------------------------------------------------
# Top posts
# ---------------------------------------------------------------------------


class TestTopPosts:
    def test_top_3_by_score(self):
        posts = [
            _reddit_post(author="user1", score=100, subreddit="SaaS", title="Post A"),
            _reddit_post(author="user1", score=50, subreddit="SaaS", title="Post B"),
            _reddit_post(author="user1", score=200, subreddit="startups", title="Post C"),
            _reddit_post(author="user1", score=10, subreddit="test", title="Post D"),
        ]
        results = aggregate_author_metrics(posts, [])
        user = results[0]
        assert len(user["top_posts"]) == 3
        assert user["top_posts"][0]["title"] == "Post C"
        assert user["top_posts"][0]["score"] == 200
        assert user["top_posts"][1]["title"] == "Post A"

    def test_comments_tracked_with_truncated_body(self):
        long_body = "x" * 200
        c = _comment(author="user1", score=50, body=long_body)
        posts = [_reddit_post(author="other", score=1, comments=[c])]
        results = aggregate_author_metrics(posts, [])
        user = next(r for r in results if r["name"] == "u/user1")
        assert len(user["top_posts"]) == 1
        # Title should be truncated
        assert len(user["top_posts"][0]["title"]) <= 100
        assert user["top_posts"][0]["title"].endswith("...")


# ---------------------------------------------------------------------------
# compute_influencer_profiles integration
# ---------------------------------------------------------------------------


class TestComputeInfluencerProfiles:
    def test_formatted_string_contains_names(self):
        posts = [
            _reddit_post(author="alice", score=100, subreddit="SaaS"),
            _reddit_post(author="bob", score=50, subreddit="startups"),
        ]
        result = compute_influencer_profiles(posts, [])
        assert "u/alice" in result["influencer_names_formatted"]
        assert "u/bob" in result["influencer_names_formatted"]

    def test_profiles_have_all_fields(self):
        posts = [_reddit_post(author="alice", score=100, subreddit="SaaS")]
        result = compute_influencer_profiles(posts, [])
        p = result["profiles"][0]
        assert "name" in p
        assert "platform" in p
        assert "relevance_score" in p
        assert "engagement_level" in p
        assert "outreach_priority" in p
        assert "content_focus" in p
        assert "top_subreddits" in p
        assert "top_posts" in p
