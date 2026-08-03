"""Adversarial red-team pass over top visible ideas (2026-07-10; slot allocation and
off-category abstain reworked 2026-07-30, run-quality fixes §2/§5) — a POST-demote,
PRE-portfolio-summary attacker LLM pass that tries to KILL each reviewed idea from search
evidence alone: category incumbents the idea's own vocabulary would miss, free/bundled
alternatives where the buyer already lives, whether the mechanism handles the MODAL case
of the pain (the common form, not an edge case), and the one PRO-idea urgency question.
Independent of the brainstorm pool (attacker != generator, same class as the score-
calibration critic — see `settings.red_team_review_llm`). An actionable killed/weakened
verdict then gets ONE accept-guarded revision attempt (`_attempt_red_team_revision`) that
tries to escape the finding, mirroring `_parity_pivot_revisions`.

Fail-soft PER IDEA: one idea's LLM/search failure never blocks the others or the pipeline.
NO verdict touches scores — every verdict stamps `red_team_verdict`/`red_team_caveats` and
nothing else. The consequences live where they can be attributed: `apply_red_team_downgrade`
(verdict floor + report caveat) and the auto-pick guard (`score_helpers.choose_auto_pick`).
No-op (no LLM call, no searches) when `settings.red_team_top_k == 0`.

A 'killed' verdict USED to write its first caveat into `incumbent_parity` as
"shipped by evidence: <caveat>" and then call `_validate_idea_caps` (rule (e), a 0.45
market_fit ceiling). That coupling is deleted (2026-08-02). `_RedTeamVerdict` has no vendor
field, so 100% of those stamps were vendor-less BY CONSTRUCTION, and the sibling probe
`_probe_mechanism_parity` already enforces the rule this path never adopted: no named vendor
=> no parity finding. An audit of all 8 vendor-less stamps found 0 valid parity claims of any
class — a finding of an EMPTY competitive field was being stamped as the harshest parity
class and charged a second time on top of the kill itself.
"""

from __future__ import annotations

from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel, Field

from .data_access import DATA_ACCESS_VOCAB, normalize_data_access, note_route_label
from .idea_carryover import carry_forward_idea_fields
from .validation.niche_anchor import anchor_coverage

# Minimum anchor_entities for the off-category guard to activate — below this the
# guard fails OPEN (review proceeds). Mirrors QueryGenerator.MIN_ANCHORS_ACTIVE
# (utils/generation/query_generator.py) without importing the class.
_MIN_ANCHORS_ACTIVE = 3


class _RedTeamVerdict(BaseModel):
    verdict: Literal["survives", "weakened", "killed"] = "survives"
    caveats: list[str] = Field(default_factory=list, description="up to 3, each evidence-cited")
    uplift: Optional[str] = Field(None, description="up to 1 pro-idea note")


# Keywords that mark a caveat as naming a FREE/BUNDLED alternative rather than a plain shipped
# commercial competitor — an escapable finding, so it is worth a revision attempt.
_KILL_ALTERNATIVE_WORDS = ("free", "bundled", "included in", "built into", "built-in", "loss-leader")

# A caveat is "actionable" (worth attempting a revision for) when it names a free/bundled
# alternative (the kill-alternative words) OR flags a modal-case miss.
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
    (`_mechanism_keywords`, here glossary-expanded so ambiguous niche acronyms like "SMS"
    search as their expansions). Truncated to `budget`; '' capability phrase -> no queries.

    Run-quality fixes §2 (2026-07-30): every query but the last carries a short niche
    anchor term — the old set anchored only 1 of 6, and that one sat at index 4 where any
    budget < 5 dropped it, so mechanism vocabulary alone routinely retrieved a DIFFERENT
    industry ("deterministic governance" -> AI-agent security). The anchor goes right
    after `kw` (a trailing anchor would be chopped by the [:120] truncation). The LAST
    candidate stays deliberately unanchored: it preserves the broad "incumbents the
    idea's own vocabulary would miss" arm and hedges against anchored queries
    over-constraining into all-empty retrieval."""
    if budget <= 0:
        return []
    from .jargon_glossary import build_jargon_glossary
    from .validation.niche_anchor import niche_anchor_query_term

    ctx = getattr(crew, "niche_context", None)
    kw = crew._mechanism_keywords(idea, glossary=build_jargon_glossary(ctx))
    if not kw:
        return []
    anchor = niche_anchor_query_term(ctx)
    candidates = [
        f"{kw} {anchor}".strip(),
        f"{kw} {anchor} alternative".strip(),
        f"free {kw} {anchor}".strip(),
        f"{kw} {anchor} built in".strip(),
        f"{kw} {anchor} vs".strip(),
        f"{kw} alternative",
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
        # Same reset-then-stamp gap as the parity pivot (utils/idea_carryover.py): `_Revision`
        # names a fraction of BaseSolutionIdea, so everything else used to reset to default —
        # red-team revisions shipped with `project_type: None` in three audited runs.
        carry_forward_idea_fields(orig, rev)
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
            rev.rebuild_origin = "red_team_revision"
            # A revision changes the product, so the summary/positioning fields the
            # `_Revision` schema does not rewrite are deliberately NOT carried
            # (idea_carryover rules 2 and 4) and must be re-derived against the new
            # description. Fill-only, and no LLM call when nothing is blank. Runs after
            # `_score_wave` so scoring still sees the revision's own prose, not repaired text.
            crew._repair_blank_idea_fields(
                rev, escaped_parity=getattr(orig, "incumbent_parity", None),
                rebuild=True,
            )
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
    """Attacker pass over `settings.red_team_top_k` visible ideas, slotted across three
    axes — angle-composite leader, best shippability (min(build, solo) >= 0.70), then
    market_fit / shippability alternation — so the likely selection AND the most
    shippable ideas both get reviewed (a pure market_fit sort excluded whatever the
    payability/parity caps had compressed). Mutates ideas in place — `red_team_verdict` and
    `red_team_caveats` ONLY; no verdict writes a score or a parity class (see the module
    docstring for the deleted killed->`incumbent_parity` coupling). An actionable
    killed/weakened verdict then gets one accept-guarded revision attempt via
    `_attempt_red_team_revision`. Fail-soft per idea; never raises."""
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

    def _ship(i) -> float:
        # Binding-constraint shippability: min(buildability, one-person operability).
        bf = getattr(i, "build_feasibility_score", None)
        sd = getattr(i, "solo_dev_feasibility", None)
        if isinstance(bf, (int, float)) and isinstance(sd, (int, float)):
            return min(bf, sd)
        return -1.0

    def _comp_key(i) -> float:
        from ..utils.score_helpers import _composite_for_angle
        return _composite_for_angle(
            getattr(i, "market_fit_score", None),
            getattr(i, "technical_feasibility_score", None),
            getattr(i, "novelty_score", None),
            getattr(i, "seo_scalability_score", None),
            getattr(i, "winning_angle", None))

    # Slot allocation (run-quality fixes §5, 2026-07-30) — reserve-then-fill across three
    # axes instead of pure market_fit. market_fit is the field the payability/parity caps
    # compress hardest, so a pure-mf sort systematically excluded the most shippable ideas
    # AND (because selection ranks by composite) sometimes the likely winner itself from
    # adversarial review. Slot 1 = composite leader (the idea most likely to become the
    # selection, so the verdict floor has something to read). Slot 2 = best shippability
    # (>= 0.70 bar — below it the axis is noise) from the REMAINDER (reserve-then-fill:
    # picking both axes' winners independently collapses to pure-mf whenever one idea tops
    # both). Slots 3+ alternate market_fit / shippability. Unscored ideas sink (-1.0);
    # with no composite/shippability signal anywhere this degrades to the old mf order.
    top: list = []

    def _take(order_key, floor: float | None = None) -> None:
        if len(top) >= top_k:
            return
        pool = [i for i in visible if i not in top]
        pool.sort(key=order_key, reverse=True)
        for cand in pool:
            score = order_key(cand)
            if floor is not None and score < floor:
                break  # sorted desc — nothing later clears the floor
            top.append(cand)
            return

    _take(_comp_key)
    _take(_ship, floor=0.70)
    ax = 0
    while len(top) < min(top_k, len(visible)):
        _take((_mf, _ship)[ax % 2])  # floorless — always fills from a non-empty pool
        ax += 1
    if not top:
        return

    niche = (getattr(getattr(crew, "niche_context", None), "niche_description", "") or "").strip()
    niche_short = niche[:80]
    budget = settings.red_team_searches_per_idea

    # Off-category guard (run-quality fixes §2, 2026-07-30): anchor-vocabulary matchers
    # decide whether retrieved evidence is even in this niche's category — a probe whose
    # results are entirely foreign (live 3-of-4-runs failure: "deterministic governance"
    # retrieved AI-agent security tools) must ABSTAIN, not report "no incumbents found".
    # Matched against RESULT BODIES only, never the assembled evidence block: its
    # "[query]" headers now contain the anchor term by construction and would make the
    # guard self-satisfying. Matcher vocabulary = brands (anchor_entities) + multi-word
    # community terms + jargon-glossary expansions; single-word jargon is deliberately
    # excluded (generic tokens like "versioning" stem-match foreign evidence and would
    # silently disable the guard). Fail-open below _MIN_ANCHORS_ACTIVE entities
    # (mirrors QueryGenerator.MIN_ANCHORS_ACTIVE — see query_generator.py).
    _ctx = getattr(crew, "niche_context", None)
    _entities = list(getattr(_ctx, "anchor_entities", None) or [])
    vocab_matchers: list = []
    if len(_entities) >= _MIN_ANCHORS_ACTIVE:
        from .jargon_glossary import build_jargon_glossary
        from .validation.niche_anchor import build_anchor_matchers
        _multiword = [t for t in (getattr(_ctx, "community_search_terms", None) or [])
                      if len((t or "").split()) >= 2]
        vocab_matchers = build_anchor_matchers(
            _entities + _multiword + list(build_jargon_glossary(_ctx).values()))

    reviewed = revised = revision_accepted = 0
    empty_abstained = offcategory_abstained = 0
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
                empty_abstained += 1
                continue

            bodies = [res for res in result_map.values() if res]
            if vocab_matchers and anchor_coverage(bodies, vocab_matchers) == 0.0:
                # ABSTAIN on off-category evidence — same semantics as the empty case:
                # no verdict, no caveats, no revision. A vocabulary mismatch is a
                # retrieval failure, not negative market evidence; stamping "weakened"
                # here is how 3 of 4 audited runs laundered a bad query set into
                # "no evidence this pain is real" (docs/RUN_QUALITY_ROOT_CAUSES.md §2).
                idea.red_team_vocab_mismatch = (
                    "probe evidence off-category: the idea's mechanism vocabulary "
                    "retrieved a different industry — market conclusions abstained; "
                    "rename/re-probe advised")
                offcategory_abstained += 1
                logger.warning(
                    f"[RedTeam] '{name}' abstained: evidence shares no niche anchor "
                    "(vocabulary mismatch)")
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

            if result.verdict == "killed":
                logger.info(f"[RedTeam] '{name}' killed: {result.caveats[:1]}")
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
        fc["red_team_empty_evidence_abstained"] = empty_abstained
        fc["red_team_offcategory_abstained"] = offcategory_abstained
    except Exception as e:
        logger.warning(f"[RedTeam] funnel update skipped: {str(e)[:120]}")
