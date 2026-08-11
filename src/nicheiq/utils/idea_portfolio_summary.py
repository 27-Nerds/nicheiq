"""Run-level idea-portfolio summary — one honest-reviewer LLM narrative assessing the
STRENGTHS/WEAKNESSES of the whole VISIBLE idea pool, generated at the end of Stage 5 and
refreshed after a successful visible-pool mutation (see research_flow.py). A
second, orthogonal prose layer alongside NicheDifficultyVerdict: that verdict judges the
NICHE, this judges the SPECIFIC ideas the pipeline generated for it.

Deterministic digest -> ONE grounded LLM call -> deterministic name-coverage, visibility,
and commercial-copy guardrail (retry once with an explicit correction, then fail-soft to None).
Unlike
utils/niche_difficulty.py, there is no code-computed fallback prose — a failed/ungrounded
call means no summary at all (never a fabricated or partial one; the UI card just doesn't
render).
"""

from __future__ import annotations

import json
import re
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from .niche_difficulty import (
    monetization_guidance,
    paying_wallet_commercial_contract_copy,
    paying_wallet_summary_copy_violations,
    priced_wallet_prescription_violations,
)
from .score_helpers import score_band

# Delta above which a raw (generator self-issued) market_fit score is reported as
# "self-score corrected down" — mirrors the calibration-gap notability bar used elsewhere
# (utils/niche_difficulty.py CALIB_GAP_NOTABLE).
_SELF_SCORE_CORRECTION_DELTA = 0.15
_FINGERPRINT_VERSION = 1


class _PortfolioSummary(BaseModel):
    summary: str = Field(
        "", description="2-4 short paragraphs, plain text (no markdown), honest reviewer tone"
    )


def idea_portfolio_fingerprint(ideas: list, *, job_id: str | None = None) -> str | None:
    """Canonical identity of the visible candidate set.

    The order in which candidates happen to be rendered is irrelevant. Revisions are
    material: changing an existing candidate invalidates guidance just like adding or
    removing one. During initial Stage 5, identities have not yet been stamped onto the
    models, so ``job_id`` lets us derive the exact Phase-1 identities the worker stamps
    before publishing the pool. A caller without either persisted ids or ``job_id`` gets
    ``None`` and must fail closed.
    """
    from ..models.solution_idea import visible_ideas
    from .idea_identity import deterministic_idea_id

    raw = list(ideas or [])
    visible_object_ids = {id(idea) for idea in visible_ideas(raw)}
    refs: list[tuple[str, int]] = []
    for index, idea in enumerate(raw):
        if id(idea) not in visible_object_ids:
            continue
        if isinstance(idea, dict):
            idea_id = idea.get("idea_id")
            revision = idea.get("idea_revision", 1)
        else:
            idea_id = getattr(idea, "idea_id", None)
            revision = getattr(idea, "idea_revision", 1)
        idea_id = str(idea_id or "").strip()
        if not idea_id:
            if not job_id:
                return None
            idea_id = deterministic_idea_id(job_id, "phase1", "initial", index)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            return None
        refs.append((idea_id, revision))

    refs.sort()
    return json.dumps(
        {"version": _FINGERPRINT_VERSION, "ideas": refs},
        separators=(",", ":"),
    )


def _name_head(name: str) -> str:
    """Coverage matches on the name's head — long names carry subtitle tails
    ("ShipDelayRadar Ops (Risk-Aware Pick/Pack + ...)", "ClosePack Recon: ...")
    that models rightly shorten in prose; demanding the full string drops
    otherwise-valid summaries (live-caught on the Etsy run, 2026-07-10)."""
    head = re.split(r"[(:]", name, maxsplit=1)[0].strip()
    return head if len(head) >= 4 else name


# Exclusion vocabulary the guard scans for — describing a RANKED, SELECTABLE idea with
# any of these is state misinformation (the workbench renders it with an enabled
# selection control). Genuinely ruled-out ideas are not in the visible-name list and
# stay describable however the model likes.
_EXCLUSION_TERMS = {"excluded", "removed", "eliminated", "dropped", "cut"}
_CLAUSE_SPLIT_RE = re.compile(r"[.;\n]+")
_WORD_RE = re.compile(r"[a-z0-9']+")
_EXCLUSION_PROXIMITY = 8  # lexical tokens; catches the live "were ultimately excluded" span


def _exclusion_conflicts(text: str, names: list[str]) -> list[str]:
    """Visible ideas the summary describes with exclusion vocabulary — clause-scoped,
    whole-word, within `_EXCLUSION_PROXIMITY` lexical tokens of the idea's name head.
    Clause scoping lets "We excluded pricing data. X remains selectable." pass."""
    conflicts: list[str] = []
    for clause in _CLAUSE_SPLIT_RE.split(text.lower()):
        words = _WORD_RE.findall(clause)
        if not words:
            continue
        term_positions = [i for i, w in enumerate(words) if w in _EXCLUSION_TERMS]
        if not term_positions:
            continue
        for name in names:
            head_words = _WORD_RE.findall(_name_head(name).lower())
            if not head_words:
                continue
            for i in range(len(words) - len(head_words) + 1):
                if words[i : i + len(head_words)] == head_words:
                    span = range(i, i + len(head_words))
                    if any(min(abs(t - h) for h in span) <= _EXCLUSION_PROXIMITY
                           for t in term_positions):
                        if name not in conflicts:
                            conflicts.append(name)
                    break
    return conflicts


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
    elif rt_verdict == "killed":
        # "killed" is a NOMINATION verdict, not a visibility state — the bare word
        # invited the model to describe still-listed ideas as "excluded" (live-caught
        # on the landlord run: two killed-but-selectable ideas narrated as removed).
        first = f" ({rt_caveats[0]})" if rt_caveats else ""
        rt_clause = (f"; red-team verdict: killed for nomination only{first}; "
                     "remains ranked and selectable; resolve the caveat before choosing")
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


# D1 round 14: the monetisation LICENSE is withdrawn from the analyst prose, so the guidance has
# to come from somewhere that cannot contradict the wallet evidence. It comes from here — one
# deterministic line per wallet reading — plus each idea's own `pricing_shape_note`, which the
# idea detail already renders. Nothing about how the product makes money is left to free prose.
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
    lines.append(
        "\nMONETIZATION GUIDANCE (this run's deterministic niche-level line, derived from the "
        "wallet evidence above; it is persisted on the Research Reality Check verdict as "
        "`monetization_guidance` — this is CONTEXT for you, not something to restate, re-derive, "
        "second-guess or override): "
        + monetization_guidance(wallet)
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
    insensitive substring match), visible ideas cannot be described as excluded, and verified
    paying-wallet copy must include the shared deterministic positive statement. Retry once with
    an explicit correction, else give up and return None (no JSON-repair, no partial summary).
    `usage` reflects only the LAST attempt made (the common case is a single call; the retry path
    is a rare edge case and is not cost-tracked twice)."""
    from ..config.settings import settings
    from ..models.solution_idea import visible_ideas
    from .llm_service import LLMService

    visible = visible_ideas(ideas)
    names = [(getattr(i, "solution_name", "") or "").strip() for i in visible]
    names = [n for n in names if n]
    if not names:
        return None, None

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

    wallet = dict(niche_wallet_brief or {})
    commercial_contract_copy = paying_wallet_commercial_contract_copy(
        wallet.get("wallet_class"), wallet.get("evidence")
    )

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
        "reasoned from the evidence above only, no new facts. NEVER nominate an idea whose "
        "red-team verdict is 'killed' for that step. A killed idea under VISIBLE IDEAS "
        "remains ranked and selectable: say that the adversarial review refuted its core "
        "premise and that the caveat must be resolved before choosing it. NEVER describe "
        "any idea under VISIBLE IDEAS as excluded, removed, eliminated, dropped, or cut. "
        "If every idea was killed, say plainly that none of them is ready for nomination "
        "and name the caveat that has to be resolved first."
        # D1 round 14. Six filters on the OUTPUT hit a ceiling — a blind critic published 13 of
        # 14 novel non-paying commercial shapes past the last one — because there is no closed
        # structural property in surface text that separates "recommends a shape where nobody
        # pays" from every other sentence. So the license is withdrawn instead: a contradiction
        # the generator was never allowed to state cannot arise in any register.
        " OUT OF YOUR REMIT — HOW THE PRODUCT MAKES MONEY. Choosing or ruling out a commercial "
        "shape (subscription, one-time, free, freemium, ad/sponsor/lead-gen funded, licensed, "
        "revenue-share, member-funded, employer- or insurer-paid, or anything else) is not your "
        "job. The MONETIZATION GUIDANCE line above is written deterministically from the wallet "
        "evidence and is carried to the reader on the Research Reality Check verdict, and each "
        "idea carries its own pricing note; a second opinion written "
        "here can only contradict them. You MAY REPORT a market fact you were given — "
        "'incumbents bundle this free', 'buyers here already pay', 'the discussions show no "
        "purchase intent'. Reporting is not prescribing. You MUST NOT recommend, select, rule "
        "out, or pivot toward or away from any way of charging for the product — not in the "
        "imperative, not as advice, not as 'the path forward', not as a question, not hedged, "
        "not attributed to the market. If a sentence answers 'how should this make money?', "
        "delete it. Which idea to validate, and why, is still entirely yours."
    )
    if commercial_contract_copy:
        base_prompt += (
            " COMMERCIAL COPY CONTRACT: one wallet sentence has already been written for you "
            "from the verified evidence — it is not your judgement and is not the exception to "
            "the remit rule above. Include it verbatim exactly once: "
            f"\"{commercial_contract_copy}\" This must be the summary's only wallet, pricing, "
            "subscription, billing, free/paid, or monetization claim."
        )

    usage = None
    summary: Optional[str] = None
    missing: list[str] = names
    conflicts: list[str] = []
    commercial_violations: list[str] = []
    for attempt in range(2):  # one grounded call + at most one combined re-prompt
        prompt = base_prompt
        if attempt == 1:
            if missing:
                prompt += (
                    "\n\nYOUR PREVIOUS ATTEMPT DID NOT MENTION: "
                    f"{', '.join(missing)}. Rewrite the summary so every idea listed under "
                    "VISIBLE IDEAS is named at least once."
                )
            if conflicts:
                prompt += (
                    "\n\nYOUR PREVIOUS ATTEMPT MISSTATED THE VISIBILITY OF: "
                    f"{', '.join(conflicts)}. These ideas remain ranked and selectable "
                    "under VISIBLE IDEAS. Rewrite without describing any VISIBLE IDEA as "
                    "excluded, removed, eliminated, dropped, or cut; keep the "
                    "never-nominate rule for killed ideas."
                )
            if commercial_violations and commercial_contract_copy:
                prompt += (
                    "\n\nYOUR PREVIOUS ATTEMPT VIOLATED THE PAYING-WALLET COMMERCIAL COPY "
                    "CONTRACT. Verified priced evidence shows buyers already pay for tooling. "
                    "Remove every other wallet, pricing, subscription, billing, free/paid, or "
                    "monetization claim and include this sentence verbatim exactly once: "
                    f"\"{commercial_contract_copy}\""
                )
            elif commercial_violations:
                prompt += (
                    "\n\nYOUR PREVIOUS ATTEMPT RECOMMENDED A COMMERCIAL SHAPE. That is out of "
                    "your remit entirely — not just the shape you happened to name, and this "
                    "niche's own probe evidence quotes real prices. Rewrite with every sentence "
                    "about how the product should be priced or funded deleted, keeping the rest "
                    "of your analysis intact."
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
        conflicts = _exclusion_conflicts(text, names) if text else []
        if not text:
            commercial_violations = []
        elif commercial_contract_copy:
            commercial_violations = paying_wallet_summary_copy_violations(
                text,
                wallet_class=wallet.get("wallet_class"),
                wallet_evidence=wallet.get("evidence"),
                expected_copy=commercial_contract_copy,
                allow_surrounding_copy=True,
            )
        else:
            # Scope gap closed in round 14: a `mixed` wallet whose probe quoted "$116-$565/mo"
            # had no contract at all, and shipped the identical contradiction. The backstop
            # alone applies there — see priced_wallet_prescription_violations.
            commercial_violations = priced_wallet_prescription_violations(
                text,
                wallet_class=wallet.get("wallet_class"),
                wallet_evidence=wallet.get("evidence"),
            )
        if commercial_violations:
            logger.warning(
                f"[PortfolioSummary] attempt {attempt + 1} paying-wallet commercial "
                f"invariant rejected summary: {commercial_violations}."
            )
        if text and not missing and not conflicts and not commercial_violations:
            summary = text
            break
        logger.info(
            f"[PortfolioSummary] attempt {attempt + 1} missing names: {missing}"
            + (f"; exclusion conflicts: {conflicts}" if conflicts else "")
            + (f"; commercial violations: {commercial_violations}"
               if commercial_violations else "")
        )
        missing = missing or ([] if conflicts or commercial_violations else names)

    if summary is None:
        logger.warning(
            "[PortfolioSummary] failed name-coverage/exclusion/commercial guardrail after "
            "retry; dropping summary."
        )
    return summary, usage
