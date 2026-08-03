"""
Seed-state builders for catalog-initiated research.

Turn authoritative catalog records (serialized into the Redis payload by the
backend) into the minimal `ResearchState` artifacts the pipeline needs to run
with stages skipped:

- `build_pain_seed_state`  — niche_context + merged pain_point_analysis for
  "pain research" / "remix" (skip stages 1-4, run stage 5).
- `build_idea_seed_state`  — niche_context + idea_generation + solution_selection
  + minimal pain_point_analysis for "deep research on an idea" (skip 1-5, run 5.5-14).

Pure functions (no flow or worker dependencies) so they can be unit-tested directly.
Catalog-sourced free text is sanitized (injection-pattern stripping) before it
reaches the LLM, since seeding pre-built objects bypasses the Stage-2 fencing the
normal pipeline applies.
"""

from __future__ import annotations

from typing import Any

from ..crews.pain_point_crew import _sanitize_social_content
from ..models.keyword_data import OpportunityLevel
from ..models.pain_point import PainPoint, PainPointAnalysisResult
from ..models.research_state import NicheContext
from ..models.solution_idea import BaseSolutionIdea, IdeaGenerationResult
from ..models.solution_selection import SolutionSelection
from ..utils.score_helpers import compute_solution_scores

MAX_REMIX_PAINS = 5


def _clean(text: Any) -> str:
    """Sanitize a single catalog string for LLM consumption (None -> '')."""
    if not text or not isinstance(text, str):
        return ""
    return _sanitize_social_content(text).strip()


def _clean_list(values: Any) -> list[str]:
    """Sanitize a list of catalog strings, dropping empties."""
    if not isinstance(values, list):
        return []
    out = [_clean(v) for v in values if isinstance(v, str)]
    return [v for v in out if v]


def _clamp01(value: Any, default: float) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _clamp01_opt(value: Any) -> float | None:
    """Like _clamp01 but None when the catalog carries no value (no fake default)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, f))


def sanitize_label(text: Any) -> str:
    """Public seam for callers (worker tasks) needing the same catalog-text sanitization."""
    return _clean(text)


def _opportunity(value: Any) -> OpportunityLevel:
    raw = (value or "").strip().lower() if isinstance(value, str) else ""
    if raw in ("high", "medium", "low"):
        return OpportunityLevel(raw)
    return OpportunityLevel.MEDIUM


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _pain_from_dict(pain: dict) -> PainPoint:
    title = _clean(pain.get("title")) or "Unspecified pain point"
    description = _clean(pain.get("description")) or title
    quotes = _clean_list(pain.get("representative_quotes"))
    if not quotes:
        # representative_quotes is a REQUIRED, non-empty field on PainPoint; catalog
        # rows may carry null quotes. Derive a placeholder so validation passes.
        quotes = [f"Users report: {title}"]
    return PainPoint(
        title=title,
        parent_theme_id=pain.get("parent_theme_id"),
        description=description,
        mention_count=int(pain.get("mention_count") or 0),
        severity_score=_clamp01(pain.get("severity_score"), 0.5),
        commercial_intent=_clamp01(pain.get("commercial_intent"), 0.5),
        opportunity_level=_opportunity(pain.get("opportunity_level")),
        representative_quotes=quotes,
        source_platforms=_clean_list(pain.get("source_platforms")) or None,
        categories=_clean_list(pain.get("categories")) or None,
        affected_segments=_clean_list(pain.get("affected_segments")) or None,
        solution_approach=_clean(pain.get("solution_approach")) or None,
    )


def build_pain_seed_state(
    pain_dicts: list[dict], niche: str
) -> tuple[NicheContext, PainPointAnalysisResult]:
    """Build (niche_context, pain_point_analysis) seeded from 1-5 catalog pains.

    For remix (>1 pain, possibly cross-niche) the niche_context is synthesized to
    span the combined set so downstream SEO/market-sizing stages have coherent context.
    """
    if not pain_dicts:
        raise ValueError("build_pain_seed_state requires at least one pain")
    # The label is built by the backend from raw catalog titles — sanitize at the
    # seam (the DB/display label on the backend side stays raw).
    niche = _clean(niche) or "Catalog research"
    pains = [_pain_from_dict(p) for p in pain_dicts[:MAX_REMIX_PAINS]]

    segments = _dedupe([s for p in pains for s in (p.affected_segments or [])]) or ["General market"]
    categories = _dedupe([c for p in pains for c in (p.categories or [])])
    source_niches = _dedupe(
        [_clean(p.get("source_niche")) for p in pain_dicts if _clean(p.get("source_niche"))]
    )
    titles = [p.title for p in pains]

    is_remix = len(pains) > 1
    if is_remix:
        niche_description = (
            f"A cross-niche opportunity spanning {', '.join(source_niches) or 'multiple markets'}, "
            f"unified by these pain points: {'; '.join(titles)}."
        )
        industry_boundaries = (
            "In scope: products/services that solve the listed pain points across the combined "
            f"markets ({', '.join(source_niches) or 'the selected niches'}). "
            "Out of scope: unrelated problems outside these pain points."
        )
        analysis_summary = (
            f"Remix of {len(pains)} pain points across {len(source_niches) or 1} niche(s), "
            "seeded from the NicheIQ catalog for cross-niche solution ideation."
        )
    else:
        niche_description = (
            f"{source_niches[0] if source_niches else niche}: solutions addressing the pain point "
            f"\"{titles[0]}\"."
        )
        industry_boundaries = (
            f"In scope: products/services that solve \"{titles[0]}\". Out of scope: unrelated problems."
        )
        analysis_summary = (
            f"Focused research seeded from the catalog pain point \"{titles[0]}\"."
        )

    niche_context = NicheContext(
        niche_input=niche,
        niche_description=niche_description,
        market_segments=segments,
        industry_boundaries=industry_boundaries,
    )
    pain_point_analysis = PainPointAnalysisResult(
        niche=niche,
        pain_points=pains,
        total_mentions=sum(p.mention_count for p in pains),
        top_categories=categories or ["General"],
        analysis_summary=analysis_summary,
    )
    return niche_context, pain_point_analysis


def _placeholder_idea(index: int) -> BaseSolutionIdea:
    """Minimal valid idea to satisfy IdeaGenerationResult's min_length=3 / field validators.

    Never selected and excluded from `all_solution_scores`, so it does not surface
    in the report; it exists only so the schema's "at least 3 ideas" constraint holds.
    """
    name = f"Alternative direction {index}"
    return BaseSolutionIdea(
        solution_name=name,
        description="Internal placeholder retained only to satisfy pipeline schema constraints; not part of the deep-research output.",
        value_proposition="Placeholder alternative not pursued in this run.",
        pain_points_addressed=["placeholder"],
        core_features=["placeholder"],
        target_personas=["placeholder"],
        market_fit_score=0.1,
        technical_feasibility_score=0.1,
    )


def build_idea_seed_state(
    idea: dict, niche: str
) -> tuple[NicheContext, IdeaGenerationResult, SolutionSelection, PainPointAnalysisResult]:
    """Build the synthetic state for deep research seeded from a single catalog idea."""
    # The label is built by the backend from the raw catalog headline — sanitize
    # at the seam (the DB/display label on the backend side stays raw).
    niche = _clean(niche) or "Catalog research"
    solution_name = _clean(idea.get("solution_name"))
    if not solution_name:
        raise ValueError("build_idea_seed_state requires solution_name")

    value_proposition = _clean(idea.get("value_proposition"))
    description = _clean(idea.get("description")) or value_proposition or solution_name
    if not value_proposition:
        value_proposition = description[:200] or f"A solution: {solution_name}"

    addressed = _clean_list(idea.get("addressed_pain_titles"))
    personas = _clean_list(idea.get("target_personas")) or ["Target users"]
    features = _clean_list(idea.get("core_features")) or ["Core feature"]

    real_idea = BaseSolutionIdea(
        solution_name=solution_name,
        headline=_clean(idea.get("headline")) or None,
        description=description,
        value_proposition=value_proposition,
        pain_points_addressed=addressed or [f"Core need addressed by {solution_name}"],
        core_features=features,
        target_personas=personas,
        technical_approach=_clean(idea.get("technical_approach")) or None,
        differentiation_factors=_clean_list(idea.get("differentiation_factors")) or None,
        pricing_strategy=_clean(idea.get("pricing_strategy")) or None,
        market_fit_score=_clamp01(idea.get("market_fit_score"), 0.6),
        technical_feasibility_score=_clamp01(idea.get("technical_feasibility_score"), 0.6),
        # Forward the catalog's real scores so compute_solution_scores ranks from
        # them instead of padding the report with its 0.5 defaults.
        seo_scalability_score=_clamp01_opt(idea.get("seo_scalability_score")),
        novelty_score=_clamp01_opt(idea.get("novelty_score")),
        estimated_cac_organic=_clean(idea.get("estimated_cac_organic")) or None,
        project_type=idea.get("project_type") or None,
        programmatic_seo_opportunity=_clean(idea.get("programmatic_seo_opportunity")) or None,
        organic_discovery_queries=_clean_list(idea.get("organic_discovery_queries")) or None,
    )

    idea_generation = IdeaGenerationResult(
        solution_ideas=[real_idea, _placeholder_idea(1), _placeholder_idea(2)],
        recommended_solution=solution_name,
    )

    # Score only the real idea so placeholders never appear in rankings / the report.
    real_scores = compute_solution_scores([real_idea])

    rationale = (
        f"Selected \"{solution_name}\" from the NicheIQ catalog for deep research. "
        f"{value_proposition} {description[:240]}"
    ).strip()
    if len(rationale) < 100:
        rationale = (
            rationale
            + " This solution was chosen to validate market demand, pricing, SEO opportunity, "
            "and competitive positioning before building."
        )

    solution_selection = SolutionSelection(
        selected_solution_name=solution_name,
        selection_rationale=rationale,
        recommended_focus=f"Build and launch {solution_name} for the identified market.",
        all_solution_scores=real_scores,
        runner_up_solutions=[],
    )

    pain_titles = addressed[:MAX_REMIX_PAINS] or [f"Core need addressed by {solution_name}"]
    # Synthetic pains carry NO quotes and a neutral opportunity level: there is no
    # social evidence behind them, and fabricated "quotes" would render in the
    # report as real user voice.
    pains = [
        PainPoint(
            title=t,
            description=t,
            mention_count=0,
            severity_score=0.6,
            commercial_intent=0.6,
            opportunity_level=OpportunityLevel.MEDIUM,
            representative_quotes=[],
            affected_segments=personas or None,
        )
        for t in pain_titles
    ]
    pain_point_analysis = PainPointAnalysisResult(
        niche=niche,
        pain_points=pains,
        total_mentions=0,
        top_categories=["General"],
        analysis_summary=f"Pains addressed by the catalog idea \"{solution_name}\".",
    )

    niche_context = NicheContext(
        niche_input=niche,
        niche_description=(
            f"{_clean(idea.get('source_niche')) or niche}: market for \"{solution_name}\" — {value_proposition}"
        ),
        market_segments=personas,
        industry_boundaries=(
            f"In scope: the market served by \"{solution_name}\". Out of scope: unrelated products."
        ),
    )

    return niche_context, idea_generation, solution_selection, pain_point_analysis
