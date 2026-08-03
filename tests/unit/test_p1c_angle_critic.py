"""P1c — angle-conditional critic: coherence-lock exemption for distribution_seo, bounded + honest.

The exemption suspends the novelty≤1−obviousness clamp for SEO plays (an obvious shape is the correct
form) but (a) never touches obviousness_score (the Originality tag stays honest) and (b) replaces the
clamp with a fixed moderate ceiling so the exemption can't inflate novelty.
"""

from types import SimpleNamespace

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import (
    UnifiedSolutionCrew,
    _ANGLE_SEO_NOVELTY_CEIL,
)


def _crew():
    return UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)


def _idea(**kw):
    base = dict(novelty_score=None, obviousness_score=None, winning_angle=None,
                market_fit_score=0.5, data_access_model="public", build_feasibility_score=0.8,
                solo_dev_feasibility=0.6, technical_feasibility_score=0.7)
    base.update(kw)
    return SimpleNamespace(**base)


class TestCoherenceLockExemption:
    def test_flag_off_seo_idea_still_clamped(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        # obviousness 0.7 → ceil 0.3; novelty 0.7 > 0.3+0.25 → clamp to 0.30
        idea = _idea(novelty_score=0.7, obviousness_score=0.7, winning_angle="distribution_seo")
        _crew()._validate_idea_caps(idea)
        assert idea.novelty_score == 0.30

    def test_flag_on_seo_idea_exempt_from_coherence(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        # obviousness 0.7 would clamp novelty to 0.30 under the coherence lock; SEO exemption keeps the
        # critic's moderate 0.50 (it is <= the 0.55 ceiling), decoupled from obviousness.
        idea = _idea(novelty_score=0.5, obviousness_score=0.7, winning_angle="distribution_seo")
        _crew()._validate_idea_caps(idea)
        assert idea.novelty_score == 0.5

    def test_flag_on_seo_idea_bounded_by_moderate_ceiling(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        # exemption must not license inflation: novelty 0.8 is capped at the moderate ceiling, not 1−obv
        idea = _idea(novelty_score=0.8, obviousness_score=0.3, winning_angle="distribution_seo")
        _crew()._validate_idea_caps(idea)
        assert idea.novelty_score == _ANGLE_SEO_NOVELTY_CEIL

    def test_flag_on_non_seo_angle_still_clamped(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        idea = _idea(novelty_score=0.8, obviousness_score=0.7, winning_angle="novel_differentiation")
        _crew()._validate_idea_caps(idea)
        assert idea.novelty_score == 0.30  # coherence lock still applies off-angle

    def test_obviousness_never_mutated(self, monkeypatch):
        """Honesty: the exemption changes novelty only; obviousness (the Originality tag source) is honest."""
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        idea = _idea(novelty_score=0.8, obviousness_score=0.72, winning_angle="distribution_seo")
        _crew()._validate_idea_caps(idea)
        assert idea.obviousness_score == 0.72


class TestPromptExemptionGating:
    def _prompt(self):
        fake = SimpleNamespace(_format_competitor_mentions=lambda: "",
                               pain_point_analysis=SimpleNamespace(pain_points=[]))
        return UnifiedSolutionCrew._calibration_static_prompt(fake)[0]

    def test_exemption_absent_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        assert "ANGLE-CONDITIONAL" not in self._prompt()

    def test_exemption_present_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        p = self._prompt()
        assert "ANGLE-CONDITIONAL" in p and "SUSPENDED" in p


class TestRuleGUnverifiedRouteClaimCap:
    """Rule (g) — market_fit cap when the calibration critic claimed a data route while the
    verifier left dam 'unverified'. Ships 0.0 (disabled); downgrade-only; min-composes."""

    def _g_idea(self, **kw):
        base = dict(market_fit_score=0.8, data_access_model="unverified",
                    market_fit_claimed_route="DOT/NWS APIs")
        base.update(kw)
        return _idea(**base)

    def test_fires_only_on_contradiction_with_cap_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        idea = self._g_idea()
        reasons = _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
        assert any("claimed data route" in r for r in reasons)

    def test_default_zero_disables(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.0)
        idea = self._g_idea()
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.8

    def test_no_route_claim_no_cap(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        idea = self._g_idea(market_fit_claimed_route=None)
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.8

    def test_verified_dam_no_cap(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        idea = self._g_idea(data_access_model="public")
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.8

    def test_idempotent(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        idea = self._g_idea()
        crew = _crew()
        crew._validate_idea_caps(idea)
        second = crew._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
        assert not any("claimed data route" in r for r in second)  # no re-fire at the cap

    def test_min_composes_with_rule_b(self, monkeypatch):
        # (b) fires via build_feasibility < 0.5 (dam 'unverified' alone is NOT a (b) trigger)
        # and caps at 0.40; a HIGHER (g) cap never lifts it back up.
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        idea = self._g_idea(build_feasibility_score=0.3)
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.4

    def test_min_composes_with_rule_d_payability(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "payability_market_fit_cap", 0.55)
        idea = self._g_idea(source_segment_payability=0.1)
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45  # (d) 0.55 then (g) 0.45 — lowest wins
        # reverse dominance: a higher (g) cap loses to the (d) cap
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.6)
        idea2 = self._g_idea(source_segment_payability=0.1)
        _crew()._validate_idea_caps(idea2)
        assert idea2.market_fit_score == 0.55

    def test_min_composes_with_rule_e_parity(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "parity_shipped_market_fit_cap", 0.5)
        idea = self._g_idea(incumbent_parity="shipped by evidence: ToolX")
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45

    def test_min_composes_with_rule_f_selfissued_trust(self, monkeypatch):
        monkeypatch.setattr(settings, "unverified_route_claim_market_fit_cap", 0.45)
        monkeypatch.setattr(settings, "selfissued_trust_market_fit_cap", 0.5)
        idea = self._g_idea(solution_name="BadgeCo",
                            value_proposition="self-serve verified badge generator",
                            description="generates badges")
        _crew()._validate_idea_caps(idea)
        assert idea.market_fit_score == 0.45
