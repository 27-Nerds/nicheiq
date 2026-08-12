"""The `idea_validation` block for "Check my idea" runs (plan P5.22).

A PURE reshape of restored checkpoint state — no LLM calls, no probes. Rebuilt on every
`_materialize_preview_report` call (regenerate / chat-seed operations re-materialize the
preview asset, so the block must reconstruct identically from state alone). The user's
idea and its pivot are selected by the durable marker pair:

    seed  = source_frame == 'user_seed' AND generation_operation_id == 'validate'
    pivot = source_frame == 'user_seed' AND generation_operation_id == 'validate_pivot'

Everything user-facing here is enum-driven — the frontend must never string-sniff prose.
Copy constants live at module top so tests assert them exactly.
"""

from __future__ import annotations

import re

from loguru import logger

from ..models.solution_idea import (
    effective_red_team_state,
    effective_red_team_verdict,
    has_affirmative_red_team_findings,
)
from ..utils.calibration_notes import extract_criterion_reason, truncate_for_display
from ..utils.seed_fidelity import content_tokens, seed_clause_drift

# ── fixed copy (asserted by tests; the frontend renders these verbatim) ──
UNANCHORED_NOTE = (
    "No thread in this run names your problem. We graded your idea as a hypothesis, "
    "not as evidence-backed.")
THIN_EVIDENCE_NOTE = "Not enough linked evidence to grade the problem's breadth."
DEMAND_NOT_MEASURED = ("Search-demand probes are outside this check's scope. "
                       "They're the Deep Research step.")
NONE_FOUND_NOTE = (
    "No direct competitor turned up. On this evidence that more often means nobody is "
    "paying for this yet than that the lane is open.")
PRICE_CAVEAT = "snippet-derived, ±1 tier"
MARKET_SIGNAL_PREFIX = ("The market's loudest complaint in this space. A product like "
                        "yours must not trigger it: ")
DESK_LIMITS = [
    "We read what people said unprompted. We could not ask them the follow-up question.",
    "Nothing here is commitment evidence. No one has paid, pre-ordered, or given up "
    "anything for this idea.",
    "Severity and mention counts describe this run's captured discussions, not the "
    "whole market.",
]
EXPERIMENT_LADDER = [
    {"rung": 1, "action": "Run 5 problem interviews with the buyer you named",
     "kill_number": "kill if no interview independently describes the problem",
     "cost_note": "free"},
    {"rung": 2, "action": "Put up a landing page and drive ~50 clicks to it",
     "kill_number": "kill below 1% click-to-email", "cost_note": "under $100"},
    {"rung": 3, "action": "Offer 3 pre-sales at half price",
     "kill_number": "kill below 3 paid commitments", "cost_note": "reputation only"},
    {"rung": 4, "action": "Deliver the outcome by hand for one customer (concierge)",
     "kill_number": "kill if they stop showing up", "cost_note": "a weekend"},
]

_MARKER_SEED = "validate"
_MARKER_PIVOT = "validate_pivot"


_PRICE_UNKNOWNS = {
    "unknown", "unclear", "n/a", "na", "not listed", "unlisted", "not found",
    "none", "not public", "undisclosed", "?",
}


def resolve_idea_validation_outcome(
    *,
    idea_name: str | None,
    demoted: bool,
    parity_raw: str | None,
    unanchored: bool,
    red_team_verdict: str | None,
    refinement_present: bool,
    brief_parity_hit: bool,
    red_team_findings: list | None = None,
) -> tuple[str, str]:
    """Return the one top-line outcome/headline for an evaluated idea-check seed.

    This is the sole outcome-precedence authority for both live preview materialization
    and the registered-asset backfill. Keep raw red-team diagnostics on the record, but
    absorb their decision meaning here before any consumer renders the top line.
    """
    parity = (parity_raw or "").strip().lower()
    red_team = effective_red_team_verdict(red_team_verdict, red_team_findings) or ""

    if demoted:
        return (
            "ruled_out",
            f"We ruled {idea_name or 'your idea'} out on this run. "
            "The evidence did not support building it.",
        )
    if parity.startswith(("shipped", "partial")):
        return (
            "occupied",
            "Real problem, and a named competitor already ships the core of "
            f"{idea_name or 'your idea'}. That is demand proof and an entry "
            "constraint at the same time.",
        )
    if unanchored:
        return (
            "premise_unproven",
            f"{idea_name or 'Your idea'} rests on a problem this run's evidence "
            "does not name. We graded it as a hypothesis.",
        )
    if red_team == "killed":
        if has_affirmative_red_team_findings(red_team_findings):
            return (
                "premise_unproven",
                f"The problem behind {idea_name or 'your idea'} shows up in real "
                "threads, but adversarial review found verified counterevidence "
                "against the evaluated premise. Demand is still unmeasured.",
            )
        return (
            "premise_unproven",
            f"The problem behind {idea_name or 'your idea'} shows up in real "
            "threads, but adversarial review could not confirm the premise. "
            "Demand is still unmeasured.",
        )
    if red_team == "weakened":
        if (red_team_findings is not None
                and not has_affirmative_red_team_findings(red_team_findings)):
            return (
                "worth_testing",
                f"The problem behind {idea_name or 'your idea'} shows up in real "
                "threads, but adversarial review returned incomplete evidence. "
                "Demand is still unmeasured.",
            )
        return (
            "worth_testing",
            f"The problem behind {idea_name or 'your idea'} shows up in real "
            "threads, but adversarial review found material concerns. Demand "
            "is still unmeasured.",
        )
    if refinement_present:
        # One verdict, not three: scope the sentence to the mechanism actually evaluated.
        if brief_parity_hit:
            return (
                "worth_testing",
                f"The problem behind {idea_name or 'your idea'} is real. Your "
                "original mechanism already has tools shipping in it; the "
                "sharpened version we evaluated has no direct shipper. Demand "
                "is still unmeasured.",
            )
        return (
            "worth_testing",
            f"The problem behind {idea_name or 'your idea'} shows up in "
            "real threads, and nothing we found ships the mechanism we "
            "evaluated, a sharpened version of your pitch. Demand is "
            "still unmeasured.",
        )
    if brief_parity_hit:
        return (
            "worth_testing",
            f"The problem behind {idea_name or 'your idea'} shows up in real "
            "threads. Tools already ship in your mechanism's category, though "
            "no direct equivalent of your exact product turned up. Demand is "
            "still unmeasured.",
        )
    if parity.startswith("none"):
        return (
            "worth_testing",
            f"The problem behind {idea_name or 'your idea'} shows up in real "
            "threads, and nothing we found ships your mechanism yet. Demand is "
            "still unmeasured.",
        )
    return (
        "worth_testing",
        f"The problem behind {idea_name or 'your idea'} shows up in real "
        "threads. The direct-equivalent probe did not produce a result, "
        "and demand is still unmeasured.",
    )


def _normalize_price_note(value) -> str | None:
    """Snippet-derived pricing arrives as free text. Real prices ('$15-49/mo',
    'Free or $9.99/mo') pass verbatim; unknowns become None (the column renders an
    em-dash); a bare tier word becomes a labeled tier ('Enterprise' → 'enterprise
    tier') so stray words don't masquerade as prices in a numeric column."""
    text = str(value).strip() if value is not None else ""
    if not text or text.lower() in _PRICE_UNKNOWNS:
        return None
    if (any(ch.isdigit() for ch in text)
            or any(sym in text for sym in "$€£")
            or "free" in text.lower()):
        return text
    if len(text.split()) == 1:
        return f"{text.lower()} tier"
    return text


_PARITY_VENDOR_REJECTS = {
    "", "diy", "evidence", "red-team", "unknown",
    # belt-and-braces: a class word in the vendor slot is an upstream parse bug
    "shipped", "partial", "substitute", "bundled_free",
}


def _parse_parity_incumbent(parity_raw) -> tuple[str, str] | None:
    """(vendor, evidence) from the seed's parity stamp via the shared shape authority
    (`validators/report_consistency`); None for 'none found', free text, or
    placeholder vendors (DIY, unknown …)."""
    from ..validators.report_consistency import parse_stamp_vendor_evidence

    parsed = parse_stamp_vendor_evidence(parity_raw)
    if parsed is None:
        return None
    _klass, vendor, evidence = parsed
    if vendor.strip().lower() in _PARITY_VENDOR_REJECTS:
        return None
    return vendor, evidence


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _names_match(a: str, b: str) -> bool:
    """Case-insensitive, word-boundary containment either way — covers the live
    near-miss: parity vendor 'Dext Commerce' vs map row 'Dext'."""
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    return na == nb or f" {na} " in f" {nb} " or f" {nb} " in f" {na} "


def _display_parity(stamp):
    """Human display form of a stored parity stamp. Stamps keep the probe's full
    evidence sentence ('shipped by X: X ships Y'); presentation is decided here:

    - vendor as sentence SUBJECT ('X ships Y') or comma appositive ('X, a suite,
      ships Y') → render the evidence sentence verbatim (the row's answer chip
      already carries the class; 'shipped by X: ships Y' read as a broken stitch);
    - vendor as duplicated LABEL ('X: Y' / 'X — Y') → keep the stamp form minus
      the duplicate label;
    - no echo → the stamp verbatim.

    The class/vendor prefix is never altered (≥7 consumers parse it); the raw
    stamp stays in block['incumbent_parity']."""
    if not isinstance(stamp, str) or not stamp.strip():
        return stamp
    text = stamp.strip()
    from ..validators.report_consistency import parse_stamp_vendor_evidence

    parsed = parse_stamp_vendor_evidence(text)
    if parsed is None:
        return stamp
    _klass, vendor, evidence = parsed
    if not evidence:
        return stamp
    # Dashes excluded from the lookahead (unspaced dash = compound word, not echo);
    # a spaced dash is reached through the \s and lands in sep for the label test.
    m = re.match(rf"^{re.escape(vendor)}(?=[\s:,]|$)(?P<sep>[\s:,\-–—]*)",
                 evidence, re.IGNORECASE)
    if not m:
        return stamp
    remainder = evidence[m.end():].strip()
    if not remainder:
        return stamp
    if any(ch in m.group("sep") for ch in ":-–—"):
        # label echo: 'shipped by X: X: Y' → 'shipped by X: Y'
        return text[: len(text) - len(evidence)] + remainder
    # subject (or comma-appositive) echo: the evidence is a complete sentence
    return evidence


def _display_embedded(text, parity_raw):
    """Humanize a parity stamp EMBEDDED in prose (the demotion reason quotes the
    stamp verbatim mid-sentence), and retire the stored lead's em-dash (rule 24
    reached the producer later than the stored runs)."""
    if not text:
        return text
    if parity_raw and parity_raw in text:
        display = _display_parity(parity_raw)
        if display != parity_raw:
            text = text.replace(parity_raw, display)
    return text.replace("Already well-served — ", "Already well-served: ")


_GAP_BOILERPLATE = {
    # Exact (normalized) missingness values observed across stored incumbent maps —
    # price-status text leaking into the gap field. NEVER a generic 'pricing' match:
    # real gaps like 'pricing scales with unit count' must survive.
    "pricing not disclosed in results",
    "no specific pricing or feature gaps listed",
    "pricing and feature details missing",
    "not mentioned in pricing details",
    "unknown pricing",
    "unknown",
    "none",
    "n/a",
    "na",
}


def _normalize_gap(value) -> str | None:
    """A gap cell renders an em-dash when the producer had nothing to say — data-
    availability boilerplate must not masquerade as a product limitation."""
    text = str(value).strip() if value is not None else ""
    if not text or text.strip(" .").lower() in _GAP_BOILERPLATE:
        return None
    return text


def _verdict_evidence_fragment(vendor: str, evidence: str) -> str | None:
    """The trigger row's "Why it's named" line: a vendor-SUBJECT echo drops the vendor
    (the row already names it, and the fragment keeps its verb: 'ships Ratio utility
    billing…'); comma appositives and non-echo evidence stay whole sentences."""
    if not evidence:
        return None
    m = re.match(rf"^{re.escape(vendor)}(?=[\s:,]|$)(?P<sep>[\s:,\-–—]*)",
                 evidence, re.IGNORECASE)
    if m and "," not in m.group("sep"):
        remainder = evidence[m.end():].strip()
        if remainder:
            return remainder
    return evidence


def _find_marked(ideas: list, marker: str):
    for idea in ideas or []:
        frame = (getattr(idea, "source_frame", None) or "").strip().lower()
        if frame == "user_seed" and getattr(idea, "generation_operation_id", None) == marker:
            return idea
    return None


def _score_band(score) -> str:
    if not isinstance(score, (int, float)):
        return "unrated"
    if score >= 0.80:
        return "strong"
    if score >= 0.65:
        return "good"
    if score >= 0.50:
        return "moderate"
    if score >= 0.35:
        return "limited"
    return "weak"


def _severity_label(score) -> str:
    """High/Medium/Low with the SAME cutoffs the discovery dossier uses (0.7/0.4) —
    the report and the dossier below it must speak one severity vocabulary, and
    '<band> severity' phrasing broke when the band word was 'good'."""
    if not isinstance(score, (int, float)):
        return "unrated"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _demotion_reason(state, seed) -> str | None:
    seed_id = getattr(seed, "idea_id", None)
    seed_name = (getattr(seed, "solution_name", None) or "").strip().lower()
    for finding in getattr(state, "idea_ruled_out", None) or []:
        if not isinstance(finding, dict):
            continue
        if (seed_id and finding.get("idea_id") == seed_id) or (
                seed_name and (finding.get("solution_name") or "").strip().lower() == seed_name):
            return (finding.get("reason") or finding.get("finding")
                    or finding.get("detail") or finding.get("summary"))
    return None


def _idea_focus_tokens(state) -> set[str]:
    """Distinctive stems of the pitch's mechanism+problem terms, MINUS the derived
    market's own head terms. Scoring quotes against the whole brief promotes
    audience/platform-noun rants (the live run's off-topic REST-API rant won on
    {manag, reddit, small}); mechanism/problem terms minus head terms pick the
    quotes that are about what the product actually does."""
    terms = getattr(state, "user_idea_identity_terms", None) or {}
    focus = content_tokens(" ".join(
        t for key in ("mechanism", "problem") for t in (terms.get(key) or [])
        if isinstance(t, str)))
    if not focus:  # legacy states without parsed terms: whole brief, still de-headed
        focus = content_tokens(getattr(state, "user_idea_brief", None) or "")
    head = content_tokens(
        getattr(getattr(state, "niche_context", None), "niche_description", None) or "")
    return focus - head


_QUOTE_LEAD_MARKERS = re.compile(r"^[>\*\-•\s]+")


def _ranked_quotes(pain, focus: set[str]) -> list[str]:
    """Top-2 quotes by focus-token overlap; dedupe first (live run rendered the same
    quote twice, bar a leading '>'); zero overlap everywhere keeps original order.
    Leading quote/list markers ('>', '*', '-') are presentation debris from the
    source platform — stripped for display; mid-quote formatting stays verbatim."""
    seen: set[str] = set()
    quotes: list[str] = []
    for q in (getattr(pain, "representative_quotes", None) or []):
        text = _QUOTE_LEAD_MARKERS.sub("", q if isinstance(q, str) else str(q)).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        quotes.append(text)
    scored = [(len(focus & content_tokens(q)), idx, q) for idx, q in enumerate(quotes)]
    if any(score for score, _, _ in scored):
        scored.sort(key=lambda item: (-item[0], item[1]))
    return [q for _, _, q in scored[:2]]


def _anchored_pains(state, seed) -> list[dict]:
    wanted = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
              if t and t.strip()}
    focus = _idea_focus_tokens(state)
    analysis = getattr(state, "pain_point_analysis", None)
    matched = [pain for pain in (getattr(analysis, "pain_points", None) or [])
               if (getattr(pain, "title", None) or "").strip().lower() in wanted]
    matched.sort(
        key=lambda p: p.severity_score
        if isinstance(getattr(p, "severity_score", None), (int, float)) else -1.0,
        reverse=True)
    return [{
        "pain_title": (getattr(pain, "title", None) or "").strip(),
        "severity_band": _score_band(getattr(pain, "severity_score", None)),
        "severity_label": _severity_label(getattr(pain, "severity_score", None)),
        "mention_count": getattr(pain, "mention_count", None),
        "quotes": _ranked_quotes(pain, focus),
    } for pain in matched[:3]]


def _related_pains(state, seed, market_signal_title: str | None) -> list[dict]:
    """Near-miss pains: NOT anchored to the seed but sharing the pitch's own
    mechanism/problem vocabulary. The live failure this closes: two 16-mention pains
    that literally restated the pitch sat in the dossier while the verdict anchored
    to a 10-mention pain — unexplained, they read as the verdict grading the wrong
    essay. Each row carries a disposition so the dossier can never ambush the verdict.
    """
    terms = getattr(state, "user_idea_identity_terms", None) or {}
    focus = content_tokens(" ".join(
        t for key in ("mechanism", "problem") for t in (terms.get(key) or [])
        if isinstance(t, str)))
    if not focus:
        focus = content_tokens(getattr(state, "user_idea_brief", None) or "")
    if not focus:
        return []
    anchored = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
                if t and t.strip()}
    rows = []
    for pain in (getattr(getattr(state, "pain_point_analysis", None),
                         "pain_points", None) or []):
        title = (getattr(pain, "title", None) or "").strip()
        if not title or title.lower() in anchored:
            continue
        if len(focus & content_tokens(title)) < 2:
            continue
        sev = getattr(pain, "severity_score", None)
        rows.append({
            "pain_title": title,
            "severity_label": _severity_label(sev),
            "mention_count": getattr(pain, "mention_count", None),
            "_sev": sev if isinstance(sev, (int, float)) else -1.0,
            "note": ("risk" if market_signal_title
                     and title.lower() == market_signal_title.lower() else "unmatched"),
        })
    rows.sort(key=lambda r: r["_sev"], reverse=True)
    for row in rows:
        row.pop("_sev", None)
    return rows[:2]


def _critic_concern(seed) -> str | None:
    """The concessive half of the score critic's market_fit note, or None.

    The note opens with praise and concedes later ("… however, the moderate pain
    severity and competition …") — only the concession belongs under "What would
    kill it"; a note without one is a strength and must be skipped, not rendered.
    max_len is raised so the concession survives extraction (the default 170 cuts
    the live note before its 'however')."""
    reason = extract_criterion_reason(
        getattr(seed, "calibration_notes", None), "market_fit", max_len=600)
    if not reason:
        return None
    match = re.search(r"\b(however|but|though)\b[,\s]*", reason, re.IGNORECASE)
    if not match:
        return None
    concern = reason[match.end():].strip(" ,;:—–-")
    if not concern:
        return None
    concern = concern[0].upper() + concern[1:]
    return truncate_for_display(concern, 220)


def _market_signal_risk(state, seed, anchored_max_severity: float | None) -> dict | None:
    """Highest-severity pain the idea does NOT address that (a) shares ≥2 distinctive
    stemmed tokens with the pitch's mechanism+problem terms and (b) exceeds the seed's
    own anchored pains' max severity — a RELATIVE gate (severity_score is 0-1 here; an
    absolute threshold cleared by 0.01 on the live run and failed the next)."""
    terms = getattr(state, "user_idea_identity_terms", None) or {}
    focus = content_tokens(" ".join(
        t for key in ("mechanism", "problem") for t in (terms.get(key) or [])
        if isinstance(t, str)))
    if not focus:
        focus = content_tokens(getattr(state, "user_idea_brief", None) or "")
    if not focus:
        return None
    addressed = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
                 if t and t.strip()}
    floor = anchored_max_severity if anchored_max_severity is not None else 0.0
    best = None
    best_sev = floor
    analysis = getattr(state, "pain_point_analysis", None)
    for pain in (getattr(analysis, "pain_points", None) or []):
        title = (getattr(pain, "title", None) or "").strip()
        sev = getattr(pain, "severity_score", None)
        if not title or title.lower() in addressed:
            continue
        if not isinstance(sev, (int, float)) or sev <= best_sev:
            continue
        if len(focus & content_tokens(title)) < 2:
            continue
        best, best_sev = pain, sev
    if best is None:
        return None
    quotes = [q if isinstance(q, str) else str(q)
              for q in (getattr(best, "representative_quotes", None) or [])]
    return {
        "claim": MARKET_SIGNAL_PREFIX + (getattr(best, "title", None) or "").strip() + ".",
        "why_it_matters": None,
        "falsification": None,
        "quote": _QUOTE_LEAD_MARKERS.sub("", quotes[0]).strip() if quotes else None,
        "source": "market_signal",
        "pain_title": (getattr(best, "title", None) or "").strip(),
    }


def _refinement(state, seed) -> dict | None:
    """Q6: the Keeps/Changes/Because delta between the pitch and the evaluated seed.

    None when no stated clause drifted (no panel). Computed HERE, from persisted
    state, on every materialize — a value stashed at injection time would not
    survive regenerate/chat-seed re-materialization. `because` is deterministic
    best-effort: the highest-severity pain sharing ≥2 distinctive tokens with the
    changed clauses' ORIGINAL terms; None when nothing matches — never fabricated.
    """
    terms = getattr(state, "user_idea_identity_terms", None) or {}
    inferred = list(getattr(state, "user_idea_inferred_fields", None) or [])
    changed = seed_clause_drift(terms, seed, inferred)
    if not changed:
        return None
    stated = [clause for clause in ("mechanism", "audience", "problem", "delivery")
              if clause not in inferred and (terms.get(clause) or [])]
    kept = [clause for clause in stated if clause not in changed]

    changed_tokens = content_tokens(" ".join(
        t for clause in changed for t in (terms.get(clause) or [])
        if isinstance(t, str)))
    because = None
    best_sev = -1.0
    for pain in (getattr(getattr(state, "pain_point_analysis", None),
                         "pain_points", None) or []):
        title = (getattr(pain, "title", None) or "").strip()
        sev = getattr(pain, "severity_score", None)
        if not title or not isinstance(sev, (int, float)) or sev <= best_sev:
            continue
        if len(changed_tokens & content_tokens(title)) >= 2:
            because, best_sev = title, sev
    return {"kept": kept, "changed": changed, "because": because}


def _seed_display_composite(ideas: list, seed) -> int | None:
    """The workbench's own ranking composite for the seed, /100. A demoted seed is
    deliberately absent from the preview idea list (boundary-tested), so the page
    cannot derive its score there; compute it with the SAME contract the worker
    stamps on visible rows (angle_ranked_composite + visible-pool audience-fit
    coverage) — market_fit_score alone is a different scale and must not be shown
    beside the list's /100 numbers."""
    from ..utils.score_helpers import angle_ranked_composite, audience_fit_coverage
    if seed is None:
        return None
    visible = [i for i in ideas
               if (getattr(i, "candidate_status", "active") or "active") == "active"]
    try:
        score = angle_ranked_composite(seed, audience_fit_coverage(visible))
    except Exception:  # noqa: BLE001 — display-only, never blocks the block
        return None
    if not isinstance(score, (int, float)):
        return None
    return round(score * 100)


def _evaluated_idea(seed) -> dict:
    mechanism_summary = (getattr(seed, "innovation_angle", None)
                         or getattr(seed, "technical_approach", None) or "")
    # 280, not 200: at 200 both live samples cut mid-sentence with an ellipsis on the
    # panel's one substantive line.
    return {
        "name": getattr(seed, "solution_name", None),
        "value_proposition": truncate_for_display(
            getattr(seed, "value_proposition", None) or "", 280) or None,
        "mechanism_summary": truncate_for_display(mechanism_summary, 280) or None,
    }


def _anchored_severities(state, seed) -> list:
    """Severity scores of the pains the seed anchors to — hoisted because
    `_kill_risks`' market gate and `stronger_pain_count` share the same ceiling."""
    wanted = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
              if t and t.strip()}
    return [
        getattr(pain, "severity_score", None)
        for pain in (getattr(getattr(state, "pain_point_analysis", None),
                             "pain_points", None) or [])
        if (getattr(pain, "title", None) or "").strip().lower() in wanted
        and isinstance(getattr(pain, "severity_score", None), (int, float))
    ]


def _stronger_pain_count(state, seed, anchored_sevs: list) -> int:
    """Non-anchored pains whose severity exceeds the anchored max — the ruled-out
    bridge's "where else to look" number. Unanchored seed (no anchored severities)
    → 0, never "every pain in the market"."""
    if not anchored_sevs:
        return 0
    ceiling = max(anchored_sevs)
    anchored = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
                if t and t.strip()}
    count = 0
    for pain in (getattr(getattr(state, "pain_point_analysis", None),
                         "pain_points", None) or []):
        title = (getattr(pain, "title", None) or "").strip()
        sev = getattr(pain, "severity_score", None)
        if not title or title.lower() in anchored:
            continue
        if isinstance(sev, (int, float)) and sev > ceiling:
            count += 1
    return count


def _kill_risks(state, seed, anchored_sevs: list) -> list[dict]:
    """Labeled fallback chain, cap 3: adversarial review leads when present, the score
    critic's concession fills an empty card, and the market-signal risk — the strongest
    empirical entry — always survives the cap when found."""
    entries: list[dict] = []
    _verdict, typed_findings = effective_red_team_state(seed)
    if typed_findings is not None:
        for finding in typed_findings[:3]:
            claim = (finding.get("claim") if isinstance(finding, dict)
                     else getattr(finding, "claim", None))
            kind = (finding.get("kind") if isinstance(finding, dict)
                    else getattr(finding, "kind", None))
            if not isinstance(claim, str) or not claim.strip():
                continue
            entries.append({
                "claim": claim.strip(),
                "finding_kind": kind,
                "why_it_matters": None,
                "falsification": None,
                "quote": None,
                "source": "adversarial_review",
            })
    else:
        # Exact legacy fallback: old checkpoints carry prose caveats but no typed findings.
        for caveat in (getattr(seed, "red_team_caveats", None) or [])[:3]:
            entries.append({
                "claim": caveat if isinstance(caveat, str) else str(caveat),
                "why_it_matters": None,
                "falsification": None,
                "quote": None,
                "source": "adversarial_review",
            })
    if not entries:
        concern = _critic_concern(seed)
        if concern:
            entries.append({
                "claim": concern,
                "why_it_matters": None,
                "falsification": None,
                "quote": None,
                "source": "score_critic",
            })
    market = _market_signal_risk(
        state, seed, max(anchored_sevs) if anchored_sevs else None)
    if market is not None:
        entries = entries[:2] + [market]
    return entries[:3]


def reorder_anchored_pain_quotes(state, pain_dicts) -> None:
    """VALIDATE runs: inside the preview's detailed_pain_points, order the ANCHORED
    pains' representative_quotes by idea-focus relevance, in place. The dossier card
    slices the first three quotes — on the live run the only RUBS-specific excerpt
    sat fifth and never rendered, so the card under the verdict's own anchor showed
    three off-topic quotes. Non-anchored pains keep their own order (their cards
    describe the market, not the idea). Fail-soft no-op on any surprise."""
    try:
        if not getattr(state, "user_idea_text", None) or not pain_dicts:
            return
        ideas = getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or []
        seed = _find_marked(ideas, _MARKER_SEED)
        if seed is None:
            return
        wanted = {t.strip().lower() for t in (getattr(seed, "pain_points_addressed", None) or [])
                  if t and t.strip()}
        focus = _idea_focus_tokens(state)
        if not wanted or not focus:
            return
        for pain in pain_dicts:
            if not isinstance(pain, dict):
                continue
            if (pain.get("title") or "").strip().lower() not in wanted:
                continue
            quotes = pain.get("representative_quotes") or []
            if len(quotes) < 2:
                continue
            scored = [(len(focus & content_tokens(str(q))), idx, q)
                      for idx, q in enumerate(quotes)]
            if any(score for score, _, _ in scored):
                scored.sort(key=lambda item: (-item[0], item[1]))
                pain["representative_quotes"] = [q for _, _, q in scored]
    except Exception as exc:  # noqa: BLE001 — presentation ordering, never blocks materialize
        logger.warning(f"[Idea Check] anchored-quote reorder skipped: {exc}")


def build_idea_validation_block(state, entry_mode: str | None) -> dict | None:
    """Returns the block for a validate_idea run, or None for every other mode.

    `not_evaluated` (seed missing after a validate run — injection degraded) still
    returns a block: the report page must render the honest failure, never fall
    through to the discovery layout.
    """
    is_validate = ((entry_mode or "").strip().lower() == "validate_idea"
                   or bool(getattr(state, "user_idea_text", None)))
    if not is_validate:
        return None

    # Kept local so the pure outcome resolver and its maintenance runner can import
    # under the API image's minimal Python dependency set.
    from ..utils.validation.evidence_breadth import (
        compute_evidence_breadth,
        compute_evidence_confidence,
    )
    from ..validators.report_consistency import strip_vendor_echo

    ideas = getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or []
    seed = _find_marked(ideas, _MARKER_SEED)
    pivot_idea = _find_marked(ideas, _MARKER_PIVOT)

    niche_ctx = getattr(state, "niche_context", None)
    block: dict = {
        "provisional": True,
        "user_idea_text": getattr(state, "user_idea_text", None),
        "user_idea_brief": getattr(state, "user_idea_brief", None),
        "assumed_fields": list(getattr(state, "user_idea_inferred_fields", None) or []),
        "derived_market": getattr(niche_ctx, "niche_description", None),
        "derived_buyer": (getattr(niche_ctx, "resolved_primary_audience", None)
                          or getattr(niche_ctx, "user_target_audience", None)),
        "desk_limits": list(DESK_LIMITS),
        "experiment_ladder": [dict(r) for r in EXPERIMENT_LADDER],
        "next_experiment_index": 0,
        "pivot": dict(getattr(state, "user_idea_pivot", None) or {
            "attempted": False, "outcome": "not_attempted", "trigger_finding": None,
            "because": None, "keeps": None, "changes": None, "reason_not_shown": None,
            "ries_label": None, "name": None,
        }),
    }
    if block["pivot"].get("trigger_finding"):
        block["pivot"]["trigger_finding"] = _display_parity(
            block["pivot"]["trigger_finding"])

    if seed is None:
        block.update({
            "outcome": "not_evaluated",
            "idea_name": None,
            "headline": "We could not evaluate your idea in this market on this run.",
            "parts": [],
            "evidence_confidence": "Low",
            "evidence_confidence_reason":
                "The evaluation did not complete; nothing here grades your idea.",
            "breadth": None, "anchored_pains": [], "related_pains": [],
            "stronger_pain_count": 0,
            "unanchored_hypothesis": None,
            "incumbent_parity": None, "existing_equivalent": None, "competitors": [],
            "duplicate_of": None, "red_team_verdict": None,
            "red_team_findings": None, "kill_risks": [],
            "alternatives": _alternatives(ideas, seed=None, pivot=None),
            "seed_candidate_status": None, "seed_idea_id": None,
            "seed_idea_revision": None, "seed_purchasable": False,
            "seed_display_composite_score": None,
            "demotion_reason": None,
            "evaluated_idea": None, "refinement": None,
            "original_mechanism_parity": None,
        })
        return block

    parity_raw = (getattr(seed, "incumbent_parity", None) or "").strip()
    parity = parity_raw.lower()
    red_team_verdict, red_team_findings = effective_red_team_state(seed)
    red_team_raised_concerns = red_team_verdict in ("killed", "weakened")
    red_team_evidence_incomplete = (
        red_team_raised_concerns
        and red_team_findings is not None
        and not has_affirmative_red_team_findings(red_team_findings)
    )
    unanchored = bool(getattr(seed, "unanchored_hypothesis", False))
    demoted = (getattr(seed, "candidate_status", "active") or "active") != "active"
    breadth = compute_evidence_breadth(
        getattr(getattr(state, "pain_point_analysis", None), "pain_points", None) or [],
        getattr(state, "social_content", None),
        list(getattr(seed, "pain_points_addressed", None) or []),
    )
    anchored_rows = _anchored_pains(state, seed)
    anchored_quality = any(
        row["severity_band"] in ("moderate", "good", "strong") for row in anchored_rows)
    confidence, confidence_reason = compute_evidence_confidence(
        breadth, parity_raw, anchored_quality)
    idea_name = getattr(seed, "solution_name", None)

    refinement = _refinement(state, seed)
    brief_parity_raw = (getattr(state, "user_idea_brief_parity", None) or "").strip()
    brief_parity_hit = brief_parity_raw.lower().startswith(
        ("shipped", "partial", "substitute", "bundled"))

    # ── outcome enum (priority order) ──
    outcome, headline = resolve_idea_validation_outcome(
        idea_name=idea_name,
        demoted=demoted,
        parity_raw=parity_raw,
        unanchored=unanchored,
        red_team_verdict=red_team_verdict,
        refinement_present=refinement is not None,
        brief_parity_hit=brief_parity_hit,
        red_team_findings=red_team_findings,
    )

    # ── three parts ──
    if unanchored:
        problem_state, problem_answer, problem_detail = "not_found", "Not found", UNANCHORED_NOTE
    elif breadth is None or breadth.get("posts", 0) < 3:
        problem_state, problem_answer, problem_detail = "thin", "Thin", THIN_EVIDENCE_NOTE
    else:
        problem_state, problem_answer = "supported", "Supported"
        # The numbers live in the record line ONE statement below — repeating them
        # here made the same four stats stutter three times in ~120px.
        problem_detail = "Linked to real discussion in this run."

    if parity.startswith("shipped"):
        space_state, space_answer = "shipped", "Already shipped"
    elif parity.startswith("partial"):
        space_state, space_answer = "partial", "Partially shipped"
    elif parity.startswith(("substitute", "bundled")):
        space_state, space_answer = "adjacent", "Adjacent tools exist"
    elif parity.startswith("none"):
        # NOT "None found": the category-incumbents table two cards below lists named
        # tools, and the two truths must not read as a contradiction.
        space_state, space_answer = "none_found", "No direct equivalent"
    elif red_team_evidence_incomplete:
        space_state, space_answer = "evidence_incomplete", "Evidence incomplete"
    elif red_team_raised_concerns:
        space_state, space_answer = "review_concerns", "Concerns found"
    else:
        space_state, space_answer = "not_checked", "Not checked"
    if space_state == "none_found":
        space_detail = NONE_FOUND_NOTE
    elif space_state == "evidence_incomplete":
        space_detail = (
            "The direct-equivalent probe did not produce a result, and adversarial "
            "review returned incomplete evidence. No competitive conclusion was established."
        )
    elif space_state == "review_concerns":
        space_detail = (
            "The direct-equivalent probe did not produce a result, but adversarial "
            "review found material concerns. See What would kill it."
        )
    elif space_state == "not_checked":
        space_detail = "The direct-equivalent probe did not produce a result for this idea."
    else:
        space_detail = _display_parity(parity_raw)

    parts = [
        {"key": "problem_real", "state": problem_state,
         "answer": problem_answer, "detail": problem_detail},
        {"key": "space_occupied", "state": space_state,
         "answer": space_answer, "detail": space_detail},
        # Constant by design: Phase 2 measures demand; flipping this later must not
        # need a frontend change.
        {"key": "demand", "state": "not_measured",
         "answer": "Not measured", "detail": DEMAND_NOT_MEASURED},
    ]

    # ── competitors (web-verified incumbent map; snippet-derived prices) ──
    # FULL map — the old [:6] cap sliced off the very incumbent the verdict named
    # (run 6: Rentec Direct at index 6). Long tables are the component's problem
    # (it folds rows past 8), never a data problem.
    competitors = []
    for row in (getattr(state, "niche_incumbent_map", None) or []):
        if not isinstance(row, dict):
            continue
        competitors.append({
            "name": row.get("name"),
            "what_they_ship": row.get("focus"),
            "price_note": _normalize_price_note(row.get("pricing")),
            "price_caveat": PRICE_CAVEAT,
            "gap": _normalize_gap(row.get("gap")),
            "url": row.get("url") or row.get("source_url"),
        })
    trigger = _parse_parity_incumbent(parity_raw)
    if trigger is not None:
        vendor, evidence = trigger
        hit = next((c for c in competitors
                    if isinstance(c.get("name"), str) and _names_match(vendor, c["name"])),
                   None)
        if hit is not None:
            # Promote the REAL row (keeps its focus/gap/pricing) — never synthesize
            # a thinner duplicate of a vendor the map already covers. The row must
            # also SUBSTANTIATE the verdict: the map's focus is often broader than
            # the killing capability ("rent collection & tenant tracking" for a RUBS
            # verdict), so the parity evidence rides along as its own field.
            hit["verdict_trigger"] = True
            hit["verdict_evidence"] = _verdict_evidence_fragment(vendor, evidence)
            competitors.remove(hit)
            competitors.insert(0, hit)
        else:
            competitors.insert(0, {
                "name": vendor,
                "what_they_ship": strip_vendor_echo(vendor, evidence) or None,
                "price_note": None,
                "price_caveat": PRICE_CAVEAT,
                "gap": None,
                "url": None,
                "verdict_trigger": True,
                "synthesized": True,
            })

    duplicate_of = None
    dup_name = (getattr(seed, "duplicate_of", None) or "").strip()
    if dup_name:
        dup_idea = next(
            (i for i in ideas
             if (getattr(i, "solution_name", "") or "").strip().lower() == dup_name.lower()),
            None)
        duplicate_of = {"idea_id": getattr(dup_idea, "idea_id", None), "name": dup_name}

    scores = {
        criterion: _score_band(getattr(seed, f"{criterion}_score", None))
        for criterion in ("market_fit", "technical_feasibility", "novelty", "seo_scalability")
    }

    anchored_sevs = _anchored_severities(state, seed)
    kill_risks = _kill_risks(state, seed, anchored_sevs)
    market_signal_title = next(
        (k.get("pain_title") for k in kill_risks if k.get("source") == "market_signal"),
        None)
    related_rows = _related_pains(state, seed, market_signal_title)

    pivot_block = block["pivot"]
    if pivot_idea is not None:
        pivot_block["idea_id"] = getattr(pivot_idea, "idea_id", None)
        pivot_block["idea_revision"] = getattr(pivot_idea, "idea_revision", None)
        pivot_block.setdefault("name", getattr(pivot_idea, "solution_name", None))

    block.update({
        "outcome": outcome,
        "idea_name": idea_name,
        "headline": headline,
        "parts": parts,
        "score_bands": scores,
        "evidence_confidence": confidence,
        "evidence_confidence_reason": confidence_reason,
        "breadth": breadth,
        "anchored_pains": anchored_rows,
        "related_pains": related_rows,
        "stronger_pain_count": _stronger_pain_count(state, seed, anchored_sevs),
        "unanchored_hypothesis": unanchored,
        "incumbent_parity": parity_raw or None,
        "existing_equivalent": getattr(seed, "existing_equivalent", None),
        "competitors": competitors,
        "duplicate_of": duplicate_of,
        "red_team_verdict": red_team_verdict,
        "red_team_findings": [
            finding.model_dump(mode="json") if hasattr(finding, "model_dump") else finding
            for finding in (red_team_findings or [])
        ] if red_team_findings is not None else None,
        "kill_risks": kill_risks,
        "alternatives": _alternatives(ideas, seed=seed, pivot=pivot_idea),
        "seed_candidate_status": getattr(seed, "candidate_status", None),
        "seed_idea_id": getattr(seed, "idea_id", None),
        "seed_idea_revision": getattr(seed, "idea_revision", None),
        "seed_purchasable": not demoted,
        "seed_display_composite_score": _seed_display_composite(ideas, seed),
        "demotion_reason": (_display_embedded(_demotion_reason(state, seed), parity_raw)
                            if demoted else None),
        "evaluated_idea": _evaluated_idea(seed),
        "refinement": refinement,
        # HIT-only: "none found" stays state-side telemetry — rendering "Your original
        # mechanism: none found" would read as nonsense, and the frontend never
        # string-sniffs prose to decide.
        "original_mechanism_parity": brief_parity_raw if brief_parity_hit else None,
    })
    return block


def _alternatives(ideas: list, seed, pivot) -> dict:
    pool = [i for i in ideas
            if i is not seed and i is not pivot
            and (getattr(i, "candidate_status", "active") or "active") == "active"]
    # named_buyer_count: alternatives whose audience_fit judgment says they primarily
    # serve the buyer the USER NAMED — the same field the workbench's "Adjacent
    # audience" chip reads, so the two numbers can never contradict each other.
    # (The old source_segment equality measured generation-cell provenance, which the
    # sentence "target the buyer you named" was never entitled to claim.) None when
    # the pool carries no audience_fit verdicts at all (legacy runs): inconclusive,
    # the sentence is omitted, never guessed.
    fits = [getattr(i, "audience_fit", None) for i in pool]
    named_buyer = (sum(1 for f in fits if f is True)
                   if any(f is not None for f in fits) else None)
    top = []
    for idea in pool[:5]:
        top.append({
            "idea_id": getattr(idea, "idea_id", None),
            "name": getattr(idea, "solution_name", None),
            "one_liner": (getattr(idea, "value_proposition", None)
                          or getattr(idea, "description", "") or "")[:160],
        })
    return {"count": len(pool), "named_buyer_count": named_buyer, "top": top}
