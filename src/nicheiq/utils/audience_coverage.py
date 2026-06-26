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
                    "thin in the extracted pains (empty when coverage is balanced).")
    rebalance_directive: str = Field(
        "", description="A specific instruction for a re-extraction to surface the missing audiences' "
                        "pains, grounded in real corpus evidence (empty when no rebalance needed).")
    rebalance_needed: bool = Field(
        False, description="True only when a real, evidence-backed audience gap exists.")
    rationale: str = Field("", description="≤220 chars grounding the call in the corpus vs the pains.")


def _default_invoke(prompt, model_name, reasoning_effort):
    return LLMService.invoke_structured(
        prompt=prompt, output_model=AudienceCoverageVerdict, temperature=0.2,
        model_name=model_name, reasoning_effort=reasoning_effort)


def _render_prompt(pain_titles, target_audience, market_segments, corpus_sample) -> str:
    segs = "\n".join(f"  - {s}" for s in (market_segments or [])) or "  (none specified)"
    pains = "\n".join(f"  - {t}" for t in pain_titles) or "  (none)"
    corpus = "\n".join(f"  - {t}" for t in corpus_sample) or "  (none)"
    return (
        "You are auditing a pain-point extraction for AUDIENCE-COVERAGE BIAS. Extractors often over-pick "
        "the loudest sub-audience (e.g. competitive players ranting) and crowd out quieter but larger "
        "sub-audiences (spectators, collectors, economic participants) even when the community discusses "
        "them heavily.\n\n"
        f"TARGET AUDIENCE: {target_audience or 'the niche audience'}\n"
        f"INTENDED AUDIENCE SUB-GROUPS:\n{segs}\n\n"
        f"PAINS THE EXTRACTOR SURFACED ({len(pain_titles)}):\n{pains}\n\n"
        f"WHAT THE COMMUNITY ACTUALLY DISCUSSES (sample of real post titles):\n{corpus}\n\n"
        "Identify audience sub-groups that are CLEARLY PRESENT in the community discussion (the post "
        "titles) but MISSING or thin in the extracted pains. Only flag a gap you can ground in the "
        "titles — do NOT invent demand. If the pains already reflect the corpus's audience mix, set "
        "rebalance_needed=false. Otherwise list the under_covered_audiences and write a rebalance_"
        "directive telling a re-extraction to surface THEIR pains from the existing corpus evidence "
        "(no fabrication; skip a sub-group if its evidence is actually thin)."
    )


def assess_audience_coverage(
    pain_titles: list[str],
    target_audience: str,
    market_segments: list[str],
    corpus_sample: list[str],
    *,
    invoke=_default_invoke,
    model_name: str | None = None,
    reasoning_effort: str = "medium",
) -> AudienceCoverageVerdict:
    """Return a grounded verdict on whether the extracted pains under-serve audiences the corpus
    contains. Fail-soft: any error → no-rebalance verdict (never blocks extraction)."""
    if not pain_titles or not corpus_sample:
        return AudienceCoverageVerdict()
    model_name = model_name or settings.pain_point_validation_llm
    try:
        verdict, _ = invoke(_render_prompt(pain_titles, target_audience, market_segments, corpus_sample),
                            model_name, reasoning_effort)
        return verdict
    except Exception as e:
        logger.warning(f"[AudienceCoverage] critic failed (fail-soft, no rebalance): {str(e)[:120]}")
        return AudienceCoverageVerdict()
