"""Run-level idea-portfolio summary grounded in the current visible candidate records.

The summary used to ask a prose model to infer candidate strengths from a score-only
digest. That made candidate-specific mechanism claims impossible to verify: the model
could fluently attach an unrelated workflow to the right candidate name. The current
summary is therefore extractive and deterministic. Product and mechanism statements are
copied from the candidate record; ranking language is derived from recorded score bands.
If either fact is unavailable, the summary fails closed instead of inventing a bridge.
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


def _idea_display_title(idea) -> str:
    """Mirror the frontend/backend display-title contract."""
    name = (getattr(idea, "solution_name", None) or "").strip()
    headline = (getattr(idea, "headline", None) or "").strip()
    if (
        getattr(idea, "source_frame", None) == "user_seed"
        and getattr(idea, "generation_operation_id", None) == "validate"
    ):
        return name or headline
    return headline or name


def _name_head(name: str) -> str:
    head = re.split(r"[(:]", name, maxsplit=1)[0].strip()
    return head if len(head) >= 4 else name


_EXCLUSION_TERMS = {"excluded", "removed", "eliminated", "dropped", "cut"}
_CLAUSE_SPLIT_RE = re.compile(r"[.;\n]+")
_WORD_RE = re.compile(r"[a-z0-9']+")
_EXCLUSION_PROXIMITY = 8


def _exclusion_conflicts(text: str, names: list[str]) -> list[str]:
    conflicts: list[str] = []
    for clause in _CLAUSE_SPLIT_RE.split(text.lower()):
        words = _WORD_RE.findall(clause)
        term_positions = [i for i, word in enumerate(words) if word in _EXCLUSION_TERMS]
        for name in names:
            head_words = _WORD_RE.findall(_name_head(name).lower())
            for i in range(len(words) - len(head_words) + 1):
                if words[i : i + len(head_words)] != head_words:
                    continue
                span = range(i, i + len(head_words))
                if term_positions and any(
                    min(abs(term - position) for position in span) <= _EXCLUSION_PROXIMITY
                    for term in term_positions
                ) and name not in conflicts:
                    conflicts.append(name)
                break
    return conflicts


def _grounded_candidate_sentence(idea) -> str | None:
    """Render only facts present on the current typed candidate record."""
    title = _idea_display_title(idea)
    product = (
        (getattr(idea, "short_description", None) or "").strip()
        or (getattr(idea, "description", None) or "").strip()
    )
    technical = (getattr(idea, "technical_approach", None) or "").strip()
    features = [str(value).strip() for value in (getattr(idea, "core_features", None) or [])]
    mechanism = technical or "; ".join(value for value in features if value)
    if not title or not product or not mechanism:
        return None

    codename = (getattr(idea, "solution_name", None) or "").strip()
    if codename and codename != title:
        product = product.replace(codename, title)
        mechanism = mechanism.replace(codename, title)

    market_fit = score_band(getattr(idea, "market_fit_score", None))
    dev_time = (getattr(idea, "estimated_development_time", None) or "").strip()
    build_clause = f" Estimated MVP build: {dev_time}." if dev_time else ""
    return (
        f"{title}: {product} Recorded mechanism: {mechanism}. "
        f"Recorded market fit is {market_fit}.{build_clause}"
    )


def _grounded_portfolio_summary(
    ideas: list,
    *,
    niche_wallet_brief: Optional[dict],
) -> str | None:
    """Production summary contract: extract current facts or publish nothing."""
    sentences = [_grounded_candidate_sentence(idea) for idea in ideas]
    if not sentences or any(sentence is None for sentence in sentences):
        return None

    eligible = [
        idea for idea in ideas
        if (getattr(idea, "red_team_verdict", None) or "").strip() != "killed"
    ]
    eligible.sort(
        key=lambda idea: (
            getattr(idea, "market_fit_score", None)
            if isinstance(getattr(idea, "market_fit_score", None), (int, float))
            else -1
        ),
        reverse=True,
    )
    recommendation = ""
    if eligible:
        title = _idea_display_title(eligible[0])
        recommendation = (
            f" Based on the recorded market-fit bands, validate {title} first; "
            "the candidate-specific mechanism above is copied from its current record."
        )

    wallet = dict(niche_wallet_brief or {})
    commercial_contract_copy = paying_wallet_commercial_contract_copy(
        wallet.get("wallet_class"), wallet.get("evidence")
    )
    parts = ["Grounded candidate review:", *sentences]
    if recommendation:
        parts.append(recommendation.strip())
    if commercial_contract_copy:
        parts.append(commercial_contract_copy)
    summary = "\n\n".join(str(part) for part in parts)

    violations = (
        paying_wallet_summary_copy_violations(
            summary,
            wallet_class=wallet.get("wallet_class"),
            wallet_evidence=wallet.get("evidence"),
            expected_copy=commercial_contract_copy,
            allow_surrounding_copy=True,
        )
        if commercial_contract_copy
        else priced_wallet_prescription_violations(
            summary,
            wallet_class=wallet.get("wallet_class"),
            wallet_evidence=wallet.get("evidence"),
        )
    )
    if violations:
        logger.warning(
            f"[PortfolioSummary] deterministic commercial invariant rejected summary: {violations}"
        )
        return None
    return summary


def _idea_digest_line(idea) -> str:
    """One deterministic, words-only digest line for a single visible idea. Everything
    quantitative is rendered as a qualitative band (score_band), never a raw decimal — the
    prompt built from these lines must not give the LLM a number to echo. Deliberately
    excludes source_frame (internal generation steer, not yet user-facing)."""
    name = _idea_display_title(idea) or "?"
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

    product = (
        (getattr(idea, "short_description", None) or "").strip()
        or (getattr(idea, "description", None) or "").strip()
    )
    technical = (getattr(idea, "technical_approach", None) or "").strip()
    features = [str(value).strip() for value in (getattr(idea, "core_features", None) or [])]
    features = [value for value in features if value]
    mechanism = technical or "; ".join(features)

    return (
        f"- {name}: product fact: {product or 'not recorded'}; "
        f"mechanism fact: {mechanism or 'not recorded'}; "
        f"market fit {mf_band}{corrected}; SEO scalability {seo_band}; "
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
    """Generate a current-record-grounded portfolio summary for production candidates.

    ResearchFlow stores Pydantic candidate models; that path is deterministic and cannot
    author candidate claims absent from those records. Lightweight non-model inputs retain
    the legacy guarded generator for backwards-compatible library callers. They are never
    checkpointed or published by ResearchFlow.
    """
    from ..config.settings import settings
    from ..models.solution_idea import visible_ideas
    from .llm_service import LLMService

    visible = visible_ideas(ideas)
    names = [_idea_display_title(idea) for idea in visible]
    names = [n for n in names if n]
    if not names:
        return None, None

    if all(callable(getattr(idea, "model_dump", None)) for idea in visible):
        grounded = _grounded_portfolio_summary(
            visible,
            niche_wallet_brief=niche_wallet_brief,
        )
        if grounded is None:
            logger.warning(
                "[PortfolioSummary] current candidate facts were incomplete or violated "
                "the commercial-copy invariant; dropping summary without an LLM retry"
            )
        return grounded, None

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
