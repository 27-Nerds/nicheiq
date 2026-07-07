"""Tests for the idea-score calibration tuning:

1. `_cap_feasibility_scores` — the deterministic critic-side feasibility caps
   (restricted/blocked data floors, build<=data+margin coupling, sentinel hole).
2. `feasibility_adjusted_composite` / `apply_feasibility_to_scores` — the downgrade-only
   ranking de-inversion (the critic's build_feasibility lowers the composite the ranker
   actually sorts on), never raising a composite.
3. Over-correction guard: a defect-free idea (public data, high build) is left unchanged.
"""

from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import _cap_feasibility_scores
from nicheiq.utils import score_helpers as sh
from nicheiq.utils.score_helpers import (
    apply_feasibility_to_scores,
    compute_solution_scores,
    feasibility_adjusted_composite,
)
from nicheiq.models.solution_selection import SolutionScores


# --- _cap_feasibility_scores (critic-side caps) -----------------------------

CAP, MARGIN = 0.45, 0.15


class TestCapFeasibilityScores:
    def test_restricted_caps_data_and_couples_build(self):
        # restricted -> data clamped to 0.45; build clamped to data+margin = 0.60
        assert _cap_feasibility_scores("restricted", 0.8, 0.9, restricted_cap=CAP, margin=MARGIN) == (0.45, 0.6)

    def test_blocked_floor(self):
        assert _cap_feasibility_scores("blocked", 0.9, 0.9, restricted_cap=CAP, margin=MARGIN) == (0.2, pytest.approx(0.35))

    def test_public_passes_through(self):
        assert _cap_feasibility_scores("public", 0.9, 0.85, restricted_cap=CAP, margin=MARGIN) == (0.9, 0.85)

    def test_build_coupled_to_data_even_when_public(self):
        # build can't exceed obtainable data by more than margin, regardless of access label
        assert _cap_feasibility_scores("public", 0.3, 0.9, restricted_cap=CAP, margin=MARGIN) == (0.3, pytest.approx(0.45))

    def test_sentinel_hole_build_scored_data_unscored(self):
        # data unscored (-1.0) but build high -> suspicious -> cap build at restricted_cap+margin
        assert _cap_feasibility_scores("public", -1.0, 0.9, restricted_cap=CAP, margin=MARGIN) == (-1.0, pytest.approx(0.6))

    def test_both_sentinel_passthrough(self):
        assert _cap_feasibility_scores("public", -1.0, -1.0, restricted_cap=CAP, margin=MARGIN) == (-1.0, -1.0)

    def test_already_low_build_untouched(self):
        assert _cap_feasibility_scores("public", 0.9, 0.5, restricted_cap=CAP, margin=MARGIN) == (0.9, 0.5)


# --- feasibility_adjusted_composite (downgrade-only, gated) ------------------

@pytest.fixture
def critic_on():
    """Feasibility critic is always on (enable_feasibility_critic removed 2026-07-06); kept as a
    marker fixture so the tests below read as the critic-on scenario without editing signatures."""
    return None


class TestFeasibilityAdjustedComposite:
    def test_downgrades_when_build_below_tf(self, critic_on):
        # drop = (0.90 - 0.30) / 4 present = 0.15 -> 0.65
        assert feasibility_adjusted_composite(0.80, 0.88, 0.90, 0.70, 0.85, 0.30) == 0.65

    def test_noop_when_build_ge_tf(self, critic_on):
        assert feasibility_adjusted_composite(0.80, 0.88, 0.90, 0.70, 0.85, 0.95) == 0.80

    def test_noop_on_sentinel_build(self, critic_on):
        assert feasibility_adjusted_composite(0.80, 0.88, 0.90, 0.70, 0.85, -1.0) == 0.80

    def test_noop_on_none_build(self, critic_on):
        assert feasibility_adjusted_composite(0.80, 0.88, 0.90, 0.70, 0.85, None) == 0.80

    def test_never_raises_composite(self, critic_on):
        # even with a low build, the result is <= the input composite
        out = feasibility_adjusted_composite(0.50, 0.6, 0.9, None, None, 0.1)
        assert out <= 0.50


# --- apply_feasibility_to_scores (the post-Task-4 rank de-inversion) ---------

def _score(name, mf, tf, ca, seo, composite, source="llm"):
    return SolutionScores(
        solution_name=name, market_fit_score=mf, technical_feasibility_score=tf,
        competitive_advantage_score=ca, seo_growth_potential_score=seo,
        composite_score=composite, rank=0, score_source=source,
    )


class TestApplyFeasibilityToScores:
    def test_reorders_when_low_build_buries_top_idea(self, critic_on):
        # 'Phantom' ranks #1 on the LLM composite but has a low build estimate (0.3);
        # 'Shippable' ranks #2 with honest high build. After adjustment the order flips.
        scores = [
            _score("Phantom", 0.88, 0.90, 0.70, 0.85, 0.85),
            _score("Shippable", 0.80, 0.85, 0.60, 0.78, 0.78),
        ]
        ideas = [
            SimpleNamespace(solution_name="Phantom", build_feasibility_score=0.30),
            SimpleNamespace(solution_name="Shippable", build_feasibility_score=0.85),
        ]
        out = apply_feasibility_to_scores(scores, ideas)
        assert out[0].solution_name == "Shippable"   # de-inverted
        assert out[0].rank == 1 and out[1].rank == 2
        phantom = next(s for s in out if s.solution_name == "Phantom")
        assert phantom.composite_score < 0.85         # downgraded

    def test_skips_non_llm_entries_no_double_subtract(self, critic_on):
        # a 'backfill' entry was already feasibility-adjusted at compute time -> must NOT
        # be adjusted again here.
        scores = [_score("BF", 0.88, 0.90, 0.70, 0.85, 0.70, source="backfill")]
        ideas = [SimpleNamespace(solution_name="BF", build_feasibility_score=0.30)]
        out = apply_feasibility_to_scores(scores, ideas)
        assert out[0].composite_score == 0.70   # untouched

# --- compute_solution_scores integration + over-correction guard ------------

class TestComputeWithFeasibility:
    def test_defect_free_idea_unchanged(self, critic_on):
        # A clean idea: public data, high build (the calculator archetype). Its composite
        # must NOT drop (build >= tf -> no adjustment). Over-correction guard.
        idea = SimpleNamespace(
            solution_name="Calc", market_fit_score=0.72, technical_feasibility_score=0.85,
            novelty_score=0.42, seo_scalability_score=0.78, build_feasibility_score=0.90,
        )
        [s] = compute_solution_scores([idea])
        # composite == the raw mean of the 4 (no feasibility drop), compared via the
        # helper's own computation to avoid float-order rounding-boundary flakiness.
        # seo 0.78 is provisional (no refined score) -> rank-capped at the 0.7 ceiling.
        assert s.composite_score == sh._composite_of_present(0.72, 0.85, 0.42, 0.7)

class TestFinalizeFeasibility:
    """The final re-assertion that fixes the leak where the filter/refiner LLMs overwrite
    the critic's capped feasibility on the shipped ideas."""

    def _run(self, crit, idea):
        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
        fake = SimpleNamespace(_critic_feasibility=crit)
        UnifiedSolutionCrew._finalize_feasibility(fake, [idea])
        return idea

    def test_restores_critic_value_over_filter_inflation(self, critic_on):
        # filter inflated build to 0.75; critic authority says 0.5 -> restored to 0.5
        idea = SimpleNamespace(
            solution_name="RecoveryROICalculator", data_feasibility_score=0.5,
            build_feasibility_score=0.75, data_access_model="freemium", data_acquisition_notes=None,
        )
        crit = {"recoveryroicalculator": {"data": 0.5, "build": 0.5, "access": "freemium", "notes": "x"}}
        out = self._run(crit, idea)
        assert out.build_feasibility_score == 0.5
        assert out.data_feasibility_score == 0.5

    def test_caps_unmatched_idea_invariant(self, critic_on):
        # no critic match -> still enforce build <= data + margin on the shipped value
        idea = SimpleNamespace(
            solution_name="Unmatched", data_feasibility_score=0.4, build_feasibility_score=0.6,
            data_access_model="freemium", data_acquisition_notes=None,
        )
        out = self._run({}, idea)
        assert out.build_feasibility_score == pytest.approx(0.55)  # 0.4 + 0.15

    # test_noop_when_critic_off deleted 2026-07-07: the feasibility critic is permanent
    # (enable_feasibility_critic removed), so the critic-off path no longer exists.


class TestComputeWithFeasibilityDowngrade:
    def test_data_fragile_idea_downgraded(self, critic_on):
        idea = SimpleNamespace(
            solution_name="Phantom", market_fit_score=0.88, technical_feasibility_score=0.90,
            novelty_score=0.70, seo_scalability_score=0.85, build_feasibility_score=0.30,
        )
        [s] = compute_solution_scores([idea])
        raw = round((0.88 + 0.90 + 0.70 + 0.85) / 4, 3)
        assert s.composite_score < raw   # build 0.30 < tf 0.90 -> downgraded
