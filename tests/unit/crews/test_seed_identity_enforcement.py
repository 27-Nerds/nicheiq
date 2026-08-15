"""Stated-clause preservation for "Check my idea" seeds.

The evaluated project must BE the pitched product — a Chrome-extension pitch yields a
Chrome-extension project. That is enforced in ONE place: the generation-lens constraint
block, which constrains the generator BEFORE the copy exists.

It used to be enforced in a second place as well — a post-birth corrective rewrite of
eight identity-copy fields, run whenever `seed_clause_drift` fired. That was removed on
2026-08-15 (S17) after it was measured LAUNDERING substitutions past the birth judge:
the judge refuses 7/7 of the corpus's adversarial substitutions as the generator produced
them, and only 2/7 after the rewrite had rewritten them toward the pitch. The two
`test_the_judge_*` tests below are what replaced it, and they are deliberately written
as properties of the birth path rather than as assertions about a named method — any
future mutation of the candidate between the generator and the judge turns them red,
whatever it is called.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.crews.unified_solution_crew import (
    UnifiedSolutionCrew,
    _stated_clause_lens_block,
)

TERMS = {
    "mechanism": ["drafts Reddit replies"],
    "audience": ["community managers", "small SaaS companies"],
    "problem": [],
    "delivery": ["Chrome extension"],
}


# ── lens constraint block ──

def test_lens_block_empty_without_terms():
    assert _stated_clause_lens_block(None) == ""
    assert _stated_clause_lens_block({}) == ""
    assert _stated_clause_lens_block({"mechanism": [], "audience": []}) == ""


def test_lens_block_lists_stated_clauses_only():
    block = _stated_clause_lens_block(TERMS)
    assert "STATED-IDENTITY CONSTRAINTS" in block
    assert "drafts Reddit replies" in block
    assert "Chrome extension" in block
    assert "community managers; small SaaS companies" in block
    assert "problem" not in block.split("Every variant")[0].lower().replace(
        "the pain it removes", "")  # empty clause emits no line
    assert "stays a Chrome extension" in block


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    return crew


# ── S17: NOTHING MAY REWRITE THE CANDIDATE BETWEEN THE GENERATOR AND THE JUDGE ──────────
#
# A corrective rewrite used to sit exactly here, and these two tests are the shape of the
# measurement that removed it (docs/SEED_IDENTITY_REMEDIATION.md, "ROUND 16"). They drive
# the REAL `execute_seed_pipeline` birth sequence with only the transport replaced, and
# they assert two properties rather than the absence of a method name:
#
#   1. the object the judge rules on is field-identical to the object the generator
#      produced, and
#   2. the advisory evidence the judge is shown reports the drift that object actually has.
#
# Both were FALSE before the removal, and both are false again the moment any rewrite comes
# back, because the stubbed transport below answers a rewrite's structured call with a
# complete, valid restored-spec payload — i.e. a reintroduced repair SUCCEEDS here, which is
# the case that breaks the properties.
#
# NON-VACUITY VERIFIED BY INVERSE EDIT, 2026-08-15, and the numbers are quoted rather than
# described: with `_enforce_seed_identity`/`_restore_seed_clauses` restored to their removed
# behaviour and re-called at the birth site, this file reports **8 failed, 13 passed** —
#     mech_analytics: the birth path mutated ['description', 'solution_name',
#         'value_proposition'] before the judge ruled
#     mech_analytics: evidence said drift [] but the generator's candidate drifted on
#         ['mechanism'] — the judge was shown a finding the pipeline had erased
# and the same pair on `mech_negated`, `delivery_swap` and `echo_smuggle`. It is FOUR of the
# eight drifting cases rather than all eight because the stub payload restores one pitch's
# clauses, so the other four leave residual drift and hit the repair's own rollback — which
# is exactly the shape the real rewrite had (it failed on 3 of 8 corpus cases and on 7 of 7
# real captured ones). The production file was restored afterwards and verified by checksum
# (`unified_solution_crew.py` 9fbdc8eba614de8775e8e2706850f78e before and after).

_CORPUS = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "seed_identity_corpus.json").read_text()
)

_RESTORED_SPEC_PAYLOAD = {
    "solution_name": "ReplyDraft Assistant",
    "value_proposition": "Drafts Reddit replies you approve before posting.",
    "description": ("A Chrome extension that drafts Reddit replies for community "
                    "managers at small SaaS companies."),
    "core_features": ["one-click draft", "approval step"],
    "why_it_works": "Keeps the human in the loop.",
    "innovation_angle": "Draft-first with policy safeguards.",
    "technical_approach": "Drafts from approved answers; flags low confidence.",
    "mechanism_tag": "reply-drafting-with-approval",
}


def _drifting_corpus_cases():
    """Cases whose candidate, AS THE GENERATOR PRODUCED IT, trips `seed_clause_drift` —
    derived by driving the detector, never listed, so a change to it moves this population
    instead of leaving a stale set of ids behind."""
    from nicheiq.utils.seed_fidelity import seed_clause_drift

    out = []
    for case in _CORPUS["adversarial"]:
        if not case.get("identity_terms"):
            continue
        if seed_clause_drift(case["identity_terms"], SimpleNamespace(**case["candidate"]),
                             case.get("inferred_fields") or []):
            out.append(case)
    return out


def _drive_birth(monkeypatch, case):
    """Run the REAL birth sequence on one corpus case and record what the judge received.

    Only the transport is replaced, and it DISPATCHES: a call whose output model carries
    `same_product` is the judge and gets an accepting verdict; anything else is treated as a
    copy-rewriting call and gets a complete restored-spec payload, so a reintroduced repair
    succeeds rather than fail-softing into a rollback that would hide it.
    """
    import nicheiq.crews.unified_solution_crew as usc
    from nicheiq.crews.unified_solution_crew import SeedRequest

    candidate = SimpleNamespace(**case["candidate"])
    generated = copy.deepcopy(candidate)

    def fake_invoke(**kwargs):
        model = kwargs.get("output_model")
        fields = getattr(model, "model_fields", {}) or {}
        if "same_product" in fields:
            return SimpleNamespace(
                same_product=True, changed_axes=[], rationale="stub"), None
        return SimpleNamespace(model_dump=lambda: dict(_RESTORED_SPEC_PAYLOAD)), None

    monkeypatch.setattr(usc.LLMService, "invoke_structured", fake_invoke)
    monkeypatch.setattr(usc, "_SEED_JUDGE_RETRY_DELAY_S", 0)
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **kw: candidate)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)

    seen: dict = {}
    real_judge = UnifiedSolutionCrew._semantic_seed_identity_matches

    def recording_judge(self, seed_text, cand, evidence=None):
        seen["candidate"] = copy.deepcopy(cand)
        seen["evidence"] = copy.deepcopy(evidence)
        return real_judge(self, seed_text, cand, evidence=evidence)

    monkeypatch.setattr(UnifiedSolutionCrew, "_semantic_seed_identity_matches",
                        recording_judge)

    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.execute_seed_pipeline(SeedRequest(
        seed_text=case["pitch"],
        identity_terms=case.get("identity_terms"),
        inferred_fields=case.get("inferred_fields")))
    assert seen, f"{case['id']}: the judge was never reached, so nothing was measured"
    return generated, seen


def _generator_candidate_after_the_two_allowed_normalisations(generated, judged, case):
    """`generated`, with the only two pre-judge writes the birth path is allowed to make.

    Both are deterministic, network-free representation fixes that sit above the birth gates
    on purpose (`execute_seed_pipeline`, just under `_canonicalize_project_type`), and both
    are VERIFIED here rather than waved through: the judged value must be exactly what the
    deterministic function returns, so this exception cannot be used to smuggle a rewrite of
    either field back in. `delivery_format` is the one that matters — it is inferred from the
    PITCH, so it stamps the pitch's delivery form onto the candidate and can clear a
    `delivery` clause the generator really did drift (visible on `echo_smuggle`, whose drift
    is ['mechanism', 'audience', 'delivery'] before this line and ['mechanism', 'audience']
    after it). That is a real, pre-existing instance of the same class the corrective rewrite
    was removed for, one field wide and deterministic instead of eight fields wide and
    LLM-authored.

    THE EVIDENCE WAS GATHERED (2026-08-15, S18) AND THE OBVIOUS FIX IS THE WRONG ONE. The
    residual reads like a precedence bug — `infer(pitch) or typed` is the repo's only
    non-fallback `infer_delivery_format` call — so the reorder to `typed or infer` was tried
    and measured. It does not reach this case: `echo_smuggle` carries NO typed value, so its
    stamp comes from the BLANK-FILL branch, which every reordering keeps. Across all 10
    adversarial corpus cases the reorder moves 0 drift verdicts, and across the 9 real
    captured `user_seed` candidates it moves 0 (drift recomputed with `delivery_format` at
    None vs at the pitch's inference). It also deletes rather than narrows the inference,
    because `typed_delivery_format` is non-None on 38 of 38 real refined candidates. Note
    which half of this exception is load-bearing: `expected_delivery` below puts `infer(pitch)`
    first, so ANY change to that precedence turns `delivery_swap` red here — the precedence is
    pinned by a predicate, not by this paragraph. Closing the residual means changing what the
    delivery axis reads, and that is still a behaviour change needing its own evidence.
    """
    from nicheiq.models.delivery_format import (
        infer_delivery_format,
        normalize_delivery_format,
    )

    expected_delivery = (
        infer_delivery_format(case["pitch"])
        or normalize_delivery_format(getattr(generated, "delivery_format", None))
        or "other")
    assert getattr(judged, "delivery_format", None) == expected_delivery, (
        f"{case['id']}: delivery_format reached the judge as "
        f"{getattr(judged, 'delivery_format', None)!r}, which is not what the deterministic "
        f"inference produces ({expected_delivery!r}) — something other than that inference "
        "wrote it")
    allowed = copy.deepcopy(generated)
    allowed.delivery_format = expected_delivery
    allowed.project_type = getattr(judged, "project_type", None)
    return allowed


@pytest.mark.parametrize("case", _drifting_corpus_cases(), ids=lambda c: c["id"])
def test_the_judge_rules_on_the_candidate_the_generator_produced(monkeypatch, case):
    """The birth judge is the SOLE verdict since the 2026-08-14 reorder, and its only input
    is the candidate's copy. So anything that rewrites that copy first is not checking the
    judge's work — it is choosing the judge's answer.

    Measured on the real judge before the removal: rewriting the drifted copy toward the
    pitch moved five of the seven drifting adversarial corpus substitutions from REFUSED to
    ACCEPTED — the judge-eval's "substitutions blocked" line reading 3/8 with the rewrite
    and 8/8 without it — including a candidate that says in as many words "It does not
    draft".
    """
    generated, seen = _drive_birth(monkeypatch, case)
    judged = seen["candidate"]
    allowed = _generator_candidate_after_the_two_allowed_normalisations(
        generated, judged, case)
    mutated = sorted(
        field for field in case["candidate"]
        if getattr(judged, field, None) != getattr(allowed, field, None))
    assert not mutated, (
        f"{case['id']}: the birth path mutated {mutated} before the judge ruled. The judge "
        "would then be ruling on copy the pipeline wrote toward the pitch, not on the "
        "product the generator actually produced.")


@pytest.mark.parametrize("case", _drifting_corpus_cases(), ids=lambda c: c["id"])
def test_the_judge_sees_the_drift_the_generator_actually_left(monkeypatch, case):
    """The second half, and the one that is easy to lose.

    `seed_identity_evidence` is computed from the candidate AS IT STANDS at that line, so a
    pass that repairs the drift also deletes the report of it: the judge was handed
    `drift: none` and a retention floor the repair had just manufactured. The same erasure
    reaches the user — `_refinement` (report/idea_validation_block.py) renders the
    Keeps/Changes/Because panel from `seed_clause_drift`, so a clean rewrite silently
    removes the disclosure that the evaluated product differs from the pitch.
    """
    from nicheiq.utils.seed_fidelity import seed_clause_drift

    generated, seen = _drive_birth(monkeypatch, case)
    allowed = _generator_candidate_after_the_two_allowed_normalisations(
        generated, seen["candidate"], case)
    expected = seed_clause_drift(case["identity_terms"], allowed,
                                 case.get("inferred_fields") or [])
    assert expected, f"{case['id']}: population is stale — this case no longer drifts"
    assert (seen["evidence"] or {}).get("seed_clause_drift") == expected, (
        f"{case['id']}: evidence said drift "
        f"{(seen['evidence'] or {}).get('seed_clause_drift')} but the generator's candidate "
        f"drifted on {expected} — the judge was shown a finding the pipeline had erased")


# ── brief-parity probe query construction ──

def test_brief_probe_runs_three_query_angles_including_listicle():
    """Run-to-run noise fix: the 'best … tools' roundup query is the discovery
    workhorse (the run that found the crowded category found it via a listicle;
    the plain two-query form missed it on the same pitch)."""
    crew = _crew()
    seen: list[str] = []

    class _Search:
        def run(self, search_query):
            seen.append(search_query)
            return "SERP: 8 Reddit reply automation tools tested, including Okara"

    crew.search_tool = _Search()
    crew.niche_context = SimpleNamespace(
        niche_description="Community-management tooling for B2B SaaS teams")
    finding = SimpleNamespace(
        parity="shipped", covered_by="Okara", evidence="reply automation agents")
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(finding, None)):
        note, calls = crew._probe_seed_brief_parity(
            SimpleNamespace(solution_name="X"), ["drafts Reddit replies"])

    assert calls == 3 and len(seen) == 3
    assert seen[0] == "drafts Reddit replies tool"
    assert seen[1] == "best drafts Reddit replies tools"
    assert "software" in seen[2]
    assert note == "shipped by Okara: reply automation agents"


def test_brief_probe_fail_soft_when_every_search_raises():
    crew = _crew()

    class _Broken:
        def run(self, search_query):
            raise RuntimeError("serper down")

    crew.search_tool = _Broken()
    crew.niche_context = SimpleNamespace(niche_description="market")
    note, calls = crew._probe_seed_brief_parity(
        SimpleNamespace(solution_name="X"), ["drafts replies"])
    assert note is None and calls == 3


def test_brief_probe_writer_stores_evidence_verbatim():
    """Post-audit revision: the writer stores the evidence sentence verbatim (echo
    kept); display humanizes (block-side _display_parity)."""
    crew = _crew()

    class _Search:
        def run(self, search_query):
            return "SERP result"

    crew.search_tool = _Search()
    crew.niche_context = SimpleNamespace(niche_description="market")
    finding = SimpleNamespace(
        parity="shipped", covered_by="Okara",
        evidence="Okara ships reply automation agents")
    with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
               return_value=(finding, None)):
        note, _calls = crew._probe_seed_brief_parity(
            SimpleNamespace(solution_name="X"), ["drafts Reddit replies"])
    assert note == "shipped by Okara: Okara ships reply automation agents"
