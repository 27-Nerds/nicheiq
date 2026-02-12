"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

import json
import re
from difflib import SequenceMatcher
from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import (
    ContentCategorizationReport,
    EnrichedPainPointQuotes,
    ExtractedQuote,
    PainPoint,
    PainPointAnalysisResult,
    PainPointExtraction,
    QuoteEnrichmentResult,
    SinglePainPointQuotesResult,
    UnvalidatedPainPoint,
    ValidationResult,
)
from ..models.social_content import RedditComment, RedditPost, TwitterThread, TwitterTweet
from ..utils.parsing.json_extractor import clean_llm_response, extract_json_object_from_text
from ..utils.token_monitor import ContentTokenMonitor
from ..utils.validation.crew_guardrails import (
    validate_content_categorization,
    validate_quote_enrichment,
)

# Source tracking pattern for [source: ID] suffixes
# Matches alphanumeric, dash, underscore, period (1-50 chars) for post/thread IDs
SOURCE_TAG_PATTERN = r'[\w\-_\.]{1,50}'

# Fuzzy matching threshold for pain point title matching (0.0-1.0)
# 0.85 = 85% similarity required to consider a match
FUZZY_MATCH_THRESHOLD = 0.85


def fuzzy_find_matching_score(title: str, scores: list, threshold: float = FUZZY_MATCH_THRESHOLD):
    """
    Find a matching score using fuzzy string matching.

    Args:
        title: The pain point title to match
        scores: List of PainPointScoring objects with pain_point_title attribute
        threshold: Minimum similarity ratio to consider a match (0.0-1.0)

    Returns:
        Tuple of (matching_score, similarity_ratio) or (None, 0.0) if no match
    """
    best_match = None
    best_ratio = 0.0
    title_normalized = title.lower().strip()

    for score in scores:
        score_title_normalized = score.pain_point_title.lower().strip()

        # First try exact match (case-insensitive)
        if title_normalized == score_title_normalized:
            return (score, 1.0)

        # Then try fuzzy match
        ratio = SequenceMatcher(None, title_normalized, score_title_normalized).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = score

    if best_ratio >= threshold:
        return (best_match, best_ratio)

    return (None, best_ratio)


def validate_pain_point_extraction(task_output) -> tuple[bool, Any]:
    """
    Guardrail for extract_pain_points_task to handle JSON parsing errors.

    CrewAI 1.7.0 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, clean_json_string) on success.

    Validates:
    - JSON is parseable (catches malformed output)
    - Has at least 3 extracted_pain_points
    - Each pain point has minimum required fields

    Falls back to bracket-matching JSON extraction when json.loads() fails
    (e.g., when agent wraps JSON in markdown text).

    Returns:
        tuple[bool, Any]: (success, model_dump_json_or_error)
    """
    try:
        # CrewAI 1.7.0: When guardrails exist, pydantic is intentionally None
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Pain point extraction returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response (remove XML tags, markdown fencing, etc.)
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = PainPointExtraction.model_validate(raw_json)
                logger.debug("Pain point extraction guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # Provide helpful error message for retry
                logger.warning(f"JSON parse error in pain point extraction: {e}")
                logger.warning(f"Raw output first 500 chars: {task_output.raw[:500] if task_output.raw else 'empty'}")

                # Fallback: try to extract a JSON object from surrounding text
                extracted_obj = extract_json_object_from_text(task_output.raw)
                if extracted_obj is not None:
                    try:
                        result = PainPointExtraction.model_validate(extracted_obj)
                        logger.info("Pain point extraction guardrail: Recovered JSON object from text")
                    except Exception as e2:
                        logger.warning(f"Extracted JSON object failed Pydantic validation: {e2}")
                        result = None

                if extracted_obj is None or result is None:
                    return (
                        False,
                        "Your output is NOT valid JSON — it appears to be markdown-formatted text. "
                        "Return ONLY a raw JSON object starting with { and ending with }. "
                        "Do NOT use **bold** markdown formatting. Do NOT include any text before or after the JSON. "
                        "The JSON must have keys: niche, extracted_pain_points, extraction_summary."
                    )
            except Exception as e:
                logger.warning(f"Failed to validate PainPointExtraction: {e}")
                return (False, f"Failed to parse PainPointExtraction: {e}")

        if not isinstance(result, PainPointExtraction):
            return (
                False,
                f"Invalid type: expected PainPointExtraction, got {type(result)}"
            )

        # Validate minimum pain points
        if len(result.extracted_pain_points) < 3:
            return (
                False,
                f"Need at least 3 extracted_pain_points, got {len(result.extracted_pain_points)}. "
                "If data is sparse, still identify at least 3 distinct pain patterns with anchor_keywords."
            )

        # Validate each pain point has required fields (anchor_keywords instead of quotes)
        failing_pain_points = []
        for i, pp in enumerate(result.extracted_pain_points):
            if not pp.title or len(pp.title) < 5:
                return (False, f"Pain point {i+1} missing or too short title")
            if not pp.description or len(pp.description) < 20:
                return (False, f"Pain point '{pp.title}' has missing or too short description")
            if not pp.anchor_keywords or len(pp.anchor_keywords) < 2:
                failing_pain_points.append(
                    f"  - '{pp.title}': {len(pp.anchor_keywords) if pp.anchor_keywords else 0} anchor_keywords (need 2+)"
                )

        if failing_pain_points:
            return (
                False,
                f"Pain points with insufficient anchor_keywords:\n"
                + "\n".join(failing_pain_points)
                + "\n\nFix: Add 2-6 short anchor phrases (2-6 words each) that users say "
                "when discussing this pain point. These will be used for Task 4 vector search."
            )

        logger.info(f"✓ Pain point extraction guardrail passed: {len(result.extracted_pain_points)} pain points")
        # Return task_output.raw for CrewAI to re-parse (guardrails cannot modify output)
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Pain point extraction validation error: {str(e)}")


def validate_pain_point_scoring(task_output) -> tuple[bool, Any]:
    """
    Guardrail for validate_pain_points_task to handle JSON parsing errors.

    CrewAI 1.7.0 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, raw_string) on success.

    Validates:
    - JSON is parseable
    - Has pain_point_scores list
    - Each score has required fields

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Pain point validation returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response (remove XML tags, markdown fencing, etc.)
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ValidationResult.model_validate(raw_json)
                logger.debug("Pain point scoring guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error in pain point scoring: {e}")
                return (
                    False,
                    f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}. "
                    "Ensure valid JSON with no trailing commas and double-quoted strings."
                )
            except Exception as e:
                logger.warning(f"Failed to validate ValidationResult: {e}")
                return (False, f"Failed to parse ValidationResult: {e}")

        if not isinstance(result, ValidationResult):
            return (False, f"Invalid type: expected ValidationResult, got {type(result)}")

        # Validate has scores
        if not result.pain_point_scores or len(result.pain_point_scores) < 1:
            return (False, "Need at least 1 pain_point_score entry")

        # Validate each score has required fields in valid range
        for score in result.pain_point_scores:
            if not score.pain_point_title:
                return (False, "Score entry missing pain_point_title")
            if score.severity_score is None or not (0.0 <= score.severity_score <= 1.0):
                return (
                    False,
                    f"Score for '{score.pain_point_title}' has invalid severity_score {score.severity_score}. "
                    "Must be between 0.0 and 1.0."
                )
            if score.willingness_to_pay is None or not (0.0 <= score.willingness_to_pay <= 1.0):
                return (
                    False,
                    f"Score for '{score.pain_point_title}' has invalid willingness_to_pay {score.willingness_to_pay}. "
                    "Must be between 0.0 and 1.0."
                )

        logger.info(f"✓ Pain point scoring guardrail passed: {len(result.pain_point_scores)} scores")
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Pain point scoring validation error: {str(e)}")


@CrewBase
class PainPointCrew:
    """
    Specialized crew for qualitative pain point analysis.
    Transforms raw social discussions into structured, scored pain points.

    Architecture:
    - 3 agents working in pipeline
    - Researcher categorizes content
    - Analyst extracts pain points
    - Validator scores and validates findings
    """

    agents_config = "config/pain_point_agents.yaml"
    tasks_config = "config/pain_point_tasks.yaml"

    def __init__(self, reddit_posts: list[RedditPost] = None, twitter_threads: list[TwitterThread] = None, niche_description: str = "", market_segments: list[str] = None, industry_boundaries: str = "", job_id: str | None = None):
        """
        Initialize PainPointCrew with social content as knowledge sources.

        Knowledge sources are initialized once and embeddings are cached,
        making this more efficient than passing large content as inputs.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
            niche_description: Description of the niche being analyzed
            market_segments: Key market segments identified in niche validation
            industry_boundaries: Industry boundaries definition for context
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization

        # Store RAW unfiltered posts for Task 4 enrichment (comprehensive vector search)
        # Task 4 needs ALL posts to find quotes, not just the token-budgeted subset
        self._raw_reddit_posts = list(reddit_posts or [])
        self._raw_twitter_threads = list(twitter_threads or [])

        # Apply quality filter BEFORE formatting for knowledge sources
        original_reddit_count = len(reddit_posts or [])
        original_twitter_count = len(twitter_threads or [])

        self.reddit_posts = self._filter_low_quality_reddit(reddit_posts or [])
        self.twitter_threads = self._filter_low_quality_twitter(twitter_threads or [])

        # Log quality filtering results
        if original_reddit_count > len(self.reddit_posts):
            logger.info(
                f"Quality filter: removed {original_reddit_count - len(self.reddit_posts)} "
                f"low-quality Reddit posts ({len(self.reddit_posts)}/{original_reddit_count} remaining)"
            )
        if original_twitter_count > len(self.twitter_threads):
            logger.info(
                f"Quality filter: removed {original_twitter_count - len(self.twitter_threads)} "
                f"low-quality Twitter threads ({len(self.twitter_threads)}/{original_twitter_count} remaining)"
            )

        # Apply token budget filter to keep only top posts by engagement/recency
        if self.reddit_posts:
            from nicheiq.config.settings import settings
            from nicheiq.utils.token_monitor import ContentTokenMonitor

            token_monitor = ContentTokenMonitor()
            self.reddit_posts = token_monitor.filter_posts_to_token_budget(
                self.reddit_posts,
                settings.max_reddit_content_tokens,
                score_fn=ContentTokenMonitor.pain_point_priority_score,
                freshness_reserve_ratio=settings.token_budget_freshness_reserve,
                freshness_days=settings.token_budget_freshness_days,
            )

        self.niche_description = niche_description
        self.market_segments = market_segments or []
        self.industry_boundaries = industry_boundaries
        self.job_id = job_id
        self.knowledge_sources = []

        # Store formatted content for direct injection into Task 1 (categorization)
        # Tasks 2 & 3 use agent-level knowledge sources for RAG-based quote retrieval
        self.formatted_reddit_content = ""
        self.formatted_twitter_content = ""

        # Calculate total discussion volume
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

        # Initialize knowledge sources for agent-level RAG (Tasks 2 & 3 only)
        # Task 1 uses direct injection only (no RAG) - content_researcher has no knowledge_sources
        # Tasks 2 & 3 use agent-level knowledge_sources for RAG-based quote retrieval
        from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

        if self.reddit_posts:
            self.formatted_reddit_content = self._prepare_reddit_content()
            self.reddit_knowledge = StringKnowledgeSource(
                content=self.formatted_reddit_content,
                chunk_size=2000,      # Preserve discussion context
                chunk_overlap=600     # Protect [source: ID] tags at chunk boundaries
            )
            self.knowledge_sources.append(self.reddit_knowledge)
            logger.info(f"Reddit content: {len(self.formatted_reddit_content)} chars, knowledge source created")

        if self.twitter_threads:
            self.formatted_twitter_content = self._prepare_twitter_content()
            self.twitter_knowledge = StringKnowledgeSource(
                content=self.formatted_twitter_content,
                chunk_size=1500,      # Smaller chunks for tweets
                chunk_overlap=400     # Protect [source: ID] tags at chunk boundaries
            )
            self.knowledge_sources.append(self.twitter_knowledge)
            logger.info(f"Twitter content: {len(self.formatted_twitter_content)} chars, knowledge source created")

        # Create enrichment Knowledge for Task 4 using RAW UNFILTERED posts with post_id metadata
        # This ensures Task 4 can search ALL content, not just the token-budgeted subset
        self._enrichment_knowledge = None
        if self._raw_reddit_posts or self._raw_twitter_threads:
            self._setup_enrichment_knowledge(niche_description)

        logger.info(
            f"PainPointCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments) and {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies) - {len(self.knowledge_sources)} knowledge source(s)"
        )

    def _filter_low_quality_reddit(self, posts: list[RedditPost]) -> list[RedditPost]:
        """
        Filter out low-quality Reddit posts before analysis.

        Removes:
        - Posts with very short selftext (<50 chars - likely memes/links)
        - Posts with meme indicators in title
        - Posts with low-quality comment discussions (avg comment length <30 chars)

        Args:
            posts: List of RedditPost objects

        Returns:
            Filtered list of quality posts
        """
        if not posts:
            return []

        quality_posts = []
        meme_indicators = ['meme', 'shitpost', 'lol', 'funny', 'joke', 'humor', 'circlejerk']

        for post in posts:
            # Skip posts with very short selftext (likely memes or link posts)
            if len(post.selftext.strip()) < 50:
                logger.debug(f"Filtered Reddit post (short content): {post.title[:50]}")
                continue

            # Skip if title has meme indicators
            title_lower = post.title.lower()
            if any(indicator in title_lower for indicator in meme_indicators):
                logger.debug(f"Filtered Reddit post (meme indicator): {post.title[:50]}")
                continue

            # Check comment quality - skip if average comment is too short (low-quality discussion)
            if post.comments:
                total_comment_length = sum(len(c.body) for c in post.comments)
                avg_comment_len = total_comment_length / max(len(post.comments), 1)
                if avg_comment_len < 30:  # Average comment < 30 chars
                    logger.debug(f"Filtered Reddit post (low-quality comments): {post.title[:50]}")
                    continue

            quality_posts.append(post)

        return quality_posts

    def _filter_low_quality_twitter(self, threads: list[TwitterThread]) -> list[TwitterThread]:
        """
        Filter out low-quality Twitter threads before analysis.

        Removes:
        - Threads with very short original tweet (<50 chars - likely spam)
        - Threads with low-quality replies (avg reply length <30 chars)

        Args:
            threads: List of TwitterThread objects

        Returns:
            Filtered list of quality threads
        """
        if not threads:
            return []

        quality_threads = []

        for thread in threads:
            # Skip threads with very short original tweet (likely spam/low-effort)
            if len(thread.original_tweet.text.strip()) < 50:
                logger.debug(f"Filtered Twitter thread (short tweet): @{thread.original_tweet.author_username}")
                continue

            # Check reply quality if replies exist
            if thread.replies:
                total_reply_length = sum(len(r.text) for r in thread.replies)
                avg_reply_len = total_reply_length / max(len(thread.replies), 1)
                if avg_reply_len < 30:  # Average reply < 30 chars
                    logger.debug(f"Filtered Twitter thread (low-quality replies): @{thread.original_tweet.author_username}")
                    continue

            quality_threads.append(thread)

        return quality_threads

    def _setup_enrichment_knowledge(self, niche_description: str) -> None:
        """
        Create Knowledge instance for Task 4 quote enrichment using RAW unfiltered posts.

        Uses custom knowledge sources that store post_id in metadata for reliable
        source attribution (instead of relying on [source: ID] tags in text).

        Args:
            niche_description: Niche description for collection naming
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name
        from ..utils.knowledge import RedditKnowledgeSource, TwitterKnowledgeSource

        enrichment_sources = []

        # Create Reddit knowledge source with post_id metadata
        if self._raw_reddit_posts:
            reddit_source = RedditKnowledgeSource(
                posts=self._raw_reddit_posts,
                chunk_size=2000,
                chunk_overlap=600,
            )
            enrichment_sources.append(reddit_source)

        # Create Twitter knowledge source with thread_id metadata
        if self._raw_twitter_threads:
            twitter_source = TwitterKnowledgeSource(
                threads=self._raw_twitter_threads,
                chunk_size=1500,
                chunk_overlap=400,
            )
            enrichment_sources.append(twitter_source)

        if enrichment_sources:
            collection_name = sanitize_collection_name(niche_description, "enrich", self.job_id)
            self._enrichment_knowledge = create_knowledge(
                sources=enrichment_sources,
                embedder_config={
                    "provider": "openai",
                    "config": {"model_name": "text-embedding-3-small"}
                },
                collection_name=collection_name,
            )
            if self._enrichment_knowledge:
                logger.info(
                    f"Task 4 enrichment Knowledge created and indexed: {len(self._raw_reddit_posts)} Reddit posts, "
                    f"{len(self._raw_twitter_threads)} Twitter threads (with post_id metadata)"
                )

    def _format_comments_with_replies(self, comments: list[RedditComment], post_id: str = "unknown", depth: int = 0, max_depth: int = 3) -> str:
        """
        Recursively format comments with their nested replies.

        Comments are sorted by score to prioritize high-engagement content.

        Args:
            comments: List of RedditComment objects
            post_id: Source post ID for tracking attribution
            depth: Current nesting depth (for indentation)
            max_depth: Maximum depth to traverse (default 3 levels)

        Returns:
            Formatted string with comments and nested replies
        """
        if not comments or depth > max_depth:
            return ""

        formatted = []
        indent = "  " * depth  # Indentation for nested comments

        for comment in comments:
            # Include full comment body with source tracking
            formatted.append(
                f"{indent}- [{comment.score} pts] {comment.body} [source: {post_id}]"
            )

            # Include nested replies (up to max_depth)
            if comment.replies and depth < max_depth:
                # Limits tuned for direct injection mode (no RAG)
                reply_limit = 30 if depth == 0 else (15 if depth == 1 else 8)
                # Sort by score (descending) to get most engaging replies first
                sorted_replies = sorted(comment.replies, key=lambda c: c.score, reverse=True)
                nested_content = self._format_comments_with_replies(
                    sorted_replies[:reply_limit],
                    post_id=post_id,
                    depth=depth + 1,
                    max_depth=max_depth
                )
                # Only append if there's actual content
                if nested_content:
                    formatted.append(nested_content)

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _format_twitter_replies(self, replies: list[TwitterTweet], thread_id: str = "unknown") -> str:
        """
        Format Twitter replies with comprehensive content and conversation threading.

        Replies are sorted by engagement to prioritize high-value content.

        Args:
            replies: List of TwitterTweet reply objects
            thread_id: Source thread ID for tracking attribution

        Returns:
            Formatted string with all reply content, grouped by conversation threads
        """
        if not replies:
            return "[No replies]"

        # Build a map of tweet_id -> tweet and parent_id -> children
        tweet_map = {reply.tweet_id: reply for reply in replies}
        children_map = {}
        root_replies = []

        for reply in replies:
            if reply.parent_tweet_id and reply.parent_tweet_id in tweet_map:
                # This is a reply to another reply (nested conversation)
                if reply.parent_tweet_id not in children_map:
                    children_map[reply.parent_tweet_id] = []
                children_map[reply.parent_tweet_id].append(reply)
            else:
                # This is a direct reply to the original tweet
                root_replies.append(reply)

        # Sort root replies by engagement
        root_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

        formatted = []
        # Process all root replies (sorted by engagement)

        for root_reply in root_replies:
            # Include full tweet text with source tracking
            formatted.append(
                f"- @{root_reply.author_username} [{root_reply.likes} likes, {root_reply.retweets} RTs]: {root_reply.text} [source: {thread_id}]"
            )

            # Add nested replies to this conversation (if any)
            if root_reply.tweet_id in children_map:
                nested_replies = children_map[root_reply.tweet_id]
                # Sort nested by engagement
                nested_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

                # Include top 10 nested replies per conversation (tuned for direct injection)
                for nested in nested_replies[:10]:
                    # Include full nested tweet text with source tracking
                    formatted.append(
                        f"  └─ @{nested.author_username} [{nested.likes} likes]: {nested.text} [source: {thread_id}]"
                    )

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _prepare_reddit_content(self) -> str:
        """
        Format Reddit posts with discussions for knowledge source with metadata headers.
        Includes POST_ID for traceability in pain point attribution.

        Posts are interleaved by priority: highest-value posts at the beginning and end
        of the formatted content (where LLM attention is strongest), with lower-value
        posts in the middle. This exploits the U-shaped attention curve in transformer
        models to maximize pain point extraction from the most valuable discussions.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        # Sort posts by pain point priority, then interleave:
        # best at beginning and end, weakest in the middle
        scored = sorted(
            self.reddit_posts,
            key=ContentTokenMonitor.pain_point_priority_score,
            reverse=True,
        )
        front = scored[::2]    # 1st, 3rd, 5th... (odd-ranked by priority)
        back = scored[1::2]    # 2nd, 4th, 6th... (even-ranked)
        ordered_posts = front + list(reversed(back))

        formatted = []
        for post in ordered_posts:
            formatted.append(f"""[PLATFORM: REDDIT]
[POST_ID: {post.post_id}]
[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{post.selftext} [source: {post.post_id}]

---
## Discussion ({len(post.comments)} comments):

{self._format_comments_with_replies(post.comments, post_id=post.post_id)}
""")
        return "\n\n===\n\n".join(formatted)

    def _prepare_twitter_content(self) -> str:
        """
        Format Twitter threads for knowledge source with metadata headers.
        Includes THREAD_ID for traceability in pain point attribution.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for thread in self.twitter_threads:
            formatted.append(f"""[PLATFORM: TWITTER]
[THREAD_ID: {thread.thread_id}]
[AUTHOR: @{thread.original_tweet.author_username}]
[ENGAGEMENT: {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs]
[URL: {thread.original_tweet.url}]

## Original Tweet:

{thread.original_tweet.text} [source: {thread.thread_id}]

---
## Conversation ({len(thread.replies)} replies):

{self._format_twitter_replies(thread.replies, thread_id=thread.thread_id)}
""")
        return "\n\n===\n\n".join(formatted)

    @agent
    def content_researcher(self) -> Agent:
        """
        Agent responsible for reading and categorizing social content.
        Identifies themes, patterns, and user segments.

        Uses dedicated content_analysis_llm with temperature=0 for
        consistent, structured categorization output.
        """
        from langchain_openai import ChatOpenAI
        from ..utils.llm_service import build_llm_kwargs

        return Agent(
            config=self.agents_config["content_researcher"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.content_analysis_llm,
                temperature=0,  # Deterministic for categorization (ignored for reasoning models)
            )),
            verbose=True,
        )

    @agent
    def pain_point_analyst(self) -> Agent:
        """
        Agent responsible for extracting pain points from categorized content.
        Identifies specific problems, frustrations, and unmet needs.

        Uses low-moderate temperature (0.3) for consistent pattern extraction with flexibility.
        Has knowledge_sources attached for RAG-based quote retrieval.
        Uses dedicated pain_point_validation_llm (non-reasoning) to allow max_tokens.
        """
        from langchain_openai import ChatOpenAI
        from ..utils.llm_service import build_llm_kwargs

        from crewai.knowledge.knowledge_config import KnowledgeConfig

        return Agent(
            config=self.agents_config["pain_point_analyst"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.3,  # Low-moderate for consistent pattern extraction
                max_tokens=16000,  # Prevent truncation of large extraction outputs
            )),
            knowledge_config=KnowledgeConfig(results_limit=20),  # More tagged content available
            verbose=True,
        )

    @agent
    def pain_point_validator(self) -> Agent:
        """
        Agent responsible for scoring and validating pain points.
        Assesses severity, willingness to pay, and market potential.

        Uses low temperature (0.2) for objective, consistent scoring.
        Uses crew-level knowledge for RAG-based evidence validation.
        Uses dedicated pain_point_validation_llm (non-reasoning) to allow max_tokens.
        """
        from langchain_openai import ChatOpenAI
        from ..utils.llm_service import build_llm_kwargs

        from crewai.knowledge.knowledge_config import KnowledgeConfig

        return Agent(
            config=self.agents_config["pain_point_validator"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.2,  # Low temperature for consistent scoring
                max_tokens=8192,  # Prevent truncation of large validation outputs
            )),
            knowledge_config=KnowledgeConfig(results_limit=5),  # Evidence validation
            verbose=True,
        )

    @agent
    def quote_enrichment_researcher(self) -> Agent:
        """
        Agent responsible for finding verbatim quotes via vector search (Task 4).

        Uses QuoteSearchTool to search the enrichment knowledge base
        (all raw posts with post_id metadata) and extract quotes with source attribution.

        Uses low temperature (0.1) for consistent, literal quote extraction.
        """
        from langchain_openai import ChatOpenAI

        from ..tools.quote_search_tool import QuoteSearchTool
        from ..utils.llm_service import build_llm_kwargs

        # Create search tool with enrichment knowledge (if available)
        tools = []
        if self._enrichment_knowledge:
            tools.append(QuoteSearchTool(knowledge=self._enrichment_knowledge))
        else:
            logger.warning("quote_enrichment_researcher: No enrichment knowledge available")

        return Agent(
            config=self.agents_config["quote_enrichment_researcher"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.quote_enrichment_llm,
                temperature=0.1,  # Low temperature for literal extraction
                max_tokens=16000,  # Large output for many quotes
            )),
            tools=tools,
            verbose=True,
        )

    @task
    def categorize_content_task(self) -> Task:
        """
        Task: Read and categorize all social content.

        Output: Structured categorization of discussions by theme and user segment.
        Guardrail: Validates 4+ themes with 2+ quotes each, and 3+ user segments.
        """
        return Task(
            config=self.tasks_config["categorize_content"],
            agent=self.content_researcher(),
            output_pydantic=ContentCategorizationReport,
            guardrail=validate_content_categorization,
            guardrail_max_retries=2,
        )

    @task
    def extract_pain_points_task(self) -> Task:
        """
        Task: Extract specific pain points from categorized content.

        Depends on: categorize_content_task
        Output: Structured list of identified pain points with descriptions and quotes (no scores yet).

        Includes guardrail to handle JSON parsing errors and validate output structure.
        """
        return Task(
            config=self.tasks_config["extract_pain_points"],
            agent=self.pain_point_analyst(),
            context=[self.categorize_content_task()],
            output_pydantic=PainPointExtraction,
            guardrail=validate_pain_point_extraction,
            guardrail_max_retries=2,  # Retry up to 2 times on JSON/validation failure
        )

    @task
    def validate_pain_points_task(self) -> Task:
        """
        Task: Score and validate extracted pain points.

        Depends on: extract_pain_points_task
        Output: ValidationResult with severity and WTP scores (scores only, Python will merge).

        Includes guardrail to handle JSON parsing errors and validate score ranges.
        """
        return Task(
            config=self.tasks_config["validate_pain_points"],
            agent=self.pain_point_validator(),
            context=[self.extract_pain_points_task()],
            output_pydantic=ValidationResult,
            guardrail=validate_pain_point_scoring,
            guardrail_max_retries=2,  # Retry up to 2 times on JSON/validation failure
        )

    @task
    def enrich_pain_point_quotes_task(self) -> Task:
        """
        Task 4: Find verbatim quotes for each pain point via vector search.

        Depends on: extract_pain_points_task (uses anchor_keywords)
        Output: QuoteEnrichmentResult with quotes per pain point from vector search.

        The agent uses QuoteSearchTool to search the enrichment knowledge base
        (all raw posts with post_id metadata) and extracts quotes with source attribution.

        NOTE: This task is kept for backward compatibility but is NOT used in the
        main analyze() flow. Instead, _run_parallel_quote_enrichment() is called
        directly after Tasks 1-3 complete.
        """
        return Task(
            config=self.tasks_config["enrich_pain_point_quotes"],
            agent=self.quote_enrichment_researcher(),
            context=[self.extract_pain_points_task()],  # Only Task 2 needed, not Task 3
            output_pydantic=QuoteEnrichmentResult,
            guardrail=validate_quote_enrichment,
            guardrail_max_retries=2,
        )

    def _parse_search_results(self, results: str) -> list[tuple[str, str]]:
        """
        Parse QuoteSearchTool results into (quote, post_id) tuples.

        Args:
            results: Raw string output from QuoteSearchTool._run()

        Returns:
            List of (quote_text, post_id) tuples extracted from results
        """
        parsed = []

        # Pattern: --- Result N (score: X.XX, post_id: abc123, source: reddit) ---
        pattern = r'--- Result \d+ \(score: [\d.]+, post_id: ([^,]+), source: \w+\) ---\n(.*?)(?=--- Result|\Z)'

        for match in re.finditer(pattern, results, re.DOTALL):
            post_id = match.group(1).strip()
            content = match.group(2).strip()

            # Extract sentences as potential quotes (15+ words)
            sentences = re.split(r'(?<=[.!?])\s+', content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence.split()) >= 15:
                    parsed.append((sentence, post_id))

        return parsed

    def _enrich_single_pain_point(
        self,
        pain_point: UnvalidatedPainPoint,
        search_tool: "QuoteSearchTool",
    ) -> SinglePainPointQuotesResult:
        """
        Search for quotes supporting a single pain point.

        Designed to run in parallel via ThreadPoolExecutor.
        Each pain point is processed independently, so the LLM can't skip any.

        Args:
            pain_point: The pain point to find quotes for
            search_tool: QuoteSearchTool instance for vector search

        Returns:
            SinglePainPointQuotesResult with quotes found for this pain point
        """
        all_quotes: list[ExtractedQuote] = []
        seen_quote_texts: set[str] = set()

        # Limit to 4 keywords to avoid excessive API calls
        keywords_to_search = pain_point.anchor_keywords[:4]

        for keyword in keywords_to_search:
            try:
                results = search_tool._run(keyword)
                parsed_quotes = self._parse_search_results(results)

                for quote_text, post_id in parsed_quotes:
                    normalized = quote_text.lower().strip()
                    # Deduplicate and filter short quotes
                    if normalized not in seen_quote_texts and len(quote_text.split()) >= 15:
                        seen_quote_texts.add(normalized)
                        all_quotes.append(ExtractedQuote(
                            quote_text=quote_text,
                            post_id=post_id,
                        ))
            except Exception as e:
                logger.warning(f"Search failed for keyword '{keyword}': {e}")

        return SinglePainPointQuotesResult(
            pain_point_title=pain_point.title,
            anchor_keywords_searched=keywords_to_search,
            quotes=all_quotes[:12],  # Cap at 12 quotes per pain point
            search_summary=f"Searched {len(keywords_to_search)} keywords, found {len(all_quotes)} quotes"
        )

    def _run_parallel_quote_enrichment(
        self,
        extracted_pain_points: list[UnvalidatedPainPoint],
    ) -> QuoteEnrichmentResult:
        """
        Run quote enrichment in parallel for all pain points.

        Uses ThreadPoolExecutor - each pain point is processed independently.
        This guarantees 100% coverage (every pain point gets searched) because
        the LLM can't skip any when they're processed in separate threads.

        Args:
            extracted_pain_points: Pain points from Task 2 with anchor_keywords

        Returns:
            QuoteEnrichmentResult aggregating all parallel search results
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from ..tools.quote_search_tool import QuoteSearchTool

        if not self._enrichment_knowledge:
            logger.warning("No enrichment knowledge available, skipping parallel enrichment")
            return QuoteEnrichmentResult(
                niche=self.niche_description,
                enriched_pain_points=[],
                total_quotes_found=0,
                enrichment_summary="No content available for quote search"
            )

        # Handle empty pain points list
        if not extracted_pain_points:
            logger.info("No pain points to enrich, returning empty result")
            return QuoteEnrichmentResult(
                niche=self.niche_description,
                enriched_pain_points=[],
                total_quotes_found=0,
                enrichment_summary="No pain points to enrich"
            )

        # Create search tool (thread-safe for read-only queries)
        search_tool = QuoteSearchTool(knowledge=self._enrichment_knowledge)

        enriched_results: list[EnrichedPainPointQuotes] = []
        max_workers = min(4, len(extracted_pain_points))

        logger.info(
            f"Starting parallel quote enrichment for {len(extracted_pain_points)} pain points "
            f"(max_workers={max_workers})"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all enrichment tasks
            future_to_pp = {
                executor.submit(self._enrich_single_pain_point, pp, search_tool): pp
                for pp in extracted_pain_points
            }

            # Collect results as they complete
            for future in as_completed(future_to_pp):
                pp = future_to_pp[future]
                try:
                    result = future.result()
                    enriched_results.append(EnrichedPainPointQuotes(
                        pain_point_title=result.pain_point_title,
                        quotes=result.quotes,
                    ))
                    logger.info(f"[OK] Enriched '{pp.title[:40]}': {len(result.quotes)} quotes")
                except Exception as e:
                    logger.error(f"Failed to enrich '{pp.title}': {e}")
                    # Add empty result to maintain 1:1 mapping
                    enriched_results.append(EnrichedPainPointQuotes(
                        pain_point_title=pp.title,
                        quotes=[],
                    ))

        total_quotes = sum(len(e.quotes) for e in enriched_results)

        return QuoteEnrichmentResult(
            niche=self.niche_description,
            enriched_pain_points=enriched_results,
            total_quotes_found=total_quotes,
            enrichment_summary=f"Parallel enrichment: {total_quotes} quotes for {len(enriched_results)} pain points"
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the PainPointCrew with all agents and tasks.

        NOTE: This method includes all 4 tasks for backward compatibility,
        but the main analyze() flow uses a 2-phase approach:
        - Phase 1: Tasks 1-3 via CrewAI (explicit Crew construction)
        - Phase 2: Parallel quote enrichment via Python ThreadPoolExecutor

        Architecture:
        - Task 1 (content_researcher): NO RAG - uses direct injection only
        - Tasks 2 & 3 (pain_point_analyst, pain_point_validator): HAVE RAG via crew-level knowledge
        - Task 4 (quote_enrichment_researcher): Uses QuoteSearchTool (not used in analyze())

        Returns:
            Configured Crew instance with all 4 tasks
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {
                "model_name": "text-embedding-3-small"  # Cost-effective embeddings
            }
        }

        # Create crew-level Knowledge for job-isolated RAG
        knowledge = None
        if self.knowledge_sources:
            collection_name = sanitize_collection_name(self.niche_description, "pain", self.job_id)
            logger.info(f"Creating pain point knowledge with collection: {collection_name}")
            knowledge = create_knowledge(
                sources=self.knowledge_sources,
                embedder_config=embedder_config,
                collection_name=collection_name,
            )
            self._crew_knowledge = knowledge  # Store for cleanup

        has_enrichment = self._enrichment_knowledge is not None
        logger.info(
            f"PainPointCrew using crew-level knowledge: "
            f"collection={getattr(knowledge, '_collection_name', 'none') if knowledge else 'none'}, "
            f"sources={len(self.knowledge_sources)}, "
            f"quote_enrichment=parallel Python (enrichment_knowledge={has_enrichment})"
        )

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            knowledge=knowledge,
            verbose=True,
            process_type="sequential",  # Tasks run in order
            embedder=embedder_config,
        )

    def _extract_and_clean_sources(self, pain_points: list[UnvalidatedPainPoint]) -> list[UnvalidatedPainPoint]:
        """
        Extract source_post_ids from [source: ID] suffixes in quotes and clean quote text.

        This implements CrewAI's recommended approach for source tracking:
        embed source metadata within chunk content itself, then extract post-processing.

        IMPORTANT: This method modifies pain_points in-place (Pydantic models are mutable).
        Side effects:
        - Updates pp.source_post_ids with extracted IDs
        - Updates pp.representative_quotes with cleaned text (no [source: ID] suffixes)

        Args:
            pain_points: List of UnvalidatedPainPoint objects with quotes containing [source: ID]

        Returns:
            List of pain points with source_post_ids populated and quotes cleaned (same list, modified)
        """
        import re

        logger.info(f"[Stage 6] Extracting source IDs from {len(pain_points)} pain points...")

        for pp in pain_points:
            quote_source_ids: list[str] = []  # Parallel with cleaned_quotes
            cleaned_quotes = []

            for quote in pp.representative_quotes:
                # Extract all [source: ID] patterns using module-level pattern constant
                all_matches = re.findall(rf'\[source: ({SOURCE_TAG_PATTERN})\]', quote)
                if len(all_matches) > 1:
                    logger.warning(
                        f"Quote has {len(all_matches)} source tags, using first: "
                        f"'{quote[:50]}...'"
                    )
                if all_matches:
                    quote_source_ids.append(all_matches[0])
                    # Remove [source: ID] suffix from quote text
                    cleaned_quote = re.sub(rf'\s*\[source: {SOURCE_TAG_PATTERN}\]', '', quote).strip()
                    cleaned_quotes.append(cleaned_quote)
                else:
                    # Empty string = unknown source, preserves parallel alignment
                    quote_source_ids.append("")
                    logger.debug(
                        f"Quote missing [source: ID] suffix in '{pp.title[:30]}...': "
                        f"'{quote[:50]}...'"
                    )
                    cleaned_quotes.append(quote)

            # Update pain point: parallel array (may have duplicates and empty strings)
            pp.source_post_ids = quote_source_ids
            pp.representative_quotes = cleaned_quotes

            # Bound mention_count using unique non-empty source IDs as a floor
            unique_sources = {sid for sid in quote_source_ids if sid}
            if unique_sources:
                source_count = len(unique_sources)
                if pp.mention_count < source_count:
                    pp.mention_count = source_count
                elif pp.mention_count > source_count * 10:
                    logger.warning(
                        f"Pain point '{pp.title[:40]}': mention_count {pp.mention_count} "
                        f"vs {source_count} sources, capping at {source_count * 10}"
                    )
                    pp.mention_count = source_count * 10

            # Log extraction results for this pain point
            if unique_sources:
                logger.info(
                    f"[Stage 6] '{pp.title[:50]}...': Extracted {len(unique_sources)} unique source ID(s) "
                    f"from {len(pp.representative_quotes)} quote(s)"
                )
            else:
                logger.warning(
                    f"[Stage 6] '{pp.title[:50]}...': No source IDs found in {len(pp.representative_quotes)} quote(s)"
                )

        return pain_points

    def analyze(self) -> PainPointAnalysisResult:
        """
        Execute pain point analysis workflow using knowledge sources.

        Knowledge sources handle all social media content via semantic search.
        Inputs contain only metadata needed for the crew.

        Returns:
            PainPointAnalysisResult with validated pain points
        """
        logger.info("Starting pain point analysis...")

        if not self.reddit_posts and not self.twitter_threads:
            logger.warning("No social content provided for analysis")
            return PainPointAnalysisResult(
                niche="",
                pain_points=[],
                total_mentions=0,
                top_categories=[],
                analysis_summary="No content available for analysis"
            )

        try:
            # Calculate total discussion volume (metadata only)
            total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
            total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

            # Log initialization
            logger.info(
                f"Hybrid mode (Task 1: direct injection, Tasks 2-3: agent-level RAG): "
                f"{len(self.reddit_posts)} Reddit posts ({total_reddit_comments} comments), "
                f"{len(self.twitter_threads)} Twitter threads ({total_twitter_replies} replies), "
                f"{len(self.knowledge_sources)} knowledge source(s) for agents"
            )

            # ANTI-HALLUCINATION CHECK: Verify sufficient content volume
            total_discussions = len(self.reddit_posts) + len(self.twitter_threads)
            total_engagement = total_reddit_comments + total_twitter_replies

            if total_discussions < 3:
                logger.warning(
                    f"Insufficient discussion volume ({total_discussions} discussions, minimum 3 required) "
                    f"- pain point analysis may produce low-quality results or hallucinations"
                )
                return PainPointAnalysisResult(
                    niche=self.niche_description,
                    pain_points=[],
                    total_mentions=0,
                    top_categories=[],
                    analysis_summary=f"Insufficient discussion data for analysis: only {total_discussions} discussions found. Minimum 3 substantive discussions required."
                )

            if total_engagement < 5:
                logger.warning(
                    f"Low engagement volume ({total_engagement} comments/replies total) "
                    f"- pain point extraction may be limited due to sparse discussion content"
                )

            # Execute crew in hybrid mode:
            # - Task 1: Full content via direct injection (categorization)
            # - Tasks 2 & 3: RAG via knowledge sources (quote retrieval)
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access

            # Token monitoring: Log content size and check context limits
            monitor = ContentTokenMonitor()
            content_tokens = monitor.count_tokens(
                self.formatted_reddit_content + self.formatted_twitter_content,
                model=settings.content_analysis_llm
            )

            # Use configured limit, with safe maximum cap
            max_content_tokens = min(settings.max_reddit_content_tokens, 500_000)

            # Iteratively remove lowest quality posts until content fits
            original_post_count = len(self.reddit_posts)
            reduction_iterations = 0
            max_iterations = 10  # Safety limit to prevent infinite loop

            while content_tokens > max_content_tokens and len(self.reddit_posts) > 1 and reduction_iterations < max_iterations:
                reduction_iterations += 1

                # Sort posts by pain point priority score (lowest first)
                sorted_posts = sorted(
                    self.reddit_posts,
                    key=ContentTokenMonitor.pain_point_priority_score,
                    reverse=False  # Lowest score first
                )

                # Remove bottom 20% of posts (at least 1)
                remove_count = max(1, len(sorted_posts) // 5)
                self.reddit_posts = sorted_posts[remove_count:]  # Keep the higher quality posts

                logger.info(
                    f"[Stage 6] Auto-reduction iteration {reduction_iterations}: "
                    f"removed {remove_count} lowest-quality posts, {len(self.reddit_posts)} remaining"
                )

                # Regenerate formatted content with reduced posts
                self.formatted_reddit_content = self._prepare_reddit_content()

                # Recalculate tokens after reduction
                content_tokens = monitor.count_tokens(
                    self.formatted_reddit_content + self.formatted_twitter_content,
                    model=settings.content_analysis_llm
                )

            if reduction_iterations > 0:
                logger.info(
                    f"[Stage 6] Auto-reduction complete: {original_post_count} → {len(self.reddit_posts)} posts "
                    f"({reduction_iterations} iterations), now {content_tokens:,} tokens"
                )

            if content_tokens > max_content_tokens:
                logger.warning(
                    f"[Stage 6] Content still exceeds limit after {reduction_iterations} iterations. "
                    f"Proceeding with {content_tokens:,} tokens (limit: {max_content_tokens:,})"
                )
            else:
                logger.info(f"[Stage 6] Content size: {content_tokens:,} tokens (limit: {max_content_tokens:,})")

            if settings.token_monitoring_enabled:
                # Detailed token breakdown
                reddit_tokens = monitor.log_content_stats(
                    content=self.formatted_reddit_content,
                    label="Stage 6 - Reddit content",
                    model=settings.content_analysis_llm
                )

                twitter_tokens = monitor.log_content_stats(
                    content=self.formatted_twitter_content,
                    label="Stage 6 - Twitter content",
                    model=settings.content_analysis_llm
                )

                # Combined token check
                total_tokens = reddit_tokens + twitter_tokens
                monitor.check_soft_cap(
                    tokens=total_tokens,
                    label="Stage 6 - Total content (Reddit + Twitter)",
                    model=settings.content_analysis_llm
                )

            # Format market segments for task context
            market_segments_formatted = "\n".join([f"- {seg}" for seg in self.market_segments]) if self.market_segments else "Not specified"

            # Extract research metadata
            subreddits = list(set(post.subreddit for post in self.reddit_posts if post.subreddit))
            subreddits_formatted = ", ".join(sorted(subreddits)) if subreddits else "N/A"

            # Get collection timestamp from first post (all collected at same time)
            collection_timestamp = "Not available"
            if self.reddit_posts and hasattr(self.reddit_posts[0], 'created_utc'):
                from datetime import datetime
                collection_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            # Two-phase execution:
            # - Phase 1: Tasks 1-3 via CrewAI (categorize, extract, validate)
            # - Phase 2: Python-driven parallel quote enrichment (replaces Task 4)
            #
            # Phase 2 uses ThreadPoolExecutor to search quotes for each pain point
            # independently, guaranteeing 100% coverage (LLM can't skip any).

            # Compute discussion quality stats for Task 3
            comment_counts = [
                len(p.comments) if p.comments else 0
                for p in self.reddit_posts
            ]
            avg_comments_per_post = (
                f"{sum(comment_counts) / len(comment_counts):.1f}"
                if comment_counts else "0.0"
            )
            rich_discussion_count = sum(1 for c in comment_counts if c >= 20)

            # Phase 1: Create crew with Tasks 1-3 only (exclude Task 4)
            embedder_config = {
                "provider": "openai",
                "config": {
                    "model_name": "text-embedding-3-small"
                }
            }

            phase1_crew = Crew(
                agents=[
                    self.content_researcher(),
                    self.pain_point_analyst(),
                    self.pain_point_validator(),
                ],
                tasks=[
                    self.categorize_content_task(),
                    self.extract_pain_points_task(),
                    self.validate_pain_points_task(),
                    # Task 4 removed - enrichment done via parallel Python
                ],
                verbose=True,
                process_type="sequential",
                embedder=embedder_config,
            )
            self._last_crew = phase1_crew  # Store for usage_metrics access

            logger.info(
                f"Phase 1: Running Tasks 1-3 (categorize, extract, validate) - "
                f"Task 4 (quote enrichment) will run as parallel Python"
            )

            try:
                crew_output = phase1_crew.kickoff(inputs={
                    "niche_description": self.niche_description,
                    "market_segments": market_segments_formatted,
                    "industry_boundaries": self.industry_boundaries or "Not specified",
                    "full_reddit_content": self.formatted_reddit_content,
                    "full_twitter_content": self.formatted_twitter_content,
                    "reddit_posts_count": len(self.reddit_posts),
                    "twitter_threads_count": len(self.twitter_threads),
                    "total_reddit_comments": total_reddit_comments,
                    "total_twitter_replies": total_twitter_replies,
                    "total_content": len(self.reddit_posts) + len(self.twitter_threads),
                    "subreddits": subreddits_formatted,
                    "collection_timestamp": collection_timestamp,
                    "avg_comments_per_post": avg_comments_per_post,
                    "rich_discussion_count": rich_discussion_count,
                })
            except Exception as e:
                error_msg = str(e)
                # Check if this is a guardrail validation failure
                if "guardrail validation" in error_msg.lower() or "representative_quotes" in error_msg:
                    logger.warning(
                        f"[Stage 6] Guardrail validation failed after retries: {error_msg[:200]}. "
                        "Returning empty result for quality gate evaluation."
                    )
                    return PainPointAnalysisResult(
                        niche=self.niche_description,
                        pain_points=[],
                        total_mentions=0,
                        top_categories=[],
                        analysis_summary=f"Pain point extraction failed guardrail validation: {error_msg[:300]}. "
                                       "The source content may lack sufficient quotes to support identified themes."
                    )
                # Re-raise other exceptions
                raise

            # Parse Phase 1 outputs (Tasks 1-3)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if len(task_outputs) < 3:
                logger.error(f"Expected 3 task outputs from Phase 1, got {len(task_outputs)}")
                raise ValueError("Incomplete task execution in pain point crew Phase 1")

            # Helper to parse pydantic from raw when guardrails set pydantic=None
            def _parse_output(task_output, model_class, task_name: str):
                """Parse pydantic from raw if needed (guardrail compatibility)."""
                if task_output.pydantic is not None:
                    return task_output.pydantic
                if not hasattr(task_output, 'raw') or not task_output.raw:
                    raise ValueError(f"{task_name}: No pydantic or raw output available")
                try:
                    # Clean LLM response (remove XML tags, markdown fencing, etc.)
                    cleaned_raw = clean_llm_response(task_output.raw)
                    raw_json = json.loads(cleaned_raw)
                    result = model_class.model_validate(raw_json)
                    logger.debug(f"{task_name}: Parsed {model_class.__name__} from .raw")
                    return result
                except Exception as e:
                    raise ValueError(f"{task_name}: Failed to parse {model_class.__name__} from .raw: {e}")

            categorization_output = _parse_output(task_outputs[0], ContentCategorizationReport, "Task 1")
            extraction_output = _parse_output(task_outputs[1], PainPointExtraction, "Task 2")
            validation_output = _parse_output(task_outputs[2], ValidationResult, "Task 3")

            logger.info(f"Phase 1 complete: Task 2 extracted {len(extraction_output.extracted_pain_points)} pain points")

            # Phase 2: Parallel quote enrichment (Python-driven, not LLM)
            logger.info("Phase 2: Starting parallel quote enrichment...")
            enrichment_output = self._run_parallel_quote_enrichment(
                extraction_output.extracted_pain_points
            )

            # Log quote enrichment stats
            total_pain_points = len(extraction_output.extracted_pain_points)
            total_enriched_quotes = enrichment_output.total_quotes_found
            logger.info(
                f"Phase 2 complete: {total_enriched_quotes} quotes found "
                f"for {len(enrichment_output.enriched_pain_points)} pain points"
            )

            logger.info(
                f"Python merge: Combining {len(extraction_output.extracted_pain_points)} extracted pain points "
                f"with {len(validation_output.pain_point_scores)} validation scores "
                f"and {len(enrichment_output.enriched_pain_points)} quote enrichments"
            )

            # Merge Task 2 (extraction with anchor_keywords) + Task 3 (validation scores) + Task 4 (quotes) → final PainPoint
            final_pain_points = []
            unmatched_scores = []
            unmatched_quotes = []

            for unvalidated in extraction_output.extracted_pain_points:
                # Find matching score by title (using fuzzy matching)
                matching_score, score_match_ratio = fuzzy_find_matching_score(
                    unvalidated.title,
                    validation_output.pain_point_scores
                )

                if not matching_score:
                    logger.warning(
                        f"No validation score found for pain point: '{unvalidated.title}' "
                        f"(best match similarity: {score_match_ratio:.2%}, threshold: {FUZZY_MATCH_THRESHOLD:.0%}) - skipping"
                    )
                    unmatched_scores.append(unvalidated.title)
                    continue

                # Log fuzzy match details if not exact
                if score_match_ratio < 1.0:
                    logger.debug(
                        f"Fuzzy matched score: '{unvalidated.title}' → '{matching_score.pain_point_title}' "
                        f"(similarity: {score_match_ratio:.2%})"
                    )

                # Find matching quotes from Task 4 (using fuzzy matching)
                quotes = []
                source_ids = []
                matching_enrichment = None
                best_quote_ratio = 0.0

                for enriched in enrichment_output.enriched_pain_points:
                    ratio = SequenceMatcher(
                        None,
                        unvalidated.title.lower().strip(),
                        enriched.pain_point_title.lower().strip()
                    ).ratio()
                    if ratio > best_quote_ratio:
                        best_quote_ratio = ratio
                        if ratio >= FUZZY_MATCH_THRESHOLD:
                            matching_enrichment = enriched

                if matching_enrichment:
                    # Extract quotes and source IDs from Task 4 output
                    for eq in matching_enrichment.quotes:
                        quotes.append(eq.quote_text)
                        source_ids.append(eq.post_id)
                    if best_quote_ratio < 1.0:
                        logger.debug(
                            f"Fuzzy matched quotes: '{unvalidated.title}' → '{matching_enrichment.pain_point_title}' "
                            f"(similarity: {best_quote_ratio:.2%})"
                        )
                else:
                    logger.warning(
                        f"No Task 4 quotes found for pain point: '{unvalidated.title}' "
                        f"(best match similarity: {best_quote_ratio:.2%})"
                    )
                    unmatched_quotes.append(unvalidated.title)

                # Build final PainPoint with quotes from Task 4 and scores from Task 3
                # Note: UnvalidatedPainPoint has anchor_keywords, not representative_quotes/source_post_ids
                final_pain_points.append(PainPoint(
                    title=unvalidated.title,
                    description=unvalidated.description,
                    mention_count=unvalidated.mention_count,
                    representative_quotes=quotes,  # From Task 4
                    source_post_ids=source_ids,     # From Task 4
                    source_platforms=unvalidated.source_platforms,
                    categories=unvalidated.categories,
                    severity_score=matching_score.severity_score,
                    willingness_to_pay=matching_score.willingness_to_pay,
                    opportunity_level=matching_score.opportunity_level,
                ))

            # Validate merge completeness
            if len(final_pain_points) != len(extraction_output.extracted_pain_points):
                logger.warning(
                    f"Merge incomplete: {len(final_pain_points)}/{len(extraction_output.extracted_pain_points)} "
                    f"pain points merged. Unmatched scores: {unmatched_scores}"
                )
            if unmatched_quotes:
                logger.warning(f"Pain points without Task 4 quotes: {unmatched_quotes}")

            # Log quote coverage stats
            pain_points_with_quotes = sum(1 for pp in final_pain_points if pp.representative_quotes)
            total_final_quotes = sum(len(pp.representative_quotes) for pp in final_pain_points)
            quote_coverage_pct = (pain_points_with_quotes / len(final_pain_points) * 100) if final_pain_points else 0
            logger.info(
                f"Quote coverage: {pain_points_with_quotes}/{len(final_pain_points)} pain points have quotes "
                f"({quote_coverage_pct:.1f}% coverage, {total_final_quotes} total quotes)"
            )

            # Create final result
            result = PainPointAnalysisResult(
                niche=extraction_output.niche,
                pain_points=final_pain_points,
                total_mentions=sum(pp.mention_count for pp in final_pain_points),
                top_categories=list(set(
                    cat
                    for pp in final_pain_points
                    if pp.categories
                    for cat in pp.categories
                ))[:10],  # Top 10 unique categories
                analysis_summary=validation_output.validation_summary,
                content_categorization=categorization_output,  # From Task 1
            )

            logger.info(
                f"[OK] Python merge complete: {len(result.pain_points)} validated pain points, "
                f"{len(result.top_categories)} categories"
            )

            # Verify results contain actual content from knowledge sources (sampling check)
            if result.pain_points:
                logger.debug("=" * 80)
                logger.debug("KNOWLEDGE USAGE VERIFICATION (Sample Check)")
                logger.debug("=" * 80)
                logger.debug(f"Extracted {len(result.pain_points)} pain points")
                logger.debug(f"Total representative quotes: {sum(len(pp.representative_quotes) for pp in result.pain_points)}")

                # Sample check: do quotes look like real Reddit content?
                if result.pain_points[0].representative_quotes:
                    sample_quote = result.pain_points[0].representative_quotes[0][:150]
                    logger.debug(f"Sample quote: '{sample_quote}...'")
                logger.debug("=" * 80)
            logger.info(
                f"Pain point analysis complete: "
                f"{len(result.pain_points)} pain points identified, "
                f"{len(result.top_categories)} categories"
            )
            return result

        except Exception as e:
            logger.error(f"Pain point analysis failed: {e}")
            raise

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens or None if not available
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
