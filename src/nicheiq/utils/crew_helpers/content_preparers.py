"""
Content Preparers - Functions for formatting data for crew consumption.
Includes RAG-era formatters (prepare_*) and direct injection formatters (format_*).
"""

import re
from datetime import datetime, timezone
from typing import List, Literal

from loguru import logger
from pydantic import BaseModel, Field

from ...models.pain_point import PainPointAnalysisResult
from ...models.social_content import SocialContentCollection
from ...utils.content_security import fence_content, sanitize_social_content
from ...utils.token_monitor import ContentTokenMonitor

# Known prompt injection patterns to strip from scraped content
_INJECTION_PATTERNS = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|"
    r"you\s+are\s+now\s+|"
    r"^SYSTEM:|^ASSISTANT:|^USER:|"
    r"<\|(?:im_start|im_end|endoftext)\|>|"
    r"\bdo\s+not\s+follow\s+any\s+(?:other|previous)\b)",
)


def _sanitize_for_llm(text: str) -> str:
    """Strip control characters and prompt injection patterns from scraped text."""
    if not text:
        return ""
    sanitized = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    sanitized = _INJECTION_PATTERNS.sub("[REDACTED]", sanitized)
    return sanitized


# ============================================================
# Pydantic models for LLM-based tool extraction
# ============================================================

class ExtractedToolMention(BaseModel):
    """A product/brand/tool extracted from community discussions."""
    name: str = Field(description="Product, brand, tool, or service name as mentioned by users")
    category: Literal["software", "supplement", "skincare", "equipment", "service", "compound", "other"] = Field(
        description="Category of the product/tool"
    )


class ToolMentionExtractionResult(BaseModel):
    """Extracted tool/product mentions from community discussion sentences."""
    mentions: list[ExtractedToolMention] = Field(
        description="All distinct products, brands, tools, or services mentioned. "
        "Exclude generic category terms (e.g., 'peptides', 'supplements', 'collagen')."
    )

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

    # Sanitize each sentence to strip injection patterns
    sentences = [_sanitize_for_llm(s) for s in sentences]

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

    if not social_content.reddit_posts and not social_content.twitter_threads and not social_content.generic_posts:
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

    # Process generic posts (HN, YouTube, etc.)
    generic_count = 0
    for post in (social_content.generic_posts or []):
        if total_chars >= MAX_COMPETITOR_CONTENT_CHARS:
            break

        post_text = f"{post.title}. {post.body or ''}"
        post_excerpt = _extract_relevant_sentences(post_text, _INDICATOR_PATTERN)

        response_excerpts = []
        for resp in (post.responses or []):
            if len(response_excerpts) >= MAX_COMMENT_EXCERPTS_PER_POST:
                break
            excerpt = _extract_relevant_sentences(resp.body, _INDICATOR_PATTERN)
            if excerpt:
                response_excerpts.append(excerpt)

        if not post_excerpt and not response_excerpts:
            continue

        container = {"hackernews": "Hacker News", "youtube": "YouTube"}.get(post.platform, post.platform)
        entry_parts = [f"[{container}: {post.score} pts]"]
        if post_excerpt:
            entry_parts.append(post_excerpt)
        if response_excerpts:
            entry_parts.append("Responses:")
            for re_ in response_excerpts:
                entry_parts.append(f"- {re_}")

        entry = "\n".join(entry_parts)
        if total_chars + len(entry) > MAX_COMPETITOR_CONTENT_CHARS:
            break

        formatted.append(entry)
        total_chars += len(entry)
        generic_count += 1

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
        f"{twitter_count} Twitter threads, {generic_count} generic posts, {len(result)} chars "
        f"(was {sum(len(p.selftext or '') for p in reddit_posts)} chars raw)"
    )

    return result


def _extract_tools_via_llm(
    all_mentions: list[tuple[str, str, int]],
) -> list[ExtractedToolMention]:
    """Extract tool/product names from sentences using LLM.

    Deduplicates by sentence text and takes top 80 by score, sends to gpt-4o-mini
    in a single structured-output call. Returns list of extracted mentions.
    """
    from ...config.settings import settings
    from ..llm_service import LLMService

    # Deduplicate by full lowercase sentence, keep highest-scored
    seen: set[str] = set()
    unique: list[tuple[str, str, int]] = []
    for sent, source, score in sorted(all_mentions, key=lambda x: x[2], reverse=True):
        key = sent.strip().lower()
        if key not in seen:
            seen.add(key)
            # Truncate long sentences to ~200 chars
            unique.append((sent[:200], source, score))
        if len(unique) >= 80:
            break

    # Build numbered prompt
    numbered = "\n".join(f"[{i+1}] {sent}" for i, (sent, _, _) in enumerate(unique))

    prompt = f"""Extract all specific product names, brand names, tool names, software names,
compound trade names, and service names mentioned in these community discussion excerpts.

RULES:
- Extract SPECIFIC products/brands/tools (e.g., "Notion", "BPC-157", "The Ordinary", "Ahrefs")
- Do NOT extract generic category terms (e.g., "peptides", "supplements", "software", "tools")
- Do NOT extract medical/scientific terms that aren't product names
- Normalize variations into canonical form (e.g., "tirz"/"tirzepatide" → "Tirzepatide")

Sentences:
{numbered}"""

    model = getattr(settings, 'competitor_extraction_llm', 'gpt-4.1-mini')

    # Single retry on failure before raising
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            result, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=ToolMentionExtractionResult,
                temperature=0,
                timeout=30,
                model_name=model,
            )
            logger.info(
                f"LLM tool extraction: {len(result.mentions)} unique tools "
                f"({usage.prompt_tokens}+{usage.completion_tokens} tokens, attempt {attempt+1})"
            )
            return result.mentions
        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.warning(f"LLM tool extraction attempt 1 failed: {e}, retrying...")

    raise last_error  # type: ignore[misc]


def _boost_with_seed_list(
    tool_map: dict[str, list[tuple[str, str, int]]],
    all_mentions: list[tuple[str, str, int]],
    known_tools: list[str],
) -> None:
    """Add known tools from audience mapping not already found by LLM."""
    existing_lower = {k.lower() for k in tool_map}
    for tool in known_tools:
        if tool.lower() in existing_lower:
            continue
        pattern = re.compile(r'\b' + re.escape(tool) + r'\b', re.IGNORECASE)
        matched = [(s, src, sc) for s, src, sc in all_mentions if pattern.search(s)]
        if matched:
            tool_map[tool] = matched


def format_competitor_mentions_for_prompt(
    social_content: SocialContentCollection,
    known_tools: list[str] | None = None,
    max_entries: int = 15,
    max_chars: int = 3000,
) -> str:
    """Format competitor/tool mentions as direct task input.

    Uses LLM extraction (gpt-4o-mini) to identify product/brand/tool names.
    Falls back to seed-list matching on API failure.

    Returns:
        Formatted string, or "No competitor data available" if empty.
    """
    if not social_content:
        return "No competitor data available"

    if not social_content.reddit_posts and not social_content.twitter_threads and not social_content.generic_posts:
        return "No competitor data available"

    # --- Pre-filter: extract indicator-matched sentences ---
    all_mentions: List[tuple] = []

    for post in (social_content.reddit_posts or []):
        source = f"r/{post.subreddit}"
        score = post.score or 0

        post_text = f"{post.title}. {post.selftext or ''}"
        for sent in _split_sentences(post_text):
            if _INDICATOR_PATTERN.search(sent):
                all_mentions.append((sent, source, score))

        for comment in (post.comments or []):
            for sent in _split_sentences(comment.body):
                if _INDICATOR_PATTERN.search(sent):
                    all_mentions.append((sent, source, score))

    for thread in (social_content.twitter_threads or []):
        source = "Twitter"
        score = thread.original_tweet.likes or 0

        for sent in _split_sentences(thread.original_tweet.text):
            if _INDICATOR_PATTERN.search(sent):
                all_mentions.append((sent, source, score))

        for reply in thread.replies:
            for sent in _split_sentences(reply.text):
                if _INDICATOR_PATTERN.search(sent):
                    all_mentions.append((sent, source, score))

    # Extract competitor mentions from generic sources (HN, YouTube)
    _platform_labels = {"hackernews": "Hacker News", "youtube": "YouTube"}
    for post in (social_content.generic_posts or []):
        source = _platform_labels.get(post.platform, post.platform)
        score = post.score or 0

        post_text = f"{post.title}. {post.body or ''}"
        for sent in _split_sentences(post_text):
            if _INDICATOR_PATTERN.search(sent):
                all_mentions.append((sent, source, score))

        for resp in (post.responses or []):
            for sent in _split_sentences(resp.body):
                if _INDICATOR_PATTERN.search(sent):
                    all_mentions.append((sent, source, score))

    if not all_mentions:
        return "No competitor data available"

    # --- Extract tool names via LLM ---
    tool_map: dict[str, list[tuple[str, str, int]]] = {}

    try:
        extracted = _extract_tools_via_llm(all_mentions)
        # Map extracted names back to sentences via word-boundary matching
        for mention in extracted:
            name = mention.name.strip()
            if len(name) < 2:
                continue
            pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            matched = [(s, src, sc) for s, src, sc in all_mentions if pattern.search(s)]
            if matched:
                tool_map[name] = matched
    except Exception as e:
        logger.warning(f"LLM tool extraction failed, using seed list only: {e}")

    # --- Boost with seed list ---
    if known_tools:
        _boost_with_seed_list(tool_map, all_mentions, known_tools)

    if not tool_map:
        return "No competitor data available"

    # --- Format output ---
    sorted_tools = sorted(tool_map.items(), key=lambda x: len(x[1]), reverse=True)

    lines = ["### Competitor & Tool Mentions from Community Discussions\n"]
    total_chars = len(lines[0])
    entry_count = 0

    frequent = [(name, sents) for name, sents in sorted_tools if len(sents) >= 3]
    occasional = [(name, sents) for name, sents in sorted_tools if len(sents) < 3]

    if frequent:
        lines.append("**Frequently mentioned (3+ posts):**")
        total_chars += len(lines[-1])
        for name, sents in frequent:
            if entry_count >= max_entries or total_chars >= max_chars:
                break
            best = max(sents, key=lambda x: x[2])
            line = f"- **{name}** ({len(sents)} mentions): \"{sanitize_social_content(best[0])[:150]}\" [{best[1]}]"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)
            entry_count += 1

    if occasional and entry_count < max_entries:
        lines.append("\n**Also mentioned:**")
        total_chars += len(lines[-1])
        for name, sents in occasional:
            if entry_count >= max_entries or total_chars >= max_chars:
                break
            best = max(sents, key=lambda x: x[2])
            line = f"- **{name}**: \"{sanitize_social_content(best[0])[:150]}\" [{best[1]}]"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)
            entry_count += 1

    result = "\n".join(lines)
    logger.info(
        f"Formatted {entry_count} competitor mentions for direct injection "
        f"({len(result)} chars, {len(frequent)} frequent, {len(occasional)} occasional)"
    )
    # Delimiter-fence: this block contains scraped (untrusted) snippets reaching the
    # competitive + pricing prompts. Sanitized above; fence so injected instructions
    # inside a snippet are treated as data, not commands.
    return fence_content(result, source="community-competitor-mentions")
