"""LLM-prompt keyword signals must count the GRADED set (Codex review 2026-08 §4b).

Every crew that formats keyword validation into a prompt labelled the unfiltered
expansion pool as "Validated"/"Analyzed" keywords. The formatters are called unbound
so no CrewAI agent/LLM machinery is constructed.
"""

from types import SimpleNamespace

from nicheiq.crews.market_sizing_crew import MarketSizingCrew
from nicheiq.crews.traffic_monetization_crew import TrafficMonetizationCrew
from nicheiq.crews.trend_longevity_crew import TrendLongevityCrew
from nicheiq.models.keyword_data import CrewKeywordValidationResult


def _validation(**overrides):
    """Live 2026-08-02 shape: 50-keyword expansion pool, 1 keyword survived grading."""
    defaults = dict(
        solution_name="VetMedAudit",
        validated_count=50,
        total_volume=50000,
        avg_competition=40.0,
        keyword_demand_score=0.91,
        demand_signal="strong",
        validation_signals={"has_search_demand": True},
        attempts_made=1,
        best_relevance_score=0.7,
        validated_keywords=[{"keyword": "vet medication audit", "search_volume": 90}],
    )
    defaults.update(overrides)
    return CrewKeywordValidationResult(**defaults)


class TestMarketSizingKeywordSignals:
    def test_validated_keywords_line_counts_graded_set(self):
        signals = MarketSizingCrew._format_keyword_signals(None, _validation())
        assert "**Validated Keywords:** 1" in signals
        assert "**Validated Keywords:** 50" not in signals


class TestTrendLongevityKeywordSignals:
    def test_analyzed_keywords_line_counts_graded_set(self):
        signals = TrendLongevityCrew._format_keyword_trends(None, _validation())
        assert "**Analyzed Keywords:** 1" in signals
        assert "**Analyzed Keywords:** 50" not in signals

    def test_graded_and_empty_reports_zero(self):
        signals = TrendLongevityCrew._format_keyword_trends(
            None, _validation(validated_keywords=[])
        )
        assert "**Analyzed Keywords:** 0" in signals


class TestTrafficMonetizationKeywordData:
    def test_validated_keywords_line_counts_graded_set(self):
        formatted = TrafficMonetizationCrew._format_keyword_data(
            None, [_validation()], "VetMedAudit"
        )
        assert "**Validated Keywords:** 1" in formatted
        assert "**Validated Keywords:** 50" not in formatted


class TestStage6ProgressArtifact:
    """The SSE/progress payload publishes the count under the name
    `validated_keywords`, so it has to be the graded set (it was the pool count)."""

    def test_progress_payload_reports_graded_count(self):
        from nicheiq.flows.research_flow import ResearchFlow

        stub = SimpleNamespace(
            state=SimpleNamespace(
                seo_strategy_report=None,
                keyword_validation_results=[_validation()],
                solution_selection=None,
            )
        )
        artifact = ResearchFlow._build_stage_artifact(stub, 6)
        assert artifact["validated_keywords"] == 1
