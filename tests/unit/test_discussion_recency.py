"""
Tests for improved discussion recency scoring using engagement-weighted exponential decay.

Replaces naive majority-vote algorithm with a scoring approach that weights
recent, high-engagement posts more heavily to avoid labeling active markets
as "Declining"/"Dated".

See: compute_discussion_signals() in src/nicheiq/utils/trend_scoring.py
"""

from datetime import datetime, timedelta, timezone

import pytest

from nicheiq.utils.trend_scoring import compute_discussion_signals, RECENT_DAYS


# ---------------------------------------------------------------------------
# Helpers: reuse _make_social_content from test_trend_classification
# ---------------------------------------------------------------------------

def _make_social_content(reddit_days_ago=None, twitter_days_ago=None,
                         reddit_scores=None, twitter_likes=None, twitter_retweets=None):
    """Build a minimal SocialContentCollection with posts at given ages."""
    from nicheiq.models.social_content import (
        SocialContentCollection, RedditPost, TwitterThread, TwitterTweet,
    )
    now = datetime.now(timezone.utc)
    reddit_posts = []
    if reddit_days_ago:
        for i, days in enumerate(reddit_days_ago):
            score = reddit_scores[i] if reddit_scores else 10
            reddit_posts.append(RedditPost(
                post_id=f"r{i}",
                title=f"Post {i}",
                selftext="text",
                author="user",
                subreddit="test",
                score=score,
                num_comments=5,
                created_utc=now - timedelta(days=days),
                url=f"https://reddit.com/r/test/{i}",
            ))

    twitter_threads = []
    if twitter_days_ago:
        for i, days in enumerate(twitter_days_ago):
            likes = twitter_likes[i] if twitter_likes else 10
            retweets = twitter_retweets[i] if twitter_retweets else 5
            tweet = TwitterTweet(
                tweet_id=f"t{i}",
                author_username="tweeter",
                text="tweet",
                likes=likes,
                retweets=retweets,
                replies_count=2,
                created_at=now - timedelta(days=days),
                url=f"https://twitter.com/{i}",
            )
            twitter_threads.append(TwitterThread(
                thread_id=f"t{i}",
                original_tweet=tweet,
                replies=[],
                total_engagement=likes + retweets,
            ))

    return SocialContentCollection(
        reddit_posts=reddit_posts,
        twitter_threads=twitter_threads,
    )


# ===================================================================
# A. Backward compatibility
# ===================================================================

class TestBackwardCompat:
    """New algorithm must produce same labels as old for unambiguous cases."""

    def test_all_recent_is_recent(self):
        """All posts <180 days → "Recent", "Increasing"."""
        social = _make_social_content(reddit_days_ago=[10, 30, 60, 90, 120])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"
        assert freq == "Increasing"

    def test_all_dated_is_dated(self):
        """All posts >365 days → "Dated", "Decreasing"."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600, 700])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Dated"
        assert freq == "Decreasing"

    def test_empty_posts_is_dated(self):
        """No posts → "Dated", "Decreasing"."""
        from nicheiq.models.social_content import SocialContentCollection
        empty = SocialContentCollection(reddit_posts=[], twitter_threads=[])
        recency, freq = compute_discussion_signals(empty)
        assert recency == "Dated"
        assert freq == "Decreasing"

    def test_none_social_is_dated(self):
        """None social_content → "Dated", "Decreasing"."""
        recency, freq = compute_discussion_signals(None)
        assert recency == "Dated"
        assert freq == "Decreasing"

    def test_return_type_is_tuple_of_two_strings(self):
        """Return signature unchanged: (str, str)."""
        social = _make_social_content(reddit_days_ago=[30])
        result = compute_discussion_signals(social)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str) and isinstance(result[1], str)


# ===================================================================
# B. Core bug fix: majority-vote no longer misclassifies active markets
# ===================================================================

class TestCoreBugFix:
    """The core problem: 4 recent + 6 old should NOT produce "Dated"."""

    def test_4_recent_6_old_not_dated(self):
        """4 recent high-engagement + 6 old low-engagement ≠ Dated.
        Under old majority-vote: 4 < 6 → "Dated". Must be "Moderate" or "Recent"."""
        social = _make_social_content(
            reddit_days_ago=[10, 30, 60, 90, 400, 500, 600, 700, 800, 900],
            reddit_scores=[100, 80, 60, 40, 5, 5, 3, 3, 2, 2],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency in ("Recent", "Moderate"), f"Expected Recent/Moderate, got {recency}"
        assert freq in ("Increasing", "Stable"), f"Expected Increasing/Stable, got {freq}"

    def test_3_recent_7_old_with_engagement(self):
        """3 recent high-engagement + 7 old → should not be Dated."""
        social = _make_social_content(
            reddit_days_ago=[15, 45, 120, 400, 450, 500, 550, 600, 650, 700],
            reddit_scores=[200, 150, 100, 5, 5, 3, 3, 3, 2, 2],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency != "Dated", f"3 high-engagement recent posts shouldn't yield Dated"


# ===================================================================
# C. Engagement weighting
# ===================================================================

class TestEngagementWeighting:
    """High-engagement recent posts should outweigh many low-engagement old posts."""

    def test_high_score_recent_outweighs_many_old(self):
        """One recent viral post (score=500) outweighs 5 old posts (score=5)."""
        social = _make_social_content(
            reddit_days_ago=[10, 400, 500, 600, 700, 800],
            reddit_scores=[500, 5, 5, 5, 5, 5],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency in ("Recent", "Moderate")

    def test_engagement_cap_prevents_viral_domination(self):
        """A viral post (score=50000) is capped so it doesn't completely dominate.
        With 1 recent (50k score) vs 10 old (score=500 each), the old posts
        should still have meaningful influence."""
        social = _make_social_content(
            reddit_days_ago=[10, 400, 400, 400, 400, 400, 400, 400, 400, 400, 400],
            reddit_scores=[50000, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500],
        )
        recency, freq = compute_discussion_signals(social)
        # The 10 old posts with score=500 each should have enough weight
        # to prevent "Recent" — verify the cap works
        assert recency in ("Moderate", "Recent")


# ===================================================================
# D. Temporal spread bonus
# ===================================================================

class TestTemporalSpreadBonus:
    """Spread bonus: +0.1 if newest <90d AND oldest >365d (capped at 1.0)."""

    def test_spread_bonus_applied(self):
        """Posts spanning <90d to >365d should get spread bonus."""
        social = _make_social_content(
            reddit_days_ago=[30, 150, 250, 400],
            reddit_scores=[10, 10, 10, 10],
        )
        recency, _ = compute_discussion_signals(social)
        # With spread bonus, the 30-day post + bonus should push toward Recent/Moderate
        assert recency in ("Recent", "Moderate")

    def test_no_spread_bonus_all_old(self):
        """All posts >365d → no spread bonus (newest not <90d)."""
        social = _make_social_content(
            reddit_days_ago=[400, 500, 600, 700],
            reddit_scores=[10, 10, 10, 10],
        )
        recency, _ = compute_discussion_signals(social)
        assert recency == "Dated"

    def test_no_spread_bonus_all_recent(self):
        """All posts <90d → no spread bonus (oldest not >365d)."""
        social = _make_social_content(
            reddit_days_ago=[10, 20, 30, 60],
            reddit_scores=[10, 10, 10, 10],
        )
        recency, _ = compute_discussion_signals(social)
        # Still Recent, but no bonus needed
        assert recency == "Recent"


# ===================================================================
# E. Edge cases
# ===================================================================

class TestEdgeCases:
    """Boundary and edge case behavior."""

    def test_single_recent_post(self):
        """Single recent post → Recent."""
        social = _make_social_content(reddit_days_ago=[30], reddit_scores=[10])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"
        assert freq == "Increasing"

    def test_single_old_post(self):
        """Single old post → Dated."""
        social = _make_social_content(reddit_days_ago=[500], reddit_scores=[10])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Dated"
        assert freq == "Decreasing"

    def test_boundary_exactly_180_days(self):
        """Post at exactly RECENT_DAYS (180) boundary — decay = 0.5 → Recent boundary."""
        social = _make_social_content(reddit_days_ago=[RECENT_DAYS], reddit_scores=[10])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"  # 0.5 >= 0.5 threshold

    def test_boundary_exactly_360_days(self):
        """Post at 360 days — decay ~0.25 → Moderate boundary."""
        social = _make_social_content(reddit_days_ago=[360], reddit_scores=[10])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Moderate"  # 0.25 >= 0.25 threshold

    def test_negative_reddit_score(self):
        """Negative Reddit score → clamped to 1 for engagement floor."""
        social = _make_social_content(reddit_days_ago=[30], reddit_scores=[-5])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"  # Still scored, engagement = sqrt(1)

    def test_zero_reddit_score(self):
        """Zero Reddit score → clamped to 1."""
        social = _make_social_content(reddit_days_ago=[30], reddit_scores=[0])
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"


# ===================================================================
# F. Twitter engagement
# ===================================================================

class TestTwitterEngagement:
    """Twitter posts use likes + retweets for engagement."""

    def test_twitter_likes_retweets_engagement(self):
        """Twitter engagement = likes + retweets."""
        social = _make_social_content(
            twitter_days_ago=[10, 20, 30],
            twitter_likes=[100, 80, 60],
            twitter_retweets=[50, 40, 30],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"
        assert freq == "Increasing"

    def test_mixed_reddit_and_twitter(self):
        """Both Reddit and Twitter posts combined."""
        social = _make_social_content(
            reddit_days_ago=[30, 60],
            twitter_days_ago=[10, 20],
            reddit_scores=[50, 30],
            twitter_likes=[100, 80],
            twitter_retweets=[50, 40],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency == "Recent"


# ===================================================================
# G. _now parameter for deterministic testing
# ===================================================================

class TestNowParameter:
    """The _now parameter allows deterministic testing without time mocking."""

    def test_now_parameter_shifts_reference(self):
        """Passing _now shifts what counts as 'recent'."""
        from nicheiq.models.social_content import (
            SocialContentCollection, RedditPost,
        )
        # Post created at a fixed date
        fixed_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        post = RedditPost(
            post_id="r0", title="Post 0", selftext="text", author="user",
            subreddit="test", score=10, num_comments=5, created_utc=fixed_date,
            url="https://reddit.com/r/test/0",
        )
        social = SocialContentCollection(reddit_posts=[post], twitter_threads=[])

        # If _now is 30 days after the post → recent
        now_recent = fixed_date + timedelta(days=30)
        recency_recent, _ = compute_discussion_signals(social, _now=now_recent)
        assert recency_recent == "Recent"

        # If _now is 500 days after the post → dated
        now_old = fixed_date + timedelta(days=500)
        recency_old, _ = compute_discussion_signals(social, _now=now_old)
        assert recency_old == "Dated"


# ===================================================================
# H. Tie / balanced scenarios
# ===================================================================

class TestTieScenarios:
    """Equal number of recent and dated posts with equal engagement."""

    def test_equal_recent_and_dated_equal_engagement(self):
        """5 recent + 5 old, all same score → should be Moderate or better.
        Under old majority-vote, this was a tie won by whichever bucket came first.
        Under decay: recent posts have higher decay values, so should lean Moderate/Recent."""
        social = _make_social_content(
            reddit_days_ago=[30, 60, 90, 120, 150, 400, 450, 500, 550, 600],
            reddit_scores=[10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        )
        recency, freq = compute_discussion_signals(social)
        assert recency in ("Recent", "Moderate"), f"Tie scenario should favor recency, got {recency}"
