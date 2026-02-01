"""
Tests for selection_criteria_scores rebuild after re-ranking.

Covers:
- _build_selection_criteria_from_scores (Stage 8.5 pivot path)
- _build_selection_criteria_from_solution_idea (Stage 7 fallback path)
- Regression tests for Stage 8.5 pivot and Stage 7 fallback
- Downstream consumer compatibility
"""

import pytest
from unittest.mock import MagicMock, patch

from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.models.solution_selection import SelectionCriteriaScore, SolutionScores


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_solution_scores():
    """SolutionScores for a typical winner."""
    return SolutionScores(
        solution_name="PricingValueCalc",
        market_fit_score=0.85,
        technical_feasibility_score=0.72,
        competitive_advantage_score=0.68,
        seo_growth_potential_score=0.91,
        composite_score=0.79,
        rank=1,
    )


@pytest.fixture
def old_winner_scores():
    """SolutionScores for the original winner that gets displaced."""
    return SolutionScores(
        solution_name="SoloClientQueue",
        market_fit_score=0.75,
        technical_feasibility_score=0.80,
        competitive_advantage_score=0.60,
        seo_growth_potential_score=0.55,
        composite_score=0.68,
        rank=2,
    )


@pytest.fixture
def sample_solution():
    """BaseSolutionIdea with all score fields populated."""
    return BaseSolutionIdea(
        solution_name="PricingValueCalc",
        description="A value-based pricing calculator that helps freelancers justify their rates.",
        value_proposition="Generate transparent ROI models and pricing justifications",
        pain_points_addressed=["Pricing and Value Perception"],
        core_features=["ROI calculator", "Template library"],
        target_personas=["Freelancers"],
        market_fit_score=0.82,
        technical_feasibility_score=0.78,
        seo_scalability_score=0.65,
    )


@pytest.fixture
def minimal_solution():
    """BaseSolutionIdea with no score fields populated."""
    return BaseSolutionIdea(
        solution_name="MinimalTool",
        description="A minimal tool.",
        value_proposition="Does something useful",
        pain_points_addressed=[],
        core_features=[],
        target_personas=["Users"],
    )


@pytest.fixture
def _from_scores():
    """Return _build_selection_criteria_from_scores as a callable."""
    with patch("nicheiq.flows.research_flow.settings"):
        from nicheiq.flows.research_flow import ResearchFlow
        return ResearchFlow._build_selection_criteria_from_scores


@pytest.fixture
def _from_solution():
    """Return _build_selection_criteria_from_solution_idea as a callable."""
    with patch("nicheiq.flows.research_flow.settings"):
        from nicheiq.flows.research_flow import ResearchFlow
        return ResearchFlow._build_selection_criteria_from_solution_idea


# ---------------------------------------------------------------------------
# TestBuildSelectionCriteriaFromScores
# ---------------------------------------------------------------------------

class TestBuildSelectionCriteriaFromScores:
    """Tests for _build_selection_criteria_from_scores."""

    def test_produces_exactly_4_criteria(self, _from_scores, sample_solution_scores):
        result = _from_scores(sample_solution_scores)
        assert len(result) == 4

    def test_criterion_names(self, _from_scores, sample_solution_scores):
        result = _from_scores(sample_solution_scores)
        names = [s.criterion for s in result]
        assert names == [
            "market_fit",
            "competitive_advantage",
            "technical_feasibility",
            "seo_growth_potential",
        ]

    def test_score_values_match_input(self, _from_scores, sample_solution_scores):
        result = _from_scores(sample_solution_scores)
        score_map = {s.criterion: s.score for s in result}
        assert score_map["market_fit"] == 0.85
        assert score_map["competitive_advantage"] == 0.68
        assert score_map["technical_feasibility"] == 0.72
        assert score_map["seo_growth_potential"] == 0.91

    def test_justification_prefix_propagated(self, _from_scores, sample_solution_scores):
        prefix = "Updated after pivot."
        result = _from_scores(sample_solution_scores, justification_prefix=prefix)
        for entry in result:
            assert entry.justification == prefix

    def test_justification_empty_string_when_no_prefix(self, _from_scores, sample_solution_scores):
        result = _from_scores(sample_solution_scores)
        for entry in result:
            assert entry.justification == ""

    def test_zero_score_is_valid(self, _from_scores):
        scores = SolutionScores(
            solution_name="ZeroTool",
            market_fit_score=0.0,
            technical_feasibility_score=0.0,
            competitive_advantage_score=0.0,
            seo_growth_potential_score=0.0,
            composite_score=0.0,
            rank=1,
        )
        result = _from_scores(scores)
        assert len(result) == 4
        for entry in result:
            assert entry.score == 0.0

    def test_returns_selection_criteria_score_instances(self, _from_scores, sample_solution_scores):
        result = _from_scores(sample_solution_scores)
        for entry in result:
            assert isinstance(entry, SelectionCriteriaScore)

    def test_stage_85_justification_mentions_pivot_and_old_winner(
        self, _from_scores, sample_solution_scores
    ):
        prefix = (
            "Updated after Stage 8.5 keyword validation pivot. "
            "Previous winner: SoloClientQueue."
        )
        result = _from_scores(sample_solution_scores, justification_prefix=prefix)
        for entry in result:
            assert "pivot" in entry.justification
            assert "SoloClientQueue" in entry.justification


# ---------------------------------------------------------------------------
# TestBuildSelectionCriteriaFromSolutionIdea
# ---------------------------------------------------------------------------

class TestBuildSelectionCriteriaFromSolutionIdea:
    """Tests for _build_selection_criteria_from_solution_idea."""

    def test_produces_3_criteria_no_competitive_advantage(self, _from_solution, sample_solution):
        result = _from_solution(sample_solution)
        assert len(result) == 3
        names = [s.criterion for s in result]
        assert "competitive_advantage" not in names

    def test_seo_scalability_maps_to_seo_growth_potential(self, _from_solution, sample_solution):
        result = _from_solution(sample_solution)
        score_map = {s.criterion: s.score for s in result}
        assert score_map["seo_growth_potential"] == 0.65

    def test_none_scores_omitted(self, _from_solution):
        solution = BaseSolutionIdea(
            solution_name="PartialTool",
            description="A tool with partial scores.",
            value_proposition="Partial value",
            pain_points_addressed=["Pain"],
            core_features=["Feature"],
            target_personas=["Users"],
            market_fit_score=0.70,
            technical_feasibility_score=None,
            seo_scalability_score=None,
        )
        result = _from_solution(solution)
        assert len(result) == 1
        assert result[0].criterion == "market_fit"
        assert result[0].score == 0.70

    def test_all_none_scores_produce_empty_list(self, _from_solution, minimal_solution):
        result = _from_solution(minimal_solution)
        assert result == []

    def test_partial_scores_only_non_none_included(self, _from_solution):
        solution = BaseSolutionIdea(
            solution_name="TwoScores",
            description="A tool with two scores.",
            value_proposition="Two scores",
            pain_points_addressed=["Pain"],
            core_features=["Feature"],
            target_personas=["Users"],
            market_fit_score=0.60,
            technical_feasibility_score=0.75,
            seo_scalability_score=None,
        )
        result = _from_solution(solution)
        names = [s.criterion for s in result]
        assert "market_fit" in names
        assert "technical_feasibility" in names
        assert "seo_growth_potential" not in names

    def test_justification_prefix_works(self, _from_solution, sample_solution):
        prefix = "[AUTO-FALLBACK] Scores from SolutionIdea fields."
        result = _from_solution(sample_solution, justification_prefix=prefix)
        for entry in result:
            assert entry.justification == prefix

    def test_justification_empty_string_when_no_prefix(self, _from_solution, sample_solution):
        result = _from_solution(sample_solution)
        for entry in result:
            assert entry.justification == ""


# ---------------------------------------------------------------------------
# TestStage85PivotRegression
# ---------------------------------------------------------------------------

class TestStage85PivotRegression:
    """Regression tests: selection_criteria_scores match the NEW winner after pivot."""

    def test_scores_rebuilt_match_new_winner(
        self, _from_scores, sample_solution_scores, old_winner_scores
    ):
        """After pivot, rebuilt scores match PricingValueCalc, not SoloClientQueue."""
        result = _from_scores(sample_solution_scores)
        score_map = {s.criterion: s.score for s in result}
        # New winner scores
        assert score_map["market_fit"] == 0.85
        assert score_map["competitive_advantage"] == 0.68
        # NOT old winner scores
        assert score_map["market_fit"] != 0.75
        assert score_map["competitive_advantage"] != 0.60

    def test_old_winner_scores_not_present(
        self, _from_scores, sample_solution_scores, old_winner_scores
    ):
        """Rebuilt list contains new winner's scores, not old winner's."""
        result = _from_scores(sample_solution_scores)
        score_map = {s.criterion: s.score for s in result}
        old_result = _from_scores(old_winner_scores)
        old_map = {s.criterion: s.score for s in old_result}
        # At least one score must differ (they do for all 4)
        differences = sum(
            1 for k in score_map if score_map[k] != old_map.get(k)
        )
        assert differences >= 1


# ---------------------------------------------------------------------------
# TestStage7FallbackPaths
# ---------------------------------------------------------------------------

class TestStage7FallbackPaths:
    """Tests for Stage 7 fallback selection_criteria_scores rebuild."""

    def test_uses_all_solution_scores_when_available(
        self, _from_scores, sample_solution_scores
    ):
        """When all_solution_scores has the fallback, produces 4 criteria."""
        result = _from_scores(
            sample_solution_scores,
            justification_prefix="[AUTO-FALLBACK] Scores from all_solution_scores.",
        )
        assert len(result) == 4
        names = [s.criterion for s in result]
        assert "competitive_advantage" in names

    def test_falls_back_to_solution_idea_when_no_scores(
        self, _from_solution, sample_solution
    ):
        """When all_solution_scores is None, produces 3 criteria from SolutionIdea."""
        result = _from_solution(
            sample_solution,
            justification_prefix="[AUTO-FALLBACK] Scores from SolutionIdea fields.",
        )
        assert len(result) == 3
        names = [s.criterion for s in result]
        assert "competitive_advantage" not in names

    def test_name_mismatch_falls_through_to_solution_idea(
        self, _from_scores, _from_solution, sample_solution_scores, sample_solution
    ):
        """When all_solution_scores has no match, falls through to SolutionIdea path.

        Simulates the fallback logic: if next(...) returns None,
        use _build_selection_criteria_from_solution_idea instead.
        """
        # Simulate: all_solution_scores has a different name
        all_scores = [sample_solution_scores]  # name="PricingValueCalc"
        fallback_name = "NonExistentTool"

        fallback_scores_obj = next(
            (s for s in all_scores if s.solution_name.strip() == fallback_name.strip()),
            None,
        )
        assert fallback_scores_obj is None

        # Falls through to SolutionIdea path
        result = _from_solution(
            sample_solution,
            justification_prefix="[AUTO-FALLBACK] Scores from SolutionIdea fields.",
        )
        assert len(result) == 3


# ---------------------------------------------------------------------------
# TestDownstreamConsumerCompatibility
# ---------------------------------------------------------------------------

class TestDownstreamConsumerCompatibility:
    """Verify rebuilt scores work with downstream report_generator consumers."""

    def test_sync_solution_with_selection_scores_compatibility(
        self, _from_scores, sample_solution_scores
    ):
        """Rebuilt scores produce the score_map keys expected by
        _sync_solution_with_selection_scores (report_generator.py:696-710).
        """
        result = _from_scores(sample_solution_scores)
        score_map = {s.criterion: s.score for s in result}

        # These keys are used by the downstream consumer
        assert "market_fit" in score_map
        assert "technical_feasibility" in score_map
        assert "seo_growth_potential" in score_map
        assert "competitive_advantage" in score_map

        # Values should be floats in 0-1 range
        for v in score_map.values():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0

    def test_solution_idea_path_missing_competitive_advantage(
        self, _from_solution, sample_solution
    ):
        """SolutionIdea path (3 entries) — competitive_advantage returns None via .get()."""
        result = _from_solution(sample_solution)
        score_map = {s.criterion: s.score for s in result}

        # competitive_advantage is NOT in the map
        assert score_map.get("competitive_advantage") is None

        # Other keys work normally
        assert score_map.get("market_fit") == 0.82
        assert score_map.get("technical_feasibility") == 0.78
        assert score_map.get("seo_growth_potential") == 0.65
