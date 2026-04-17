"""Tests for source attribution: fuzzy matching, evidence appendix.

NOTE: The _extract_and_clean_sources tests were removed because that method
is now dead code - Task 4 (quote enrichment) handles source attribution via
vector search with post_id in metadata, not [source: ID] tags in text.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from nicheiq.models.pain_point import PainPoint
from nicheiq.report.report_generator import ReportGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pain_point(
    title: str = "Test Pain",
    quotes: list[str] | None = None,
    source_ids: list[str] | None = None,
) -> PainPoint:
    """Create a PainPoint for evidence appendix tests."""
    return PainPoint(
        title=title,
        description="Test description",
        mention_count=10,
        severity_score=0.7,
        willingness_to_pay=0.5,
        opportunity_level="high",
        representative_quotes=quotes or ["Quote one", "Quote two"],
        source_platforms=["Reddit"],
        categories=["General"],
        source_post_ids=source_ids or ["post1", "post2"],
    )


# ---------------------------------------------------------------------------
# Tests: ReportGenerator fuzzy matching helpers
# ---------------------------------------------------------------------------

class TestFuzzyMatchQuote:
    """Test ReportGenerator._fuzzy_match_quote static method."""

    def test_fuzzy_match_substring(self):
        """Verbatim substring match returns correct post_id."""
        content_index = [
            ("this is a long comment about spreadsheets being terrible for tracking expenses", "post_abc"),
            ("another unrelated comment about weather patterns and forecasting", "post_xyz"),
        ]
        result = ReportGenerator._fuzzy_match_quote(
            "spreadsheets being terrible for tracking expenses",
            content_index,
        )
        assert result == "post_abc"

    def test_fuzzy_match_short_quote_skipped(self):
        """Quotes < 30 chars return None."""
        content_index = [
            ("short content that matches exactly this short quote", "post1"),
        ]
        result = ReportGenerator._fuzzy_match_quote(
            "short quote",  # < 30 chars
            content_index,
        )
        assert result is None

    def test_fuzzy_match_no_match(self):
        """Unrelated quote returns None."""
        content_index = [
            ("this is about cooking recipes and ingredient substitutions", "post1"),
            ("discussion about gardening tools and soil quality improvements", "post2"),
        ]
        result = ReportGenerator._fuzzy_match_quote(
            "this quote is about software engineering and deployment pipelines",
            content_index,
        )
        assert result is None

    def test_fuzzy_match_short_content_ignored(self):
        """Content < 30 chars in index doesn't cause false positive."""
        # Short content is filtered at index build time, but test the matcher itself
        content_index = [
            ("spreadsheets", "post_short"),  # Would match but content is short
        ]
        # Even with content_index having short entries, the quote normalization
        # and min_length check on the quote side prevents short matches
        result = ReportGenerator._fuzzy_match_quote(
            "spreadsheets",  # Also short
            content_index,
        )
        assert result is None

    def test_fuzzy_match_strips_quotes_and_ellipsis(self):
        """Leading/trailing quote marks and ellipsis are stripped before matching."""
        content_index = [
            ("i spent three hours trying to configure this tool and still failed", "post_match"),
        ]
        result = ReportGenerator._fuzzy_match_quote(
            '"I spent three hours trying to configure this tool and still failed"',
            content_index,
        )
        assert result == "post_match"


# ---------------------------------------------------------------------------
# Tests: ReportGenerator helpers
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_basic_normalization(self):
        assert ReportGenerator._normalize_text("  Hello   World  ") == "hello world"

    def test_newlines_collapsed(self):
        assert ReportGenerator._normalize_text("line1\n  line2\t\tline3") == "line1 line2 line3"


class TestFlattenComments:
    def test_flat_list(self):
        c1 = MagicMock()
        c1.replies = []
        c2 = MagicMock()
        c2.replies = []
        result = ReportGenerator._flatten_comments([c1, c2])
        assert len(result) == 2

    def test_nested_replies(self):
        child = MagicMock()
        child.replies = []
        parent = MagicMock()
        parent.replies = [child]
        result = ReportGenerator._flatten_comments([parent])
        assert len(result) == 2  # parent + child

    def test_max_depth_guard(self):
        """Recursion stops at depth 5."""
        deep = MagicMock()
        deep.replies = []
        current = deep
        for _ in range(10):
            wrapper = MagicMock()
            wrapper.replies = [current]
            current = wrapper
        result = ReportGenerator._flatten_comments([current])
        # Should not crash and should stop at depth 5
        assert len(result) <= 7  # 6 levels (0-5) + 1 for the deepest


# ---------------------------------------------------------------------------
# Tests: Evidence appendix integration (parallel IDs → QuoteSource)
# ---------------------------------------------------------------------------

class TestEvidenceAppendixParallelIds:
    """Integration test: parallel IDs produce correct QuoteSource objects."""

    def test_evidence_appendix_parallel_ids(self):
        """Parallel source IDs map correctly to QuoteSource post_id fields."""
        # Build minimal state
        state = MagicMock()

        # Social content with one Reddit post
        post = MagicMock()
        post.post_id = "real_post_1"
        post.title = "Test Post"
        post.subreddit = "test"
        post.score = 100
        post.num_comments = 10
        post.url = "https://reddit.com/r/test/1"
        post.created_utc = datetime(2025, 1, 1, tzinfo=timezone.utc)
        post.selftext = "This is the post body text for testing purposes"
        post.comments = []

        state.social_content.reddit_posts = [post]
        state.social_content.twitter_threads = []

        # Pain point with parallel source_post_ids
        pain_point = _make_pain_point(
            title="Test Pain",
            quotes=["First cleaned quote", "Second cleaned quote", "Third cleaned quote"],
            source_ids=["real_post_1", "", "real_post_1"],
        )
        state.pain_point_analysis.pain_points = [pain_point]

        # Create generator with mocked state
        gen = ReportGenerator.__new__(ReportGenerator)
        gen.state = state
        gen.accessor = MagicMock()
        gen.score_accessor = MagicMock()

        result = gen._generate_evidence_appendix()

        assert result is not None
        assert len(result.pain_point_quote_sources) == 1

        quotes_with_sources = result.pain_point_quote_sources[0].quotes_with_sources
        assert len(quotes_with_sources) == 3

        # Tier 0: parallel ID available
        assert quotes_with_sources[0].post_id == "real_post_1"
        assert quotes_with_sources[0].source_label == "test"

        # Tier 1 or final: empty source ID, no fuzzy match → "unknown"
        # (the quote text doesn't match post body)
        assert quotes_with_sources[1].post_id == "unknown"

        # Tier 0: parallel ID available
        assert quotes_with_sources[2].post_id == "real_post_1"

    def test_evidence_appendix_fuzzy_fallback(self):
        """Empty source ID falls back to fuzzy match when quote matches content."""
        state = MagicMock()

        post = MagicMock()
        post.post_id = "matched_post"
        post.title = "Matched Post"
        post.subreddit = "matchsub"
        post.score = 50
        post.num_comments = 5
        post.url = "https://reddit.com/r/matchsub/1"
        post.created_utc = datetime(2025, 1, 1, tzinfo=timezone.utc)
        post.selftext = "This is a short body"

        # Add a comment with the exact text that will match the quote
        comment = MagicMock()
        comment.body = "I spent three hours trying to configure the deployment pipeline and it still failed miserably"
        comment.replies = []
        post.comments = [comment]

        state.social_content.reddit_posts = [post]
        state.social_content.twitter_threads = []

        pain_point = _make_pain_point(
            title="Deployment Pain",
            quotes=["I spent three hours trying to configure the deployment pipeline and it still failed miserably"],
            source_ids=[""],  # Empty - should trigger fuzzy match
        )
        state.pain_point_analysis.pain_points = [pain_point]

        gen = ReportGenerator.__new__(ReportGenerator)
        gen.state = state
        gen.accessor = MagicMock()
        gen.score_accessor = MagicMock()

        result = gen._generate_evidence_appendix()
        assert result is not None

        qs = result.pain_point_quote_sources[0].quotes_with_sources[0]
        assert qs.post_id == "matched_post"  # Fuzzy match found the source
        assert qs.source_label == "matchsub"
