"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

from difflib import SequenceMatcher
from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import (
    ContentCategorizationReport,
    PainPoint,
    PainPointAnalysisResult,
    PainPointExtraction,
    UnvalidatedPainPoint,
    ValidationResult,
)
from ..models.social_content import RedditComment, RedditPost, TwitterThread, TwitterTweet
from ..utils.token_monitor import ContentTokenMonitor

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

    def __init__(self, reddit_posts: list[RedditPost] = None, twitter_threads: list[TwitterThread] = None, niche_description: str = "", market_segments: list[str] = None, industry_boundaries: str = ""):
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
                settings.max_reddit_content_tokens
            )

        self.niche_description = niche_description
        self.market_segments = market_segments or []
        self.industry_boundaries = industry_boundaries
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
                chunk_overlap=300     # More overlap for conversational threading
            )
            self.knowledge_sources.append(self.reddit_knowledge)
            logger.info(f"Reddit content: {len(self.formatted_reddit_content)} chars, knowledge source created")

        if self.twitter_threads:
            self.formatted_twitter_content = self._prepare_twitter_content()
            self.twitter_knowledge = StringKnowledgeSource(
                content=self.formatted_twitter_content,
                chunk_size=1500,      # Smaller chunks for tweets
                chunk_overlap=200     # Less overlap needed
            )
            self.knowledge_sources.append(self.twitter_knowledge)
            logger.info(f"Twitter content: {len(self.formatted_twitter_content)} chars, knowledge source created")

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

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for post in self.reddit_posts:
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

        return Agent(
            config=self.agents_config["pain_point_analyst"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.3,  # Low-moderate for consistent pattern extraction
                max_tokens=16000,  # Prevent truncation of large extraction outputs
            )),
            knowledge_sources=self.knowledge_sources,  # RAG for quote retrieval
            verbose=True,
        )

    @agent
    def pain_point_validator(self) -> Agent:
        """
        Agent responsible for scoring and validating pain points.
        Assesses severity, willingness to pay, and market potential.

        Uses low temperature (0.2) for objective, consistent scoring.
        Has knowledge_sources attached for RAG-based evidence validation.
        Uses dedicated pain_point_validation_llm (non-reasoning) to allow max_tokens.
        """
        from langchain_openai import ChatOpenAI
        from ..utils.llm_service import build_llm_kwargs

        return Agent(
            config=self.agents_config["pain_point_validator"],
            llm=ChatOpenAI(**build_llm_kwargs(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.2,  # Low temperature for consistent scoring
                max_tokens=8192,  # Prevent truncation of large validation outputs
            )),
            knowledge_sources=self.knowledge_sources,  # RAG for evidence validation
            verbose=True,
        )

    @task
    def categorize_content_task(self) -> Task:
        """
        Task: Read and categorize all social content.

        Output: Structured categorization of discussions by theme and user segment.
        """
        return Task(
            config=self.tasks_config["categorize_content"],
            agent=self.content_researcher(),
            output_pydantic=ContentCategorizationReport,
        )

    @task
    def extract_pain_points_task(self) -> Task:
        """
        Task: Extract specific pain points from categorized content.

        Depends on: categorize_content_task
        Output: Structured list of identified pain points with descriptions and quotes (no scores yet).
        """
        return Task(
            config=self.tasks_config["extract_pain_points"],
            agent=self.pain_point_analyst(),
            context=[self.categorize_content_task()],
            output_pydantic=PainPointExtraction,
        )

    @task
    def validate_pain_points_task(self) -> Task:
        """
        Task: Score and validate extracted pain points.

        Depends on: extract_pain_points_task
        Output: ValidationResult with severity and WTP scores (scores only, Python will merge).
        """
        return Task(
            config=self.tasks_config["validate_pain_points"],
            agent=self.pain_point_validator(),
            context=[self.extract_pain_points_task()],
            output_pydantic=ValidationResult,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the PainPointCrew with all agents, tasks, and knowledge sources.

        Architecture:
        - Task 1 (content_researcher): NO RAG - uses direct injection only
        - Tasks 2 & 3 (pain_point_analyst, pain_point_validator): HAVE RAG via agent-level knowledge_sources

        Returns:
            Configured Crew instance (knowledge is agent-level, not crew-level)
        """
        embedder_config = {
            "provider": "openai",
            "config": {
                "model_name": "text-embedding-3-small"  # Cost-effective embeddings
            }
        }

        # Note: Knowledge sources are attached at agent level (pain_point_analyst, pain_point_validator)
        # Task 1's agent (content_researcher) has NO knowledge_sources - uses direct injection only
        logger.info(
            f"PainPointCrew using agent-level knowledge: "
            f"content_researcher=NO RAG, pain_point_analyst=RAG ({len(self.knowledge_sources)} sources), "
            f"pain_point_validator=RAG ({len(self.knowledge_sources)} sources)"
        )

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            process_type="sequential",  # Tasks run in order
            embedder=embedder_config  # Shared embedder config for agent-level knowledge
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
            sources = set()
            cleaned_quotes = []

            for quote in pp.representative_quotes:
                # Extract [source: ID] pattern using module-level pattern constant
                match = re.search(rf'\[source: ({SOURCE_TAG_PATTERN})\]', quote)
                if match:
                    sources.add(match.group(1))
                    # Remove [source: ID] suffix from quote text
                    cleaned_quote = re.sub(rf'\s*\[source: {SOURCE_TAG_PATTERN}\]', '', quote).strip()
                    cleaned_quotes.append(cleaned_quote)
                else:
                    # Log missing source tag for debugging
                    logger.debug(
                        f"Quote missing [source: ID] suffix in '{pp.title[:30]}...': "
                        f"'{quote[:50]}...'"
                    )
                    cleaned_quotes.append(quote)

            # Update pain point with extracted sources and cleaned quotes
            pp.source_post_ids = list(sources)
            pp.representative_quotes = cleaned_quotes

            # Recalculate mention_count from actual unique sources
            # LLM often confuses mention_count with quote count (always ~3)
            # Actual mention count = number of unique source posts
            if sources:
                pp.mention_count = len(sources)

            # Log extraction results for this pain point
            if sources:
                logger.info(
                    f"[Stage 6] '{pp.title[:50]}...': Extracted {len(sources)} source ID(s) "
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

            # Context limit check: ~1M tokens available, leave 400K for scaffolding + agent overhead
            max_content_tokens = 600_000
            if content_tokens > max_content_tokens:
                logger.warning(
                    f"[Stage 6] Content tokens ({content_tokens:,}) exceed safe limit ({max_content_tokens:,}). "
                    f"Consider reducing posts or comment depth. Proceeding anyway..."
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

            # Hybrid approach:
            # - Task 1 (content_researcher): full content via direct injection (NO RAG)
            # - Tasks 2 & 3 (pain_point_analyst, pain_point_validator): agent-level RAG for quote retrieval
            crew_output = crew_instance.kickoff(inputs={
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
            })

            # Python merge: Extract all task outputs and merge Task 2 + Task 3
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if len(task_outputs) < 3:
                logger.error(f"Expected 3 task outputs, got {len(task_outputs)}")
                raise ValueError("Incomplete task execution in pain point crew")

            categorization_output = task_outputs[0].pydantic  # Task 1: ContentCategorizationReport
            extraction_output = task_outputs[1].pydantic      # Task 2: PainPointExtraction
            validation_output = task_outputs[2].pydantic      # Task 3: ValidationResult

            # Extract source IDs from [source: ID] suffixes and clean quotes
            extraction_output.extracted_pain_points = self._extract_and_clean_sources(
                extraction_output.extracted_pain_points
            )

            # Calculate and log aggregate source tracking stats
            pain_points_with_sources = sum(
                1 for pp in extraction_output.extracted_pain_points
                if pp.source_post_ids and len(pp.source_post_ids) > 0
            )
            total_pain_points = len(extraction_output.extracted_pain_points)
            total_quotes = sum(len(pp.representative_quotes) for pp in extraction_output.extracted_pain_points)
            coverage_pct = (pain_points_with_sources / total_pain_points * 100) if total_pain_points > 0 else 0

            logger.info(
                f"Source tracking: Extracted source IDs from {pain_points_with_sources}/{total_pain_points} "
                f"pain points ({coverage_pct:.1f}% coverage, {total_quotes} total quotes)"
            )

            # Warn if source coverage is low (< 80%)
            if coverage_pct < 80:
                logger.warning(
                    f"Low source attribution coverage: Only {pain_points_with_sources}/{total_pain_points} "
                    f"pain points ({coverage_pct:.1f}%) have source IDs. Expected >80% coverage."
                )

            logger.info(
                f"Python merge: Combining {len(extraction_output.extracted_pain_points)} extracted pain points "
                f"with {len(validation_output.pain_point_scores)} validation scores"
            )

            # Merge Task 2 (extraction) + Task 3 (validation) → final PainPointAnalysisResult
            final_pain_points = []
            unmatched_scores = []

            for unvalidated in extraction_output.extracted_pain_points:
                # Find matching score by title (using fuzzy matching)
                matching_score, match_ratio = fuzzy_find_matching_score(
                    unvalidated.title,
                    validation_output.pain_point_scores
                )

                if matching_score:
                    # Log fuzzy match details if not exact
                    if match_ratio < 1.0:
                        logger.debug(
                            f"Fuzzy matched '{unvalidated.title}' → '{matching_score.pain_point_title}' "
                            f"(similarity: {match_ratio:.2%})"
                        )

                    # Merge unvalidated pain point + validation scores
                    # Safety check: Warn if spreading would overwrite fields with explicit kwargs
                    # This catches future schema changes where UnvalidatedPainPoint adds score fields
                    unvalidated_fields = set(unvalidated.model_dump().keys())
                    explicit_fields = {'severity_score', 'willingness_to_pay', 'opportunity_level'}
                    overlapping = unvalidated_fields & explicit_fields
                    if overlapping:
                        logger.warning(
                            f"Field overlap detected in PainPoint merge: {overlapping}. "
                            f"Validation scores will overwrite values from UnvalidatedPainPoint."
                        )

                    final_pain_points.append(PainPoint(
                        **unvalidated.model_dump(),  # All original fields
                        severity_score=matching_score.severity_score,
                        willingness_to_pay=matching_score.willingness_to_pay,
                        opportunity_level=matching_score.opportunity_level,
                    ))
                else:
                    logger.warning(
                        f"No validation score found for pain point: '{unvalidated.title}' "
                        f"(best match similarity: {match_ratio:.2%}, threshold: {FUZZY_MATCH_THRESHOLD:.0%}) - skipping"
                    )
                    unmatched_scores.append(unvalidated.title)

            # Validate merge completeness
            if len(final_pain_points) != len(extraction_output.extracted_pain_points):
                logger.warning(
                    f"Merge incomplete: {len(final_pain_points)}/{len(extraction_output.extracted_pain_points)} "
                    f"pain points matched with scores. Unmatched: {unmatched_scores}"
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
