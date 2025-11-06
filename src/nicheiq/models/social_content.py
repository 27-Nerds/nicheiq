"""
Pydantic models for social media content (Stages 4-5).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RedditComment(BaseModel):
    """Represents a single Reddit comment."""

    comment_id: str = Field(..., description="Reddit comment ID")
    author: str = Field(..., description="Comment author username")
    body: str = Field(..., description="Comment text")
    score: int = Field(..., description="Comment score (upvotes - downvotes)")
    created_utc: datetime = Field(..., description="Comment creation timestamp")
    is_submitter: bool = Field(default=False, description="Whether author is post submitter")
    replies: List["RedditComment"] = Field(
        default_factory=list, description="Nested reply comments"
    )


class RedditPost(BaseModel):
    """Represents a Reddit post with comments."""

    post_id: str = Field(..., description="Reddit post ID")
    title: str = Field(..., description="Post title")
    selftext: str = Field(..., description="Post body text")
    author: str = Field(..., description="Post author username")
    subreddit: str = Field(..., description="Subreddit name")
    score: int = Field(..., description="Post score (upvotes - downvotes)")
    num_comments: int = Field(..., description="Number of comments")
    created_utc: datetime = Field(..., description="Post creation timestamp")
    url: str = Field(..., description="Post URL")
    comments: List[RedditComment] = Field(
        default_factory=list, description="Top-level comments"
    )

    class Config:
        json_schema_extra = {
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


class TwitterTweet(BaseModel):
    """Represents a single tweet."""

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

    thread_id: str = Field(..., description="Thread identifier (original tweet ID)")
    original_tweet: TwitterTweet = Field(..., description="Original tweet starting the thread")
    replies: List[TwitterTweet] = Field(default_factory=list, description="Reply tweets")
    total_engagement: int = Field(..., description="Total likes + retweets across thread")

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "xyz789",
                "original_tweet": {},
                "replies": [],
                "total_engagement": 150,
            }
        }


class SocialContentCollection(BaseModel):
    """Collection of social media content from both platforms."""

    reddit_posts: List[RedditPost] = Field(
        default_factory=list, description="Collected Reddit posts"
    )
    twitter_threads: List[TwitterThread] = Field(
        default_factory=list, description="Collected Twitter threads"
    )
    total_reddit_comments: int = Field(default=0, description="Total Reddit comments collected")
    total_twitter_tweets: int = Field(default=0, description="Total tweets collected")
    collection_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When collection was performed"
    )


# Update forward references
RedditComment.model_rebuild()
