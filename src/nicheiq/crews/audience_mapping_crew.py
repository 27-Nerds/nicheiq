"""
Audience Mapping Crew (Stage 6.5).

Analyzes social media discussions to identify audience segments, key influencers,
common vocabulary, and content preferences for targeted marketing strategy.

Uses Knowledge Sources (RAG) for semantic search through full discussion content,
enabling extraction of ACTUAL usernames, vocabulary, and tools mentioned.
"""

from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import AudienceMappingResult
from ..models.social_content import RedditPost, TwitterThread


@CrewBase
class AudienceMappingCrew:
    """
    Crew for audience segmentation and influencer mapping in Stage 6.5.

    Uses Knowledge Sources (RAG) to enable semantic search through full
    discussion content for extracting real usernames, vocabulary, and tools.

    Analyzes:
    - Social media discussions (Reddit/Twitter) via knowledge sources
    - Pain point data for segment alignment
    - User vocabulary and content preferences
    - Influencers and community hubs

    Outputs:
    - Audience segments with characteristics
    - Key influencers and communities
    - Messaging frameworks and acquisition channels
    """

    agents_config = "config/audience_mapping_agents.yaml"
    tasks_config = "config/audience_mapping_tasks.yaml"

    def __init__(
        self,
        reddit_posts: list[RedditPost] = None,
        twitter_threads: list[TwitterThread] = None,
        niche_description: str = ""
    ):
        """
        Initialize AudienceMappingCrew with social content as knowledge sources.

        Knowledge sources enable semantic search through full discussion content,
        allowing the agent to find actual usernames, vocabulary, and tools.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
            niche_description: Description of the niche being analyzed
        """
        # The @CrewBase decorator handles parent class initialization

        self.reddit_posts = reddit_posts or []
        self.twitter_threads = twitter_threads or []
        self.niche_description = niche_description
        self.knowledge_sources = []

        # Calculate content stats for logging
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

        # Initialize knowledge sources for semantic search
        from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

        if self.reddit_posts:
            reddit_content = self._prepare_reddit_content()
            self.reddit_knowledge = StringKnowledgeSource(
                content=reddit_content,
                chunk_size=2000,      # Preserve discussion context
                chunk_overlap=300     # Overlap for conversational threading
            )
            self.knowledge_sources.append(self.reddit_knowledge)
            logger.info(f"Reddit knowledge source created ({len(reddit_content)} chars)")

        if self.twitter_threads:
            twitter_content = self._prepare_twitter_content()
            self.twitter_knowledge = StringKnowledgeSource(
                content=twitter_content,
                chunk_size=1500,      # Smaller chunks for tweets
                chunk_overlap=200
            )
            self.knowledge_sources.append(self.twitter_knowledge)
            logger.info(f"Twitter knowledge source created ({len(twitter_content)} chars)")

        logger.info(
            f"AudienceMappingCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments) and {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies) - {len(self.knowledge_sources)} knowledge source(s) ready"
        )

    def _prepare_reddit_content(self) -> str:
        """
        Format Reddit posts with discussions for knowledge source with metadata headers.
        Includes usernames and post IDs for traceability.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for post in self.reddit_posts:
            # Format comments with usernames
            comments_formatted = self._format_comments(post.comments, post.post_id)

            formatted.append(f"""[PLATFORM: REDDIT]
[POST_ID: {post.post_id}]
[SUBREDDIT: r/{post.subreddit}]
[AUTHOR: u/{getattr(post, 'author', 'unknown')}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{post.selftext} [source: {post.post_id}]

---
## Discussion ({len(post.comments)} comments):

{comments_formatted}
""")
        return "\n\n===\n\n".join(formatted)

    def _format_comments(self, comments, post_id: str, depth: int = 0, max_depth: int = 3) -> str:
        """
        Format comments with usernames for knowledge source.

        Args:
            comments: List of RedditComment objects
            post_id: Source post ID for tracking
            depth: Current nesting depth
            max_depth: Maximum depth to traverse

        Returns:
            Formatted string with comments including usernames
        """
        if not comments or depth > max_depth:
            return ""

        formatted = []
        indent = "  " * depth

        for comment in comments:
            author = getattr(comment, 'author', 'unknown')
            formatted.append(
                f"{indent}- [u/{author}] [{comment.score} pts] {comment.body} [source: {post_id}]"
            )

            # Include nested replies
            if hasattr(comment, 'replies') and comment.replies and depth < max_depth:
                reply_limit = 20 if depth == 0 else (10 if depth == 1 else 5)
                nested_content = self._format_comments(
                    comment.replies[:reply_limit],
                    post_id=post_id,
                    depth=depth + 1,
                    max_depth=max_depth
                )
                if nested_content:
                    formatted.append(nested_content)

        return "\n".join(str(item) for item in formatted if item)

    def _prepare_twitter_content(self) -> str:
        """
        Format Twitter threads for knowledge source with metadata headers.
        Includes usernames and thread IDs for traceability.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for thread in self.twitter_threads:
            # Format replies with usernames
            replies_formatted = self._format_twitter_replies(thread.replies, thread.thread_id)

            formatted.append(f"""[PLATFORM: TWITTER]
[THREAD_ID: {thread.thread_id}]
[AUTHOR: @{thread.original_tweet.author_username}]
[ENGAGEMENT: {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs]
[URL: {thread.original_tweet.url}]

## Original Tweet:

{thread.original_tweet.text} [source: {thread.thread_id}]

---
## Conversation ({len(thread.replies)} replies):

{replies_formatted}
""")
        return "\n\n===\n\n".join(formatted)

    def _format_twitter_replies(self, replies, thread_id: str) -> str:
        """
        Format Twitter replies with usernames for knowledge source.

        Args:
            replies: List of TwitterTweet reply objects
            thread_id: Source thread ID for tracking

        Returns:
            Formatted string with replies including usernames
        """
        if not replies:
            return "[No replies]"

        formatted = []
        for reply in replies:
            formatted.append(
                f"- [@{reply.author_username}] [{reply.likes} likes] {reply.text} [source: {thread_id}]"
            )

        return "\n".join(formatted)

    @agent
    def audience_researcher(self) -> Agent:
        """
        Audience Research Specialist agent.

        Identifies distinct audience segments, influencers, and communities
        from social media discussions using knowledge source queries.
        """
        return Agent(
            config=self.agents_config["audience_researcher"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate creativity for segment identification
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def audience_mapping_task(self) -> Task:
        """
        Main audience mapping and segmentation task.

        Analyzes social discussions via knowledge sources to identify
        segments, influencers, vocabulary, and messaging frameworks.
        """
        return Task(
            config=self.tasks_config["audience_mapping_analysis"],
            agent=self.audience_researcher(),
            output_pydantic=AudienceMappingResult,
            guardrail=self._validate_audience_output,
        )

    def _validate_audience_output(self, task_output) -> tuple[bool, Any]:
        """
        Validate audience mapping output meets CRITICAL RULES from task YAML.

        Checks:
        - Rule 1: 3-5 distinct audience segments
        - Rule 3: 5-10 key influencers with actual names
        - Rule 4: 10-15 vocabulary terms from discussions

        Args:
            task_output: Task output from CrewAI

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic

            # Rule 1: 3-5 distinct segments
            if not result.audience_segments or len(result.audience_segments) < 3:
                return (False, f"Must have 3-5 audience segments, got {len(result.audience_segments) if result.audience_segments else 0}")

            if len(result.audience_segments) > 5:
                return (False, f"Must have 3-5 audience segments, got {len(result.audience_segments)} (too many)")

            # Rule 3: 5-10 influencers
            if not result.key_influencers or len(result.key_influencers) < 5:
                return (False, f"Must have 5-10 key influencers, got {len(result.key_influencers) if result.key_influencers else 0}")

            # Rule 4: 10-15 vocabulary terms
            if not result.common_vocabulary or len(result.common_vocabulary) < 10:
                return (False, f"Must have 10-15 vocabulary terms, got {len(result.common_vocabulary) if result.common_vocabulary else 0}")

            return (True, result)
        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the audience mapping crew with knowledge sources.

        Knowledge sources enable semantic search through full discussion
        content for extracting real usernames, vocabulary, and tools.
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
            collection_name = sanitize_collection_name(self.niche_description, "audience")
            logger.info(f"Creating knowledge with collection: {collection_name}")
            knowledge = Knowledge(
                sources=self.knowledge_sources,
                embedder=embedder_config,
                collection_name=collection_name,
            )
            knowledge.add_sources()

        return Crew(
            agents=[self.audience_researcher()],
            tasks=[self.audience_mapping_task()],
            knowledge=knowledge,
            verbose=True,
            embedder=embedder_config
        )

    def analyze(
        self,
        pain_point_analysis: PainPointAnalysisResult,
        niche_description: str
    ) -> AudienceMappingResult | None:
        """
        Execute audience mapping crew to identify segments and influencers.

        Knowledge sources (set in __init__) handle full discussion content.
        This method passes only metadata needed for the task.

        Args:
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            niche_description: Niche description for context

        Returns:
            AudienceMappingResult with audience segments and influencer data, or None if analysis fails
        """
        logger.info("[Stage 6.5] Starting Audience & Influence Mapping...")
        logger.info(f"  Niche: {niche_description}")

        # Calculate data quality metrics
        total_discussions = len(self.reddit_posts) + len(self.twitter_threads)
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

        logger.info(f"  Analyzing {total_discussions} social discussions...")
        logger.info(f"  Knowledge sources: {len(self.knowledge_sources)} source(s) ready for semantic search")

        # Format pain points summary for task input
        pain_points_summary = self._format_pain_points(pain_point_analysis)

        # Format subreddit distribution for context
        subreddits = {}
        for post in self.reddit_posts:
            sub = getattr(post, 'subreddit', 'unknown')
            subreddits[sub] = subreddits.get(sub, 0) + 1

        subreddit_summary = "\n".join([
            f"- r/{sub}: {count} discussions"
            for sub, count in sorted(subreddits.items(), key=lambda x: x[1], reverse=True)[:10]
        ])

        # Prepare inputs - knowledge sources handle full content
        inputs = {
            "niche_description": niche_description,
            "total_discussions": total_discussions,
            "reddit_posts_count": len(self.reddit_posts),
            "twitter_threads_count": len(self.twitter_threads),
            "total_reddit_comments": total_reddit_comments,
            "total_twitter_replies": total_twitter_replies,
            "subreddit_distribution": subreddit_summary if subreddits else "No Reddit data",
            "pain_points_summary": pain_points_summary,
        }

        try:
            # Execute crew - knowledge sources enable semantic search
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                audience_result = result.pydantic
                logger.info("[Stage 6.5] Audience Mapping Complete")
                logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
                logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
                logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
                logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
                return audience_result
            else:
                logger.error("[Stage 6.5] Audience mapping failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 6.5] Audience mapping error: {str(e)}")
            return None

    def _format_pain_points(self, pain_point_analysis: PainPointAnalysisResult) -> str:
        """
        Format pain point data for segment alignment.

        Returns:
            Formatted string with pain points and categories
        """
        if not pain_point_analysis or not pain_point_analysis.pain_points:
            return "No pain point data available."

        summary = []
        summary.append(f"**Total Pain Points:** {len(pain_point_analysis.pain_points)}")

        if pain_point_analysis.top_categories:
            summary.append(f"\n**Pain Point Categories:** {', '.join(pain_point_analysis.top_categories[:5])}")

        summary.append("\n**Top Pain Points:**")
        for pain_point in pain_point_analysis.pain_points[:10]:
            title = getattr(pain_point, 'title', 'Untitled')
            severity = getattr(pain_point, 'severity_score', 0)
            summary.append(f"- {title} (Severity: {severity:.2f})")

        return "\n".join(summary)

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            CrewAI UsageMetrics object or None if no execution yet
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
