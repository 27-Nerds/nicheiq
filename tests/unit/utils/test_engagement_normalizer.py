"""Tests for per-source engagement normalization."""

import pytest
from datetime import datetime
from nicheiq.utils.engagement_normalizer import normalize_engagement
from nicheiq.models.social_content import SocialPost


def _make_post(
    platform: str = "hackernews",
    score: int = 100,
    num_responses: int = 20,
    raw_engagement: dict | None = None,
) -> SocialPost:
    return SocialPost(
        post_id="test_1",
        platform=platform,
        title="Test",
        body="Test body",
        author="user",
        url="https://example.com",
        score=score,
        num_responses=num_responses,
        created_utc=datetime(2025, 1, 1),
        raw_engagement=raw_engagement or {},
    )


class TestNormalizeEngagement:
    def test_hn_returns_0_to_1(self):
        post = _make_post(platform="hackernews", score=500, num_responses=100)
        result = normalize_engagement(post)
        assert 0.0 <= result <= 1.0

    def test_hn_higher_score_means_higher_engagement(self):
        low = _make_post(platform="hackernews", score=5, num_responses=2)
        high = _make_post(platform="hackernews", score=500, num_responses=100)
        assert normalize_engagement(high) > normalize_engagement(low)

    def test_reddit_with_raw_engagement(self):
        post = _make_post(
            platform="reddit",
            score=200,
            num_responses=50,
            raw_engagement={"upvotes": 200, "num_comments": 50, "upvote_ratio": 0.95},
        )
        result = normalize_engagement(post)
        assert 0.0 <= result <= 1.0

    def test_youtube_with_raw_engagement(self):
        post = _make_post(
            platform="youtube",
            score=0,
            raw_engagement={"views": 50000, "likes": 1200, "comments": 80},
        )
        result = normalize_engagement(post)
        assert 0.0 <= result <= 1.0
        assert result > 0.0

    def test_zero_values_no_crash(self):
        post = _make_post(platform="hackernews", score=0, num_responses=0)
        result = normalize_engagement(post)
        assert result == 0.0

    def test_unknown_platform_fallback(self):
        post = _make_post(platform="indiehackers", score=50, num_responses=10)
        result = normalize_engagement(post)
        assert 0.0 <= result <= 1.0
        assert result > 0.0

    def test_reddit_fallback_to_model_fields(self):
        # No raw_engagement keys — should fall back to .score and .num_responses
        post = _make_post(platform="reddit", score=100, num_responses=30)
        result = normalize_engagement(post)
        assert result > 0.0
