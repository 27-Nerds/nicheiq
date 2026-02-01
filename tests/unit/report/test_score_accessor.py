"""
Unit tests for ScoreAccessor fallback logic.

Tests score extraction with various missing data scenarios,
verifying that defaults are used appropriately and warnings are logged.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.report.utils.score_accessor import ScoreAccessor


class TestScoreAccessorFallbacks:
    """Test ScoreAccessor default fallback behavior."""

    def test_get_market_fit_from_solution_scores(self):
        """Test market_fit extracted from SolutionScores."""
        # Mock solution selection with scores
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.market_fit_score = 0.85
        solution_selection.all_solution_scores = [solution_score]

        # Mock solution
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        # Should use SolutionScores value
        assert score == 0.85

    def test_get_market_fit_fallback_to_solution_field(self):
        """Test market_fit falls back to SolutionIdea field."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.72

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        # Should use SolutionIdea field
        assert score == 0.72

    def test_get_market_fit_uses_default(self):
        """Test market_fit uses default when all sources missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution, default=0.5)

        # Should use default
        assert score == 0.5

        # Note: Logging verification would require loguru sink setup
        # For now, we just verify the default value is returned

    def test_get_competitive_advantage_uses_market_fit_proxy(self):
        """Test competitive_advantage falls back to market_fit as proxy."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_competitive_advantage(solution)

        # Should use market_fit as proxy
        assert score == 0.80

        # Note: Logging verification would require loguru sink setup

    def test_get_technical_feasibility_from_solution(self):
        """Test technical_feasibility from SolutionIdea field."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.technical_feasibility_score = 0.78

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_technical_feasibility(solution)

        assert score == 0.78

    def test_get_technical_feasibility_uses_default(self):
        """Test technical_feasibility uses default when missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.technical_feasibility_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_technical_feasibility(solution, default=0.6)

        assert score == 0.6

    def test_get_seo_growth_from_solution_scores(self):
        """Test seo_growth from SolutionScores."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.seo_growth_potential_score = 0.88
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_growth(solution)

        assert score == 0.88

    def test_get_seo_growth_fallback_to_scalability(self):
        """Test seo_growth falls back to seo_scalability_score."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score = 0.75

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_growth(solution)

        assert score == 0.75

    def test_get_confidence_score_averages_correctly(self):
        """Test confidence score averages market_fit and competitive_advantage."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80
        # No competitive_advantage, will use market_fit as proxy

        accessor = ScoreAccessor(solution_selection)
        confidence = accessor.get_confidence_score(solution)

        # Average of 0.80 (market_fit) and 0.80 (competitive_adv proxy)
        assert confidence == 0.80

    def test_get_all_scores_returns_dict(self):
        """Test get_all_scores returns complete dict."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80
        solution.technical_feasibility_score = 0.75
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(solution_selection)
        scores = accessor.get_all_scores(solution)

        assert isinstance(scores, dict)
        assert "market_fit" in scores
        assert "competitive_advantage" in scores
        assert "technical_feasibility" in scores
        assert "seo_growth" in scores
        assert scores["market_fit"] == 0.80
        assert scores["technical_feasibility"] == 0.75
        assert scores["seo_growth"] == 0.70

    def test_custom_default_values(self):
        """Test custom default values are respected."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)

        # Test different custom defaults
        assert accessor.get_market_fit(solution, default=0.3) == 0.3
        assert accessor.get_market_fit(solution, default=0.7) == 0.7
        assert accessor.get_market_fit(solution, default=0.0) == 0.0

    def test_get_scores_not_found(self):
        """Test get_scores when solution name not in all_solution_scores."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "OtherSolution"
        solution_score.market_fit_score = 0.85
        solution_selection.all_solution_scores = [solution_score]

        accessor = ScoreAccessor(solution_selection)
        scores = accessor.get_scores("TestSolution")

        # Should return None
        assert scores is None

        # Note: Logging verification would require loguru sink setup

    def test_no_solution_selection(self):
        """Test accessor works with None solution_selection."""
        accessor = ScoreAccessor(None)

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.75

        score = accessor.get_market_fit(solution)
        assert score == 0.75


class TestSeoScoreCanonical:
    """Test canonical SEO score resolution order."""

    def test_prefers_refined_over_selection(self):
        """Stage 9.5 refined score should take priority over selection score."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.seo_growth_potential_score = 0.78
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = 0.84
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.84

    def test_uses_selection_when_no_refined(self):
        """Fall back to selection criteria when refined is None."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.seo_growth_potential_score = 0.78
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = None
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.78

    def test_uses_baseline_when_no_selection(self):
        """Fall back to baseline when selection score is also missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = None
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.70

    def test_uses_default_when_all_missing(self):
        """Return default when all sources are None."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = None
        solution.seo_scalability_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.5

    def test_zero_is_valid_not_falsy(self):
        """0.0 should be returned as valid, not treated as falsy."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = 0.0
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(None)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.0

    def test_custom_default(self):
        """Custom default value should be respected."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = None
        solution.seo_scalability_score = None

        accessor = ScoreAccessor(None)
        score = accessor.get_seo_score_canonical(solution, default=0.3)
        assert score == 0.3

    def test_works_with_none_solution_selection(self):
        """Should work when ScoreAccessor has None solution_selection but refined is set."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = 0.84
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(None)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.84


class TestScoreAccessorEdgeCases:
    """Test edge cases and None handling."""

    def test_none_scores_use_defaults(self):
        """Test that None scores consistently use defaults."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None
        solution.technical_feasibility_score = None
        solution.seo_scalability_score = None

        accessor = ScoreAccessor(solution_selection)

        # All should use default 0.5
        assert accessor.get_market_fit(solution) == 0.5
        assert accessor.get_competitive_advantage(solution) == 0.5
        assert accessor.get_technical_feasibility(solution) == 0.5
        assert accessor.get_seo_growth(solution) == 0.5

    def test_zero_scores_are_valid(self):
        """Test that 0.0 scores are treated as valid (not None)."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.0
        solution.technical_feasibility_score = 0.0

        accessor = ScoreAccessor(solution_selection)

        # 0.0 is valid, should not use default
        assert accessor.get_market_fit(solution) == 0.0
        assert accessor.get_technical_feasibility(solution) == 0.0

    def test_empty_all_solution_scores(self):
        """Test behavior when all_solution_scores is empty list."""
        solution_selection = MagicMock()
        solution_selection.all_solution_scores = []

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.75

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        # Should fall back to solution field
        assert score == 0.75


class TestConfidenceScoreQualityAdjustment:
    """Test get_confidence_score with quality adjustment params."""

    def _make_solution(self, market_fit=0.80):
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = market_fit
        return solution

    def test_get_confidence_score_backward_compatible(self):
        """No kwargs = old behavior (no adjustment)."""
        solution = self._make_solution(0.80)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(solution)
        # avg of 0.80 + 0.80 (proxy) = 0.80
        assert score == pytest.approx(0.80)

    def test_get_confidence_score_all_none_kwargs(self):
        """Explicit None kwargs = old behavior."""
        solution = self._make_solution(0.80)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(
            solution,
            pain_point_quality_tier=None,
            social_content_quality_tier=None,
            pain_point_confidence_score=None,
        )
        assert score == pytest.approx(0.80)

    def test_get_confidence_score_with_bronze_tier(self):
        """BRONZE tier reduces confidence score."""
        solution = self._make_solution(0.80)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(
            solution, pain_point_quality_tier="BRONZE"
        )
        # base 0.80 * 0.85 = 0.68
        assert score == pytest.approx(0.80 * 0.85)

    def test_get_confidence_score_with_low_pp_confidence(self):
        """Low PP confidence reduces score."""
        solution = self._make_solution(0.80)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(
            solution, pain_point_confidence_score=0.4
        )
        # base 0.80 * 0.90 = 0.72
        assert score == pytest.approx(0.80 * 0.90)
