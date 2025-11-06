"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

from typing import List

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..models.pain_point import PainPoint, PainPointAnalysisResult
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

    def __init__(self, reddit_posts: List[RedditPost] = None, twitter_threads: List[TwitterThread] = None):
        """
        Initialize PainPointCrew with social content.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.reddit_posts = reddit_posts or []
        self.twitter_threads = twitter_threads or []

        # Calculate total discussion volume
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

        logger.info(
            f"PainPointCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments) and {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies)"
        )

    def _format_comments_with_replies(self, comments: List[RedditComment], depth: int = 0, max_depth: int = 2) -> str:
        """
        Recursively format comments with their nested replies.

        Args:
            comments: List of RedditComment objects
            depth: Current nesting depth (for indentation)
            max_depth: Maximum depth to traverse (default 2 levels)

        Returns:
            Formatted string with comments and nested replies
        """
        if not comments or depth > max_depth:
            return ""

        formatted = []
        indent = "  " * depth  # Indentation for nested comments

        for comment in comments:
            # Format main comment with appropriate character limit based on depth
            char_limit = 800 if depth == 0 else 400  # Top-level gets more chars
            comment_text = comment.body[:char_limit]
            if len(comment.body) > char_limit:
                comment_text += "..."

            formatted.append(
                f"{indent}- [{comment.score} pts] {comment_text}"
            )

            # Include nested replies (up to max_depth)
            if comment.replies and depth < max_depth:
                # Limit nested replies to avoid explosion
                reply_limit = 5 if depth == 0 else 3
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
        processed_count = 0
        max_conversations = 25  # Maximum conversation threads to include

        for root_reply in root_replies[:max_conversations]:
            if processed_count >= max_conversations:
                break

            engagement = root_reply.likes + root_reply.retweets
            char_limit = 1000 if engagement > 10 else 700
            reply_text = root_reply.text[:char_limit]
            if len(root_reply.text) > char_limit:
                reply_text += "..."

            formatted.append(
                f"- @{root_reply.author_username} [{root_reply.likes} likes, {root_reply.retweets} RTs]: {reply_text}"
            )
            processed_count += 1

            # Add nested replies to this conversation (if any)
            if root_reply.tweet_id in children_map:
                nested_replies = children_map[root_reply.tweet_id]
                # Sort nested by engagement and limit to top 3 per conversation
                nested_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

                for nested in nested_replies[:3]:
                    if processed_count >= max_conversations:
                        break

                    nested_text = nested.text[:600]
                    if len(nested.text) > 600:
                        nested_text += "..."

                    formatted.append(
                        f"  └─ @{nested.author_username} [{nested.likes} likes]: {nested_text}"
                    )
                    processed_count += 1

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    @agent
    def content_researcher(self) -> Agent:
        """
        Agent responsible for reading and categorizing social content.
        Identifies themes, patterns, and user segments.
        """
        return Agent(
            config=self.agents_config["content_researcher"],
            verbose=True,
        )

    @agent
    def pain_point_analyst(self) -> Agent:
        """
        Agent responsible for extracting pain points from categorized content.
        Identifies specific problems, frustrations, and unmet needs.
        """
        return Agent(
            config=self.agents_config["pain_point_analyst"],
            verbose=True,
        )

    @agent
    def pain_point_validator(self) -> Agent:
        """
        Agent responsible for scoring and validating pain points.
        Assesses severity, willingness to pay, and market potential.
        """
        return Agent(
            config=self.agents_config["pain_point_validator"],
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
        Output: List of identified pain points with descriptions and quotes.
        """
        return Task(
            config=self.tasks_config["extract_pain_points"],
            agent=self.pain_point_analyst(),
            context=[self.categorize_content_task()],
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
        Assemble the PainPointCrew with all agents and tasks.

        Returns:
            Configured Crew instance
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=True,
            process_type="sequential",  # Tasks run in order
        )

    def analyze(self) -> PainPointAnalysisResult:
        """
        Execute pain point analysis workflow.

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
            # Prepare Reddit summary
            reddit_summary = "\n\n".join([
                f"### Reddit Post: {post.title}\n"
                f"**Subreddit:** r/{post.subreddit}\n"
                f"**Score:** {post.score} upvotes | **Comments:** {len(post.comments)}\n"
                f"**Post Content:** {post.selftext[:500]}{'...' if len(post.selftext) > 500 else ''}\n\n"
                f"**Discussion:**\n{self._format_comments_with_replies(post.comments)}"
                for post in self.reddit_posts
            ]) if self.reddit_posts else "[No Reddit content]"

            # Prepare Twitter summary
            twitter_summary = "\n\n".join([
                f"### Twitter Thread: {thread.original_tweet.text[:100]}...\n"
                f"**Author:** @{thread.original_tweet.author_username}\n"
                f"**Engagement:** {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs, "
                f"{thread.original_tweet.replies_count} replies\n"
                f"**Full Tweet:** {thread.original_tweet.text}\n\n"
                f"**Replies:**\n{self._format_twitter_replies(thread.replies)}"
                for thread in self.twitter_threads
            ]) if self.twitter_threads else "[No Twitter content]"

            # Calculate total discussion volume
            total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
            total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

            # Debug logging
            logger.debug("=" * 80)
            logger.debug("PAIN POINT ANALYSIS INPUTS")
            logger.debug("=" * 80)
            logger.debug(f"Reddit posts: {len(self.reddit_posts)} ({total_reddit_comments} comments)")
            logger.debug(f"Twitter threads: {len(self.twitter_threads)} ({total_twitter_replies} replies)")
            logger.debug("=" * 80)

            # Execute crew with inputs
            crew_output = self.crew().kickoff(inputs={
                "reddit_posts_count": len(self.reddit_posts),
                "twitter_threads_count": len(self.twitter_threads),
                "total_reddit_comments": total_reddit_comments,
                "total_twitter_replies": total_twitter_replies,
                "total_content": len(self.reddit_posts) + len(self.twitter_threads),
                "reddit_summary": reddit_summary,
                "twitter_summary": twitter_summary
            })

            # Extract the Pydantic model from CrewOutput
            result = crew_output.pydantic
            logger.info(f"Pain point analysis complete: {len(result.pain_points)} pain points identified")
            return result

        except Exception as e:
            logger.error(f"Pain point analysis failed: {e}")
            raise
