"""
Influencer Pre-Compute — algorithmic influencer metrics from raw social data.

Replaces 100% LLM-generated influencer metrics with reproducible,
data-driven scores computed from Reddit posts/comments and Twitter threads.

The LLM only contributes ``content_focus``; all other fields are authoritative.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from typing import Any

from ...models.social_content import RedditComment, RedditPost, TwitterThread
from ..content_security import sanitize_social_content

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEIGHT_ENGAGEMENT = 0.5
WEIGHT_ACTIVITY = 0.3
WEIGHT_BREADTH = 0.2

POST_ENGAGEMENT_WEIGHT = 0.6
COMMENT_ENGAGEMENT_WEIGHT = 0.4

BREADTH_CAP = 5
RELEVANCE_FLOOR = 0.10
TOP_N_DEFAULT = 10
TOP_SUBREDDITS_N = 3
TOP_POSTS_N = 3

BOT_BLOCKLIST: frozenset[str] = frozenset({
    "automoderator",
    "remindmebot",
    "repostsleuthbot",
    "sneakpeekbot",
    "savevideo",
})

BOT_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)(bot$|^\[deleted\]$|^\[removed\]$|^$)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_excluded(author: str) -> bool:
    """Return True if author should be filtered out."""
    lower = author.strip().lower()
    if not lower:
        return True
    if lower in BOT_BLOCKLIST:
        return True
    if BOT_PATTERN.search(lower):
        return True
    return False


def _format_karma(total_karma: int) -> str:
    """Format karma into a human-readable string."""
    if total_karma >= 1_000_000:
        return f"{total_karma / 1_000_000:.1f}M karma"
    if total_karma >= 1_000:
        return f"{total_karma / 1_000:.1f}K karma"
    return f"{total_karma} karma"


def _truncate(text: str, max_len: int = 100) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ---------------------------------------------------------------------------
# Author tracking data structure
# ---------------------------------------------------------------------------

def _empty_author() -> dict[str, Any]:
    return {
        "posts": 0,
        "comments": 0,
        "threads": 0,
        "replies": 0,
        "post_score": 0,
        "comment_score": 0,
        "twitter_likes": 0,
        "twitter_retweets": 0,
        "subreddit_counts": defaultdict(int),
        "unique_subreddits": set(),
        "platform": "Reddit",
        "top_posts": [],  # list of {title, subreddit, score, url}
    }


# ---------------------------------------------------------------------------
# Reddit aggregation
# ---------------------------------------------------------------------------

def _walk_comments(
    comments: list[RedditComment],
    authors: dict[str, dict],
    post_url: str,
    subreddit: str,
) -> None:
    """Recursively walk comments, accumulating per-author stats."""
    for comment in comments:
        author = comment.author.strip()
        if _is_excluded(author):
            if comment.replies:
                _walk_comments(comment.replies, authors, post_url, subreddit)
            continue

        lower = author.lower()
        a = authors[lower]
        a["comments"] += 1
        a["comment_score"] += max(0, comment.score)
        a["subreddit_counts"][subreddit] += 1
        a["unique_subreddits"].add(subreddit)
        a["_raw_name"] = author  # preserve original case

        a["top_posts"].append({
            "title": _truncate(sanitize_social_content(comment.body)),
            "subreddit": subreddit,
            "score": comment.score,
            "url": post_url,
        })

        if comment.replies:
            _walk_comments(comment.replies, authors, post_url, subreddit)


def _collect_reddit_authors(
    reddit_posts: list[RedditPost],
    authors: dict[str, dict],
) -> None:
    """Aggregate per-author metrics from Reddit posts and comments."""
    for post in reddit_posts:
        author = post.author.strip()
        subreddit = post.subreddit

        if not _is_excluded(author):
            lower = author.lower()
            a = authors[lower]
            a["posts"] += 1
            a["post_score"] += max(0, post.score)
            a["subreddit_counts"][subreddit] += 1
            a["unique_subreddits"].add(subreddit)
            a["platform"] = "Reddit"
            a["_raw_name"] = author

            a["top_posts"].append({
                "title": sanitize_social_content(post.title),
                "subreddit": subreddit,
                "score": post.score,
                "url": post.url,
            })

        if post.comments:
            _walk_comments(post.comments, authors, post.url, subreddit)


# ---------------------------------------------------------------------------
# Twitter aggregation
# ---------------------------------------------------------------------------

def _collect_twitter_authors(
    twitter_threads: list[TwitterThread],
    authors: dict[str, dict],
) -> None:
    """Aggregate per-author metrics from Twitter threads."""
    for thread in twitter_threads:
        tweet = thread.original_tweet
        author = tweet.author_username.strip()
        if not _is_excluded(author):
            lower = author.lower()
            a = authors[lower]
            a["threads"] += 1
            a["twitter_likes"] += max(0, tweet.likes)
            a["twitter_retweets"] += max(0, tweet.retweets)
            a["_raw_name"] = author

            # If this author has no Reddit data, mark as Twitter
            if a["posts"] == 0 and a["comments"] == 0:
                a["platform"] = "Twitter"

        for reply in thread.replies:
            r_author = reply.author_username.strip()
            if _is_excluded(r_author):
                continue
            lower = r_author.lower()
            a = authors[lower]
            a["replies"] += 1
            a["twitter_likes"] += max(0, reply.likes)
            a["twitter_retweets"] += max(0, reply.retweets)
            a["_raw_name"] = r_author

            if a["posts"] == 0 and a["comments"] == 0:
                a["platform"] = "Twitter"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_author(a: dict) -> float:
    """Compute raw composite score for one author."""
    activity = math.log2(
        1 + a["posts"] + a["comments"] + a["threads"] + a["replies"]
    )
    engagement_reddit = (
        math.log2(1 + a["post_score"]) * POST_ENGAGEMENT_WEIGHT
        + math.log2(1 + a["comment_score"]) * COMMENT_ENGAGEMENT_WEIGHT
    )
    engagement_twitter = math.log2(
        1 + a["twitter_likes"] + a["twitter_retweets"]
    )
    engagement = max(engagement_reddit, engagement_twitter)
    breadth = math.log2(1 + min(len(a["unique_subreddits"]), BREADTH_CAP))
    return (
        engagement * WEIGHT_ENGAGEMENT
        + activity * WEIGHT_ACTIVITY
        + breadth * WEIGHT_BREADTH
    )


def _derive_engagement_level(relevance: float) -> str:
    if relevance >= 0.70:
        return "High"
    if relevance >= 0.35:
        return "Medium"
    return "Low"


def _derive_outreach_priority(relevance: float, engagement_level: str) -> str:
    if relevance >= 0.60 and engagement_level != "Low":
        return "High"
    if relevance >= 0.30:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate_author_metrics(
    reddit_posts: list[RedditPost],
    twitter_threads: list[TwitterThread],
) -> list[dict]:
    """
    Pure aggregation: compute per-author metrics from raw social data.

    Returns a list of author dicts sorted by raw score descending.
    No I/O is performed.
    """
    authors: dict[str, dict] = defaultdict(_empty_author)

    _collect_reddit_authors(reddit_posts, authors)
    _collect_twitter_authors(twitter_threads, authors)

    if not authors:
        return []

    # Score all authors
    scored: list[tuple[str, dict, float]] = []
    for username, a in authors.items():
        raw = _score_author(a)
        scored.append((username, a, raw))

    scored.sort(key=lambda x: x[2], reverse=True)
    max_raw = scored[0][2] if scored else 1.0
    if max_raw == 0:
        max_raw = 1.0

    results = []
    for username, a, raw in scored:
        relevance = round(raw / max_raw, 2)
        relevance = max(relevance, RELEVANCE_FLOOR)

        # Derive top subreddits
        sub_counts = dict(a["subreddit_counts"])
        top_subs = sorted(sub_counts.items(), key=lambda x: x[1], reverse=True)[:TOP_SUBREDDITS_N]
        top_subreddits = [f"r/{s}" for s, _ in top_subs]

        # Derive top posts
        all_posts = sorted(a["top_posts"], key=lambda x: x["score"], reverse=True)[:TOP_POSTS_N]

        # Determine display name (sanitize: a scraped username can carry injection bytes)
        raw_name = sanitize_social_content(a.get("_raw_name", username))
        platform = a["platform"]
        if platform == "Twitter":
            display_name = f"@{raw_name}"
        else:
            display_name = f"u/{raw_name}"

        engagement_level = _derive_engagement_level(relevance)
        outreach_priority = _derive_outreach_priority(relevance, engagement_level)

        # Fallback content_focus
        fallback_focus = f"Active in {top_subreddits[0]}" if top_subreddits else "Active community member"

        results.append({
            "name": display_name,
            "platform": platform,
            "relevance_score": relevance,
            "engagement_level": engagement_level,
            "outreach_priority": outreach_priority,
            "follower_estimate": None,
            "content_focus": fallback_focus,
            "top_subreddits": top_subreddits,
            "top_posts": all_posts,
        })

    return results


def enrich_top_authors_via_praw(
    profiles: list[dict],
    reddit_client: Any,
    n: int = TOP_N_DEFAULT,
) -> list[dict]:
    """
    Enrich the top *n* Reddit profiles with karma data from PRAW.

    Modifies profiles in-place and returns the same list.
    Failures are logged but never raise.
    """
    import prawcore.exceptions

    for profile in profiles[:n]:
        if profile["platform"] != "Reddit":
            continue

        username = profile["name"].lstrip("u/")
        try:
            redditor = reddit_client.redditor(username)
            total_karma = redditor.link_karma + redditor.comment_karma
            profile["follower_estimate"] = _format_karma(total_karma)
        except (
            prawcore.exceptions.NotFound,
            prawcore.exceptions.Forbidden,
            prawcore.exceptions.ServerError,
        ):
            logger.debug(f"PRAW lookup failed for u/{username}, keeping follower_estimate=None")
        except Exception:
            logger.debug(f"Unexpected PRAW error for u/{username}", exc_info=True)

    return profiles


def compute_influencer_profiles(
    reddit_posts: list[RedditPost],
    twitter_threads: list[TwitterThread],
    reddit_client: Any | None = None,
    n: int = TOP_N_DEFAULT,
) -> dict:
    """
    Main entry point: aggregate → rank → enrich → format.

    Returns::

        {
            "profiles": list[dict],
            "influencer_names_formatted": str,
        }
    """
    all_profiles = aggregate_author_metrics(reddit_posts, twitter_threads)

    # Take top N
    top_profiles = all_profiles[:n]

    # Enrich via PRAW if client available
    if reddit_client is not None and top_profiles:
        enrich_top_authors_via_praw(top_profiles, reddit_client, n=n)

    # Build formatted string for LLM prompt injection
    lines = []
    for i, p in enumerate(top_profiles, 1):
        subs = ", ".join(p["top_subreddits"]) if p["top_subreddits"] else "N/A"
        posts_str = ""
        if p["top_posts"]:
            post_items = []
            for tp in p["top_posts"]:
                post_items.append(f'"{tp["title"]}" (r/{tp["subreddit"]}, {tp["score"]} pts)')
            posts_str = "; ".join(post_items)

        lines.append(
            f"{i}. {p['name']} ({p['platform']}) — "
            f"relevance={p['relevance_score']:.2f}, "
            f"engagement={p['engagement_level']}, "
            f"outreach={p['outreach_priority']}"
            + (f", karma={p['follower_estimate']}" if p["follower_estimate"] else "")
            + f"\n   Top subreddits: {subs}"
            + (f"\n   Top posts: {posts_str}" if posts_str else "")
        )

    formatted = "\n".join(lines) if lines else "No influencer data available."

    return {
        "profiles": top_profiles,
        "influencer_names_formatted": formatted,
    }
