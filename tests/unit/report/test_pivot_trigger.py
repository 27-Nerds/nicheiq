"""
Unit tests for ReportGenerator._build_pivot_trigger.

Tests relative score comparison logic that replaces the old
absolute-threshold pivot trigger generation.
"""

from unittest.mock import MagicMock, patch

import pytest

from nicheiq.report.report_generator import ReportGenerator


@pytest.fixture
def generator():
    """Create a ReportGenerator with a minimal mocked state."""
    state = MagicMock()
    state.solution_selection = None
    state.competitive_analysis = None
    state.idea_generation = None
    state.social_content = None
    state.pain_point_analysis = None
    state.seo_strategy = None
    state.solution_refinement = None
    return ReportGenerator(state)


class TestBuildPivotTriggerStrongAdvantage:
    """Test detection of dimensions where runner-up outscores selected (delta > 0.05)."""

    def test_single_strong_signal(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Pivot to RunnerUp if:" in result
        assert "Strong pivot signal" in result
        assert "market fit" in result
        assert "0.80" in result
        assert "0.70" in result

    def test_multiple_strong_signals(self, generator):
        runner_up_scores = {
            "market_fit": 0.85,
            "seo_growth": 0.75,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.60,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Strong pivot signal" in result
        assert "market fit" in result
        assert "SEO growth potential" in result


class TestBuildPivotTriggerNearParity:
    """Test detection of dimensions within 0.05 of each other."""

    def test_near_parity_detected(self, generator):
        runner_up_scores = {
            "market_fit": 0.72,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.75,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Near-parity" in result
        assert "market fit" in result
        assert "closely matched" in result

    def test_exact_tie_is_near_parity(self, generator):
        runner_up_scores = {
            "market_fit": 0.75,
            "seo_growth": 0.60,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.75,
            "seo_growth": 0.60,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Near-parity" in result


class TestBuildPivotTriggerModerateGap:
    """Test detection of moderate gaps (-0.15 <= delta < -0.05)."""

    def test_moderate_gap_detected(self, generator):
        # Runner-up is 0.10 behind on market_fit but 0.10 ahead on seo_growth
        runner_up_scores = {
            "market_fit": 0.65,
            "seo_growth": 0.70,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.75,
            "seo_growth": 0.55,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Worth monitoring" in result
        assert "market fit" in result
        assert "Strong pivot signal" in result  # seo_growth is ahead


class TestBuildPivotTriggerAllBehindFallback:
    """Test fallback when runner-up is behind in all dimensions."""

    def test_all_behind_still_data_driven(self, generator):
        runner_up_scores = {
            "market_fit": 0.50,
            "seo_growth": 0.40,
            "technical_feasibility": 0.45,
            "competitive_advantage": 0.35,
        }
        selected_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.75,
            "technical_feasibility": 0.70,
            "competitive_advantage": 0.65,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        # Should still have scores in output, not generic text
        assert "Pivot to RunnerUp if:" in result
        assert "Strongest relative dimension" in result
        # Best relative dim is technical_feasibility (delta -0.25, smallest gap)
        assert "technical feasibility" in result
        assert "0.45" in result
        assert "0.70" in result
        assert "delta" in result

    def test_all_behind_with_key_differentiator(self, generator):
        runner_up_scores = {
            "market_fit": 0.50,
            "seo_growth": 0.40,
            "technical_feasibility": 0.45,
            "competitive_advantage": 0.35,
        }
        selected_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.75,
            "technical_feasibility": 0.70,
            "competitive_advantage": 0.65,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            key_differentiator="AI-powered insights",
        )
        assert "Key differentiator: AI-powered insights" in result


class TestBuildPivotTriggerMissingSelectedSolution:
    """Test absolute threshold fallback when selected solution not found."""

    def test_no_selected_scores_above_threshold(self, generator):
        runner_up_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.65,
            "technical_feasibility": 0.70,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=None,
        )
        assert "Pivot to RunnerUp if:" in result
        assert "market fit score (0.70)" in result
        assert "SEO growth potential (0.65)" in result
        assert "technical feasibility (0.70)" in result

    def test_no_selected_scores_below_threshold(self, generator):
        runner_up_scores = {
            "market_fit": 0.50,
            "seo_growth": 0.40,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=None,
        )
        assert "customer discovery" in result


class TestBuildPivotTriggerDefaultScores:
    """Test behavior when all scores are the default 0.5."""

    def test_all_defaults_detected(self, generator):
        runner_up_scores = {
            "market_fit": 0.5,
            "seo_growth": 0.5,
            "technical_feasibility": 0.5,
            "competitive_advantage": 0.5,
        }
        selected_scores = {
            "market_fit": 0.5,
            "seo_growth": 0.5,
            "technical_feasibility": 0.5,
            "competitive_advantage": 0.5,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
        )
        assert "Scores not yet validated" in result
        assert "customer discovery" in result

    def test_all_defaults_with_differentiator(self, generator):
        runner_up_scores = {
            "market_fit": 0.5,
            "seo_growth": 0.5,
            "technical_feasibility": 0.5,
            "competitive_advantage": 0.5,
        }
        selected_scores = {
            "market_fit": 0.5,
            "seo_growth": 0.5,
            "technical_feasibility": 0.5,
            "competitive_advantage": 0.5,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            key_differentiator="Open-source community",
        )
        assert "Key differentiator: Open-source community" in result


class TestBuildPivotTriggerContextualSignals:
    """Test non-score contextual signals."""

    def test_low_competitive_intensity(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            competitive_intensity="LOW",
        )
        assert "less saturated market segment" in result

    def test_medium_competitive_intensity_not_mentioned(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            competitive_intensity="MEDIUM",
        )
        assert "less saturated" not in result

    def test_easier_solo_dev_path(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            solo_dev_feasibility=0.85,
            selected_solo_dev=0.60,
        )
        assert "easier solo-dev path" in result

    def test_solo_dev_small_difference_not_mentioned(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            solo_dev_feasibility=0.70,
            selected_solo_dev=0.65,
        )
        assert "solo-dev" not in result

    def test_different_project_type(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            project_type="marketplace",
            selected_project_type="saas",
        )
        assert "if user research favors marketplace model" in result

    def test_same_project_type_not_mentioned(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            project_type="saas",
            selected_project_type="saas",
        )
        assert "user research favors" not in result

    def test_all_contextual_signals_combined(self, generator):
        runner_up_scores = {
            "market_fit": 0.80,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        selected_scores = {
            "market_fit": 0.70,
            "seo_growth": 0.50,
            "technical_feasibility": 0.50,
            "competitive_advantage": 0.50,
        }
        result = generator._build_pivot_trigger(
            runner_up_name="RunnerUp",
            runner_up_scores=runner_up_scores,
            selected_scores=selected_scores,
            competitive_intensity="LOW",
            solo_dev_feasibility=0.90,
            selected_solo_dev=0.60,
            project_type="directory",
            selected_project_type="saas",
        )
        assert "less saturated market segment" in result
        assert "easier solo-dev path" in result
        assert "if user research favors directory model" in result
