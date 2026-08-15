"""Judge-eval: can `_semantic_seed_identity_matches` carry the authority the reorder would give it?

RUN IT: `pytest tests/integration/test_seed_identity_judge_eval.py -m integration -s`
(the suite's autouse `_no_live_llm` fixture blocks network by default; `@pytest.mark.integration`
opts out — roughly 20c for the full sweep.)

COST WARNING — the hole is CLOSED as of 2026-08-15, and the sequence is worth knowing.

Until that date this header claimed the sweep "costs money only when you ask for it", and that
was false the whole time. Nothing FILTERED the marker: `addopts` carried no `-m`, and
`tests/conftest.py:305` reads the marker only to LIFT the network block. So a plain `pytest` —
the command CLAUDE.md documented as "All tests" — ran this file against the live provider, about
30 calls at REPEATS=1. Measured rather than read: the S13 test below passed inside the default
full suite, which it cannot do without a live judge (with the network blocked every candidate is
refused and its must-pass assertion goes red).

`pyproject.toml`'s `addopts` now carries `-m "not integration"`. Verified both directions on
2026-08-15: a bare `pytest` reports `5911 passed, 5 deselected` and executes nothing in this
file, while `-m integration` on the command line overrides the ini and collects all 5.

**The marker is the opt-in, not the path.** `pytest tests/integration/` alone now deselects
everything and runs nothing — which is safe, but silent, so pass `-m integration` when you mean
it. Keep this paragraph honest if `addopts` changes again: it is the sixth false claim this
subsystem has had to correct in a comment, and two of those were written by rounds whose job was
correcting false comments.

THE DECISION THIS EXISTS TO MAKE. The proposed authority reorder demotes the two lexical semantic
gates (`unpitched_core_dependencies`, `seed_clause_drift`) from unilateral vetoes to labelled
evidence, and lets the LLM judge issue the only birth verdict. Its entire premise is "the judge
catches what the lexical gates caught" — a claim nobody has ever measured. Four independent
investigations endorsed the reorder; one of them tried to construct a counterexample and failed.
"I could not think of one" is not evidence, and the cost of being wrong is a confident Go verdict
on a product the user never submitted.

So: run the SAME corpus the deterministic suite uses, against the real judge, and let three
numbers decide.

  * blocks all 8 substitutions        -> required. ANY miss kills the reorder outright.
  * accepts all 3 known false positives -> required, or the reorder does not fix what it is for.
  * accepts both must-pass elaborations -> required, incl. the category-instance case that the
                                           deterministic layer cannot pass by construction.

Plus STABILITY: this repo documents its own critic as non-deterministic at temperature 0, so a
verdict that flips between runs is a finding. If any case flips, `n=3` majority stops being
optional and becomes a precondition of the reorder.

A FAILING RESULT IS A GOOD OUTCOME. It costs cents and keeps a veto that is over-firing but
sound, instead of discovering the gap when a user is handed a verdict on someone else's product.

STATUS: the reorder SHIPPED on 2026-08-14. This file is no longer deciding whether to do it —
it is the regression gate on the arrangement that now runs in production, and the two numbers
it protects are opposite failure directions. Re-run it whenever the judge's model, tier,
reasoning_effort, prompt, or the advisory-evidence block changes.
"""

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration

_CORPUS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "seed_identity_corpus.json").read_text()
)

# How many times to re-ask each case. 1 = accuracy sweep only; >1 also measures flip rate.
#
# MEASURED 2026-08-14 at REPEATS=3 on `report_structured_llm` (grok-4.3, reasoning_effort="none"),
# BEFORE the reorder, judging on the rule text alone:
#   substitutions blocked 8/8 · known false positive accepted 1/1 · elaboration kept 2/2
#   flip rate 0/11 — every verdict identical across three runs at temperature 0.
#
# RE-MEASURED 2026-08-14 at REPEATS=1, AFTER the reorder, with the ADVISORY EVIDENCE block in
# the prompt — i.e. the arrangement that actually ships:
#   substitutions blocked 8/8 · known false positive accepted 1/1 · elaboration kept 2/2
# The block changed nothing on this corpus, in either direction, which is the result that had
# to be checked rather than assumed:
#   * `instances_named_ok` was accepted while its advisory block carried the heaviest evidence
#     in the corpus (4 unpitched routes, clause drift ['mechanism'], retention 12/23 against a
#     floor of 14). The judge did not inherit the lexical layer's over-blocking.
#   * `scope_global` was still blocked while its advisory block read "none / none". An empty
#     evidence block is not read as an endorsement.
# NOT RE-MEASURED: flip rate with the advisory block (that needs REPEATS=3, ~66 calls). The
# block is deterministic given the candidate, so the input is as stable as it was before, but
# this is an assumption, not a measurement — raise REPEATS before treating it as one.
#
# Left at 1 so a routine re-check after a code change stays cheap (~22 calls). Raise it to 3
# whenever the JUDGE ITSELF changes — a different model, tier, or reasoning_effort — because
# that is what could reintroduce instability, and a gate that flips cannot be the sole authority
# on a paid verdict without n=3 majority.
#
# NOTE ON TIER: two audits recommended raising the judge to a reasoning tier before giving it
# sole authority. The measurement above says the speed tier is already accurate AND stable on
# this corpus, so that change is not currently justified — re-measure before making it, rather
# than hardening a layer that has no observed defect.
REPEATS = 1


def _crew():
    """A crew shell with only what `_semantic_seed_identity_matches` touches."""
    from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    return crew


def _judge(case: dict) -> bool:
    """Judge one case EXACTLY as birth calls it — advisory evidence included.

    Passing `evidence=None` here would measure a prompt that no longer ships. It would also
    miss the sharpest risk in the whole reorder: the heaviest evidence in this corpus
    (`instances_named_ok`: 4 unpitched routes, clause drift, retention 12/23 under a floor of
    14) sits on a case that MUST be accepted. If handing the judge the lexical findings makes
    it inherit the lexical layer's over-blocking, that case is where it shows up.

    THIS SENTENCE WAS FALSE UNTIL 2026-08-15, and its falsehood was the whole of S17. Birth
    ran a corrective rewrite of the candidate's copy BEFORE collecting the evidence and
    calling the judge, so every number in this file described a candidate production did not
    judge. Measured on the arrangement that actually shipped, the first sweep below reads
    **substitutions blocked 3/8, not 8/8**: `scope_global` trips no clause drift so the
    rewrite never fired on it, `route_replacement` and `route_swap_named` fired and failed
    (rollback), and the other five were rewritten toward the pitch until the judge accepted
    them. The rewrite is gone and this function is faithful again — 8/8 · 1/1 · 2/2,
    re-measured 2026-08-15 after the removal. Keep it that way: if a pass is ever added
    between the generator and the judge, the honest fix is to run it here too, and then to
    watch what these three numbers do.
    """
    from nicheiq.utils.seed_fidelity import seed_identity_evidence

    candidate = SimpleNamespace(**case["candidate"])
    evidence = seed_identity_evidence(
        case["pitch"], candidate,
        case.get("identity_terms"), case.get("inferred_fields"),
    )
    return _crew()._semantic_seed_identity_matches(
        case["pitch"], candidate, evidence=evidence)


def _sweep(cases, expect_same_product: bool, label: str):
    """Returns (rows, correct, total). Prints a per-case table — the artifact you actually read."""
    rows = []
    for case in cases:
        verdicts = [_judge(case) for _ in range(REPEATS)]
        agreed = len(set(verdicts)) == 1
        got = Counter(verdicts).most_common(1)[0][0]
        rows.append((case["id"], got == expect_same_product, got, agreed))
    correct = sum(1 for _, ok, _, _ in rows if ok)   # filter on ok — counting every
    # row made the printed table disagree with the assertions (caught 2026-08-14)
    print(f"\n  {label}: {correct}/{len(rows)}")
    for cid, ok, got, agreed in rows:
        flag = "" if ok else "   <-- WRONG"
        stab = "" if agreed else f"   (FLIPPED across {REPEATS} runs)"
        print(f"     {cid:22} judge_says_same_product={str(got):5}{flag}{stab}")
    return rows, correct, len(rows)


def test_judge_blocks_every_substitution():
    """The reorder-killer. These are products the user did NOT submit."""
    cases = [c for c in _CORPUS["adversarial"] if c["axis"] != "must_pass"]
    rows, correct, total = _sweep(cases, expect_same_product=False, label="substitutions blocked")
    missed = [cid for cid, ok, _, _ in rows if not ok]
    assert not missed, (
        f"the judge ACCEPTED {missed} as the same product — the authority reorder is UNSAFE, "
        "because these are exactly the cases the lexical gates exist to stop")


def test_judge_accepts_the_known_false_positives():
    """The three production kills. If the judge refuses these too, the reorder fixes nothing."""
    cases = [p for p in _CORPUS["honest"]
             if p["kind"] == "reconstructed_from_log" and p.get("judge_eval", True)]
    assert cases, "no judge-valid reconstructions left in the corpus"
    rows, correct, total = _sweep(cases, expect_same_product=True,
                                  label="known false positives accepted")
    refused = [cid for cid, ok, _, _ in rows if not ok]
    assert not refused, (
        f"the judge also refuses {refused} — moving authority to it would preserve the very "
        "false positives the reorder is meant to remove")


def test_judge_accepts_legitimate_elaboration():
    """Including the category-instance case the deterministic layer cannot pass by construction
    (deciding DeepSeek is an 'AI assistant' is world knowledge). This is the reorder's whole
    argument: only the judge can rule on it."""
    cases = [c for c in _CORPUS["adversarial"] if c["axis"] == "must_pass"]
    rows, correct, total = _sweep(cases, expect_same_product=True,
                                  label="legitimate elaboration kept")
    refused = [cid for cid, ok, _, _ in rows if not ok]
    assert not refused, (
        f"the judge refuses {refused} — it would inherit the over-blocking it was supposed to fix")


# THE S13 TEST THAT STOOD HERE WAS DELETED WITH ITS SUBJECT (2026-08-15, S17).
#
# `test_the_judge_is_the_check_on_a_candidate_whose_repair_FAILED` measured the judge on the
# eight corpus cases whose corrective rewrite came back UNCLEAN, and found substitutions
# refused 7/7 and the must-pass elaboration accepted 1/1. Those numbers were right, and they
# were the wrong half of the population: the repair rolls back when it fails, so that arm was
# always the unrepaired candidate, which the three sweeps above already judge. The arm nobody
# had measured was the one where the repair SUCCEEDS — and there the judge accepted five of
# seven substitutions it refuses unrepaired. The rewrite is removed; there is no repair-failed
# population left to sample, and `_judge` above is now what birth does. Full table in
# docs/SEED_IDENTITY_REMEDIATION.md, "ROUND 16".


def test_judge_verdicts_are_stable_enough_to_be_authoritative():
    """Skipped unless REPEATS > 1. Temperature 0 is not a determinism guarantee, and this repo
    already documents that for its calibration critic. A gate that flips cannot be the sole
    authority on a paid promise without n=3 majority."""
    if REPEATS < 2:
        pytest.skip("set REPEATS > 1 to measure flip rate (costs REPEATS x ~22 calls)")
    unstable = []
    pool = _CORPUS["adversarial"] + [
        p for p in _CORPUS["honest"]
        if p["kind"] == "reconstructed_from_log" and p.get("judge_eval", True)]
    for case in pool:
        verdicts = [_judge(case) for _ in range(REPEATS)]
        if len(set(verdicts)) > 1:
            unstable.append(case["id"])
    print(f"\n  flip rate: {len(unstable)}/{len(pool)} unstable: {unstable}")
    assert not unstable, (
        f"{unstable} flipped at temperature 0 — require n=3 majority before the judge becomes "
        "the sole birth authority")
