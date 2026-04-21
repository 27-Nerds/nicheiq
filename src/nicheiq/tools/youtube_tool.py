"""
YouTube transcript collector tool with optional Data API enrichment.

Uses youtube-transcript-api (no API key needed) for transcripts and
Serper search results for metadata (title, view count, upload date).

When YOUTUBE_API_KEY is set, enriches posts with:
- Accurate engagement metrics (views, likes, comment count)
- Top YouTube comments as SocialResponse objects
- Channel name and exact upload date
"""

from __future__ import annotations

import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from crewai.tools import BaseTool
from loguru import logger
from pydantic import Field

from ..config.settings import settings
from ..models.social_content import SocialPost, SocialResponse
from ..utils.snippet_extraction import best_evidence_window

if TYPE_CHECKING:
    from ..models.research_state import SearchResultItem

# Video ID: exactly 11 base64url characters
_VALID_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# View count patterns in Serper snippets (e.g., "1.2M views", "45K views", "123,456 views")
_VIEWS_PATTERN = re.compile(r"([\d,.]+)\s*([KMB])?\s*views", re.IGNORECASE)
_MULTIPLIERS = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

# Tags to strip from auto-generated transcripts
_TRANSCRIPT_TAGS = re.compile(r"\[(?:Music|Applause|Laughter|Inaudible|music|applause)\]")

# YouTube Data API v3 base URL
_YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# Retry settings
_MAX_RETRIES = 2
_RETRY_DELAY = 2.0

# Transcript size limit
_MAX_TRANSCRIPT_CHARS = 5000

# Comment fetch rate limit (seconds between requests)
_COMMENT_FETCH_DELAY = 0.5

# Abort transcript collection after this many IP-block signals
_IP_BLOCK_ABORT_THRESHOLD = 3

# Message patterns that indicate YouTube is blocking the worker's IP
_IP_BLOCK_PATTERNS = re.compile(
    r"blocking requests from your ip"
    r"|ip.?blocked"
    r"|too many requests"
    r"|\b429\b"
    r"|cloudflare challenge",
    re.IGNORECASE,
)


def _looks_like_ip_block(exc: Exception) -> bool:
    """Best-effort detection of YouTube IP-block responses.

    Matches on the exception class name (RequestBlocked / IpBlocked) and on
    message patterns, so we stay robust to minor library version changes.
    """
    name = type(exc).__name__.lower()
    if "blocked" in name:
        return True
    return bool(_IP_BLOCK_PATTERNS.search(str(exc)))


def _sanitize_api_url(url: str) -> str:
    """Strip API key from URL for safe logging."""
    return re.sub(r"key=[^&]+", "key=***", url)


class YouTubeCollectorTool(BaseTool):
    """Collect YouTube video transcripts and comments for market research."""

    name: str = "YouTubeCollectorTool"
    description: str = (
        "Fetches YouTube video transcripts and comments for pain point analysis. "
        "Transcripts require no API key. Comments require YOUTUBE_API_KEY."
    )

    # Instance flag to disable API mid-run on auth/quota errors
    _api_disabled: bool = False

    def search_and_collect(
        self,
        serper_results: list,
        niche_description: str = "",
        min_views: int = 0,
        max_total: int = 25,
        niche_keywords: list[str] | None = None,
    ) -> list[SocialPost]:
        """Fetch transcripts and optionally comments for YouTube videos.

        Args:
            serper_results: SearchResultItem objects from Serper (url, title, snippet).
            niche_description: Niche description for relevance filtering.
            min_views: Minimum view count (parsed from snippet). 0 = accept all.
            max_total: Maximum videos to collect.
            niche_keywords: Keywords for sliding-window transcript extraction.

        Returns:
            List of SocialPost objects with platform='youtube'.
        """
        from ..utils.validation.dedup import token_jaccard

        self._api_disabled = False
        api_key = settings.youtube_api_key

        # Step 1: Extract candidates with relevance filtering
        candidates = []
        for result in serper_results:
            video_id = self._extract_video_id(result.url)
            if not video_id:
                continue
            views = self._parse_views_from_snippet(result.snippet or "")
            if views < min_views and min_views > 0:
                continue
            if niche_description:
                text = f"{result.title} {result.snippet or ''}"
                relevance = token_jaccard(niche_description, text)
                if relevance < 0.05:
                    logger.debug(f"[YouTube] Skipping irrelevant: {result.title[:60]} (relevance={relevance:.3f})")
                    continue
            candidates.append((video_id, result, views))
            if len(candidates) >= max_total:
                break

        if not candidates:
            logger.info("[YouTube] No valid video URLs found in Serper results")
            return []

        # Step 2: Batch fetch video stats via API (if key set)
        video_stats: dict[str, dict[str, Any]] = {}
        if api_key and not self._api_disabled:
            video_ids = [vid for vid, _, _ in candidates]
            video_stats = self._fetch_video_stats(api_key, video_ids)
            if video_stats:
                logger.info(f"[YouTube] Fetched API stats for {len(video_stats)} videos")
                # Re-filter by accurate min_views from API
                if min_views > 0:
                    before = len(candidates)
                    candidates = [
                        (vid, res, video_stats.get(vid, {}).get("views", v))
                        for vid, res, v in candidates
                        if video_stats.get(vid, {}).get("views", v) >= min_views
                    ]
                    if len(candidates) < before:
                        logger.info(f"[YouTube] Filtered {before - len(candidates)} videos below {min_views} views (API-accurate)")

        # Step 3: Parallel transcript fetching
        posts: list[SocialPost] = []
        reason_counts: Counter[str] = Counter()
        errors = 0
        ip_block_count = 0
        aborted_ip_block = False

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._fetch_and_build,
                    video_id, result, views, niche_keywords, video_stats.get(video_id),
                ): video_id
                for video_id, result, views in candidates
            }
            for future in as_completed(futures):
                video_id = futures[future]
                try:
                    post, reason = future.result()
                    reason_counts[reason] += 1
                    if post:
                        posts.append(post)
                    if reason == "ip_blocked":
                        ip_block_count += 1
                        if ip_block_count >= _IP_BLOCK_ABORT_THRESHOLD and not aborted_ip_block:
                            aborted_ip_block = True
                            pending = sum(1 for f in futures if not f.done())
                            logger.warning(
                                f"[YouTube] IP block detected ({ip_block_count} transcript requests "
                                f"refused). Aborting {pending} pending fetches — configure a residential "
                                "proxy (youtube-transcript-api supports proxy_config) to fix this."
                            )
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                    errors = 0  # reset on any non-exception result (including None)
                except Exception as exc:
                    errors += 1
                    logger.warning(f"[YouTube] Failed to fetch {video_id}: {exc}")
                    if errors >= 5:
                        logger.warning("[YouTube] Too many consecutive errors, stopping")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

        # Emit a single categorized summary when anything failed. A 100% failure
        # (the case this fix was written for) escalates to WARNING so it's visible
        # in default INFO-level worker logs.
        failures = sum(c for r, c in reason_counts.items() if r != "ok")
        if failures > 0:
            breakdown = ", ".join(
                f"{reason}={count}"
                for reason, count in reason_counts.most_common()
                if reason != "ok"
            )
            log_fn = logger.warning if len(posts) == 0 else logger.info
            log_fn(
                f"[YouTube] Transcript failures: {failures}/{len(candidates)} ({breakdown})"
            )

        # Step 4: Sequential comment fetching via API (if key set)
        if api_key and not self._api_disabled and posts:
            comment_count = 0
            for post in posts:
                if self._api_disabled:
                    break
                comments = self._fetch_top_comments(api_key, post.post_id)
                if comments:
                    post.responses = comments
                    post.num_responses = len(comments)
                    comment_count += len(comments)
                time.sleep(_COMMENT_FETCH_DELAY)
            if comment_count > 0:
                logger.info(f"[YouTube] Fetched {comment_count} comments across {len(posts)} videos")

        logger.info(f"[YouTube] Collected {len(posts)} videos from {len(candidates)} candidates")
        return posts

    def _fetch_and_build(
        self,
        video_id: str,
        serper_result: Any,
        serper_views: int,
        niche_keywords: list[str] | None,
        api_stats: dict[str, Any] | None = None,
    ) -> tuple[SocialPost | None, str]:
        """Fetch transcript and build SocialPost for a single video.

        Returns (post, reason). Reason is "ok" on success or a transcript
        failure code ("disabled", "unavailable", "no_transcript", "ip_blocked",
        "fetch_error", "empty") so callers can aggregate failure modes.
        """
        transcript, reason = self._fetch_transcript(video_id, niche_keywords)
        if transcript is None:
            return None, reason

        # Use API stats if available, otherwise fall back to Serper parsing
        if api_stats:
            views = api_stats.get("views", serper_views)
            likes = api_stats.get("likes", 0)
            comment_count = api_stats.get("comments", 0)
            author = api_stats.get("channel_title", "")
            upload_date = api_stats.get("published_at")
            date_estimated = False
            raw_engagement = {
                "views": views,
                "likes": likes,
                "comments": comment_count,
                "date_estimated": date_estimated,
            }
        else:
            views = serper_views
            author = ""
            upload_date = self._parse_date_from_snippet(serper_result.snippet or "")
            date_estimated = upload_date is None
            raw_engagement = {
                "views": views,
                "date_estimated": date_estimated,
            }

        post = SocialPost(
            post_id=video_id,
            platform="youtube",
            title=serper_result.title or f"YouTube video {video_id}",
            body=transcript,
            author=author,
            url=f"https://www.youtube.com/watch?v={video_id}",
            score=views,
            num_responses=0,  # Updated later if comments fetched
            created_utc=upload_date or datetime.now(timezone.utc),
            responses=[],  # Updated later if comments fetched
            raw_engagement=raw_engagement,
        )
        return post, "ok"

    # ==================================================================================
    # YouTube Data API v3 methods (REST, no SDK dependency)
    # ==================================================================================

    def _fetch_video_stats(
        self, api_key: str, video_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Batch fetch video statistics and snippet data via YouTube Data API.

        Single API call for up to 50 video IDs. Returns dict mapping
        video_id to {views, likes, comments, channel_title, published_at}.
        """
        if not video_ids:
            return {}

        try:
            resp = requests.get(
                f"{_YT_API_BASE}/videos",
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(video_ids[:50]),
                    "key": api_key,
                },
                timeout=15,
            )
            if not self._handle_api_response(resp, "videos.list"):
                return {}

            data = resp.json()
            stats: dict[str, dict[str, Any]] = {}
            for item in data.get("items", []):
                vid = item["id"]
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})

                published_at = None
                if snippet.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(
                            snippet["publishedAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                stats[vid] = {
                    "views": int(statistics.get("viewCount", 0)),
                    "likes": int(statistics.get("likeCount", 0)),
                    "comments": int(statistics.get("commentCount", 0)),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": published_at,
                }
            return stats

        except requests.exceptions.RequestException as exc:
            logger.warning(f"[YouTube API] videos.list request failed: {exc}")
            return {}

    def _fetch_top_comments(
        self, api_key: str, video_id: str,
    ) -> list[SocialResponse]:
        """Fetch top comments for a video via YouTube Data API.

        Returns list of SocialResponse objects, filtered by quality settings.
        Sequential call (not parallel) to respect rate limits.
        """
        from ..crews.pain_point_crew import _sanitize_social_content

        max_results = settings.max_youtube_comments_per_video
        min_likes = settings.min_youtube_comment_likes
        min_length = settings.min_youtube_comment_length

        try:
            resp = requests.get(
                f"{_YT_API_BASE}/commentThreads",
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(max_results * 2, 100),  # fetch extra to account for filtering
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": api_key,
                },
                timeout=15,
            )
            if not self._handle_api_response(resp, "commentThreads.list"):
                return []

            data = resp.json()
            responses: list[SocialResponse] = []

            for item in data.get("items", []):
                if len(responses) >= max_results:
                    break

                snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                text = snippet.get("textDisplay", "").strip()
                like_count = int(snippet.get("likeCount", 0))
                author = snippet.get("authorDisplayName", "")
                comment_id = item.get("id", "")

                # Quality filters
                if len(text) < min_length:
                    continue
                if like_count < min_likes:
                    continue

                # Sanitize content
                text = _sanitize_social_content(text)
                if not text.strip():
                    continue

                published_at = datetime.now(timezone.utc)
                if snippet.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(
                            snippet["publishedAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                responses.append(SocialResponse(
                    response_id=comment_id,
                    author=author,
                    body=text,
                    score=like_count,
                    created_utc=published_at,
                    replies=[],  # Skip reply threads to conserve quota
                ))

            return responses

        except requests.exceptions.RequestException as exc:
            logger.warning(f"[YouTube API] commentThreads.list failed for {video_id}: {exc}")
            return []

    def _handle_api_response(self, resp: requests.Response, endpoint: str) -> bool:
        """Handle YouTube API response, checking for errors.

        Returns True if response is OK, False if should skip/fallback.
        Sets _api_disabled on fatal errors (invalid key, quota exceeded).
        """
        if resp.status_code == 200:
            return True

        # Parse error reason from response
        reason = ""
        try:
            error_data = resp.json()
            errors = error_data.get("error", {}).get("errors", [])
            if errors:
                reason = errors[0].get("reason", "")
        except Exception:
            pass

        safe_url = _sanitize_api_url(resp.url)

        if reason == "commentsDisabled":
            logger.debug(f"[YouTube API] Comments disabled for video ({endpoint})")
            return False

        if reason in ("keyInvalid", "forbidden", "accessNotConfigured"):
            logger.warning(f"[YouTube API] API key invalid or forbidden ({reason}). Disabling API for this run.")
            self._api_disabled = True
            return False

        if reason in ("quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded", "userRateLimitExceeded"):
            logger.warning(f"[YouTube API] Rate/quota limit hit ({reason}). Disabling API for this run.")
            self._api_disabled = True
            return False

        logger.warning(f"[YouTube API] {endpoint} returned {resp.status_code} ({reason}): {safe_url}")
        return False

    # ==================================================================================
    # Transcript and metadata parsing (no API key needed)
    # ==================================================================================

    def _extract_video_id(self, url: str) -> str | None:
        """Parse and validate YouTube video ID from URL."""
        if not url:
            return None

        # youtube.com/watch?v=ID
        match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
        if match:
            vid = match.group(1)
            if _VALID_VIDEO_ID.match(vid):
                return vid

        # youtu.be/ID
        match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
        if match:
            vid = match.group(1)
            if _VALID_VIDEO_ID.match(vid):
                return vid

        return None

    def _parse_views_from_snippet(self, snippet: str) -> int:
        """Parse view count from Serper snippet text."""
        match = _VIEWS_PATTERN.search(snippet)
        if not match:
            return 0
        try:
            num_str = match.group(1).replace(",", "")
            num = float(num_str)
            suffix = (match.group(2) or "").upper()
            multiplier = _MULTIPLIERS.get(suffix, 1)
            return int(num * multiplier)
        except (ValueError, TypeError):
            return 0

    def _parse_date_from_snippet(self, snippet: str) -> datetime | None:
        """Parse absolute upload date from Serper snippet. Returns None for relative dates."""
        try:
            from dateutil.parser import parse as dateutil_parse
            date_patterns = re.findall(
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}"
                r"|\d{4}-\d{2}-\d{2}",
                snippet,
            )
            if date_patterns:
                parsed = dateutil_parse(date_patterns[0])
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
        except Exception:
            pass
        return None

    def _fetch_transcript(
        self,
        video_id: str,
        niche_keywords: list[str] | None = None,
    ) -> tuple[str | None, str]:
        """Fetch and process transcript for a YouTube video.

        Returns (text, reason). On success: (sanitized_text, "ok"). On failure:
        (None, one of "disabled", "unavailable", "no_transcript", "ip_blocked",
        "fetch_error", "empty"). Reasons are aggregated by the caller so a 100%
        failure batch produces a single diagnostic WARNING instead of silent
        DEBUG-level drops.
        """
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )

        from ..crews.pain_point_crew import _sanitize_social_content

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                api = YouTubeTranscriptApi()
                try:
                    result = api.fetch(video_id, languages=["en"])
                except NoTranscriptFound:
                    # Fallback: try auto-generated English transcript
                    transcript_list = api.list(video_id)
                    result = transcript_list.find_generated_transcript(["en"]).fetch()

                text = " ".join(snippet.text for snippet in result)
                text = _TRANSCRIPT_TAGS.sub("", text)
                text = _sanitize_social_content(text)

                if not text.strip():
                    return None, "empty"

                if len(text) > _MAX_TRANSCRIPT_CHARS and niche_keywords:
                    text = best_evidence_window(text, niche_keywords, window_words=700)
                elif len(text) > _MAX_TRANSCRIPT_CHARS:
                    text = text[:_MAX_TRANSCRIPT_CHARS]

                return text.strip(), "ok"

            except TranscriptsDisabled:
                logger.debug(f"[YouTube] Transcripts disabled for {video_id}")
                return None, "disabled"
            except VideoUnavailable:
                logger.debug(f"[YouTube] Video unavailable: {video_id}")
                return None, "unavailable"
            except NoTranscriptFound:
                logger.debug(f"[YouTube] No transcript found for {video_id}")
                return None, "no_transcript"
            except Exception as exc:
                last_exc = exc
                # IP blocks won't recover on retry — short-circuit so the caller
                # can abort before hammering the blocked IP with 24 more requests.
                if _looks_like_ip_block(exc):
                    logger.debug(
                        f"[YouTube] IP-block signal for {video_id}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return None, "ip_blocked"
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                logger.debug(f"[YouTube] Transcript fetch failed for {video_id}: {exc}")
                return None, "fetch_error"

        logger.debug(f"[YouTube] Transcript fetch exhausted retries for {video_id}: {last_exc}")
        return None, "fetch_error"

    def _run(self, urls: str) -> str:
        """CrewAI tool interface. Accepts comma-separated YouTube URLs."""
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        if not url_list:
            return "No URLs provided"

        from types import SimpleNamespace
        results = [SimpleNamespace(url=u, title="", snippet="") for u in url_list]
        posts = self.search_and_collect(results)
        return f"Collected {len(posts)} YouTube videos"
