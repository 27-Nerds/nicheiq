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
from .idea_improvement_loop import (
    CellGrounding, _carry_forward_fields, _idea_to_text, _ONPAIN_SLACK,
)

_DEFAULT_ROUNDS = 2
_HARD_CAP = 3
_QUALITY_BAR = 0.72
# Soft-only composite: no data/technical feasibility (those are verified, not judged-in-the-loop).
_WEIGHTS = {"market_fit": 0.45, "novelty": 0.30, "clarity": 0.25}
_VERIFY_RE = re.compile(r"\[NEEDS[-\s]?VERIFY:\s*([^\]]+)\]", re.I)


class IdeaCritiqueV4(BaseModel):
    """One reviewer turn — SOFT dimensions only (no data/API judgement; that's verified separately)."""
    market_fit: float = Field(..., ge=0, le=1, description="Does it solve the SOURCE pain for the TARGET audience?")
    novelty: float = Field(..., ge=0, le=1, description="Non-obvious vs the named competitors / generic tools?")
    clarity: float = Field(..., ge=0, le=1, description="Coherent, specific, complete spec (penalize vagueness/empty fields)?")
    binding_constraint: str = Field(..., description="The ONE lowest, most-actionable of the three dimensions")
    directive: str = Field(..., description="A specific, actionable fix for the binding constraint — staying ON the source pain")
    meets_bar: bool = Field(..., description="True only if strong on all three dimensions")
    rationale: str = Field("", description="≤200 chars grounding the call")

    def composite(self) -> float:
        return round(sum(_WEIGHTS[k] * getattr(self, k) for k in _WEIGHTS), 4)


class DataRouteVerdict(BaseModel):
    """Separate, tool-grounded resolution of ONE data claim (never judged inside the loop)."""
    obtainable: bool = Field(..., description="Can a solo dev get this data via the claimed route?")
    access_model: str = Field(..., description="one of: official | unofficial | blocked")
    note: str = Field("", description="≤160 chars citing the search evidence")


def _soft_invoke(messages, output_model, *, temperature, model_name, reasoning_effort):
    creative = output_model is not BaseSolutionIdea
    return LLMService.invoke_structured(
        messages=messages, output_model=output_model, temperature=temperature,
        model_name=model_name, reasoning_effort=reasoning_effort, creative=creative)


def _reviewer_system(g: CellGrounding) -> dict:
    return {"role": "system", "content": (
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
        "values). For ANY data route you are not CERTAIN a public/official source exposes, write it as "
        "`[NEEDS-VERIFY: does <source> expose <exactly what you need>?]` — never assert an API can do "
        "something you're unsure of (a separate tool checks these; a refuted guess gets capped).\n"
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
        "Review on market_fit, novelty, clarity only. Name the binding constraint + one directive.\n\n"
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
        "rule: flag uncertain routes with [NEEDS-VERIFY: ...], don't assert. Return the COMPLETE spec — "
        "if the mechanism, data route, or name changed, rewrite headline, short_description, "
        "value_proposition, why_it_works, and innovation_angle so they describe the revised idea, "
        "not the old one."})
    idea, usage = invoke(thread, BaseSolutionIdea, temperature=0.5, model_name=model, reasoning_effort=effort)
    _carry_forward_fields(idea, prior)
    thread.append({"role": "assistant", "content": _idea_to_text(idea)})
    return idea, usage


def verify_data_routes(idea, grounding, *, search, invoke, model_name=None, reasoning_effort="medium") -> DataRouteVerdict | None:
    """SEPARATE tool-grounded check (Chain-of-Verification): pull the idea's data claims (+ any
    NEEDS-VERIFY flags), search them, and resolve obtainability. Sets idea.data_access_model so the
    downstream deterministic cap can act. Fail-soft → None (leaves the idea's own value)."""
    model_name = model_name or settings.pain_point_validation_llm
    sources = ", ".join(getattr(idea, "data_sources", None) or [])
    flags = _VERIFY_RE.findall(
        f"{getattr(idea,'technical_approach','') or ''} {getattr(idea,'description','') or ''} "
        f"{getattr(idea,'data_acquisition_notes','') or ''}")
    claim = "; ".join(flags) or sources
    if not claim:
        return None
    query = f"{sources} {claim} public official API developer access documentation".strip()
    snippets = ""
    if search is not None:
        try:
            snippets = (search(query) or "")[:1800]
        except Exception as e:
            logger.warning(f"[v4-verify] search failed: {str(e)[:80]}")
    prompt = (
        "Resolve whether a SOLO DEVELOPER can actually obtain the data this product needs, using the "
        "web-search evidence below as ground truth over the idea's optimistic claims.\n\n"
        f"DATA THE PRODUCT NEEDS: {claim}\nNAMED SOURCES: {sources or 'n/a'}\n\n"
        f"WEB-SEARCH EVIDENCE:\n{snippets or '(no evidence retrieved)'}\n\n"
        "FIRST decide whether the product even depends on a specific EXTERNAL API/feed. If it does NOT — "
        "it computes from static formulas, uses publicly downloadable datasets, user-entered values, or "
        "first-party submissions — then the data IS obtainable → access_model='official', obtainable=true. "
        "Do NOT penalize an idea for 'no API found' when it needs no external API.\n"
        "Only when it DOES depend on a specific external source, classify that source: a real public/"
        "official/documented endpoint that exposes what's needed → 'official'; obtainable only via "
        "scraping/ToS-gray/undocumented → 'unofficial'; reverse-engineered, partner/affiliate-gated, "
        "blocked, or no such endpoint exists → 'blocked'. When it depends on an external API and the "
        "evidence doesn't confirm that endpoint+capability is real and open, treat it as NOT obtainable."
    )
    try:
        verdict, _ = LLMService.invoke_structured(
            prompt=prompt, output_model=DataRouteVerdict, temperature=0.1,
            model_name=model_name, reasoning_effort=reasoning_effort)
        idea.data_access_model = verdict.access_model
        if verdict.access_model == "blocked":
            idea.build_feasibility_score = min(getattr(idea, "build_feasibility_score", 0.5) or 0.5, 0.3)
        logger.info(f"[v4-verify] '{getattr(idea,'solution_name','?')}' route -> {verdict.access_model} "
                    f"(obtainable={verdict.obtainable})")
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
        score = crit.composite()
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
        improved.source_segment = getattr(current, "source_segment", None) or grounding.audience_segment
        current = improved

    # SEPARATE verification stage (decoupled from the loop) — resolves the data routes the loop ignored.
    verify_data_routes(best, grounding, search=search, invoke=invoke)
    return best
