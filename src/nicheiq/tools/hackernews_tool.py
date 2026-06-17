"""
Hacker News collector tool using the free Algolia HN Search API.

No API key required. Returns SocialPost objects for the generic source pipeline.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests
from crewai.tools import BaseTool
from loguru import logger
from pydantic import Field

from ..config.settings import settings
from ..models.social_content import SocialPost, SocialResponse

if TYPE_CHECKING:
    from ..models.research_state import SearchResultItem

# Algolia HN API endpoints
_SEARCH_URL = "http://hn.algolia.com/api/v1/search"
_ITEM_URL = "http://hn.algolia.com/api/v1/items"

# Validate story IDs: alphanumeric only (prevent path traversal)
_VALID_STORY_ID = re.compile(r"^[a-zA-Z0-9]+$")

# Retry settings
_MAX_RETRIES = 2
_RETRY_DELAY = 2.0


class HackerNewsCollectorTool(BaseTool):
    """Collect Hacker News stories and comments via Algolia API."""

    name: str = "HackerNewsCollectorTool"
    description: str = (
        "Searches Hacker News for relevant discussions and collects "
        "stories with their comment trees. Free API, no auth needed."
    )

    def search_stories(
        self,
        queries: list[str],
        niche_description: str = "",
        min_points: int | None = None,
        min_comments: int | None = None,
        max_results_per_query: int = 10,
        max_total: int = 30,
    ) -> list[dict]:
        """Search HN via Algolia and return story metadata.

        Args:
            queries: Search queries to run.
            niche_description: Niche description for relevance filtering.
            min_points: Minimum story points (defaults to settings.min_hn_points).
            min_comments: Minimum comments (defaults to settings.min_hn_comments).
            max_results_per_query: Max results per query.
            max_total: Max total unique stories across all queries.

        Returns:
            List of story dicts with keys: objectID, title, url, points, num_comments, created_at_i.
        """
        if min_points is None:
            min_points = settings.min_hn_points
        if min_comments is None:
            min_comments = settings.min_hn_comments

        seen_ids: set[str] = set()
        stories: list[dict] = []

        for query in queries:
            if len(stories) >= max_total:
                break
            try:
                results = self._search_algolia(
                    query, max_results=max_results_per_query,
                )
            except Exception as exc:
                logger.warning(f"[HN] Search failed for '{query}': {exc}")
                continue

            for hit in results:
                story_id = str(hit.get("objectID", ""))
                if not story_id or story_id in seen_ids:
                    continue
                # Quality filter
                points = int(hit.get("points") or 0)
                num_comments = int(hit.get("num_comments") or 0)
                if points < min_points or num_comments < min_comments:
                    continue
                # Relevance filter (stemmed token Jaccard)
                if niche_description:
                    from ..utils.validation.dedup import token_jaccard
                    title = str(hit.get("title", ""))
                    relevance = token_jaccard(niche_description, title)
                    if relevance < 0.05:
                        logger.debug(f"[HN] Skipping irrelevant: {title[:60]} (relevance={relevance:.3f})")
                        continue
                seen_ids.add(story_id)
                stories.append(hit)
                if len(stories) >= max_total:
                    break

        logger.info(f"[HN] Found {len(stories)} stories from {len(queries)} queries")
        return stories

    def collect_posts(self, stories: list[dict]) -> list[SocialPost]:
        """Fetch full story data with comment trees.

        Args:
            stories: Story dicts from search_stories().

        Returns:
            List of SocialPost objects with platform='hackernews'.
        """
        posts: list[SocialPost] = []
        errors = 0
        for story in stories:
            story_id = str(story.get("objectID", ""))
            if not story_id:
                continue
            try:
                post = self._fetch_story(story_id, story_meta=story)
                if post:
                    posts.append(post)
            except Exception as exc:
                errors += 1
                logger.warning(f"[HN] Failed to fetch story {story_id}: {exc}")
                if errors >= 5:
                    logger.warning("[HN] Too many errors, stopping collection")
                    break

        logger.info(f"[HN] Collected {len(posts)} stories with comments ({errors} errors)")
        return posts

    def search_and_collect(
        self,
        queries: list[str],
        niche_description: str = "",
        min_points: int | None = None,
        min_hn_comments: int | None = None,
        max_results_per_query: int = 10,
        max_total: int = 25,
    ) -> list[SocialPost]:
        """Search and collect in one step (convenience method for Stage 2)."""
        stories = self.search_stories(
            queries=queries,
            niche_description=niche_description,
            min_points=min_points,
            min_comments=min_hn_comments,
            max_results_per_query=max_results_per_query,
            max_total=max_total,
        )
        return self.collect_posts(stories)

    def _search_algolia(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict]:
        """Execute a single Algolia HN search with retry."""
        three_years_ago = int(time.time()) - (3 * 365 * 24 * 3600)
        # Algolia's HN index only allows created_at_i in numericFilters; points
        # and num_comments were dropped from numericAttributesForFiltering and
        # now cause a 400. Points/comments thresholds are enforced client-side
        # in search_stories() instead.
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": max_results,
            "numericFilters": f"created_at_i>{three_years_ago}",
        }
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = requests.get(_SEARCH_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return data.get("hits", [])
            except requests.exceptions.HTTPError as exc:
                if resp.status_code == 429 and attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except requests.exceptions.RequestException:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise
        return []

    def _fetch_story(self, story_id: str, story_meta: dict | None = None) -> SocialPost | None:
        """Fetch a single story with its comment tree from Algolia items API."""
        # Validate story_id to prevent path traversal
        if not _VALID_STORY_ID.match(story_id):
            logger.warning(f"[HN] Invalid story ID: {story_id}")
            return None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = requests.get(f"{_ITEM_URL}/{story_id}", timeout=15)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.RequestException:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise
        else:
            return None

        title = str(data.get("title") or "")
        author = str(data.get("author") or "")
        url = str(data.get("url") or f"https://news.ycombinator.com/item?id={story_id}")
        text = str(data.get("text") or "")  # Some HN posts have body text (Ask HN, Show HN)
        points = int(data.get("points") or (story_meta or {}).get("points", 0))
        created_at_i = data.get("created_at_i") or (story_meta or {}).get("created_at_i", 0)

        # Parse comments
        children = data.get("children") or []
        responses = self._parse_comments(children, max_depth=3)
        num_comments = self._count_responses(responses)

        try:
            created_utc = datetime.fromtimestamp(int(created_at_i), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            created_utc = datetime.now(timezone.utc)

        return SocialPost(
            post_id=story_id,
            platform="hackernews",
            title=title,
            body=text,
            author=author,
            url=url,
            score=points,
            num_responses=num_comments,
            created_utc=created_utc,
            responses=responses,
            raw_engagement={"points": points, "num_comments": num_comments, "date_estimated": False},
        )

    def _parse_comments(
        self,
        children: list[dict],
        depth: int = 0,
        max_depth: int = 3,
    ) -> list[SocialResponse]:
        """Recursively parse HN comment tree into SocialResponse objects."""
        if depth > max_depth or not children:
            return []

        responses: list[SocialResponse] = []
        for child in children:
            if child.get("type") != "comment":
                continue
            text = str(child.get("text") or "").strip()
            if not text or len(text) < 20:  # Skip very short comments
                continue

            author = str(child.get("author") or "")
            comment_id = str(child.get("id") or "")
            created_at_i = child.get("created_at_i", 0)

            try:
                created_utc = datetime.fromtimestamp(int(created_at_i), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                created_utc = datetime.now(timezone.utc)

            # Recursively parse nested replies
            nested = child.get("children") or []
            replies = self._parse_comments(nested, depth=depth + 1, max_depth=max_depth)

            responses.append(SocialResponse(
                response_id=comment_id,
                author=author,
                body=text,
                score=0,  # HN comments don't expose score via API
                created_utc=created_utc,
                replies=replies,
            ))

        return responses

    @staticmethod
    def _count_responses(responses: list[SocialResponse]) -> int:
        """Recursively count total responses in a tree."""
        count = len(responses)
        for resp in responses:
            count += HackerNewsCollectorTool._count_responses(resp.replies)
        return count

    def _run(self, queries: str) -> str:
        """CrewAI tool interface. Accepts comma-separated search queries."""
        query_list = [q.strip() for q in queries.split(",") if q.strip()]
        if not query_list:
            return "No queries provided"
        posts = self.search_and_collect(query_list)
        return f"Collected {len(posts)} Hacker News stories"
