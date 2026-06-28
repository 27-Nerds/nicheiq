"""Downgrade-only SEO-realism caps for ``seo_scalability_score``.

Mirrors the feasibility-cap pattern (``_cap_feasibility_scores``). The LLM's SEO score tracks
raw indexable-page *potential* without discounting account-gated data, thin/combinatorially
sparse corpora, or hand-seeded (non-programmatic) content — so true aggregators score 0.9 when
~0.6 is realistic. These caps enforce the ``seo_scalability_score`` field's OWN documented intent
("0.8-1.0 REQUIRES a real, enumerable content corpus ... cap at 0.5 [for restricted/hand-seeded]")
in code.

Every rule is ``min()``-based: it can only LOWER the score, is order-independent, and is
idempotent (re-applying on an already-capped score is a no-op). Gating on the master flag is the
caller's responsibility (mirrors ``enable_feasibility_critic`` guards).
"""
from __future__ import annotations

# Rule C heuristic on the free-text content_generation_model (no structured enum exists).
_HANDSEED_HINTS = (
    "manual", "hand", "blog", "content marketing", "user submission",
    "user-generated", "crowdsourc", "community",
)
_PROGRAMMATIC_HINTS = ("aggregat", "programmatic")


def cap_seo_realism_score(
    seo: float | None,
    *,
    project_type: str | None,
    data_access_model: str | None,
    content_generation_model: str | None,
    estimated_indexable_pages: int | None,
    require_saas_for_gating: bool,
    gated_saas_ceiling: float,
    thin_pages_threshold: int,
    thin_pages_ceiling: float,
    high_score_min_pages: int,
    moderate_pages_ceiling: float,
    handseed_ceiling: float | None,
) -> tuple[float | None, str | None]:
    """Return ``(capped_seo, note | None)``.

    SEO scalability = realistic count of distinct, indexable, non-thin pages. These caps key ONLY
    on that — page count, page quality, and whether the pages are publicly indexable. They do NOT
    penalize data *sourcing* (official vs. unofficial/scraping): that affects feasibility/durability,
    not whether a page ranks, and is already scored by the feasibility critic. Folding it in here
    would double-count and make the SEO score pessimistic for a non-SEO reason.

    Rules (each an independent ceiling; final = min of all applicable):
      A. Account-gated SaaS — output pages sit behind a login and can't be indexed. No real
         ``account_gated`` flag exists, so the proxy is ``data_access_model == 'restricted'`` AND
         (``project_type == 'saas'`` unless ``require_saas_for_gating`` is False) -> <= ``gated_saas_ceiling``.
      B. Thin page counts — the core SEO signal. ONLY when ``estimated_indexable_pages`` is known
         (post-Stage-12; a no-op pre-Stage-12, which keeps the cap idempotent across checkpoints):
         ``< thin_pages_threshold`` -> <= ``thin_pages_ceiling``;
         ``< high_score_min_pages`` -> <= ``moderate_pages_ceiling`` (gates the 0.8+ band).
      C. Hand-seeded / non-programmatic content — substring heuristic on
         ``content_generation_model`` (hand/manual/blog/crowdsourced but NOT aggregat/programmatic)
         -> <= ``handseed_ceiling``. Disabled when ``handseed_ceiling is None``.

    Pre-Stage-12 the page-count truth (Rule B) isn't known, so any cap is a preliminary estimate
    refined after keyword analysis.
    """
    if seo is None:
        return seo, None

    capped = seo
    notes: list[str] = []
    pt = (project_type or "").strip().lower()
    dm = (data_access_model or "").strip().lower()

    # Rule A — account-gated SaaS
    if dm == "restricted" and (pt == "saas" or not require_saas_for_gating):
        if capped > gated_saas_ceiling:
            capped = gated_saas_ceiling
            notes.append(
                f"capped to {gated_saas_ceiling:.2f} (account-gated/restricted data is not publicly indexable)")

    # Rule B — thin / combinatorially-thin page counts (post-Stage-12 only)
    if estimated_indexable_pages is not None:
        pages = estimated_indexable_pages
        if pages < thin_pages_threshold and capped > thin_pages_ceiling:
            capped = thin_pages_ceiling
            notes.append(
                f"capped to {thin_pages_ceiling:.2f} ({pages} indexable pages < {thin_pages_threshold})")
        elif pages < high_score_min_pages and capped > moderate_pages_ceiling:
            capped = moderate_pages_ceiling
            notes.append(
                f"capped to {moderate_pages_ceiling:.2f} ({pages} pages < {high_score_min_pages} for the 0.8+ band)")

    # Rule C — hand-seeded / non-programmatic content
    if handseed_ceiling is not None and content_generation_model:
        cg = content_generation_model.lower()
        if any(h in cg for h in _HANDSEED_HINTS) and not any(h in cg for h in _PROGRAMMATIC_HINTS):
            if capped > handseed_ceiling:
                capped = handseed_ceiling
                notes.append(f"capped to {handseed_ceiling:.2f} (hand-seeded/non-programmatic content)")

    if capped < seo:
        return capped, ("SEO realism (preliminary estimate, refined after keyword analysis): "
                        + "; ".join(notes))
    return seo, None


def cap_idea_seo_realism(idea, settings) -> tuple[float | None, str | None]:
    """Thin wrapper: pull the real idea fields + settings ceilings, call the pure cap.

    Returns ``(capped_seo, note | None)``; does NOT mutate ``idea``.
    """
    return cap_seo_realism_score(
        getattr(idea, "seo_scalability_score", None),
        project_type=getattr(idea, "project_type", None),
        data_access_model=getattr(idea, "data_access_model", None),
        content_generation_model=getattr(idea, "content_generation_model", None),
        estimated_indexable_pages=getattr(idea, "estimated_indexable_pages", None),
        require_saas_for_gating=settings.seo_cap_require_saas_for_gating,
        gated_saas_ceiling=settings.seo_cap_gated_saas_ceiling,
        thin_pages_threshold=settings.seo_cap_thin_pages_threshold,
        thin_pages_ceiling=settings.seo_cap_thin_pages_ceiling,
        high_score_min_pages=settings.seo_cap_high_score_min_pages,
        moderate_pages_ceiling=settings.seo_cap_moderate_pages_ceiling,
        handseed_ceiling=(settings.seo_cap_handseed_ceiling
                          if settings.enable_seo_handseed_cap else None),
    )
