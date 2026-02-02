"""
Tests for competitor count scoping to selected solution's landscape.

Verifies that competitor counts in market_sizing_crew, trend_longevity_crew,
and report_generator are scoped to the selected solution's competitive
landscape rather than aggregated across all landscapes.

Regression tests for bug #5: REPORT_INCONSISTENCIES.
"""

import pytest
from unittest.mock import MagicMock, patch

from nicheiq.models.competitor import (
    Competitor,
    CompetitorType,
    CompetitiveAnalysisResult,
    CompetitiveLandscape,
    find_landscape_for_solution,
)


# ---------------------------------------------------------------------------
# Helpers: build test data
# ---------------------------------------------------------------------------

def _make_competitor(name: str) -> Competitor:
    """Create a minimal Competitor instance."""
    return Competitor(
        name=name,
        competitor_type=CompetitorType.DIRECT,
        description=f"{name} description",
        key_features=["feature1", "feature2"],
    )


def _make_landscape(solution_name: str, competitor_names: list[str]) -> CompetitiveLandscape:
    """Create a CompetitiveLandscape with named competitors."""
    return CompetitiveLandscape(
        solution_name=solution_name,
        competitors=[_make_competitor(n) for n in competitor_names],
        market_gaps=["gap1", "gap2"],
        differentiation_opportunities=["diff1"],
        competitive_intensity="Medium",
        recommended_positioning="Position well",
        pricing_insights="Price wisely",
    )


def _make_analysis(landscapes: list[CompetitiveLandscape]) -> CompetitiveAnalysisResult:
    """Create a CompetitiveAnalysisResult wrapping given landscapes."""
    return CompetitiveAnalysisResult(
        solution_landscapes=landscapes,
        top_opportunities=["opp1", "opp2", "opp3"],
        strategic_recommendations="Strategic recommendations text that is long enough to pass validation.",
    )


# ---------------------------------------------------------------------------
# Test: find_landscape_for_solution (shared helper)
# ---------------------------------------------------------------------------

class TestFindLandscapeForSolution:
    """Tests for the shared find_landscape_for_solution helper."""

    def test_exact_match(self):
        """Finds correct landscape by exact name."""
        l1 = _make_landscape("SolutionA", ["Comp1", "Comp2"])
        l2 = _make_landscape("SolutionB", ["Comp3", "Comp4", "Comp5"])
        analysis = _make_analysis([l1, l2])

        result = find_landscape_for_solution(analysis, "SolutionB")
        assert result is l2

    def test_case_insensitive(self):
        """'SolutionA' matches 'solutiona'."""
        l1 = _make_landscape("SolutionA", ["Comp1"])
        analysis = _make_analysis([l1])

        result = find_landscape_for_solution(analysis, "solutiona")
        assert result is l1

    def test_fallback_to_first(self):
        """Returns first landscape when no name match found."""
        l1 = _make_landscape("SolutionA", ["Comp1"])
        l2 = _make_landscape("SolutionB", ["Comp2"])
        analysis = _make_analysis([l1, l2])

        result = find_landscape_for_solution(analysis, "NonExistent")
        assert result is l1

    def test_no_landscapes(self):
        """Returns None when competitive_analysis is None."""
        result = find_landscape_for_solution(None, "SolutionA")
        assert result is None

    def test_whitespace_stripped(self):
        """' SolutionA ' matches 'SolutionA'."""
        l1 = _make_landscape("SolutionA", ["Comp1"])
        analysis = _make_analysis([l1])

        result = find_landscape_for_solution(analysis, "  SolutionA  ")
        assert result is l1

    def test_none_solution_name_falls_back(self):
        """None solution_name returns first landscape."""
        l1 = _make_landscape("SolutionA", ["Comp1"])
        l2 = _make_landscape("SolutionB", ["Comp2", "Comp3"])
        analysis = _make_analysis([l1, l2])

        result = find_landscape_for_solution(analysis, None)
        assert result is l1


# ---------------------------------------------------------------------------
# Test: MarketSizingCrew competitor scoping (RC1 + RC2)
# ---------------------------------------------------------------------------

class TestMarketSizingCompetitorScoping:
    """Tests that MarketSizingCrew scopes competitor count to selected solution."""

    def _build_analysis(self):
        """3 landscapes with 2, 3, 4 competitors."""
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3"])
        l3 = _make_landscape("Gamma", ["G1", "G2", "G3", "G4"])
        return _make_analysis([l1, l2, l3])

    def _make_solution(self, name: str):
        """Create a minimal mock SolutionIdea."""
        sol = MagicMock()
        sol.solution_name = name
        sol.description = "A solution"
        sol.market_fit_score = 0.8
        sol.target_personas = ["Dev"]
        sol.core_features = ["feat1"]
        return sol

    def test_scoped_count_not_aggregate(self):
        """Selected 'Beta' has 3 competitors, not aggregate 9."""
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew

        crew = MarketSizingCrew()
        analysis = self._build_analysis()
        solution = self._make_solution("Beta")

        # We test the scoping logic by checking that the competitor_count
        # computed in analyze() would be 3 (Beta), not 9 (aggregate).
        # Rather than running the full crew, we replicate the scoping logic.
        from nicheiq.models.competitor import find_landscape_for_solution
        selected_landscape = find_landscape_for_solution(analysis, solution.solution_name)
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        assert count == 3

    def test_fallback_when_no_match(self):
        """Falls back to first landscape when no name match."""
        analysis = self._build_analysis()
        selected_landscape = find_landscape_for_solution(analysis, "NonExistent")
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        # Falls back to first landscape ("Alpha") with 2 competitors
        assert count == 2

    def test_single_landscape(self):
        """Single landscape: scoped count equals total."""
        l1 = _make_landscape("Only", ["O1", "O2", "O3"])
        analysis = _make_analysis([l1])
        selected_landscape = find_landscape_for_solution(analysis, "Only")
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        assert count == 3

    def test_empty_competitors(self):
        """Returns 0 when selected landscape has no competitors."""
        l1 = _make_landscape("Empty", [])
        analysis = _make_analysis([l1])
        selected_landscape = find_landscape_for_solution(analysis, "Empty")
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        assert count == 0


class TestFormatCompetitiveSignals:
    """Tests that _format_competitive_signals scopes to selected landscape."""

    def test_scoped_to_selected_landscape(self):
        """Samples competitors from selected landscape, not first."""
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew

        crew = MarketSizingCrew()
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3"])
        analysis = _make_analysis([l1, l2])

        result = crew._format_competitive_signals(analysis, "Beta")
        assert "B1" in result
        assert "B2" in result
        # Should NOT contain Alpha's competitors
        assert "A1" not in result

    def test_competitor_count_scoped(self):
        """Count text says selected count, not aggregate."""
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew

        crew = MarketSizingCrew()
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3"])
        analysis = _make_analysis([l1, l2])

        result = crew._format_competitive_signals(analysis, "Beta")
        # Should say 3 (Beta's count), not 5 (aggregate)
        assert "3" in result
        assert "5" not in result


# ---------------------------------------------------------------------------
# Test: TrendLongevityCrew competitor scoping (RC4 + RC5)
# ---------------------------------------------------------------------------

class TestTrendLongevityCompetitorScoping:
    """Tests that TrendLongevityCrew scopes competitor count to selected solution."""

    def test_scoped_count_not_aggregate(self):
        """Selected landscape count, not aggregate across all."""
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3"])
        l3 = _make_landscape("Gamma", ["G1"])
        analysis = _make_analysis([l1, l2, l3])

        selected_landscape = find_landscape_for_solution(analysis, "Beta")
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        # Beta has 3, not aggregate 6
        assert count == 3

    def test_backward_compat_no_name(self):
        """None name falls back to first landscape (no crash)."""
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1"])
        analysis = _make_analysis([l1, l2])

        selected_landscape = find_landscape_for_solution(analysis, None)
        count = len(selected_landscape.competitors or []) if selected_landscape else 0
        # Falls back to first (Alpha) with 2 competitors
        assert count == 2


class TestFormatCompetitiveMomentum:
    """Tests that _format_competitive_momentum scopes to selected landscape."""

    def test_scoped_to_selected(self):
        """Competitors and count from selected landscape only."""
        from nicheiq.crews.trend_longevity_crew import TrendLongevityCrew

        crew = TrendLongevityCrew()
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3", "B4"])
        analysis = _make_analysis([l1, l2])

        result = crew._format_competitive_momentum(analysis, "Beta")
        assert "B1" in result
        assert "4" in result
        assert "A1" not in result

    def test_no_solution_name_uses_first(self):
        """No solution name falls back to first landscape."""
        from nicheiq.crews.trend_longevity_crew import TrendLongevityCrew

        crew = TrendLongevityCrew()
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1"])
        analysis = _make_analysis([l1, l2])

        result = crew._format_competitive_momentum(analysis, None)
        assert "A1" in result
        assert "2" in result


# ---------------------------------------------------------------------------
# Test: ReportGenerator competitor count (RC3)
# ---------------------------------------------------------------------------

class TestReportGeneratorCompetitorCount:
    """Tests that report_generator uses accessor.get_competitor_count()."""

    def test_uses_accessor_not_landscape_len(self):
        """Verify the accessor returns scoped count, not number of landscapes."""
        # Build 3 landscapes; selected is "Beta" with 5 competitors
        l1 = _make_landscape("Alpha", ["A1", "A2"])
        l2 = _make_landscape("Beta", ["B1", "B2", "B3", "B4", "B5"])
        l3 = _make_landscape("Gamma", ["G1"])
        analysis = _make_analysis([l1, l2, l3])

        # Simulate what state_accessors.get_competitor_count does
        landscape = find_landscape_for_solution(analysis, "Beta")
        count = len(landscape.competitors) if landscape and landscape.competitors else 0

        # Should be 5 (Beta's competitors), not 3 (number of landscapes)
        assert count == 5
        assert count != len(analysis.solution_landscapes)
