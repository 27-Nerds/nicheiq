"""Angle-aware ranking (Stage 2 of angle-aware idea evaluation).

Covers: the angle=None regression-lock (byte-identical to the equal-weight composite + drop),
the weighted-mean direction per angle, the weighted feasibility drop invariant
(w_tf·(tf−build)/Σw == recomputing the weighted mean with tf capped at build), monotonic
downgrade-only behaviour, winning_angle threaded through compute_solution_scores, and the
preview-grid `adjusted_composite_score` stamp (always angle-weighted).
"""

import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root, for `worker` package

import nicheiq.utils.score_helpers as sh
from nicheiq.config.settings import settings
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.score_helpers import (
    _ANGLE_WEIGHTS,
    _composite_for_angle,
    _composite_of_present,
    angle_ranked_composite,
    compute_solution_scores,
    feasibility_adjusted_composite,
)

ANGLES = list(_ANGLE_WEIGHTS)


@pytest.fixture
def critic_on(monkeypatch):
    monkeypatch.setattr(settings, "enable_feasibility_critic", True)
    yield


class TestRegressionLockAngleNone:
    def test_base_mean_identical_to_equal_weight(self):
        for mf, tf, ca, seo in itertools.product([0.3, 0.7], [0.4, 0.9], [0.2, 0.8, None], [0.1, 0.6, None]):
            assert _composite_for_angle(mf, tf, ca, seo, None) == _composite_of_present(mf, tf, ca, seo)
            assert _composite_for_angle(mf, tf, ca, seo, "unknown_angle") == _composite_of_present(mf, tf, ca, seo)

    def test_adjusted_composite_identical_to_legacy(self, critic_on):
        for mf, tf, ca, seo in itertools.product([0.3, 0.7], [0.4, 0.9], [0.2, 0.8, None], [0.1, 0.6, None]):
            base = _composite_of_present(mf, tf, ca, seo)
            for bf in (None, 0.3, 0.95):
                legacy = feasibility_adjusted_composite(base, mf, tf, ca, seo, bf)
                with_none = feasibility_adjusted_composite(base, mf, tf, ca, seo, bf, None)
                assert legacy == with_none


class TestWeightedDirection:
    def test_distribution_seo_rewards_seo(self):
        # high seo, low novelty -> distribution_seo composite beats the equal-weight mean
        w = _composite_for_angle(0.5, 0.5, 0.2, 0.9, "distribution_seo")
        assert w > _composite_of_present(0.5, 0.5, 0.2, 0.9)

    def test_novel_rewards_novelty(self):
        # high novelty, low seo -> novel_differentiation beats equal-weight
        w = _composite_for_angle(0.5, 0.5, 0.9, 0.1, "novel_differentiation")
        assert w > _composite_of_present(0.5, 0.5, 0.9, 0.1)

    def test_weights_sum_to_one(self):
        for angle, w in _ANGLE_WEIGHTS.items():
            assert abs(sum(w.values()) - 1.0) < 1e-9, angle


class TestWeightedDrop:
    @pytest.mark.parametrize("angle", ANGLES)
    def test_drop_equals_recompute_with_capped_tf(self, critic_on, angle):
        # Capping tf at build inside the weighted mean must equal subtracting w_tf·(tf−build)/Σw.
        mf, tf, ca, seo, build = 0.6, 0.9, 0.4, 0.7, 0.5
        base = _composite_for_angle(mf, tf, ca, seo, angle)
        adjusted = feasibility_adjusted_composite(base, mf, tf, ca, seo, build, angle)
        recomputed = _composite_for_angle(mf, build, ca, seo, angle)  # tf capped at build
        assert abs(adjusted - recomputed) <= 0.001

    @pytest.mark.parametrize("angle", ANGLES)
    def test_downgrade_only_never_raises(self, critic_on, angle):
        mf, tf, ca, seo = 0.6, 0.9, 0.4, 0.7
        base = _composite_for_angle(mf, tf, ca, seo, angle)
        # build >= tf -> no-op; build < tf -> strictly lower
        assert feasibility_adjusted_composite(base, mf, tf, ca, seo, 0.95, angle) == base
        assert feasibility_adjusted_composite(base, mf, tf, ca, seo, 0.5, angle) < base

    def test_unaffected_idea_untouched(self, critic_on):
        # build >= tf -> the weighted composite is preserved exactly (only build<tf ideas move).
        mf, tf, ca, seo = 0.6, 0.7, 0.4, 0.7
        base = _composite_for_angle(mf, tf, ca, seo, "distribution_seo")
        assert feasibility_adjusted_composite(base, mf, tf, ca, seo, 0.8, "distribution_seo") == base


class TestThreadingAndStamp:
    def _idea(self, name, angle, **kw):
        base = dict(
            solution_name=name, description="d" * 30, value_proposition="v",
            pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
            market_fit_score=0.6, technical_feasibility_score=0.6, novelty_score=0.3,
            seo_scalability_score=0.9, winning_angle=angle,
        )
        base.update(kw)
        return BaseSolutionIdea(**base)

    def test_compute_solution_scores_uses_winning_angle(self, monkeypatch):
        monkeypatch.setattr(settings, "enable_feasibility_critic", False)
        seo_idea = self._idea("Seo", "distribution_seo")
        none_idea = self._idea("Plain", None)
        scores = compute_solution_scores([seo_idea, none_idea])
        by = {s.solution_name: s for s in scores}
        # same sub-scores, but the distribution_seo idea is weighted toward its strong seo -> higher.
        assert by["Seo"].composite_score > by["Plain"].composite_score

    def test_angle_ranked_composite_on_dict(self):
        d = {"market_fit_score": 0.6, "technical_feasibility_score": 0.6, "novelty_score": 0.3,
             "seo_scalability_score": 0.9, "build_feasibility_score": None, "winning_angle": "distribution_seo"}
        assert angle_ranked_composite(d) == _composite_for_angle(0.6, 0.6, 0.3, 0.9, "distribution_seo")

    def test_preview_stamp_is_angle_weighted(self, monkeypatch):
        # The preview dict is always stamped with the angle-weighted composite so the selection grid
        # ranks by it (the grid short-circuits to adjusted_composite_score when present).
        from worker.tasks import _solution_to_preview_dict
        idea = self._idea("Seo", "distribution_seo")
        monkeypatch.setattr(sh.settings, "enable_feasibility_critic", False)
        stamped = _solution_to_preview_dict(idea)
        assert stamped["adjusted_composite_score"] == _composite_for_angle(0.6, 0.6, 0.3, 0.9, "distribution_seo")
