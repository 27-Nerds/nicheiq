"""
Tests for market sizing crew volume selection logic (Bug #13 fix).

Verifies that MarketSizingCrew.analyze() uses niche_relevant_volume
when available and falls back to total_volume for legacy data.
"""

import pytest
from unittest.mock import MagicMock, patch

from nicheiq.models.keyword_data import CrewKeywordValidationResult


def _make_keyword_validation(**overrides):
    """Helper to create a CrewKeywordValidationResult with defaults."""
    defaults = dict(
        solution_name="Test Solution",
        validated_count=20,
        total_volume=50000,
        avg_competition=40.0,
        keyword_demand_score=0.6,
        demand_signal="strong",
        validation_signals={"has_search_demand": True},
        attempts_made=1,
        best_relevance_score=0.7,
    )
    defaults.update(overrides)
    return CrewKeywordValidationResult(**defaults)


class TestMarketSizingVolumeSelection:
    """Test that market sizing crew selects the correct volume for TAM."""

    def test_uses_filtered_volume_when_available(self):
        """When niche_relevant_volume is set, it should be used instead of total_volume."""
        kv = _make_keyword_validation(
            total_volume=50000,
            niche_relevant_volume=12000,
        )
        # Explicit None check: niche_relevant_volume is not None → use it
        if kv.niche_relevant_volume is not None:
            kv_volume = kv.niche_relevant_volume
        else:
            kv_volume = kv.total_volume

        assert kv_volume == 12000

    def test_uses_total_volume_when_none(self):
        """When niche_relevant_volume is None (legacy), fall back to total_volume."""
        kv = _make_keyword_validation(
            total_volume=50000,
            niche_relevant_volume=None,
        )
        if kv.niche_relevant_volume is not None:
            kv_volume = kv.niche_relevant_volume
        else:
            kv_volume = kv.total_volume

        assert kv_volume == 50000

    def test_zero_does_not_fallback(self):
        """niche_relevant_volume=0 must NOT fall back to total_volume.

        Zero means semantic filtering found no relevant keywords —
        the correct TAM signal is 0, not the inflated total.
        """
        kv = _make_keyword_validation(
            total_volume=50000,
            niche_relevant_volume=0,
        )
        # This is the critical edge case: 0 is falsy but is not None
        if kv.niche_relevant_volume is not None:
            kv_volume = kv.niche_relevant_volume
        else:
            kv_volume = kv.total_volume

        assert kv_volume == 0

    def test_default_none_backward_compat(self):
        """CrewKeywordValidationResult without niche_relevant_volume defaults to None."""
        kv = _make_keyword_validation()
        assert kv.niche_relevant_volume is None

    def test_analyze_passes_filtered_volume(self):
        """Integration: analyze() passes niche_relevant_volume to crew inputs."""
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew

        # Set up mocks
        mock_crew_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.pydantic = MagicMock()
        mock_result.pydantic.total_addressable_market = "$100M"
        mock_result.pydantic.serviceable_available_market = "$30M"
        mock_result.pydantic.serviceable_obtainable_market_y1 = "$600K"
        mock_result.pydantic.market_viability_verdict = "Moderate"
        mock_result.pydantic.recommended_entry_strategy = "Measured Expansion"
        mock_crew_instance.kickoff.return_value = mock_result

        kv = _make_keyword_validation(
            total_volume=50000,
            niche_relevant_volume=12000,
        )

        solution = MagicMock()
        solution.solution_name = "Test"
        solution.description = "Test desc"
        solution.market_fit_score = 0.7
        solution.target_personas = []
        solution.core_features = []

        pain = MagicMock()
        pain.pain_points = []
        pain.total_mentions = 100

        comp = MagicMock()
        comp.solution_landscapes = []

        crew = MarketSizingCrew()
        # Patch the crew() method on the instance to avoid CrewAI decorator issues
        crew.crew = MagicMock(return_value=mock_crew_instance)
        crew.analyze(solution, kv, pain, comp, "test niche")

        # Verify kickoff was called with filtered volume
        call_args = mock_crew_instance.kickoff.call_args
        inputs = call_args.kwargs.get("inputs") or call_args[1].get("inputs")
        assert inputs["total_keyword_volume"] == 12000
        assert inputs["unfiltered_keyword_volume"] == 50000

    def test_analyze_falls_back_to_total_when_none(self):
        """Integration: analyze() uses total_volume when niche_relevant_volume is None."""
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew

        mock_crew_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.pydantic = MagicMock()
        mock_result.pydantic.total_addressable_market = "$100M"
        mock_result.pydantic.serviceable_available_market = "$30M"
        mock_result.pydantic.serviceable_obtainable_market_y1 = "$600K"
        mock_result.pydantic.market_viability_verdict = "Moderate"
        mock_result.pydantic.recommended_entry_strategy = "Measured Expansion"
        mock_crew_instance.kickoff.return_value = mock_result

        kv = _make_keyword_validation(
            total_volume=50000,
            # niche_relevant_volume defaults to None
        )

        solution = MagicMock()
        solution.solution_name = "Test"
        solution.description = "Test desc"
        solution.market_fit_score = 0.7
        solution.target_personas = []
        solution.core_features = []

        pain = MagicMock()
        pain.pain_points = []
        pain.total_mentions = 100

        comp = MagicMock()
        comp.solution_landscapes = []

        crew = MarketSizingCrew()
        crew.crew = MagicMock(return_value=mock_crew_instance)
        crew.analyze(solution, kv, pain, comp, "test niche")

        call_args = mock_crew_instance.kickoff.call_args
        inputs = call_args.kwargs.get("inputs") or call_args[1].get("inputs")
        assert inputs["total_keyword_volume"] == 50000
        assert inputs["unfiltered_keyword_volume"] == 50000
