"""
Twitter content collection tool using twitter-api-client.
Supports authenticated and guest sessions for scraping public data.
"""

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
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
            with open(self._cookies_cache_path) as f:
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
                logger.debug(f"Extracting cookies from session (found {len(cookie_jar)} cookies)")

                # Extract the important cookies
                for cookie in cookie_jar:
                    if cookie.name in ['ct0', 'auth_token']:
                        cookies[cookie.name] = cookie.value
                        logger.debug(f"  Found cookie '{cookie.name}'")
            else:
                logger.warning("Scraper session does not have cookies attribute")
                return False

            if 'ct0' in cookies and 'auth_token' in cookies:
                # Ensure parent directory exists
                self._cookies_cache_path.parent.mkdir(parents=True, exist_ok=True)

                # Save cookies to file with restricted permissions
                with open(self._cookies_cache_path, 'w') as f:
                    json.dump(cookies, f, indent=2)
                os.chmod(self._cookies_cache_path, 0o600)

                logger.info(f"✓ Saved Twitter cookies to {self._cookies_cache_path}")
                return True
            else:
                missing = []
                if 'ct0' not in cookies:
                    missing.append('ct0')
                if 'auth_token' not in cookies:
                    missing.append('auth_token')
                logger.warning(f"Could not extract required cookies from session (missing: {', '.join(missing)})")
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
                try:
                    self._scraper = Scraper(
                        email=settings.twitter_email,
                        username=settings.twitter_username,
                        password=settings.twitter_password,
                    )
                    logger.info("✓ Twitter authentication successful (username/password)")

                    # Save cookies for future use
                    cookie_save_success = self._save_cookies(self._scraper)
                    if not cookie_save_success:
                        logger.warning(
                            "⚠️  Cookies could not be saved. Next run will require re-authentication.\n"
                            "    Check that:\n"
                            "    1. Scraper session contains 'ct0' and 'auth_token' cookies\n"
                            "    2. File write permissions are correct\n"
                            "    3. twitter-api-client library version is compatible"
                        )

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

    def _extract_tweets_from_response(self, response: dict) -> tuple[dict | None, list[dict]]:
        """
        Extract main tweet and replies from nested GraphQL response structure.

        The twitter-api-client returns deeply nested responses like:
        data.threaded_conversation_with_injections_v2.instructions[].entries[]

        Main tweet entries have entryId starting with "tweet-"
        Reply entries have entryId starting with "conversationthread-" with items array

        Args:
            response: Raw API response dictionary

        Returns:
            Tuple of (main_tweet, replies_list) where:
            - main_tweet: Tweet result dict with rest_id and legacy fields, or None
            - replies_list: List of reply tweet dicts
        """
        main_tweet = None
        replies = []

        try:
            # Navigate the GraphQL response structure
            data = response.get('data', {})
            conversation = data.get('threaded_conversation_with_injections_v2', {})
            instructions = conversation.get('instructions', [])

            for instruction in instructions:
                if instruction.get('type') == 'TimelineAddEntries':
                    entries = instruction.get('entries', [])
                    for entry in entries:
                        entry_id = entry.get('entryId', '')
                        content = entry.get('content', {})

                        # Main tweet: entry starts with "tweet-"
                        if entry_id.startswith('tweet-'):
                            item_content = content.get('itemContent', {})
                            tweet_results = item_content.get('tweet_results', {})
                            result = tweet_results.get('result', {})

                            if result.get('__typename') == 'Tweet' and result.get('legacy'):
                                main_tweet = result

                        # Replies: entry starts with "conversationthread-"
                        elif entry_id.startswith('conversationthread-'):
                            items = content.get('items', [])
                            for item in items:
                                item_content = item.get('item', {}).get('itemContent', {})
                                tweet_results = item_content.get('tweet_results', {})
                                result = tweet_results.get('result', {})

                                if result.get('__typename') == 'Tweet' and result.get('legacy'):
                                    replies.append(result)
                                    logger.debug(f"[DIAG] Found reply {result.get('rest_id')}: likes={result.get('legacy', {}).get('favorite_count')}")

            if replies:
                logger.info(f"[DIAG] Extracted {len(replies)} replies from conversation threads")

            return main_tweet, replies
        except Exception as e:
            logger.debug(f"Failed to extract tweets from response: {e}")
            return None, []

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
            tweet_data: Tweet data dictionary (the 'result' object from GraphQL response)
            is_reply: Whether this is a reply tweet

        Returns:
            TwitterTweet model instance
        """
        legacy = tweet_data.get('legacy', {})
        logger.debug(f"[DIAG] parse_tweet: legacy keys={list(legacy.keys())}, likes={legacy.get('favorite_count', 'MISSING')}, replies={legacy.get('reply_count', 'MISSING')}")

        # Extract tweet text - use note_tweet for long tweets if available
        text = legacy.get('full_text', '')
        note_tweet = tweet_data.get('note_tweet', {})
        if note_tweet:
            note_text = note_tweet.get('note_tweet_results', {}).get('result', {}).get('text', '')
            if note_text:
                text = note_text  # Use full text from note_tweet (not truncated)
                logger.debug(f"[DIAG] Using note_tweet text ({len(text)} chars) instead of truncated legacy.full_text")

        # Extract author username from user_results (not in tweet's legacy)
        author_username = 'unknown'
        try:
            user_legacy = tweet_data.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {})
            author_username = user_legacy.get('screen_name', 'unknown')
        except Exception:
            pass

        # Extract parent tweet ID if this is a reply
        parent_id = None
        if is_reply and 'in_reply_to_status_id_str' in legacy:
            parent_id = legacy['in_reply_to_status_id_str']

        # Parse created_at with fallback
        created_at_str = legacy.get('created_at', '')
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S %z %Y')
            except ValueError:
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        return TwitterTweet(
            tweet_id=tweet_data.get('rest_id', ''),
            author_username=author_username,
            text=text,
            likes=legacy.get('favorite_count', 0),
            retweets=legacy.get('retweet_count', 0),
            replies_count=legacy.get('reply_count', 0),
            created_at=created_at,
            url=f"https://twitter.com/{author_username}/status/{tweet_data.get('rest_id', '')}",
            is_reply=is_reply,
            parent_tweet_id=parent_id,
        )

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def collect_thread(self, url: str) -> TwitterThread:
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
                # Create async helper to collect tweets
                async def _collect_tweets():
                    tweets_list = []
                    result = scraper.tweets_details([int(tweet_id)])

                    # Handle both async iterator and list return types
                    # (twitter-api-client returns different types based on auth state)
                    if hasattr(result, '__aiter__'):
                        # It's an async iterator - iterate normally
                        async for tweet in result:
                            tweets_list.append(tweet)
                    elif isinstance(result, list):
                        # Already a list (happens with some auth failures)
                        tweets_list = result
                    else:
                        # Try to convert to list as fallback
                        logger.warning(f"Unexpected type from tweets_details: {type(result)}")
                        tweets_list = list(result) if result else []

                    return tweets_list

                # Run in a separate thread to avoid conflict with any
                # already-running event loop (e.g., CrewAI Flow)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    tweet_details = executor.submit(asyncio.run, _collect_tweets()).result()

                # Diagnostic logging to trace data flow
                logger.info(f"[DIAG] API returned {len(tweet_details) if tweet_details else 0} raw response objects for {tweet_id}")
                if tweet_details:
                    first = tweet_details[0]
                    if isinstance(first, dict):
                        logger.debug(f"[DIAG] First response keys: {list(first.keys())}")
                    else:
                        logger.warning(f"[DIAG] Unexpected response type: {type(first)}")

                # Extract actual tweet data and replies from nested GraphQL responses
                extracted_main = None
                all_replies = []
                if tweet_details:
                    for response in tweet_details:
                        main_tweet, replies = self._extract_tweets_from_response(response)
                        if main_tweet:
                            extracted_main = main_tweet
                            logger.debug(f"[DIAG] Extracted main tweet {main_tweet.get('rest_id')}: likes={main_tweet.get('legacy', {}).get('favorite_count')}")
                        if replies:
                            all_replies.extend(replies)
                    logger.info(f"[DIAG] Extracted main tweet + {len(all_replies)} replies from {len(tweet_details)} responses")
                    # Replace tweet_details with list containing just the main tweet for compatibility
                    tweet_details = [extracted_main] if extracted_main else []

            except Exception as fetch_error:
                error_type = type(fetch_error).__name__
                error_msg = str(fetch_error)
                logger.error(f"tweets_details() API call failed: {error_type}: {error_msg}")

                # Check for authentication/JSON errors
                if "JSONDecodeError" in error_type or "JSONDecodeError" in error_msg:
                    logger.error(
                        "⚠️  TWITTER AUTHENTICATION FAILED - Non-JSON Response\n"
                        "\n"
                        "Possible causes:\n"
                        "  1. Account rate limited or suspended\n"
                        "  2. Tweet deleted or made private\n"
                        "  3. Twitter anti-bot detection triggered\n"
                        "  4. Invalid or expired credentials/cookies\n"
                        "\n"
                        "Recommended solutions:\n"
                        "  1. Export cookies manually from browser:\n"
                        "     - Log into twitter.com in your browser\n"
                        "     - Open DevTools (F12) → Application → Cookies\n"
                        "     - Copy 'ct0' and 'auth_token' cookie values\n"
                        f"     - Save to: {self._cookies_cache_path}\n"
                        "       Format: {\"ct0\": \"value1\", \"auth_token\": \"value2\"}\n"
                        "  2. Check if your Twitter account has security challenges\n"
                        "  3. Wait 15-30 minutes if rate limited"
                    )
                elif "NoneType" in error_msg or "has no attribute 'json'" in error_msg:
                    logger.error(
                        "⚠️  TWITTER API RETURNED EMPTY RESPONSE\n"
                        "\n"
                        "This typically means:\n"
                        "  - Authentication failed completely\n"
                        "  - Twitter blocked the request\n"
                        "  - Cookies are invalid/expired\n"
                        "\n"
                        "Action required: Export cookies manually from browser login\n"
                        f"Save to: {self._cookies_cache_path}"
                    )
                elif "TypeError" in error_type and "__aiter__" in error_msg:
                    logger.error(
                        "⚠️  ASYNC ITERATION ERROR\n"
                        "\n"
                        "The twitter-api-client library returned unexpected data type.\n"
                        "This can happen when authentication fails.\n"
                        "\n"
                        "Check authentication and try manual cookie export."
                    )

                raise

            if not tweet_details:
                raise ValueError(f"Could not fetch tweet: {url}")

            logger.debug(f"Received {len(tweet_details)} tweet objects from API")
            logger.info(f"[DIAG] Processing tweet {tweet_id}: {len(tweet_details)} objects, proceeding to parse")

            # The first tweet is the original
            original_data = tweet_details[0]
            original_tweet = self.parse_tweet(original_data, is_reply=False)

            # Parse replies from extracted conversation threads
            replies = []
            for reply_data in all_replies:
                try:
                    reply_tweet = self.parse_tweet(reply_data, is_reply=True)
                    replies.append(reply_tweet)
                except Exception as e:
                    logger.debug(f"Failed to parse reply {reply_data.get('rest_id', 'unknown')}: {e}")

            if replies:
                logger.info(f"[DIAG] Parsed {len(replies)} replies from conversation threads")

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

    def collect_threads(self, urls: list[str]) -> list[TwitterThread]:
        """
        Collect multiple Twitter threads with quality filtering.

        Args:
            urls: List of Twitter post URLs

        Returns:
            List of TwitterThread models that meet quality thresholds
        """
        threads = []
        consecutive_errors = 0

        for i, url in enumerate(urls):
            try:
                # Rate limiting between requests (long delay to avoid Twitter blocks)
                if i > 0:
                    import random
                    delay = 10.0 + random.uniform(0, 5.0)  # 10-15 seconds with jitter
                    time.sleep(delay)

                thread = self.collect_thread(url)

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

                consecutive_errors = 0  # Reset on successful fetch

            except Exception as e:
                logger.error(f"Skipping thread {url} due to error: {type(e).__name__}: {e}")
                import traceback
                logger.debug(f"[DIAG] Full traceback:\n{traceback.format_exc()}")

                consecutive_errors += 1
                if consecutive_errors >= 5:
                    logger.warning(
                        f"⚠️ Stopping Twitter collection after {consecutive_errors} consecutive errors "
                        f"(likely rate limited). Collected {len(threads)} threads from {i+1}/{len(urls)} URLs."
                    )
                    break
                continue

        logger.info(f"Collected {len(threads)} quality Twitter threads from {len(urls)} URLs")
        return threads

    def _run(self, urls: str) -> str:
        """
        Main run method for CrewAI tool interface.

        Args:
            urls: Comma-separated list of Twitter URLs

        Returns:
            JSON string with collected threads
        """
        try:
            url_list = [url.strip() for url in urls.split(',') if url.strip()]
            threads = self.collect_threads(url_list)

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
