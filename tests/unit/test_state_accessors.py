"""
Tests for state accessor utilities.

Note: This test file focuses on the basic accessor patterns.
Complex extraction logic is tested via integration tests.
"""

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
