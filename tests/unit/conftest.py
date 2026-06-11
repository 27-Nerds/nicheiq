"""
Shared fixtures for unit tests.

Provides mock objects for:
- RedditPost/TwitterThread for knowledge source tests
- Knowledge mock for QuoteSearchTool tests
- CrewAI task_output mock for guardrail tests
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from nicheiq.models.social_content import (
    RedditComment,
    RedditPost,
    TwitterThread,
    TwitterTweet,
)


@pytest.fixture
def mock_reddit_post():
    """Create a mock RedditPost with comments for knowledge source tests."""
    reply_comment = RedditComment(
        comment_id="c1_reply",
        author="replier",
        body="I totally agree, this is super frustrating for our team",
        score=25,
        created_utc=datetime.now(timezone.utc),
        is_submitter=False,
        replies=[],
    )

    comment = RedditComment(
        comment_id="c1",
        author="commenter1",
        body="I spend 3 hours every week on manual invoices and it's killing me",
        score=50,
        created_utc=datetime.now(timezone.utc),
        is_submitter=False,
        replies=[reply_comment],
    )

    return RedditPost(
        post_id="abc123",
        title="Manual invoicing is a nightmare",
        selftext="We've been doing invoices manually for years and it's a huge time sink. "
                 "Looking for automation solutions that actually work with our existing tools.",
        author="testuser",
        subreddit="smallbusiness",
        score=100,
        num_comments=15,
        created_utc=datetime.now(timezone.utc),
        url="https://reddit.com/r/smallbusiness/comments/abc123",
        comments=[comment],
    )


@pytest.fixture
def mock_reddit_post_minimal():
    """Create a minimal RedditPost without comments."""
    return RedditPost(
        post_id="minimal123",
        title="Short test post",
        selftext="This is minimal content for testing chunking behavior.",
        author="minuser",
        subreddit="test",
        score=10,
        num_comments=0,
        created_utc=datetime.now(timezone.utc),
        url="https://reddit.com/r/test/comments/minimal123",
        comments=[],
    )


@pytest.fixture
def mock_twitter_thread():
    """Create a mock TwitterThread with replies for knowledge source tests."""
    original_tweet = TwitterTweet(
        tweet_id="t1",
        author_username="testuser",
        text="We spend way too much time on expense reports. There has to be a better way! "
             "Anyone have recommendations for automation tools?",
        likes=100,
        retweets=50,
        replies_count=10,
        created_at=datetime.now(timezone.utc),
        url="https://twitter.com/testuser/status/t1",
        is_reply=False,
        parent_tweet_id=None,
    )

    reply = TwitterTweet(
        tweet_id="t2",
        author_username="replier",
        text="Same here! Manual expense tracking is the worst part of my job",
        likes=25,
        retweets=5,
        replies_count=2,
        created_at=datetime.now(timezone.utc),
        url="https://twitter.com/replier/status/t2",
        is_reply=True,
        parent_tweet_id="t1",
    )

    return TwitterThread(
        thread_id="thread_xyz",
        original_tweet=original_tweet,
        replies=[reply],
        total_engagement=180,
    )


@pytest.fixture
def mock_twitter_thread_minimal():
    """Create a minimal TwitterThread without replies."""
    original_tweet = TwitterTweet(
        tweet_id="t_min",
        author_username="minuser",
        text="This is a minimal tweet for testing chunking.",
        likes=10,
        retweets=2,
        replies_count=0,
        created_at=datetime.now(timezone.utc),
        url="https://twitter.com/minuser/status/t_min",
        is_reply=False,
        parent_tweet_id=None,
    )

    return TwitterThread(
        thread_id="thread_min",
        original_tweet=original_tweet,
        replies=[],
        total_engagement=12,
    )


@pytest.fixture
def mock_knowledge():
    """Create a mock Knowledge instance for QuoteSearchTool tests."""
    knowledge = MagicMock()
    knowledge.query.return_value = [
        {
            "content": "I spend 3 hours every week on invoices",
            "metadata": {"post_id": "abc123", "source_type": "reddit", "subreddit": "smallbusiness"},
            "score": 0.92,
        },
        {
            "content": "Manual expense tracking is the worst part of my job",
            "metadata": {"post_id": "thread_xyz", "source_type": "twitter", "author": "replier"},
            "score": 0.87,
        },
    ]
    return knowledge


@pytest.fixture
def mock_knowledge_no_results():
    """Create a mock Knowledge instance that returns no results."""
    knowledge = MagicMock()
    knowledge.query.return_value = []
    return knowledge


@pytest.fixture
def mock_knowledge_error():
    """Create a mock Knowledge instance that raises an exception."""
    knowledge = MagicMock()
    knowledge.query.side_effect = Exception("Vector search failed")
    return knowledge


@pytest.fixture
def mock_task_output_valid_categorization():
    """Create a mock CrewAI task output for content categorization."""
    output = MagicMock()
    output.pydantic = None  # CrewAI 1.7.0 behavior with guardrails
    output.raw = '''{
        "executive_summary": "Analysis of small business discussions revealed 5 major themes.",
        "theme_categories": [
            {
                "category_name": "Invoicing Pain",
                "definition": "Frustrations with manual invoicing processes",
                "frequency": "High",
                "mention_count": 25,
                "primary_user_segments": ["Small Business Owners", "Freelancers"],
                "anchor_keywords": ["manual invoicing", "invoice automation", "billing nightmare", "time on invoices"]
            },
            {
                "category_name": "Expense Tracking",
                "definition": "Difficulties tracking business expenses",
                "frequency": "Medium",
                "mention_count": 15,
                "primary_user_segments": ["Remote Workers", "Contractors"],
                "anchor_keywords": ["expense reports", "receipt tracking", "expense management"]
            },
            {
                "category_name": "Tax Preparation",
                "definition": "Challenges with tax documentation",
                "frequency": "Medium",
                "mention_count": 12,
                "primary_user_segments": ["Solo Founders", "Freelancers"],
                "anchor_keywords": ["tax prep nightmare", "quarterly taxes", "tax documentation"]
            },
            {
                "category_name": "Cash Flow",
                "definition": "Issues with cash flow management",
                "frequency": "High",
                "mention_count": 20,
                "primary_user_segments": ["Small Business Owners"],
                "anchor_keywords": ["cash flow problems", "late payments", "payment tracking"]
            }
        ],
        "user_segments": [
            {"segment_name": "Small Business Owners", "primary_concerns": ["Invoicing", "Cash Flow"], "mention_frequency": "High"},
            {"segment_name": "Freelancers", "primary_concerns": ["Invoicing", "Tax Prep"], "mention_frequency": "Medium"},
            {"segment_name": "Remote Workers", "primary_concerns": ["Expense Tracking"], "mention_frequency": "Medium"}
        ],
        "overall_quality": "High",
        "overall_quality_justification": "Rich discussion data with clear themes"
    }'''
    return output


