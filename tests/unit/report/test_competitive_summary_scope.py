"""The competitor count in the prose must count the SELECTED idea's competitors.

Live 2026-08 (job 8ef396eb): the report's tile read "Alternatives reviewed: 2" (the selected
idea's landscape) while the prose beside it read "Identified 7 competitors" — the LAST
landscape Stage 5.5 analysed, a runner-up. `CompetitiveAnalysisResult.strategic_recommendations`
is one scalar field that every landscape overwrites, so the prose described a different
product entirely and read as a contradiction about one.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.report.utils.state_accessors import StateAccessor
from nicheiq.utils.competitive_summary import build_strategic_recommendations

LIVE_REPORT = Path(__file__).resolve().parents[3] / (
    "output/jobs/8ef396eb-c63d-4641-889e-1db6dfc9dfde/report.json"
)


def _landscape(name, n_competitors):
    return SimpleNamespace(
        solution_name=name,
        competitive_intensity="Moderate",
        competitors=[SimpleNamespace(name=f"Comp{i}") for i in range(n_competitors)],
        market_gaps=["gap one"],
        differentiation_opportunities=["opp one"],
        recommended_positioning="Position against incumbents on settlement accuracy.",
    )


class TestBuildStrategicRecommendations:
    def test_count_is_attributed_to_the_solution_it_counts(self):
        text = build_strategic_recommendations(_landscape("HouseNutIndex", 2))
        assert "Identified 2 direct competitors for HouseNutIndex." in text

    def test_singular_competitor_reads_correctly(self):
        text = build_strategic_recommendations(_landscape("HouseNutIndex", 1))
        assert "Identified 1 direct competitor for HouseNutIndex." in text

    def test_zero_competitors(self):
        text = build_strategic_recommendations(_landscape("HouseNutIndex", 0))
        assert "Identified 0 direct competitors for HouseNutIndex." in text

    def test_meets_the_model_min_length(self):
        bare = SimpleNamespace(
            solution_name="X", competitive_intensity="Low", competitors=[],
            market_gaps=[], differentiation_opportunities=[], recommended_positioning="-",
        )
        assert len(build_strategic_recommendations(bare)) >= 50


class TestGetCompetitiveSummary:
    def _accessor(self, landscapes, selected, stored_recs):
        state = MagicMock()
        state.competitive_analysis = SimpleNamespace(
            solution_landscapes=landscapes, strategic_recommendations=stored_recs
        )
        state.solution_selection = SimpleNamespace(selected_solution_name=selected)
        return StateAccessor(state)

    def test_prose_describes_the_selected_idea_not_the_last_analysed(self):
        """The 8ef396eb shape: selected idea has 2 competitors, a runner-up analysed
        afterwards has 7 and left its text in strategic_recommendations."""
        accessor = self._accessor(
            landscapes=[_landscape("HouseNutIndex", 2), _landscape("ShowClose Settlement Desk", 7)],
            selected="HouseNutIndex",
            stored_recs=build_strategic_recommendations(_landscape("ShowClose Settlement Desk", 7)),
        )
        summary = accessor.get_competitive_summary()
        assert "Identified 2 direct competitors for HouseNutIndex." in summary
        assert "7 direct competitors" not in summary
        assert "ShowClose" not in summary

    def test_prose_count_matches_the_alternatives_reviewed_tile(self):
        """Both numbers must come from the same landscape."""
        accessor = self._accessor(
            landscapes=[_landscape("HouseNutIndex", 2), _landscape("Other", 7)],
            selected="HouseNutIndex",
            stored_recs="stale text about Other",
        )
        assert f"Identified {accessor.get_competitor_count()} direct competitors" in (
            accessor.get_competitive_summary()
        )

    def test_falls_back_to_stored_text_when_no_landscape_matches(self):
        accessor = self._accessor(
            landscapes=[], selected="HouseNutIndex", stored_recs="stored fallback text"
        )
        assert accessor.get_competitive_summary() == "stored fallback text"

    def test_no_competitive_analysis_at_all(self):
        state = MagicMock()
        state.competitive_analysis = None
        state.solution_selection = None
        assert StateAccessor(state).get_competitive_summary() == "No competitive analysis available."


@pytest.mark.skipif(
    not LIVE_REPORT.exists(), reason="stored 8ef396eb report not present in this checkout"
)
class TestAgainstStoredLiveReport:
    @pytest.fixture(scope="class")
    def report(self):
        return json.loads(LIVE_REPORT.read_text())

    def test_the_stored_record_still_exhibits_the_defect(self, report):
        assert "Identified 7 competitors" in report["competitive_summary"]
        assert report["competitive_analytics"]["competitor_count"] == 2
        # The prose is about a runner-up, not the selected idea.
        assert report["selected_solution_name"] not in report["competitive_summary"]
        assert "ShowClose Settlement Desk" in report["competitive_summary"]

    def test_rebuilt_summary_agrees_with_the_tile(self, report):
        from nicheiq.models.competitor import (
            CompetitiveAnalysisResult,
            find_landscape_for_solution,
        )

        analysis = CompetitiveAnalysisResult(**report["competitive_analysis"])
        landscape = find_landscape_for_solution(analysis, report["selected_solution_name"])
        summary = build_strategic_recommendations(landscape)

        tile_count = report["competitive_analytics"]["competitor_count"]
        assert f"Identified {tile_count} direct competitors" in summary
        assert report["selected_solution_name"] in summary
        assert "Identified 7 " not in summary
