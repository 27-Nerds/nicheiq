"""Utilities for computing SolutionScores from BaseSolutionIdea fields.

Used in interactive mode when Task 4 (LLM selection/scoring) is skipped,
and as a backfill for non-interactive mode when the LLM misses some solutions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicheiq.models.solution_idea import BaseSolutionIdea

from nicheiq.config.settings import settings
from nicheiq.models.solution_selection import SolutionScores

logger = logging.getLogger(__name__)

# Field mapping from BaseSolutionIdea → SolutionScores:
#   market_fit_score           → market_fit_score           (direct)
#   technical_feasibility_score → technical_feasibility_score (direct)
#   novelty_score              → competitive_advantage_score (best proxy — novelty/differentiation drives competitive edge)
#   seo_scalability_score      → seo_growth_potential_score  (semantic match)


def _extract_score(idea: BaseSolutionIdea, field: str, default: float = 0.5) -> float:
    """Extract a required score field, defaulting when None (preserves 0.0).

    Only used for market_fit/technical_feasibility, which crew validators
    enforce as present — the default is a never-in-practice safety net.
    """
    raw = getattr(idea, field, None)
    return raw if raw is not None else default


def _extract_optional_score(idea: BaseSolutionIdea, field: str) -> float | None:
    """Extract an optional score field; missing stays None (never fabricated).

    Fabricating a neutral 0.5 masked missing novelty/SEO data as a measured
    middle-of-the-road score with no provenance trail.
    """
    return getattr(idea, field, None)


def _composite_of_present(*scores: float | None) -> float:
    """Mean over the scores that are actually present (None excluded)."""
    present = [s for s in scores if s is not None]
    return round(sum(present) / len(present), 3) if present else 0.0


def feasibility_adjusted_composite(
    composite_score: float,
    market_fit: float | None,
    technical_feasibility: float | None,
    competitive_advantage: float | None,
    seo: float | None,
    build_feasibility: float | None,
) -> float:
    """Downgrade-only feasibility adjustment to a composite ranking score.

    The independent critic's ``build_feasibility`` can only LOWER the ranked technical
    feasibility (you can't ship what you can't build). We subtract the *marginal drop*
    that capping technical_feasibility at build_feasibility would cause inside the
    mean-of-present composite — so ONLY ideas where build < technical_feasibility move,
    and only downward. The LLM-assigned composite of unaffected ideas is preserved, and
    the stored technical_feasibility_score is never mutated (the verdict reads it raw).

    No-op when the feasibility critic is off, build is unscored (sentinel -1.0 / None),
    or build >= technical_feasibility.
    """
    if not settings.enable_feasibility_critic:
        return composite_score
    # Defensive: only adjust when both scores are real numbers (bool excluded). A non-numeric
    # build (e.g. unset/sentinel) or build < 0 means "not scored" -> no-op.
    if not isinstance(build_feasibility, (int, float)) or isinstance(build_feasibility, bool):
        return composite_score
    if not isinstance(technical_feasibility, (int, float)) or isinstance(technical_feasibility, bool):
        return composite_score
    if build_feasibility < 0 or build_feasibility >= technical_feasibility:
        return composite_score
    n_present = sum(
        1 for s in (market_fit, technical_feasibility, competitive_advantage, seo) if s is not None
    )
    if n_present == 0:
        return composite_score
    drop = (technical_feasibility - build_feasibility) / n_present
    return round(max(0.0, composite_score - drop), 3)


def apply_feasibility_to_scores(
    all_scores: list[SolutionScores] | None,
    solution_ideas: list[BaseSolutionIdea] | None,
) -> list[SolutionScores] | None:
    """Re-apply the downgrade-only feasibility adjustment to the Task-4 SELECTOR LLM's
    composites and re-rank.

    The selector LLM emits ``composite_score`` directly (``score_source='llm'``) and it
    never sees the critic's ``build_feasibility`` — so without this pass the ranking can't
    reflect a low build estimate (the cause of the ranking inversion). ONLY 'llm'-sourced
    entries are adjusted; 'backfill'/'interactive' composites were already adjusted at
    compute time (re-applying would double-subtract). No-op when the critic is off.
    """
    if not settings.enable_feasibility_critic or not all_scores:
        return all_scores
    bf_by_name = {
        idea.solution_name: getattr(idea, "build_feasibility_score", None)
        for idea in (solution_ideas or [])
    }
    changed = False
    for s in all_scores:
        if getattr(s, "score_source", None) != "llm":
            continue
        before = s.composite_score
        s.composite_score = feasibility_adjusted_composite(
            before,
            s.market_fit_score,
            s.technical_feasibility_score,
            s.competitive_advantage_score,
            s.seo_growth_potential_score,
            bf_by_name.get(s.solution_name),
        )
        if s.composite_score != before:
            changed = True
            logger.info(
                f"[FEASIBILITY] composite '{s.solution_name}' {before:.3f} -> "
                f"{s.composite_score:.3f} (build_feasibility={bf_by_name.get(s.solution_name)})"
            )
    if changed:
        all_scores.sort(key=lambda s: s.composite_score, reverse=True)
        for i, s in enumerate(all_scores, 1):
            s.rank = i
    return all_scores


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
        ca = _extract_optional_score(idea, "novelty_score")
        seo = _extract_optional_score(idea, "seo_scalability_score")
        bf = _extract_optional_score(idea, "build_feasibility_score")
        composite = feasibility_adjusted_composite(
            _composite_of_present(mf, tf, ca, seo), mf, tf, ca, seo, bf
        )
        scores.append(
            SolutionScores(
                solution_name=idea.solution_name,
                market_fit_score=mf,
                technical_feasibility_score=tf,
                competitive_advantage_score=ca,
                seo_growth_potential_score=seo,
                composite_score=composite,
                rank=0,
                score_source='interactive',
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
            ca = _extract_optional_score(idea, "novelty_score")
            seo = _extract_optional_score(idea, "seo_scalability_score")
            bf = _extract_optional_score(idea, "build_feasibility_score")
            composite = feasibility_adjusted_composite(
                _composite_of_present(mf, tf, ca, seo), mf, tf, ca, seo, bf
            )
            result.append(
                SolutionScores(
                    solution_name=idea.solution_name,
                    market_fit_score=mf,
                    technical_feasibility_score=tf,
                    competitive_advantage_score=ca,
                    seo_growth_potential_score=seo,
                    composite_score=composite,
                    rank=0,
                    score_source='backfill',
                )
            )
            logger.info(f"Backfilled scores for '{idea.solution_name}'")

    # Re-rank entire list by composite_score
    result.sort(key=lambda s: s.composite_score, reverse=True)
    for i, s in enumerate(result, 1):
        s.rank = i
    return result


def blend_adjusted_composite(composite_score: float, keyword_demand_score: float) -> float:
    """Adjusted composite after keyword validation: 0.7 × composite + 0.3 × demand.

    A bounded blend, NOT multiplication: an unfloored multiplier let demand
    crush the qualitative composite (0.8 × 0.3 = 0.24), reliably handing the
    win to whatever already has search volume. The blend keeps the composite
    (which carries novelty at 25% weight) dominant while demand evidence still
    moves the ranking.
    """
    return round(0.7 * composite_score + 0.3 * keyword_demand_score, 4)


def rerank_solutions_by_adjusted_score(
    all_scores: list[SolutionScores],
    validated_names: set[str],
    tiebreak_margin: float = 0.05,
) -> list[SolutionScores]:
    """Re-rank after keyword validation; rewrites every entry's stale .rank.

    - Validated solutions are sorted by adjusted_composite_score and take
      ranks 1..N (only they can win — non-validated entries kept their raw
      composite as adjusted, which would be an unfair advantage).
    - Novelty tiebreaker (mirrors the Task 4 prompt rule in code): adjacent
      solutions within `tiebreak_margin` adjusted score are ordered by higher
      competitive_advantage_score. Bubbles until stable (n ≤ 6).
    - Non-validated solutions get ranks N+1.. in their existing score order.

    Returns the ranked validated solutions (position 0 = winner).
    """
    ranked = sorted(
        [s for s in all_scores if s.solution_name in validated_names],
        key=lambda s: s.adjusted_composite_score or 0.0,
        reverse=True,
    )

    changed = True
    while changed:
        changed = False
        for i in range(len(ranked) - 1):
            a, b = ranked[i], ranked[i + 1]
            a_adj = a.adjusted_composite_score or 0.0
            b_adj = b.adjusted_composite_score or 0.0
            if (
                abs(a_adj - b_adj) < tiebreak_margin
                and (b.competitive_advantage_score or 0.0) > (a.competitive_advantage_score or 0.0)
            ):
                ranked[i], ranked[i + 1] = b, a
                changed = True
                logger.info(
                    f"Novelty tiebreaker: '{b.solution_name}' over '{a.solution_name}' "
                    f"(adjusted within {tiebreak_margin}, higher competitive advantage)"
                )

    for i, score in enumerate(ranked, start=1):
        score.rank = i
    non_validated = sorted(
        [s for s in all_scores if s.solution_name not in validated_names],
        key=lambda s: s.adjusted_composite_score or s.composite_score,
        reverse=True,
    )
    for i, score in enumerate(non_validated, start=len(ranked) + 1):
        score.rank = i

    return ranked
