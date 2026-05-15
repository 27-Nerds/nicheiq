"""
PostgreSQL-backed Reddit thread cache.

Stores fetched Reddit threads via the backend API to avoid redundant
PRAW calls when related categories need the same threads.
"""

import os
import re
from datetime import datetime, timezone

import requests
from loguru import logger

from ..models.social_content import RedditComment, RedditPost

_POST_ID_RE = re.compile(r"/comments/([a-z0-9]+)/")

# Reuse a single Session across cache calls. Each raw requests.post()
# instantiates a new urllib3 PoolManager + TLS context; on a busy worker
# this is a noticeable source of allocation churn. Session is thread-safe
# for top-level .get/.post; worker recycle (queue_consumer.py) restarts
# the process every MAX_JOBS_PER_WORKER jobs and the OS reclaims the pool.
_session = requests.Session()


def _get_backend_url() -> str:
    return os.environ.get("BACKEND_URL", "http://localhost:3001")


def _get_internal_secret() -> str:
    return os.environ.get("INTERNAL_SERVICE_SECRET", "")


def _headers() -> dict[str, str]:
    return {"x-internal-service": _get_internal_secret()}


class RedditThreadCache:
    """Cache layer that stores/retrieves Reddit threads from PostgreSQL via the backend API."""

    @staticmethod
    def _extract_post_id(url: str) -> str | None:
        """Extract Reddit post ID from a URL like .../comments/<id>/..."""
        m = _POST_ID_RE.search(url)
        return m.group(1) if m else None

    def batch_get(self, urls: list[str]) -> dict[str, RedditPost]:
        """
        Look up cached threads by URL.

        Returns:
            Dict keyed by URL -> RedditPost for cache hits.
        """
        url_to_pid: dict[str, str] = {}
        for url in urls:
            pid = self._extract_post_id(url)
            if pid:
                url_to_pid[url] = pid

        if not url_to_pid:
            return {}

        pid_to_url = {pid: url for url, pid in url_to_pid.items()}
        post_ids = list(set(url_to_pid.values()))

        # Backend API has a limit of 100 post IDs per request
        BATCH_SIZE = 100
        all_found: dict[str, dict] = {}

        for i in range(0, len(post_ids), BATCH_SIZE):
            chunk = post_ids[i:i + BATCH_SIZE]
            try:
                resp = _session.post(
                    f"{_get_backend_url()}/api/workers/reddit-threads/batch-lookup",
                    json={"postIds": chunk},
                    headers=_headers(),
                    timeout=15,
                )
                if resp.status_code >= 500:
                    logger.warning(f"[RedditCache] batch-lookup 5xx: {resp.status_code}")
                    continue
                if resp.status_code >= 400:
                    logger.error(f"[RedditCache] batch-lookup {resp.status_code}: {resp.text[:200]}")
                    continue

                data = resp.json()
                found = data.get("found", {})
                all_found.update(found)

            except requests.exceptions.RequestException as e:
                logger.warning(f"[RedditCache] batch-lookup network error: {e}")
                continue

        result: dict[str, RedditPost] = {}
        for pid, thread in all_found.items():
            url = pid_to_url.get(pid)
            if not url:
                continue
            try:
                post = self._thread_to_post(thread, url)
                result[url] = post
            except Exception as e:
                logger.warning(f"[RedditCache] Failed to parse cached thread {pid}: {e}")

        hit_count = len(result)
        miss_count = len(urls) - hit_count
        if hit_count:
            logger.info(f"[RedditCache] HIT {hit_count}, MISS {miss_count}")
        return result

    def store_post(self, post: RedditPost) -> None:
        """Store a fetched Reddit post in the cache."""
        try:
            comments_data = [c.model_dump(mode="json") for c in post.comments] if post.comments else None

            payload = {
                "postId": post.post_id,
                "url": post.url,
                "title": post.title[:500],
                "selftext": post.selftext[:40000],
                "author": post.author[:100],
                "subreddit": post.subreddit[:50],
                "score": post.score,
                "numComments": post.num_comments,
                "comments": comments_data,
                "redditCreatedAt": post.created_utc.isoformat(),
            }

            resp = _session.post(
                f"{_get_backend_url()}/api/workers/reddit-threads",
                json=payload,
                headers=_headers(),
                timeout=30,
            )
            if resp.status_code >= 500:
                logger.warning(f"[RedditCache] store 5xx: {resp.status_code}")
            elif resp.status_code >= 400:
                logger.error(f"[RedditCache] store {resp.status_code}: {resp.text[:200]}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"[RedditCache] store network error: {e}")

    @staticmethod
    def _thread_to_post(thread: dict, url: str) -> RedditPost:
        """Convert a cached thread dict back to a RedditPost model."""
        comments = []
        if thread.get("comments"):
            comments = [RedditComment.model_validate(c) for c in thread["comments"]]

        created_str = thread["redditCreatedAt"]
        if isinstance(created_str, str):
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        else:
            created = created_str

        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        return RedditPost(
            post_id=thread["postId"],
            title=thread["title"],
            selftext=thread["selftext"],
            author=thread["author"],
            subreddit=thread["subreddit"],
            score=thread["score"],
            num_comments=thread["numComments"],
            created_utc=created,
            url=url,
            comments=comments,
        )
