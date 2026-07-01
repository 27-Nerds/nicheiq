"""P1a — provisional winning_angle + idea_focus force-override (respecting the seo hard-floor)."""

from types import SimpleNamespace

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew(idea_focus):
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c.idea_focus = idea_focus
    return c


class TestProvisionalAngle:
    def test_forced_distribution(self):
        assert _crew("distribution")._provisional_angle(SimpleNamespace(project_type="saas")) == "distribution_seo"

    def test_forced_novelty(self):
        assert _crew("novelty")._provisional_angle(SimpleNamespace(project_type="directory")) == "novel_differentiation"

    def test_auto_directory_is_distribution(self):
        assert _crew("auto")._provisional_angle(SimpleNamespace(project_type="aggregator")) == "distribution_seo"

    def test_auto_saas_is_novel(self):
        assert _crew("auto")._provisional_angle(SimpleNamespace(project_type="saas")) == "novel_differentiation"


class TestForceOverride:
    @pytest.fixture(autouse=True)
    def _flags(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        monkeypatch.setattr(settings, "enable_score_calibration", False)  # skip the live re-calibrate

    def test_force_overrides_classifier_angle(self):
        idea = SimpleNamespace(winning_angle="novel_differentiation", seo_scalability_score=0.8)
        _crew("distribution")._reconcile_angle_after_classify(idea, provisional_angle="distribution_seo", usages=[])
        assert idea.winning_angle == "distribution_seo"

    def test_force_respects_seo_floor(self):
        # idea_focus=distribution but no SEO surface (seo<0.35) → keep the classifier's angle, don't force
        idea = SimpleNamespace(winning_angle="novel_differentiation", seo_scalability_score=0.2)
        _crew("distribution")._reconcile_angle_after_classify(idea, provisional_angle="distribution_seo", usages=[])
        assert idea.winning_angle == "novel_differentiation"

    def test_auto_mode_no_force(self):
        idea = SimpleNamespace(winning_angle="novel_differentiation", seo_scalability_score=0.8)
        _crew("auto")._reconcile_angle_after_classify(idea, provisional_angle="novel_differentiation", usages=[])
        assert idea.winning_angle == "novel_differentiation"

    def test_flag_off_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        idea = SimpleNamespace(winning_angle="novel_differentiation", seo_scalability_score=0.8)
        _crew("distribution")._reconcile_angle_after_classify(idea, provisional_angle="distribution_seo", usages=[])
        assert idea.winning_angle == "novel_differentiation"  # untouched
