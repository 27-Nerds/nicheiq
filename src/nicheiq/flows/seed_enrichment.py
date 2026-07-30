"""
Best-effort quality passes for catalog-seeded research jobs.

- `synthesize_remix_niche_context` — one structured-LLM call producing a
  coherent cross-niche NicheContext for remix jobs; the hand-rolled template in
  `catalog_seed.build_pain_seed_state` remains the fallback on ANY failure.
- `collect_seed_evidence` / `maybe_enrich_seed` — targeted Hacker News evidence
  collection so seeded runs don't execute with `social_content=None` (which
  thins the report's evidence appendix and forces stage 11's "Risky" fallback
  trend verdict).

Hacker News only for v1: there is no standalone Reddit search path (subreddit
discovery lives inside the stage-2 flow listener and depends on Serper). A
Reddit pass needs either Serper-based discovery or an r/all search validation —
deferred until the `[SeedEnrichment]` log lines show whether HN-only pulls its
weight.

Everything here is BEST-EFFORT: `maybe_enrich_seed` swallows all errors except
job cancellation; callers proceed without enrichment on failure.
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from ..config.settings import settings
from ..models.research_state import NicheContext
from ..models.social_content import SocialContentCollection
from ..utils.engagement_normalizer import normalize_engagement
from ..utils.validation.dedup import deduplicate_posts
from .catalog_seed import MAX_REMIX_PAINS, sanitize_label

MAX_QUERIES = 6
MAX_POSTS = 12
# checkpoint_manager's load-time quality gate discards a social_content
# checkpoint with fewer than 3 total posts AND resets current_stage to <=2 —
# on Phase-2 resume that would re-run discovery uncharged and overwrite the
# user's explicitly selected pains. Never persist a thinner collection.
MIN_POSTS = 3


def synthesize_remix_niche_context(
    pain_dicts: list[dict], niche_label: str
) -> tuple[NicheContext, Any]:
    """LLM-synthesize a coherent cross-niche NicheContext for a remix job.

    Raises on any failure — the caller keeps the template context from
    `build_pain_seed_state`. Returns (context, TokenUsage).
    """
    if not pain_dicts:
        raise ValueError("synthesize_remix_niche_context requires pains")

    pains = pain_dicts[:MAX_REMIX_PAINS]
    source_niches: list[str] = []
    for p in pains:
        sn = sanitize_label(p.get("source_niche"))
        if sn and sn not in source_niches:
            source_niches.append(sn)
    segments: list[str] = []
    for p in pains:
        for s in p.get("affected_segments") or []:
            cs = sanitize_label(s)
            if cs and cs not in segments:
                segments.append(cs)
    pain_lines = "\n".join(
        f'{i + 1}. "{sanitize_label(p.get("title"))}" — '
        f'{sanitize_label(p.get("description"))[:300]}'
        for i, p in enumerate(pains)
    )

    prompt = f"""You are a market research analyst. A user combined {len(pains)} validated pain points from {len(source_niches) or 1} different niche(s) into a single cross-niche research brief.

**Source niches:** {", ".join(source_niches) or "not specified"}

**Pain points:**
{pain_lines}

**Affected segments observed in the source data:** {", ".join(segments[:10]) or "not specified"}

**Your Task:**
Define the unified market that a single product addressing ALL of these pains would serve:

1. **niche_description**:
   - 2-3 sentences naming the COMMON THREAD that connects these pains — the shared workflow, buyer, or underlying job-to-be-done
   - Do NOT merely restate the pain list

2. **market_segments**:
   - 3-7 specific segments that experience SEVERAL of these pains at once (not one segment per source niche)

3. **industry_boundaries**:
   - 2-3 sentences: IN scope = solutions to the listed pains in the unified market; OUT of scope = adjacent problems and the parts of each source niche unrelated to these pains

Return a valid JSON object with this structure:
{{
  "niche_description": "...",
  "market_segments": ["segment 1", "segment 2", "..."],
  "industry_boundaries": "..."
}}"""

    from ..utils.llm_service import LLMService

    context, usage = LLMService.invoke_structured(
        prompt=prompt,
        output_model=NicheContext,
        temperature=0.5,
        timeout=90,
        model_name=settings.openai_model_name,
    )
    if not context.niche_description or not context.market_segments:
        raise ValueError("synthesized niche context is incomplete")
    # Force the job label as niche_input (mirrors stage 1's post-fill).
    context.niche_input = niche_label
    return context, usage


def collect_seed_evidence(
    query_candidates: list[str],
    niche_description: str,
    cancel_check: Callable[[], None] | None = None,
) -> SocialContentCollection | None:
    """Targeted HN evidence collection for a seeded run.

    Returns None when fewer than MIN_POSTS relevant posts are found — see the
    MIN_POSTS comment; persisting a thin collection corrupts Phase-2 resume.
    """
    queries: list[str] = []
    seen: set[str] = set()
    for candidate in query_candidates:
        q = " ".join(sanitize_label(candidate).split()[:10])
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
        if len(queries) >= MAX_QUERIES:
            break
    if not queries:
        return None

    if cancel_check:
        cancel_check()

    from ..tools.hackernews_tool import HackerNewsCollectorTool

    collection = HackerNewsCollectorTool().search_relevant_and_collect(
        queries,
        niche_description=niche_description,
        max_results_per_query=8,
        max_total=MAX_POSTS,
    )

    if cancel_check:
        cancel_check()

    # The shared HN collector owns semantic relevance. Keep this persisted-grade
    # check as a contract boundary so no ungraded legacy/mock post can enter a
    # seed checkpoint.
    relevant = [
        p for p in collection.posts
        if p.relevance_grade is not None and p.relevance_grade >= 2
    ]
    relevant = deduplicate_posts(relevant, threshold=0.6)
    relevant.sort(key=normalize_engagement, reverse=True)
    relevant = relevant[:MAX_POSTS]

    if len(relevant) < MIN_POSTS:
        return None

    return SocialContentCollection(
        generic_posts=relevant,
        # num_responses (API total), NOT len(responses) (capped at collection) —
        # matches the normal stage-2 computation.
        total_generic_responses=sum(p.num_responses for p in relevant),
    )


def maybe_enrich_seed(
    flow: Any,
    query_candidates: list[str],
    niche_description: str,
    cancel_check: Callable[[], None] | None = None,
) -> None:
    """Best-effort enrichment entry for the catalog worker tasks.

    On success: sets `flow.state.social_content` and persists the
    `stage_2_social_content` checkpoint (so pain-mode Phase 2 resume keeps it).
    Job cancellation propagates; every other failure logs and returns.
    """
    job_id = getattr(flow, "job_id", "?")
    try:
        evidence = collect_seed_evidence(
            query_candidates, niche_description, cancel_check=cancel_check
        )
    except Exception as e:
        # Cancellation is raised by the injected cancel_check (worker-owned
        # exception type — matched by name to keep library code free of worker
        # imports); it must end the job, not be swallowed.
        if type(e).__name__ == "JobCancelledException":
            raise
        logger.warning(f"[SeedEnrichment] job={job_id} enrichment=skipped reason=error: {e}")
        return
    if evidence is None:
        logger.info(
            f"[SeedEnrichment] job={job_id} posts=0 enrichment=skipped "
            "reason=insufficient_relevant_posts"
        )
        return
    flow.state.social_content = evidence
    flow.checkpoint_mgr.save_stage("stage_2_social_content", evidence)
    logger.info(
        f"[SeedEnrichment] job={job_id} posts={len(evidence.generic_posts)} enrichment=used"
    )
