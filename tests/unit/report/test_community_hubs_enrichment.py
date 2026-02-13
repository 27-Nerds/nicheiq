"""
Unit tests for community hubs enrichment with real subreddit data.

Tests that LLM-hallucinated r/... entries are replaced by real subreddits
from collected Reddit posts, while non-Reddit hubs are preserved.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.report.utils.state_accessors import StateAccessor


def _make_accessor(subreddit_counts: dict[str, int] | None = None) -> StateAccessor:
    """Create a StateAccessor with mocked social_content Reddit posts."""
    state = MagicMock()

    if subreddit_counts:
        posts = []
        for sub, count in subreddit_counts.items():
            for _ in range(count):
                post = MagicMock()
                post.subreddit = sub
                posts.append(post)
        state.social_content.reddit_posts = posts
    else:
        state.social_content = None

    return StateAccessor(state)


class TestGetRealCommunityHubs:
    """Test StateAccessor.get_real_community_hubs()."""

    def test_replaces_reddit_hubs_preserves_non_reddit(self):
        """Real subreddits replace r/... LLM entries; non-Reddit hubs kept."""
        accessor = _make_accessor({"entrepreneur": 5, "SaaS": 3})
        llm_hubs = ["r/SaaS", "r/indiehackers", "Indie Hackers Discord", "Startup School Slack"]

        result = accessor.get_real_community_hubs(llm_hubs)

        # Real subreddits first (sorted by count desc)
        assert result[0] == "r/entrepreneur"
        assert result[1] == "r/SaaS"
        # Non-Reddit LLM hubs preserved
        assert "Indie Hackers Discord" in result
        assert "Startup School Slack" in result
        # Hallucinated r/indiehackers gone
        assert "r/indiehackers" not in result

    def test_no_reddit_data_returns_original(self):
        """Falls back to original LLM hubs when no Reddit data exists."""
        accessor = _make_accessor(None)
        llm_hubs = ["r/SaaS", "r/indiehackers", "Indie Hackers Discord"]

        result = accessor.get_real_community_hubs(llm_hubs)

        assert result == llm_hubs

    def test_no_llm_hubs_returns_only_real(self):
        """Empty LLM hubs → only real subreddits returned."""
        accessor = _make_accessor({"python": 10, "learnprogramming": 4})

        result = accessor.get_real_community_hubs([])

        assert result == ["r/python", "r/learnprogramming"]

    def test_none_llm_hubs_returns_only_real(self):
        """None LLM hubs → only real subreddits returned."""
        accessor = _make_accessor({"python": 10})

        result = accessor.get_real_community_hubs(None)

        assert result == ["r/python"]

    def test_sorted_by_post_count_descending(self):
        """Real subreddits are sorted by post count descending."""
        accessor = _make_accessor({
            "low": 1,
            "high": 20,
            "mid": 5,
        })

        result = accessor.get_real_community_hubs([])

        assert result == ["r/high", "r/mid", "r/low"]

    def test_capped_at_10_subreddits(self):
        """At most 10 real subreddits are included."""
        subs = {f"sub{i}": 100 - i for i in range(15)}
        accessor = _make_accessor(subs)

        result = accessor.get_real_community_hubs([])

        reddit_entries = [h for h in result if h.startswith("r/")]
        assert len(reddit_entries) == 10

    def test_no_reddit_data_and_no_llm_hubs(self):
        """No data at all → empty list."""
        accessor = _make_accessor(None)

        result = accessor.get_real_community_hubs(None)

        assert result == []

    def test_case_insensitive_reddit_prefix_filter(self):
        """LLM hubs with 'R/' prefix are also filtered as Reddit entries."""
        accessor = _make_accessor({"actual": 5})
        llm_hubs = ["R/SomeSub", "r/AnotherSub", "Discord Server"]

        result = accessor.get_real_community_hubs(llm_hubs)

        assert result == ["r/actual", "Discord Server"]


class TestEnrichCommunityHubsIntegration:
    """Test _enrich_community_hubs on ReportGenerator (thin wrapper)."""

    def test_enriches_audience_mapping(self):
        """Overwrites community_hubs on final_report.audience_mapping."""
        from nicheiq.report.report_generator import ReportGenerator

        state = MagicMock()
        posts = [MagicMock(subreddit="realSub") for _ in range(3)]
        state.social_content.reddit_posts = posts

        generator = ReportGenerator.__new__(ReportGenerator)
        generator.accessor = StateAccessor(state)

        final_report = MagicMock()
        final_report.audience_mapping.community_hubs = ["r/Hallucinated", "Discord Group"]

        generator._enrich_community_hubs(final_report)

        assert final_report.audience_mapping.community_hubs == ["r/realSub", "Discord Group"]

    def test_noop_when_no_audience_mapping(self):
        """Does nothing when audience_mapping is None."""
        from nicheiq.report.report_generator import ReportGenerator

        generator = ReportGenerator.__new__(ReportGenerator)
        generator.accessor = MagicMock()

        final_report = MagicMock()
        final_report.audience_mapping = None

        generator._enrich_community_hubs(final_report)

        # accessor should never be called
        generator.accessor.get_real_community_hubs.assert_not_called()
