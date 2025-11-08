"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

from typing import List

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import (
    PainPoint,
    PainPointAnalysisResult,
    PainPointExtraction,
    UnvalidatedPainPoint,
)
from ..models.social_content import RedditComment, RedditPost, TwitterThread, TwitterTweet


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

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, reddit_posts: List[RedditPost] = None, twitter_threads: List[TwitterThread] = None, niche_description: str = ""):
        """
        Initialize PainPointCrew with social content as knowledge sources.

        Knowledge sources are initialized once and embeddings are cached,
        making this more efficient than passing large content as inputs.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
            niche_description: Description of the niche being analyzed
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

    def _filter_low_quality_reddit(self, posts: List[RedditPost]) -> List[RedditPost]:
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

    def _filter_low_quality_twitter(self, threads: List[TwitterThread]) -> List[TwitterThread]:
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

    def _format_comments_with_replies(self, comments: List[RedditComment], depth: int = 0, max_depth: int = 3) -> str:
        """
        Recursively format comments with their nested replies.

        With knowledge sources + RAG, we can include full comment bodies without truncation.

        Args:
            comments: List of RedditComment objects
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
            # Include full comment body (no truncation with RAG)
            formatted.append(
                f"{indent}- [{comment.score} pts] {comment.body}"
            )

            # Include nested replies (up to max_depth)
            if comment.replies and depth < max_depth:
                # Much higher limits with RAG - semantic search retrieves only relevant chunks
                reply_limit = 30 if depth == 0 else (20 if depth == 1 else 10)
                nested_content = self._format_comments_with_replies(
                    comment.replies[:reply_limit],
                    depth=depth + 1,
                    max_depth=max_depth
                )
                # Only append if there's actual content
                if nested_content:
                    formatted.append(nested_content)

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _format_twitter_replies(self, replies: List[TwitterTweet]) -> str:
        """
        Format Twitter replies with comprehensive content and conversation threading.

        With knowledge sources + RAG, we can include full tweet text and more conversations.

        Args:
            replies: List of TwitterTweet reply objects

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
            # Include full tweet text (no truncation with RAG)
            formatted.append(
                f"- @{root_reply.author_username} [{root_reply.likes} likes, {root_reply.retweets} RTs]: {root_reply.text}"
            )

            # Add nested replies to this conversation (if any)
            if root_reply.tweet_id in children_map:
                nested_replies = children_map[root_reply.tweet_id]
                # Sort nested by engagement and include more replies per conversation
                nested_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

                # Include top 20 nested replies per conversation (was 10)
                for nested in nested_replies[:20]:
                    # Include full nested tweet text (no truncation)
                    formatted.append(
                        f"  └─ @{nested.author_username} [{nested.likes} likes]: {nested.text}"
                    )

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _prepare_reddit_content(self) -> str:
        """
        Format Reddit posts with discussions for knowledge source with metadata headers.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for post in self.reddit_posts:
            formatted.append(f"""[PLATFORM: REDDIT]
[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{post.selftext}

---
## Discussion ({len(post.comments)} comments):

{self._format_comments_with_replies(post.comments)}
""")
        return "\n\n===\n\n".join(formatted)

    def _prepare_twitter_content(self) -> str:
        """
        Format Twitter threads for knowledge source with metadata headers.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for thread in self.twitter_threads:
            formatted.append(f"""[PLATFORM: TWITTER]
[AUTHOR: @{thread.original_tweet.author_username}]
[ENGAGEMENT: {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs]
[URL: {thread.original_tweet.url}]

## Original Tweet:

{thread.original_tweet.text}

---
## Conversation ({len(thread.replies)} replies):

{self._format_twitter_replies(thread.replies)}
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
        Output: Validated pain points with severity and WTP scores.
        """
        return Task(
            config=self.tasks_config["validate_pain_points"],
            agent=self.pain_point_validator(),
            context=[self.extract_pain_points_task()],
            output_pydantic=PainPointAnalysisResult,
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
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            knowledge_sources=self.knowledge_sources,  # Attach knowledge sources
            verbose=True,
            process_type="sequential",  # Tasks run in order
            embedder={
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"  # Cost-effective embeddings
                }
            }
        )

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

            # Hybrid approach: Pass full content for first agent (comprehensive categorization),
            # while knowledge sources remain available for subsequent agents (targeted evidence retrieval)
            crew_output = crew_instance.kickoff(inputs={
                "niche_description": self.niche_description,
                "full_reddit_content": self.formatted_reddit_content,
                "full_twitter_content": self.formatted_twitter_content,
                "reddit_posts_count": len(self.reddit_posts),
                "twitter_threads_count": len(self.twitter_threads),
                "total_reddit_comments": total_reddit_comments,
                "total_twitter_replies": total_twitter_replies,
                "total_content": len(self.reddit_posts) + len(self.twitter_threads),
            })

            # Extract the Pydantic model from CrewOutput
            result = crew_output.pydantic

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
