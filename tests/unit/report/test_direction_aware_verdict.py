"""P1d — angle-aware LIFT-ONLY verdict gate + buildability floor (enable_direction_aware_eval)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.config.settings import settings
from nicheiq.report.report_generator import ReportGenerator


@pytest.fixture
def generator(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm_verdict_explanation", False)  # use template, no live LLM
    state = MagicMock()
    state.trend_longevity = None      # skip trend downgrade (Phase 2)
    state.market_sizing = None        # skip viability floor (Phase 3)
    state.seo_strategy_report = None  # skip SEO kill-question (Phase 4)
    state.seeded_from_catalog = False
    gen = ReportGenerator(state)
    gen.score_accessor = MagicMock()
    gen.accessor = MagicMock()
    return gen


def _scores(gen, *, mf, tech, seo, nov):
    gen.score_accessor.get_market_fit.return_value = mf
    gen.score_accessor.get_technical_feasibility.return_value = tech
    gen.score_accessor.get_seo_score_canonical.return_value = seo
    gen.score_accessor.get_competitive_advantage.return_value = nov


def _verdict(gen, angle):
    return gen._compute_go_no_go_verdict(
        SimpleNamespace(winning_angle=angle), narrative_rationale="ok"
    ).verdict


class TestDirectionAwareGate:
    def test_seo_idea_moderate_tech_gets_go_only_with_flag(self, generator, monkeypatch):
        # Strong SEO play, moderate tech: avg clears 0.72 via the angle lift; the tech-based gate
        # (min(mf,tech)=0.55) blocks Go, but the SEO binding gate (min(mf,seo)=0.75) clears it.
        _scores(generator, mf=0.75, tech=0.55, seo=0.85, nov=0.5)
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        assert _verdict(generator, "distribution_seo") == "Conditional"   # tech-gated
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        assert _verdict(generator, "distribution_seo") == "Go"            # seo-gated

    def test_unbuildable_seo_idea_blocked_from_go_by_buildability_floor(self, generator, monkeypatch):
        # Great SEO but un-buildable (tech=0.2): the seo gate would pass, but the independent tech
        # buildability floor keeps it out of Go.
        _scores(generator, mf=0.8, tech=0.2, seo=1.0, nov=0.6)
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        assert _verdict(generator, "distribution_seo") == "Conditional"   # NOT Go

    def test_lift_only_never_demotes_misclassified_idea(self, generator, monkeypatch):
        # A strong tech idea mislabeled distribution_seo (low seo): the max() keeps the tech pass,
        # so the verdict is identical with the flag on vs off (no wrong demotion).
        _scores(generator, mf=0.8, tech=0.8, seo=0.3, nov=0.7)
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        off = _verdict(generator, "distribution_seo")
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        assert _verdict(generator, "distribution_seo") == off
