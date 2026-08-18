"""Segment payability scoring (permanent since the 2026-07-06 calibration-gate pass).

Scores each Stage-4 audience segment on its ability and habit of PAYING for software —
the signal the idea scores structurally miss (live 2026-07-06: procurement lead-gen ranked
#2 by composite while selling to bootstrapped indie founders, a documented low-WTP class).
Grounded in the bootstrapped-business criteria (budget authority + evidence of existing
spend), not stated intent.

Evidence per segment (all deterministic, already collected by the pipeline):
  - `budget_sensitivity` (Stage-4 LLM field, High/Medium/Low)
  - pains joined via `PainPoint.affected_segments` -> max/mean `commercial_intent` + up to
    two money-language quotes
  - the niche's incumbent pricing rows (`_probe_incumbents`) — proof the market already pays

One batched LLM call classifies each segment into a closed wallet-class vocabulary with a
0-1 score; the final score is a DETERMINISTIC blend (class prior averaged with the LLM
score, clamped) so a single optimistic LLM draw can't flip a personal-wallet segment into
a payable one. Fail-soft -> {} (callers no-op on missing payability, never wrongly demote).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .content_security import prompt_field

logger = logging.getLogger(__name__)

# Closed wallet-class vocabulary + priors. The prior anchors the blended score: classes are
# far more predictable than per-segment nuance (indie/hobbyist wallets are documented
# low-WTP regardless of how enthusiastic the corpus sounds).
PAYABILITY_CLASSES = ("corporate-budget", "smb-budget", "prosumer-wallet", "personal-wallet")
_CLASS_PRIOR = {
    "corporate-budget": 0.85,
    "smb-budget": 0.60,
    "prosumer-wallet": 0.40,
    "personal-wallet": 0.25,
}

# Human phrases for user-facing text (verdict concerns, downgrade notes). The raw class tokens
# and 0-1 scores are internal vocabulary — user-facing strings use these, never the enum/decimal.
PAYABILITY_CLASS_PHRASES = {
    "corporate-budget": "a buyer with organizational budget authority",
    "smb-budget": "a small-business buyer paying from business revenue",
    "prosumer-wallet": "a prosumer paying out of pocket",
    "personal-wallet": "a buyer spending personal money",
    "mixed": "a mixed pool of buyer types",
}


def payability_phrase(payability_class) -> str:
    """User-facing phrase for a wallet class (falls back to a neutral phrase, never the token)."""
    return PAYABILITY_CLASS_PHRASES.get(payability_class or "", "a buyer with unproven willingness-to-pay")

_MONEY_RE = re.compile(r"\$\s?\d|paid|paying|budget|subscription|per month|/mo|pricing|invoice",
                       re.IGNORECASE)


class SegmentPayability(BaseModel):
    model_config = ConfigDict(extra="ignore")
    segment_name: str = ""
    payability_score: float = 0.5
    payability_class: str = ""
    rationale: str = ""


class _PayabilityBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    segments: list[SegmentPayability] = Field(default_factory=list)


def norm_segment_name(name: str) -> str:
    return " ".join((name or "").lower().split())


def _segment_evidence(segment, pains) -> str:
    """Deterministic evidence lines for one segment: budget sensitivity, joined-pain buying
    signals, and up to two money-language quotes."""
    name = getattr(segment, "segment_name", "") or "?"
    budget = getattr(segment, "budget_sensitivity", None) or "unknown"
    joined = [p for p in (pains or [])
              if name.lower() in [s.lower() for s in (getattr(p, "affected_segments", None) or [])]]
    ci = [c for c in (getattr(p, "commercial_intent", None) for p in joined)
          if isinstance(c, (int, float))]
    ci_line = (f"max {max(ci):.2f}, mean {sum(ci) / len(ci):.2f} across {len(ci)} pain(s)"
               if ci else "no joined pains carried buying signals")
    quotes = []
    for p in joined:
        for q in (getattr(p, "representative_quotes", None) or []):
            if _MONEY_RE.search(q or ""):
                quotes.append(q.strip()[:160])
            if len(quotes) >= 2:
                break
        if len(quotes) >= 2:
            break
    lines = [f"### {name}",
             f"- budget sensitivity: {budget}",
             f"- expertise: {getattr(segment, 'expertise_level', None) or 'n/a'}",
             f"- buying signals (commercial intent of joined pains): {ci_line}"]
    for q in quotes:
        lines.append(f'- money quote: "{q}"')
    return "\n".join(lines)


def blend_payability(llm_score: float, payability_class: str,
                     budget_sensitivity: Optional[str]) -> float:
    """Deterministic blend: class prior averaged with the (clamped) LLM score; a High budget
    sensitivity caps the result at prior - 0.1 (a price-sensitive segment can't out-score its
    own wallet class)."""
    prior = _CLASS_PRIOR.get(payability_class, 0.5)
    llm = min(max(float(llm_score), 0.0), 1.0)
    score = (prior + llm) / 2.0
    if (budget_sensitivity or "").strip().lower() == "high":
        score = min(score, prior - 0.1)
    return round(min(max(score, 0.0), 1.0), 2)


def score_segment_payability(segments, pain_points, incumbent_rows, niche_description,
                             ) -> tuple[dict[str, SegmentPayability], Optional[object]]:
    """Score all segments in ONE batched LLM call; returns ({norm_name: SegmentPayability},
    usage). Fail-soft -> ({}, None)."""
    segments = [s for s in (segments or []) if (getattr(s, "segment_name", "") or "").strip()]
    if not segments:
        return {}, None
    try:
        from ..config.settings import settings
        from .llm_service import LLMService

        incumbent_lines = "\n".join(
            f"- {r.get('name', '?')}: {r.get('pricing', 'unknown')} ({r.get('focus', '')})"
            for r in (incumbent_rows or [])[:8]) or "none probed"
        evidence = "\n\n".join(_segment_evidence(s, pain_points) for s in segments[:5])
        prompt = (
            "Score each audience segment's ability and HABIT of paying for software. Judge the "
            "WALLET, not the job title: does someone hold budget authority, and is there "
            "evidence this segment already pays for tools? Classes:\n"
            "- corporate-budget: organizational budget authority (procurement, teams, agencies)\n"
            "- smb-budget: small-business operators paying from business revenue\n"
            "- prosumer-wallet: serious hobbyists paying out of pocket for their craft\n"
            "- personal-wallet: individuals spending personal money episodically (e.g. "
            "bootstrapped indie founders validating side-project ideas — a documented "
            "low-willingness-to-pay class no matter how loud the pain reads)\n\n"
            f"NICHE: {niche_description or 'n/a'}\n\n"
            f"TOOLS THIS MARKET ALREADY PAYS FOR (web-probed incumbents):\n{incumbent_lines}\n\n"
            f"SEGMENTS:\n{evidence}\n\n"
            "For EACH segment return: segment_name (EXACT name given), payability_class "
            "(exactly one class), payability_score (0-1), rationale (one evidence-grounded "
            "sentence — QUALITATIVE only, never cite numeric scores; the rationale may be "
            "shown to users). Never raise a score on pain intensity alone — pain without a "
            "wallet is not a market. Return JSON."
        )
        r, usage = LLMService.invoke_structured(
            prompt=prompt, output_model=_PayabilityBatch, temperature=0, timeout=120,
            model_name=settings.report_structured_llm, reasoning_effort="none")

        by_seg = {norm_segment_name(getattr(s, "segment_name", "")): s for s in segments}
        out: dict[str, SegmentPayability] = {}
        for item in (getattr(r, "segments", None) or []):
            key = norm_segment_name(item.segment_name)
            seg = by_seg.get(key)
            if seg is None or item.payability_class not in PAYABILITY_CLASSES:
                continue  # allow-list on INPUT names + closed vocab; drop the rest
            item.payability_score = blend_payability(
                item.payability_score, item.payability_class,
                getattr(seg, "budget_sensitivity", None))
            # WRITE truncation: this value is STORED (-> AudienceSegment.payability_rationale,
            # persisted through model_dump / checkpoint round-trip and re-read by
            # `_payability_map_from_segments`), so a cut here is inherited by every downstream
            # reader and no read-side fix can recover it. The old 200 constant severed 71 of 221
            # distinct values — 32.1%, sitting EXACTLY at 200 — mid-word and with no marker
            # (measured over the checkpoint corpus). The field has no length contract: the prompt
            # asks for "one evidence-grounded sentence" and the model field documents it as a
            # user-facing reason, and no renderer imposes a slot width. So the bound is the
            # runaway backstop only, and it announces itself when it fires.
            item.rationale = prompt_field((item.rationale or "").strip())
            out[key] = item
        if out:
            logger.info("[Payability] scored %d/%d segment(s): %s", len(out), len(segments),
                        "; ".join(f"{v.segment_name}={v.payability_score:.2f} "
                                  f"({v.payability_class})" for v in out.values()))
        return out, usage
    except Exception as e:  # noqa: BLE001 — fail-soft; callers no-op on missing payability
        logger.warning(f"[Payability] scoring failed (non-fatal): {str(e)[:120]}")
        return {}, None


def payer_retarget_hint(idea) -> Optional[str]:
    """Operator≠payer HYPOTHESIS for a thin-wallet idea with a B2B shape (run-quality
    fixes §5, 2026-07-30, exposure-only). The payability machinery scores the SOURCE
    segment's wallet — but when that segment merely OPERATES the tool (a freelance
    bookkeeper reconciling a restaurant's books), the likely payer may be a different
    segment with a real budget, and "thin wallet" is the wrong epitaph.

    Deliberately phrased as a hypothesis, never a claim: the b2b tag alone cannot prove
    a separate payer exists (live counter-example: ClearingCalc's b2b tag described the
    thin-wallet bookkeeper it charged directly). Deterministic, no LLM. Fires only when
    ALL hold: payability class is personal/prosumer-wallet, the payability score is
    below settings.payability_low_threshold (noise gate — without it the condition
    matches nearly every B2B pool), and tags.target_market is b2b/b2b2c. Pure function —
    called INLINE at exposure time (`_compose_ruled_out_reason`, `_idea_digest_line`),
    never stamped, so demotion-time snapshots can use it without ordering constraints."""
    from ..config.settings import settings

    pay_cls = (getattr(idea, "source_segment_payability_class", None) or "").strip().lower()
    if pay_cls not in ("personal-wallet", "prosumer-wallet"):
        return None
    pay = getattr(idea, "source_segment_payability", None)
    if not (isinstance(pay, (int, float)) and pay < settings.payability_low_threshold):
        return None
    tags = getattr(idea, "tags", None)
    target = (getattr(tags, "target_market", None) or "").strip().lower() if tags is not None else ""
    if target not in ("b2b", "b2b2c"):
        return None
    segment = getattr(idea, "source_segment", None) or "this segment"
    return (
        f"The low payability score describes {segment} as the buyer — if they operate "
        "this tool on someone else's books or budget, the paying segment may differ; "
        "worth re-checking who actually pays before ruling this out."
    )
