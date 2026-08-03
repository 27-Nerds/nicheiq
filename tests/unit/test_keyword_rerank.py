"""
Tests for the keyword-validation re-rank helpers (Phase 2 fixes).

Covers:
- blend_adjusted_composite: the 0.7/0.3 bounded blend (replaces unfloored multiplication)
- rerank_solutions_by_adjusted_score: novelty tiebreaker + stale-rank rewrite
- Regression: a demand-poor/novelty-rich solution survives the blend that the
  old multiplicative formula killed
- Two-tier ranking (flow-weakness fix plan 2026-08, correction 1): graded-and-empty
  solutions (demand_unmeasured) rank below validated-with-keywords solutions
"""

from nicheiq.models.solution_selection import SolutionScores
from nicheiq.utils.score_helpers import (
    blend_adjusted_composite,
    rerank_solutions_by_adjusted_score,
)


def _make_score(
    name,
    composite,
    adjusted=None,
    competitive_advantage=0.5,
    rank=0,
    demand=None,
    demand_unmeasured=False,
):
    return SolutionScores(
        solution_name=name,
        market_fit_score=0.7,
        technical_feasibility_score=0.7,
        competitive_advantage_score=competitive_advantage,
        seo_growth_potential_score=0.6,
        composite_score=composite,
        rank=rank,
        keyword_demand_score=demand,
        adjusted_composite_score=adjusted,
        demand_unmeasured=demand_unmeasured,
    )


class TestBlendAdjustedComposite:
    def test_blend_formula(self):
        assert blend_adjusted_composite(0.8, 0.5) == 0.71  # 0.56 + 0.15

    def test_blend_bounds_demand_influence(self):
        """Zero demand reduces but never erases a strong composite."""
        assert blend_adjusted_composite(0.8, 0.0) == 0.56
        # Old multiplicative formula would have produced 0.0

    def test_full_demand(self):
        assert blend_adjusted_composite(0.8, 1.0) == 0.86


class TestRerankSolutions:
    def test_novelty_rich_demand_poor_survives_blend(self):
        """Regression for V3: under multiplication, NovelTool (0.85 × 0.30 = 0.255)
        lost to SafeTool (0.75 × 0.70 = 0.525) by a landslide. Under the blend
        they land within the tiebreaker margin and novelty decides."""
        novel = _make_score(
            "NovelTool",
            composite=0.85,
            adjusted=blend_adjusted_composite(0.85, 0.30),  # 0.685
            competitive_advantage=0.9,
            demand=0.30,
        )
        safe = _make_score(
            "SafeTool",
            composite=0.75,
            adjusted=blend_adjusted_composite(0.75, 0.70),  # 0.735
            competitive_advantage=0.4,
            demand=0.70,
        )
        ranked = rerank_solutions_by_adjusted_score(
            [novel, safe], validated_names={"NovelTool", "SafeTool"}
        )
        assert ranked[0].solution_name == "NovelTool"  # tiebreaker prefers novelty

    def test_clear_demand_gap_still_decides(self):
        """The tiebreaker only applies within the margin — a real demand gap wins."""
        novel = _make_score(
            "NovelTool", composite=0.70, adjusted=0.55, competitive_advantage=0.9
        )
        proven = _make_score(
            "ProvenTool", composite=0.80, adjusted=0.78, competitive_advantage=0.4
        )
        ranked = rerank_solutions_by_adjusted_score(
            [novel, proven], validated_names={"NovelTool", "ProvenTool"}
        )
        assert ranked[0].solution_name == "ProvenTool"

    def test_rank_fields_rewritten(self):
        """Stale Stage-5 ranks must be rewritten after the re-sort
        (pricing prompt context reads .rank)."""
        a = _make_score("A", composite=0.8, adjusted=0.60, rank=1)
        b = _make_score("B", composite=0.7, adjusted=0.75, rank=2)
        c = _make_score("C", composite=0.6, adjusted=None, rank=3)  # not validated
        ranked = rerank_solutions_by_adjusted_score(
            [a, b, c], validated_names={"A", "B"}
        )
        assert [s.solution_name for s in ranked] == ["B", "A"]
        assert b.rank == 1
        assert a.rank == 2
        assert c.rank == 3  # non-validated ranked after validated

    def test_only_validated_solutions_can_win(self):
        validated = _make_score("Validated", composite=0.5, adjusted=0.55)
        unvalidated = _make_score("Unvalidated", composite=0.95, adjusted=0.95)
        ranked = rerank_solutions_by_adjusted_score(
            [validated, unvalidated], validated_names={"Validated"}
        )
        assert ranked[0].solution_name == "Validated"
        assert len(ranked) == 1
        assert unvalidated.rank == 2

    def test_tiebreaker_leader_anchored(self):
        """Leader-anchored: within the margin-of-top cluster, highest competitive advantage wins
        rank 1; the rest keep adjusted-score order (NOT re-sorted by CA). Demand spreads (0.70/0.60/0.50,
        >= the P3a gate's 0.05 eps) so the novelty override fires under the default demand-gated tiebreak."""
        a = _make_score("A", composite=0.7, adjusted=0.70, competitive_advantage=0.3, demand=0.70)
        b = _make_score("B", composite=0.7, adjusted=0.69, competitive_advantage=0.6, demand=0.60)
        c = _make_score("C", composite=0.7, adjusted=0.68, competitive_advantage=0.9, demand=0.50)
        ranked = rerank_solutions_by_adjusted_score(
            [a, b, c], validated_names={"A", "B", "C"}
        )
        # C promoted (highest CA, within 0.05 of leader); A before B by adjusted score.
        assert [s.solution_name for s in ranked] == ["C", "A", "B"]

    def test_tiebreaker_outside_margin_cannot_win(self):
        """A solution >= margin below the leader can NEVER win rank 1, however high its CA."""
        # Top has the highest CA within the cluster, so it stays rank 1; Low is outside the margin.
        top = _make_score("Top", composite=0.9, adjusted=0.90, competitive_advantage=0.5)
        mid = _make_score("Mid", composite=0.86, adjusted=0.86, competitive_advantage=0.3)
        low = _make_score("Low", composite=0.82, adjusted=0.82, competitive_advantage=0.99)
        ranked = rerank_solutions_by_adjusted_score(
            [top, mid, low], validated_names={"Top", "Mid", "Low"}, tiebreak_margin=0.05
        )
        # Low (0.82) is 0.08 below Top (0.90) — outside the margin — so its 0.99 CA cannot win.
        assert ranked[0].solution_name == "Top"
        assert ranked[-1].solution_name == "Low"
        assert [s.rank for s in ranked] == [1, 2, 3]


class TestTwoTierDemandUnmeasured:
    """Correction 1: graded-and-empty solutions (demand_unmeasured=True, demand=None,
    adjusted=composite) rank strictly below validated-with-keywords solutions."""

    def test_unmeasured_ranks_below_measured_despite_higher_adjusted(self):
        """A graded-and-empty idea whose unblended composite EXCEEDS the measured
        leader's blended adjusted score still ranks below it (no fabricated demand,
        no free ride past the 0.3-demand toll)."""
        empty = _make_score(
            "GradedEmpty",
            composite=0.90,
            adjusted=0.90,  # flow sets adjusted = composite (blend skipped)
            demand=None,
            demand_unmeasured=True,
        )
        measured = _make_score(
            "Measured",
            composite=0.70,
            adjusted=blend_adjusted_composite(0.70, 0.50),  # 0.64 < 0.90
            demand=0.50,
        )
        ranked = rerank_solutions_by_adjusted_score(
            [empty, measured], validated_names={"GradedEmpty", "Measured"}
        )
        assert [s.solution_name for s in ranked] == ["Measured", "GradedEmpty"]
        assert measured.rank == 1
        assert empty.rank == 2

    def test_unmeasured_cannot_win_novelty_tiebreak(self):
        """The leader cluster is built from the measured tier only — an unmeasured
        idea within margin of the leader with sky-high novelty must not take rank 1."""
        measured_a = _make_score("A", composite=0.80, adjusted=0.80, competitive_advantage=0.4, demand=0.80)
        measured_b = _make_score("B", composite=0.78, adjusted=0.78, competitive_advantage=0.5, demand=0.60)
        empty = _make_score(
            "GradedEmpty", composite=0.79, adjusted=0.79,
            competitive_advantage=0.99, demand=None, demand_unmeasured=True,
        )
        ranked = rerank_solutions_by_adjusted_score(
            [measured_a, measured_b, empty], validated_names={"A", "B", "GradedEmpty"}
        )
        assert ranked[-1].solution_name == "GradedEmpty"
        assert ranked[0].solution_name in {"A", "B"}

    def test_within_tier_order_preserved(self):
        """Within the unmeasured tier, existing (adjusted=composite) order holds."""
        e1 = _make_score("E1", composite=0.70, adjusted=0.70, demand=None, demand_unmeasured=True)
        e2 = _make_score("E2", composite=0.60, adjusted=0.60, demand=None, demand_unmeasured=True)
        m = _make_score("M", composite=0.50, adjusted=0.55, demand=0.60)
        ranked = rerank_solutions_by_adjusted_score(
            [e2, e1, m], validated_names={"E1", "E2", "M"}
        )
        assert [s.solution_name for s in ranked] == ["M", "E1", "E2"]
        assert [s.rank for s in ranked] == [1, 2, 3]

    def test_all_unmeasured_degrades_to_adjusted_order(self):
        """When EVERY validated solution is graded-and-empty, the tier ordering
        degrades to plain adjusted(=composite) order — someone must still be rank 1."""
        e1 = _make_score("E1", composite=0.80, adjusted=0.80, demand=None, demand_unmeasured=True)
        e2 = _make_score("E2", composite=0.60, adjusted=0.60, demand=None, demand_unmeasured=True)
        ranked = rerank_solutions_by_adjusted_score(
            [e2, e1], validated_names={"E1", "E2"}
        )
        assert [s.solution_name for s in ranked] == ["E1", "E2"]
        assert [s.rank for s in ranked] == [1, 2]

    def test_unmeasured_still_ranks_above_non_validated(self):
        """Two-tier applies WITHIN the validated set; non-validated entries keep
        trailing everything validated."""
        empty = _make_score("GradedEmpty", composite=0.60, adjusted=0.60, demand=None, demand_unmeasured=True)
        unvalidated = _make_score("Unvalidated", composite=0.95, adjusted=0.95)
        ranked = rerank_solutions_by_adjusted_score(
            [empty, unvalidated], validated_names={"GradedEmpty"}
        )
        assert ranked[0].solution_name == "GradedEmpty"
        assert empty.rank == 1
        assert unvalidated.rank == 2
