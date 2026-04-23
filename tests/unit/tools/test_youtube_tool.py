"""Tests for YouTube transcript collector tool."""

import time
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nicheiq.tools.youtube_tool import YouTubeCollectorTool


@pytest.fixture(autouse=False)
def no_youtube_api():
    """Disable YouTube Data API and Webshare proxy paths so tests are hermetic."""
    with patch("nicheiq.tools.youtube_tool.settings") as mock_settings:
        mock_settings.youtube_api_key = None
        mock_settings.max_youtube_comments_per_video = 20
        mock_settings.min_youtube_comment_likes = 10
        mock_settings.min_youtube_comment_length = 50
        mock_settings.webshare_api_key = None
        mock_settings.webshare_proxy_country_codes = None
        yield mock_settings


@pytest.fixture
def proxy_pool_enabled():
    """Enable Webshare proxy path (real pool is still mocked per-test)."""
    with patch("nicheiq.tools.youtube_tool.settings") as mock_settings:
        mock_settings.youtube_api_key = None
        mock_settings.max_youtube_comments_per_video = 20
        mock_settings.min_youtube_comment_likes = 10
        mock_settings.min_youtube_comment_length = 50
        mock_settings.webshare_api_key = "TEST_KEY"
        mock_settings.webshare_proxy_country_codes = None
        yield mock_settings


class TestExtractVideoId:
    def test_standard_url(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_params(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ&t=30") == "dQw4w9WgXcQ"

    def test_shorts_rejected(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtube.com/shorts/abc123") is None

    def test_playlist_rejected(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtube.com/playlist?list=PLxyz") is None

    def test_channel_rejected(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtube.com/@someuser") is None

    def test_invalid_id_length(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("https://youtube.com/watch?v=short") is None

    def test_empty_url(self):
        tool = YouTubeCollectorTool()
        assert tool._extract_video_id("") is None


class TestParseViewsFromSnippet:
    def test_millions(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("1.2M views · 3 years ago") == 1_200_000

    def test_thousands(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("45K views") == 45_000

    def test_billions(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("1.2B views") == 1_200_000_000

    def test_plain_number(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("123,456 views") == 123_456

    def test_no_views(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("This is a great video about coding") == 0

    def test_empty_snippet(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("") == 0

    def test_case_insensitive(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_views_from_snippet("500k Views") == 500_000


class TestParseDateFromSnippet:
    def test_month_day_year(self):
        tool = YouTubeCollectorTool()
        result = tool._parse_date_from_snippet("Published Mar 15, 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_iso_format(self):
        tool = YouTubeCollectorTool()
        result = tool._parse_date_from_snippet("uploaded 2024-01-20")
        assert result is not None
        assert result.year == 2024

    def test_relative_date_returns_none(self):
        tool = YouTubeCollectorTool()
        # Relative dates are NOT parsed — falls through to sentinel
        result = tool._parse_date_from_snippet("3 months ago · 45K views")
        assert result is None

    def test_no_date(self):
        tool = YouTubeCollectorTool()
        assert tool._parse_date_from_snippet("Just a regular video description") is None


class TestFetchTranscript:
    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_successful_fetch(self, MockApi):
        # Mock the v1.x API
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance

        # Mock transcript segments (FetchedTranscriptSnippet-like objects)
        segment1 = MagicMock()
        segment1.text = "Hello everyone"
        segment2 = MagicMock()
        segment2.text = "today we discuss pricing strategies"
        mock_result = [segment1, segment2]
        mock_instance.fetch.return_value = mock_result

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript("dQw4w9WgXcQ")

        assert text is not None
        assert reason == "ok"
        assert "Hello everyone" in text
        assert "pricing strategies" in text

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_strips_music_tags(self, MockApi):
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance

        segment = MagicMock()
        segment.text = "[Music] Hello [Applause] everyone [Laughter]"
        mock_instance.fetch.return_value = [segment]

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript("dQw4w9WgXcQ")

        assert text is not None
        assert reason == "ok"
        assert "[Music]" not in text
        assert "[Applause]" not in text
        assert "Hello" in text

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_transcripts_disabled(self, MockApi):
        from youtube_transcript_api._errors import TranscriptsDisabled
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance
        mock_instance.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript("dQw4w9WgXcQ")
        assert text is None
        assert reason == "disabled"

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_ip_block_short_circuits(self, MockApi):
        """IpBlocked is detected and returns immediately without retrying."""
        from youtube_transcript_api._errors import IpBlocked
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance
        mock_instance.fetch.side_effect = IpBlocked("dQw4w9WgXcQ")

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript("dQw4w9WgXcQ")
        assert text is None
        assert reason == "ip_blocked"
        # Must not retry on an IP block — single fetch attempt
        assert mock_instance.fetch.call_count == 1

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_truncation_with_keywords(self, MockApi):
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance

        # Create a long transcript
        long_text = " ".join(["filler word"] * 500 + ["pricing strategy SaaS"] + ["more filler"] * 500)
        segment = MagicMock()
        segment.text = long_text
        mock_instance.fetch.return_value = [segment]

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript("dQw4w9WgXcQ", niche_keywords=["pricing", "SaaS"])

        assert text is not None
        assert reason == "ok"
        assert len(text) <= 6000  # window_words=700 ≈ ~5000 chars


class TestSearchAndCollect:
    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript")
    def test_end_to_end(self, mock_fetch, no_youtube_api):
        mock_fetch.return_value = ("This is a transcript about SaaS pricing.", "ok")

        serper_results = [
            SimpleNamespace(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="SaaS Pricing Guide",
                snippet="1.2M views · Mar 15, 2024",
            ),
        ]

        tool = YouTubeCollectorTool()
        posts = tool.search_and_collect(serper_results, min_views=0, max_total=5)

        assert len(posts) == 1
        post = posts[0]
        assert post.platform == "youtube"
        assert post.post_id == "dQw4w9WgXcQ"
        assert post.title == "SaaS Pricing Guide"
        assert post.score == 1_200_000
        assert "transcript" in post.body.lower()
        assert post.raw_engagement.get("views") == 1_200_000

    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript")
    def test_min_views_filter(self, mock_fetch, no_youtube_api):
        mock_fetch.return_value = ("Transcript text.", "ok")

        serper_results = [
            SimpleNamespace(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title="Low view video",
                snippet="50 views",  # below threshold
            ),
        ]

        tool = YouTubeCollectorTool()
        posts = tool.search_and_collect(serper_results, min_views=1000, max_total=5)

        assert len(posts) == 0  # filtered out

    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript")
    def test_ip_block_aborts_batch(self, mock_fetch, no_youtube_api, caplog):
        """After the threshold of IP-block signals, remaining fetches are skipped.

        Uses a slow mock so the main thread has time to process results and
        trigger the abort before the executor drains all queued futures.
        """
        def slow_ip_block(*args, **kwargs):
            time.sleep(0.05)
            return (None, "ip_blocked")
        mock_fetch.side_effect = slow_ip_block

        # 20 candidates — with max_workers=4 and cancel_futures=True on abort,
        # the majority of queued futures should never start.
        video_ids = [f"vid{i:08d}" for i in range(20)]
        serper_results = [
            SimpleNamespace(
                url=f"https://www.youtube.com/watch?v={vid}",
                title=f"Video {vid}",
                snippet="100K views",
            )
            for vid in video_ids
        ]

        tool = YouTubeCollectorTool()
        posts = tool.search_and_collect(serper_results, min_views=0, max_total=20)

        assert len(posts) == 0
        assert mock_fetch.call_count < 20, (
            f"Expected abort before all 20 calls, got {mock_fetch.call_count}"
        )


class TestProxyPoolIntegration:
    """Tests for Webshare-proxy-aware transcript fetching."""

    def test_no_pool_when_api_key_missing(self, no_youtube_api):
        tool = YouTubeCollectorTool()
        assert tool._get_proxy_pool() is None

    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript_via_pool",
           autospec=True)
    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript_direct",
           autospec=True)
    def test_dispatcher_routes_to_direct_without_pool(
        self, mock_direct, mock_pool, no_youtube_api,
    ):
        mock_direct.return_value = ("txt", "ok")
        tool = YouTubeCollectorTool()
        tool._fetch_transcript("vid00000001")
        mock_direct.assert_called_once()
        mock_pool.assert_not_called()

    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript_via_pool",
           autospec=True)
    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript_direct",
           autospec=True)
    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._get_proxy_pool")
    def test_dispatcher_routes_to_pool_when_active(
        self, mock_get_pool, mock_direct, mock_pool, proxy_pool_enabled,
    ):
        mock_get_pool.return_value = MagicMock()  # truthy = pool active
        mock_pool.return_value = ("txt", "ok")
        tool = YouTubeCollectorTool()
        tool._fetch_transcript("vid00000001")
        mock_pool.assert_called_once()
        mock_direct.assert_not_called()

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_pool_proxy_flows_to_generic_config(self, MockApi, proxy_pool_enabled):
        """GenericProxyConfig is constructed with the proxy's URL for http and https."""
        mock_instance = MagicMock()
        MockApi.return_value = mock_instance
        segment = MagicMock()
        segment.text = "transcript text"
        mock_instance.fetch.return_value = [segment]

        from nicheiq.tools.webshare_client import WebshareProxy
        proxy = WebshareProxy(address="1.2.3.4", port=8168, username="u", password="p")
        pool = MagicMock()
        pool.next_proxy.return_value = proxy

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "ok"
        # YouTubeTranscriptApi was constructed with proxy_config=GenericProxyConfig(...)
        _, kwargs = MockApi.call_args
        config = kwargs.get("proxy_config")
        assert config is not None
        assert config.http_url == config.https_url, "Both must be set for HTTPS targets"
        assert "u:p@1.2.3.4:8168" in config.http_url

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_ip_block_rotates_proxy(self, MockApi, proxy_pool_enabled):
        """First proxy raises IpBlocked, second returns text → returns ok."""
        from youtube_transcript_api._errors import IpBlocked
        from nicheiq.tools.webshare_client import WebshareProxy

        # Two api instances: first raises, second succeeds
        bad_api = MagicMock()
        bad_api.fetch.side_effect = IpBlocked("blocked")
        good_api = MagicMock()
        seg = MagicMock()
        seg.text = "good transcript"
        good_api.fetch.return_value = [seg]
        MockApi.side_effect = [bad_api, good_api]

        p1 = WebshareProxy("1.1.1.1", 1111, "u1", "p1")
        p2 = WebshareProxy("2.2.2.2", 2222, "u2", "p2")
        pool = MagicMock()
        pool.next_proxy.side_effect = [p1, p2]

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "ok"
        assert text is not None
        pool.mark_blocked.assert_called_once_with(p1)

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_all_proxies_blocked_returns_ip_blocked(self, MockApi, proxy_pool_enabled):
        from youtube_transcript_api._errors import IpBlocked
        from nicheiq.tools.webshare_client import WebshareProxy

        bad_api = MagicMock()
        bad_api.fetch.side_effect = IpBlocked("blocked")
        MockApi.return_value = bad_api

        p1 = WebshareProxy("1.1.1.1", 1, "u", "p")
        p2 = WebshareProxy("2.2.2.2", 2, "u", "p")
        pool = MagicMock()
        # Two proxies, then None (exhausted). _PROXY_RETRY_ATTEMPTS=3 so 3 calls.
        pool.next_proxy.side_effect = [p1, p2, None]

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert text is None
        assert reason == "ip_blocked"
        # Both proxies marked blocked
        assert pool.mark_blocked.call_count == 2

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_single_proxy_remaining_does_not_retry_itself(self, MockApi, proxy_pool_enabled):
        """Pool of 1: the tried-set must prevent retrying the same proxy 3 times."""
        from youtube_transcript_api._errors import IpBlocked
        from nicheiq.tools.webshare_client import WebshareProxy

        bad_api = MagicMock()
        bad_api.fetch.side_effect = IpBlocked("blocked")
        MockApi.return_value = bad_api

        p = WebshareProxy("1.1.1.1", 1, "u", "p")
        # Cycle of 1 would naively yield p every time.
        pool = MagicMock()
        pool.next_proxy.side_effect = [p, p, p]  # cycle returns same proxy

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "ip_blocked"
        # First proxy attempted, marked blocked once; then tried-set short-circuits.
        assert bad_api.fetch.call_count == 1, (
            f"Expected exactly 1 fetch (first proxy), got {bad_api.fetch.call_count}"
        )
        assert pool.mark_blocked.call_count == 1

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_pool_smaller_than_retry_attempts(self, MockApi, proxy_pool_enabled):
        """2 distinct proxies + _PROXY_RETRY_ATTEMPTS=3 → 3rd slot sees None and returns ip_blocked."""
        from youtube_transcript_api._errors import IpBlocked
        from nicheiq.tools.webshare_client import WebshareProxy

        bad_api = MagicMock()
        bad_api.fetch.side_effect = IpBlocked("blocked")
        MockApi.return_value = bad_api

        p1 = WebshareProxy("1.1.1.1", 1, "u", "p")
        p2 = WebshareProxy("2.2.2.2", 2, "u", "p")
        pool = MagicMock()
        pool.next_proxy.side_effect = [p1, p2, None]

        tool = YouTubeCollectorTool()
        _, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "ip_blocked"
        assert bad_api.fetch.call_count == 2
        assert pool.mark_blocked.call_count == 2

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_non_block_error_does_not_rotate(self, MockApi, proxy_pool_enabled):
        """TranscriptsDisabled → return disabled, don't mark_blocked."""
        from youtube_transcript_api._errors import TranscriptsDisabled
        from nicheiq.tools.webshare_client import WebshareProxy

        api = MagicMock()
        api.fetch.side_effect = TranscriptsDisabled("vid00000001")
        MockApi.return_value = api

        p = WebshareProxy("1.1.1.1", 1, "u", "p")
        pool = MagicMock()
        pool.next_proxy.return_value = p

        tool = YouTubeCollectorTool()
        text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "disabled"
        pool.mark_blocked.assert_not_called()
        # Only ONE fetch attempt — non-block error short-circuits
        assert api.fetch.call_count == 1

    def test_build_transcript_api_failure_returns_fetch_error(self, proxy_pool_enabled):
        """Construct error falls through to fetch_error, no rotation, no mark_blocked."""
        from nicheiq.tools.webshare_client import WebshareProxy

        p = WebshareProxy("1.1.1.1", 1, "u", "p")
        pool = MagicMock()
        pool.next_proxy.return_value = p

        tool = YouTubeCollectorTool()
        with patch.object(
            YouTubeCollectorTool, "_build_transcript_api",
            side_effect=RuntimeError("simulated construct error"),
        ):
            text, reason = tool._fetch_transcript_via_pool("vid00000001", None, pool)

        assert reason == "fetch_error"
        assert text is None
        pool.mark_blocked.assert_not_called()

    def test_api_stats_not_routed_through_proxy(self, proxy_pool_enabled):
        """_fetch_video_stats hits googleapis.com directly — never takes proxy."""
        tool = YouTubeCollectorTool()
        with patch("nicheiq.tools.youtube_tool.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"items": []}
            mock_resp.url = "https://www.googleapis.com/youtube/v3/videos"
            mock_get.return_value = mock_resp
            tool._fetch_video_stats("fake_key", ["vid00000001"])
        _, kwargs = mock_get.call_args
        assert "proxies" not in kwargs, (
            "API stats (googleapis.com) must never be routed through proxy"
        )

    @patch("nicheiq.tools.youtube_tool.YouTubeCollectorTool._fetch_transcript")
    def test_adaptive_abort_warn_copy_with_pool(
        self, mock_fetch, proxy_pool_enabled, caplog,
    ):
        """When pool is active, abort WARN references 'proxy pool exhausted'."""
        import logging

        def slow_ip_block(*args, **kwargs):
            time.sleep(0.05)
            return (None, "ip_blocked")
        mock_fetch.side_effect = slow_ip_block

        serper_results = [
            SimpleNamespace(
                url=f"https://www.youtube.com/watch?v=vid{i:08d}",
                title=f"v{i}",
                snippet="100K views",
            )
            for i in range(10)
        ]

        fake_pool = MagicMock()
        fake_pool.size.return_value = 5

        tool = YouTubeCollectorTool()

        # Bridge loguru → caplog so pytest's caplog can see loguru warnings.
        from loguru import logger as loguru_logger
        sink_id = loguru_logger.add(
            lambda msg: caplog.handler.emit(
                logging.LogRecord(
                    name="youtube", level=logging.WARNING, pathname="", lineno=0,
                    msg=msg, args=(), exc_info=None,
                )
            ),
            level="WARNING",
        )
        try:
            with patch.object(
                YouTubeCollectorTool, "_get_proxy_pool", return_value=fake_pool,
            ):
                # _proxy_pool is set by _get_proxy_pool in real code; replicate here
                # since we've mocked the method.
                tool._proxy_pool = fake_pool
                caplog.set_level(logging.WARNING)
                tool.search_and_collect(serper_results, min_views=0, max_total=10)
        finally:
            loguru_logger.remove(sink_id)

        all_msgs = " ".join(r.getMessage() for r in caplog.records)
        assert "proxy pool exhausted" in all_msgs.lower(), (
            f"Expected proxy-aware abort WARN. Got: {all_msgs}"
        )
        assert "configure WEBSHARE_API_KEY" not in all_msgs
