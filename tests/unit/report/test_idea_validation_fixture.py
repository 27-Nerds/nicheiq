"""Offline regression of the idea_validation block against the first live run.

The fixture is the trimmed 056b2c68 checkpoint; `expected_block_v1` is the block the
live run actually shipped. The quality pass deliberately changes a known key set —
everything OUTSIDE that set must keep reproducing the live block byte-for-byte.
"""

import json
import os

import pytest

from nicheiq.report.idea_validation_block import build_idea_validation_block

from .fixture_056b2c68 import expected_block_v1, state_from_fixture
from .fixture_idea_check_states import CAPTURES, generate_block, golden_path

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
    "red_team_findings",             # RT-1 (new): typed red-team evidence kinds
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
    # A5 R2: "No direct equivalent" asserted a fact about the market; the run knows only
    # that its own queries (built from this idea's wording) returned nothing.
    assert parts["space_occupied"]["answer"] == "No equivalent surfaced"
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


# ══════════════════════════════════════════════════════════════════════════════════════
# THE OTHER CAPTURED STATES — one per branch tuple `056b2c68` cannot reach.
#
# The machinery above is right and was pointed at too little: ONE run in ONE state, held
# byte-exact. A mutation campaign over `report/idea_validation_block.py` left 476
# survivors, and the triage found no mutmut noise and no guard elsewhere — the survivors
# are, almost exactly, the branches this run does not take. `056b2c68` has parity
# "none found", `red_team_verdict: None`, no typed findings, an active seed, an empty
# `idea_ruled_out`, a `not_attempted` pivot, and a trim that dropped `audience_fit`, so
# `named_buyer_count` is `None`. Everything on the other side of each of those is
# unasserted, and no assertion written against THIS state can reach it.
#
# So the remedy is more captured states through the SAME byte-exact machinery, not
# stronger assertions about this one. See `fixture_idea_check_states` for provenance,
# the trim recipe, and why each run is here.
# ══════════════════════════════════════════════════════════════════════════════════════


def _check_golden(slug: str) -> dict:
    generated = generate_block(slug)
    path = golden_path(slug)
    if os.environ.get("IDEA_VALIDATION_FIXTURE_REGEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(generated, indent=1) + "\n")

    assert json.loads(path.read_text()) == generated, (
        f"The vendored golden for the captured `{slug}` run ({path.name}) has drifted "
        "from what build_idea_validation_block emits for it. If the change is deliberate, "
        "regenerate:\n  IDEA_VALIDATION_FIXTURE_REGEN=1 pytest "
        "tests/unit/report/test_idea_validation_fixture.py\n"
        "Do NOT hand-edit the JSON: a golden in a shape the pipeline cannot produce is "
        "exactly what made three rounds of report assertions pass vacuously."
    )
    return generated


@pytest.mark.parametrize("slug", sorted(CAPTURES))
def test_captured_state_block_matches_the_real_builder(slug):
    """Byte-exact drift, per captured branch tuple. This one assertion is worth more than
    any list of field checks: it fails on ANY change to ANY key of the block for a state
    the pipeline demonstrably produced, and it names the state that changed."""
    _check_golden(slug)


def _tuple_of(block: dict) -> tuple:
    """The branch coordinates a state exercises — what makes it worth its own capture."""
    parts = {p["key"]: p["state"] for p in block["parts"]}
    return (
        block["outcome"],
        parts["space_occupied"],
        block["red_team_verdict"],
        block["red_team_findings"] is not None,
        block["seed_candidate_status"],
        block["pivot"]["outcome"],
        tuple(dict.fromkeys(k["source"] for k in block["kill_risks"])),
    )


def test_each_captured_state_takes_a_path_no_other_capture_takes():
    """A fixture family is only as good as its spread. Six states that all land on
    `worth_testing / none_found` would look like coverage and buy nothing, and the way
    that happens is by accident — a checkpoint picked for one field while five others
    quietly agree with a state already committed.

    Pairwise-distinct branch tuples is the property that cannot be satisfied by accident,
    and it is what makes the deletion of any one capture a visible loss rather than a
    silent one.
    """
    tuples = {slug: _tuple_of(_check_golden(slug)) for slug in CAPTURES}
    assert len(set(tuples.values())) == len(tuples), (
        "two captured states take the same path through the block: "
        f"{sorted(tuples.items(), key=lambda kv: kv[1])}"
    )


def test_the_captures_reach_the_families_the_legacy_fixture_cannot():
    """Named, because "distinct" alone would be satisfied by six near-misses.

    Each value below is absent from `idea_check_056b2c68.json` — it is the reason its
    run was captured, stated where a future reader can check it rather than only in a
    docstring.
    """
    blocks = {slug: _check_golden(slug) for slug in CAPTURES}
    outcomes = {b["outcome"] for b in blocks.values()}
    spaces = {p["state"] for b in blocks.values() for p in b["parts"]
              if p["key"] == "space_occupied"}

    # The legacy fixture reaches exactly `worth_testing` / `none_found`.
    legacy = _live_block()
    assert legacy["outcome"] == "worth_testing"
    assert {"occupied", "ruled_out", "premise_unproven"} <= outcomes
    assert {"shipped", "partial", "review_concerns"} <= spaces

    # A demoted seed: the `ruled_out` branch outranks a `shipped` parity, the seed stops
    # being purchasable, and the demotion reason is quoted back with its embedded parity
    # stamp humanized (`Already well-served — ` -> `Already well-served: `).
    demoted = blocks["demoted_rentec_ruled_out"]
    assert demoted["seed_candidate_status"] == "demoted"
    assert demoted["seed_purchasable"] is False
    assert demoted["incumbent_parity"].startswith("shipped by Rentec Direct")
    assert demoted["outcome"] == "ruled_out"
    assert demoted["demotion_reason"].startswith("Already well-served: ")
    assert " — " not in demoted["demotion_reason"]

    # Typed red-team findings: the `_kill_risks` arm that carries `finding_kind`, and the
    # affirmative-evidence headline. The legacy run has `red_team_findings is None`.
    typed = blocks["typed_findings_killed"]
    assert [f["kind"] for f in typed["red_team_findings"]] == [
        "verified_incumbent_overlap", "verified_free_or_bundled_alternative",
        "evidence_gap"]
    assert all(r["source"] == "adversarial_review" for r in typed["kill_risks"])
    assert [r["finding_kind"] for r in typed["kill_risks"]] == [
        "verified_incumbent_overlap", "verified_free_or_bundled_alternative",
        "evidence_gap"]
    assert "found verified counterevidence" in typed["headline"]

    # …and the other arm of the same verdict: killed with PROSE caveats only, where
    # `has_affirmative_red_team_findings` is false because the record is legacy rather
    # than because the evidence was weak. Same verdict word, different sentence.
    unverified = blocks["none_found_killed_unverified"]
    assert unverified["red_team_verdict"] == "killed"
    assert unverified["red_team_findings"] is None
    assert "could not confirm the premise" in unverified["headline"]
    assert all(r.get("finding_kind") is None for r in unverified["kill_risks"])

    # An ACCEPTED pivot: a second `user_seed` candidate under `validate_pivot`, whose
    # identity is stamped onto the pivot record — and which is still excluded from the
    # market's alternatives.
    pivoted = blocks["pivot_accepted_teamsnap"]
    assert pivoted["pivot"]["outcome"] == "accepted"
    assert pivoted["pivot"]["idea_id"] and pivoted["pivot"]["name"]
    assert pivoted["pivot"]["idea_revision"] is not None
    assert all(row["idea_id"] != pivoted["pivot"]["idea_id"]
               for row in pivoted["alternatives"]["top"])

    # A rejected pivot's `trigger_finding` renders humanized, while state keeps the stamp.
    hubdoc = blocks["partial_hubdoc_killed"]
    assert hubdoc["pivot"]["outcome"] == "rejected"
    assert hubdoc["pivot"]["trigger_finding"] == (
        "Hubdoc users send auto-reminders via Slack every Monday morning for receipts")
    assert hubdoc["incumbent_parity"].startswith("partial by Hubdoc: Hubdoc ")


def test_a_captured_pool_carries_an_odd_named_buyer_count():
    """`named_buyer_count` is `sum(1 for f in fits if f is True)`, and until these
    captures landed its ONLY two committed values were `None` (the legacy trim dropped
    `audience_fit`) and `0` — the exact two values at which the arithmetic is invisible.
    `sum(2 …)`, `sum(0 …)` and `len(fits)` all agree with the real expression at 0.

    A pool with an odd count ≥ 1 separates all three at once, and the byte-exact goldens
    above then hold it for free. Asserted here rather than left implicit so a recapture
    that happens to land on all-even counts fails loudly instead of quietly giving the
    doubling mutant its cover back.
    """
    counts = {slug: _check_golden(slug)["alternatives"]["named_buyer_count"]
              for slug in CAPTURES}
    assert all(isinstance(c, int) for c in counts.values()), counts
    assert any(c >= 1 and c % 2 == 1 for c in counts.values()), (
        f"no captured pool separates sum(1 …) from sum(2 …) / len(fits): {counts}")
    # The legacy fixture is the None case; keep the contrast explicit.
    assert _live_block()["alternatives"]["named_buyer_count"] is None
