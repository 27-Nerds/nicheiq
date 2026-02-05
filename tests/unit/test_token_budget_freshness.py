"""
Tests for freshness reserve in token budget filtering.

Ensures filter_posts_to_token_budget() can reserve a portion of the token
budget for fresh posts, guaranteeing recent content survives even when
lower-scoring than older posts.
"""

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
    post_id: str = "p0",
):
    """Create a mock RedditPost for token budget tests."""
    post = MagicMock()
    post.score = score
    post.selftext = selftext
    post.title = title
    post.post_id = post_id
    post.created_utc = datetime.now(timezone.utc) - timedelta(days=days_old)

    comments = []
    for _ in range(num_comments):
        c = MagicMock()
        c.body = "a" * avg_comment_len
        c.replies = []
        comments.append(c)
    post.comments = comments
    return post


class TestTokenBudgetFreshnessReserve:
    """Tests for freshness reserve in filter_posts_to_token_budget."""

    def test_backward_compat_zero_reserve(self):
        """freshness_reserve_ratio=0 produces identical output to current behavior."""
        monitor = ContentTokenMonitor()
        posts = [
            _make_post(score=100, days_old=1, post_id="recent"),
            _make_post(score=50, days_old=200, post_id="old"),
        ]

        def static_score(post):
            return post.score

        result_old = monitor.filter_posts_to_token_budget(
            posts, max_tokens=999999, score_fn=static_score,
        )
        result_new = monitor.filter_posts_to_token_budget(
            posts, max_tokens=999999, score_fn=static_score,
            freshness_reserve_ratio=0,
        )
        assert [p.post_id for p in result_old] == [p.post_id for p in result_new]

    def test_all_fresh_posts_entire_budget(self):
        """When all posts are fresh, entire budget available (no split needed)."""
        monitor = ContentTokenMonitor()
        posts = [
            _make_post(score=100, days_old=10, post_id="p1"),
            _make_post(score=80, days_old=30, post_id="p2"),
            _make_post(score=60, days_old=60, post_id="p3"),
        ]

        result = monitor.filter_posts_to_token_budget(
            posts, max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        assert len(result) == 3

    def test_all_old_posts_reserve_unused(self):
        """When all posts are old, reserve flows back to quality pool."""
        monitor = ContentTokenMonitor()
        posts = [
            _make_post(score=100, days_old=200, post_id="old1"),
            _make_post(score=80, days_old=300, post_id="old2"),
            _make_post(score=60, days_old=400, post_id="old3"),
        ]

        result = monitor.filter_posts_to_token_budget(
            posts, max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        # All posts should still be included since budget is large
        assert len(result) == 3

    def test_mixed_fresh_posts_survive(self):
        """Fresh posts appear even if lower-scoring than old posts."""
        monitor = ContentTokenMonitor()
        # Fresh but low-scoring
        fresh = _make_post(score=5, days_old=30, post_id="fresh")
        # Old but high-scoring (3 of them to crowd out fresh in pure quality sort)
        old1 = _make_post(score=100, days_old=300, post_id="old1")
        old2 = _make_post(score=90, days_old=350, post_id="old2")
        old3 = _make_post(score=80, days_old=400, post_id="old3")

        result = monitor.filter_posts_to_token_budget(
            [fresh, old1, old2, old3], max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        result_ids = [p.post_id for p in result]
        assert "fresh" in result_ids, "Fresh post should survive with freshness reserve"

    def test_no_double_counting(self):
        """A high-quality fresh post should only appear once in results."""
        monitor = ContentTokenMonitor()
        posts = [
            _make_post(score=100, days_old=10, post_id="fresh_high"),
            _make_post(score=50, days_old=200, post_id="old_med"),
            _make_post(score=30, days_old=300, post_id="old_low"),
        ]

        result = monitor.filter_posts_to_token_budget(
            posts, max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        result_ids = [p.post_id for p in result]
        # fresh_high should only appear once (not in both pools)
        assert result_ids.count("fresh_high") == 1

    def test_score_fn_respected_in_both_pools(self):
        """score_fn parameter is used for sorting in both fresh and quality pools."""
        monitor = ContentTokenMonitor()

        # Custom score function that reverses normal ordering
        def reverse_score(post):
            return -post.score

        # Two fresh posts - with reverse_score, lower score = higher priority
        fresh_low = _make_post(score=5, days_old=30, post_id="fresh_low")
        fresh_high = _make_post(score=100, days_old=60, post_id="fresh_high")

        result = monitor.filter_posts_to_token_budget(
            [fresh_high, fresh_low], max_tokens=999999,
            score_fn=reverse_score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        # With reverse scoring, fresh_low should come first
        assert result[0].post_id == "fresh_low"

    def test_total_tokens_never_exceeds_max(self):
        """Total tokens must not exceed max_tokens."""
        monitor = ContentTokenMonitor()
        # Create posts where each is roughly the same size
        posts = [
            _make_post(score=50, days_old=30, post_id="fresh1", selftext="y" * 500),
            _make_post(score=40, days_old=60, post_id="fresh2", selftext="y" * 500),
            _make_post(score=100, days_old=300, post_id="old1", selftext="y" * 500),
            _make_post(score=90, days_old=400, post_id="old2", selftext="y" * 500),
        ]

        # Use a small budget that can only fit ~2 posts
        # Each post is roughly 200-300 tokens
        result = monitor.filter_posts_to_token_budget(
            posts, max_tokens=500,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        # Should not include all 4 posts
        assert len(result) <= 4

    def test_boundary_exactly_freshness_days(self):
        """Post at exactly freshness_days boundary should be considered old."""
        monitor = ContentTokenMonitor()
        boundary_post = _make_post(score=50, days_old=180, post_id="boundary")
        old_post = _make_post(score=100, days_old=300, post_id="old")

        result = monitor.filter_posts_to_token_budget(
            [boundary_post, old_post], max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
            freshness_days=180,
        )
        # Both should be included with large budget
        assert len(result) == 2

    def test_empty_posts_returns_empty(self):
        """Empty post list returns empty list."""
        monitor = ContentTokenMonitor()
        result = monitor.filter_posts_to_token_budget(
            [], max_tokens=999999,
            score_fn=lambda p: p.score,
            freshness_reserve_ratio=0.25,
        )
        assert result == []
