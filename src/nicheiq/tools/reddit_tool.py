"""
Reddit content collection tool using PRAW.
"""

from datetime import datetime
from typing import List

import praw
from crewai.tools import BaseTool
from loguru import logger
from praw.models import MoreComments
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings
from ..models.social_content import RedditComment, RedditPost


class RedditCollectorTool(BaseTool):
    """
    Tool for collecting Reddit posts and comments using PRAW.
    Fetches full post content including all nested comments.
    """

    name: str = "RedditCollectorTool"
    description: str = (
        "Collect Reddit posts and all comments from given URLs. "
        "Fetches complete discussion threads including nested replies."
    )

    def _get_reddit_client(self) -> praw.Reddit:
        """Get initialized PRAW Reddit client."""
        return praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            check_for_async=False,  # Suppress async environment warning
        )

    def _parse_comment(self, comment) -> RedditComment:
        """
        Recursively parse a PRAW comment and its replies into our RedditComment model.

        Args:
            comment: PRAW Comment object

        Returns:
            RedditComment model instance with nested replies
        """
        replies = []

        # Recursively parse all replies
        if hasattr(comment, 'replies'):
            for reply in comment.replies:
                # Skip MoreComments objects (load more links)
                if isinstance(reply, MoreComments):
                    continue
                replies.append(self._parse_comment(reply))

        return RedditComment(
            comment_id=comment.id,
            author=str(comment.author) if comment.author else "[deleted]",
            body=comment.body,
            score=comment.score,
            created_utc=datetime.fromtimestamp(comment.created_utc),
            is_submitter=comment.is_submitter,
            replies=replies,
        )

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def collect_post(self, url: str) -> RedditPost:
        """
        Collect a single Reddit post with all comments.

        Args:
            url: Reddit post URL

        Returns:
            RedditPost model with all comments
        """
        try:
            logger.info(f"Collecting Reddit post: {url}")

            # Get Reddit client
            reddit = self._get_reddit_client()

            # Get submission from URL (PRAW best practice)
            submission = reddit.submission(url=url)

            # Load comments - configurable limit
            # None = all comments (slowest, most complete)
            # 32 = most comments (balanced)
            # 0 = top-level only (fastest, least complete)
            logger.info(f"Loading comments with limit={settings.reddit_comment_limit}")
            submission.comments.replace_more(limit=settings.reddit_comment_limit)

            # Parse all top-level comments and their replies
            comments = []
            for comment in submission.comments:
                # Skip any remaining MoreComments objects
                if isinstance(comment, MoreComments):
                    continue
                comments.append(self._parse_comment(comment))

            post = RedditPost(
                post_id=submission.id,
                title=submission.title,
                selftext=submission.selftext,
                author=str(submission.author) if submission.author else "[deleted]",
                subreddit=submission.subreddit.display_name,
                score=submission.score,
                num_comments=submission.num_comments,
                created_utc=datetime.fromtimestamp(submission.created_utc),
                url=url,
                comments=comments,
            )

            logger.info(
                f"✓ Collected post '{post.title[:50]}...' with {len(comments)} top-level comments "
                f"(score: {post.score}, total comments reported: {post.num_comments})"
            )
            return post

        except Exception as e:
            logger.error(f"Failed to collect Reddit post {url}: {e}")
            raise

    def collect_posts(self, urls: List[str]) -> List[RedditPost]:
        """
        Collect multiple Reddit posts with quality filtering.

        Args:
            urls: List of Reddit post URLs

        Returns:
            List of RedditPost models that meet quality thresholds
        """
        posts = []

        for url in urls:
            try:
                post = self.collect_post(url)

                # Quality filtering based on settings
                if (
                    post.score >= settings.min_reddit_upvotes
                    and post.num_comments >= settings.min_reddit_comments
                ):
                    posts.append(post)
                    logger.info(f"✓ Post meets quality thresholds: {post.title[:50]}...")
                else:
                    logger.info(
                        f"✗ Post filtered out (score: {post.score}, "
                        f"comments: {post.num_comments}): {post.title[:50]}..."
                    )

            except Exception as e:
                logger.error(f"Skipping post {url} due to error: {e}")
                continue

        logger.info(f"Collected {len(posts)} quality Reddit posts from {len(urls)} URLs")
        return posts

    def _run(self, urls: str) -> str:
        """
        Main run method for CrewAI tool interface.

        Args:
            urls: Comma-separated list of Reddit URLs

        Returns:
            JSON string with collected posts
        """
        try:
            url_list = [url.strip() for url in urls.split(',') if url.strip()]
            posts = self.collect_posts(url_list)

            # Convert to dict for JSON serialization
            posts_data = [post.model_dump() for post in posts]

            result = {
                "success": True,
                "posts_count": len(posts),
                "total_comments": sum(len(p.comments) for p in posts),
                "posts": posts_data,
            }

            return str(result)

        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")
            return str({"success": False, "error": str(e), "posts": []})
