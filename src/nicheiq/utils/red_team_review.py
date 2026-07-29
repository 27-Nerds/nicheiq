"""Adversarial red-team pass over the top visible ideas (2026-07-10) — a POST-demote,
PRE-portfolio-summary attacker LLM pass that tries to KILL each top idea from search
evidence alone: category incumbents the idea's own vocabulary would miss, free/bundled
alternatives where the buyer already lives, whether the mechanism handles the MODAL case
of the pain (the common form, not an edge case), and the one PRO-idea urgency question.
Independent of the brainstorm pool (attacker != generator, same class as the score-
calibration critic — see `settings.red_team_review_llm`). An actionable killed/weakened
verdict then gets ONE accept-guarded revision attempt (`_attempt_red_team_revision`) that
tries to escape the finding, mirroring `_parity_pivot_revisions`.

Fail-soft PER IDEA: one idea's LLM/search failure never blocks the others or the pipeline.
A 'killed' verdict whose evidence names a shipped/bundled-free alternative applies the
EXISTING downgrade-only parity cap (`_validate_idea_caps` rule (e)) — there is no parallel
capping mechanism here. 'survives'/'weakened' verdicts stamp verdict+caveats only, never
touch scores. No-op (no LLM call, no searches) when `settings.red_team_top_k == 0`.
"""

from __future__ import annotations

from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field

from .data_access import DATA_ACCESS_VOCAB, normalize_data_access, note_route_label


class _RedTeamVerdict(BaseModel):
    verdict: Literal["survives", "weakened", "killed"] = "survives"
    caveats: list[str] = Field(default_factory=list, description="up to 3, each evidence-cited")
    uplift: Optional[str] = Field(None, description="up to 1 pro-idea note")


# Keywords that mark a killing caveat as a FREE/BUNDLED alternative rather than a plain shipped
# commercial competitor — routes the finding to the bundled_free parity shape vs. the generic
# "shipped by evidence" shape.
_KILL_ALTERNATIVE_WORDS = ("free", "bundled", "included in", "built into", "built-in", "loss-leader")

# A caveat is "actionable" (worth attempting a revision for) when it names a free/bundled
# alternative (the kill-alternative words) OR flags a modal-case miss. Mirrors the killed+cap
# heuristic, extended to catch modal-case language.
_ACTIONABLE_WORDS = _KILL_ALTERNATIVE_WORDS + (
    "modal", "common form", "most common", "doesn't handle", "does not handle", "edge case",
)


def _is_actionable(result) -> bool:
    if result.verdict not in ("killed", "weakened"):
        return False
    blob = " ".join(result.caveats or []).lower()
    return any(w in blob for w in _ACTIONABLE_WORDS)


def _build_queries(crew, idea, niche_short: str, budget: int) -> list[str]:
    """Deterministic category-outcome / free-alternative / platform-native query set for one
    idea, reusing the same capability-phrase derivation as the market-awareness probes
    (`_mechanism_keywords`). Truncated to `budget`; '' capability phrase -> no queries."""
    if budget <= 0:
        return []
    kw = crew._mechanism_keywords(idea)
    if not kw:
        return []
    candidates = [
        f"{kw} alternative",
        f"free {kw}",
        f"{kw} built in",
        f"{kw} vs",
        f"{kw} {niche_short}".strip(),
        f"{kw} reddit",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for q in candidates:
        q = q.strip()[:120]
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            out.append(q)
        if len(out) >= budget:
            break
    return out


def _evidence_block(result_map: dict) -> str:
    """'' when no query returned anything — callers ABSTAIN on empty (never review
    without evidence; a sentinel string here previously defeated that check)."""
    chunks = [f"[{q}]\n{res[:1500]}" for q, res in result_map.items() if res]
    return "\n\n".join(chunks)


def _attempt_red_team_revision(crew, refined_solutions, orig, result, evidence) -> bool:
    """ONE accept-guarded revision of a red-teamed idea (mirrors _parity_pivot_revisions'
    per-idea body): same _Pivot-shape schema, same brainstorm_llm ideator settings, the FULL
    `_score_wave` gauntlet, the same incomplete-vector guard, and the same accept-guard
    (`_comp(rev) > _comp(orig)` AND the revision's own parity re-probe cleared to 'none'). On
    accept: 1:1 in-place replacement carrying provenance, stamps `red_team_revised=True`.
    Fully fail-soft — any failure returns False and the original (with its verdict/caveats)
    stands. Returns True iff a revision REPLACED the original."""
    from pydantic import BaseModel
    from pydantic import Field as _F

    from ..config.settings import settings
    from ..models.solution_idea import BaseSolutionIdea
    from ..utils.score_helpers import _composite_for_angle
    from .llm_service import LLMService

    def _comp(i):
        return _composite_for_angle(
            getattr(i, "market_fit_score", None),
            getattr(i, "technical_feasibility_score", None),
            getattr(i, "novelty_score", None),
            getattr(i, "seo_scalability_score", None),
            getattr(i, "winning_angle", None))

    try:
        class _Revision(BaseModel):
            solution_name: str = ""
            value_proposition: str = ""
            description: str = ""
            core_features: list[str] = _F(default_factory=list)
            conventional_approach: str = ""
            innovation_angle: str = ""
            why_it_works: str = ""
            technical_approach: str = ""
            data_access_model: str = _F(
                "", description="EXACTLY one of: public | freemium | paywalled | "
                                "unofficial | restricted | blocked | unverified. Use 'public' when "
                                "the product needs no external data (pure computation / "
                                "user-supplied input).")
            market_fit_score: float | None = None
            technical_feasibility_score: float | None = None
            build_feasibility_score: float = 0.7
            data_feasibility_score: float = 0.7
            programmatic_seo_opportunity: str = ""

        caveats = result.caveats or []
        prompt = (
            "You are improving an idea that an adversarial reviewer just attacked.\n"
            f"RED-TEAM VERDICT: {result.verdict}\n"
            f"CAVEATS: {' | '.join(caveats) or 'none'}\n"
            f"UPLIFT NOTE: {result.uplift or 'none'}\n"
            f"SEARCH EVIDENCE:\n{(evidence or '')[:1500]}\n\n"
            "THE IDEA (validated pain — keep it):\n"
            f"- name: {getattr(orig, 'solution_name', '')}\n"
            f"- value_prop: {(getattr(orig, 'value_proposition', '') or '')[:250]}\n"
            f"- mechanism: {(getattr(orig, 'technical_approach', '') or '')[:300]}\n\n"
            "Revise this idea to ESCAPE these specific findings while staying on the SAME "
            "anchor pains: drop or de-emphasize any capability the evidence shows is free/"
            "bundled/commoditized, re-target the wedge to the unserved part, make the "
            "mechanism handle the modal case if flagged, and fold in any urgency mechanics "
            "from the uplift note. Keep every field complete — no blanks.")

        r, usage = LLMService.invoke_structured(
            prompt=prompt, output_model=_Revision, temperature=0.3, timeout=180,
            model_name=settings.brainstorm_llm, reasoning_effort="medium", creative=True)
        if usage is not None and getattr(crew, "cost_tracker", None):
            crew.cost_tracker.record_llm_usage("Stage 7 - Red Team Revision", usage.to_dict())

        d = r.model_dump()
        if not d.get("solution_name") or not d.get("value_proposition"):
            return False
        d.setdefault("market_fit_score", 0.5)
        d.setdefault("technical_feasibility_score", 0.6)
        for k in ("build_feasibility_score", "data_feasibility_score",
                  "market_fit_score", "technical_feasibility_score"):
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                d[k] = max(0.0, min(1.0, v / 100.0 if 1.0 < v <= 100.0 else v))
        # Closed-vocab data route: off-vocab ABSTAINS to 'unverified'. Dropping to None used to
        # erase the canonical 'blocked'/'unverified' labels (absent from the old accept-list),
        # and a null label reads downstream as "no data barrier", skipping the feasibility caps.
        _raw = (d.get("data_access_model") or "").strip()
        _dam = normalize_data_access(_raw)
        note_route_label(crew, "red-team", _dam)
        if _raw and _dam is None:
            logger.warning(
                f"[RedTeam] revision of '{getattr(orig, 'solution_name', '?')}' data_access_model "
                f"'{_raw[:40]}' outside DataAccessTag {sorted(DATA_ACCESS_VOCAB)} — "
                f"abstaining to 'unverified'")
            _dam = "unverified"
        d["data_access_model"] = _dam
        d["description"] = d.get("description") or d.get("value_proposition", "")
        d["core_features"] = d.get("core_features") or ["revised workflow"]
        d["pain_points_addressed"] = list(
            getattr(orig, "pain_points_addressed", None) or ["revised pain"])
        d["target_personas"] = list(
            getattr(orig, "target_personas", None) or ["primary audience member"])
        rev = BaseSolutionIdea.model_validate(d)
        rev.source_pain = getattr(orig, "source_pain", None)
        rev.source_segment = getattr(orig, "source_segment", None)
        rev.source_frame = getattr(orig, "source_frame", None) or "pain"
        rev.idea_tier = getattr(orig, "idea_tier", "single") or "single"
        if rev.source_frame == "user_seed":
            from .seed_fidelity import is_seed_faithful
            seed_text = getattr(crew, "_current_seed_text", "") or ""
            if seed_text and not is_seed_faithful(seed_text, rev):
                logger.info(
                    f"[RedTeamRevision] rejected off-seed revision "
                    f"'{getattr(rev, 'solution_name', '?')}' — the submitted product "
                    "mechanism is immutable")
                return False

        crew._score_wave([rev])  # full per-idea sequence; parity re-probe + rule (e) re-apply

        score_dims = [getattr(rev, k, None) for k in
                      ("market_fit_score", "technical_feasibility_score",
                       "novelty_score", "seo_scalability_score")]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in score_dims):
            logger.info(f"[RedTeamRevision] rejected '{getattr(orig, 'solution_name', '?')}' "
                        "— incomplete score vector after scoring")
            return False

        rev_par = (getattr(rev, "incumbent_parity", None) or "").strip().lower()
        if _comp(rev) > _comp(orig) and rev_par.startswith("none"):
            ideas = refined_solutions.solution_ideas
            idx = ideas.index(orig)
            rev.red_team_revised = True
            ideas[idx] = rev
            logger.info(f"[RedTeamRevision] accepted '{rev.solution_name}' "
                        f"(composite {_comp(orig):.3f} -> {_comp(rev):.3f})")
            return True
        logger.info(f"[RedTeamRevision] rejected '{getattr(orig, 'solution_name', '?')}' "
                    f"(composite {_comp(rev):.3f} vs {_comp(orig):.3f}, "
                    f"parity '{rev_par[:40] or 'none'}') — original stands, still tagged")
        return False
    except Exception as e:
        logger.warning(f"[RedTeamRevision] attempt failed (non-fatal): {str(e)[:120]}")
        return False


def run_red_team_review(crew, refined_solutions) -> None:
    """Attacker pass over the top `settings.red_team_top_k` visible ideas (by
    market_fit_score). Mutates ideas in place (`red_team_verdict`, `red_team_caveats`, and —
    on a qualifying 'killed' verdict — `incumbent_parity` plus a `_validate_idea_caps` call
    that applies the existing downgrade-only cap). An actionable killed/weakened verdict then
    gets one accept-guarded revision attempt via `_attempt_red_team_revision`. Fail-soft per
    idea; never raises."""
    from ..config.settings import settings
    from ..models.solution_idea import visible_ideas
    from ..utils.content_security import fence_content
    from .llm_service import LLMService

    top_k = settings.red_team_top_k
    if top_k <= 0:
        return

    ideas = getattr(refined_solutions, "solution_ideas", None) or []
    visible = visible_ideas(ideas)
    if not visible:
        return

    def _mf(i) -> float:
        v = getattr(i, "market_fit_score", None)
        return v if isinstance(v, (int, float)) else -1.0

    top = sorted(visible, key=_mf, reverse=True)[:top_k]
    if not top:
        return

    niche = (getattr(getattr(crew, "niche_context", None), "niche_description", "") or "").strip()
    niche_short = niche[:80]
    budget = settings.red_team_searches_per_idea

    reviewed = revised = revision_accepted = 0
    for idea in top:
        name = (getattr(idea, "solution_name", "") or "?").strip()
        try:
            queries = _build_queries(crew, idea, niche_short, budget)
            result_map = crew._ma_search_batch(queries, budget_exempt=True) if queries else {}
            evidence = _evidence_block(result_map)
            if not evidence.strip():
                # ABSTAIN on empty evidence — no verdict, no caveats, no revision. A review
                # without evidence is not a review; stamping one poisons the analyst summary
                # (live-caught 2026-07-10: a drained shared search budget produced zero
                # results, the verdict said "weakened", and the summary spun the empty
                # search into "no incumbents found — suggesting a potential gap").
                logger.warning(f"[RedTeam] '{name}' skipped: no search evidence returned")
                continue

            prompt = (
                f"Niche: {niche or 'n/a'}\n\n"
                "IDEA under evaluation:\n"
                f"- name: {name}\n"
                f"- value_proposition: {(getattr(idea, 'value_proposition', '') or '')[:220]}\n"
                f"- mechanism: {(getattr(idea, 'technical_approach', '') or '')[:220]}\n\n"
                "Search evidence:\n"
                + fence_content(evidence, source="web-search", label="UNTRUSTED WEB RESULTS")
                + "\n\nYou are trying to KILL this idea. From the search evidence ONLY, answer: "
                  "(1) category incumbents the idea's own vocabulary would miss; (2) free/"
                  "bundled alternatives where the buyer already lives; (3) does the mechanism "
                  "handle the MODAL case of the pain (the common form, not an edge case); (4) "
                  "any urgency mechanics the scores can't see (deadline/race dynamics) — the "
                  "one PRO-idea question; (5) WHO PAYS and why — if the honest answer is "
                  "'nobody; it pressures a platform or serves users who won't pay', say so. "
                  "Cite only what the evidence actually shows — never "
                  "invent products or features. Verdict: survives | weakened | killed, plus up "
                  "to 3 evidence-cited caveats and up to 1 uplift note. Return JSON."
            )

            result, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=_RedTeamVerdict,
                temperature=0.2,
                timeout=120,
                model_name=settings.red_team_review_llm,
                reasoning_effort="high",
                creative=True,
            )
            if usage is not None and getattr(crew, "cost_tracker", None):
                crew.cost_tracker.record_llm_usage("Stage 7 - Red Team", usage.to_dict())

            idea.red_team_verdict = result.verdict
            idea.red_team_caveats = result.caveats or None
            reviewed += 1

            if result.verdict == "killed" and result.caveats:
                caveat = result.caveats[0]
                low = caveat.lower()
                if any(w in low for w in _KILL_ALTERNATIVE_WORDS):
                    note = f"bundled_free (red-team): {caveat}"
                else:
                    note = f"shipped by evidence: {caveat}"
                idea.incumbent_parity = note
                crew._validate_idea_caps(idea)
                logger.info(f"[RedTeam] '{name}' killed -> {note[:80]}")
            elif result.verdict == "weakened":
                logger.info(f"[RedTeam] '{name}' weakened: {result.caveats[:1]}")

            if _is_actionable(result):
                revised += 1
                if _attempt_red_team_revision(crew, refined_solutions, idea, result, evidence):
                    revision_accepted += 1
        except Exception as e:
            logger.warning(f"[RedTeam] '{name}' skipped (non-fatal): {str(e)[:120]}")
            continue

    try:
        fc = getattr(crew, "funnel_counts", None)
        if not isinstance(fc, dict):
            fc = crew.funnel_counts = {}
        fc["red_team_reviewed"] = reviewed
        fc["red_team_revised"] = revised
        fc["red_team_revision_accepted"] = revision_accepted
    except Exception as e:
        logger.warning(f"[RedTeam] funnel update skipped: {str(e)[:120]}")
