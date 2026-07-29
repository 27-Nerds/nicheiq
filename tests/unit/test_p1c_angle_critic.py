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
