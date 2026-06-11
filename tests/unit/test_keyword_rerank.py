"""
Tests for the keyword-validation re-rank helpers (Phase 2 fixes).

Covers:
- blend_adjusted_composite: the 0.7/0.3 bounded blend (replaces unfloored multiplication)
- rerank_solutions_by_adjusted_score: novelty tiebreaker + stale-rank rewrite
- Regression: a demand-poor/novelty-rich solution survives the blend that the
  old multiplicative formula killed
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

    def test_tiebreaker_cascades_until_stable(self):
        """Three solutions within margin: highest competitive advantage ends first."""
        a = _make_score("A", composite=0.7, adjusted=0.70, competitive_advantage=0.3)
        b = _make_score("B", composite=0.7, adjusted=0.69, competitive_advantage=0.6)
        c = _make_score("C", composite=0.7, adjusted=0.68, competitive_advantage=0.9)
        ranked = rerank_solutions_by_adjusted_score(
            [a, b, c], validated_names={"A", "B", "C"}
        )
        assert [s.solution_name for s in ranked] == ["C", "B", "A"]
