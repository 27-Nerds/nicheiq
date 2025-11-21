"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tasks.task_output import TaskOutput
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

def validate_pydantic_pain_point_output(result: TaskOutput) -> tuple[bool, Any]:
    """
    Guardrail function to ensure ValidationResult is valid with no extra text.

    This prevents agents from adding explanatory commentary and validates that
    the number of scores matches the number of extracted pain points.

    Returns:
        tuple[bool, Any]: (success, validated_result_or_error_message)
    """
    try:
        # Check if Pydantic output exists
        if not result.pydantic:
            # Log raw output preview for debugging
            raw_preview = result.raw[:500] if hasattr(result, 'raw') and result.raw else "No raw output available"
            logger.error(f"Guardrail validation failed - No Pydantic output found. Raw output preview: {raw_preview}...")
            return (False, "CRITICAL ERROR: Return ONLY the ValidationResult Pydantic model with NO additional text, explanations, or commentary. Do not add phrases like 'The above JSON object fully complies...'")

        # Validate it's the correct type
        validation_result = result.pydantic  # Should be ValidationResult

        # Check pain_point_scores list exists
        if not hasattr(validation_result, 'pain_point_scores'):
            logger.error(f"Guardrail validation failed - Missing 'pain_point_scores' field. Output type: {type(validation_result)}")
            return (False, "OUTPUT ERROR: Missing 'pain_point_scores' field in ValidationResult")

        if not validation_result.pain_point_scores:
            logger.error("Guardrail validation failed - Empty pain_point_scores list")
            return (False, "VALIDATION ERROR: Empty pain_point_scores list. You must score all extracted pain points.")

        # Success - return the validated Pydantic output
        logger.debug(f"Guardrail validation passed: {len(validation_result.pain_point_scores)} pain points scored")
        return (True, result.pydantic)

    except Exception as e:
        # Log exception details for debugging
        raw_preview = result.raw[:500] if hasattr(result, 'raw') and result.raw else "No raw output available"
        logger.error(f"Guardrail validation exception: {str(e)}. Raw output preview: {raw_preview}...")
        return (False, f"VALIDATION_ERROR: Failed to validate output - {str(e)}. Return ONLY the ValidationResult model with no extra text.")

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

        # Log filtering results
        if original_reddit_count > len(self.reddit_posts):
            logger.info(
                f"Filtered out {original_reddit_count - len(self.reddit_posts)} "
                f"low-quality Reddit posts ({len(self.reddit_posts)}/{original_reddit_count} remaining)"
            )
        if original_twitter_count > len(self.twitter_threads):
            logger.info(
                f"Filtered out {original_twitter_count - len(self.twitter_threads)} "
                f"low-quality Twitter threads ({len(self.twitter_threads)}/{original_twitter_count} remaining)"
            )

        self.niche_description = niche_description
        self.market_segments = market_segments or []
        self.industry_boundaries = industry_boundaries
        self.knowledge_sources = []

        # Store formatted content for direct injection into first task
        # (subsequent tasks use knowledge sources for RAG-based evidence retrieval)
        self.formatted_reddit_content = ""
        self.formatted_twitter_content = ""

        # Calculate total discussion volume
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

        # Initialize knowledge sources for semantic search
        from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

        if self.reddit_posts:
            reddit_content = self._prepare_reddit_content()
            self.formatted_reddit_content = reddit_content  # Store for direct task injection
            self.reddit_knowledge = StringKnowledgeSource(
                content=reddit_content,
                chunk_size=2000,      # Preserve discussion context
                chunk_overlap=300     # More overlap for conversational threading
            )
            self.knowledge_sources.append(self.reddit_knowledge)
            logger.info(f"Reddit knowledge source created ({len(reddit_content)} chars)")

        if self.twitter_threads:
            twitter_content = self._prepare_twitter_content()
            self.formatted_twitter_content = twitter_content  # Store for direct task injection
            self.twitter_knowledge = StringKnowledgeSource(
                content=twitter_content,
                chunk_size=1500,      # Smaller chunks for tweets
                chunk_overlap=200     # Less overlap needed
            )
            self.knowledge_sources.append(self.twitter_knowledge)
            logger.info(f"Twitter knowledge source created ({len(twitter_content)} chars)")

        logger.info(
            f"PainPointCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments) and {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies) - {len(self.knowledge_sources)} knowledge source(s) ready"
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

        With knowledge sources + RAG, we can include full comment bodies without truncation.

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
                # Much higher limits with RAG - semantic search retrieves only relevant chunks
                reply_limit = 30 if depth == 0 else (20 if depth == 1 else 10)
                nested_content = self._format_comments_with_replies(
                    comment.replies[:reply_limit],
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

        With knowledge sources + RAG, we can include full tweet text and more conversations.

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
        # No limit with RAG - semantic search retrieves only relevant chunks
        # Process all root replies (was 50)

        for root_reply in root_replies:
            # Include full tweet text with source tracking
            formatted.append(
                f"- @{root_reply.author_username} [{root_reply.likes} likes, {root_reply.retweets} RTs]: {root_reply.text} [source: {thread_id}]"
            )

            # Add nested replies to this conversation (if any)
            if root_reply.tweet_id in children_map:
                nested_replies = children_map[root_reply.tweet_id]
                # Sort nested by engagement and include more replies per conversation
                nested_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

                # Include top 20 nested replies per conversation (was 10)
                for nested in nested_replies[:20]:
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

        return Agent(
            config=self.agents_config["content_researcher"],
            llm=ChatOpenAI(
                model=settings.content_analysis_llm,
                temperature=0,  # Deterministic for categorization
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def pain_point_analyst(self) -> Agent:
        """
        Agent responsible for extracting pain points from categorized content.
        Identifies specific problems, frustrations, and unmet needs.

        Uses low-moderate temperature (0.3) for consistent pattern extraction with flexibility.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["pain_point_analyst"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.3,  # Low-moderate for consistent extraction with nuanced understanding
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @agent
    def pain_point_validator(self) -> Agent:
        """
        Agent responsible for scoring and validating pain points.
        Assesses severity, willingness to pay, and market potential.

        Uses low temperature (0.2) for objective, consistent scoring.
        """
        from langchain_openai import ChatOpenAI

        return Agent(
            config=self.agents_config["pain_point_validator"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.2,  # Low temperature for analytical, objective scoring
                api_key=settings.openai_api_key
            ),
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
            guardrail=validate_pydantic_pain_point_output,
            guardrail_max_retries=3,
        )

    @crew
    def crew(self) -> Crew:
        """
        Assemble the PainPointCrew with all agents, tasks, and knowledge sources.

        Knowledge sources are attached at crew level so all agents can access them
        for semantic search and retrieval during task execution.

        Returns:
            Configured Crew instance with knowledge sources
        """
        from crewai.knowledge.knowledge import Knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {
                "model_name": "text-embedding-3-small"  # Cost-effective embeddings
            }
        }

        # Create Knowledge with niche-specific collection name for isolation
        knowledge = None
        if self.knowledge_sources:
            collection_name = sanitize_collection_name(self.niche_description, "pain")
            logger.info(f"Creating knowledge with collection: {collection_name}")
            knowledge = Knowledge(
                sources=self.knowledge_sources,
                embedder=embedder_config,
                collection_name=collection_name,
            )
            knowledge.add_sources()

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            knowledge=knowledge,  # Use pre-configured Knowledge instead of knowledge_sources
            verbose=True,
            process_type="sequential",  # Tasks run in order
            embedder=embedder_config
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
                f"Knowledge sources: {len(self.knowledge_sources)} source(s), "
                f"{len(self.reddit_posts)} Reddit posts ({total_reddit_comments} comments), "
                f"{len(self.twitter_threads)} Twitter threads ({total_twitter_replies} replies)"
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

            # Execute crew with metadata inputs only
            # Content is accessed automatically via knowledge sources
            crew_instance = self.crew()

            # Verify knowledge sources are initialized (debug logging)
            logger.debug("=" * 80)
            logger.debug("KNOWLEDGE SOURCES VERIFICATION")
            logger.debug("=" * 80)
            if hasattr(crew_instance, 'knowledge_sources') and crew_instance.knowledge_sources:
                logger.debug(f"✅ {len(crew_instance.knowledge_sources)} knowledge source(s) attached to crew")
                for i, ks in enumerate(crew_instance.knowledge_sources, 1):
                    logger.debug(f"   Source {i}: {type(ks).__name__}, {len(ks.content)} chars")
            else:
                logger.warning("⚠️  No knowledge sources attached to crew!")
            logger.debug("=" * 80)

            # Token monitoring: Log content size and check soft caps
            if settings.token_monitoring_enabled:
                monitor = ContentTokenMonitor()

                # Monitor Reddit content
                reddit_tokens = monitor.log_content_stats(
                    content=self.formatted_reddit_content,
                    label="Stage 6 - Reddit content",
                    model=settings.content_analysis_llm
                )

                # Monitor Twitter content
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

            # Hybrid approach: Pass full content for first agent (comprehensive categorization),
            # while knowledge sources remain available for subsequent agents (targeted evidence retrieval)
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
                # Find matching score by title
                matching_score = next(
                    (score for score in validation_output.pain_point_scores
                     if score.pain_point_title == unvalidated.title),
                    None
                )

                if matching_score:
                    # Merge unvalidated pain point + validation scores
                    final_pain_points.append(PainPoint(
                        **unvalidated.model_dump(),  # All original fields
                        severity_score=matching_score.severity_score,
                        willingness_to_pay=matching_score.willingness_to_pay,
                        opportunity_level=matching_score.opportunity_level,
                    ))
                else:
                    logger.warning(f"No validation score found for pain point: '{unvalidated.title}' - skipping")
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
