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

from nicheiq.config.settings import settings
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


@pytest.fixture(autouse=True)
def _deterministic_verdict_explanation(monkeypatch):
    """Default the verdict flags off so these tests are deterministic regardless of the prod defaults:
    no live LLM call (band path) and no SEO kill-floor (the floor-wiring tests opt back in per-test with
    a real kill-question shape). Angle-aware verdict is always on now (flag removed) but is a lift-only
    no-op unless a solution sets a real winning_angle — the non-angle tests here don't, so they stay
    equal-weight; LLM-path tests opt back in per-test."""
    monkeypatch.setattr(settings, "enable_llm_verdict_explanation", False)
    monkeypatch.setattr(settings, "enable_seo_kill_question_floor", False)


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
            is_fallback=False,
            trend_direction="declining",
            momentum_score=0.2,
            timing_recommendation="Missed Window",
            longevity_verdict="Risky",
            market_maturity="Mature",
        )
        verdict = generator._compute_go_no_go_verdict(MagicMock())
        assert verdict.verdict == "Conditional"  # trend caps at Conditional, never No-Go
        assert verdict.rationale.startswith("Note: verdict downgraded from Go to Conditional")
        assert verdict.trend_context  # context recorded for the UI

    def test_rationale_is_band_based_no_decimals_no_narrative_passthrough(self, generator):
        """The verdict owns its explanation: band language, no internal decimals, and the
        pre-verdict narrative is NOT passed through (it could argue a different outcome)."""
        import re
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        narrative = "This is a solid opportunity with strong fundamentals."
        verdict = generator._compute_go_no_go_verdict(MagicMock(), narrative_rationale=narrative)
        assert verdict.verdict == "Go"
        assert narrative not in verdict.rationale              # pre-verdict narrative dropped
        assert "Strong opportunity" in verdict.rationale       # band-based Go explanation
        assert not re.search(r"\d\.\d", verdict.rationale)     # no scoring decimals leaked


class TestAngleAwareVerdict:
    """Angle-aware verdict (always on — flag removed): the verdict average uses the ranking's angle
    weights, so a strong distribution_seo idea is not penalized for its intentionally-low novelty. No
    winning_angle => the exact equal-weight mean (lift-only no-op)."""

    # mf=0.72, novelty=0.30, tf=0.72, seo=0.95:
    #   equal-weight avg = (0.72+0.30+0.72+0.95)/4 = 0.6725  -> Conditional (< 0.72 Go threshold)
    #   distribution_seo  = .30*.72+.15*.72+.15*.30+.40*.95 = 0.749  -> Go  (min(mf,tf)=0.72 >= 0.60)
    _SCORES = (0.72, 0.30, 0.72, 0.95)

    def test_distribution_seo_reconciles_to_go(self, generator):
        generator._enriched_solution = None
        _set_scores(generator, *self._SCORES)
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="distribution_seo"))
        assert v.verdict == "Go"  # angle-weighted 0.749 — low novelty no longer drags it down

    def test_no_angle_is_equal_weight(self, generator):
        generator._enriched_solution = None
        _set_scores(generator, *self._SCORES)
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle=None))
        assert v.verdict == "Conditional"  # no winning_angle => equal-weight no-op

    def test_angle_weight_keeps_min_gate(self, generator):
        """Angle weighting must NOT let a weak-feasibility idea sneak to Go — the min(mf,tf) gate holds."""
        generator._enriched_solution = None
        # high seo + mf but tech_feasibility 0.45 < 0.60 Go-min: angle avg may be high, but the gate blocks Go
        _set_scores(generator, 0.8, 0.3, 0.45, 0.98)
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="distribution_seo"))
        assert v.verdict != "Go"

    def test_lift_only_never_demotes(self, generator):
        """LIFT-ONLY: a weak-in-lane idea (angle avg < equal avg) keeps its equal-weight verdict — the
        angle weighting can only help, so a winning_angle MISCLASSIFICATION can't tank a deserving idea."""
        generator._enriched_solution = None
        # distribution_seo with weak SEO: equal (0.68+0.55+0.68+0.30)/4 = 0.5525 (Conditional);
        # angle-weighted = 0.509 (No-Go under symmetric weighting). max() keeps it Conditional.
        _set_scores(generator, 0.68, 0.55, 0.68, 0.30)
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="distribution_seo"))
        assert v.verdict == "Conditional"  # NOT demoted to No-Go


class TestVerdictNoInternalScores:
    """Verdict prose uses qualitative bands, never the internal decimals."""

    import re as _re

    def test_go_rationale_has_no_decimals(self, generator):
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        v = generator._compute_go_no_go_verdict(MagicMock())
        assert v.verdict == "Go"
        assert not self._re.search(r"\d\.\d", v.rationale)

    def test_nogo_concern_and_rationale_use_bands_not_decimals(self, generator):
        _set_scores(generator, 0.3, 0.3, 0.4, 0.3)
        v = generator._compute_go_no_go_verdict(MagicMock())
        assert v.verdict == "No-Go"
        assert not self._re.search(r"\d\.\d", v.rationale or "")
        assert not self._re.search(r"\d\.\d", v.primary_concern or "")
        assert "market fit" in v.primary_concern.lower()  # names the weak dimension in words


class TestScoreBand:
    """score_band: 0-1 score -> plain qualitative word (no decimals leak into verdict prose)."""

    def test_bands(self):
        from nicheiq.utils.score_helpers import score_band
        assert score_band(0.95) == "strong"
        assert score_band(0.80) == "strong"
        assert score_band(0.70) == "good"
        assert score_band(0.55) == "moderate"
        assert score_band(0.40) == "limited"
        assert score_band(0.20) == "weak"
        assert score_band(None) == "unrated"


class TestLlmVerdictExplanation:
    """enable_llm_verdict_explanation: the LLM EXPLAINS the decided verdict; it never decides it, and
    its output is validated (verdict-stance consistent, no internal decimals) with a band fallback."""

    # --- the validation guard (pure) ---
    def test_valid_go_text_accepted(self):
        assert ReportGenerator._verdict_explanation_valid(
            "Good market fit and a solid distribution angle make this worth building now.", "Go")

    def test_decimals_rejected(self):
        assert not ReportGenerator._verdict_explanation_valid(
            "Market fit of 0.82 makes this a clear winner for the segment.", "Go")

    def test_percentages_rejected(self):
        assert not ReportGenerator._verdict_explanation_valid(
            "With 80% market fit this is a strong, buildable opportunity today.", "Go")

    def test_nogo_endorsement_rejected(self):
        assert not ReportGenerator._verdict_explanation_valid(
            "This is a strong opportunity worth pursuing right away with confidence.", "No-Go")

    def test_go_rejection_language_rejected(self):
        assert not ReportGenerator._verdict_explanation_valid(
            "Weak fundamentals make this not viable; do not build it at all.", "Go")

    def test_too_short_rejected(self):
        assert not ReportGenerator._verdict_explanation_valid("Good.", "Go")

    # --- routing through _compute_go_no_go_verdict ---
    def test_flag_on_uses_validated_llm_text(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_llm_verdict_explanation", True)
        monkeypatch.setattr(generator, "_llm_verdict_explanation",
                            lambda **kw: "Good market fit and a strong SEO angle clear the bar here.")
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        v = generator._compute_go_no_go_verdict(MagicMock())
        assert v.verdict == "Go"
        assert "strong SEO angle" in v.rationale  # LLM text used

    def test_flag_on_llm_none_falls_back_to_band(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_llm_verdict_explanation", True)
        monkeypatch.setattr(generator, "_llm_verdict_explanation", lambda **kw: None)
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        v = generator._compute_go_no_go_verdict(MagicMock())
        assert "Strong opportunity" in v.rationale  # deterministic band fallback

    def test_flag_off_never_calls_llm(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_llm_verdict_explanation", False)
        called = {"n": 0}
        monkeypatch.setattr(generator, "_llm_verdict_explanation",
                            lambda **kw: called.__setitem__("n", called["n"] + 1) or "x")
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        generator._compute_go_no_go_verdict(MagicMock())
        assert called["n"] == 0  # band template path, no LLM call

    # --- the real LLM-call wiring (LLMService mocked) ---
    def test_llm_wiring_uses_validated_result(self, generator, monkeypatch):
        from nicheiq.models.executive_summary import VerdictExplanation
        import nicheiq.report.report_generator as rg
        monkeypatch.setattr(generator, "_record_cost", lambda *a, **k: None)
        generator._enriched_solution = SimpleNamespace(solution_name="X")
        monkeypatch.setattr(rg.LLMService, "invoke_structured", lambda **kw: (
            VerdictExplanation(explanation="Good market fit with a strong SEO angle makes this a build."), {}))
        out = generator._llm_verdict_explanation(
            verdict="Go", primary_concern=None, mf_band="good", ca_band="moderate",
            feasibility_band="good", seo_band="strong", winning_angle="distribution_seo", downgrade_note=None)
        assert out and "strong SEO angle" in out

    def test_llm_wiring_rejects_decimal_result(self, generator, monkeypatch):
        from nicheiq.models.executive_summary import VerdictExplanation
        import nicheiq.report.report_generator as rg
        monkeypatch.setattr(generator, "_record_cost", lambda *a, **k: None)
        generator._enriched_solution = SimpleNamespace(solution_name="X")
        monkeypatch.setattr(rg.LLMService, "invoke_structured", lambda **kw: (
            VerdictExplanation(explanation="Market fit of 0.82 makes this strong and worth building soon."), {}))
        out = generator._llm_verdict_explanation(
            verdict="Go", primary_concern=None, mf_band="good", ca_band="moderate",
            feasibility_band="good", seo_band="strong", winning_angle=None, downgrade_note=None)
        assert out is None  # decimal leaked -> rejected -> caller uses band template


class TestSeoKillFloorWiring:
    """The kill-question floor block: distribution_seo + flag on + failing kill-question → downgrade."""

    def test_floor_downgrades_distribution_seo_go(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_seo_kill_question_floor", True)
        generator._enriched_solution = None
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)  # solid Go pre-floor
        generator.state.seo_strategy_report = SimpleNamespace(seo_kill_question=SimpleNamespace(
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=100, indexable_page_ceiling=120))  # dense coverage → floor acts
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="distribution_seo"))
        assert v.verdict == "Conditional"  # floored from Go (no winnable page universe)

    def test_floor_skips_non_distribution_angle(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_seo_kill_question_floor", True)
        generator._enriched_solution = None
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        generator.state.seo_strategy_report = SimpleNamespace(seo_kill_question=SimpleNamespace(
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=100, indexable_page_ceiling=120))
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="novel_differentiation"))
        assert v.verdict == "Go"  # floor is distribution_seo-only

    def test_floor_off_is_noop(self, generator, monkeypatch):
        monkeypatch.setattr(settings, "enable_seo_kill_question_floor", False)
        generator._enriched_solution = None
        _set_scores(generator, 0.9, 0.85, 0.9, 0.85)
        generator.state.seo_strategy_report = SimpleNamespace(seo_kill_question=SimpleNamespace(
            winnable_pages=0, median_keyword_difficulty=20.0, penalty_risk_flag=False,
            kd_sample_size=100, indexable_page_ceiling=120))
        v = generator._compute_go_no_go_verdict(SimpleNamespace(winning_angle="distribution_seo"))
        assert v.verdict == "Go"  # flag off → floor skipped
