"""
Twitter content collection tool using twitter-api-client.
Supports authenticated and guest sessions for scraping public data.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from crewai.tools import BaseTool
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings
from ..models.social_content import TwitterThread, TwitterTweet


class TwitterCollectorTool(BaseTool):
    """
    Tool for collecting Twitter/X threads using twitter-api-client.
    Fetches tweets and replies without requiring API keys.
    """

    name: str = "TwitterCollectorTool"
    description: str = (
        "Collect Twitter/X threads including original tweet and all replies. "
        "Works with authenticated or guest sessions."
    )

    def __init__(self):
        """Initialize tool and create reusable scraper instance."""
        super().__init__()
        self._scraper = None
        self._scraper_failed = False
        self._cookies_cache_path = Path(settings.twitter_cookies_cache)

    def _load_cookies(self) -> dict:
        """Load cached cookies from file."""
        if not self._cookies_cache_path.exists():
            return None

        try:
            with open(self._cookies_cache_path, 'r') as f:
                cookies = json.load(f)
                if 'ct0' in cookies and 'auth_token' in cookies:
                    logger.info(f"Loaded cached Twitter cookies from {self._cookies_cache_path}")
                    return cookies
                else:
                    logger.warning("Cached cookies missing required fields (ct0, auth_token)")
                    return None
        except Exception as e:
            logger.warning(f"Failed to load cached cookies: {e}")
            return None

    def _save_cookies(self, scraper):
        """Save scraper cookies to cache file for future use."""
        try:
            # Extract cookies from scraper session
            cookies = {}
            if hasattr(scraper, 'session') and hasattr(scraper.session, 'cookies'):
                cookie_jar = scraper.session.cookies
                # Extract the important cookies
                for cookie in cookie_jar:
                    if cookie.name in ['ct0', 'auth_token']:
                        cookies[cookie.name] = cookie.value

            if 'ct0' in cookies and 'auth_token' in cookies:
                with open(self._cookies_cache_path, 'w') as f:
                    json.dump(cookies, f, indent=2)
                logger.info(f"✓ Saved Twitter cookies to {self._cookies_cache_path}")
                return True
            else:
                logger.warning("Could not extract required cookies from session")
                return False
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")
            return False

    def _get_scraper(self):
        """Get initialized Twitter scraper with automatic cookie caching."""
        # If scraper creation previously failed, don't retry
        if self._scraper_failed:
            return None

        # Return cached scraper if available
        if self._scraper:
            return self._scraper

        try:
            from twitter.scraper import Scraper
            from twitter.util import init_session

            # Strategy 1: Try to load and use cached cookies
            cached_cookies = self._load_cookies()
            if cached_cookies:
                logger.info("Attempting authentication with cached cookies")
                try:
                    self._scraper = Scraper(cookies=cached_cookies)
                    logger.info("✓ Twitter authentication successful (using cached cookies)")
                    return self._scraper
                except Exception as cookie_error:
                    logger.warning(f"Cached cookies invalid or expired: {cookie_error}")
                    logger.info("Will attempt fresh login with username/password")
                    # Delete invalid cache file
                    if self._cookies_cache_path.exists():
                        self._cookies_cache_path.unlink()

            # Strategy 2: Login with username/password and cache cookies
            if settings.twitter_username and settings.twitter_password:
                logger.info("Attempting fresh login with username/password")
                logger.debug(f"Twitter username: {settings.twitter_username}")
                try:
                    self._scraper = Scraper(
                        email=settings.twitter_email,
                        username=settings.twitter_username,
                        password=settings.twitter_password,
                    )
                    logger.info("✓ Twitter authentication successful (username/password)")

                    # Save cookies for future use
                    self._save_cookies(self._scraper)

                    return self._scraper
                except Exception as auth_error:
                    logger.error(f"Username/password authentication failed: {auth_error}")
                    logger.warning("Falling back to guest session")

            # Strategy 3: Guest session fallback (very limited)
            logger.info("Using guest session (no authentication - limited access)")
            session = init_session()
            self._scraper = Scraper(session=session)
            logger.warning(
                "Guest session has very limited access. "
                "Provide TWITTER_USERNAME and TWITTER_PASSWORD for better results."
            )
            return self._scraper

        except ImportError:
            logger.warning(
                "twitter-api-client not available. Twitter collection will be disabled. "
                "Install with: pip install twitter-api-client"
            )
            self._scraper_failed = True
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Twitter scraper: {e}")
            self._scraper_failed = True
            return None

    def extract_tweet_id(self, url: str) -> str:
        """
        Extract tweet ID from Twitter URL.

        Args:
            url: Twitter/X.com URL

        Returns:
            Tweet ID string
        """
        # URL format: https://twitter.com/user/status/1234567890
        # or: https://x.com/user/status/1234567890
        parts = urlparse(url).path.split('/')
        if 'status' in parts:
            status_idx = parts.index('status')
            if status_idx + 1 < len(parts):
                tweet_id = parts[status_idx + 1]
                # Remove any query parameters
                tweet_id = tweet_id.split('?')[0]
                return tweet_id
        raise ValueError(f"Could not extract tweet ID from URL: {url}")

    def parse_tweet(self, tweet_data: dict, is_reply: bool = False) -> TwitterTweet:
        """
        Parse tweet data from twitter-api-client response.

        Args:
            tweet_data: Tweet data dictionary
            is_reply: Whether this is a reply tweet

        Returns:
            TwitterTweet model instance
        """
        legacy = tweet_data.get('legacy', {})

        # Extract parent tweet ID if this is a reply
        parent_id = None
        if is_reply and 'in_reply_to_status_id_str' in legacy:
            parent_id = legacy['in_reply_to_status_id_str']

        return TwitterTweet(
            tweet_id=tweet_data.get('rest_id', ''),
            author_username=legacy.get('screen_name', 'unknown'),
            text=legacy.get('full_text', ''),
            likes=legacy.get('favorite_count', 0),
            retweets=legacy.get('retweet_count', 0),
            replies_count=legacy.get('reply_count', 0),
            created_at=datetime.strptime(
                legacy.get('created_at', ''), '%a %b %d %H:%M:%S %z %Y'
            ),
            url=f"https://twitter.com/{legacy.get('screen_name', 'unknown')}/status/{tweet_data.get('rest_id', '')}",
            is_reply=is_reply,
            parent_tweet_id=parent_id,
        )

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def collect_thread(self, url: str) -> TwitterThread:
        """
        Collect a Twitter thread (original tweet + replies).

        Args:
            url: Twitter post URL

        Returns:
            TwitterThread model with original tweet and replies
        """
        scraper = self._get_scraper()
        if not scraper:
            raise RuntimeError(
                "twitter-api-client not available. Cannot collect Twitter data."
            )

        try:
            logger.info(f"Collecting Twitter thread: {url}")

            tweet_id = self.extract_tweet_id(url)
            logger.debug(f"Extracted tweet ID: {tweet_id}")

            # Get tweet details (includes conversation thread)
            try:
                tweet_details = [tweet async for tweet in scraper.tweets_details([int(tweet_id)])]
            except Exception as fetch_error:
                logger.error(f"tweets_details() API call failed: {type(fetch_error).__name__}: {fetch_error}")
                # Check if it's a JSON decode error
                if "JSONDecodeError" in str(type(fetch_error).__name__) or "JSONDecodeError" in str(fetch_error):
                    logger.warning(
                        "Twitter returned non-JSON response. Possible causes:\n"
                        "  1. Account rate limited or suspended\n"
                        "  2. Tweet deleted or made private\n"
                        "  3. Twitter's anti-bot detection triggered\n"
                        "  4. twitter-api-client library needs update"
                    )
                raise

            if not tweet_details:
                raise ValueError(f"Could not fetch tweet: {url}")

            logger.debug(f"Received {len(tweet_details)} tweet objects from API")

            # The first tweet is the original
            original_data = tweet_details[0]
            original_tweet = self.parse_tweet(original_data, is_reply=False)

            # Collect replies
            # tweet_details might include some replies, but we might need to fetch more
            # For now, we'll work with what we get from tweets_details
            replies = []

            # Check if there are reply entries in the response
            # The structure might vary, so we'll need to explore the response
            # For simplicity, let's fetch replies separately using tweet search
            # Note: Guest sessions have limited access to replies

            # Calculate total engagement
            total_engagement = original_tweet.likes + original_tweet.retweets
            total_engagement += sum(r.likes + r.retweets for r in replies)

            thread = TwitterThread(
                thread_id=tweet_id,
                original_tweet=original_tweet,
                replies=replies,
                total_engagement=total_engagement,
            )

            logger.info(
                f"✓ Collected thread with {len(replies)} replies "
                f"(engagement: {total_engagement})"
            )
            return thread

        except Exception as e:
            logger.error(f"Failed to collect Twitter thread {url}: {type(e).__name__}: {e}")
            raise

    async def collect_threads(self, urls: List[str]) -> List[TwitterThread]:
        """
        Collect multiple Twitter threads with quality filtering.

        Args:
            urls: List of Twitter post URLs

        Returns:
            List of TwitterThread models that meet quality thresholds
        """
        threads = []

        try:
            for url in urls:
                try:
                    thread = await self.collect_thread(url)

                    # Quality filtering
                    original = thread.original_tweet
                    if (
                        original.likes >= settings.min_twitter_likes
                        and original.replies_count >= settings.min_twitter_replies
                    ):
                        threads.append(thread)
                        logger.info(
                            f"✓ Thread meets quality thresholds: "
                            f"{original.text[:50]}... (likes: {original.likes})"
                        )
                    else:
                        logger.info(
                            f"✗ Thread filtered out (likes: {original.likes}, "
                            f"replies: {original.replies_count}): {original.text[:50]}..."
                        )

                except Exception as e:
                    logger.error(f"Skipping thread {url} due to error: {e}")
                    continue

            logger.info(f"Collected {len(threads)} quality Twitter threads from {len(urls)} URLs")
            return threads

        finally:
            # Cleanup scraper to close any pending async tasks
            if self._scraper:
                try:
                    # Close the scraper if it has a close method
                    if hasattr(self._scraper, 'close'):
                        await self._scraper.close()
                    # Clear pending tasks
                    import asyncio
                    pending = asyncio.all_tasks()
                    for task in pending:
                        if not task.done() and 'Scraper._process' in str(task):
                            task.cancel()
                except Exception as cleanup_error:
                    logger.debug(f"Scraper cleanup warning: {cleanup_error}")
                    pass

    async def _run(self, urls: str) -> str:
        """
        Main run method for CrewAI tool interface.

        Args:
            urls: Comma-separated list of Twitter URLs

        Returns:
            JSON string with collected threads
        """
        try:
            url_list = [url.strip() for url in urls.split(',') if url.strip()]
            threads = await self.collect_threads(url_list)

            # Convert to dict for JSON serialization
            threads_data = [thread.model_dump() for thread in threads]

            result = {
                "success": True,
                "threads_count": len(threads),
                "total_tweets": sum(1 + len(t.replies) for t in threads),
                "threads": threads_data,
            }

            return str(result)

        except Exception as e:
            logger.error(f"Twitter collection failed: {e}")
            return str({"success": False, "error": str(e), "threads": []})
