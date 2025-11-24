"""
Comprehensive unit tests for SocialContentValidator.

Tests cover:
1. Quality tier classification (EXCELLENT, GOOD, MINIMAL, INSUFFICIENT)
2. Metrics calculation (sources, interactions, engagement)
3. Edge cases and boundary conditions
4. Error handling for invalid inputs
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from nicheiq.utils.validation import SocialContentValidator
from nicheiq.models.social_content import (
    SocialContentCollection,
    RedditPost,
    RedditComment,
    TwitterThread,
    TwitterTweet
)


class TestSocialContentValidatorInit:
    """Test SocialContentValidator initialization."""

    def test_init_creates_validator(self):
        """Should successfully create validator instance."""
        validator = SocialContentValidator()
        assert validator is not None


class TestQualityTierClassification:
    """Test quality tier classification logic."""

    def test_excellent_tier_with_rich_dataset(self):
        """Should classify rich dataset as EXCELLENT."""
        validator = SocialContentValidator()

        # Create 40 Reddit posts with comments
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext=f"Content {i}",
                author=f"user{i}",
                subreddit="test",
                score=10 + i,
                num_comments=5,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author=f"commenter{j}",
                        body=f"Comment {j}",
                        score=2,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(3)
                ]
            )
            for i in range(40)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "EXCELLENT"
        assert metrics["reddit_posts"] == 40
        assert metrics["total_sources"] == 40
        assert metrics["total_interactions"] == 120  # 40 posts * 3 comments each
        assert metrics["total_engagement"] > 0

    def test_good_tier_with_adequate_dataset(self):
        """Should classify adequate dataset as GOOD."""
        validator = SocialContentValidator()

        # Create 20 Reddit posts with comments (adequate but not rich)
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext="Content",
                author="user",
                subreddit="test",
                score=5,
                num_comments=3,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(3)
                ]
            )
            for i in range(20)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "GOOD"
        assert metrics["total_sources"] == 20
        assert metrics["total_interactions"] == 60

    def test_minimal_tier_with_minimum_dataset(self):
        """Should classify minimal dataset as MINIMAL."""
        validator = SocialContentValidator()

        # Create exactly 10 posts with minimal comments (meets threshold)
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext="Content",
                author="user",
                subreddit="test",
                score=3,
                num_comments=3,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(3)
                ]
            )
            for i in range(10)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "MINIMAL"
        assert metrics["total_sources"] == 10
        assert metrics["total_interactions"] == 30

    def test_insufficient_tier_with_too_few_sources(self):
        """Should classify dataset with <5 sources as INSUFFICIENT."""
        validator = SocialContentValidator()

        # Only 3 posts (below minimum of 5)
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext="Content",
                author="user",
                subreddit="test",
                score=5,
                num_comments=10,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(10)
                ]
            )
            for i in range(3)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["total_sources"] == 3

    def test_insufficient_tier_with_too_few_interactions(self):
        """Should classify dataset with <20 interactions as INSUFFICIENT."""
        validator = SocialContentValidator()

        # 10 posts but only 1 comment each (total 10 interactions < 20)
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext="Content",
                author="user",
                subreddit="test",
                score=5,
                num_comments=1,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                ]
            )
            for i in range(10)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["total_sources"] == 10
        assert metrics["total_interactions"] == 10

    def test_insufficient_tier_with_zero_engagement(self):
        """Should classify dataset with 0 engagement as INSUFFICIENT."""
        validator = SocialContentValidator()

        # Posts with 0 score (no engagement)
        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title=f"Test post {i}",
                selftext="Content",
                author="user",
                subreddit="test",
                score=0,  # No engagement
                num_comments=5,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(5)
                ]
            )
            for i in range(10)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["total_engagement"] == 0
        assert metrics["avg_engagement_per_source"] == 0


class TestMetricsCalculation:
    """Test metrics calculation accuracy."""

    def test_calculates_reddit_metrics_correctly(self):
        """Should accurately calculate Reddit metrics."""
        validator = SocialContentValidator()

        reddit_posts = [
            RedditPost(
                post_id="post1",
                title="Test post",
                selftext="Content",
                author="user",
                subreddit="test",
                score=15,
                num_comments=3,
                created_utc=datetime.now(),
                url="https://reddit.com/r/test/post1",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for i in range(3)
                ]
            )
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert metrics["reddit_posts"] == 1
        assert metrics["twitter_threads"] == 0
        assert metrics["total_sources"] == 1
        assert metrics["total_interactions"] == 3
        assert metrics["total_engagement"] == 15
        assert metrics["avg_engagement_per_source"] == 15.0

    def test_calculates_twitter_metrics_correctly(self):
        """Should accurately calculate Twitter metrics."""
        validator = SocialContentValidator()

        twitter_threads = [
            TwitterThread(
                thread_id="123",
                original_tweet=TwitterTweet(
                    tweet_id="123",
                    author_username="user",
                    text="Test tweet",
                    likes=10,
                    retweets=5,
                    replies_count=3,
                    created_at=datetime.now(),
                    url="https://twitter.com/user/status/123",
                    is_reply=False,
                    parent_tweet_id=None
                ),
                replies=[
                    TwitterTweet(
                        tweet_id=f"reply{i}",
                        author_username=f"replier{i}",
                        text="Reply",
                        likes=2,
                        retweets=0,
                        replies_count=0,
                        created_at=datetime.now(),
                        url=f"https://twitter.com/replier{i}/status/reply{i}",
                        is_reply=True,
                        parent_tweet_id="123"
                    )
                    for i in range(3)
                ],
                total_engagement=15  # 10 likes + 5 retweets
            )
        ]

        social_content = SocialContentCollection(
            reddit_posts=[],
            twitter_threads=twitter_threads
        )

        tier, metrics = validator.validate_quality(social_content)

        assert metrics["reddit_posts"] == 0
        assert metrics["twitter_threads"] == 1
        assert metrics["total_sources"] == 1
        assert metrics["total_interactions"] == 3
        assert metrics["total_engagement"] == 15

    def test_calculates_cross_platform_metrics(self):
        """Should accurately calculate metrics across both platforms."""
        validator = SocialContentValidator()

        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title="Test",
                selftext="Content",
                author="user",
                subreddit="test",
                score=10,
                num_comments=2,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(2)
                ]
            )
            for i in range(10)
        ]

        twitter_threads = [
            TwitterThread(
                thread_id=f"thread{i}",
                original_tweet=TwitterTweet(
                    tweet_id=f"tweet{i}",
                    author_username="user",
                    text="Tweet",
                    likes=5,
                    retweets=2,
                    replies_count=2,
                    created_at=datetime.now(),
                    url=f"https://twitter.com/user/status/tweet{i}",
                    is_reply=False,
                    parent_tweet_id=None
                ),
                replies=[
                    TwitterTweet(
                        tweet_id=f"reply{i}_{j}",
                        author_username="replier",
                        text="Reply",
                        likes=1,
                        retweets=0,
                        replies_count=0,
                        created_at=datetime.now(),
                        url=f"https://twitter.com/replier/status/reply{i}_{j}",
                        is_reply=True,
                        parent_tweet_id=f"tweet{i}"
                    )
                    for j in range(2)
                ],
                total_engagement=7
            )
            for i in range(10)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=twitter_threads
        )

        tier, metrics = validator.validate_quality(social_content)

        assert metrics["reddit_posts"] == 10
        assert metrics["twitter_threads"] == 10
        assert metrics["total_sources"] == 20
        assert metrics["total_interactions"] == 40  # 10*2 + 10*2
        assert metrics["total_engagement"] == 170  # 10*10 + 10*7


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_handles_empty_social_content(self):
        """Should handle empty social content collection."""
        validator = SocialContentValidator()

        social_content = SocialContentCollection(
            reddit_posts=[],
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["total_sources"] == 0
        assert metrics["total_interactions"] == 0
        assert metrics["total_engagement"] == 0
        assert metrics["avg_engagement_per_source"] == 0

    def test_handles_empty_reddit_posts(self):
        """Should handle empty reddit_posts field."""
        validator = SocialContentValidator()

        social_content = SocialContentCollection(
            reddit_posts=[],
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["reddit_posts"] == 0

    def test_handles_empty_twitter_threads(self):
        """Should handle empty twitter_threads field."""
        validator = SocialContentValidator()

        social_content = SocialContentCollection(
            reddit_posts=[],
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == "INSUFFICIENT"
        assert metrics["twitter_threads"] == 0

    def test_handles_invalid_input_type(self):
        """Should handle invalid input type gracefully."""
        validator = SocialContentValidator()

        tier, metrics = validator.validate_quality("invalid")

        assert tier == "INSUFFICIENT"
        assert metrics == {}

    def test_handles_posts_without_comments(self):
        """Should handle posts with empty comments list."""
        validator = SocialContentValidator()

        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title="Test",
                selftext="Content",
                author="user",
                subreddit="test",
                score=5,
                num_comments=0,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[]
            )
            for i in range(25)  # Enough sources but no interactions
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        # Should be INSUFFICIENT due to <20 total interactions
        assert tier == "INSUFFICIENT"
        assert metrics["total_interactions"] == 0


class TestBoundaryConditions:
    """Test boundary conditions for tier thresholds."""

    @pytest.mark.parametrize("source_count,expected_tier", [
        (4, "INSUFFICIENT"),  # Below minimum
        (5, "MINIMAL"),       # At minimum (with enough interactions)
        (14, "MINIMAL"),      # Just below GOOD threshold
        (15, "GOOD"),         # At GOOD threshold
        (29, "GOOD"),         # Just below EXCELLENT threshold
        (30, "EXCELLENT"),    # At EXCELLENT threshold
    ])
    def test_source_count_boundaries(self, source_count, expected_tier):
        """Should correctly classify based on source count boundaries."""
        validator = SocialContentValidator()

        reddit_posts = [
            RedditPost(
                post_id=f"post{i}",
                title="Test",
                selftext="Content",
                author="user",
                subreddit="test",
                score=5,
                num_comments=10,
                created_utc=datetime.now(),
                url=f"https://reddit.com/r/test/post{i}",
                comments=[
                    RedditComment(
                        comment_id=f"comment{i}_{j}",
                        author="commenter",
                        body="Comment",
                        score=1,
                        created_utc=datetime.now(),
                        is_submitter=False,
                        replies=[]
                    )
                    for j in range(10)  # Enough interactions to not trigger that threshold
                ]
            )
            for i in range(source_count)
        ]

        social_content = SocialContentCollection(
            reddit_posts=reddit_posts,
            twitter_threads=[]
        )

        tier, metrics = validator.validate_quality(social_content)

        assert tier == expected_tier
        assert metrics["total_sources"] == source_count
