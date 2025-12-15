"""
Content Preparers - Functions for formatting data into knowledge source content.
Used by crews to prepare pain points and competitor intelligence for RAG.
"""

import re

from loguru import logger

from ...models.pain_point import PainPointAnalysisResult
from ...models.social_content import SocialContentCollection


def prepare_pain_point_content(pain_point_analysis: PainPointAnalysisResult) -> str:
    """
    Format pain points with ALL quotes for knowledge source.
    Preserves all 3-5 quotes per pain point for richer context.

    Args:
        pain_point_analysis: Validated pain points from PainPointCrew

    Returns:
        Formatted string suitable for StringKnowledgeSource
    """
    if not pain_point_analysis.pain_points:
        return ""

    formatted = []
    for pp in pain_point_analysis.pain_points:
        formatted.append(
            f"""[PAIN POINT: {pp.title}]
[SEVERITY: {pp.severity_score:.2f}]
[WILLINGNESS TO PAY: {pp.willingness_to_pay:.2f}]
[OPPORTUNITY LEVEL: {pp.opportunity_level.value}]
[MENTIONS: {pp.mention_count}]
[PLATFORMS: {', '.join(pp.source_platforms if pp.source_platforms else ['N/A'])}]
[CATEGORIES: {', '.join(pp.categories if pp.categories else ['N/A'])}]

### Problem Description:
{pp.description}

### All User Evidence ({len(pp.representative_quotes)} quotes):
{chr(10).join(f'- "{quote}"' for quote in pp.representative_quotes)}
"""
        )
    return "\n\n===\n\n".join(formatted)


def prepare_competitor_intelligence(social_content: SocialContentCollection) -> str:
    """
    Extract competitor and tool mentions from social discussions.
    Filters content for existing tools, alternatives, comparisons, pricing.

    Args:
        social_content: Social media posts and threads

    Returns:
        Formatted string of competitor mentions suitable for StringKnowledgeSource
    """
    if not social_content:
        return ""

    if not social_content.reddit_posts and not social_content.twitter_threads:
        return ""

    competitor_indicators = [
        # Usage patterns
        "using",
        "used",
        "tried",
        "currently use",
        "switched from",
        "switched to",
        # Comparisons and alternatives
        "alternative",
        "instead of",
        "compared to",
        "better than",
        "worse than",
        # Tool/product names and categories
        "tool",
        "platform",
        "service",
        "app",
        "software",
        "website",
        # Pricing and value
        "price",
        "cost",
        "expensive",
        "cheap",
        "affordable",
        "worth",
        "subscription",
        "free",
        "paid",
        "trial",
    ]

    # Performance optimization: Compile indicators into regex pattern
    # Reduces O(n*m*k) to O(n*m) where k=indicator count
    indicator_pattern = re.compile(
        "|".join(re.escape(indicator) for indicator in competitor_indicators),
        re.IGNORECASE,
    )

    # Filter Reddit posts for competitor mentions
    filtered_reddit = []
    for post in social_content.reddit_posts:
        # Check post title and body
        content_lower = (post.title + " " + (post.selftext or "")).lower()
        if indicator_pattern.search(content_lower):
            filtered_reddit.append(post)
        else:
            # Check comments for competitor mentions
            for comment in post.comments:
                if indicator_pattern.search(comment.body.lower()):
                    filtered_reddit.append(post)
                    break

    # Filter Twitter threads for competitor mentions
    filtered_twitter = []
    for thread in social_content.twitter_threads:
        content_lower = thread.root_tweet.text.lower()
        if indicator_pattern.search(content_lower):
            filtered_twitter.append(thread)
        else:
            # Check replies
            for reply in thread.replies:
                if indicator_pattern.search(reply.text.lower()):
                    filtered_twitter.append(thread)
                    break

    if not filtered_reddit and not filtered_twitter:
        logger.info("No competitor mentions found in social content")
        return ""

    # Format filtered content
    formatted = []

    # Reddit competitor intelligence
    if filtered_reddit:
        formatted.append("[REDDIT COMPETITOR INTELLIGENCE]\n")
        for post in filtered_reddit:
            formatted.append(
                f"""[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]

### {post.title}

{post.selftext}

---
## Discussion ({len(post.comments)} comments):
{chr(10).join(f'- "{c.body}"' for c in post.comments[:10])}
"""
            )

    # Twitter competitor intelligence
    if filtered_twitter:
        formatted.append("\n\n[TWITTER COMPETITOR INTELLIGENCE]\n")
        for thread in filtered_twitter:
            formatted.append(
                f"""[LIKES: {thread.root_tweet.likes}]

### Root Tweet:
{thread.root_tweet.text}

---
## Replies ({len(thread.replies)} total):
{chr(10).join(f'- "{r.text}"' for r in thread.replies[:10])}
"""
            )

    logger.info(
        f"Filtered competitor intelligence: {len(filtered_reddit)} Reddit posts, "
        f"{len(filtered_twitter)} Twitter threads"
    )

    return "\n\n===\n\n".join(formatted)
