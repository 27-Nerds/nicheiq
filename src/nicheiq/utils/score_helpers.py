"""Utilities for computing SolutionScores from BaseSolutionIdea fields.

Used in interactive mode when Task 4 (LLM selection/scoring) is skipped,
and as a backfill for non-interactive mode when the LLM misses some solutions.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nicheiq.models.solution_idea import BaseSolutionIdea

from nicheiq.config.settings import settings
from nicheiq.models.solution_selection import SolutionScores

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


def score_band(score: float | None) -> str:
    """Map a 0-1 sub-score to a plain qualitative band for USER-FACING verdict text.

    Verdict prose must read in general terms ("good SEO", "weak market fit") and NEVER expose the
    internal decimal. Bands: strong >=0.80, good >=0.65, moderate >=0.50, limited >=0.35, else weak;
    None => "unrated".
    """
    if score is None:
        return "unrated"
    if score >= 0.80:
        return "strong"
    if score >= 0.65:
        return "good"
    if score >= 0.50:
        return "moderate"
    if score >= 0.35:
        return "limited"
    return "weak"


# Angle-aware ranking weights over the four composite dimensions (market_fit,
# technical_feasibility, novelty=competitive_advantage, seo). Each preset sums to 1.0 so the
# weighted mean stays on the same 0-1 scale as the equal-weight mean. distribution_seo keeps a
# SMALL non-zero novelty weight (it still rewards representation differentiation, just not as the
# primary lever). An idea is ranked by ITS OWN winning_angle — the run-level focus never enters here.
# These are starting weights; the Stage-2 A/B tunes them. angle=None => equal-weight (today).
# P3a: within a tiebreak cluster, a demand max-min below this carries no differentiating signal
# (demand is flat/saturated), so the novelty override is suppressed in favour of the composite leader.
_DEMAND_SPREAD_EPS = 0.05

# P3b: fold beachhead demand MAGNITUDE into the ratio-based demand score. log10(vol)/DIVISOR maps
# volume→[0,1] (100k/mo→1.0, 10k→0.8, 1k→0.6); RATIO_WEIGHT blends the existing clean-keywords ratio
# against that magnitude so a thin-but-clean beachhead can't score as high demand as a truly large one.
_DEMAND_VOL_LOG_DIVISOR = 5.0
_DEMAND_RATIO_WEIGHT = 0.5


def demand_with_beachhead_magnitude(
    ratio_demand: float,
    niche_relevant_volume: int | float | None,
    total_volume: int | float | None,
) -> float:
    """P3b: blend the ratio-based keyword_demand_score with the solution's log-scaled BEACHHEAD volume.

    The ratio score rewards 'most keywords are individually clean' (have volume, low competition) but
    ignores MAGNITUDE — a thin beachhead of clean-but-tiny keywords can score ~1.0. We blend in a
    log-scaled niche-relevant volume so demand tracks real magnitude; the log floors a genuinely-
    thin-but-real idea rather than zeroing it.

    Fallback semantics (bug-fixed 2026-07-02 after the cottage-food run): an EXPLICIT
    niche_relevant_volume == 0 means the keywords were graded and NOTHING passed — total_volume is then
    precisely the drifted category number. That is not merely "no magnitude credit": a ratio derived
    from irrelevant head terms/token collisions is no demand evidence, so the result is zero. ``None``
    remains the legacy/unmeasured state and may fall back to total volume.
    """
    if isinstance(niche_relevant_volume, (int, float)) and not isinstance(niche_relevant_volume, bool):
        if niche_relevant_volume <= 0:
            return 0.0  # graded-and-empty → no relevant demand evidence
        vol = niche_relevant_volume
    else:
        vol = total_volume or 0  # nrv never computed → total is the only signal available
    if not isinstance(vol, (int, float)) or vol <= 0:
        return round(ratio_demand, 4)
    magnitude = min(math.log10(vol + 1) / _DEMAND_VOL_LOG_DIVISOR, 1.0)
    return round(_DEMAND_RATIO_WEIGHT * ratio_demand + (1 - _DEMAND_RATIO_WEIGHT) * magnitude, 4)

_ANGLE_WEIGHTS: dict[str, dict[str, float]] = {
    "distribution_seo":       {"market_fit": 0.30, "technical_feasibility": 0.15, "novelty": 0.15, "seo": 0.40},
    "novel_differentiation":  {"market_fit": 0.30, "technical_feasibility": 0.20, "novelty": 0.40, "seo": 0.10},
    "vertical_workflow":      {"market_fit": 0.35, "technical_feasibility": 0.35, "novelty": 0.20, "seo": 0.10},
}


def _composite_for_angle(
    market_fit: float | None,
    technical_feasibility: float | None,
    novelty: float | None,
    seo: float | None,
    angle: str | None,
) -> float:
    """Angle-weighted mean over the present dimensions. When `angle` is None or unknown, returns the
    exact equal-weight `_composite_of_present` (byte-identical regression-lock). Otherwise weights by
    the angle preset and re-normalizes over the present dimensions' weights (a None dim drops out of
    BOTH numerator and denominator, mirroring _composite_of_present)."""
    w = _ANGLE_WEIGHTS.get(angle or "")
    if not w:
        return _composite_of_present(market_fit, technical_feasibility, novelty, seo)
    pairs = [
        (w["market_fit"], market_fit),
        (w["technical_feasibility"], technical_feasibility),
        (w["novelty"], novelty),
        (w["seo"], seo),
    ]
    present = [(wt, s) for wt, s in pairs if s is not None]
    denom = sum(wt for wt, _ in present)
    if denom <= 0:
        return _composite_of_present(market_fit, technical_feasibility, novelty, seo)
    return round(sum(wt * s for wt, s in present) / denom, 3)


def feasibility_adjusted_composite(
    composite_score: float,
    market_fit: float | None,
    technical_feasibility: float | None,
    competitive_advantage: float | None,
    seo: float | None,
    build_feasibility: float | None,
    angle: str | None = None,
) -> float:
    """Downgrade-only feasibility adjustment to a composite ranking score.

    The independent critic's ``build_feasibility`` can only LOWER the ranked technical
    feasibility (you can't ship what you can't build). We subtract the *marginal drop*
    that capping technical_feasibility at build_feasibility would cause inside the
    mean-of-present composite — so ONLY ideas where build < technical_feasibility move,
    and only downward. The LLM-assigned composite of unaffected ideas is preserved, and
    the stored technical_feasibility_score is never mutated (the verdict reads it raw).

    When ``angle`` is set, the composite is an angle-WEIGHTED mean (see _composite_for_angle),
    so the marginal drop must use the SAME weighting: w_tf·(tf−build)/Σw_present, not the plain
    1/n_present. ``angle=None`` keeps the exact equal-weight arithmetic (byte-identical no-op).

    No-op when build is unscored (sentinel -1.0 / None), or build >= technical_feasibility.
    """
    # Defensive: only adjust when both scores are real numbers (bool excluded). A non-numeric
    # build (e.g. unset/sentinel) or build < 0 means "not scored" -> no-op.
    if not isinstance(build_feasibility, (int, float)) or isinstance(build_feasibility, bool):
        return composite_score
    if not isinstance(technical_feasibility, (int, float)) or isinstance(technical_feasibility, bool):
        return composite_score
    if build_feasibility < 0 or build_feasibility >= technical_feasibility:
        return composite_score
    w = _ANGLE_WEIGHTS.get(angle or "")
    if w:
        # Weighted mean: capping tf->build lowers the composite by w_tf·(tf−build)/Σw_present.
        # Σw_present uses the SAME present-dimension weights as the base (None dims drop out).
        denom = sum(
            wt for wt, s in (
                (w["market_fit"], market_fit),
                (w["technical_feasibility"], technical_feasibility),
                (w["novelty"], competitive_advantage),
                (w["seo"], seo),
            ) if s is not None
        )
        if denom <= 0:
            return composite_score
        drop = w["technical_feasibility"] * (technical_feasibility - build_feasibility) / denom
    else:
        n_present = sum(
            1 for s in (market_fit, technical_feasibility, competitive_advantage, seo) if s is not None
        )
        if n_present == 0:
            return composite_score
        drop = (technical_feasibility - build_feasibility) / n_present
    return round(max(0.0, composite_score - drop), 3)


def ranking_seo(seo: float | None, idea) -> float | None:
    """The seo score as the RANKING layer consumes it: capped at
    ``settings.provisional_seo_rank_ceiling`` while still provisional.

    "Provisional" = not yet keyword-grounded, i.e. ``seo_scalability_score_refined`` is
    absent (Stage 12 sets it — and mutates the base score — for the selected winner only).
    A provisional SEO score is the one ranking dimension with no independent evidence
    behind it at selection time, yet distribution_seo weights it 0.40 — observed live
    putting a speculative bundle at rank 1 over a verified-data idea. The cap applies ONLY
    to the composite input; the stored/displayed ``seo_scalability_score`` is untouched.
    Ceiling 1.0 disables. ``idea`` may be a model or a dict.
    """
    if not isinstance(seo, (int, float)) or isinstance(seo, bool):
        return seo  # None / non-numeric: pass through untouched (mirrors _extract_optional_score)
    def _get(field):
        return idea.get(field) if isinstance(idea, dict) else getattr(idea, field, None)

    refined = _get("seo_scalability_score_refined")
    if refined is not None:
        return seo  # keyword-grounded — earned its value

    # Distribution routes are not exempt from competition: when the bounded pre-ranking probe
    # found authority/incumbent ownership, apply the same ceiling the stored-score realism pass
    # uses. Unlike the old runtime-only marker, this survives model copies/checkpoints.
    if _get("serp_competition") == "owned" and settings.serp_owned_seo_ceiling > 0:
        seo = min(seo, settings.serp_owned_seo_ceiling)

    ceiling = settings.provisional_seo_rank_ceiling
    if ceiling >= 1.0 or seo <= ceiling:
        return seo
    return ceiling


AUDIENCE_FIT_COVERAGE_MIN = 0.90
"""Minimum fraction of a pool that must carry an ``audience_fit`` verdict before the
adjacent-audience penalty may be applied. Below this, tagging was partial (fail-open LLM
judgment, a batch appended after the last tagging pass, legacy checkpoints) and penalising
only the tagged ideas would stealth-PROMOTE the untagged ones."""


def red_team_killed(idea) -> bool:
    """True when the adversarial red-team pass returned a 'killed' verdict for this idea.

    Reads defensively from models OR dicts (the worker/queue boundary hands the same idea
    across as a plain dict).
    """
    from ..models.solution_idea import effective_red_team_state

    verdict, _findings = effective_red_team_state(idea)
    return verdict == "killed"


def choose_auto_pick(ranked, ideas):
    """Highest-ranked candidate ELIGIBLE for the automatic #1 recommendation, plus an
    attributable note when the leader was skipped.

    ``ranked`` is any rank-ordered sequence carrying ``.solution_name`` (SolutionScores or
    ideas); ``ideas`` is the idea pool the red-team verdicts live on. Returns
    ``(pick, note)`` — ``note`` is None when nothing was skipped.

    An idea the red team KILLED stays visible, stays selectable, and keeps its rank in the
    list; only the automatic "this is our pick" designation is withheld, because the caps
    that used to hold a killed idea down were removed with the red-team parity coupling
    (2026-08-02) and `apply_red_team_downgrade` runs at FINAL REPORT ASSEMBLY, after
    selection — so nothing else stops a killed idea from becoming a stronger automatic #1
    than before it was killed. The note cites the kill caveat so the withholding is
    attributable, never a silent reorder.

    Degrades honestly: when EVERY candidate is killed the top-ranked one is still returned
    (the pipeline needs a subject) with a note saying no candidate survived adversarial
    review — a stated non-endorsement, not a silent pick.
    """
    items = list(ranked or [])
    if not items:
        return None, None
    killed: dict[str, str] = {}
    for idea in ideas or []:
        if not red_team_killed(idea):
            continue
        name = (idea.get("solution_name") if isinstance(idea, dict)
                else getattr(idea, "solution_name", None)) or ""
        caveats = (idea.get("red_team_caveats") if isinstance(idea, dict)
                   else getattr(idea, "red_team_caveats", None)) or []
        first = next((c.strip() for c in caveats if isinstance(c, str) and c.strip()), "")
        killed[name] = f"{first[:200].rstrip()}…" if len(first) > 200 else first
    if not killed:
        return items[0], None

    skipped = []
    for item in items:
        name = getattr(item, "solution_name", None) or ""
        if name in killed:
            skipped.append(name)
            continue
        if not skipped:
            return item, None
        cited = killed[skipped[0]]
        note = (
            f"**Automatic recommendation withheld from {skipped[0]}:** an adversarial "
            f"red-team review killed it"
            + (f" — {cited}" if cited else "")
            + f". It stays in the ranked list and remains selectable; {name} is the "
            "highest-ranked idea that survived the review."
        )
        return item, note

    cited = killed[skipped[0]]
    note = (
        "**No automatic recommendation:** an adversarial red-team review killed every "
        f"candidate, including the top-ranked {skipped[0]}"
        + (f" — {cited}" if cited else "")
        + ". The leader is shown for reference only; treat resolving the caveats as the "
        "next step, not the build."
    )
    return items[0], note


def audience_fit_coverage(ideas) -> float:
    """Fraction of ``ideas`` carrying a non-None ``audience_fit`` verdict (0.0 for an empty pool).

    Pure helper — reads defensively from models OR dicts. Gates
    :func:`apply_audience_fit_penalty`; see ``AUDIENCE_FIT_COVERAGE_MIN``.
    """
    items = list(ideas or [])
    if not items:
        return 0.0
    tagged = 0
    for it in items:
        fit = it.get("audience_fit") if isinstance(it, dict) else getattr(it, "audience_fit", None)
        if fit is not None:
            tagged += 1
    return tagged / len(items)


def apply_audience_fit_penalty(composite: float, idea, coverage: float | None) -> float:
    """Subtract ``settings.audience_fit_penalty`` from a COMPOSITE when this idea serves an
    ADJACENT audience (``audience_fit is False``).

    Composite-only and downgrade-only: the stored ``market_fit_score`` is never touched, so the
    displayed sub-scores stay the model's own judgment while the RANKING reflects that the idea
    doesn't serve the audience the user asked for. ``audience_fit is None`` (untagged /
    fail-open / no stated audience) is never penalised.

    ``coverage`` None or below ``AUDIENCE_FIT_COVERAGE_MIN`` → no-op (see that constant).
    """
    penalty = settings.audience_fit_penalty
    if penalty <= 0.0 or coverage is None or coverage < AUDIENCE_FIT_COVERAGE_MIN:
        return composite
    fit = idea.get("audience_fit") if isinstance(idea, dict) else getattr(idea, "audience_fit", None)
    if fit is not False:
        return composite
    return round(max(0.0, composite - penalty), 3)


def angle_ranked_composite(idea, audience_fit_coverage: float | None = None) -> float:
    """The angle-weighted, feasibility-adjusted composite for ONE idea, by its winning_angle.

    Used to STAMP ``adjusted_composite_score`` on preview dicts so the interactive selection grid
    ranks by the same angle-aware composite the report uses (the grid short-circuits to
    adjusted_composite_score when present). Reads sub-scores defensively from a model OR a dict.
    An idea whose winning_angle is None (classify fail-soft) falls back to an equal-weight 4-dim mean.

    ``audience_fit_coverage`` is this idea's POOL coverage (from :func:`audience_fit_coverage`) —
    a single-idea signature can't compute it. Default None = no adjacent-audience penalty, which
    preserves every call site that doesn't know its pool.
    """
    def _g(field):
        return idea.get(field) if isinstance(idea, dict) else getattr(idea, field, None)

    mf = _g("market_fit_score")
    tf = _g("technical_feasibility_score")
    mf = mf if mf is not None else 0.5  # match compute_solution_scores' required-field default
    tf = tf if tf is not None else 0.5
    ca = _g("novelty_score")
    seo = ranking_seo(_g("seo_scalability_score"), idea)
    bf = _g("build_feasibility_score")
    angle = _g("winning_angle")
    composite = feasibility_adjusted_composite(
        _composite_for_angle(mf, tf, ca, seo, angle), mf, tf, ca, seo, bf, angle
    )
    return apply_audience_fit_penalty(composite, idea, audience_fit_coverage)


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

    Angle policy (intentional): the 'llm' composite is whatever the selector emitted, NOT a
    weighted mean of the four sub-scores, so we DON'T angle-reweight it here — re-weighting a
    base built with unknown internal weighting would compound the approximation. The 'llm' path
    stays equal-weight; angle-aware ranking lives where the composite is built from sub-scores
    (compute/backfill + the preview-grid stamp). Mixed 'llm'+'backfill' lists therefore carry a
    small cross-source scale gap — accepted for v1, validated by the A/B.
    """
    if not all_scores:
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
    coverage = audience_fit_coverage(solution_ideas)
    for idea in solution_ideas:
        mf = _extract_score(idea, "market_fit_score")
        tf = _extract_score(idea, "technical_feasibility_score")
        # novelty_score is best available proxy for competitive_advantage_score
        ca = _extract_optional_score(idea, "novelty_score")
        seo = _extract_optional_score(idea, "seo_scalability_score")
        bf = _extract_optional_score(idea, "build_feasibility_score")
        # Rank by each idea's OWN winning_angle (None when angle eval is off => equal-weight no-op).
        angle = getattr(idea, "winning_angle", None)
        # Composite uses the provisional-capped seo; the STORED score stays raw (display parity).
        rseo = ranking_seo(seo, idea)
        composite = feasibility_adjusted_composite(
            _composite_for_angle(mf, tf, ca, rseo, angle), mf, tf, ca, rseo, bf, angle
        )
        # Adjacent-audience penalty: composite ONLY — the stored market_fit_score below stays raw.
        composite = apply_audience_fit_penalty(composite, idea, coverage)
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
    # Secondary key (normalized solution_name) so equal composites order deterministically —
    # completion-order tie-breaking made results depend on network latency (audit 2026-07-10).
    scores.sort(key=lambda s: (-s.composite_score, (s.solution_name or "").strip().lower()))
    for i, s in enumerate(scores, 1):
        s.rank = i
    return scores


def backfill_solution_scores(
    existing_scores: list[SolutionScores] | None,
    solution_ideas: list[BaseSolutionIdea],
) -> list[SolutionScores]:
    """Synchronize final idea sub-scores and add entries the selector missed.

    Used in non-interactive mode after Task 4 (which may miss some solutions).
    Task 4 runs before late evaluator caps, so its component scores can be stale even
    when an entry exists. The selector's strategic composite is preserved, while the
    four displayed component fields are synchronized from the finalized idea. Missing
    entries use the same mapping as :func:`compute_solution_scores`.
    """
    result = list(existing_scores) if existing_scores else []
    coverage = audience_fit_coverage(solution_ideas)
    scores_by_name: dict[str, list[SolutionScores]] = {}
    for score in result:
        scores_by_name.setdefault(score.solution_name, []).append(score)

    for idea in solution_ideas:
        mf = _extract_score(idea, "market_fit_score")
        tf = _extract_score(idea, "technical_feasibility_score")
        ca = _extract_optional_score(idea, "novelty_score")
        seo = _extract_optional_score(idea, "seo_scalability_score")
        existing_for_idea = scores_by_name.get(idea.solution_name, [])
        if existing_for_idea:
            for score in existing_for_idea:
                score.market_fit_score = mf
                score.technical_feasibility_score = tf
                score.competitive_advantage_score = ca
                score.seo_growth_potential_score = seo
        else:
            bf = _extract_optional_score(idea, "build_feasibility_score")
            angle = getattr(idea, "winning_angle", None)
            rseo = ranking_seo(seo, idea)
            composite = feasibility_adjusted_composite(
                _composite_for_angle(mf, tf, ca, rseo, angle), mf, tf, ca, rseo, bf, angle
            )
            # Same composite-only adjacent-audience penalty as compute_solution_scores — an idea
            # first scored down THIS branch would otherwise escape it entirely. Existing entries
            # above keep the selector's own composite (only sub-scores are synchronized).
            composite = apply_audience_fit_penalty(composite, idea, coverage)
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

    # Re-rank entire list by composite_score. Secondary key (normalized solution_name) so equal
    # composites order deterministically — completion-order tie-breaking made results depend on
    # network latency (audit 2026-07-10).
    result.sort(key=lambda s: (-s.composite_score, (s.solution_name or "").strip().lower()))
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


def build_pivot_rationale(
    new_score,
    orig_score,
    new_validation,
    orig_name: str,
    orig_validated: bool = True,
) -> str:
    """User-facing rationale for a keyword-validation winner change (run-quality fixes §3,
    2026-07-30). Lives next to `blend_adjusted_composite` because the honest attribution
    depends on its 0.7/0.3 weights.

    The old flow text unconditionally claimed the original "was overtaken due to weaker
    keyword demand evidence" — arithmetically false whenever the composite term drove the
    flip (the audited bookkeepers pivot was ~97% composite-driven), and impossible for a
    novelty-tiebreak flip where the new winner's adjusted score is LOWER. Three branches,
    never asserting a cause the numbers don't support:
      (a) new adjusted > original adjusted -> decompose 0.7*Δcomposite vs 0.3*Δdemand and
          name the dominant term;
      (b) new adjusted <= original adjusted -> the novelty/competitive-advantage tiebreak
          among near-tied leaders (see rerank_solutions_by_adjusted_score);
      (c) original not keyword-validated (or missing from all_scores) -> validated
          solutions take precedence; no fabricated 0.00 scores.
    """
    new_name = getattr(new_score, "solution_name", "") or "the new selection"
    new_adj = getattr(new_score, "adjusted_composite_score", None) or 0.0
    new_kd = getattr(new_score, "keyword_demand_score", None) or 0.0
    parts = [
        f"**Keyword-validation update:** **{new_name}** emerged as the top solution "
        f"after keyword validation with an adjusted composite score of {new_adj:.2f} "
        f"(keyword demand score: {new_kd:.2f})."
    ]

    if new_validation is not None:
        kw_names = [
            k.get("keyword", "")
            for k in (getattr(new_validation, "top_keywords", None) or [])[:3]
            if k.get("keyword")
        ]
        evidence = (
            f"Keyword research shows {new_validation.demand_signal} demand "
            f"with {new_validation.total_volume:,} monthly searches "
            # graded_keyword_count, not validated_count: this sentence claims the keywords
            # were validated, so it must count the graded set, never the expansion pool
            # (pre-2026-08 checkpoints stored the pool size in validated_count).
            f"across {new_validation.graded_keyword_count} validated keywords."
        )
        if kw_names:
            evidence += f" Top keywords: {', '.join(kw_names)}."
        parts.append(evidence)

    if orig_score is None or not orig_validated:
        # (c) — the dethroned winner never went through keyword validation; only
        # validated solutions can take rank 1 (rerank_solutions_by_adjusted_score).
        parts.append(
            f"The previous selection, {orig_name}, was not keyword-validated; "
            "validated solutions take precedence in the post-validation ranking."
        )
        return "\n\n".join(parts)

    orig_adj = getattr(orig_score, "adjusted_composite_score", None) or 0.0
    orig_kd = getattr(orig_score, "keyword_demand_score", None) or 0.0
    lead_in = (
        f"The previous selection, {orig_name}, scored an adjusted composite "
        f"of {orig_adj:.2f} (keyword demand: {orig_kd:.2f})"
    )
    if new_adj > orig_adj:
        # (a) — decompose the gap into the blend's two terms (0.7/0.3 mirrors
        # blend_adjusted_composite; recomputed here so the claim can't drift from it).
        comp_delta = 0.7 * (
            (getattr(new_score, "composite_score", None) or 0.0)
            - (getattr(orig_score, "composite_score", None) or 0.0)
        )
        demand_delta = 0.3 * (new_kd - orig_kd)
        if abs(comp_delta) >= abs(demand_delta):
            cause = (
                f"and was overtaken primarily on overall qualitative scoring "
                f"(composite contribution {comp_delta:+.2f} of the gap, keyword "
                f"demand {demand_delta:+.2f})."
            )
        else:
            cause = (
                f"and was overtaken primarily on keyword demand evidence "
                f"(demand contribution {demand_delta:+.2f} of the gap, composite "
                f"{comp_delta:+.2f})."
            )
        parts.append(f"{lead_in} {cause}")
    else:
        # (b) — the winner did NOT out-score the original on adjusted composite; it won
        # the leader-anchored novelty tiebreak. Saying "weaker demand" here would be false.
        parts.append(
            f"{lead_in} — within the near-tie margin, {new_name} won on the "
            "novelty/competitive-advantage tiebreak among near-tied leaders."
        )
    return "\n\n".join(parts)


def build_keyword_advisory_note(new_name: str, new_adj: float, orig_adj: float) -> str:
    """Advisory appended (never replacing) when keyword validation favors a different
    solution but the current winner was explicitly USER-selected — the pivot must not
    silently override a human decision (run-quality fixes §3)."""
    return (
        f"**Keyword-validation note:** keyword validation favors **{new_name}** "
        f"(adjusted composite {new_adj:.2f} vs {orig_adj:.2f}), but your selected "
        f"solution is kept. Review {new_name} as a runner-up."
    )


def rerank_solutions_by_adjusted_score(
    all_scores: list[SolutionScores],
    validated_names: set[str],
    tiebreak_margin: float = 0.05,
) -> list[SolutionScores]:
    """Re-rank after keyword validation; rewrites every entry's stale .rank.

    - Validated solutions are sorted by adjusted_composite_score and take
      ranks 1..N (only they can win — non-validated entries kept their raw
      composite as adjusted, which would be an unfair advantage).
    - Two-tier (flow-weakness fix plan 2026-08, correction 1): within the
      validated set, graded-and-empty solutions (``demand_unmeasured`` — their
      keywords were graded and NONE passed) rank strictly BELOW
      validated-with-keywords solutions regardless of adjusted score. Their
      adjusted equals the raw composite (no demand blend), which would
      otherwise be an unfair advantage over ideas that paid the 0.3-demand
      toll. Within each tier, adjusted-score order.
    - Novelty tiebreaker (mirrors the Task 4 prompt rule in code): adjacent
      solutions within `tiebreak_margin` adjusted score are ordered by higher
      competitive_advantage_score. Bubbles until stable (n ≤ 6).
    - Non-validated solutions get ranks N+1.. in their existing score order.

    Returns the ranked validated solutions (position 0 = winner).
    """
    validated = [s for s in all_scores if s.solution_name in validated_names]
    measured = sorted(
        [s for s in validated if not getattr(s, "demand_unmeasured", False)],
        key=lambda s: s.adjusted_composite_score or 0.0,
        reverse=True,
    )
    unmeasured = sorted(
        [s for s in validated if getattr(s, "demand_unmeasured", False)],
        key=lambda s: s.adjusted_composite_score or 0.0,
        reverse=True,
    )
    # The novelty tiebreak operates on the TOP tier only — an unmeasured
    # solution must never be promoted to rank 1 over a measured one via the
    # leader cluster. (All-unmeasured runs degrade to the plain tier order.)
    ranked = measured if measured else unmeasured

    # Leader-anchored novelty tiebreak (order-independent; mirrors the Task-4 prompt rule).
    # Among solutions within `tiebreak_margin` of the TOP adjusted score, the one with the
    # highest competitive_advantage_score wins rank 1; the rest keep adjusted-score order. A
    # solution >= margin below the leader can NEVER win (the old transitive adjacent-swap loop
    # could reorder within the cluster non-obviously). Strict `<` boundary: a gap of exactly
    # tiebreak_margin does not tie.
    if ranked:
        top_adj = ranked[0].adjusted_composite_score or 0.0
        cluster = [s for s in ranked if (top_adj - (s.adjusted_composite_score or 0.0)) < tiebreak_margin]
        # P3a (A/B-validated 2026-07-01, always on): the novelty override breaks DEMAND-driven near-ties,
        # but keyword_demand_score saturates (~0.94 constant) in practice, so the cluster is really a
        # composite-proximity artifact and overriding the composite leader on novelty systematically
        # promotes a weaker idea. Fire the override ONLY if within-cluster demand actually spreads
        # (>= _DEMAND_SPREAD_EPS); on flat/saturated demand keep the composite leader.
        fire_override = True
        if len(cluster) > 1:
            demands = [s.keyword_demand_score for s in cluster if s.keyword_demand_score is not None]
            if len(demands) < 2 or (max(demands) - min(demands)) < _DEMAND_SPREAD_EPS:
                fire_override = False
                logger.info(
                    f"Demand-gated tiebreak: demand spread <{_DEMAND_SPREAD_EPS} across {len(cluster)} "
                    f"clustered solution(s) — keeping composite leader '{ranked[0].solution_name}' "
                    f"(novelty override suppressed)"
                )
        if fire_override:
            winner = max(cluster, key=lambda s: s.competitive_advantage_score or 0.0)
            if winner is not ranked[0]:
                logger.info(
                    f"Novelty tiebreaker: '{winner.solution_name}' over '{ranked[0].solution_name}' "
                    f"(adjusted within {tiebreak_margin} of leader, higher competitive advantage)"
                )
                ranked.remove(winner)
                ranked.insert(0, winner)

    if measured:
        ranked = ranked + unmeasured  # unmeasured tier trails the measured tier

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
