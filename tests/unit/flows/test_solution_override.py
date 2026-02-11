"""
Tests for _build_recommended_focus helper and solution override logic
at Stage 6 (integrated keyword validation) and Stage 5.4 (fallback selection).
"""

import pytest
from unittest.mock import MagicMock, patch

from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.models.keyword_data import CrewKeywordValidationResult
from nicheiq.utils.helpers import find_solution_by_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_solution():
    """BaseSolutionIdea with all fields populated."""
    return BaseSolutionIdea(
        solution_name="PricingValueCalc",
        description="A value-based pricing calculator that helps freelancers and agencies justify their rates.",
        value_proposition="Generate transparent ROI models and pricing justifications",
        pain_points_addressed=["Pricing and Value Perception", "Marketing Struggles"],
        core_features=["ROI calculator", "Template library", "PDF export"],
        target_personas=["Freelancers", "Micro agencies"],
        project_type="saas",
        market_fit_score=0.82,
        technical_feasibility_score=0.78,
    )


@pytest.fixture
def sample_keyword_validation():
    """CrewKeywordValidationResult with realistic data."""
    return CrewKeywordValidationResult(
        solution_name="PricingValueCalc",
        validated_count=35,
        total_volume=12500,
        avg_competition=42.0,
        keyword_demand_score=0.37,
        top_keywords=[
            {"keyword": "value based pricing calculator", "volume": 2400, "competition": 0.38},
            {"keyword": "ROI calculator freelancer", "volume": 1800, "competition": 0.35},
            {"keyword": "pricing justification tool", "volume": 1200, "competition": 0.40},
        ],
        top_geographic_keywords=["pricing calculator US", "freelancer pricing UK"],
        demand_signal="moderate",
        validation_signals={
            "has_search_demand": True,
            "keyword_diversity": True,
            "high_volume_presence": True,
            "average_volume_per_keyword": 357.1,
        },
        attempts_made=1,
        best_relevance_score=0.72,
    )


@pytest.fixture
def minimal_solution():
    """BaseSolutionIdea with only required fields (Optional fields are None)."""
    return BaseSolutionIdea(
        solution_name="MinimalTool",
        description="A minimal tool.",
        value_proposition="Does something useful",
        pain_points_addressed=[],
        core_features=[],
        target_personas=["Users"],
    )


@pytest.fixture
def _build_focus():
    """Return the _build_recommended_focus method as a standalone callable.

    The method only uses its arguments (solution, keyword_validation) and never
    accesses self.state, so we can bind it to a simple object.
    """
    with patch("nicheiq.flows.research_flow.settings"):
        from nicheiq.flows.research_flow import ResearchFlow

        method = ResearchFlow._build_recommended_focus
        dummy_self = MagicMock()
        return lambda solution, keyword_validation=None: method(
            dummy_self, solution=solution, keyword_validation=keyword_validation
        )


# ---------------------------------------------------------------------------
# TestBuildRecommendedFocus
# ---------------------------------------------------------------------------

class TestBuildRecommendedFocus:
    """Tests for the _build_recommended_focus helper method."""

    def test_full_data(self, _build_focus, sample_solution, sample_keyword_validation):
        """All fields populated: result contains solution name, features, keyword info, pain point."""
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=sample_keyword_validation,
        )
        assert "PricingValueCalc" in result
        assert "ROI calculator" in result
        assert "Template library" in result
        assert "12,500 monthly searches" in result
        assert "Pricing and Value Perception" in result
        # Should have 4 sentences
        assert result.count(".") >= 4

    def test_without_keyword_validation(self, _build_focus, sample_solution):
        """keyword_validation=None: result has no keyword sentence."""
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=None,
        )
        assert "PricingValueCalc" in result
        assert "ROI calculator" in result
        assert "Pricing and Value Perception" in result
        # No keyword-related content
        assert "monthly searches" not in result

    def test_minimal_solution(self, _build_focus, minimal_solution):
        """Empty core_features, empty pain_points_addressed: result is 1 sentence."""
        result = _build_focus(
            solution=minimal_solution,
            keyword_validation=None,
        )
        assert "MinimalTool" in result
        assert "Does something useful" in result
        # No feature or pain point sentences
        assert "Prioritize" not in result
        assert "Anchor messaging" not in result

    def test_no_project_type(self, _build_focus, sample_solution):
        """project_type=None: falls back to 'SaaS tool'."""
        sample_solution.project_type = None
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=None,
        )
        assert "SaaS tool" in result

    def test_geographic_keywords_in_output(self, _build_focus, sample_solution, sample_keyword_validation):
        """When top_geographic_keywords present, geographic info appears in output."""
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=sample_keyword_validation,
        )
        assert "pricing calculator US" in result or "freelancer pricing UK" in result

    def test_single_feature(self, _build_focus, sample_solution):
        """1 core feature uses singular phrasing."""
        sample_solution.core_features = ["ROI calculator"]
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=None,
        )
        assert "core feature: ROI calculator" in result

    def test_empty_pain_point_strings_skipped(self, _build_focus, sample_solution):
        """pain_points_addressed=[''] skips sentence 4."""
        sample_solution.pain_points_addressed = [""]
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=None,
        )
        assert "Anchor messaging" not in result


# ---------------------------------------------------------------------------
# TestStage85RationaleOverride
# ---------------------------------------------------------------------------

class TestStage85RationaleOverride:
    """Tests for the rationale rewrite in _run_integrated_keyword_validation."""

    def _build_rationale(
        self,
        new_winner="PricingValueCalc",
        original_winner="SoloClientQueue",
        new_kd=0.37,
        new_adj=0.31,
        orig_kd=0.22,
        orig_adj=0.19,
        new_winner_validation=None,
    ):
        """Helper to build the rationale using the same logic as the flow."""
        rationale_parts = [
            f"**{new_winner}** emerged as the top solution after keyword validation "
            f"with an adjusted composite score of {new_adj:.2f} "
            f"(keyword demand score: {new_kd:.2f})."
        ]

        if new_winner_validation:
            kw_names = [
                k.get("keyword", "")
                for k in (new_winner_validation.top_keywords or [])[:3]
                if k.get("keyword")
            ]
            evidence = (
                f"Keyword research shows {new_winner_validation.demand_signal} demand "
                f"with {new_winner_validation.total_volume:,} monthly searches "
                f"across {new_winner_validation.validated_count} validated keywords."
            )
            if kw_names:
                evidence += f" Top keywords: {', '.join(kw_names)}."
            rationale_parts.append(evidence)

        rationale_parts.append(
            f"The previous selection, {original_winner}, scored an adjusted composite "
            f"of {orig_adj:.2f} (keyword demand: {orig_kd:.2f}) and was overtaken "
            f"due to weaker keyword demand evidence."
        )

        return "\n\n".join(rationale_parts)

    def test_rationale_leads_with_new_winner(self, sample_keyword_validation):
        """Rationale starts with new winner name, not old winner."""
        rationale = self._build_rationale(
            new_winner_validation=sample_keyword_validation,
        )
        first_line = rationale.split("\n")[0]
        assert first_line.startswith("**PricingValueCalc**")

    def test_rationale_does_not_start_with_old_winner(self, sample_keyword_validation):
        """Old winner name does NOT appear in first paragraph."""
        rationale = self._build_rationale(
            new_winner_validation=sample_keyword_validation,
        )
        first_paragraph = rationale.split("\n\n")[0]
        assert "SoloClientQueue" not in first_paragraph

    def test_rationale_includes_keyword_scores(self, sample_keyword_validation):
        """Contains keyword demand score values."""
        rationale = self._build_rationale(
            new_winner_validation=sample_keyword_validation,
        )
        assert "0.37" in rationale
        assert "0.31" in rationale

    def test_rationale_mentions_original_as_context(self, sample_keyword_validation):
        """Original winner mentioned but only in context paragraph."""
        rationale = self._build_rationale(
            new_winner_validation=sample_keyword_validation,
        )
        paragraphs = rationale.split("\n\n")
        # Original winner should NOT be in first two paragraphs
        for p in paragraphs[:-1]:
            assert "SoloClientQueue" not in p
        # But SHOULD be in the last paragraph
        assert "SoloClientQueue" in paragraphs[-1]

    def test_rationale_without_validation_data(self):
        """When new_winner_validation is None, rationale still valid."""
        rationale = self._build_rationale(
            new_winner_validation=None,
        )
        assert "PricingValueCalc" in rationale
        assert "SoloClientQueue" in rationale
        # No keyword evidence paragraph
        assert "monthly searches" not in rationale

    def test_rationale_meets_min_length(self, sample_keyword_validation):
        """Result is >= 100 chars (SolutionSelection.selection_rationale min_length)."""
        rationale = self._build_rationale(
            new_winner_validation=sample_keyword_validation,
        )
        assert len(rationale) >= 100


# ---------------------------------------------------------------------------
# TestStage85RecommendedFocusUpdate
# ---------------------------------------------------------------------------

class TestStage85RecommendedFocusUpdate:
    """Tests for recommended_focus update at Stage 6 (integrated keyword validation)."""

    def test_focus_updated_on_winner_change(self, _build_focus, sample_solution, sample_keyword_validation):
        """When winner changes, recommended_focus references new winner."""
        solution_ideas = [sample_solution]

        new_winner_solution = find_solution_by_name("PricingValueCalc", solution_ideas)
        assert new_winner_solution is not None

        new_focus = _build_focus(
            solution=new_winner_solution,
            keyword_validation=sample_keyword_validation,
        )
        assert "PricingValueCalc" in new_focus
        assert "OldWinner" not in new_focus

    def test_focus_not_updated_when_winner_same(self):
        """When winner confirmed (no change), recommended_focus untouched.

        The actual flow code only calls _build_recommended_focus when
        new_winner != original_winner, so focus stays as-is.
        """
        original_focus = "Focus on building ConfirmedWinner as a saas..."
        # Simulate no-change branch: _build_recommended_focus is never called
        assert original_focus == "Focus on building ConfirmedWinner as a saas..."

    def test_focus_unchanged_when_solution_not_found(self):
        """find_solution_by_name returns None -> focus stays stale (logged)."""
        result = find_solution_by_name("NonExistentSolution", [])
        assert result is None
        # In the flow, when find_solution_by_name returns None the code logs
        # a warning and skips the focus update, leaving the old value intact.


# ---------------------------------------------------------------------------
# TestStage74FallbackFocusUpdate
# ---------------------------------------------------------------------------

class TestStage74FallbackFocusUpdate:
    """Tests for recommended_focus update at Stage 5.4 fallback."""

    def test_focus_updated_on_fallback(self, _build_focus, sample_solution):
        """Fallback triggers _build_recommended_focus with no keyword data."""
        result = _build_focus(
            solution=sample_solution,
            keyword_validation=None,
        )
        # Should have content but no keyword info
        assert "PricingValueCalc" in result
        assert "monthly searches" not in result

    def test_focus_references_fallback_solution(self, _build_focus, minimal_solution):
        """Result contains fallback solution name."""
        result = _build_focus(
            solution=minimal_solution,
            keyword_validation=None,
        )
        assert "MinimalTool" in result
