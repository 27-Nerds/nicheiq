"""
Tests for score provenance & verdict consistency (Phase 3 fixes).

Covers:
- score_helpers: None propagation (no fabricated 0.5), composite over present
  scores, score_source tagging
- ScoreThresholds.from_settings: behavior-neutral mapping
- Verdict stability fixtures: identical verdicts for full-score solutions
  before/after the Optional-score change; present-score averaging with caveat;
  downgrade note prepended to the rationale (I1)
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.models.solution_selection import SolutionScores
from nicheiq.report.report_generator import ReportGenerator
from nicheiq.utils.score_helpers import (
    backfill_solution_scores,
    compute_solution_scores,
)
from nicheiq.validators.score_validators import ScoreThresholds


def _idea(name="Tool", mf=0.8, tf=0.7, novelty=0.6, seo=0.5):
    idea = MagicMock()
    idea.solution_name = name
    idea.market_fit_score = mf
    idea.technical_feasibility_score = tf
    idea.novelty_score = novelty
    idea.seo_scalability_score = seo
    return idea


class TestScoreHelpersNonePropagation:
    def test_missing_novelty_stays_none(self):
        scores = compute_solution_scores([_idea(novelty=None)])
        assert scores[0].competitive_advantage_score is None

    def test_missing_seo_stays_none(self):
        scores = compute_solution_scores([_idea(seo=None)])
        assert scores[0].seo_growth_potential_score is None

    def test_composite_averages_present_scores_only(self):
        """No more fabricated 0.5 dragging the composite toward neutral."""
        scores = compute_solution_scores([_idea(mf=0.9, tf=0.9, novelty=None, seo=None)])
        assert scores[0].composite_score == 0.9  # mean of 2 present, not (0.9+0.9+0.5+0.5)/4

    def test_full_scores_composite_unchanged(self):
        """Regression: solutions with all 4 scores keep the same composite."""
        scores = compute_solution_scores([_idea(mf=0.8, tf=0.7, novelty=0.6, seo=0.5)])
        assert scores[0].composite_score == round((0.8 + 0.7 + 0.6 + 0.5) / 4, 3)

    def test_interactive_source_tag(self):
        scores = compute_solution_scores([_idea()])
        assert scores[0].score_source == 'interactive'

    def test_backfill_source_tag_only_on_new_entries(self):
        existing = SolutionScores(
            solution_name="LLMScored",
            market_fit_score=0.8,
            technical_feasibility_score=0.8,
            competitive_advantage_score=0.7,
            seo_growth_potential_score=0.6,
            composite_score=0.725,
            rank=1,
            score_source='llm',
        )
        result = backfill_solution_scores([existing], [_idea(name="Missed")])
        by_name = {s.solution_name: s for s in result}
        assert by_name["LLMScored"].score_source == 'llm'
        assert by_name["Missed"].score_source == 'backfill'


class TestScoreThresholdsFromSettings:
    def test_empty_settings_yields_defaults(self):
        """No matching attrs → identical to no-arg construction (behavior-neutral)."""
        assert ScoreThresholds.from_settings(SimpleNamespace()) == ScoreThresholds()

    def test_settings_override_is_applied(self):
        thresholds = ScoreThresholds.from_settings(SimpleNamespace(verdict_go_avg_score=0.65))
        assert thresholds.verdict_go_avg_score == 0.65
        assert thresholds.verdict_conditional_avg_score == ScoreThresholds().verdict_conditional_avg_score

    def test_app_settings_defaults_match_threshold_defaults(self):
        """The 0ef15e3 regression pin: settings field DEFAULTS must equal
        ScoreThresholds defaults for every shared verdict field, so wiring
        from_settings into VerdictValidator changes nothing by default."""
        from nicheiq.config.settings import Settings

        shared = [
            name for name in ScoreThresholds.model_fields
            if name in Settings.model_fields
        ]
        assert shared, "expected shared threshold fields between Settings and ScoreThresholds"
        for name in shared:
            assert (
                Settings.model_fields[name].default
                == ScoreThresholds.model_fields[name].default
            ), f"default drift on '{name}'"


@pytest.fixture
def generator():
    """ReportGenerator with minimal mocked state and controllable scores."""
    state = MagicMock()
    state.trend_longevity = None
    state.market_sizing = None
    gen = ReportGenerator(state)
    gen.score_accessor = MagicMock()
    return gen


def _set_scores(gen, mf, ca, tf, seo):
    gen.score_accessor.get_market_fit.return_value = mf
    gen.score_accessor.get_competitive_advantage.return_value = ca
    gen.score_accessor.get_technical_feasibility.return_value = tf
    gen.score_accessor.get_seo_score_canonical.return_value = seo


class TestVerdictStability:
    """Fixture-pinned verdicts: the Optional-score change must not shift them."""

    def test_go_verdict_stable(self, generator):
        _set_scores(generator, 0.9, 0.8, 0.85, 0.75)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Go"
        assert verdict.risk_level == "Low"

    def test_conditional_verdict_stable(self, generator):
        _set_scores(generator, 0.6, 0.6, 0.6, 0.6)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Conditional"

    def test_nogo_verdict_stable(self, generator):
        _set_scores(generator, 0.3, 0.3, 0.4, 0.3)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "No-Go"

    def test_boundary_go_stable(self, generator):
        """avg exactly at the Go threshold with min individuals at the gate."""
        _set_scores(generator, 0.72, 0.72, 0.72, 0.72)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Go"

    def test_three_present_scores_average_with_caveat(self, generator):
        """None competitive_advantage → 3-score average + caveat, NOT a blanket
        insufficient-data Conditional (which would re-tighten verdicts)."""
        _set_scores(generator, 0.9, None, 0.85, 0.8)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Go"  # (0.9+0.85+0.8)/3 = 0.85 ≥ 0.72
        assert "competitive_advantage" in verdict.rationale
        assert "unavailable" in verdict.rationale

    def test_missing_required_score_bails_conditional(self, generator):
        _set_scores(generator, None, 0.8, 0.85, 0.8)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Conditional"
        assert verdict.primary_concern is not None
        assert "Missing score data" in verdict.primary_concern

    def test_two_missing_scores_bails_conditional(self, generator):
        _set_scores(generator, 0.9, None, 0.85, None)
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Conditional"
        assert "Missing score data" in (verdict.primary_concern or "")


class TestVerdictDowngradeReconciliation:
    """I1: a Phase-2 downgrade must be reconciled into the shipped rationale."""

    def test_trend_downgrade_prepends_note(self, generator):
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)  # solid Go before downgrade
        generator.state.trend_longevity = MagicMock(
            trend_direction="declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Risky",
            market_maturity="Mature",
        )
        narrative = "This is a solid opportunity with strong fundamentals and clear demand."
        verdict = generator._compute_go_no_go_verdict(MagicMock(), narrative_rationale=narrative)
        assert verdict.verdict == "Conditional"  # trend caps at Conditional, never No-Go
        assert verdict.rationale.startswith("Note: verdict downgraded from Go to Conditional")
        assert narrative in verdict.rationale  # original narrative preserved
        assert verdict.trend_context  # context recorded for the UI

    def test_no_downgrade_leaves_rationale_untouched(self, generator):
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        narrative = "This is a solid opportunity with strong fundamentals."
        verdict = generator._compute_go_no_go_verdict(MagicMock(), narrative_rationale=narrative)
        assert verdict.verdict == "Go"
        assert verdict.rationale == narrative
