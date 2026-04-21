"""Tests for YouTube transcript collector tool."""

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nicheiq.tools.youtube_tool import YouTubeCollectorTool


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
    def test_end_to_end(self, mock_fetch):
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
    def test_min_views_filter(self, mock_fetch):
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
    def test_ip_block_aborts_batch(self, mock_fetch, caplog):
        """After the threshold of IP-block signals, remaining fetches are skipped."""
        mock_fetch.return_value = (None, "ip_blocked")

        # 10 distinct candidates (unique 11-char video IDs)
        video_ids = [f"vid{i:08d}" for i in range(10)]
        serper_results = [
            SimpleNamespace(
                url=f"https://www.youtube.com/watch?v={vid}",
                title=f"Video {vid}",
                snippet="100K views",
            )
            for vid in video_ids
        ]

        tool = YouTubeCollectorTool()
        posts = tool.search_and_collect(serper_results, min_views=0, max_total=10)

        # No transcripts collected
        assert len(posts) == 0
        # Abort kicks in after 3 ip_blocked signals, so not all 10 should have
        # been called. Parallelism (max_workers=4) means we may see up to
        # ~3 + workers_in_flight calls — but strictly fewer than 10.
        assert mock_fetch.call_count < 10, (
            f"Expected abort before all 10 calls, got {mock_fetch.call_count}"
        )
