"""Part 1 — the ideator↔reviewer improvement loop (generate → critique → IMPROVE).

The pipeline used to run generate → FILTER (drop) → refine-once → score: when an idea scored
low it just RECORDED the score, with no path to make it better. This module is the missing
improvement loop, realised as a DIALOG between two grounded agents kept as TWO mirrored threads
(each agent's own outputs are the `assistant` role in its thread; the other's are `user`):

  ideator thread:  [system=ideator role + pain/segment] → assistant=idea_v1 → user=critique_1 → assistant=idea_v2 …
  reviewer thread: [system=critic role + GROUNDED context] → user=idea_v1 → assistant=critique_1 → user=idea_v2 …

The reviewer carries EXTERNAL, grounded signal (the target audience, the source pain text +
evidence + severity/opportunity, competitor mentions, and the deterministic score flags) so it
judges against real evidence rather than rubber-stamping the ideator — intrinsic self-correction
without reliable external feedback does not work (Huang et al. 2023; Self-Refine; Cross-Context
Review). It critiques ALL core dimensions (market_fit, technical + data feasibility, novelty),
surfaces the SINGLE binding constraint each turn, and drives the fix for that one thing.

Per cell: select the best candidate (tournament) → review → improve → review → … with the gains
front-loaded, so default 2 rounds, hard cap 3, exit early on (a) quality bar met, (b) plateau (a
round doesn't beat the prior), and we KEEP-BEST (never return a version worse than the input).

This module is pure + dependency-injected (`invoke`) so the A/B harness and unit tests drive it
without the full crew. It is NOT wired into execute_pipeline until the isolated A/B (independent
Opus judge) shows the loop's ideas beat the current filter→refine flow.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger
from pydantic import BaseModel, Field

from ..config.settings import settings
from ..models.solution_idea import BaseSolutionIdea
from ..utils.llm_service import LLMService

# Composite quality scalar: how the reviewer's per-dimension scores collapse to one number for
# best-tracking / plateau detection. market_fit and feasibility carry the most weight (a thin or
# unbuildable idea is worse than a slightly-less-novel one); novelty is real but secondary.
_WEIGHTS = {"market_fit": 0.35, "technical_feasibility": 0.20, "data_feasibility": 0.20, "novelty": 0.25}
_DEFAULT_ROUNDS = 2
_HARD_CAP = 3
_QUALITY_BAR = 0.72   # composite at/above which an idea is "good enough" → stop refining it
_ONPAIN_SLACK = 0.05  # a revision whose market_fit falls more than this below the start = off-pain drift


class IdeaCritique(BaseModel):
    """One reviewer turn: grounded per-dimension scores + the single binding constraint to fix."""
    market_fit: float = Field(..., ge=0, le=1, description="Does it solve the SOURCE pain for the TARGET audience? 0-1")
    technical_feasibility: float = Field(..., ge=0, le=1, description="Buildable by a solo dev? 0-1")
    data_feasibility: float = Field(..., ge=0, le=1, description="Is the required data obtainable via public/official routes? 0-1")
    novelty: float = Field(..., ge=0, le=1, description="Non-obvious vs the named competitors / generic approaches? 0-1")
    binding_constraint: str = Field(..., description="The ONE lowest, most-actionable dimension holding this idea back")
    directive: str = Field(..., description="A specific, actionable instruction to fix the binding constraint (not 'improve everything')")
    meets_bar: bool = Field(..., description="True only if this idea is already strong on all dimensions and needs no further change")
    rationale: str = Field("", description="≤200 chars grounding the call in the audience/pain/competitor evidence")

    def composite(self) -> float:
        return round(sum(_WEIGHTS[k] * getattr(self, k) for k in _WEIGHTS), 4)


class CandidateChoice(BaseModel):
    """Tournament selection: which candidate is the strongest starting point to refine."""
    selected_index: int = Field(..., ge=0, description="0-based index of the best candidate to refine")
    reason: str = Field("", description="≤160 chars: why this one over the others")


@dataclass
class CellGrounding:
    """External evidence the reviewer judges against (NOT the ideator's own claims)."""
    niche: str = ""
    audience_segment: str = ""          # the target segment for this cell
    segment_profile: str = ""           # motivations / expertise / budget of that segment
    pain_title: str = ""
    pain_evidence: str = ""             # description + representative quotes
    pain_severity: str = ""             # severity / opportunity labels
    competitor_mentions: str = ""       # real competitor list for the novelty judgement
    deterministic_flags: list[str] = field(default_factory=list)  # from _validate_idea_scores
    winning_angle: str = ""             # P1b: provisional GTM angle so the loop optimizes on-direction

    def as_block(self) -> str:
        flags = "\n".join(f"  - {f}" for f in self.deterministic_flags) or "  (none)"
        return (
            f"NICHE: {self.niche}\n"
            f"TARGET AUDIENCE SEGMENT: {self.audience_segment}\n"
            f"SEGMENT PROFILE: {self.segment_profile or 'n/a'}\n"
            f"SOURCE PAIN: {self.pain_title}\n"
            f"PAIN EVIDENCE (severity {self.pain_severity or 'n/a'}):\n{self.pain_evidence or '  n/a'}\n"
            f"COMPETITORS ALREADY IN THIS SPACE:\n{self.competitor_mentions or '  (none surfaced)'}\n"
            f"DETERMINISTIC SCORE FLAGS (hard signal — treat as ground truth):\n{flags}"
        )


def _invoke_default(messages, output_model, *, temperature, model_name, reasoning_effort):
    """Default injection point over the shared LLMService messages path.

    The large idea spec (BaseSolutionIdea) goes through the json_schema WORKHORSE path
    (creative=False) — the same route _refine_single_concept uses, since open-weight models
    (GLM) fail the forced tool-call transport on a schema that big. The small critique /
    selection schemas use the reasoning-honored tool path (creative=True) so the reviewer can
    actually think before judging."""
    creative = output_model is not BaseSolutionIdea
    result, usage = LLMService.invoke_structured(
        messages=messages,
        output_model=output_model,
        temperature=temperature,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        creative=creative,
    )
    return result, usage


def _idea_to_text(idea: BaseSolutionIdea) -> str:
    """Compact rendering of an idea for a dialog turn (what the agent 'said')."""
    g = lambda a, d="": (getattr(idea, a, None) or d)
    feats = ", ".join(g("core_features", []) or []) if isinstance(g("core_features", []), list) else g("core_features")
    return (
        f"NAME: {g('solution_name')}\n"
        f"HEADLINE: {g('headline')}\n"
        f"WHAT IT IS: {g('short_description') or g('description')}\n"
        f"HOW IT WORKS: {g('description')}\n"
        f"VALUE PROP: {g('value_proposition')}\n"
        f"KEY FEATURES: {feats}\n"
        f"DATA SOURCES: {', '.join(g('data_sources', []) or [])} (access: {g('data_access_model','n/a')})\n"
        f"TECH APPROACH: {g('technical_approach')}\n"
        f"INNOVATION ANGLE: {g('innovation_angle')}\n"
        f"SELF-SCORES — market_fit={g('market_fit_score','?')} tech_feas={g('technical_feasibility_score','?')} "
        f"novelty={g('novelty_score','?')} data_feas={g('data_feasibility_score','?')}"
    )


def _reviewer_system(grounding: CellGrounding) -> dict:
    return {"role": "system", "content": (
        "You are a SKEPTICAL product reviewer for a solo-dev SaaS studio. You judge each idea ONLY "
        "against the grounded evidence below — never the idea's own self-scores. Score four "
        "dimensions 0-1:\n"
        "• market_fit — does it solve THE SOURCE PAIN BELOW for THIS audience? This is anchored to "
        "the specific pain. If the idea has drifted to a DIFFERENT problem (e.g. pre-match prevention "
        "→ post-match forensics, a rental marketplace → a planning tool), market_fit is ≤ 0.3 no "
        "matter how good the new idea is — solving a different pain is NOT progress.\n"
        "• technical_feasibility — a solo dev can build it.\n"
        "• data_feasibility — the data is obtainable via PUBLIC / OFFICIAL / first-party routes, NOT "
        "reverse-engineered/undocumented endpoints, ToS-gray scraping, blocked APIs, or 'partner "
        "access' a solo dev can't get. This is the dimension most worth fixing.\n"
        "• novelty — non-obvious vs the named competitors (not just relabeling the same mechanism).\n"
        "Then name the SINGLE binding constraint — the lowest, most-actionable dimension — and give "
        "ONE specific directive to fix THAT WHILE STAYING ON THE SOURCE PAIN (e.g. 're-route the data "
        "to the official Steam Web API but keep solving the pre-accept problem', 'sharpen the angle: "
        "nobody else does X'). Prefer fixing the DATA ROUTE over pivoting the PRODUCT. Balance novelty "
        "against feasibility; never push novelty at the cost of buildability or on-pain fit. Set "
        "meets_bar=true ONLY when the idea is genuinely strong on every dimension. Be concrete.\n\n"
        "==== GROUNDED EVIDENCE ====\n" + grounding.as_block()
    )}


def _ideator_system(grounding: CellGrounding) -> dict:
    return {"role": "system", "content": (
        "You are a sharp SaaS ideator for a solo developer. You design ONE product that solves the "
        "source pain below for the target audience, then iteratively improve it in response to a "
        "reviewer's critique. Each time the reviewer replies, address the SINGLE binding constraint "
        "they name — change the idea materially (re-route the DATA to an official source, sharpen the "
        "angle), don't just reword. TWO HARD RULES: (1) you must keep solving the SAME source pain — "
        "never pivot to a different problem to dodge a constraint; (2) return a COMPLETE spec every "
        "time — fill EVERY field with real content (headline 5-12 words; short_description ≤180 chars; "
        "description 4-6 sentences on HOW it works, DISTINCT from short_description; value_proposition; "
        "core_features; target_personas; technical_approach; differentiation_factors; data_sources; "
        "pricing_strategy; and numeric market_fit_score / technical_feasibility_score / novelty_score "
        "0-1). Never leave a field blank or duplicate one field into another. Keep what already "
        "works. Stay buildable by one developer with public/official data.\n\n"
        "==== THE PAIN & AUDIENCE YOU SERVE ====\n" + grounding.as_block()
    )}


def review_idea(idea, grounding, reviewer_thread, *, invoke, model_name, reasoning_effort,
                search_evidence=""):
    """Append the idea as a user turn, get the critique as the reviewer's assistant turn.

    `search_evidence` (web-search snippets about the idea's claimed data routes) is injected so the
    reviewer judges data_feasibility against EXTERNAL reality, not the ideator's self-assertion — the
    fix for v2's failure where the ideator fabricated official APIs and the reviewer credited them."""
    evidence_block = (
        "\n\n==== WEB-SEARCH EVIDENCE on the claimed data routes (ground truth — trust this over the "
        "idea's own claims) ====\n" + search_evidence +
        "\nIf the search evidence does NOT confirm the claimed API/endpoint actually exposes the data "
        "this idea needs (or shows it's reverse-engineered / partner-gated / deprecated), score "
        "data_feasibility LOW and make it the binding constraint."
    ) if search_evidence else ""
    reviewer_thread.append({"role": "user", "content":
        "Review this idea against the grounded evidence. Score all four dimensions, name the binding "
        "constraint, and give one directive.\n\n" + _idea_to_text(idea) + evidence_block})
    critique, usage = invoke(reviewer_thread, IdeaCritique, temperature=0.2,
                             model_name=model_name, reasoning_effort=reasoning_effort)
    reviewer_thread.append({"role": "assistant", "content":
        f"scores: market_fit={critique.market_fit} tech={critique.technical_feasibility} "
        f"data={critique.data_feasibility} novelty={critique.novelty}; "
        f"binding={critique.binding_constraint}; directive={critique.directive}"})
    return critique, usage


# STRUCTURAL prose fields: a blank here is a genuine breakage and they rarely change between
# versions, so carrying the prior value forward is safe (prevents the v1 −3.0 clarity collapse).
_CARRY_TEXT = ("description", "technical_approach", "pricing_strategy", "conventional_approach",
               "data_acquisition_notes")
# SURFACE pitch fields (headline, short_description, value_proposition, why_it_works,
# innovation_angle) DESCRIBE the idea and are NEVER back-filled from prior — the old pitch would
# contradict the new mechanism (the stale-field bug); short_description is derived from the NEW
# description below so it's consistent and never blank.
_CARRY_LIST = ("core_features", "target_personas", "data_sources", "differentiation_factors",
               "pain_points_addressed")
_CARRY_NUM = ("market_fit_score", "technical_feasibility_score", "novelty_score")


def _carry_forward_fields(improved, prior) -> None:
    """Fill fields the improve step left empty so the spec never degrades — WITHOUT introducing the
    stale-surface-field bug. Structural prose / lists / scores carry from the prior version; surface
    PITCH fields never carry the old idea's text (that's what made the spec self-contradict), and an
    empty short_description is derived from the NEW description so it's consistent and never blank."""
    for f in _CARRY_TEXT:
        if not (getattr(improved, f, None) or "").strip():
            setattr(improved, f, getattr(prior, f, None))
    # description collapsing into short_description reads as an empty HOW-IT-WORKS — restore the prior.
    if (getattr(improved, "description", "") or "").strip() == (getattr(improved, "short_description", "") or "").strip():
        if (getattr(prior, "description", "") or "").strip():
            improved.description = prior.description
    # Surface fields the model left blank: derive short_description from the NEW description (never
    # stale, never empty); the rest stay blank rather than carry the old pitch — the reviewer's
    # clarity score surfaces a blank next turn, but a CONTRADICTION would slip through unseen.
    if not (getattr(improved, "short_description", "") or "").strip():
        nd = (getattr(improved, "description", "") or "").strip()
        if nd:
            improved.short_description = nd[:177].rstrip() + ("…" if len(nd) > 177 else "")
    for f in _CARRY_LIST:
        if not (getattr(improved, f, None) or []):
            setattr(improved, f, getattr(prior, f, None))
    for f in _CARRY_NUM:
        if getattr(improved, f, None) is None:
            setattr(improved, f, getattr(prior, f, None))


def improve_idea(critique, ideator_thread, prior, *, invoke, model_name, reasoning_effort):
    """Append the critique as a user turn, get the revised idea as the ideator's assistant turn."""
    ideator_thread.append({"role": "user", "content":
        f"Reviewer feedback. Binding constraint: {critique.binding_constraint}. "
        f"Directive: {critique.directive}. Rationale: {critique.rationale}\n"
        "Revise the product to fix THAT constraint — WITHOUT weakening the other dimensions and "
        "WITHOUT pivoting off the source pain. Keep everything that already works. Return the "
        "COMPLETE updated spec: every field filled with real content, no blanks, no field copied "
        "verbatim into another."})
    idea, usage = invoke(ideator_thread, BaseSolutionIdea, temperature=0.5,
                         model_name=model_name, reasoning_effort=reasoning_effort)
    _carry_forward_fields(idea, prior)
    ideator_thread.append({"role": "assistant", "content": _idea_to_text(idea)})
    return idea, usage


def select_best(candidates, grounding, *, invoke, model_name, reasoning_effort):
    """Tournament selection: the reviewer picks the strongest candidate to refine. Index-safe."""
    if len(candidates) == 1:
        return 0
    listing = "\n\n".join(f"[{i}] {_idea_to_text(c)}" for i, c in enumerate(candidates))
    thread = [_reviewer_system(grounding), {"role": "user", "content":
        "Pick the SINGLE candidate that is the strongest starting point to refine into a winner for "
        "this pain + audience (most on-pain and buildable; novelty breaks ties). Return its index.\n\n"
        + listing}]
    try:
        choice, _ = invoke(thread, CandidateChoice, temperature=0.2,
                           model_name=model_name, reasoning_effort=reasoning_effort)
        return choice.selected_index if 0 <= choice.selected_index < len(candidates) else 0
    except Exception as e:
        logger.warning(f"[loop] tournament selection failed ({str(e)[:80]}); taking candidate 0")
        return 0


def _search_data_evidence(idea, search) -> str:
    """Web-search the idea's claimed data routes so the reviewer can judge data_feasibility against
    reality (does the named API actually expose this data, or is it reverse-engineered/gated?).
    `search` is an injected `query -> snippets_text` callable; None disables grounding (degrades to
    the v2 behaviour). Fail-soft: any search error returns ''."""
    if search is None:
        return ""
    sources = ", ".join(getattr(idea, "data_sources", None) or [])
    access = getattr(idea, "data_access_model", "") or ""
    if not (sources or access):
        return ""
    query = f"{sources} {access} API official public access developer documentation".strip()
    try:
        snippets = search(query)
    except Exception as e:
        logger.warning(f"[loop] data-route search failed ({str(e)[:80]}); no evidence")
        return ""
    return (snippets or "").strip()[:1800]


def tournament_refine_cell(
    candidates: list[BaseSolutionIdea],
    grounding: CellGrounding,
    *,
    rounds: int = _DEFAULT_ROUNDS,
    cap: int = _HARD_CAP,
    bar: float = _QUALITY_BAR,
    invoke=_invoke_default,
    ideator_model: str | None = None,
    ideator_effort: str | None = None,
    reviewer_model: str | None = None,
    reviewer_effort: str | None = None,
    search=None,
    usage_sink: list | None = None,
) -> BaseSolutionIdea:
    """Refine ONE (pain×segment) cell to a single high-quality winner.

    select best candidate → (search-ground) review → improve → review → … keeping the BEST ELIGIBLE
    version. The reviewer runs on a DIFFERENT, stronger model than the ideator (v2 failed when GLM
    judged its own output) and is grounded with web-search evidence on the data routes. A version is
    ELIGIBLE to win only if its on-pain (market_fit) score didn't drop below the starting candidate's
    — so a pivot off the source pain can never be selected (the v2 regression). Early-exit on
    meets_bar / round budget. Fail-soft: any LLM error ends the loop with the best idea so far.
    """
    if not candidates:
        raise ValueError("tournament_refine_cell requires at least one candidate")
    ideator_model = ideator_model or settings.ideation_refine_llm
    if ideator_effort is None:
        ideator_effort = settings.ideation_refine_reasoning_effort
    # Reviewer defaults to a strong reasoning model from a DIFFERENT family than the GLM ideator.
    reviewer_model = reviewer_model or "gpt-5.4-mini"
    if reviewer_effort is None:
        reviewer_effort = "medium"
    rounds = max(1, min(rounds, cap))

    def _record(u):
        if usage_sink is not None and u is not None:
            usage_sink.append(u)

    idx = select_best(candidates, grounding, invoke=invoke,
                      model_name=reviewer_model, reasoning_effort=reviewer_effort)
    current = candidates[idx]

    ideator_thread = [_ideator_system(grounding), {"role": "assistant", "content": _idea_to_text(current)}]
    reviewer_thread = [_reviewer_system(grounding)]

    best_idea, best_score = current, -1.0
    start_mf = None              # the starting candidate's on-pain score → the eligibility floor
    for r in range(rounds):
        evidence = _search_data_evidence(current, search)
        try:
            critique, u = review_idea(current, grounding, reviewer_thread, invoke=invoke,
                                      model_name=reviewer_model, reasoning_effort=reviewer_effort,
                                      search_evidence=evidence)
            _record(u)
        except Exception as e:
            logger.warning(f"[loop] review failed round {r} ({str(e)[:80]}); stopping with best so far")
            break
        score = critique.composite()
        if start_mf is None:
            start_mf = critique.market_fit
        # ON-PAIN FLOOR: a version that drifted off the source pain (market_fit fell below the
        # starting candidate's) is INELIGIBLE to win, no matter how its other dims inflated.
        on_pain = critique.market_fit >= start_mf - _ONPAIN_SLACK
        if score > best_score and on_pain:
            best_idea, best_score = current, score
        logger.info(f"[loop] '{getattr(current,'solution_name','?')}' round {r}: composite={score:.2f} "
                    f"mf={critique.market_fit:.2f} on_pain={on_pain} binding={critique.binding_constraint} "
                    f"meets_bar={critique.meets_bar}")
        # (a) quality bar met / reviewer satisfied → ship the current (if it's still on-pain)
        if (critique.meets_bar or score >= bar) and on_pain:
            best_idea, best_score = current, max(best_score, score)
            break
        if r == rounds - 1:
            break   # out of round budget; keep best
        try:
            improved, u = improve_idea(critique, ideator_thread, current, invoke=invoke,
                                       model_name=ideator_model, reasoning_effort=ideator_effort)
            _record(u)
        except Exception as e:
            logger.warning(f"[loop] improve failed round {r} ({str(e)[:80]}); keeping best so far")
            break
        # carry provenance forward (the improve LLM may drop it)
        improved.source_pain = getattr(current, "source_pain", None) or grounding.pain_title
        improved.source_segment = getattr(current, "source_segment", None) or grounding.audience_segment
        current = improved

    return best_idea
