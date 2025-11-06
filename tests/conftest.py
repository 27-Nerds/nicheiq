"""
Pytest configuration and shared fixtures.
"""

import pytest
from datetime import datetime
from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult, OpportunityLevel
from nicheiq.models.social_content import RedditPost, RedditComment, TwitterTweet, TwitterThread


@pytest.fixture
def sample_pain_point():
    """Fixture providing a sample PainPoint."""
    return PainPoint(
        title="Manual data entry consuming hours daily",
        description="Users report spending 3-5 hours on repetitive manual data entry tasks",
        mention_count=25,
        severity_score=0.85,
        willingness_to_pay=0.75,
        representative_quotes=[
            "I waste 4 hours daily on data entry",
            "This manual process is killing my productivity",
            "Would pay for good automation here",
        ],
        source_platforms=["reddit", "twitter"],
        categories=["workflow inefficiency", "time waste"],
        opportunity_level=OpportunityLevel.HIGH,
    )


@pytest.fixture
def sample_reddit_post():
    """Fixture providing a sample RedditPost."""
    comment = RedditComment(
        comment_id="comment1",
        author="testuser",
        body="This is a test comment discussing the problem",
        score=10,
        created_utc=datetime.now(),
        is_submitter=False,
        replies=[],
    )

    return RedditPost(
        post_id="post123",
        title="Looking for solutions to manual data entry",
        selftext="I spend hours every day manually entering data. Any recommendations?",
        author="originaluser",
        subreddit="productivity",
        score=50,
        num_comments=15,
        created_utc=datetime.now(),
        url="https://reddit.com/r/productivity/comments/post123",
        comments=[comment],
    )


@pytest.fixture
def sample_twitter_thread():
    """Fixture providing a sample TwitterThread."""
    tweet = TwitterTweet(
        tweet_id="123456789",
        author_username="testuser",
        text="Spent 3 hours on manual data entry today. There has to be a better way! #productivity",
        likes=100,
        retweets=25,
        replies_count=10,
        created_at=datetime.now(),
        url="https://twitter.com/testuser/status/123456789",
        is_reply=False,
        parent_tweet_id=None,
    )

    return TwitterThread(
        thread_id="123456789",
        original_tweet=tweet,
        replies=[],
        total_engagement=125,
    )


@pytest.fixture
def sample_pain_point_analysis():
    """Fixture providing a sample PainPointAnalysisResult."""
    pain_points = [
        PainPoint(
            title="Manual data entry time waste",
            description="Users spend excessive time on manual entry",
            mention_count=30,
            severity_score=0.85,
            willingness_to_pay=0.75,
            representative_quotes=["Quote 1", "Quote 2"],
            source_platforms=["reddit"],
            categories=["workflow"],
            opportunity_level=OpportunityLevel.HIGH,
        ),
        PainPoint(
            title="Poor integration between tools",
            description="Tools don't talk to each other",
            mention_count=20,
            severity_score=0.70,
            willingness_to_pay=0.65,
            representative_quotes=["Quote 3"],
            source_platforms=["twitter"],
            categories=["integration"],
            opportunity_level=OpportunityLevel.MEDIUM,
        ),
    ]

    return PainPointAnalysisResult(
        pain_points=pain_points,
        total_mentions=50,
        top_categories=["workflow", "integration"],
        analysis_summary="Identified 2 key pain points with strong market signals",
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test (requires API keys)")
    config.addinivalue_line("markers", "slow: mark test as slow running")
