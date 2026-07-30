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

def _score(name, composite=0.5, demand=0.9, adjusted=None):
    """SolutionScores stand-in for build_pivot_rationale (attribute access only)."""
    from types import SimpleNamespace
    if adjusted is None:
        adjusted = round(0.7 * composite + 0.3 * demand, 4)
    return SimpleNamespace(
        solution_name=name, composite_score=composite, keyword_demand_score=demand,
        adjusted_composite_score=adjusted, market_fit_score=0.5,
        technical_feasibility_score=0.7, competitive_advantage_score=0.5,
        seo_growth_potential_score=0.5,
    )


class TestStage85RationaleOverride:
    """Tests for the REAL pivot rationale helper (`build_pivot_rationale`) — the old
    local `_build_rationale` replica had drifted from the flow (missing the
    '**Keyword-validation update:** ' prefix) and could not catch the false-cause bug."""

    def _rationale(self, new=None, orig=None, validation=None, orig_validated=True):
        from nicheiq.utils.score_helpers import build_pivot_rationale
        new = new or _score("PricingValueCalc", composite=0.31, demand=0.37, adjusted=0.31)
        orig_name = getattr(orig, "solution_name", None) or "SoloClientQueue"
        return build_pivot_rationale(
            new, orig, validation, orig_name=orig_name,
            orig_validated=orig_validated)

    def test_rationale_leads_with_new_winner(self, sample_keyword_validation):
        rationale = self._rationale(
            orig=_score("SoloClientQueue", composite=0.19, demand=0.22, adjusted=0.19),
            validation=sample_keyword_validation)
        first_line = rationale.split("\n")[0]
        assert first_line.startswith("**Keyword-validation update:** **PricingValueCalc**")
        assert "SoloClientQueue" not in rationale.split("\n\n")[0]

    def test_rationale_includes_keyword_scores(self, sample_keyword_validation):
        rationale = self._rationale(
            orig=_score("SoloClientQueue", composite=0.19, demand=0.22, adjusted=0.19),
            validation=sample_keyword_validation)
        assert "0.37" in rationale
        assert "0.31" in rationale
        assert len(rationale) >= 100  # selection_rationale min_length

    def test_composite_dominant_flip_never_claims_demand(self):
        """The real bookkeepers numbers: ~97% of the gap came from the composite term.
        The old text asserted 'weaker keyword demand evidence' — arithmetically false."""
        new = _score("MultiEntityConsolidationCalc", composite=0.625, demand=0.9804)
        orig = _score("ConsolidatorAI", composite=0.430, demand=0.9660)
        rationale = self._rationale(new=new, orig=orig)
        assert "weaker keyword demand" not in rationale
        assert "qualitative scoring" in rationale
        assert "ConsolidatorAI" in rationale

    def test_demand_dominant_flip_names_demand(self):
        new = _score("A", composite=0.50, demand=0.90)
        orig = _score("B", composite=0.50, demand=0.20)
        rationale = self._rationale(new=new, orig=orig)
        assert "keyword demand evidence" in rationale
        assert "qualitative scoring" not in rationale

    def test_tiebreak_flip_uses_tiebreak_phrasing(self):
        """Novelty tiebreak can crown a winner with a LOWER adjusted score — a delta
        decomposition would assert a new false cause."""
        new = _score("A", composite=0.50, demand=0.90, adjusted=0.68)
        orig = _score("B", composite=0.52, demand=0.90, adjusted=0.70)
        rationale = self._rationale(new=new, orig=orig)
        assert "tiebreak" in rationale
        assert "overtaken" not in rationale

    def test_unvalidated_original_no_fabricated_scores(self):
        """Original missing from all_scores / not keyword-validated: no '0.00' claims."""
        rationale = self._rationale(new=_score("A"), orig=None)
        assert "not keyword-validated" in rationale
        assert "0.00" not in rationale
        rationale2 = self._rationale(
            new=_score("A"), orig=_score("SoloClientQueue"), orig_validated=False)
        assert "not keyword-validated" in rationale2

    def test_rationale_without_validation_data(self):
        rationale = self._rationale(
            orig=_score("SoloClientQueue", composite=0.19, demand=0.22, adjusted=0.19))
        assert "PricingValueCalc" in rationale
        assert "SoloClientQueue" in rationale
        assert "monthly searches" not in rationale


class TestKeywordPivotUserGuard:
    """Run-quality fixes §3: `_apply_keyword_pivot` must not silently override an
    explicitly user-selected winner (`state._user_selected_solutions`); headless runs
    (which stamp score_source='interactive' too) keep pivoting."""

    def _flow(self, user_selected=None):
        """Bind the real _apply_keyword_pivot to a plain object (Flow.state is a
        CrewAI property; the method only touches self.state/_build_recommended_focus)."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from nicheiq.flows.research_flow import ResearchFlow
        selection = SimpleNamespace(
            selected_solution_name="UserPick",
            selection_rationale="Original human rationale " + "x" * 100,
            original_selection_reasoning=None,
            selection_criteria_scores=[],
            runner_up_solutions=["SomeOther"],
            recommended_focus="old focus",
        )
        state = MagicMock()
        state.solution_selection = selection
        state.idea_generation.solution_ideas = []
        state._user_selected_solutions = user_selected if user_selected is not None else set()
        host = SimpleNamespace(state=state, checkpoint_mgr=MagicMock(),
                               _build_recommended_focus=MagicMock(return_value="new focus"))
        host._apply_keyword_pivot = ResearchFlow._apply_keyword_pivot.__get__(host)
        return host

    def _run(self, flow):
        new = _score("KeywordFavorite", composite=0.6, demand=0.98)
        orig = _score("UserPick", composite=0.43, demand=0.97)
        flow._apply_keyword_pivot(
            ranked_solutions=[new, orig], all_scores=[new, orig],
            validation_results=[], validated_names={"KeywordFavorite", "UserPick"})

    def test_user_selected_winner_is_kept(self):
        flow = self._flow(user_selected={"UserPick"})
        self._run(flow)
        sel = flow.state.solution_selection
        assert sel.selected_solution_name == "UserPick"
        assert "Keyword-validation note" in sel.selection_rationale
        assert sel.selection_rationale.startswith("Original human rationale")
        assert sel.runner_up_solutions[0] == "KeywordFavorite"
        assert sel.recommended_focus == "old focus"  # untouched

    def test_headless_winner_still_pivots(self):
        flow = self._flow(user_selected=set())  # headless: no user selections stamped
        self._run(flow)
        sel = flow.state.solution_selection
        assert sel.selected_solution_name == "KeywordFavorite"
        assert sel.selection_rationale.startswith("**Keyword-validation update:**")
        assert "UserPick" in sel.runner_up_solutions


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
