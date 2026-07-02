"""
Pydantic models for social media content (Stages 4-5).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RedditComment(BaseModel):
    """Represents a single Reddit comment."""

    model_config = ConfigDict(extra='forbid')

    comment_id: str = Field(..., description="Reddit comment ID")
    author: str = Field(..., description="Comment author username")
    body: str = Field(..., description="Comment text")
    score: int = Field(..., description="Comment score (upvotes - downvotes)")
    created_utc: datetime = Field(..., description="Comment creation timestamp")
    is_submitter: bool = Field(default=False, description="Whether author is post submitter")
    replies: list["RedditComment"] = Field(
        default_factory=list, description="Nested reply comments"
    )

class RedditPost(BaseModel):
    """Represents a Reddit post with comments."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "post_id": "abc123",
                "title": "Struggling to find good freelancers",
                "selftext": "I've been searching for weeks...",
                "author": "user123",
                "subreddit": "freelance",
                "score": 45,
                "num_comments": 12,
                "created_utc": "2025-01-15T10:30:00",
                "url": "https://reddit.com/r/freelance/comments/abc123",
                "comments": [],
            }
        }
    )

    post_id: str = Field(..., description="Reddit post ID")
    title: str = Field(..., description="Post title")
    selftext: str = Field(..., description="Post body text")
    author: str = Field(..., description="Post author username")
    subreddit: str = Field(..., description="Subreddit name")
    score: int = Field(..., description="Post score (upvotes - downvotes)")
    num_comments: int = Field(..., description="Number of comments")
    created_utc: datetime = Field(..., description="Post creation timestamp")
    url: str = Field(..., description="Post URL")
    comments: list[RedditComment] = Field(
        default_factory=list, description="Top-level comments"
    )
    relevance_grade: int | None = Field(
        default=None, ge=0, le=3,
        description="TREC/UMBRELA 0-3 niche-relevance from thread validation; used to "
        "prioritize the most-relevant posts when capping to the pain-finder token budget",
    )
    subreddit_subscribers: int | None = Field(
        default=None,
        description="Subscriber count of the post's subreddit at collection time; posts from "
        "small dedicated communities get a waived engagement gate (None = unknown, full bars)",
    )

class TwitterTweet(BaseModel):
    """Represents a single tweet."""

    model_config = ConfigDict(extra='forbid')

    tweet_id: str = Field(..., description="Twitter tweet ID")
    author_username: str = Field(..., description="Tweet author username")
    text: str = Field(..., description="Tweet text")
    likes: int = Field(..., description="Number of likes")
    retweets: int = Field(..., description="Number of retweets")
    replies_count: int = Field(..., description="Number of replies")
    created_at: datetime = Field(..., description="Tweet creation timestamp")
    url: str = Field(..., description="Tweet URL")
    is_reply: bool = Field(default=False, description="Whether this is a reply tweet")
    parent_tweet_id: Optional[str] = Field(
        default=None, description="Parent tweet ID if this is a reply"
    )

class TwitterThread(BaseModel):
    """Represents a Twitter thread (original tweet + replies)."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "thread_id": "xyz789",
                "original_tweet": {},
                "replies": [],
                "total_engagement": 150,
            }
        }
    )

    thread_id: str = Field(..., description="Thread identifier (original tweet ID)")
    original_tweet: TwitterTweet = Field(..., description="Original tweet starting the thread")
    replies: list[TwitterTweet] = Field(default_factory=list, description="Reply tweets")
    total_engagement: int = Field(..., description="Total likes + retweets across thread")

class SocialResponse(BaseModel):
    """Source-agnostic comment/reply for generic social sources."""

    model_config = ConfigDict(extra='forbid')

    response_id: str = Field(..., description="Response identifier")
    author: str = Field(..., description="Response author")
    body: str = Field(..., description="Response text")
    score: int = Field(..., description="Response score/upvotes")
    created_utc: datetime = Field(..., description="Response creation timestamp")
    replies: list["SocialResponse"] = Field(
        default_factory=list, description="Nested replies"
    )


class SocialPost(BaseModel):
    """Source-agnostic post for non-Reddit/Twitter sources (HN, YouTube, etc.)."""

    model_config = ConfigDict(extra='forbid')

    post_id: str = Field(..., description="Post identifier")
    platform: str = Field(..., description="Source platform (hackernews, youtube, etc.)")
    title: str = Field(..., description="Post title")
    body: str = Field(..., description="Post body text (selftext, transcript, etc.)")
    author: str = Field(..., description="Post author")
    url: str = Field(..., description="Post URL")
    score: int = Field(..., description="Post score/points")
    num_responses: int = Field(..., description="Number of comments/replies")
    created_utc: datetime = Field(..., description="Post creation timestamp")
    responses: list[SocialResponse] = Field(
        default_factory=list, description="Top-level comments/replies"
    )
    raw_engagement: dict[str, int | float | bool] = Field(
        default_factory=dict, description="Platform-specific engagement metrics"
    )


class SocialContentCollection(BaseModel):
    """Collection of social media content from all platforms."""

    model_config = ConfigDict(extra='forbid')

    reddit_posts: list[RedditPost] = Field(
        default_factory=list, description="Collected Reddit posts"
    )
    twitter_threads: list[TwitterThread] = Field(
        default_factory=list, description="Collected Twitter threads"
    )
    generic_posts: list[SocialPost] = Field(
        default_factory=list, description="Collected posts from generic sources (HN, YouTube, etc.)"
    )
    total_reddit_comments: int = Field(default=0, description="Total Reddit comments collected")
    total_twitter_tweets: int = Field(default=0, description="Total tweets collected")
    total_generic_responses: int = Field(default=0, description="Total generic source responses collected")
    collection_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When collection was performed"
    )

# Update forward references
RedditComment.model_rebuild()
SocialResponse.model_rebuild()
