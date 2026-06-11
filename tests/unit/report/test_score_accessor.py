"""
Unit tests for ScoreAccessor fallback logic.

Tests score extraction with various missing data scenarios,
verifying that None is returned for missing scores (no silent defaults).
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.report.utils.score_accessor import ScoreAccessor


class TestScoreAccessorFallbacks:
    """Test ScoreAccessor fallback behavior with Optional returns."""

    def test_get_market_fit_from_solution_scores(self):
        """Test market_fit extracted from SolutionScores."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.market_fit_score = 0.85
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        assert score == 0.85

    def test_get_market_fit_fallback_to_solution_field(self):
        """Test market_fit falls back to SolutionIdea field."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.72

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        assert score == 0.72

    def test_get_market_fit_returns_none_when_all_missing(self):
        """Test market_fit returns None when all sources missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_market_fit(solution)

        assert score is None

    def test_get_competitive_advantage_from_solution_scores(self):
        """Test competitive_advantage from SolutionScores."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "TestSolution"
        solution_score.competitive_advantage_score = 0.73
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_competitive_advantage(solution)

        assert score == 0.73

    def test_get_competitive_advantage_uses_novelty_fallback(self):
        """competitive_advantage falls back to novelty_score (the backfill's
        mapping) — the market_fit proxy is gone (it double-counted market_fit
        in the verdict average)."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80
        solution.novelty_score = 0.65

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_competitive_advantage(solution)

        assert score == 0.65

    def test_get_competitive_advantage_novelty_fallback_when_ca_none(self):
        """competitive_advantage falls back to the solution's novelty_score
        when the SolutionScores entry has None — never to market_fit."""
        solution_selection = MagicMock()
        solution_score = MagicMock(spec=['solution_name', 'competitive_advantage_score', 'market_fit_score'])
        solution_score.solution_name = "TestSolution"
        solution_score.competitive_advantage_score = None
        solution_score.market_fit_score = 0.85
        solution_selection.all_solution_scores = [solution_score]

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80
        solution.novelty_score = 0.55

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_competitive_advantage(solution)

        assert score == 0.55

    def test_get_competitive_advantage_returns_none_when_all_missing(self):
        """competitive_advantage returns None when no scores and no novelty —
        no proxy fabrication."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None
        solution.novelty_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_competitive_advantage(solution)

        assert score is None

    def test_get_technical_feasibility_from_solution(self):
        """Test technical_feasibility from SolutionIdea field."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.technical_feasibility_score = 0.78

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_technical_feasibility(solution)

        assert score == 0.78

    def test_get_technical_feasibility_returns_none_when_missing(self):
        """Test technical_feasibility returns None when missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.technical_feasibility_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_technical_feasibility(solution)

        assert score is None

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
        solution.novelty_score = 0.80  # competitive_advantage falls back to novelty

        accessor = ScoreAccessor(solution_selection)
        confidence = accessor.get_confidence_score(solution)

        # Average of 0.80 (market_fit) and 0.80 (novelty fallback)
        assert confidence == 0.80

    def test_get_confidence_score_returns_none_when_scores_missing(self):
        """Test confidence score returns None when underlying scores are None."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None

        accessor = ScoreAccessor(solution_selection)
        confidence = accessor.get_confidence_score(solution)

        assert confidence is None

    def test_get_all_scores_returns_dict(self):
        """Test get_all_scores returns complete dict."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.80
        solution.technical_feasibility_score = 0.75
        solution.seo_scalability_score = 0.70
        solution.seo_scalability_score_refined = None

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

    def test_get_all_scores_returns_none_values(self):
        """Test get_all_scores includes None for missing scores."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None
        solution.novelty_score = None
        solution.technical_feasibility_score = None
        solution.seo_scalability_score = None
        solution.seo_scalability_score_refined = None

        accessor = ScoreAccessor(solution_selection)
        scores = accessor.get_all_scores(solution)

        assert scores["market_fit"] is None
        assert scores["competitive_advantage"] is None
        assert scores["technical_feasibility"] is None
        assert scores["seo_growth"] is None

    def test_get_scores_not_found(self):
        """Test get_scores when solution name not in all_solution_scores."""
        solution_selection = MagicMock()
        solution_score = MagicMock()
        solution_score.solution_name = "OtherSolution"
        solution_score.market_fit_score = 0.85
        solution_selection.all_solution_scores = [solution_score]

        accessor = ScoreAccessor(solution_selection)
        scores = accessor.get_scores("TestSolution")

        assert scores is None

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
        """Stage 12 refined score should take priority over selection score."""
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
        """Fall back to all_solution_scores when refined is None."""
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

    def test_returns_none_when_all_missing(self):
        """Return None when all sources are missing."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = None
        solution.seo_scalability_score = None

        accessor = ScoreAccessor(solution_selection)
        score = accessor.get_seo_score_canonical(solution)
        assert score is None

    def test_zero_is_valid_not_falsy(self):
        """0.0 should be returned as valid, not treated as falsy."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.seo_scalability_score_refined = 0.0
        solution.seo_scalability_score = 0.70

        accessor = ScoreAccessor(None)
        score = accessor.get_seo_score_canonical(solution)
        assert score == 0.0

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

    def test_none_scores_return_none(self):
        """Test that None scores consistently return None."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = None
        solution.novelty_score = None
        solution.technical_feasibility_score = None
        solution.seo_scalability_score = None
        solution.seo_scalability_score_refined = None

        accessor = ScoreAccessor(solution_selection)

        assert accessor.get_market_fit(solution) is None
        assert accessor.get_competitive_advantage(solution) is None
        assert accessor.get_technical_feasibility(solution) is None
        assert accessor.get_seo_growth(solution) is None

    def test_zero_scores_are_valid(self):
        """Test that 0.0 scores are treated as valid (not None)."""
        solution_selection = None

        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = 0.0
        solution.technical_feasibility_score = 0.0

        accessor = ScoreAccessor(solution_selection)

        # 0.0 is valid, should not return None
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


class TestSoloDevFeasibility:
    """Test get_solo_dev_feasibility method."""

    def test_returns_float_from_solution(self):
        """Test solo_dev_feasibility returns float from solution."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.solo_dev_feasibility = 0.85

        accessor = ScoreAccessor(None)
        score = accessor.get_solo_dev_feasibility(solution)
        assert score == 0.85

    def test_returns_none_when_missing(self):
        """Test solo_dev_feasibility returns None when not set."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.solo_dev_feasibility = None

        accessor = ScoreAccessor(None)
        score = accessor.get_solo_dev_feasibility(solution)
        assert score is None

    def test_converts_int_to_float(self):
        """Test solo_dev_feasibility converts int to float."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.solo_dev_feasibility = 1

        accessor = ScoreAccessor(None)
        score = accessor.get_solo_dev_feasibility(solution)
        assert score == 1.0
        assert isinstance(score, float)

    def test_returns_none_for_string(self):
        """Test solo_dev_feasibility returns None for non-numeric values."""
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.solo_dev_feasibility = "high"

        accessor = ScoreAccessor(None)
        score = accessor.get_solo_dev_feasibility(solution)
        assert score is None


class TestConfidenceScoreQualityAdjustment:
    """Test get_confidence_score with quality adjustment params."""

    def _make_solution(self, market_fit=0.80):
        solution = MagicMock()
        solution.solution_name = "TestSolution"
        solution.market_fit_score = market_fit
        solution.novelty_score = market_fit  # competitive_advantage novelty fallback
        return solution

    def test_get_confidence_score_backward_compatible(self):
        """No kwargs = old behavior (no adjustment)."""
        solution = self._make_solution(0.80)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(solution)
        # avg of 0.80 (market_fit) + 0.80 (novelty fallback) = 0.80
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

    def test_get_confidence_score_returns_none_when_scores_missing(self):
        """Confidence returns None when market_fit is None."""
        solution = self._make_solution(None)
        accessor = ScoreAccessor(None)
        score = accessor.get_confidence_score(solution)
        assert score is None
