"""Offline regression of the idea_validation block against the first live run.

The fixture is the trimmed 056b2c68 checkpoint; `expected_block_v1` is the block the
live run actually shipped. The quality pass deliberately changes a known key set —
everything OUTSIDE that set must keep reproducing the live block byte-for-byte.
"""

import json

from nicheiq.report.idea_validation_block import build_idea_validation_block

from .fixture_056b2c68 import expected_block_v1, state_from_fixture

# Keys the Research Quality Pass deliberately changes (asserted per-PR in the
# feature tests). Everything else is pinned to the live run.
QUALITY_PASS_KEYS = {
    "kill_risks",                    # Q2 fallback chain
    "evidence_confidence",           # Q3 anchored-quality cap
    "evidence_confidence_reason",    # Q3 appended reason
    "anchored_pains",                # Q3 sort / quote re-rank / mention_count
    "headline",                      # Q6 refinement-aware swap
    "evaluated_idea",                # Q6 (new)
    "refinement",                    # Q6 (new)
    "original_mechanism_parity",     # Q1 (new, display-only)
    "competitors",                   # design audit: price_note normalization
    "parts",                         # polish pass: de-stuttered detail + "No direct equivalent"
    "desk_limits",                   # polish pass: limit 3 now maps to on-screen numbers
    "experiment_ladder",             # polish pass: rung-1 gains the "kill" verb
    "related_pains",                 # polish pass (new): near-miss pains with dispositions
    "stronger_pain_count",           # Maya pass (new): ruled-out bridge count
    "alternatives",                  # findings pass: named_buyer_count replaces same_buyer_count
    "seed_display_composite_score",  # findings pass (new): ruled-out header score
}


def test_fixture_reproduces_live_block_outside_quality_pass_keys():
    rebuilt = json.loads(json.dumps(
        build_idea_validation_block(state_from_fixture(), "validate_idea")))
    expected = expected_block_v1()

    stable_expected = {k: v for k, v in expected.items() if k not in QUALITY_PASS_KEYS}
    stable_rebuilt = {k: v for k, v in rebuilt.items() if k not in QUALITY_PASS_KEYS}
    assert stable_rebuilt == stable_expected


def _live_block() -> dict:
    return json.loads(json.dumps(
        build_idea_validation_block(state_from_fixture(), "validate_idea")))


def test_live_kill_card_now_populated_with_provenance():
    """Q2: the live run rendered NO kill card (empty red team). The chain now fills it
    with the critic's concession + the market-signal pain, each labeled."""
    from nicheiq.report.idea_validation_block import MARKET_SIGNAL_PREFIX

    risks = _live_block()["kill_risks"]
    assert [r["source"] for r in risks] == ["score_critic", "market_signal"]
    market = risks[1]
    assert market["claim"].startswith(MARKET_SIGNAL_PREFIX)
    assert "Fully automated replies publish confidently wrong answers" in market["claim"]
    assert market["quote"]
    # The critic entry is the CONCESSION, never the praise half of the note.
    assert "addresses a validated pain" not in risks[0]["claim"].lower()


def test_live_confidence_capped_at_moderate():
    """Q3: 9-post breadth anchored to a severity-0.43 pain must not read High."""
    from nicheiq.utils.validation.evidence_breadth import MILD_ANCHOR_NOTE

    block = _live_block()
    assert block["evidence_confidence"] == "Moderate"
    assert block["evidence_confidence_reason"].endswith(MILD_ANCHOR_NOTE)
    assert expected_block_v1()["evidence_confidence"] == "High"  # the defect being fixed


def test_live_anchored_quotes_reranked_and_deduped():
    """Q3: mechanism-relevant quote first; the off-topic REST-API rant not promoted;
    the byte-identical twin quotes collapse."""
    rows = _live_block()["anchored_pains"]
    assert rows and rows[0]["mention_count"] == 12
    quotes = rows[0]["quotes"]
    assert "already answered" in quotes[0]
    assert all("REST" not in q and "API" not in q for q in quotes)
    assert len({q.lstrip(">").strip() for q in quotes}) == len(quotes)


def test_live_refinement_disclosed_as_refinement():
    """Q6: the live seed kept audience/problem/delivery but repositioned the mechanism —
    the panel must say so, and the headline must scope to the EVALUATED mechanism."""
    block = _live_block()
    assert block["refinement"] == {
        "kept": ["audience", "problem", "delivery"],
        "changed": ["mechanism"],
        "because": "Fully automated replies publish confidently wrong answers",
    }
    assert block["evaluated_idea"]["name"] == "ReplyMatch Policy-Safe Reddit Response Desk"
    assert block["evaluated_idea"]["mechanism_summary"]
    assert "the mechanism we evaluated" in block["headline"]
    assert "ships your mechanism" not in block["headline"]
    assert block["original_mechanism_parity"] is None  # probe hasn't run on this state


def test_live_brief_parity_is_display_only():
    """Q1 invariant: a brief-parity finding changes the panel + headline wording but
    NEVER outcome, confidence, or the space_occupied part."""
    state = state_from_fixture()
    state.user_idea_brief_parity = "substitute (ReplyGuy): AI drafts Reddit replies"
    with_finding = json.loads(json.dumps(
        build_idea_validation_block(state, "validate_idea")))
    without = _live_block()

    assert with_finding["original_mechanism_parity"] == (
        "substitute (ReplyGuy): AI drafts Reddit replies")
    assert "original mechanism already has tools shipping" in with_finding["headline"]
    for key in ("outcome", "evidence_confidence", "evidence_confidence_reason",
                "parts", "incumbent_parity", "kill_risks"):
        assert with_finding[key] == without[key], key


def test_live_price_column_normalized():
    """Design audit: real prices verbatim, bare tier words labeled, unknowns to None
    (the column renders an em-dash) — words must not masquerade as prices. Maya pass:
    the [:6] cap is gone, so all 12 map rows emit."""
    prices = [c["price_note"] for c in _live_block()["competitors"]]
    assert prices == ["$15-49/mo", "$99+/mo", "$99+/mo", "enterprise tier",
                      "$19-199/mo", "Free or $9.99/mo",
                      None, None, "enterprise tier", None, None, None]
    # The first six rows stay pinned to the live run.
    expected = expected_block_v1()["competitors"]
    rebuilt = _live_block()["competitors"]
    for exp, got in zip(expected, rebuilt):
        for key in ("name", "what_they_ship", "gap", "url", "price_caveat"):
            assert got[key] == exp[key]


def test_live_parity_none_found_synthesizes_no_row():
    """Maya pass: 'none found' parity names no vendor — the table must gain no
    verdict-trigger or synthesized row and keep the map's own order."""
    competitors = _live_block()["competitors"]
    assert len(competitors) == 12
    assert not any(c.get("verdict_trigger") or c.get("synthesized") for c in competitors)
    assert competitors[0]["name"] == "Buffer"


def test_live_related_pains_carry_dispositions():
    """Polish pass: the near-miss pain (the automated-replies pain shares the pitch's
    mechanism vocabulary) surfaces WITH its disposition instead of ambushing the
    verdict from the dossier."""
    block = _live_block()
    related = block["related_pains"]
    assert related and related[0]["pain_title"] == (
        "Fully automated replies publish confidently wrong answers")
    assert related[0]["note"] == "risk"  # same pain the kill card flags
    assert related[0]["severity_label"] == "medium"  # 0.66 on the dossier's cutoffs


def test_live_parts_copy_reconciled():
    """Polish pass: no stat stutter in the problem row; the space row can never
    contradict the category table two cards below."""
    from nicheiq.report.idea_validation_block import DEMAND_NOT_MEASURED

    parts = {p["key"]: p for p in _live_block()["parts"]}
    assert parts["problem_real"]["detail"] == "Linked to real discussion in this run."
    assert parts["space_occupied"]["answer"] == "No direct equivalent"
    assert parts["demand"]["detail"] == DEMAND_NOT_MEASURED


def test_fixture_seed_shape_is_the_live_seed():
    state = state_from_fixture()
    seeds = [i for i in state.idea_generation.solution_ideas
             if getattr(i, "source_frame", None) == "user_seed"
             and getattr(i, "generation_operation_id", None) == "validate"]
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed.solution_name == "ReplyMatch Policy-Safe Reddit Response Desk"
    assert (seed.incumbent_parity or "").startswith("none")
    # Q2's critic fallback depends on this surviving the trim.
    assert seed.calibration_notes


def test_live_alternatives_named_buyer_inconclusive_on_legacy_run():
    """Findings pass: the buyer sentence now counts audience_fit=True (the same field
    the workbench's Adjacent-audience chip reads). The fixture run predates the
    field → None (inconclusive, sentence omitted), never a guessed number."""
    alts = _live_block()["alternatives"]
    assert alts["count"] == 10
    assert alts["named_buyer_count"] is None
    assert "same_buyer_count" not in alts


def test_live_seed_display_composite_score_matches_workbench_scale():
    """The seed's /100 score computed with the workbench's own ranking contract
    (angle composite + visible-pool audience-fit coverage)."""
    assert _live_block()["seed_display_composite_score"] == 53
