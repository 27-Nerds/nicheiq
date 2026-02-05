"""
Unit tests for organic_discovery_queries enrichment with validated SEO keywords.

Tests the logic added to ReportGenerator._merge_solution_enrichments() that
appends relevant tier_0 + tier_1 SEO keywords to organic_discovery_queries.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.report.report_generator import ReportGenerator


def _make_tiered_keyword(keyword: str, opportunity_score: float | None = None):
    """Create a mock TieredKeyword with .keyword and .opportunity_score."""
    kw = MagicMock()
    kw.keyword = keyword
    kw.opportunity_score = opportunity_score
    return kw


def _make_generator(
    tier_0_keywords=None,
    tier_1_keywords=None,
    seo_strategy_report_exists=True,
):
    """Create a ReportGenerator with mocked state for SEO keyword enrichment."""
    state = MagicMock()
    state.solution_selection = None
    state.competitive_analysis = None
    state.idea_generation = None
    state.social_content = None
    state.pain_point_analysis = None
    state.seo_strategy = None
    state.solution_refinement = None
    state.pricing_strategies = None

    if seo_strategy_report_exists:
        seo_report = MagicMock()
        seo_report.tier_0_keywords = tier_0_keywords
        seo_report.tier_1_keywords = tier_1_keywords or []
        state.seo_strategy_report = seo_report
    else:
        state.seo_strategy_report = None

    return ReportGenerator(state)


def _make_solution(organic_queries=None):
    """Create a real BaseSolutionIdea with organic_discovery_queries set."""
    return BaseSolutionIdea(
        solution_name="TestSolution",
        description="A test solution for unit testing",
        value_proposition="Test value proposition",
        pain_points_addressed=["pain1"],
        core_features=["feature1"],
        target_personas=["persona1"],
        organic_discovery_queries=organic_queries,
    )


class TestOrganicQueryEnrichment:
    """Tests for SEO keyword enrichment of organic_discovery_queries."""

    def test_appends_relevant_keywords_sorted_by_opportunity_score(self):
        """Relevant SEO keywords are appended after originals, highest opp score first."""
        tier_0 = [
            _make_tiered_keyword("telescope building guide", 80.0),
            _make_tiered_keyword("dobsonian telescope", 95.0),
        ]
        tier_1 = [
            _make_tiered_keyword("telescope maintenance tips", 60.0),
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=tier_1)

        solution = _make_solution(
            organic_queries=["how to build a telescope", "best telescope for beginners"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        # Original queries first
        assert queries[0] == "how to build a telescope"
        assert queries[1] == "best telescope for beginners"
        # SEO keywords appended: dobsonian (95) before building guide (80) before maintenance (60)
        assert "dobsonian telescope" in queries
        assert "telescope building guide" in queries
        assert "telescope maintenance tips" in queries
        # Order: highest opp score first among appended
        seo_appended = queries[2:]
        assert seo_appended[0] == "dobsonian telescope"
        assert seo_appended[1] == "telescope building guide"
        assert seo_appended[2] == "telescope maintenance tips"

    def test_filters_out_irrelevant_keywords(self):
        """Keywords with no word overlap with original queries are excluded."""
        tier_0 = [
            _make_tiered_keyword("telescope building kit", 90.0),  # "telescope" overlaps
            _make_tiered_keyword("portable wifi hotspot", 100.0),  # no overlap
            _make_tiered_keyword("equipment sharing platform", 85.0),  # no overlap
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        solution = _make_solution(
            organic_queries=["how to build a telescope", "astronomy club software"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        assert "telescope building kit" in queries
        assert "portable wifi hotspot" not in queries
        assert "equipment sharing platform" not in queries

    def test_case_insensitive_dedup(self):
        """Keywords already present (case-insensitive) are not duplicated."""
        tier_0 = [
            _make_tiered_keyword("Best Telescope For Beginners", 90.0),
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        solution = _make_solution(
            organic_queries=["best telescope for beginners"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        assert len(queries) == 1
        assert queries[0] == "best telescope for beginners"

    def test_no_change_when_seo_report_is_none(self):
        """No enrichment when seo_strategy_report is None."""
        gen = _make_generator(seo_strategy_report_exists=False)

        original = ["how to build a telescope", "best telescope"]
        solution = _make_solution(organic_queries=original.copy())
        result = gen._merge_solution_enrichments(solution, None, None)

        assert result.organic_discovery_queries == original

    def test_no_change_when_original_queries_empty(self):
        """No enrichment when original queries are empty list."""
        tier_0 = [_make_tiered_keyword("telescope guide", 90.0)]
        gen = _make_generator(tier_0_keywords=tier_0)

        solution = _make_solution(organic_queries=[])
        result = gen._merge_solution_enrichments(solution, None, None)

        assert result.organic_discovery_queries == []

    def test_no_change_when_original_queries_none(self):
        """No enrichment when original queries are None."""
        tier_0 = [_make_tiered_keyword("telescope guide", 90.0)]
        gen = _make_generator(tier_0_keywords=tier_0)

        solution = _make_solution(organic_queries=None)
        result = gen._merge_solution_enrichments(solution, None, None)

        assert result.organic_discovery_queries is None

    def test_respects_max_seo_append_limit(self):
        """At most 5 SEO keywords are appended."""
        tier_0 = [
            _make_tiered_keyword(f"telescope model {i}", float(100 - i))
            for i in range(10)
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        solution = _make_solution(
            organic_queries=["best telescope for viewing"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        # 1 original + 5 max appended = 6
        assert len(queries) <= 6
        assert queries[0] == "best telescope for viewing"

    def test_respects_max_total_limit(self):
        """Total queries capped at 10 (originals + appended)."""
        tier_0 = [
            _make_tiered_keyword(f"telescope type {i}", float(100 - i))
            for i in range(10)
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        original = [f"original query about telescope {i}" for i in range(8)]
        solution = _make_solution(organic_queries=original.copy())
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        assert len(queries) <= 10

    def test_no_enrichment_when_tier_keywords_empty(self):
        """No enrichment when both tier_0 and tier_1 keywords are empty."""
        gen = _make_generator(tier_0_keywords=[], tier_1_keywords=[])

        original = ["how to build a telescope"]
        solution = _make_solution(organic_queries=original.copy())
        result = gen._merge_solution_enrichments(solution, None, None)

        assert result.organic_discovery_queries == original

    def test_none_opportunity_score_sorts_to_bottom(self):
        """Keywords with None opportunity_score treated as 0.0 and sort last."""
        tier_0 = [
            _make_tiered_keyword("telescope accessories", None),
            _make_tiered_keyword("telescope building plans", 50.0),
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        solution = _make_solution(
            organic_queries=["how to build a telescope"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        assert queries[0] == "how to build a telescope"
        # building plans (50.0) before accessories (None -> 0.0)
        seo_appended = queries[1:]
        assert seo_appended[0] == "telescope building plans"
        assert seo_appended[1] == "telescope accessories"

    def test_tier_0_and_tier_1_combined_and_sorted(self):
        """Keywords from both tiers are combined and sorted by opportunity_score."""
        tier_0 = [_make_tiered_keyword("telescope optics", 70.0)]
        tier_1 = [_make_tiered_keyword("telescope mirror grinding", 90.0)]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=tier_1)

        solution = _make_solution(
            organic_queries=["how to build a telescope"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        seo_appended = queries[1:]
        # tier_1 keyword (90) should come before tier_0 (70) since sorted by score
        assert seo_appended[0] == "telescope mirror grinding"
        assert seo_appended[1] == "telescope optics"

    def test_short_words_excluded_from_relevance_check(self):
        """Words with 3 or fewer characters are not used for relevance matching."""
        tier_0 = [
            _make_tiered_keyword("the big app store", 90.0),
        ]
        gen = _make_generator(tier_0_keywords=tier_0, tier_1_keywords=[])

        solution = _make_solution(
            organic_queries=["the best telescope app"]
        )
        result = gen._merge_solution_enrichments(solution, None, None)

        queries = result.organic_discovery_queries
        # "the" (3 chars) and "app" (3 chars) are excluded from relevance terms
        # Original relevance terms: "best" (4), "telescope" (9)
        # Keyword words > 3 chars: "store" (5) — no overlap with {"best", "telescope"}
        assert "the big app store" not in queries
