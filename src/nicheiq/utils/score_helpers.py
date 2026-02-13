"""Utilities for computing SolutionScores from BaseSolutionIdea fields.

Used in interactive mode when Task 4 (LLM selection/scoring) is skipped,
and as a backfill for non-interactive mode when the LLM misses some solutions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicheiq.models.solution_idea import BaseSolutionIdea

from nicheiq.models.solution_selection import SolutionScores

logger = logging.getLogger(__name__)

# Field mapping from BaseSolutionIdea → SolutionScores:
#   market_fit_score           → market_fit_score           (direct)
#   technical_feasibility_score → technical_feasibility_score (direct)
#   novelty_score              → competitive_advantage_score (best proxy — novelty/differentiation drives competitive edge)
#   seo_scalability_score      → seo_growth_potential_score  (semantic match)


def _extract_score(idea: BaseSolutionIdea, field: str, default: float = 0.5) -> float:
    """Extract a score field, defaulting to `default` when None (preserves 0.0)."""
    raw = getattr(idea, field, None)
    return raw if raw is not None else default


def compute_solution_scores(solution_ideas: list[BaseSolutionIdea]) -> list[SolutionScores]:
    """Compute SolutionScores for ALL solutions from BaseSolutionIdea Task 3 fields.

    Used in interactive mode when Task 4 didn't run.
    Returns a ranked list sorted by composite_score descending.
    """
    scores: list[SolutionScores] = []
    for idea in solution_ideas:
        mf = _extract_score(idea, "market_fit_score")
        tf = _extract_score(idea, "technical_feasibility_score")
        # novelty_score is best available proxy for competitive_advantage_score
        ca = _extract_score(idea, "novelty_score")
        seo = _extract_score(idea, "seo_scalability_score")
        composite = round((mf + tf + ca + seo) / 4, 3)
        scores.append(
            SolutionScores(
                solution_name=idea.solution_name,
                market_fit_score=mf,
                technical_feasibility_score=tf,
                competitive_advantage_score=ca,
                seo_growth_potential_score=seo,
                composite_score=composite,
                rank=0,
            )
        )
    scores.sort(key=lambda s: s.composite_score, reverse=True)
    for i, s in enumerate(scores, 1):
        s.rank = i
    return scores


def backfill_solution_scores(
    existing_scores: list[SolutionScores] | None,
    solution_ideas: list[BaseSolutionIdea],
) -> list[SolutionScores]:
    """Add missing score entries for solutions not already scored.

    Used in non-interactive mode after Task 4 (which may miss some solutions).
    Re-ranks the entire list after backfill. Same field mapping as compute_solution_scores.
    """
    result = list(existing_scores) if existing_scores else []
    scored_names = {s.solution_name for s in result}

    for idea in solution_ideas:
        if idea.solution_name not in scored_names:
            mf = _extract_score(idea, "market_fit_score")
            tf = _extract_score(idea, "technical_feasibility_score")
            ca = _extract_score(idea, "novelty_score")
            seo = _extract_score(idea, "seo_scalability_score")
            composite = round((mf + tf + ca + seo) / 4, 3)
            result.append(
                SolutionScores(
                    solution_name=idea.solution_name,
                    market_fit_score=mf,
                    technical_feasibility_score=tf,
                    competitive_advantage_score=ca,
                    seo_growth_potential_score=seo,
                    composite_score=composite,
                    rank=0,
                )
            )
            logger.info(f"Backfilled scores for '{idea.solution_name}'")

    # Re-rank entire list by composite_score
    result.sort(key=lambda s: s.composite_score, reverse=True)
    for i, s in enumerate(result, 1):
        s.rank = i
    return result
