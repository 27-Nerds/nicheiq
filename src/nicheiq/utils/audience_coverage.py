"""Part 4 — audience-coverage critic (a SEPARATE, grounded pain-critique pass).

The 3-run audit found pain extraction is unstable on the audience axis: run 6a4600ca regressed to
player/anti-cheat pains even though its corpus was 2:1 FAN-vs-player (the fan content was present but
the extractor crowded it out — EXTRACTION-limited, not corpus-limited). The plan's fix is a separate,
externally-grounded critic (NOT an inline critic-in-prompt — intrinsic self-correction doesn't work),
which reads the EXTRACTED pains against the TARGET AUDIENCE and a sample of what the community ACTUALLY
discusses, and flags audience sub-groups that are well-represented in the corpus but missing from the
pains. Its directive then drives ONE corrective re-extraction (reusing PainPointCrew._run_corrective_
extraction's machinery + anti-fabrication rule).

Pure + dependency-injected (`invoke`) so it's isolated-testable and A/B-validatable without the crew.

Workstream A (audience-rebalance plan) grounds the critic quantitatively: `corpus_composition`
turns the raw corpus into (source, count, sample titles) shares instead of a flat unweighted title
slice, so the critic's evidence block can cite "X% of posts are from r/Y" instead of an anonymous
sample that can silently omit a quiet-but-real sub-audience.

Workstream B (critic-only) adds `persona_from_niche`, a deterministic leading-persona-clause
extractor used to give the critic a concrete "who" on plain-niche runs (no stated target_audience),
so it has something to resolve sub-audiences against. Never used to scope research/query-gen.
"""
from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..utils.llm_service import LLMService


class AudienceCoverageVerdict(BaseModel):
    """Whether the extracted pains under-serve audience sub-groups the CORPUS clearly contains."""
    under_covered_audiences: list[str] = Field(
        default_factory=list,
        description="Audience sub-groups well-represented in the community discussion but missing / "
                    "thin in the extracted pains (empty when coverage is balanced). REQUIRED — must "
                    "list the group names — whenever rebalance_needed=true; naming them only in "
                    "rationale is not enough, that field is never read by the pipeline.")
    rebalance_directive: str = Field(
        "", description="A specific instruction for a re-extraction to surface the missing audiences' "
                        "pains, grounded in real corpus evidence (empty when no rebalance needed). "
                        "REQUIRED — a concrete one-sentence extraction instruction — whenever "
                        "rebalance_needed=true; an empty directive makes the verdict inert (the "
                        "re-extraction it triggers gets no instruction), so never set "
                        "rebalance_needed=true without filling this in.")
    rebalance_needed: bool = Field(
        False, description="True only when a real, evidence-backed audience gap exists.")
    rationale: str = Field("", description="≤220 chars grounding the call in the corpus vs the pains. "
                           "Informational only — the pipeline does NOT read this field, so it must "
                           "never be the only place the under-covered groups or the directive appear.")
    evidence_shares: dict[str, float] = Field(
        default_factory=dict,
        description="Telemetry only: the corpus share (0-100) the critic grounded each flagged "
                    "under-covered audience in, when a corpus_evidence composition block was "
                    "available. Empty on legacy runs, flat corpus_sample runs, or when the critic "
                    "didn't populate it. Never used to gate rebalance_needed.")


def _default_invoke(prompt, model_name, reasoning_effort):
    # creative=True: the reasoning-ON tool path. On the guided json_schema/reason-off path,
    # deepseek-v4-flash returned rebalance_needed=True with EMPTY structured directive fields
    # in 6/6 live calls even after an explicit retry reminder (2026-07-11 harness) — the same
    # signature as the judge-feasibility no-op (critic emitting 0 numeric scores), where
    # creative=True was the validated fix.
    return LLMService.invoke_structured(
        prompt=prompt, output_model=AudienceCoverageVerdict, temperature=0.2,
        model_name=model_name, reasoning_effort=reasoning_effort, creative=True)


def corpus_composition(
    posts, *, sample_cap: int = 70
) -> list[tuple[str, int, list[str]]]:
    """Group corpus posts by source community and produce a stratified title sample.

    Returns ``[(source_label, post_count, sample_titles)]`` sorted desc by post_count. Label is
    ``r/<subreddit>`` for Reddit posts, else the post's ``platform`` attribute, else falls back to
    "twitter" (Twitter threads carry neither field). Sample titles are stratified proportional to
    each source's share of the total post count -- NOT a flat first-N slice, which can silently
    omit a quiet-but-real sub-audience entirely -- with a floor of 1 title for any source with >=3
    posts, and the total capped at ~``sample_cap`` titles.
    """
    buckets: dict[str, list[str]] = {}
    for p in posts or []:
        title = getattr(p, "title", "") or ""
        if not title:
            continue
        subreddit = getattr(p, "subreddit", None)
        if subreddit:
            label = f"r/{subreddit}"
        else:
            label = getattr(p, "platform", None) or "twitter"
        buckets.setdefault(label, []).append(title)

    total = sum(len(titles) for titles in buckets.values())
    if total == 0:
        return []

    composition: list[tuple[str, int, list[str]]] = []
    for label, titles in buckets.items():
        count = len(titles)
        quota = round(sample_cap * count / total)
        if count >= 3:
            quota = max(quota, 1)
        quota = min(quota, count)
        composition.append((label, count, titles[:quota]))

    composition.sort(key=lambda t: t[1], reverse=True)
    return composition


def persona_from_niche(niche_description: str) -> tuple[str, str]:
    """Extract a deterministic leading persona clause from a niche description.

    Used to give the audience-coverage critic a concrete "who" on plain-niche runs (no stated
    target_audience) instead of the whole niche string, so it can resolve sub-audiences. Cuts the
    description at the first " who "/" that " clause boundary, keeping everything before it
    (including leading qualifiers -- e.g. "...agents running small agencies who handle X" keeps
    "running small agencies"; narrowing all the way to the bare head noun phrase would over-narrow
    the persona). Falls back to the full description (source "niche_full") when the description is
    short (<6 words), has no such clause boundary, or the extracted head would itself be too short
    (<3 words) to be a useful persona. No LLM call -- pure, deterministic string ops.

    Returns (audience_string, source) with source in {"niche_persona", "niche_full"}.
    """
    text = (niche_description or "").strip()
    if len(text.split()) < 6:
        return text, "niche_full"

    cut = len(text)
    lower = text.lower()
    for delim in (" who ", " that "):
        idx = lower.find(delim)
        if idx != -1:
            cut = min(cut, idx)
    if cut == len(text):
        return text, "niche_full"

    head = text[:cut].strip()
    if len(head.split()) < 3:
        return text, "niche_full"
    return head, "niche_persona"


def _render_corpus_block(corpus_sample, corpus_evidence) -> str:
    if corpus_evidence:
        composition = corpus_evidence.get("composition") or []
        pain_sources = corpus_evidence.get("pain_sources") or {}
        total = sum(count for _, count, _ in composition) or 1
        comp_lines = []
        for label, count, titles in composition:
            pct = 100.0 * count / total
            comp_lines.append(f"  - {label}: {pct:.0f}% ({count} posts)")
            for t in titles:
                comp_lines.append(f"      - {t}")
        comp_block = "\n".join(comp_lines) or "  (none)"
        pain_lines = []
        for title, labels in pain_sources.items():
            if labels is None:
                src = "(unattributable — ignore for coverage judgments)"
            elif labels:
                src = ", ".join(labels)
            else:
                src = "(none matched)"
            pain_lines.append(f"  - {title}: {src}")
        pain_block = "\n".join(pain_lines) or "  (none)"
        return (
            f"CORPUS COMPOSITION (share of posts by community):\n{comp_block}\n\n"
            "EXTRACTED PAINS AND WHICH COMMUNITIES' POSTS THEY MATCH (approximate, keyword-based):\n"
            "  (Treat '(unattributable)' pains as neutral — never as evidence a community lacks pains.)\n"
            f"{pain_block}"
        )
    corpus = "\n".join(f"  - {t}" for t in (corpus_sample or [])) or "  (none)"
    return f"WHAT THE COMMUNITY ACTUALLY DISCUSSES (sample of real post titles):\n{corpus}"


def _render_prompt(pain_titles, target_audience, market_segments, corpus_sample,
                    corpus_evidence=None) -> str:
    segs = "\n".join(f"  - {s}" for s in (market_segments or [])) or "  (none specified)"
    pains = "\n".join(f"  - {t}" for t in pain_titles) or "  (none)"
    corpus_block = _render_corpus_block(corpus_sample, corpus_evidence)
    evidence_rule = (
        "\n\nA sub-audience is UNDER-COVERED when a community with a large corpus share (see "
        "percentages) has zero or few pains drawing from it. Ground every flag in a share "
        "number. Do not flag a sub with <10% share."
    ) if corpus_evidence else ""
    return (
        "You are auditing a pain-point extraction for AUDIENCE-COVERAGE BIAS. Extractors often over-pick "
        "the loudest sub-audience (e.g. competitive players ranting) and crowd out quieter but larger "
        "sub-audiences (spectators, collectors, economic participants) even when the community discusses "
        "them heavily.\n\n"
        f"TARGET AUDIENCE: {target_audience or 'the niche audience'}\n"
        f"INTENDED AUDIENCE SUB-GROUPS:\n{segs}\n\n"
        f"PAINS THE EXTRACTOR SURFACED ({len(pain_titles)}):\n{pains}\n\n"
        f"{corpus_block}\n\n"
        "Identify audience sub-groups that are CLEARLY PRESENT in the community discussion (the post "
        "titles) but MISSING or thin in the extracted pains. Only flag a gap you can ground in the "
        "titles — do NOT invent demand. If the pains already reflect the corpus's audience mix, set "
        "rebalance_needed=false. Otherwise list the under_covered_audiences and write a rebalance_"
        "directive telling a re-extraction to surface THEIR pains from the existing corpus evidence "
        "(no fabrication; skip a sub-group if its evidence is actually thin)."
        f"{evidence_rule}\n\n"
        "IMPORTANT: if you set rebalance_needed=true, you MUST populate BOTH "
        "under_covered_audiences (the group names) AND rebalance_directive (the one-sentence "
        "extraction instruction) — the rationale field is NOT read by the pipeline, so naming the "
        "groups only in rationale has no effect. An empty under_covered_audiences/rebalance_"
        "directive with rebalance_needed=true triggers a corrective re-extraction with no "
        "instruction, which is worse than not flagging at all."
    )


def assess_audience_coverage(
    pain_titles: list[str],
    target_audience: str,
    market_segments: list[str],
    corpus_sample: list[str] | None = None,
    *,
    corpus_evidence: dict | None = None,
    invoke=_default_invoke,
    model_name: str | None = None,
    reasoning_effort: str = "medium",
) -> AudienceCoverageVerdict:
    """Return a grounded verdict on whether the extracted pains under-serve audiences the corpus
    contains. Fail-soft: any error → no-rebalance verdict (never blocks extraction).

    `corpus_sample` (legacy) is a flat list of post titles. `corpus_evidence` (Workstream A) is the
    richer, structured alternative: {"composition": corpus_composition(...) output,
    "pain_sources": {pain_title: [source_label, ...]}}. When both are omitted (or empty), this is a
    no-op short circuit -- same as the legacy `corpus_sample`-only contract.

    Deterministic empty-directive guard (live-caught via scripts/audience_coverage_critic_ab.py: 4/4
    deepseek-v4-flash calls returned rebalance_needed=True with an EMPTY rebalance_directive while
    naming the groups only in rationale, which the pipeline never reads): if rebalance_needed is True
    but rebalance_directive is blank, retry ONCE with an explicit reminder appended. If the retry is
    still blank, log a warning and coerce rebalance_needed=False -- an instruction-less rebalance is
    inert anyway (the corrective re-extraction it triggers gets no directive), so this just makes the
    inertness honest instead of firing a directive-less retry downstream.
    """
    has_evidence = bool(corpus_evidence and (
        corpus_evidence.get("composition") or corpus_evidence.get("pain_sources")))
    if not pain_titles or not (corpus_sample or has_evidence):
        return AudienceCoverageVerdict()
    model_name = model_name or settings.pain_point_validation_llm
    try:
        prompt = _render_prompt(pain_titles, target_audience, market_segments, corpus_sample,
                                 corpus_evidence if has_evidence else None)
        verdict, _ = invoke(prompt, model_name, reasoning_effort)
        if verdict.rebalance_needed and not verdict.rebalance_directive.strip():
            logger.warning(
                "[AudienceCoverage] rebalance_needed=True but rebalance_directive is empty "
                "(inert verdict) — retrying once with an explicit reminder."
            )
            retry_prompt = prompt + (
                "\n\nYOUR PREVIOUS ANSWER SET rebalance_needed=true BUT LEFT rebalance_directive "
                "EMPTY. rebalance_directive is REQUIRED whenever rebalance_needed=true — write the "
                "one-sentence extraction instruction there (and list the group names in "
                "under_covered_audiences). Naming the groups only in rationale does not count; that "
                "field is never read by the pipeline."
            )
            verdict, _ = invoke(retry_prompt, model_name, reasoning_effort)
            if verdict.rebalance_needed and not verdict.rebalance_directive.strip():
                logger.warning(
                    "[AudienceCoverage] retry still returned rebalance_needed=True with an empty "
                    "rebalance_directive — coercing to no-rebalance (inert verdict, so this makes "
                    "the inertness honest instead of firing a directive-less corrective re-extraction)."
                )
                verdict = verdict.model_copy(update={"rebalance_needed": False})
        return verdict
    except Exception as e:
        logger.warning(f"[AudienceCoverage] critic failed (fail-soft, no rebalance): {str(e)[:120]}")
        return AudienceCoverageVerdict()
