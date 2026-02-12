"""
Content Preparers - Functions for formatting data into knowledge source content.
Used by crews to prepare pain points and competitor intelligence for RAG.
"""

import re
from datetime import datetime, timezone
from typing import List

from loguru import logger

from ...models.pain_point import PainPointAnalysisResult
from ...models.social_content import SocialContentCollection
from ...utils.token_monitor import ContentTokenMonitor

MAX_COMPETITOR_CONTENT_CHARS = 30_000
MAX_COMMENT_EXCERPTS_PER_POST = 8

# Strip URLs before sentence splitting (dots in URLs cause bad splits)
_URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)

# Sentence splitting: split on sentence-ending punctuation followed by whitespace, or newlines
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+|\n+')

# Word-boundary keyword pattern for competitor/tool mentions.
# Using \b ensures "app" won't match inside "happy", etc.
_COMPETITOR_KEYWORDS = [
    # Usage patterns
    r"tried", r"currently use", r"been using", r"started using",
    r"switched from", r"switched to", r"switching from", r"switching to",
    r"migrated from", r"migrated to",
    # Comparisons
    r"alternative", r"instead of", r"compared to", r"better than",
    r"worse than", r"\bvs\b", r"competitor",
    # Product terms
    r"tools?", r"platform", r"software", r"apps?", r"plugin",
    r"integration", r"dashboard", r"automation", r"workflow",
    r"saas", r"\bapi\b", r"features?",
    # Pricing
    r"subscription", r"pricing", r"free tier", r"free plan",
    r"paid plan", r"freemium", r"trial", r"per month", r"per year",
    r"per seat", r"expensive", r"affordable", r"cheap",
    r"upgrade", r"downgrade",
    # Evaluation
    r"recommend", r"reviews?", r"worth trying", r"looking for",
    # Domain hints (product URLs like foo.com, bar.io, baz.app)
    r"\w+\.(?:com|io|app|ai)\b",
]

_INDICATOR_PATTERN = re.compile(
    r"\b(?:" + "|".join(_COMPETITOR_KEYWORDS) + r")",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences after stripping URLs.

    Replaces URLs with [URL] placeholder to avoid sentence-split on dots in URLs.
    Skips sentences shorter than 15 characters.
    """
    cleaned = _URL_PATTERN.sub("[URL]", text)
    raw_sentences = _SENTENCE_SPLIT.split(cleaned)
    return [s.strip() for s in raw_sentences if s.strip() and len(s.strip()) >= 15]


def _extract_relevant_sentences(
    text: str,
    pattern: re.Pattern,
    context_sentences: int = 2,
) -> str:
    """Extract sentences matching the pattern with surrounding context.

    Groups consecutive matching regions into contiguous excerpts.

    Args:
        text: Raw text to extract from
        pattern: Compiled regex pattern for keyword matching
        context_sentences: Number of context sentences before/after each match

    Returns:
        Extracted excerpt string (may be empty)
    """
    if not text:
        return ""

    sentences = _split_sentences(text)
    if not sentences:
        return ""

    # Find indices of matching sentences
    match_indices = set()
    for i, sent in enumerate(sentences):
        if pattern.search(sent):
            match_indices.add(i)

    if not match_indices:
        return ""

    # Expand with context
    include_indices = set()
    for idx in match_indices:
        start = max(0, idx - context_sentences)
        end = min(len(sentences) - 1, idx + context_sentences)
        for i in range(start, end + 1):
            include_indices.add(i)

    # Build contiguous excerpts separated by "..."
    sorted_indices = sorted(include_indices)
    excerpts = []
    current_group: List[str] = []
    prev_idx = -2

    for idx in sorted_indices:
        if idx != prev_idx + 1 and current_group:
            excerpts.append(" ".join(current_group))
            current_group = []
        current_group.append(sentences[idx])
        prev_idx = idx

    if current_group:
        excerpts.append(" ".join(current_group))

    return " ... ".join(excerpts)


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
    Extract competitor and tool mentions from social discussions using
    sentence-level extraction. Instead of dumping entire posts, extracts
    only the relevant sentences (with surrounding context) that match
    competitor/tool keyword patterns.

    Args:
        social_content: Social media posts and threads

    Returns:
        Formatted string of competitor excerpts suitable for StringKnowledgeSource
    """
    if not social_content:
        return ""

    if not social_content.reddit_posts and not social_content.twitter_threads:
        return ""

    # Sort Reddit posts by discussion quality (highest first)
    reddit_posts = sorted(
        social_content.reddit_posts,
        key=ContentTokenMonitor.pain_point_priority_score,
        reverse=True,
    ) if social_content.reddit_posts else []

    formatted = []
    total_chars = 0
    now = datetime.now(timezone.utc)
    reddit_count = 0
    twitter_count = 0

    # Process Reddit posts
    for post in reddit_posts:
        if total_chars >= MAX_COMPETITOR_CONTENT_CHARS:
            break

        # Extract from post title + body
        post_text = f"{post.title}. {post.selftext or ''}"
        post_excerpt = _extract_relevant_sentences(post_text, _INDICATOR_PATTERN)

        # Extract from comments
        comment_excerpts = []
        for comment in (post.comments or []):
            if len(comment_excerpts) >= MAX_COMMENT_EXCERPTS_PER_POST:
                break
            excerpt = _extract_relevant_sentences(comment.body, _INDICATOR_PATTERN)
            if excerpt:
                comment_excerpts.append(excerpt)

        # Skip post if nothing relevant found
        if not post_excerpt and not comment_excerpts:
            continue

        # Compute age label
        age_label = "Unknown"
        created = getattr(post, 'created_utc', None)
        if created:
            days_ago = (now - created).days
            if days_ago < 30:
                age_label = f"Recent: {days_ago}d ago"
            elif days_ago < 180:
                age_label = f"Moderate: {days_ago // 30}mo ago"
            else:
                years_ago = days_ago // 365
                age_label = f"Dated: {years_ago}yr ago" if years_ago >= 1 else f"Dated: {days_ago}d ago"

        # Format post entry
        entry_parts = [
            f"[SUBREDDIT: r/{post.subreddit}]",
            f"[SCORE: {post.score}]",
            f"[AGE: {age_label}]",
            f"### {post.title}",
        ]
        if post_excerpt:
            entry_parts.append(post_excerpt)
        if comment_excerpts:
            entry_parts.append("Comments:")
            for ce in comment_excerpts:
                entry_parts.append(f"- {ce}")

        entry = "\n".join(entry_parts)

        if total_chars + len(entry) > MAX_COMPETITOR_CONTENT_CHARS:
            break

        formatted.append(entry)
        total_chars += len(entry)
        reddit_count += 1

    # Process Twitter threads
    for thread in (social_content.twitter_threads or []):
        if total_chars >= MAX_COMPETITOR_CONTENT_CHARS:
            break

        # Extract from original tweet
        tweet_excerpt = _extract_relevant_sentences(
            thread.original_tweet.text, _INDICATOR_PATTERN
        )

        # Extract from replies
        reply_excerpts = []
        for reply in thread.replies:
            if len(reply_excerpts) >= MAX_COMMENT_EXCERPTS_PER_POST:
                break
            excerpt = _extract_relevant_sentences(reply.text, _INDICATOR_PATTERN)
            if excerpt:
                reply_excerpts.append(excerpt)

        if not tweet_excerpt and not reply_excerpts:
            continue

        entry_parts = [
            f"[LIKES: {thread.original_tweet.likes}]",
        ]
        if tweet_excerpt:
            entry_parts.append(tweet_excerpt)
        if reply_excerpts:
            entry_parts.append("Replies:")
            for re_ in reply_excerpts:
                entry_parts.append(f"- {re_}")

        entry = "\n".join(entry_parts)

        if total_chars + len(entry) > MAX_COMPETITOR_CONTENT_CHARS:
            break

        formatted.append(entry)
        total_chars += len(entry)
        twitter_count += 1

    if not formatted:
        logger.info("No competitor mentions found in social content")
        return ""

    result = "\n\n===\n\n".join(formatted)

    if len(result) < 100:
        logger.warning(
            f"Competitor intelligence too short ({len(result)} chars), skipping"
        )
        return ""

    logger.info(
        f"Extracted competitor intelligence: {reddit_count} Reddit posts, "
        f"{twitter_count} Twitter threads, {len(result)} chars "
        f"(was {sum(len(p.selftext or '') for p in reddit_posts)} chars raw)"
    )

    return result
