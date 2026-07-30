"""Run-level idea-portfolio summary — one honest-reviewer LLM narrative assessing the
STRENGTHS/WEAKNESSES of the whole VISIBLE idea pool, generated once at the end of Stage 5
(after funnel counts + the niche-difficulty verdict are final; see research_flow.py). A
second, orthogonal prose layer alongside NicheDifficultyVerdict: that verdict judges the
NICHE, this judges the SPECIFIC ideas the pipeline generated for it.

Deterministic digest -> ONE grounded LLM call -> deterministic name-coverage guardrail
(retry once with an explicit reminder, then fail-soft to None). Unlike
utils/niche_difficulty.py, there is no code-computed fallback prose — a failed/ungrounded
call means no summary at all (never a fabricated or partial one; the UI card just doesn't
render).
"""

from __future__ import annotations

import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from .score_helpers import score_band

# Delta above which a raw (generator self-issued) market_fit score is reported as
# "self-score corrected down" — mirrors the calibration-gap notability bar used elsewhere
# (utils/niche_difficulty.py CALIB_GAP_NOTABLE).
_SELF_SCORE_CORRECTION_DELTA = 0.15


class _PortfolioSummary(BaseModel):
    summary: str = Field(
        "", description="2-4 short paragraphs, plain text (no markdown), honest reviewer tone"
    )


def _idea_digest_line(idea) -> str:
    """One deterministic, words-only digest line for a single visible idea. Everything
    quantitative is rendered as a qualitative band (score_band), never a raw decimal — the
    prompt built from these lines must not give the LLM a number to echo. Deliberately
    excludes source_frame (internal generation steer, not yet user-facing)."""
    name = getattr(idea, "solution_name", "?") or "?"
    mf = getattr(idea, "market_fit_score", None)
    mf_raw = getattr(idea, "market_fit_score_raw", None)
    mf_band = score_band(mf)
    corrected = ""
    if (
        isinstance(mf, (int, float))
        and isinstance(mf_raw, (int, float))
        and mf_raw - mf >= _SELF_SCORE_CORRECTION_DELTA
    ):
        corrected = " (self-score corrected down during calibration)"
    seo_band = score_band(getattr(idea, "seo_scalability_score", None))
    pay = getattr(idea, "source_segment_payability", None)
    pay_band = score_band(pay)
    pay_class = getattr(idea, "source_segment_payability_class", None) or "unclassified"
    parity = (getattr(idea, "incumbent_parity", None) or "").strip() or "no incumbent match found"
    adjacent = (getattr(idea, "adjacent_market_parity", None) or "").strip() or "n/a"
    dev_time = getattr(idea, "estimated_development_time", None) or "unestimated"
    tags = getattr(idea, "tags", None)
    risk_flags = list(getattr(tags, "risk_flags", None) or []) if tags is not None else []
    pricing_note = (getattr(tags, "pricing_shape_note", None) or "").strip() if tags is not None else ""

    rt_verdict = (getattr(idea, "red_team_verdict", None) or "").strip()
    rt_caveats = list(getattr(idea, "red_team_caveats", None) or [])
    rt_clause = ""
    if getattr(idea, "red_team_revised", None):
        rt_clause = "; revised after red-team review"
    elif rt_verdict:
        first = f" ({rt_caveats[0]})" if rt_caveats else ""
        rt_clause = f"; red-team verdict: {rt_verdict}{first}"
    elif getattr(idea, "red_team_vocab_mismatch", None):
        # Off-category abstain — surface it as a retrieval failure so the summary
        # LLM cannot spin it into "no incumbents found" (RUN_QUALITY_ROOT_CAUSES §2).
        rt_clause = ("; red-team probe abstained: off-category evidence (vocabulary "
                     "mismatch — not negative market evidence)")

    # Operator≠payer hypothesis (run-quality fixes §5): computed inline, never stamped —
    # stops the summary from writing "no wallet" over a re-targetable visible idea.
    from .segment_payability import payer_retarget_hint
    payer_hint = payer_retarget_hint(idea)
    payer_clause = f"; payer note: {payer_hint}" if payer_hint else ""

    return (
        f"- {name}: market fit {mf_band}{corrected}; SEO scalability {seo_band}; "
        f"dev time {dev_time}; buyer-segment payability {pay_band} ({pay_class}); "
        f"incumbent parity: {parity}; adjacent-market parity: {adjacent}; "
        f"risk flags: {', '.join(risk_flags) if risk_flags else 'none'}; "
        f"pricing note: {pricing_note or 'none'}"
        + rt_clause
        + payer_clause
    )


def build_idea_portfolio_digest(
    ideas: list,
    ruled_out: Optional[list[dict]] = None,
    funnel_counts: Optional[dict] = None,
    niche_wallet_brief: Optional[dict] = None,
    niche_difficulty_headline: Optional[str] = None,
    niche_difficulty_narrative: Optional[str] = None,
) -> str:
    """Pure, deterministic, no-LLM/IO digest of the VISIBLE idea pool plus run-level context
    — the grounding text fed verbatim into the portfolio-summary prompt. Accepts the raw
    (unfiltered) idea list; applies `visible_ideas()` internally so callers never have to
    remember the filter. Returns '' when there are no visible ideas (callers should skip the
    LLM call entirely on an empty digest)."""
    from ..models.solution_idea import visible_ideas

    visible = visible_ideas(ideas)
    if not visible:
        return ""

    lines = ["VISIBLE IDEAS (the ones the user sees as candidates):"]
    lines.extend(_idea_digest_line(i) for i in visible)

    ro = list(ruled_out or [])
    if ro:
        lines.append(
            "\nEXAMINED & RULED OUT (findings the market's own evidence produced, "
            "not generation failures):"
        )
        lines.extend(
            f"- {r.get('idea_name', '?')}: {r.get('reason', 'no reason recorded')}" for r in ro
        )

    fc = dict(funnel_counts or {})
    if fc:
        lines.append("\nRESEARCH FUNNEL: " + ", ".join(f"{k}={v}" for k, v in fc.items()))

    wallet = dict(niche_wallet_brief or {})
    if wallet.get("wallet_class"):
        lines.append(
            f"\nNICHE SPEND NORM: {wallet['wallet_class']} — {wallet.get('evidence') or 'no detail'}. "
            f"Free routes: {wallet.get('free_density') or 'unknown'}."
        )

    if niche_difficulty_headline or niche_difficulty_narrative:
        lines.append(
            "\nRESEARCH REALITY CHECK (software-fit verdict for the niche as a whole): "
            f"{niche_difficulty_headline or ''} {niche_difficulty_narrative or ''}".strip()
        )

    return "\n".join(lines)


def generate_idea_portfolio_summary(
    ideas: list,
    ruled_out: Optional[list[dict]] = None,
    funnel_counts: Optional[dict] = None,
    niche_wallet_brief: Optional[dict] = None,
    niche_difficulty_headline: Optional[str] = None,
    niche_difficulty_narrative: Optional[str] = None,
    niche: Optional[str] = None,
) -> tuple[Optional[str], Optional[object]]:
    """Generate the run-level portfolio summary: one honest-reviewer LLM narrative over the
    VISIBLE idea pool + run-level context. Fail-soft -> (None, None) whenever there is
    nothing to summarize or the call fails outright.

    Deterministic post-call guardrail: every visible idea must be named in the text (case-
    insensitive substring match) — retry once with an explicit reminder, else give up and
    return None (no JSON-repair, no partial summary). `usage` reflects only the LAST attempt
    made (the common case is a single call; the retry path is a rare edge case and is not
    cost-tracked twice)."""
    from ..config.settings import settings
    from ..models.solution_idea import visible_ideas
    from .llm_service import LLMService

    visible = visible_ideas(ideas)
    names = [(getattr(i, "solution_name", "") or "").strip() for i in visible]
    names = [n for n in names if n]
    if not names:
        return None, None

    def _name_head(name: str) -> str:
        # Coverage matches on the name's head — long names carry subtitle tails
        # ("ShipDelayRadar Ops (Risk-Aware Pick/Pack + ...)", "ClosePack Recon: ...")
        # that models rightly shorten in prose; demanding the full string drops
        # otherwise-valid summaries (live-caught on the Etsy run, 2026-07-10).
        head = re.split(r"[(:]", name, maxsplit=1)[0].strip()
        return head if len(head) >= 4 else name

    digest = build_idea_portfolio_digest(
        ideas,
        ruled_out=ruled_out,
        funnel_counts=funnel_counts,
        niche_wallet_brief=niche_wallet_brief,
        niche_difficulty_headline=niche_difficulty_headline,
        niche_difficulty_narrative=niche_difficulty_narrative,
    )
    if not digest:
        return None, None

    base_prompt = (
        f"Niche: {niche or 'this niche'}\n\n{digest}\n\n"
        "Write an honest analyst's summary of this idea pool for the founder who is about "
        "to pick one to validate further. Reviewer tone: candid, not promotional. 2-4 short "
        "paragraphs of PLAIN TEXT — no markdown headers, no bullet lists. You MUST mention "
        "every idea listed under VISIBLE IDEAS by name, exactly once each. Attribute every "
        "weakness to the market evidence given above — never invent a reason, and never cite "
        "the exact digits behind a score (say 'strong', 'moderate', or 'weak market fit', "
        "never a decimal). If the whole pool looks weak, say so plainly and make clear "
        "that's the market's verdict, not a failure of the idea-generation process. End the "
        "summary by naming the 1-2 ideas that most deserve deep validation next, and why — "
        "reasoned from the evidence above only, no new facts."
    )

    usage = None
    summary: Optional[str] = None
    missing: list[str] = names
    for attempt in range(2):  # one grounded call + at most one name-coverage re-prompt
        prompt = base_prompt
        if attempt == 1:
            prompt += (
                "\n\nYOUR PREVIOUS ATTEMPT DID NOT MENTION: "
                f"{', '.join(missing)}. Rewrite the summary so every idea listed under "
                "VISIBLE IDEAS is named at least once."
            )
        try:
            result, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_PortfolioSummary,
                temperature=0.3,
                timeout=90,
                model_name=settings.function_calling_llm,
            )
        except Exception as e:  # noqa: BLE001 — fail-soft, never blocks the pipeline
            logger.warning(f"[PortfolioSummary] LLM call failed (attempt {attempt + 1}): {str(e)[:120]}")
            return None, usage
        text = (result.summary or "").strip()
        low = text.lower()
        missing = [n for n in names if _name_head(n).lower() not in low]
        if text and not missing:
            summary = text
            break
        logger.info(f"[PortfolioSummary] attempt {attempt + 1} missing names: {missing or names}")
        missing = missing or names

    if summary is None:
        logger.warning(
            "[PortfolioSummary] failed name-coverage guardrail after retry; dropping summary."
        )
    return summary, usage
