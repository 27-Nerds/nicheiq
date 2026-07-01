"""P3a — demand-gated novelty tiebreak, always on (A/B-validated 2026-07-01, flag removed).

The novelty override promotes the highest-competitive-advantage idea within tiebreak_margin of the top
adjusted score. Under SATURATED demand it fires on a composite-proximity artifact and picks a weaker
idea; the gate suppresses it there but is a no-op when demand is a real signal.
"""

from nicheiq.models.solution_selection import SolutionScores
from nicheiq.utils.score_helpers import rerank_solutions_by_adjusted_score


def _s(name, composite, novelty, demand):
    return SolutionScores(
        solution_name=name,
        market_fit_score=composite, technical_feasibility_score=composite,
        competitive_advantage_score=novelty, seo_growth_potential_score=composite,
        composite_score=composite, rank=0,
        keyword_demand_score=demand,
        adjusted_composite_score=round(0.7 * composite + 0.3 * demand, 4),
    )


def _winner(scores):
    names = {s.solution_name for s in scores}
    return rerank_solutions_by_adjusted_score(list(scores), names)[0].solution_name


def test_flat_demand_keeps_composite_leader():
    # A (composite 0.65) vs noveler B (0.63, novelty 0.95), both within margin, SATURATED demand →
    # spread 0 across the cluster → suppress novelty override → composite leader A wins.
    assert _winner([_s("A", 0.65, 0.40, 0.94), _s("B", 0.63, 0.95, 0.94)]) == "A"


def test_varied_demand_fires_override():
    # same near-tie but demand spreads (0.95 vs 0.85, >= eps) → override fires → noveler B wins.
    assert _winner([_s("A", 0.65, 0.40, 0.95), _s("B", 0.63, 0.95, 0.85)]) == "B"


def test_no_cluster_no_override():
    # B far below A (gap > margin) → not in cluster → composite leader A wins.
    assert _winner([_s("A", 0.80, 0.40, 0.94), _s("B", 0.50, 0.99, 0.94)]) == "A"
