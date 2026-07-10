"""Part 1 v4 — decouple creative refinement from data-route VERIFICATION.

v1–v3 all failed the same way: the loop scored data_feasibility INSIDE the dialog, so the ideator
confabulated official APIs that don't exist (StubHub/HLTV/Stratz-for-CS2) and the reviewer rewarded
the confident lie. The research is unanimous on the fix (uncertainty-based abstention; decouple
generation from verification; Chain-of-Verification): don't make the generator assert facts it can't
verify — have it FLAG uncertainty, and resolve facts in a SEPARATE, tool-grounded step.

So v4:
  1. The loop reviewer scores ONLY the soft dimensions it can actually judge — market_fit, novelty,
     clarity. data/technical feasibility are REMOVED from the loop (no confabulation pressure).
  2. The ideator is told to FLAG any uncertain data route as `[NEEDS-VERIFY: <question>]` and NEVER
     assert an API can do something it's unsure of (honest flags rewarded, confident guesses not).
  3. A SEPARATE post-loop verification stage searches each data claim and resolves it
     (official / unofficial / blocked) — the loop never touches this.
  4. The deterministic `_validate_idea_scores` backstop (already shipped) then caps market_fit on any
     route that came back unverified.

Reuses the v3 module's grounding + idea-rendering + field-carry helpers; only the critique schema,
the two system prompts, and the verification stage are new.
"""
from __future__ import annotations

import re

from loguru import logger
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..models.solution_idea import BaseSolutionIdea
from ..utils.llm_service import LLMService
from ..utils.public_data_sources import (
    llm_confirm_known_route, match_known_public_source, retrieve_known_sources,
)
from .idea_improvement_loop import (
    CellGrounding, _carry_forward_fields, _idea_to_text, _ONPAIN_SLACK,
)

_DEFAULT_ROUNDS = 2
_HARD_CAP = 3
_QUALITY_BAR = 0.72
# Soft-only composite: no data/technical feasibility (those are verified, not judged-in-the-loop).
_WEIGHTS = {"market_fit": 0.45, "novelty": 0.30, "clarity": 0.25}
# P1b: angle-aware loop weights (behind enable_direction_aware_eval) — a distribution_seo idea is
# optimized on its SEO SURFACE (structural page-corpus), not novelty; a novel idea on novelty. Mirrors
# the ranking/verdict _ANGLE_WEIGHTS intent. seo_surface enters ONLY on these angle paths.
_ANGLE_LOOP_WEIGHTS = {
    "distribution_seo":      {"market_fit": 0.35, "seo_surface": 0.40, "novelty": 0.10, "clarity": 0.15},
    "novel_differentiation": {"market_fit": 0.35, "novelty": 0.40, "seo_surface": 0.10, "clarity": 0.15},
}
_VERIFY_RE = re.compile(r"\[NEEDS[-\s]?VERIFY:\s*([^\]]+)\]", re.I)


def _relocate_needs_verify_flags(idea) -> None:
    """Defense-in-depth: the ideator prompt directs [NEEDS-VERIFY: ...] flags to data_acquisition_notes
    only, but LLMs sometimes drop them into the data_sources list. Strip any flagged items from
    data_sources (which must stay clean source NAMES) and append the flags to data_acquisition_notes so
    the verifier still sees them. Idempotent. Runs after each ideator turn (so the echoed spec in the
    thread never teaches the LLM that data_sources is where flags belong) and at verify_data_routes
    entry (so no contaminated list can ever reach the search-query builder)."""
    sources = getattr(idea, "data_sources", None)
    if not sources:
        return
    clean: list[str] = []
    found: list[str] = []
    for s in sources:
        flags = _VERIFY_RE.findall(str(s))
        if flags:
            found.extend(flags)
        else:
            clean.append(s)
    if not found:
        return
    idea.data_sources = clean or None
    note = (getattr(idea, "data_acquisition_notes", "") or "").strip()
    for f in found:
        tag = f"[NEEDS-VERIFY: {f.strip()}]"
        if tag.lower() not in note.lower():
            note = (note + " " + tag).strip() if note else tag
    idea.data_acquisition_notes = note


class IdeaCritiqueV4(BaseModel):
    """One reviewer turn — SOFT dimensions only (no data/API judgement; that's verified separately)."""
    market_fit: float = Field(..., ge=0, le=1, description="Does it solve the SOURCE pain for the TARGET audience?")
    novelty: float = Field(..., ge=0, le=1, description="Non-obvious vs the named competitors / generic tools?")
    clarity: float = Field(..., ge=0, le=1, description="Coherent, specific, complete spec (penalize vagueness/empty fields)?")
    # P1b: STRUCTURAL SEO surface only — does the idea SHAPE yield an enumerable corpus of many indexable
    # pages? Judge the shape, NEVER search demand/volume (the loop has no keyword data). Default 0.5 so the
    # legacy/flag-off path (reviewer not asked for it) is unaffected.
    seo_surface: float = Field(0.5, ge=0, le=1, description="Structural: does the idea shape yield an enumerable corpus of many indexable pages? SHAPE only, NOT search demand/volume.")
    binding_constraint: str = Field(..., description="The ONE lowest, most-actionable dimension")
    directive: str = Field(..., description="A specific, actionable fix for the binding constraint — staying ON the source pain")
    meets_bar: bool = Field(..., description="True only if strong on all scored dimensions")
    rationale: str = Field("", description="≤200 chars grounding the call")

    def composite(self, angle: str | None = None) -> float:
        w = _ANGLE_LOOP_WEIGHTS.get(angle or "") if settings.enable_direction_aware_eval else None
        w = w or _WEIGHTS
        return round(sum(wt * getattr(self, k) for k, wt in w.items()), 4)


class DataRouteVerdict(BaseModel):
    """Separate, tool-grounded resolution of ONE data claim (never judged inside the loop).

    Three-way, evidence-symmetric (SAFE / decompose-then-verify): the search evidence either
    CONFIRMS a public route, CONTRADICTS it, or is insufficient — the last ABSTAINS rather than
    blocking, so poor search recall can never mis-classify a real public API as unobtainable."""
    self_sourced: bool = Field(
        ...,
        description=(
            "True if the product needs NO external feed — it computes from static formulas, uses "
            "publicly downloadable datasets, user-entered values, or first-party submissions."
        ),
    )
    verdict: str = Field(
        "not_enough_info",
        description=(
            "one of: 'supported' (evidence shows a real, accessible public/official route), "
            "'refuted' (evidence shows it's removed / gated / paywalled / nonexistent), or "
            "'not_enough_info' (evidence neither confirms nor refutes)."
        ),
    )
    access_model: str = Field(
        "",
        description="when verdict='supported': 'official' (documented public/free) or 'unofficial' (only scraping / ToS-gray).",
    )
    obtainable: bool = Field(True, description="convenience flag; false only when verdict='refuted'.")
    note: str = Field("", description="≤160 chars CITING the specific search evidence for the verdict")


def _soft_invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
    creative = output_model is not BaseSolutionIdea
    return LLMService.invoke_structured(
        messages=messages, output_model=output_model, temperature=temperature,
        model_name=model_name, reasoning_effort=reasoning_effort, creative=creative)


def _angle_directive(g: CellGrounding) -> str:
    """P1b: angle-specific mentor guidance so the loop optimizes the direction's winning axis."""
    if not (settings.enable_direction_aware_eval and g.winning_angle):
        return ""
    if g.winning_angle == "distribution_seo":
        return (
            "\nDIRECTION = DISTRIBUTION_SEO — this idea WINS on SEO distribution, NOT mechanism novelty.\n"
            "• ALSO score `seo_surface` 0-1: does the idea SHAPE yield an enumerable corpus of MANY indexable "
            "pages (one per entity / comparison / location / question)? Judge the SHAPE ONLY — you have no "
            "keyword data, so NEVER assume or claim search volume/demand.\n"
            "• Do NOT penalize the idea for being an 'obvious' shape — an obvious directory/comparison/"
            "benchmark shape is the CORRECT form here; low novelty is EXPECTED, not a flaw.\n"
            "• Prioritize `seo_surface` and `market_fit` as the binding_constraint; push the ideator toward a "
            "richer, more enumerable page corpus and a sharper wedge into the pain — NOT a novel mechanism.\n"
        )
    if g.winning_angle == "novel_differentiation":
        return (
            "\nDIRECTION = NOVEL_DIFFERENTIATION — this idea WINS on a genuine, non-obvious mechanism.\n"
            "• Prioritize `novelty` and `market_fit` as the binding_constraint; push toward a sharper, "
            "non-obvious mechanism. (Score `seo_surface` too, but it is secondary for this direction.)\n"
        )
    return ""


def _frame_directive(g: CellGrounding) -> str:
    """Multi-Frame Idea Generation Portfolio (2026-07-10): a non-pain cell has no single SOURCE
    PAIN — it is seeded from a typed FOCUS (gap/data-asset/workflow) and anchored
    to a VALIDATED set of pains at mint time (`anchor_pains_for_frame_focus`). Two-clause
    market_fit lock so the reviewer doesn't score honest frame ideation as pain drift: (a) does
    it fit the frame's own FOCUS, (b) does it serve one of the listed ANCHOR PAINS. '' for a pain
    cell (frame_type '' or 'pain') — byte-identical to before."""
    if not g.frame_type or g.frame_type == "pain":
        return ""
    from ..utils.frames import FRAME_REGISTRY
    spec = FRAME_REGISTRY.get(g.frame_type)
    mf_anchor = spec.mf_anchor if spec is not None else "does it fit the FOCUS below"
    return (
        f"\nPRODUCT FRAME = {g.frame_type.upper()} — this idea is seeded from THE FOCUS below, "
        "NOT a single source pain. Score market_fit on TWO clauses together: (a) "
        f"{mf_anchor}; (b) it must serve at least one of THE ANCHOR PAINS listed (exact titles). "
        "An idea that fails EITHER clause scores market_fit ≤ 0.3, however clever.\n"
    )


def _reviewer_system(g: CellGrounding) -> dict:
    return {"role": "system", "content": (
        _frame_directive(g) +
        _angle_directive(g) +
        "You are a CREATIVE PRODUCT MENTOR for a solo developer — not a grader. Your job is to GUIDE the "
        "ideator toward a sharper, more ORIGINAL, genuinely BUILDABLE product that nails the source pain "
        "below. Every turn you give ONE concrete creative direction that moves the idea forward, plus "
        "scores so we can track progress.\n\n"
        "Score three dimensions 0-1 (for tracking):\n"
        "• market_fit — does it solve THE SOURCE PAIN BELOW for THIS audience? A drift to a DIFFERENT "
        "problem scores ≤ 0.3, however clever.\n"
        "• novelty — a genuinely non-obvious angle/mechanism vs the named competitors (not relabeling).\n"
        "• clarity — coherent, specific, complete spec.\n\n"
        "Then give the GUIDANCE (the part that matters most) as `directive`: a SPECIFIC, imaginative next "
        "move — a sharper mechanism, an unexpected recombination, a clever data angle, a tighter wedge "
        "into the pain. Push for creativity AND doability together.\n"
        "HARD RULES for your guidance:\n"
        "  – Stay ON the source pain and KEEP the idea's working core. Creativity means a sharper, smaller, "
        "    more surprising idea — NOT bolting on more features, platforms, or 'pro/enterprise' scope "
        "    (scope-inflation is a failure, not progress).\n"
        "  – Steer toward data a solo dev can actually get (public datasets, official APIs, first-party / "
        "    user-submitted data, computed/static values). You do NOT verify specific APIs — that's done "
        "    separately — but you DO push the ideator away from data that obviously can't be obtained and "
        "    toward an angle that needs only gettable data. Treat `[NEEDS-VERIFY: ...]` tags as honest, not "
        "    a flaw.\n"
        "  – Name the single binding_constraint (lowest dimension) so the ideator knows the priority.\n"
        "meets_bar=true only when it's original, clearly on-pain, AND plausibly buildable on gettable data.\n\n"
        "==== GROUNDED EVIDENCE ====\n" + g.as_block()
    )}


def _ideator_system(g: CellGrounding) -> dict:
    return {"role": "system", "content": (
        "You are a sharp, imaginative SaaS ideator for a solo developer, working WITH a creative mentor. "
        "Design ONE product that solves the source pain below, then evolve it each turn by taking the "
        "mentor's creative direction and running with it. HARD RULES:\n"
        "(1) Keep solving the SAME source pain, and KEEP the idea's working core — evolve it into something "
        "sharper and more original, don't pivot to a different problem and don't 'professionalize' it by "
        "piling on features/platforms/enterprise scope. A smaller, more surprising idea beats a bigger one.\n"
        "(2) DATA HONESTY: you are NOT rewarded for naming an official API. Prefer angles that need only "
        "gettable data (public datasets, official APIs, first-party / user-submitted data, computed/static "
        "values). For ANY data route you are not CERTAIN a public/official source exposes, write the flag "
        "`[NEEDS-VERIFY: does <source> expose <exactly what you need>?]` ONLY inside `data_acquisition_notes` "
        "— NEVER inside the `data_sources` list, which must hold clean source NAMES only (e.g. 'Reddit API', "
        "'SEC EDGAR'). Never assert an API can do something you're unsure of (a separate tool checks these; "
        "a refuted guess gets capped).\n"
        "(3) Return a COMPLETE spec every time — every field filled, none blank or duplicated. "
        "CRITICAL: headline, short_description, value_proposition, why_it_works, and innovation_angle "
        "must DESCRIBE THE SAME IDEA as description and data_sources. If you change the mechanism, data "
        "route, or product name, REWRITE all of those surface fields to match — never keep the old "
        "pitch. A spec whose description says one thing and headline says another is wrong.\n"
        "Act on the mentor's binding_constraint + direction without weakening the other dimensions.\n\n"
        "==== THE PAIN & AUDIENCE YOU SERVE ====\n" + g.as_block()
    )}


def _review(idea, thread, *, invoke, model, effort):
    thread.append({"role": "user", "content":
        "Review on the scored dimensions. Name the binding constraint + one directive.\n\n"
        + _idea_to_text(idea)})
    crit, usage = invoke(thread, IdeaCritiqueV4, temperature=0.2, model_name=model, reasoning_effort=effort)
    thread.append({"role": "assistant", "content":
        f"mf={crit.market_fit} nov={crit.novelty} clarity={crit.clarity}; "
        f"binding={crit.binding_constraint}; directive={crit.directive}"})
    return crit, usage


def _improve(crit, thread, prior, *, invoke, model, effort):
    thread.append({"role": "user", "content":
        f"Reviewer feedback. Binding constraint: {crit.binding_constraint}. Directive: {crit.directive}. "
        "Fix THAT without weakening the others or pivoting off the source pain. Remember the DATA HONESTY "
        "rule: flag uncertain routes with [NEEDS-VERIFY: ...] ONLY in `data_acquisition_notes` (never in "
        "the `data_sources` list — that holds clean source names only), don't assert. Return the COMPLETE "
        "spec — "
        "if the mechanism, data route, or name changed, rewrite headline, short_description, "
        "value_proposition, why_it_works, innovation_angle, technical_approach, and "
        "differentiation_factors so they describe the revised idea, not the old one."})
    idea, usage = invoke(thread, BaseSolutionIdea, temperature=0.5, model_name=model, reasoning_effort=effort)
    _relocate_needs_verify_flags(idea)
    _carry_forward_fields(idea, prior)
    thread.append({"role": "assistant", "content": _idea_to_text(idea)})
    return idea, usage


def _canonicalize_route(access_model: str, obtainable: bool) -> str:
    """Fold the v4 verifier's vocab (`official|unofficial|blocked`) onto the critic / `DataAccessTag`
    vocab the rest of the pipeline keys on. `official` is not a recognized `DataAccessTag` (it shows
    no chip and no downstream cap matches it) → map to `public` when obtainable, else `blocked` so a
    confused `official + obtainable=false` keeps the cap."""
    am = (access_model or "").strip().lower()
    if am == "official":
        return "public" if obtainable else "blocked"
    return am or "blocked"


# A no-op web search: no Google query can confirm/refute these — they're the verdict's
# `self_sourced` axis, which the LLM judge already reasons about from the claim text.
_NON_WEB_HINTS = (
    "user input", "user-provided", "user provided", "manual entry", "internal", "proprietary",
    "static values", "crowdsourced", "self-reported", "self reported",
)


def _is_non_web_source(item: str) -> bool:
    low = (item or "").lower()
    return any(h in low for h in _NON_WEB_HINTS)


def verify_data_routes(idea, grounding, *, search, invoke, model_name=None, reasoning_effort="medium") -> DataRouteVerdict | None:
    """SEPARATE tool-grounded check (Chain-of-Verification): pull the idea's data claims (+ any
    NEEDS-VERIFY flags), search them, and resolve obtainability. Sets idea.data_access_model (canonical
    vocab) + reconciles data_acquisition_notes so label and notes agree. Fail-soft → None."""
    model_name = model_name or settings.pain_point_validation_llm
    _relocate_needs_verify_flags(idea)  # guarantee data_sources is clean before building any query
    sources = ", ".join(getattr(idea, "data_sources", None) or [])
    flags = _VERIFY_RE.findall(
        f"{getattr(idea,'technical_approach','') or ''} {getattr(idea,'description','') or ''} "
        f"{getattr(idea,'data_acquisition_notes','') or ''}")
    claim = "; ".join(flags) or sources
    if not claim:
        return None

    prior = (getattr(idea, "data_access_model", None) or "").strip().lower()

    # Well-known-source pass (2026-07-03): canonically famous free sources were getting
    # misclassified by sparse search snippets (observed live: GitHub API -> 'restricted',
    # SAM.gov -> 'paywalled'). Two steps: deterministic RETRIEVAL (every claimed part must
    # match a known public source; parts are the ORIGINAL list items / flags — never a
    # re-split of the joined string) then an LLM CONFIRM over the retrieved entries (a name
    # hit alone is too broad). Reject/error at either step falls through to the web verifier.
    matches = retrieve_known_sources(flags or getattr(idea, "data_sources", None))
    names = llm_confirm_known_route(matches, context=claim[:400]) if matches else None
    if names:
        idea.data_access_model = "public"
        if prior != "public":
            idea.data_acquisition_notes = f"Known public data source: {names} (allowlist-verified)"[:160]
        logger.info(f"[v4-verify] '{getattr(idea, 'solution_name', '?')}' route -> public "
                    f"(well-known source: {names}; LLM-confirmed, web search skipped)")
        return DataRouteVerdict(self_sourced=False, verdict="supported", access_model="official",
                                obtainable=True, note=f"Well-known public source: {names}")

    # Targeted retrieval (SAFE-style): a generic availability query, then ONE query per web source
    # item (not a combined blob). Live case (2026-07-09): a single 6-source combined query buried
    # EPA RSL among 6 named items and returned 9 EPA hits, 1 USDA, 0 for the other 4 — the verdict
    # LLM then judged those 4 sources on silence. Per-item queries give each source a fair shot.
    # `claim` is either the NEEDS-VERIFY questions (when flags exist) or the clean sources — never
    # both, so the query is never a duplicated/polluted string shipped to the search API.
    original_items = list(getattr(idea, "data_sources", None) or [])
    web_items = [s for s in original_items if not _is_non_web_source(s)]
    queries = [f"{claim} data availability access".strip()] if flags else []
    # skip items the allowlist pre-pass already recognizes — no need to spend a query on them.
    unmatched_web_items = [s for s in web_items if not match_known_public_source(s)]
    for item in unmatched_web_items[:3]:
        queries.append(f"{item[:80]} public API documentation dataset access".strip())
    snippets = ""
    if search is not None:
        for q in queries:
            try:
                snippets += (search(q) or "")[:1200] + "\n"
            except Exception as e:
                logger.warning(f"[v4-verify] search failed: {str(e)[:80]}")
    snippets = snippets.strip()[:6000]
    prompt = (
        "You verify whether a SOLO DEVELOPER can actually obtain the data this product needs. Decide "
        "from the web-search evidence below — do NOT assume an API you don't recognize exists just "
        "because the idea names it (that is how fabricated APIs slip through), and do NOT treat thin "
        "evidence as proof of absence.\n\n"
        f"DATA THE PRODUCT NEEDS: {claim}\nNAMED SOURCES: {sources or 'n/a'}\n\n"
        f"WEB-SEARCH EVIDENCE:\n{snippets or '(no evidence retrieved)'}\n\n"
        "STEP 1 — Does the product even depend on a specific EXTERNAL API/feed? If NOT (it computes from "
        "static formulas, publicly downloadable datasets, user-entered values, or first-party "
        "submissions), set self_sourced=true and verdict='supported'. Never penalize an idea that needs "
        "no external API.\n"
        "STEP 2 — If it DOES depend on an external source (self_sourced=false), return a THREE-WAY "
        "verdict, grounded in the evidence and CITED in `note`:\n"
        "- 'supported': the evidence shows a real, documented, publicly or officially accessible route "
        "that exposes what's needed. Set access_model='official', or 'unofficial' if the only route is "
        "scraping / ToS-gray / undocumented.\n"
        "- 'refuted': the evidence POSITIVELY shows the route is NOT obtainable — the endpoint was "
        "removed/deprecated, is partner/affiliate/login-gated with no public path, is paywalled, or no "
        "such source exists.\n"
        "- 'not_enough_info': the evidence neither confirms a public route NOR shows it is closed.\n"
        "Be SYMMETRIC: 'supported' requires positive evidence of access; 'refuted' requires positive "
        "evidence of NON-access. A specifically NAMED official API or product for which the search "
        "returns NO trace of existence is 'refuted' (a named, official-sounding source with zero "
        "corroboration is fabricated). Reserve 'not_enough_info' for when the platform/source clearly "
        "EXISTS but only its specific capability, granularity, or endpoint is unconfirmed. Never infer "
        "'refuted' from a search miss on a real platform, nor 'supported' from optimism.\n"
        "EXCEPTION — canonically famous sources: if a named source is one you know with HIGH confidence "
        "to be a major, well-established public data source (a government open-data portal or registry "
        "in any country, an official statistics agency, or a large platform whose free public API is "
        "widely documented), treat it as 'supported' with the access model you know to be true — sparse "
        "or ambiguous snippets must NOT downgrade a famous source. This exception NEVER applies to "
        "niche or vendor-specific APIs you don't recognize; those still require corroborating evidence.\n"
        "CADENCE CHECK (2026-07-10, live case: a product assumed a WEEKLY marriage-index feed off a "
        "source the evidence showed was a static 1908-2017 HISTORICAL index): even a real, accessible "
        "source can fail the claimed mechanism if it does not publish often enough. If the evidence "
        "shows the source's actual publication cadence is staler than what the claimed mechanism needs "
        "(e.g. a 'daily'/'weekly'/'real-time' feature built on a source that is a static or "
        "historical/archival dataset), set obtainable=False and cite the cadence mismatch in `note`, "
        "even if verdict='supported' on access."
    )
    try:
        verdict, _ = LLMService.invoke_structured(
            prompt=prompt, output_model=DataRouteVerdict, temperature=0.1,
            model_name=model_name, reasoning_effort=reasoning_effort)
        # Map the three-way verdict onto the pipeline's access vocab. 'not_enough_info' ABSTAINS
        # (canonical 'unverified') — it is NOT in any score-cap set, so an unconfirmed route is
        # surfaced as a caveat rather than penalized (search recall can't false-block a real API).
        v3 = (verdict.verdict or "not_enough_info").strip().lower()
        if verdict.self_sourced:
            canonical = "public"
        elif v3 == "supported":
            canonical = _canonicalize_route(verdict.access_model or "official", True)
        elif v3 == "refuted":
            canonical = "blocked"
        else:
            canonical = "unverified"
        idea.data_access_model = canonical
        if canonical == "blocked":
            idea.build_feasibility_score = min(getattr(idea, "build_feasibility_score", 0.5) or 0.5, 0.3)
            df = getattr(idea, "data_feasibility_score", None)
            if isinstance(df, (int, float)) and df > 0.2:  # re-cap stale data score (cap ran pre-loop)
                idea.data_feasibility_score = 0.2
            if (verdict.note or "").strip():
                idea.data_acquisition_notes = verdict.note.strip()[:160]
        elif canonical == "unverified":
            # Calibrated abstention: no score penalty — flag the uncertainty honestly instead.
            note = (verdict.note or "").strip()
            idea.data_acquisition_notes = (
                "Data route UNVERIFIED — could not confirm or refute a public source; verify "
                "obtainability before building." + (f" {note}" if note else ""))[:200]
        elif canonical != prior and (verdict.note or "").strip():
            idea.data_acquisition_notes = verdict.note.strip()[:120]
        logger.info(f"[v4-verify] '{getattr(idea,'solution_name','?')}' route -> {canonical} "
                    f"(verdict={v3}, access={verdict.access_model})")
        return verdict
    except Exception as e:
        logger.warning(f"[v4-verify] resolve failed: {str(e)[:80]}")
        return None


def tournament_refine_cell_v4(
    candidates: list[BaseSolutionIdea],
    grounding: CellGrounding,
    *,
    rounds: int = _DEFAULT_ROUNDS,
    bar: float = _QUALITY_BAR,
    invoke=_soft_invoke,
    ideator_model: str | None = None,
    ideator_effort: str | None = None,
    reviewer_model: str | None = None,
    reviewer_effort: str | None = None,
    search=None,
    usage_sink: list | None = None,
) -> BaseSolutionIdea:
    """v4 loop: refine on SOFT dimensions only (keep-best + on-pain floor), then run the SEPARATE
    data-route verification on the winner. The loop never scores/optimizes data-feasibility."""
    if not candidates:
        raise ValueError("need at least one candidate")
    ideator_model = ideator_model or settings.ideation_refine_llm
    ideator_effort = ideator_effort if ideator_effort is not None else settings.ideation_refine_reasoning_effort
    reviewer_model = reviewer_model or settings.ideation_mentor_llm
    reviewer_effort = reviewer_effort if reviewer_effort is not None else settings.ideation_mentor_reasoning_effort

    def _rec(u):
        if usage_sink is not None and u is not None:
            usage_sink.append(u)

    current = candidates[0]   # single starting candidate in the A/B (tournament select is unchanged from v3)
    ideator_thread = [_ideator_system(grounding), {"role": "assistant", "content": _idea_to_text(current)}]
    reviewer_thread = [_reviewer_system(grounding)]
    best, best_score, start_mf = current, -1.0, None

    for r in range(max(1, rounds)):
        try:
            crit, u = _review(current, reviewer_thread, invoke=invoke, model=reviewer_model, effort=reviewer_effort)
            _rec(u)
        except Exception as e:
            logger.warning(f"[v4] review failed r{r}: {str(e)[:80]}"); break
        score = crit.composite(grounding.winning_angle)  # P1b: angle-weighted (flag-gated)
        if start_mf is None:
            start_mf = crit.market_fit
        on_pain = crit.market_fit >= start_mf - _ONPAIN_SLACK
        if score > best_score and on_pain:
            best, best_score = current, score
        logger.info(f"[v4] '{getattr(current,'solution_name','?')}' r{r}: comp={score:.2f} mf={crit.market_fit:.2f} "
                    f"on_pain={on_pain} binding={crit.binding_constraint} meets_bar={crit.meets_bar}")
        if (crit.meets_bar or score >= bar) and on_pain:
            best, best_score = current, max(best_score, score); break
        if r == max(1, rounds) - 1:
            break
        try:
            improved, u = _improve(crit, ideator_thread, current, invoke=invoke, model=ideator_model, effort=ideator_effort)
            _rec(u)
        except Exception as e:
            logger.warning(f"[v4] improve failed r{r}: {str(e)[:80]}"); break
        improved.source_pain = getattr(current, "source_pain", None) or grounding.pain_title
        # Do NOT backfill the arbitrary cell segment when None — the crew re-derives honest
        # provenance (or leaves None) at the terminal stamp sites (_provenance_segment_for_pain).
        improved.source_segment = getattr(current, "source_segment", None)
        current = improved

    # SEPARATE verification stage (decoupled from the loop) — resolves the data routes the loop ignored.
    verify_data_routes(best, grounding, search=search, invoke=invoke)
    return best
