"""Regressions for the 2026-08-02 Sev-1 (job 8ef396eb) and its siblings.

The live run shipped a completed, paid report with ``executive_dashboard: null`` because
``SolutionSnapshot.project_type`` was declared ``str`` and the winning idea's project_type was
None. The verdict machinery ran correctly seventeen seconds later and produced three NEGATIVE
signals plus an explanation — none of which reached the reader.

Covered here:
- a None project_type still produces a dashboard, and the verdict survives intact;
- the same for every other descriptive section (metrics / core pain / snapshot);
- a verdict-bearing failure is LOUD (raises) instead of degrading to None;
- sub-1% shares never render as "0%";
- skipped stages are excluded from completed_stages and named in the caveats.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.config.settings import settings
from nicheiq.models.executive_summary import CorePainPoint, GoNoGoVerdict, KeyMetrics
from nicheiq.report.report_generator import (
    ExecutiveDashboardError,
    ReportGenerator,
    _format_percent,
    _format_share,
    _rescale_money_text,
)


@pytest.fixture(autouse=True)
def _deterministic_verdict_explanation(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm_verdict_explanation", False)


def _key_metrics() -> KeyMetrics:
    return KeyMetrics(
        total_keyword_search_volume=1000,
        tier0_keyword_count=1,
        tier1_keyword_count=2,
        tier2_keyword_count=3,
        total_keyword_count=6,
        high_severity_pain_points=2,
        primary_competitor_count=3,
        avg_pain_point_severity=0.7,
        avg_commercial_intent=0.6,
        social_evidence_threads=25,
    )


def _core_pain() -> CorePainPoint:
    return CorePainPoint(
        title="Cannot calculate artist payouts under a versus deal",
        severity_score=0.72,
        commercial_intent_score=0.61,
        representative_quote="I redo the settlement sheet three times every show.",
        source_platform="Reddit r/livesound",
    )


def _negative_verdict() -> GoNoGoVerdict:
    return GoNoGoVerdict(
        verdict="Conditional",
        rationale="Explanation of an already-decided verdict.",
        risk_level="High",
        primary_concern="Trend concern: Declining market",
        trend_context="Trend risk noted (already at the Conditional/Medium cap)",
        market_viability_context="Risk floor no-op (already Medium): Weak market viability",
        red_team_context="Red-team review: an adversarial evidence probe killed this idea",
    )


def _generator(solution) -> ReportGenerator:
    state = MagicMock()
    state.pain_point_quality_tier = "SILVER"
    gen = ReportGenerator(state)
    gen.accessor = MagicMock()
    gen.accessor.get_selected_solution_details.return_value = solution
    gen.score_accessor = MagicMock()
    for getter in (
        "get_market_fit",
        "get_competitive_advantage",
        "get_technical_feasibility",
        "get_seo_score_canonical",
    ):
        getattr(gen.score_accessor, getter).return_value = 0.7
    # Decorative LLM narrative is never exercised here.
    gen._generate_executive_narrative = MagicMock(return_value=None)
    gen._compute_go_no_go_verdict = MagicMock(return_value=_negative_verdict())
    gen._compute_executive_metrics = MagicMock(return_value=_key_metrics())
    gen._extract_core_pain_point = MagicMock(return_value=_core_pain())
    return gen


def _solution(**overrides):
    base = dict(
        solution_name="HouseNutIndex",
        headline="Pre-show settlement benchmarks for independent rooms",
        description="Benchmarks the house nut before the show.",
        target_personas=["Independent venue operator"],
        project_type=None,  # the Sev-1 input
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestNoneProjectTypeKeepsTheVerdict:
    """Sev-1: one nullable descriptive field must never delete the verdict."""

    def test_none_project_type_still_produces_a_dashboard(self):
        gen = _generator(_solution())

        dashboard = gen._generate_executive_dashboard(enriched_solution=_solution())

        assert dashboard is not None
        assert dashboard.recommended_solution_snapshot is not None
        assert dashboard.recommended_solution_snapshot.project_type is None
        assert dashboard.recommended_solution_snapshot.delivery_format is None
        assert dashboard.unavailable_sections == []

    def test_none_project_type_carries_the_negative_verdict_and_all_signals(self):
        gen = _generator(_solution())

        dashboard = gen._generate_executive_dashboard(enriched_solution=_solution())

        verdict = dashboard.go_no_go_verdict
        assert verdict.verdict == "Conditional"
        assert verdict.risk_level == "High"
        # The three computed signals from the live run must all reach the reader.
        assert "killed this idea" in verdict.red_team_context
        assert "Trend risk noted" in verdict.trend_context
        assert "Weak market viability" in verdict.market_viability_context
        assert verdict.rationale

    def test_blank_project_type_is_normalized_to_none_not_an_empty_badge(self):
        gen = _generator(_solution(project_type="   "))

        dashboard = gen._generate_executive_dashboard(enriched_solution=_solution(project_type="   "))

        assert dashboard.recommended_solution_snapshot.project_type is None

    def test_real_project_type_is_preserved(self):
        gen = _generator(_solution(project_type="directory"))

        dashboard = gen._generate_executive_dashboard(
            enriched_solution=_solution(project_type="directory")
        )

        assert dashboard.recommended_solution_snapshot.project_type == "directory"

    def test_delivery_format_is_preserved_independently_of_project_type(self):
        solution = _solution(
            project_type="saas",
            delivery_format="browser-extension",
        )
        gen = _generator(solution)

        dashboard = gen._generate_executive_dashboard(enriched_solution=solution)

        assert dashboard.recommended_solution_snapshot.delivery_format == "browser-extension"


class TestSupportingSectionsDegradeAlone:
    """Any descriptive section may go missing; the verdict may not."""

    def test_missing_metrics_marks_the_section_and_keeps_the_verdict(self):
        gen = _generator(_solution())
        gen._compute_executive_metrics = MagicMock(return_value=None)

        dashboard = gen._generate_executive_dashboard(enriched_solution=_solution())

        assert dashboard.key_metrics is None
        assert dashboard.unavailable_sections == ["key_metrics"]
        assert dashboard.go_no_go_verdict.verdict == "Conditional"

    def test_missing_core_pain_point_marks_the_section_and_keeps_the_verdict(self):
        gen = _generator(_solution())
        gen._extract_core_pain_point = MagicMock(return_value=None)

        dashboard = gen._generate_executive_dashboard(enriched_solution=_solution())

        assert dashboard.core_pain_point is None
        assert dashboard.unavailable_sections == ["core_pain_point"]
        assert dashboard.go_no_go_verdict.red_team_context

    def test_degraded_dashboard_raises_a_reader_facing_caveat(self):
        gen = _generator(_solution())
        gen._compute_executive_metrics = MagicMock(return_value=None)

        gen._generate_executive_dashboard(enriched_solution=_solution())

        assert gen._dashboard_caveats
        assert "key_metrics" in gen._dashboard_caveats[0]

    def test_no_selected_solution_is_the_only_none_dashboard(self):
        gen = _generator(None)

        assert gen._generate_executive_dashboard(enriched_solution=None) is None


class TestVerdictBearingFailureIsLoud:
    """A fail-soft that hides a computed verdict is worse than a loud failure."""

    def test_verdict_computation_failure_raises(self):
        gen = _generator(_solution())
        gen._compute_go_no_go_verdict = MagicMock(side_effect=RuntimeError("boom"))

        with pytest.raises(ExecutiveDashboardError):
            gen._generate_executive_dashboard(enriched_solution=_solution())

    def test_dashboard_assembly_failure_raises_naming_the_lost_verdict(self):
        gen = _generator(_solution())
        gen._compute_executive_metrics = MagicMock(return_value="not a KeyMetrics")

        with pytest.raises(ExecutiveDashboardError, match="Conditional"):
            gen._generate_executive_dashboard(enriched_solution=_solution())


class TestSmallShareFormatting:
    """Sev-2: `round(100 * 5230 / 2264020)` rendered a real 0.23% share as '0%'."""

    def test_the_live_run_share_is_not_zero(self):
        assert _format_share(5_230, 2_264_020) == "0.23%"

    @pytest.mark.parametrize("ratio", [0.000_001, 0.0001, 0.002_31, 0.009])
    def test_nonzero_shares_never_render_as_a_bare_zero(self, ratio):
        assert _format_percent(ratio) not in ("0%", "0.00%")

    def test_exact_zero_still_renders_zero(self):
        assert _format_percent(0.0) == "0%"
        assert _format_share(0, 100) == "0%"

    def test_missing_base_is_not_a_percentage(self):
        assert _format_share(5, 0) == "n/a"
        assert _format_percent(None) == "n/a"

    @pytest.mark.parametrize(
        "ratio,expected",
        [(0.523, "52%"), (1.0, "100%"), (0.05, "5.0%"), (0.0000001, "<0.01%")],
    )
    def test_resolution_follows_magnitude(self, ratio, expected):
        assert _format_percent(ratio) == expected


class TestSkippedStagesAreNotCompleted:
    """Sev-2: metadata listed stages 8 and 13 as completed after skipping them."""

    def _generator_with_stages(self, completed, skipped):
        state = MagicMock()
        state.completed_stages = completed
        state.skipped_stages = skipped
        state.fallback_stages = []
        state.filtering_stats = None
        state.started_at = None
        state.idea_funnel_counts = {}
        gen = ReportGenerator(state)
        gen.accessor = MagicMock()
        social = MagicMock()
        social.reddit_posts = []
        social.twitter_threads = []
        social.generic_posts = []
        social.model_dump_json.return_value = "{}"
        gen.accessor.get_social_content.return_value = social
        gen.accessor.get_subreddit_breakdown.return_value = {}
        return gen

    def test_skipped_stages_are_excluded_from_completed_stages(self):
        gen = self._generator_with_stages([1, 2, 8, 9, 13], [8, 13])

        metadata = gen._generate_research_metadata()

        assert metadata.completed_stages == [1, 2, 9]

    def test_completed_stages_unchanged_when_nothing_was_skipped(self):
        gen = self._generator_with_stages([1, 2, 3], [])

        assert gen._generate_research_metadata().completed_stages == [1, 2, 3]

    def test_skipped_stages_are_named_in_the_quality_caveats(self):
        state = MagicMock()
        state.seeded_from_catalog = False
        state.social_content_quality_tier = "GOOD"
        state.pain_point_quality_tier = "SILVER"
        state.pain_point_confidence_score = 0.7
        state.seo_strategy_report = None
        state.fallback_stages = []
        state.filtering_stats = None
        state.skipped_stages = [8, 13]
        state.niche_drift_telemetry = {}
        state.idea_coverage_caveats = []
        state.pipeline_degradations = []
        state.idea_ruled_out = []
        gen = ReportGenerator(state)
        gen.accessor = MagicMock()
        gen.accessor.get_volume_filter_ratio.return_value = None
        gen.accessor.get_selected_solution_details.return_value = SimpleNamespace(
            data_feasibility_score=0.82
        )

        caveats = gen._generate_data_quality_summary().quality_caveats

        assert any("Stage 13 (Data Source Research)" in c for c in caveats)
        assert any("Stage 8 (Traffic Monetization)" in c for c in caveats)
        # A data-feasibility score whose sourcing stage never ran must be flagged, not trusted.
        assert any("Data feasibility was not independently researched" in c for c in caveats)


class TestMoneyUnitsMatchMagnitude:
    """Sev-3: '$0.000227-$0.000454M' for what the prose calls '$227-$454'."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("$0.000227-$0.000454M", "$227-$454"),
            ("$0.000001-$0.000009M", "$1-$9"),
            (
                "$0.000001-$0.000009M in Year 1; $0.000011-$0.000045M in Year 3",
                "$1-$9 in Year 1; $11-$45 in Year 3",
            ),
        ],
    )
    def test_absurd_units_are_rescaled(self, raw, expected):
        assert _rescale_money_text(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["$2.5B", "$800M", "$300", "600K users", "Not calculated", "$50M+", "$5 million"]
    )
    def test_sane_values_are_left_alone(self, raw):
        assert _rescale_money_text(raw) == raw

    def test_a_one_sided_range_suffix_applies_to_both_ends(self):
        assert _rescale_money_text("$50-80M") == "$50M-$80M"

    def test_rescaling_is_idempotent(self):
        once = _rescale_money_text("$0.000227-$0.000454M")
        assert _rescale_money_text(once) == once

    def test_none_and_empty_pass_through(self):
        assert _rescale_money_text(None) is None
        assert _rescale_money_text("") == ""
