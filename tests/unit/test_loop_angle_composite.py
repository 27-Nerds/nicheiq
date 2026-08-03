"""P1b — angle-weighted loop composite + structural seo_surface criterion (enable_direction_aware_eval)."""

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.idea_improvement_loop_v4 import IdeaCritiqueV4


def _crit(mf, nov, clarity, seo):
    return IdeaCritiqueV4(market_fit=mf, novelty=nov, clarity=clarity, seo_surface=seo,
                          on_anchor_pain=True, binding_constraint="novelty", directive="x",
                          meets_bar=False)


class TestAngleComposite:
    def test_flag_off_uses_legacy_weights_ignoring_seo(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", False)
        c = _crit(0.7, 0.3, 0.7, 0.9)
        # legacy 0.45*mf + 0.30*nov + 0.25*clarity ; seo_surface ignored, angle ignored
        assert c.composite("distribution_seo") == pytest.approx(0.58, abs=1e-6)

    def test_distribution_seo_rewards_seo_surface(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        c = _crit(0.7, 0.3, 0.7, 0.9)
        # 0.35*0.7 + 0.40*0.9 + 0.10*0.3 + 0.15*0.7 = 0.74 -> a strong-SEO/low-novelty idea clears the bar
        assert c.composite("distribution_seo") == pytest.approx(0.74, abs=1e-6)
        assert c.composite("distribution_seo") > c.composite(None)  # angle lifts it above legacy

    def test_novel_rewards_novelty(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        c = _crit(0.7, 0.9, 0.7, 0.3)
        # 0.35*0.7 + 0.40*0.9 + 0.10*0.3 + 0.15*0.7 = 0.74
        assert c.composite("novel_differentiation") == pytest.approx(0.74, abs=1e-6)

    def test_none_angle_falls_back_to_legacy_even_with_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_direction_aware_eval", True)
        c = _crit(0.7, 0.3, 0.7, 0.9)
        assert c.composite(None) == pytest.approx(0.58, abs=1e-6)  # legacy weights

    def test_seo_surface_defaults_to_neutral(self):
        # legacy/flag-off path where the reviewer never scores seo_surface -> default 0.5, no crash
        c = IdeaCritiqueV4(market_fit=0.6, novelty=0.5, clarity=0.6, on_anchor_pain=True,
                           binding_constraint="clarity", directive="x", meets_bar=False)
        assert c.seo_surface == 0.5
