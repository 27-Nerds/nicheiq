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


class TestPayabilityReclassification:
    """2026-07-06 product decision: No-Go is reserved for STRUCTURAL blockers. A buildable idea
    whose market_fit was grounded by weak buyer payability presents as Conditional/High with the
    validation condition named — a paid analysis says "validate willingness-to-pay", not "no"."""

    def _sol(self, pay=0.2, cls="personal-wallet"):
        return SimpleNamespace(winning_angle=None, source_segment_payability=pay,
                               source_segment_payability_class=cls, tags=None)

    def test_buildable_weak_wallet_no_go_becomes_conditional_high(self, generator):
        # mf grounded to 0.4 by payability evidence; tech fine -> would be score-No-Go
        _scores(generator, mf=0.4, tech=0.75, seo=0.4, nov=0.4)
        v = generator._compute_go_no_go_verdict(self._sol(), narrative_rationale="ok")
        assert v.verdict == "Conditional"
        assert v.risk_level == "High"
        assert "willingness-to-pay" in v.primary_concern
        assert "spending personal money" in v.primary_concern   # human phrase, not the enum token
        assert "personal-wallet" not in v.primary_concern
        import re
        assert not re.search(r"\d\.\d", v.primary_concern)     # band-clean: no decimals

    def test_unbuildable_stays_no_go(self, generator):
        _scores(generator, mf=0.4, tech=0.4, seo=0.4, nov=0.4)   # tech below 0.6 = structural
        v = generator._compute_go_no_go_verdict(self._sol(), narrative_rationale="ok")
        assert v.verdict == "No-Go"

    def test_no_payability_stays_no_go(self, generator):
        _scores(generator, mf=0.4, tech=0.75, seo=0.4, nov=0.4)
        v = generator._compute_go_no_go_verdict(self._sol(pay=None, cls=None),
                                                narrative_rationale="ok")
        assert v.verdict == "No-Go"       # unscored payability: no reclassification (fail-open)

    def test_healthy_wallet_no_go_stays_no_go(self, generator):
        _scores(generator, mf=0.4, tech=0.75, seo=0.4, nov=0.4)
        v = generator._compute_go_no_go_verdict(self._sol(pay=0.65, cls="smb-budget"),
                                                narrative_rationale="ok")
        assert v.verdict == "No-Go"       # weak market with a REAL wallet is a genuine No-Go


