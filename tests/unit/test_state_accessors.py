"""
Tests for state accessor utilities.

Note: This test file focuses on the basic accessor patterns.
Complex extraction logic is tested via integration tests.
"""

import logging

import pytest
from unittest.mock import MagicMock
from nicheiq.report.utils.state_accessors import StateAccessor


class TestStateAccessorInitialization:
    """Tests for StateAccessor initialization."""

    def test_initialize_with_valid_state(self):
        """Test initializing accessor with valid ResearchState."""
        mock_state = MagicMock()
        accessor = StateAccessor(mock_state)

        assert accessor.state is mock_state


class TestBasicStageDataExtraction:
    """Tests for basic stage data extraction."""

    def test_get_pain_point_analysis_when_present(self):
        """Test getting pain point analysis when data is present."""
        mock_analysis = MagicMock()
        mock_state = MagicMock()
        mock_state.pain_point_analysis = mock_analysis

        accessor = StateAccessor(mock_state)
        result = accessor.get_pain_point_analysis()

        assert result is mock_analysis

    def test_get_pain_point_analysis_when_none(self):
        """Test getting pain point analysis when None."""
        mock_state = MagicMock()
        mock_state.pain_point_analysis = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_pain_point_analysis()

        assert result is None

    def test_get_idea_generation_when_present(self):
        """Test getting idea generation when present."""
        mock_ideas = MagicMock()
        mock_state = MagicMock()
        mock_state.idea_generation = mock_ideas  # Correct attribute name

        accessor = StateAccessor(mock_state)
        result = accessor.get_idea_generation()

        assert result is mock_ideas

    def test_get_competitive_analysis_when_present(self):
        """Test getting competitive analysis when present."""
        mock_competitive = MagicMock()
        mock_state = MagicMock()
        mock_state.competitive_analysis = mock_competitive

        accessor = StateAccessor(mock_state)
        result = accessor.get_competitive_analysis()

        assert result is mock_competitive

    def test_get_seo_strategy_when_present(self):
        """Test getting SEO strategy when present."""
        mock_seo = MagicMock()
        mock_state = MagicMock()
        mock_state.seo_strategy_report = mock_seo

        accessor = StateAccessor(mock_state)
        result = accessor.get_seo_strategy()

        assert result is mock_seo

    def test_get_social_content_when_present(self):
        """Test getting social content when present."""
        mock_social = MagicMock()
        mock_state = MagicMock()
        mock_state.social_content = mock_social

        accessor = StateAccessor(mock_state)
        result = accessor.get_social_content()

        assert result is mock_social


class TestSortedPainPoints:
    """Tests for sorted pain points extraction."""

    def test_get_sorted_pain_points_returns_empty_when_no_analysis(self):
        """Test that sorted pain points returns empty list when no analysis."""
        mock_state = MagicMock()
        mock_state.pain_point_analysis = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_sorted_pain_points()

        assert result == []
        assert isinstance(result, list)

    def test_get_sorted_pain_points_when_present(self):
        """Test sorted pain points when data is present."""
        # Create mock pain points
        pp1 = MagicMock()
        pp1.severity_score = 0.8
        pp1.willingness_to_pay = 0.7

        pp2 = MagicMock()
        pp2.severity_score = 0.9
        pp2.willingness_to_pay = 0.8

        mock_state = MagicMock()
        mock_state.pain_point_analysis = MagicMock()
        mock_state.pain_point_analysis.pain_points = [pp1, pp2]

        accessor = StateAccessor(mock_state)
        result = accessor.get_sorted_pain_points()

        # Should return a list
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_formatted_pain_points_scores_scaled_to_10(self):
        """Scores are 0.0-1.0 internally but must display as X.Y/10."""
        pp = MagicMock()
        pp.title = "Slow Onboarding"
        pp.description = "Users drop off during setup"
        pp.severity_score = 0.75
        pp.willingness_to_pay = 0.6

        mock_state = MagicMock()
        mock_state.pain_point_analysis = MagicMock()
        mock_state.pain_point_analysis.pain_points = [pp]

        accessor = StateAccessor(mock_state)
        result = accessor.get_formatted_pain_points()

        assert len(result) == 1
        assert "Severity: 7.5/10" in result[0]
        assert "WTP: 6.0/10" in result[0]
        assert "Severity: 0.7/10" not in result[0]
        assert "WTP: 0.6/10" not in result[0]


class TestSelectionDataExtraction:
    """Tests for solution selection data extraction."""

    def test_get_selected_solution_name_when_present(self):
        """Test getting selected solution name when selection exists."""
        mock_state = MagicMock()
        mock_state.solution_selection = MagicMock()
        mock_state.solution_selection.selected_solution_name = "Best Solution"

        accessor = StateAccessor(mock_state)
        result = accessor.get_selected_solution_name()

        assert result == "Best Solution"

    def test_get_selected_solution_name_when_no_selection(self):
        """Test getting selected solution name when no selection made."""
        mock_state = MagicMock()
        mock_state.solution_selection = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_selected_solution_name()

        # Returns default message
        assert result == "No solution selected"

    def test_get_selection_rationale_when_present(self):
        """Test getting selection rationale when present."""
        mock_state = MagicMock()
        mock_state.solution_selection = MagicMock()
        mock_state.solution_selection.selection_rationale = "Chosen because..."

        accessor = StateAccessor(mock_state)
        result = accessor.get_selection_rationale()

        assert result == "Chosen because..."

    def test_get_selection_rationale_when_no_selection(self):
        """Test getting selection rationale when no selection made."""
        mock_state = MagicMock()
        mock_state.solution_selection = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_selection_rationale()

        # Should return default message (not empty string)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_runner_up_solutions_when_present(self):
        """Test getting runner-up solutions when they exist."""
        mock_state = MagicMock()
        mock_state.solution_selection = MagicMock()
        mock_state.solution_selection.runner_up_solutions = ["Solution A", "Solution B"]

        accessor = StateAccessor(mock_state)
        result = accessor.get_runner_up_solutions()

        assert result == ["Solution A", "Solution B"]

    def test_get_runner_up_solutions_when_no_selection(self):
        """Test getting runner-up solutions when no selection made."""
        mock_state = MagicMock()
        mock_state.solution_selection = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_runner_up_solutions()

        assert result == []


class TestSummaryMethods:
    """Tests for summary text extraction methods."""

    def test_get_pain_points_summary_when_present(self):
        """Test getting pain points summary when present."""
        mock_state = MagicMock()
        mock_state.pain_point_analysis = MagicMock()
        mock_state.pain_point_analysis.analysis_summary = "Summary text here"

        accessor = StateAccessor(mock_state)
        result = accessor.get_pain_points_summary()

        assert result == "Summary text here"

    def test_get_pain_points_summary_when_no_analysis(self):
        """Test getting pain points summary when no analysis."""
        mock_state = MagicMock()
        mock_state.pain_point_analysis = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_pain_points_summary()

        # Should return default message (not empty string)
        assert isinstance(result, str)
        assert len(result) > 0


class TestCountMethods:
    """Tests for count methods."""

    def test_get_reddit_posts_count_when_no_social_content(self):
        """Test Reddit post count when no social content."""
        mock_state = MagicMock()
        mock_state.social_content = None

        accessor = StateAccessor(mock_state)
        count = accessor.get_reddit_posts_count()

        assert count == 0

    def test_get_twitter_threads_count_when_no_social_content(self):
        """Test Twitter thread count when no social content."""
        mock_state = MagicMock()
        mock_state.social_content = None

        accessor = StateAccessor(mock_state)
        count = accessor.get_twitter_threads_count()

        assert count == 0


class TestKeywordValidation:
    """Tests for keyword validation checks."""

    def test_has_keyword_validation_returns_boolean(self):
        """Test that has_keyword_validation returns a boolean."""
        mock_state = MagicMock()
        # Create a mock that has the attribute
        mock_state.keyword_validation = MagicMock()

        accessor = StateAccessor(mock_state)
        result = accessor.has_keyword_validation()

        assert isinstance(result, bool)


class TestTrendLongevityAccessor:
    """Tests for trend longevity data extraction."""

    def test_get_trend_longevity_when_present(self):
        """Test getting trend longevity when data is present."""
        mock_trend = MagicMock()
        mock_state = MagicMock()
        mock_state.trend_longevity = mock_trend

        accessor = StateAccessor(mock_state)
        result = accessor.get_trend_longevity()

        assert result is mock_trend

    def test_get_trend_longevity_when_none(self):
        """Test getting trend longevity when None."""
        mock_state = MagicMock()
        mock_state.trend_longevity = None

        accessor = StateAccessor(mock_state)
        result = accessor.get_trend_longevity()

        assert result is None

    def test_has_stage_data_trend_when_present(self):
        """Test has_stage_data('trend') returns True when trend data exists."""
        mock_state = MagicMock()
        mock_state.trend_longevity = MagicMock()

        accessor = StateAccessor(mock_state)
        assert accessor.has_stage_data('trend') is True

    def test_has_stage_data_trend_when_none(self):
        """Test has_stage_data('trend') returns False when trend data is None."""
        mock_state = MagicMock()
        mock_state.trend_longevity = None

        accessor = StateAccessor(mock_state)
        assert accessor.has_stage_data('trend') is False


# ==================================================================================
# Helpers for keyword dedup tests
# ==================================================================================

def _make_tiered_kw(keyword: str, search_volume: int = 100):
    """Create a mock TieredKeyword-like object."""
    kw = MagicMock()
    kw.keyword = keyword
    kw.search_volume = search_volume
    kw.competition = "MEDIUM (50)"
    return kw


def _make_geo_entry(keyword: str, search_volume: int = 100):
    """Create a mock GeographicKeywordEntry-like object."""
    entry = MagicMock()
    entry.keyword = keyword
    entry.search_volume = search_volume
    return entry


def _make_cat_entry(keyword_name: str, search_volume: int = 100):
    """Create a mock CategoryKeywordEntry-like object."""
    entry = MagicMock()
    entry.keyword_name = keyword_name
    entry.search_volume = search_volume
    return entry


def _make_geo_group(keywords):
    """Create a mock GeographicKeywordGroup."""
    group = MagicMock()
    group.keywords = keywords
    return group


def _make_cat_group(keywords):
    """Create a mock CategoryKeywordGroup."""
    group = MagicMock()
    group.keywords = keywords
    return group


def _make_seo_state(
    tier_0=None, tier_1=None, tier_2=None,
    tier_3_groups=None, tier_4_groups=None,
):
    """Create a mock state with seo_strategy_report populated."""
    mock_state = MagicMock()
    seo = MagicMock()
    seo.tier_0_keywords = tier_0
    seo.tier_1_keywords = tier_1
    seo.tier_2_keywords = tier_2
    seo.tier_3_geographic_groups = tier_3_groups
    seo.tier_4_category_groups = tier_4_groups
    mock_state.seo_strategy_report = seo
    return mock_state


class TestKeywordDeduplication:
    """Tests for cross-tier keyword deduplication in state accessors."""

    def test_dedup_t0_t1_duplicate_counted_once(self):
        """Same keyword in T0 and T1 → total count = 1, not 2."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("beer brewing")],
            tier_1=[_make_tiered_kw("beer brewing")],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_0"] == 1
        assert counts["tier_1"] == 0  # duplicate stripped
        assert counts["total"] == 1

    def test_dedup_t1_t3_duplicate_counted_once(self):
        """Same keyword in T1 and T3 geographic group → counted once."""
        state = _make_seo_state(
            tier_1=[_make_tiered_kw("craft beer")],
            tier_3_groups=[
                _make_geo_group([_make_geo_entry("craft beer")])
            ],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_1"] == 1
        assert counts["tier_3"] == 0
        assert counts["total"] == 1

    def test_dedup_t2_t4_duplicate_counted_once(self):
        """Same keyword in T2 and T4 category group → counted once."""
        state = _make_seo_state(
            tier_2=[_make_tiered_kw("home brewing kit")],
            tier_4_groups=[
                _make_cat_group([_make_cat_entry("home brewing kit")])
            ],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_2"] == 1
        assert counts["tier_4"] == 0
        assert counts["total"] == 1

    def test_dedup_case_insensitive(self):
        """'Beer Brewing' in T0 + 'beer brewing' in T1 → counted once."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("Beer Brewing")],
            tier_1=[_make_tiered_kw("beer brewing")],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_0"] == 1
        assert counts["tier_1"] == 0
        assert counts["total"] == 1

    def test_dedup_whitespace_normalization(self):
        """' keyword ' and 'keyword' → counted once."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw(" keyword ")],
            tier_1=[_make_tiered_kw("keyword")],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["total"] == 1

    def test_dedup_no_duplicates_unchanged(self):
        """All unique keywords → counts unchanged."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("alpha")],
            tier_1=[_make_tiered_kw("beta"), _make_tiered_kw("gamma")],
            tier_2=[_make_tiered_kw("delta")],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_0"] == 1
        assert counts["tier_1"] == 2
        assert counts["tier_2"] == 1
        assert counts["total"] == 4

    def test_dedup_empty_tiers(self):
        """All tiers empty/None → zero counts, no crash."""
        state = _make_seo_state()
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["total"] == 0
        assert all(v == 0 for v in counts.values())

    def test_dedup_volume_counted_once(self):
        """Duplicate keyword volume only added once (from higher-priority tier)."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("beer brewing", search_volume=5000)],
            tier_1=[_make_tiered_kw("beer brewing", search_volume=5000)],
            tier_2=[_make_tiered_kw("unique kw", search_volume=1000)],
        )
        accessor = StateAccessor(state)
        volume = accessor.get_total_keyword_search_volume()

        # Should be 5000 (T0) + 1000 (T2) = 6000, NOT 5000 + 5000 + 1000
        assert volume == 6000

    def test_dedup_triple_duplicate(self):
        """Same keyword in T0, T1, T2 → counted once."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("triple kw")],
            tier_1=[_make_tiered_kw("triple kw")],
            tier_2=[_make_tiered_kw("triple kw")],
        )
        accessor = StateAccessor(state)
        counts = accessor.get_tier_keyword_counts()

        assert counts["tier_0"] == 1
        assert counts["tier_1"] == 0
        assert counts["tier_2"] == 0
        assert counts["total"] == 1

    def test_dedup_logs_warning_on_duplicates(self, caplog):
        """Verify warning logged when duplicates detected."""
        from loguru import logger

        # Enable loguru → standard logging propagation for caplog
        handler_id = logger.add(
            logging.getLogger("loguru_propagate").handlers[0]
            if logging.getLogger("loguru_propagate").handlers
            else logging.StreamHandler(),
            format="{message}",
            level="WARNING",
        )

        state = _make_seo_state(
            tier_0=[_make_tiered_kw("beer brewing")],
            tier_1=[_make_tiered_kw("beer brewing")],
        )
        accessor = StateAccessor(state)

        # Use a loguru sink to capture messages directly
        messages = []
        capture_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
        try:
            accessor.get_tier_keyword_counts()
        finally:
            logger.remove(capture_id)
            logger.remove(handler_id)

        assert any("duplicate keywords across tiers" in m for m in messages)


# ==================================================================================
# Niche-Relevant Volume
# ==================================================================================


def _make_kv_result(solution_name, total_volume, niche_relevant_volume=None):
    """Create a mock CrewKeywordValidationResult-like object."""
    kv = MagicMock()
    kv.solution_name = solution_name
    kv.total_volume = total_volume
    kv.niche_relevant_volume = niche_relevant_volume
    return kv


def _make_state_with_kv(
    selected_name="Test Solution",
    kv_results=None,
    include_selection=True,
    seo_state=None,
):
    """Create a mock state with keyword_validation_results and solution_selection."""
    if seo_state is not None:
        state = seo_state
    else:
        state = MagicMock()
        state.seo_strategy_report = None
    state.keyword_validation_results = kv_results
    if include_selection:
        state.solution_selection = MagicMock()
        state.solution_selection.selected_solution_name = selected_name
    else:
        state.solution_selection = None
    return state


class TestPrimarySearchVolume:
    """Tests for get_primary_search_volume() and get_volume_filter_ratio()."""

    def test_seo_strategy_uses_computed_tier_total(self):
        """Returns sum of tiered keyword volumes (not stale total_monthly_volume)."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("kw1", search_volume=500000)],
            tier_1=[_make_tiered_kw("kw2", search_volume=264480)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 764480

    def test_falls_back_to_kv_when_no_seo(self):
        """Falls back to keyword_validation niche_relevant_volume when no SEO report."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=12000)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 12000

    def test_kv_fallback_uses_total_when_niche_none(self):
        """Falls back to total_volume when niche_relevant_volume is None."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=None)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 50000

    def test_kv_fallback_zero_is_valid(self):
        """niche_relevant_volume=0 should return 0, NOT fall back to total_volume."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=0)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_returns_zero_when_no_selection(self):
        """Returns 0 when no solution_selection and no SEO report."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=12000)],
            include_selection=False,
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_returns_zero_when_not_found(self):
        """Returns 0 when selected solution is not in results."""
        state = _make_state_with_kv(
            selected_name="Missing Solution",
            kv_results=[_make_kv_result("Other Solution", total_volume=50000, niche_relevant_volume=12000)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_case_insensitive_matching(self):
        """Name matching should be case-insensitive (legacy fallback)."""
        state = _make_state_with_kv(
            selected_name="  My Solution  ",
            kv_results=[_make_kv_result("my solution", total_volume=50000, niche_relevant_volume=8000)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 8000

    def test_returns_zero_when_no_kv_results(self):
        """Returns 0 when no SEO report and keyword_validation_results is None."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=None,
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_seo_empty_tiers_returns_zero(self):
        """SEO report with no tier keywords returns 0."""
        state = _make_seo_state(tier_0=None, tier_1=None, tier_2=None)
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_seo_zero_volume_keywords_returns_zero(self):
        """SEO report with all zero-volume keywords returns 0."""
        state = _make_seo_state(
            tier_1=[_make_tiered_kw("kw1", search_volume=0)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_primary_search_volume() == 0

    def test_deprecated_alias_delegates(self):
        """get_niche_relevant_search_volume() delegates to get_primary_search_volume()."""
        state = _make_seo_state(
            tier_0=[_make_tiered_kw("kw1", search_volume=500000)],
            tier_1=[_make_tiered_kw("kw2", search_volume=264480)],
        )
        accessor = StateAccessor(state)
        assert accessor.get_niche_relevant_search_volume() == 764480

    def test_volume_filter_ratio_none_when_seo_present(self):
        """Returns None when seo_strategy_report is present (no filtering concept)."""
        seo_state = _make_seo_state(
            tier_0=[_make_tiered_kw("kw1", search_volume=5000)],
            tier_1=[_make_tiered_kw("kw2", search_volume=5000)],
        )
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=5000)],
            seo_state=seo_state,
        )
        accessor = StateAccessor(state)
        assert accessor.get_volume_filter_ratio() is None

    def test_volume_filter_ratio_works_without_seo(self):
        """Returns ratio when no seo_strategy_report (legacy fallback)."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=[_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=5000)],
        )
        # Also need total keyword search volume from keyword_validation fallback
        state.keyword_validation_results = [_make_kv_result("My Solution", total_volume=50000, niche_relevant_volume=5000)]
        accessor = StateAccessor(state)
        ratio = accessor.get_volume_filter_ratio()
        # primary = 5000, total = 50000, ratio = 0.1
        assert ratio == pytest.approx(0.1)

    def test_volume_filter_ratio_none_when_unavailable(self):
        """Returns None when volumes are 0."""
        state = _make_state_with_kv(
            selected_name="My Solution",
            kv_results=None,
        )
        accessor = StateAccessor(state)
        assert accessor.get_volume_filter_ratio() is None
