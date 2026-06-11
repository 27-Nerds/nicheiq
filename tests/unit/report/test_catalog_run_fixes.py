"""
Tests for the catalog-run findings fixes (2026-06-11 golden run, job bca92a68).

Covers:
- Fix 2: fallback trend data skips the trend downgrade rules but floors risk
  at Medium with an explicit concern (catalog-aware wording when seeded).
- Fix 3: catalog-seeded runs get a Python-built ICP (no LLM) so the GTM
  blueprint can generate; non-catalog runs keep the None behavior.
- Fix 4: catalog-seeded runs rate data quality on keyword + competitor
  evidence (capped at MEDIUM) with an explicit caveat; non-seeded unchanged.

Example-anchoring (Fix 1) lives in tests/unit/test_numeric_guardrails.py.
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.models.research_state import TrendLongevityResult
from nicheiq.report.report_generator import ReportGenerator


@pytest.fixture
def generator():
    """ReportGenerator with minimal mocked state and controllable scores."""
    state = MagicMock()
    state.trend_longevity = None
    state.market_sizing = None
    state.seeded_from_catalog = False
    gen = ReportGenerator(state)
    gen.score_accessor = MagicMock()
    gen.accessor = MagicMock()
    return gen


def _set_go_scores(gen):
    gen.score_accessor.get_market_fit.return_value = 0.9
    gen.score_accessor.get_competitive_advantage.return_value = 0.85
    gen.score_accessor.get_technical_feasibility.return_value = 0.9
    gen.score_accessor.get_seo_score_canonical.return_value = 0.85


def _fallback_trend():
    return MagicMock(
        is_fallback=True,
        trend_direction="Stable",
        momentum_score=0.5,
        timing_recommendation="Monitor & Wait",
        longevity_verdict="Risky",
        market_maturity="Emerging",
    )


class TestFallbackTrendVerdictFloor:
    def test_fallback_skips_downgrade_and_floors_risk(self, generator):
        """Placeholder trend data must not produce 'Risky longevity' concerns,
        but must not leave a Go at Low risk either."""
        _set_go_scores(generator)
        generator.state.seeded_from_catalog = True
        generator.state.trend_longevity = _fallback_trend()

        verdict = generator._compute_go_no_go_verdict(
            MagicMock(), narrative_rationale="Solid opportunity."
        )

        assert verdict.verdict == "Go"  # fallback never downgrades the verdict
        assert verdict.risk_level == "Medium"  # floored from Low
        assert "Risky longevity" not in (verdict.primary_concern or "")
        assert "not validated" in verdict.primary_concern
        assert "Catalog-seeded" in verdict.trend_context

    def test_fallback_non_catalog_uses_generic_wording(self, generator):
        _set_go_scores(generator)
        generator.state.seeded_from_catalog = False
        generator.state.trend_longevity = _fallback_trend()

        verdict = generator._compute_go_no_go_verdict(
            MagicMock(), narrative_rationale="Solid opportunity."
        )

        assert verdict.risk_level == "Medium"
        assert "fallback data" in verdict.trend_context
        assert "Catalog-seeded" not in verdict.trend_context

    def test_fallback_does_not_lower_existing_risk(self, generator):
        """The floor is raise-only: a Conditional/Medium stays Medium, and a
        score-derived High risk must not be lowered."""
        # Weak-ish scores that produce Conditional + its own concern
        generator.score_accessor.get_market_fit.return_value = 0.62
        generator.score_accessor.get_competitive_advantage.return_value = 0.6
        generator.score_accessor.get_technical_feasibility.return_value = 0.62
        generator.score_accessor.get_seo_score_canonical.return_value = 0.6
        generator.state.trend_longevity = _fallback_trend()

        verdict = generator._compute_go_no_go_verdict(
            MagicMock(), narrative_rationale="Mixed signals."
        )
        assert verdict.risk_level in ("Medium", "High")  # never Low

    def test_real_trend_data_still_downgrades(self, generator):
        """Control: is_fallback=False keeps the existing downgrade behavior."""
        _set_go_scores(generator)
        generator.state.trend_longevity = MagicMock(
            is_fallback=False,
            trend_direction="declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Risky",
            market_maturity="Mature",
        )

        verdict = generator._compute_go_no_go_verdict(
            MagicMock(), narrative_rationale="Solid opportunity."
        )
        assert verdict.verdict == "Conditional"

    def test_is_fallback_survives_serialization_roundtrip(self):
        """Checkpoint persistence: the flag is a model field, so
        model_dump -> re-validate must preserve it."""
        result = TrendLongevityResult(
            is_fallback=True,
            trend_direction="Stable",
            trend_confidence="Low",
            momentum_score=0.5,
            keyword_volume_trend="Stable",
            discussion_frequency_trend="Stable",
            discussion_recency="Unknown",
            community_growth_indicators=["none"],
            new_entrants_trend="Stable",
            competitive_activity_level="Low",
            market_maturity="Emerging",
            longevity_verdict="Risky",
            longevity_rationale="fallback",
            trend_reversal_risks=["none"],
            timing_recommendation="Monitor & Wait",
            data_sources_analyzed=["Limited - fallback mode"],
            analysis_timeframe="N/A",
        )
        restored = TrendLongevityResult.model_validate(result.model_dump())
        assert restored.is_fallback is True

    def test_legacy_data_without_flag_is_not_fallback(self):
        """Old checkpoints predate the field — they must default to False."""
        result = TrendLongevityResult(
            trend_direction="Growing",
            trend_confidence="High",
            momentum_score=0.9,
            keyword_volume_trend="Increasing",
            discussion_frequency_trend="Increasing",
            discussion_recency="Recent",
            community_growth_indicators=["growing subreddit"],
            new_entrants_trend="Increasing",
            competitive_activity_level="Moderate",
            market_maturity="Growth",
            longevity_verdict="Sustainable",
            longevity_rationale="real analysis",
            trend_reversal_risks=["none identified"],
            timing_recommendation="Enter Now",
            data_sources_analyzed=["keywords", "social"],
            analysis_timeframe="12 months",
        )
        assert result.is_fallback is False


class TestCatalogICP:
    def _catalog_state(self, generator, personas):
        generator.state.seeded_from_catalog = True
        generator.state.pain_point_analysis.content_categorization = None
        generator.state.niche_context.market_segments = personas
        pp = MagicMock()
        pp.title = "Benchmark data is anecdotal"
        generator.accessor.get_sorted_pain_points.return_value = [pp]
        solution = MagicMock()
        solution.core_features = ["Searchable benchmarks", "GPU cost calculator"]
        generator.accessor.get_selected_solution_details.return_value = solution

    def test_catalog_run_gets_python_icp(self, generator):
        self._catalog_state(generator, ["Platform engineers", "ML researchers"])

        icp = generator._extract_ideal_customer_profile()

        assert icp is not None
        assert icp.persona_name == "Platform engineers"
        assert icp.pain_points == ["Benchmark data is anecdotal"]
        assert icp.goals == [
            "Achieve searchable benchmarks",
            "Achieve gpu cost calculator",
        ]
        # Soft fields must be honest sentinels, never invented demographics
        for field in (icp.demographics, icp.psychographics, icp.buying_triggers, icp.decision_criteria):
            assert "Catalog-seeded estimate" in field

    def test_catalog_run_without_personas_returns_none(self, generator):
        self._catalog_state(generator, [])
        assert generator._extract_ideal_customer_profile() is None

    def test_non_catalog_missing_categorization_still_returns_none(self, generator):
        generator.state.seeded_from_catalog = False
        generator.state.pain_point_analysis.content_categorization = None
        assert generator._extract_ideal_customer_profile() is None

    def test_gtm_blueprint_generates_from_catalog_icp(self, generator):
        """The original bug: ICP None -> GTM None. With the catalog ICP the
        blueprint must assemble (narrative/playbook helpers mocked with real
        models — GTMBlueprint forbids extras, so MagicMocks won't validate)."""
        from nicheiq.models.marketing_blueprint import (
            ContentAngle,
            First30DaysPlaybook,
            MarketingChannel,
        )

        self._catalog_state(generator, ["Platform engineers"])

        channel = MarketingChannel(
            channel_name="SEO Blog",
            channel_type="SEO",
            rationale="Keyword evidence",
            strategy="Publish benchmark content",
            priority="High",
        )
        angle = ContentAngle(
            title="Cold-start benchmarks",
            content_type="Blog Post",
            pain_point_addressed="Benchmark data is anecdotal",
            hook="Stop guessing.",
            key_points=["p1", "p2", "p3"],
            target_channel="SEO Blog",
        )
        narrative = MagicMock(
            core_marketing_message="msg",
            message_framework="framework",
            content_angles=[angle],
        )
        playbook = First30DaysPlaybook(
            week_1_actions=["a"],
            week_2_actions=["b"],
            week_3_actions=["c"],
            week_4_actions=["d"],
            success_metrics=["m"],
        )
        generator._identify_marketing_channels = MagicMock(return_value=[channel])
        generator._generate_marketing_narrative = MagicMock(return_value=narrative)
        generator._generate_first_30_days_playbook = MagicMock(return_value=playbook)
        generator._generate_budget_estimate = MagicMock(return_value=None)

        blueprint = generator._generate_gtm_blueprint()
        assert blueprint is not None
        assert "Catalog-seeded estimate" in blueprint.ideal_customer_profile.demographics


class TestCatalogDataQuality:
    def _quality_state(self, generator, *, seeded, tier0, tier1, competitors):
        generator.state.seeded_from_catalog = seeded
        generator.state.social_content_quality_tier = None
        generator.state.pain_point_quality_tier = None
        generator.state.pain_point_confidence_score = None
        generator.state.seo_strategy_report = MagicMock(
            tier_0_keywords=tier0, tier_1_keywords=tier1
        )
        generator.state.fallback_stages = []
        generator.state.filtering_stats = None
        generator.accessor.get_volume_filter_ratio.return_value = None
        generator.accessor.get_competitor_count.return_value = competitors

    def test_seeded_with_evidence_is_medium_with_caveat(self, generator):
        self._quality_state(generator, seeded=True, tier0=[], tier1=["kw"], competitors=3)
        summary = generator._generate_data_quality_summary()
        assert summary.overall_data_quality == "MEDIUM"
        assert any("Catalog-seeded" in c for c in summary.quality_caveats)

    def test_seeded_without_keywords_is_low(self, generator):
        self._quality_state(generator, seeded=True, tier0=[], tier1=[], competitors=3)
        summary = generator._generate_data_quality_summary()
        assert summary.overall_data_quality == "LOW"
        assert any("Catalog-seeded" in c for c in summary.quality_caveats)

    def test_seeded_without_competitors_is_low(self, generator):
        self._quality_state(generator, seeded=True, tier0=["kw"], tier1=[], competitors=0)
        summary = generator._generate_data_quality_summary()
        assert summary.overall_data_quality == "LOW"

    def test_seeded_never_high(self, generator):
        """Even with strong tiers set, seeded runs cap at MEDIUM."""
        self._quality_state(generator, seeded=True, tier0=["kw"], tier1=["kw"], competitors=5)
        generator.state.social_content_quality_tier = "EXCELLENT"
        generator.state.pain_point_quality_tier = "GOLD"
        summary = generator._generate_data_quality_summary()
        assert summary.overall_data_quality == "MEDIUM"

    def test_non_seeded_path_unchanged(self, generator):
        self._quality_state(generator, seeded=False, tier0=["kw"], tier1=["kw"], competitors=0)
        generator.state.social_content_quality_tier = "EXCELLENT"
        generator.state.pain_point_quality_tier = "GOLD"
        summary = generator._generate_data_quality_summary()
        assert summary.overall_data_quality == "HIGH"
        assert not any("Catalog-seeded" in c for c in summary.quality_caveats)
