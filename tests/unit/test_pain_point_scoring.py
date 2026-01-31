"""Tests for pain_point_priority_score in ContentTokenMonitor."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from nicheiq.utils.token_monitor import ContentTokenMonitor


def _make_post(
    score: int = 10,
    num_comments: int = 5,
    selftext: str = "x" * 200,
    days_old: int = 30,
    avg_comment_len: int = 100,
    title: str = "Test post title",
):
    """Create a mock RedditPost for scoring tests."""
    post = MagicMock()
    post.score = score
    post.selftext = selftext
    post.title = title
    post.created_utc = datetime.now(timezone.utc) - timedelta(days=days_old)

    # Build comments with specified average length
    comments = []
    for _ in range(num_comments):
        c = MagicMock()
        c.body = "a" * avg_comment_len
        c.replies = []
        comments.append(c)
    post.comments = comments
    return post


class TestPainPointPriorityScore:
    """Tests for the pain_point_priority_score static method."""

    def test_rich_discussion_beats_shallow_viral(self):
        """Post with rich discussion should beat a viral link-post with few comments."""
        rich = _make_post(score=45, num_comments=120, selftext="x" * 500, days_old=300, avg_comment_len=150)
        shallow = _make_post(score=500, num_comments=8, selftext="x" * 30, days_old=5, avg_comment_len=40)

        rich_score = ContentTokenMonitor.pain_point_priority_score(rich)
        shallow_score = ContentTokenMonitor.pain_point_priority_score(shallow)

        assert rich_score > shallow_score, (
            f"Rich discussion post ({rich_score:.2f}) should beat shallow viral post ({shallow_score:.2f})"
        )

    def test_old_rich_beats_new_shallow(self):
        """Older post with extensive discussion should beat a new post with little content."""
        old_rich = _make_post(score=100, num_comments=80, selftext="x" * 1000, days_old=365, avg_comment_len=200)
        new_shallow = _make_post(score=20, num_comments=3, selftext="x" * 50, days_old=2, avg_comment_len=30)

        old_score = ContentTokenMonitor.pain_point_priority_score(old_rich)
        new_score = ContentTokenMonitor.pain_point_priority_score(new_shallow)

        assert old_score > new_score, (
            f"Old rich post ({old_score:.2f}) should beat new shallow post ({new_score:.2f})"
        )

    def test_more_comments_increases_score(self):
        """More comments (same quality) should increase score monotonically."""
        scores = []
        for n_comments in [5, 20, 50, 100]:
            post = _make_post(score=50, num_comments=n_comments, selftext="x" * 300, days_old=30, avg_comment_len=120)
            scores.append(ContentTokenMonitor.pain_point_priority_score(post))

        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Score should increase with comment count: {scores}"
            )

    def test_higher_upvotes_increases_score(self):
        """Higher upvotes should increase score monotonically."""
        scores = []
        for upvotes in [5, 50, 200, 1000]:
            post = _make_post(score=upvotes, num_comments=20, selftext="x" * 300, days_old=30, avg_comment_len=100)
            scores.append(ContentTokenMonitor.pain_point_priority_score(post))

        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Score should increase with upvotes: {scores}"
            )

    def test_longer_selftext_increases_score(self):
        """Longer selftext should increase score monotonically."""
        scores = []
        for length in [0, 100, 500, 2000]:
            post = _make_post(score=50, num_comments=20, selftext="x" * length, days_old=30, avg_comment_len=100)
            scores.append(ContentTokenMonitor.pain_point_priority_score(post))

        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Score should increase with selftext length: {scores}"
            )

    def test_gentle_recency_decay(self):
        """365-day-old post should retain significant score vs 1-day-old post."""
        recent = _make_post(score=50, num_comments=20, selftext="x" * 300, days_old=1, avg_comment_len=100)
        old = _make_post(score=50, num_comments=20, selftext="x" * 300, days_old=365, avg_comment_len=100)

        recent_score = ContentTokenMonitor.pain_point_priority_score(recent)
        old_score = ContentTokenMonitor.pain_point_priority_score(old)

        # Old post should still have a substantial portion of recent post's score
        # Recency is only 15% of the score, so the ratio should be high
        ratio = old_score / recent_score
        assert ratio > 0.75, (
            f"365-day post should retain >75% of 1-day post score (got {ratio:.2%})"
        )

    def test_zero_comments_does_not_crash(self):
        """Post with zero comments should not raise an error."""
        post = _make_post(score=10, num_comments=0, selftext="x" * 100, days_old=7)
        score = ContentTokenMonitor.pain_point_priority_score(post)
        assert score >= 0

    def test_empty_selftext_does_not_crash(self):
        """Post with empty selftext should not raise an error."""
        post = _make_post(score=10, num_comments=5, selftext="", days_old=7)
        score = ContentTokenMonitor.pain_point_priority_score(post)
        assert score >= 0

    def test_score_is_positive(self):
        """Score should always be positive for any valid post."""
        post = _make_post(score=0, num_comments=0, selftext="", days_old=1)
        score = ContentTokenMonitor.pain_point_priority_score(post)
        assert score >= 0


class TestEngagementRecencyScoreBackwardCompat:
    """Ensure the original engagement_recency_score still works unchanged."""

    def test_basic_calculation(self):
        """Verify the formula: score / days_old."""
        post = _make_post(score=100, days_old=10)
        result = ContentTokenMonitor.engagement_recency_score(post)
        assert result == pytest.approx(10.0, abs=0.1)

    def test_minimum_one_day(self):
        """Posts less than 1 day old should use 1 as minimum."""
        post = _make_post(score=50, days_old=0)
        result = ContentTokenMonitor.engagement_recency_score(post)
        assert result == pytest.approx(50.0, abs=0.1)


class TestFilterPostsToTokenBudgetScoreFn:
    """Test that filter_posts_to_token_budget respects the score_fn parameter."""

    def test_default_uses_engagement_recency(self):
        """When no score_fn is provided, should use engagement_recency_score."""
        monitor = ContentTokenMonitor()
        # Two posts: one recent high-score, one old low-score
        recent = _make_post(score=100, days_old=1)
        old = _make_post(score=10, days_old=100)

        # With a very large budget, both posts should be returned, recent first
        result = monitor.filter_posts_to_token_budget([old, recent], max_tokens=999999)
        # Recent post has higher engagement_recency_score (100/1 vs 10/100)
        assert len(result) == 2

    def test_custom_score_fn(self):
        """When a custom score_fn is provided, it should be used for sorting."""
        monitor = ContentTokenMonitor()
        post_a = _make_post(score=100, days_old=1)
        post_b = _make_post(score=10, days_old=100)

        # Custom score: always return the score directly (no recency)
        def static_score(post):
            return post.score

        result = monitor.filter_posts_to_token_budget(
            [post_b, post_a], max_tokens=999999, score_fn=static_score
        )
        assert len(result) == 2
        # post_a (score=100) should come first
        assert result[0].score == 100
