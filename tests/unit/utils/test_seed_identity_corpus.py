"""Offline replay corpus for the "Check my idea" seed-identity gates.

WHY THIS EXISTS. The gates' failure mode is OVER-blocking, and over-blocking is invisible in
production: a wrongly-refused run emits no bad verdict to inspect, just a missing result. Three
live failures in one week were each found by a user pasting a log, not by any signal we had. With
~10 seed runs in existence at 30-60 min and ~$1.60 each, production cannot be tuned against.

Every previous fix here was calibrated on a sample of one and broke on the next run:

  * `EXACT_TERMS_TOKEN_CAP = 25` was derived from "completed runs carried 17-25 tokens" — pure
    survivorship, since those runs completed BECAUSE their rewrites happened to keep every token.
    Live 7703f811 was 23 tokens and died the next day.
  * The route fix targeted the one field seen in one log (`data_acquisition_notes`); the next run
    failed five times on `data_sources`, same rule, different field.

This corpus turns "is the change safe?" from a 45-minute paid experiment into an offline
assertion, and — more importantly — it measures the direction no unit test covers: how much REAL,
HONEST material the gates accept.

WHAT IT IS NOT: training data. Nothing is fitted to it; the LLM judge never sees it.

THE FIXTURE IS VENDORED (`tests/fixtures/seed_identity_corpus.json`) and must stay that way.
Reading `output/checkpoints/` at test time would make this file resolve to zero tests on any
machine without those artifacts — green, silent, and worthless. Each honest pair records its
`provenance`; reconstructed pairs say so explicitly and quote the log line they came from.

ADDING CASES: honest pairs may only be added from real runs (or reconstructed from a quoted log).
Adversarial pairs are hand-built and must name the axis they attack. The two `must_pass`
adversarial cases are the ones that keep this suite from rewarding a guard that is strict because
it is broken — a gate can reach 100% blocking by refusing everything.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nicheiq.utils.seed_fidelity import (
    is_seed_faithful,
    seed_clause_drift,
    unpitched_core_dependencies,
)

_CORPUS = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "seed_identity_corpus.json").read_text()
)


def _candidate(spec: dict) -> SimpleNamespace:
    return SimpleNamespace(**spec)


def _deterministic_verdict(pitch: str, cand) -> tuple[bool, str]:
    """Run every DETERMINISTIC gate that can refuse a seed, and report the first refusal.

    Deliberately excludes `_semantic_seed_identity_matches` (an LLM call) and the post-birth
    snapshot (which compares against a birth snapshot, not a pitch). This measures exactly the
    layer that produced all four production false positives.

    SINCE THE 2026-08-14 AUTHORITY REORDER THIS LAYER RULES NOTHING. It was briefly the
    judge-unavailable fallback; that fallback was removed when it was measured accepting a
    lexically-clean buyer substitution (`_CLEAN_SUBSTITUTION` below) during an outage. What it
    produces now is ADVISORY EVIDENCE handed to the judge, so these numbers describe the
    quality of that evidence — not any verdict. The birth path is measured by `_birth_outcome`.
    """
    routes = unpitched_core_dependencies(pitch, cand)
    if routes:
        return False, f"unpitched_route:{routes[0][:60]}"
    if not is_seed_faithful(pitch, cand):
        return False, "retention_floor"
    return True, ""


# ── the BIRTH path, with only the LLM judge replaced ───────────────────────────────────────

def _stub_judge(monkeypatch, *, same_product=True, raises=False, prompts=None,
                fail_first=None):
    """Replace the ONE network call in the birth path. Everything else stays production code,
    including `_semantic_seed_identity_matches` itself — so the advisory block is really
    assembled and the judge-unavailable branch is reached through a real exception.

    `raises` may be True (a generic transient failure) or an exception instance, so the
    non-retryable class can be driven too. `fail_first=N` fails the first N attempts and then
    answers, which is how the retry loop is exercised. `prompts` doubles as the attempt
    counter: one entry per call that reached the transport.
    """
    import nicheiq.crews.unified_solution_crew as usc

    attempts = {"n": 0}

    def fake_invoke(**kwargs):
        attempts["n"] += 1
        if prompts is not None:
            prompts.append(kwargs.get("prompt", ""))
        if raises and (fail_first is None or attempts["n"] <= fail_first):
            raise raises if isinstance(raises, BaseException) else RuntimeError(
                "judge provider unreachable")
        return SimpleNamespace(
            same_product=same_product, changed_axes=[], rationale="stub"), None

    monkeypatch.setattr(usc.LLMService, "invoke_structured", fake_invoke)
    # The judge retries before declaring itself unreachable. The backoff is real wall clock and
    # this module drives the exhausted path repeatedly; the loop is what is under test, not the
    # sleeping. Patched on the module so the production default stays honest.
    monkeypatch.setattr(usc, "_SEED_JUDGE_RETRY_DELAY_S", 0)


def _birth_outcome(monkeypatch, case, *, same_product=True, raises=False, prompts=None,
                   fail_first=None):
    """Run the REAL `execute_seed_pipeline` birth sequence on a corpus case.

    Returns the accepted idea, or None with the typed refusal cause on
    `crew._seed_failure_reason`. Only the judge's network call, the generator, and the two
    post-birth passes are stubbed; the gate ORDER and every deterministic check are the
    shipped ones. That is the point: a test that re-implemented the ordering would keep
    passing after someone re-promoted a lexical finding to a veto.
    """
    import nicheiq.crews.unified_solution_crew as usc
    from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew

    candidate = _candidate(case["candidate"])
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **kw: candidate)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)
    # There used to be a third stub here, neutralising the post-birth corrective rewrite so
    # that residual clause drift stayed ALIVE in the evidence — "drift present, and not a
    # veto" being the state under test. The rewrite was removed on 2026-08-15 (S17, measured
    # laundering substitutions past the judge), so that state is now simply what the birth
    # path does, with nothing stubbed to arrange it. Every verdict this module reports is
    # therefore unchanged by the removal, which was checked case by case rather than assumed.
    _stub_judge(monkeypatch, same_product=same_product, raises=raises, prompts=prompts,
                fail_first=fail_first)
    assert usc  # the module is what was patched; keeps the import honest
    return crew, crew.execute_seed_pipeline(SeedRequest(
        seed_text=case["pitch"],
        identity_terms=case.get("identity_terms"),
        inferred_fields=case.get("inferred_fields"),
    ))


def _report(name: str, rows: list[tuple[str, bool, str]]) -> None:
    ok = sum(1 for _, passed, _ in rows if passed)
    print(f"\n  {name}: {ok}/{len(rows)}")
    for cid, passed, why in rows:
        if not passed:
            print(f"     REFUSED {cid}: {why}")


class TestKnownFalsePositivesAreNowAccepted:
    """The three production kills, reconstructed IN THE GATE'S OWN SHAPE from the log lines that
    describe exactly what it saw. These are assertable; the shipped-candidate pairs below are
    not (see `test_shipped_candidates_are_measured_not_asserted`)."""

    @pytest.mark.parametrize(
        "pair", [p for p in _CORPUS["honest"] if p["kind"] == "reconstructed_from_log"],
        ids=lambda p: p["id"])
    def test_a_known_false_positive_is_accepted(self, pair):
        passed, why = _deterministic_verdict(pair["pitch"], _candidate(pair["candidate"]))
        assert passed, (
            f'{pair["id"]} discarded a paid run and must now be accepted (refused: {why}). '
            f'{pair["provenance"]}')

    def test_the_corpus_still_contains_the_known_regressions(self):
        """Guards the corpus itself: these must never be quietly dropped, or the suite stops
        testing the cases it was built for."""
        ids = {p["id"] for p in _CORPUS["honest"]}
        for known in ("7703f811", "e1b42702", "d213f348"):
            assert known in ids, f"known false-positive kill {known} missing from the corpus"


class TestShippedCandidatesAreMeasuredNotAsserted:
    """MEASUREMENT ONLY — and the reason is itself a finding.

    The gates run on the candidate as it exists AT EACH GATE. What we persist is the FINAL merged
    artifact, after the worker's post-merge save and the pool contract have written route fields.
    Proof that these are different objects: every change made on 2026-08-14 was a RELAXATION, yet
    the current code refuses candidates that shipped successfully. A stricter earlier version
    cannot have seen these values.

    So this suite cannot assert on shipped pairs without testing a shape production never
    evaluates — the exact 'fixture in an unreachable shape' trap. It reports instead, and the
    real fix is upstream: capture the candidate AT each gate so the corpus can be built from
    what was actually judged. That capture does not exist today, which is a large part of why
    this subsystem has never been tunable.
    """

    def test_shipped_candidates_are_measured_not_asserted(self):
        rows = []
        for pair in _CORPUS["honest"]:
            if pair["kind"] != "shipped_candidate":
                continue
            passed, why = _deterministic_verdict(pair["pitch"], _candidate(pair["candidate"]))
            rows.append((pair["id"], passed, why))
        _report("shipped candidates accepted (final-artifact shape, NOT the gate's input)", rows)
        assert rows, "no shipped pairs in the corpus"

class TestSubstitutionsAreBlocked:
    """A relaxation must not silently re-open a hole. These are the products a user did NOT
    submit; grading one of them is the single failure this subsystem exists to prevent."""

    @pytest.mark.parametrize(
        "case", [c for c in _CORPUS["adversarial"] if c["axis"] != "must_pass"],
        ids=lambda c: c["id"])
    def test_a_substituted_product_is_refused(self, case):
        passed, _ = _deterministic_verdict(case["pitch"], _candidate(case["candidate"]))
        drift = seed_clause_drift(case.get("identity_terms"), _candidate(case["candidate"]))
        # Either layer may catch it; what matters is that SOMETHING does.
        assert not passed or drift, (
            f'substitution {case["id"]} ({case["axis"]}) was accepted — '
            f'{case["must_block_because"]}')

    @pytest.mark.parametrize(
        "case", [c for c in _CORPUS["adversarial"] if c["axis"] == "must_pass"],
        ids=lambda c: c["id"])
    def test_legitimate_elaboration_is_not_refused(self, case, monkeypatch):
        """The other failure direction. A gate can score 100% on blocking by refusing
        everything; these keep that from reading as success.

        `instances_named_ok` was a STRICT XFAIL here until 2026-08-14 and is now a plain
        assertion — see its `resolved_note` in the fixture. It is the case the whole reorder
        was for, and it is why this test now runs the BIRTH path rather than
        `_deterministic_verdict`: the deterministic layer still refuses it (4 unpitched routes,
        clause drift, retention 12/23 under a floor of 14) and always will, because ruling that
        DeepSeek is an instance of the pitched 'AI assistants' is world knowledge. What changed
        is that those findings are no longer a verdict.
        """
        _crew, idea = _birth_outcome(monkeypatch, case, same_product=True)
        assert idea is not None, (
            f'{case["id"]} must pass — {case["must_block_because"]} '
            f'(refused: {_crew._seed_failure_reason})')


# A buyer substitution whose lexical evidence is CLEAN on all three axes — measured:
#   external routes flagged as unpitched: none
#   pitch clauses reported as drifted:    none
#   literal pitch-term retention:         14 of 17 stemmed terms (heuristic floor 11)
# Built here rather than appended to the vendored corpus: it is not a case for the corpus's
# deterministic sweeps (which it passes, by construction — that IS the point), it exists only
# to drive the judge-unavailable branch. The pitch is `buyer_swap`'s; `identity_terms` is
# deliberately absent, which is a real production state (the "Check my idea" path runs with
# `identity_terms=None` whenever clause extraction returns nothing) and is what makes
# `seed_clause_drift` empty. Round-1 code ACCEPTED this candidate under a judge outage and
# handed the user a full paid Go/No-Go verdict on it.
_CLEAN_SUBSTITUTION = {
    "id": "buyer_swap_lexically_clean",
    "pitch": ("A browser-based inventory reconciliation tool for independent veterinary "
              "clinics that flags controlled-medication discrepancies and generates "
              "audit-ready DEA logs."),
    "must_block_because": "buyer moved from independent clinics to hospital chains",
    "candidate": {
        "solution_name": "EnterpriseVetLedger",
        "description": ("A browser-based inventory reconciliation tool for large hospital "
                        "chains that flags controlled-medication discrepancies and generates "
                        "audit-ready DEA logs."),
        "target_personas": ["Enterprise hospital-group procurement directors"],
        "source_frame": "user_seed",
    },
}


class TestBirthGateHasThreeStates:
    """ACCEPTED, REFUSED (judged), and REFUSED (judge unavailable).

    The third state is the one the reorder created and the one a bool cannot carry: it needs
    different user-facing copy and different follow-up (re-run, not rewrite) from a judged
    refusal, so it keeps its own typed cause — but it is still a REFUSAL.

    IT WAS NOT, IN ROUND 1. It accepted whenever the deterministic layer was clean, which is
    fail-OPEN where the code it replaced was fail-CLOSED, and `_CLEAN_SUBSTITUTION` below is a
    product the user never submitted that walked straight through it. The accepting design was
    removed rather than caveated: the lexical layer's measured weakness IS this class of
    substitution — that is why the judge was given authority in the first place — so accepting
    on it re-runs the ordering the reorder deleted, and a caveat the user may not read is not
    consent. A refused run is recoverable; a wrong Go verdict on someone else's product is not.
    """

    @staticmethod
    def _case():
        return next(c for c in _CORPUS["adversarial"] if c["id"] == "enrichment_ok")

    def test_the_judge_accepts(self, monkeypatch):
        crew, idea = _birth_outcome(monkeypatch, self._case(), same_product=True)
        assert idea is not None
        assert crew._seed_failure_reason is None

    def test_the_judge_refuses_with_its_own_typed_cause(self, monkeypatch):
        crew, idea = _birth_outcome(monkeypatch, self._case(), same_product=False)
        assert idea is None
        assert crew._seed_failure_reason == "judged_a_different_product"

    def test_an_unreachable_judge_refuses_even_a_clean_candidate(self, monkeypatch):
        """No birth is ever silently unjudged. `enrichment_ok` is the honest case the old
        fallback accepted; it must now refuse, with the outage's own typed cause."""
        crew, idea = _birth_outcome(monkeypatch, self._case(), raises=True)
        assert idea is None, (
            "a birth the authoritative check never saw was accepted — the user gets a paid "
            "verdict on an unjudged product")
        assert crew._seed_failure_reason == "identity_judge_unavailable"
        assert crew._seed_judge_unavailable is True
        assert any(r["gate"] == "semantic" and r["verdict"] == "refused"
                   and r["reason"] == "identity_judge_unavailable"
                   for r in crew._seed_identity_trace), (
            "the trace must record WHICH refusal this was")

    def test_an_unreachable_judge_blocks_a_substitution_the_lexical_layer_passes(
        self, monkeypatch,
    ):
        """THE GAP, end to end. The round-1 covering test used `route_swap_named` — a case the
        deterministic layer catches on its own (unpitched route `Yodlee`, drifted `mechanism`),
        so it read as covering this ground and did not: it passed identically whether the
        fallback accepted clean candidates or refused everything. This case is clean on every
        deterministic axis and is still a different product."""
        crew, idea = _birth_outcome(monkeypatch, _CLEAN_SUBSTITUTION, raises=True)
        assert idea is None, (
            f'{_CLEAN_SUBSTITUTION["id"]} was born under an unavailable judge — '
            f'{_CLEAN_SUBSTITUTION["must_block_because"]}; every lexical axis is clean, so '
            "nothing but the judge can catch it")
        assert crew._seed_failure_reason == "identity_judge_unavailable", (
            "an outage refusal must be distinguishable from a judged refusal — they need "
            "different user-facing copy and different follow-up")

    def test_an_unreachable_judge_never_looks_like_a_judged_verdict(self, monkeypatch):
        """`identity_judge_unavailable` is its own typed cause, distinct from every other one
        the crew can stamp. Collapsing it into `judged_a_different_product` would tell the user
        their idea became a different product when the truth is our judge did not answer.

        Enumerated from `SEED_FAILURE_COPY`, which
        `tests/unit/crews/test_seed_pipeline.py` pins to the causes the crew source actually
        assigns — so a new cause cannot slip past this by not being in a hand-written list.
        """
        from nicheiq.report.idea_validation_block import SEED_FAILURE_COPY

        crew, idea = _birth_outcome(monkeypatch, _CLEAN_SUBSTITUTION, raises=True)
        assert idea is None
        assert crew._seed_failure_reason not in (
            set(SEED_FAILURE_COPY) - {"identity_judge_unavailable"})


class TestTheJudgeIsRetriedBeforeItIsCalledUnreachable:
    """STATE 3 refuses a paid run, so what lands there must not be a 429 or a socket timeout.

    Every exception out of `invoke_structured` is indistinguishable at the call site — the
    trigger is not "provider outage" — so the transient class is retried before the run is
    refused. What survives the retry is a sustained outage or a systemic halt.
    """

    @staticmethod
    def _case():
        return next(c for c in _CORPUS["adversarial"] if c["id"] == "enrichment_ok")

    def test_a_transient_failure_does_not_refuse_the_run(self, monkeypatch):
        prompts: list[str] = []
        crew, idea = _birth_outcome(
            monkeypatch, self._case(), raises=True, fail_first=1, prompts=prompts)
        assert idea is not None, (
            "one 429 refused a paid run; the judge was reachable on the retry")
        assert crew._seed_failure_reason is None
        assert crew._seed_judge_unavailable is False
        assert len(prompts) == 2, f"expected one retry, saw {len(prompts)} attempts"

    def test_the_retry_is_bounded(self, monkeypatch):
        import nicheiq.crews.unified_solution_crew as usc

        prompts: list[str] = []
        crew, idea = _birth_outcome(monkeypatch, self._case(), raises=True, prompts=prompts)
        assert idea is None
        assert len(prompts) == usc._SEED_JUDGE_ATTEMPTS, (
            "the judge must be asked exactly _SEED_JUDGE_ATTEMPTS times before the run is "
            f"refused, saw {len(prompts)}")
        assert crew._seed_failure_reason == "identity_judge_unavailable"

    def test_a_systemic_failure_is_not_retried_and_is_not_relabelled_an_outage(
        self, monkeypatch,
    ):
        """Payment/auth trips a breaker that guarantees every further call fails. Retrying
        spends the user's wall clock on a certain failure — and CATCHING it spends the user's
        money on a lie.

        It used to land on `identity_judge_unavailable`, whose copy says "running it again
        should work". That is false while a 401/402 stands: the breaker fast-fails every
        further call for the rest of the run. `llm_service` raises this class precisely so the
        job can halt and be refunded instead of limping on, and `_inject_validate_seed` already
        codes for it (`except LLMSystemicError: raise`) — it never saw one from this path
        because the judge's `except Exception` swallowed it first.
        """
        from nicheiq.utils.llm_service import LLMSystemicError

        prompts: list[str] = []
        with pytest.raises(LLMSystemicError):
            _birth_outcome(
                monkeypatch, self._case(), raises=LLMSystemicError("HTTP 402"),
                prompts=prompts)
        assert len(prompts) == 1, f"a systemic failure was retried {len(prompts)} times"


class TestAFaultInOurOwnCodeIsNotAnOutage:
    """F-3 (2026-08-15). "Wait a few minutes" is advice about a remote service under load.

    Everything inside `_semantic_seed_identity_matches` used to land on
    `identity_judge_unavailable`, whose next step ends *"if it stops the same way immediately,
    wait a few minutes first"*. But half that method is OUR code — fencing the pitch, rendering
    the advisory evidence, assembling the prompt — and a fault there is deterministic and
    network-free, so waiting cannot help. That is the same inaccuracy round 9 minted
    `identity_check_could_not_run` for on the flow's field-diff `except`, arriving one layer in.

    The split is STRUCTURAL — our code in one `try`, the provider call in another — not a list
    of exception types, which is the shape this ledger keeps losing to. Both halves are driven
    below, and BOTH assertions matter: the provider case must KEEP its cause, or the fix would
    have traded one inaccurate sentence for another.
    """

    @staticmethod
    def _case():
        return next(c for c in _CORPUS["adversarial"] if c["id"] == "enrichment_ok")

    def test_a_fault_in_our_prompt_assembly_gets_the_our_fault_cause(self, monkeypatch):
        import nicheiq.crews.unified_solution_crew as usc

        # Fencing the pitch is unambiguously OUR code, runs before any network call, and fails
        # identically on every retry — the exact profile the outage copy misdescribes.
        monkeypatch.setattr(
            usc, "fence_content",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fence blew up")))
        crew, idea = _birth_outcome(monkeypatch, self._case())

        assert idea is None, "a birth the identity check never completed must still refuse"
        assert crew._seed_failure_reason == "identity_check_could_not_run", (
            "a deterministic, network-free fault in our own code told the user to wait a few "
            "minutes for a remote service")
        assert any(r["gate"] == "semantic" and r["verdict"] == "refused"
                   and r["reason"] == "identity_check_could_not_run"
                   for r in crew._seed_identity_trace)

    def test_the_provider_call_keeps_the_outage_cause(self, monkeypatch):
        """The control. `raises=True` fails `invoke_structured` itself, where waiting IS
        honest advice, so that cause must survive the split unchanged."""
        crew, idea = _birth_outcome(monkeypatch, self._case(), raises=True)

        assert idea is None
        assert crew._seed_failure_reason == "identity_judge_unavailable"

    def test_both_causes_carry_their_own_authored_copy(self):
        """Neither cause may fall through to the generic pair, and their next steps must
        actually differ — a split that routed to two keys with identical sentences would be
        bookkeeping, not a fix."""
        from nicheiq.report.idea_validation_block import (
            SEED_FAILURE_COPY,
            seed_failure_next_step,
        )

        ours = "identity_check_could_not_run"
        theirs = "identity_judge_unavailable"
        assert ours in SEED_FAILURE_COPY and theirs in SEED_FAILURE_COPY
        assert seed_failure_next_step(ours) != seed_failure_next_step(theirs)
        # The sentence the split exists to keep away from a deterministic failure.
        assert "wait a few minutes" in seed_failure_next_step(theirs).lower()
        assert "wait a few minutes" not in seed_failure_next_step(ours).lower()


class TestAccountingNeverRelabelsADeliveredVerdict:
    """The judge's `try` used to reach past its own subject.

    `cost_tracker.record_llm_usage` and the rationale log sat INSIDE the try whose `except`
    sets `_seed_judge_unavailable`, so a healthy `same_product=True` became
    `identity_judge_unavailable` — refusing a fully-paid run — if cost accounting raised, and a
    judged `same_product=False` was reported as our outage if the log line raised. Neither
    means "the judge did not rule", which is the only thing that flag is allowed to say.

    Structural rather than live on today's types (`record_llm_usage` does not currently raise
    on any input this path produces); the boundary is the fix, not a guard around the call.
    """

    @staticmethod
    def _judge_crew(monkeypatch, *, same_product, tracker):
        import nicheiq.crews.unified_solution_crew as usc
        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

        usage = SimpleNamespace(to_dict=lambda: {"total_tokens": 11})
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            lambda **kw: (SimpleNamespace(same_product=same_product, changed_axes=[],
                                          rationale="stub"), usage))
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.cost_tracker = tracker
        return crew

    class _ExplodingTracker:
        def record_llm_usage(self, *_args, **_kwargs):
            raise RuntimeError("cost tracker exploded")

    def test_a_cost_tracking_failure_is_not_reported_as_a_judge_outage(self, monkeypatch):
        crew = self._judge_crew(monkeypatch, same_product=True,
                                tracker=self._ExplodingTracker())
        with pytest.raises(RuntimeError, match="cost tracker exploded"):
            crew._semantic_seed_identity_matches("a pitch", _candidate({"solution_name": "X"}))
        assert crew._seed_judge_unavailable is False, (
            "the judge ruled same_product=True; accounting cannot turn that into an outage")

    def test_a_delivered_verdict_still_records_its_usage(self, monkeypatch):
        recorded: list[tuple] = []

        class _Tracker:
            def record_llm_usage(self, label, payload):
                recorded.append((label, payload))

        crew = self._judge_crew(monkeypatch, same_product=True, tracker=_Tracker())
        assert crew._semantic_seed_identity_matches(
            "a pitch", _candidate({"solution_name": "X"})) is True
        assert recorded == [("Stage 5 - Seed semantic identity", {"total_tokens": 11})], (
            "narrowing the try must not drop the cost record")


class TestEvidenceReachesTheJudge:
    """The reorder's whole mechanism: the deterministic findings must arrive at the judge as
    LABELLED ADVISORY input, and must be recorded in the trace. If either link breaks, the
    findings are simply gone and the change is a pure relaxation rather than a reordering."""

    @staticmethod
    def _case():
        return next(c for c in _CORPUS["adversarial"] if c["id"] == "instances_named_ok")

    def test_the_findings_are_in_the_prompt_and_marked_as_not_a_verdict(self, monkeypatch):
        prompts: list[str] = []
        _crew, idea = _birth_outcome(monkeypatch, self._case(), prompts=prompts)
        assert idea is not None
        assert prompts, "the judge was never called"
        prompt = prompts[0]
        assert "ADVISORY EVIDENCE" in prompt
        assert "NOT a verdict" in prompt
        # the actual findings, not just the header
        assert "OpenAI API" in prompt
        assert "mechanism" in prompt
        assert "12 of 23 stemmed terms" in prompt

    def test_the_judges_measured_rule_text_is_untouched(self, monkeypatch):
        """The rules were measured at 11/11 and two 'improvements' to them were a proven
        regression. The advisory block is additive; it must not have edited them."""
        prompts: list[str] = []
        _birth_outcome(monkeypatch, self._case(), prompts=prompts)
        assert (
            "Decide whether CANDIDATE is still the SAME PRODUCT as ORIGINAL. Same product "
            "requires the same product category, core action/artifact, interaction model, and "
            "target buyer."
        ) in prompts[0]

    def test_the_evidence_is_recorded_in_the_gate_trace(self, monkeypatch):
        crew, _idea = _birth_outcome(monkeypatch, self._case())
        rows = [r for r in crew._seed_identity_trace if r["gate"] == "birth_evidence"]
        assert rows, "the corpus cannot grow from runs whose evidence was never recorded"
        assert rows[0]["verdict"] == "advisory"
        assert "unpitched_core_dependencies" in rows[0]["reason"]
        assert rows[0]["candidate"], "the trace must hold the candidate the gate saw"


class TestPostBirthIsADiffNotARetrial:
    """The flow's pre-injection check (`_inject_validate_seed`) used to re-run the lexical
    gates against the PITCH — a fourth trial of a question the birth judge had already
    settled, with different thresholds, on a run the user had paid for in full. It is now the
    birth SNAPSHOT diff, which is the only thing that can honestly answer the narrower
    question it is actually there to ask.

    Lives here rather than beside the other Stage-5 injection tests because it is a
    seed-identity gate: this file owns the arrangement of those gates.
    """

    class _Crew:
        """Only what `_inject_validate_seed` reads."""

        _SNAP = ("_tournament_ctx", "ruled_out_pains", "overlap_groups", "funnel_counts",
                 "_ma_serper_calls", "_ma_search_lock", "_birth_verified_names",
                 "_route_label_counts", "coverage_caveats", "_current_seed_text",
                 "_current_seed_dispatch_id", "_current_seed_evaluation")

        def __init__(self, seed, lock, mutate=None):
            for attr in self._SNAP:
                setattr(self, attr, None)
            self.ruled_out_pains = []
            self._seed = seed
            self._seed_identity_lock = lock
            self._mutate = mutate

        def execute_seed_pipeline(self, _req):
            if self._mutate:
                self._mutate(self._seed)
            return self._seed

        def _probe_seed_brief_parity(self, _seed, _terms):
            return None, 0

    @staticmethod
    def _flow():
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.models.research_state import ResearchState

        flow = ResearchFlow.__new__(ResearchFlow)
        flow.entry_mode = "validate_idea"
        flow._state = ResearchState()
        flow._state.user_idea_brief = "A web app that monitors AI answers about local shops."
        flow._emit_progress = lambda *a, **k: None
        return flow

    @staticmethod
    def _seed_and_lock():
        from nicheiq.utils.seed_fidelity import seed_identity_snapshot

        case = next(c for c in _CORPUS["adversarial"] if c["id"] == "instances_named_ok")
        seed = _candidate(case["candidate"])
        seed.incumbent_parity = "unclear"
        seed.candidate_status = "active"
        seed.generation_operation_id = None
        seed.duplicate_of = None
        seed.pain_points_addressed = []
        return seed, seed_identity_snapshot(seed)

    def test_a_seed_unchanged_since_birth_is_injected(self):
        """`instances_named_ok` still fails the lexical gates against the pitch and always
        will. Nothing touched it after birth, so the flow has nothing to object to."""
        seed, lock = self._seed_and_lock()
        flow = self._flow()
        pool = SimpleNamespace(solution_ideas=[])
        flow._inject_validate_seed(self._Crew(seed, lock), pool)

        assert pool.solution_ideas == [seed], (
            "the flow withheld a seed the birth judge accepted and nothing since has "
            f"changed — degradations: {flow.state.pipeline_degradations}")

    def test_a_seed_rewritten_after_birth_is_still_withheld(self):
        """The other direction: reducing to a diff must not reduce to nothing."""
        seed, lock = self._seed_and_lock()

        def rewrite(idea):
            idea.solution_name = "London Review Reply Writer"
            idea.description = "Writes replies to Google reviews for London shops."

        flow = self._flow()
        pool = SimpleNamespace(solution_ideas=[])
        flow._inject_validate_seed(self._Crew(seed, lock, mutate=rewrite), pool)

        assert pool.solution_ideas == []

        # The REFUSAL is what this test is about; the SENTENCE moved (round 8). It used to
        # assert a hand-written "…drifted from your submitted product and was withheld",
        # which was the fourth independently authored refusal sentence in a program whose
        # single source is `SEED_FAILURE_COPY` — and it left `user_idea_failure_reason`
        # unset, so the report rendered the generic pair beside it. Asserted on the property
        # now: a typed cause the copy map knows, and a caveat derived from that map.
        from nicheiq.report.idea_validation_block import (
            SEED_FAILURE_COPY,
            seed_failure_headline,
        )

        reason = flow.state.user_idea_failure_reason
        assert reason in SEED_FAILURE_COPY, reason
        headline = seed_failure_headline(reason)
        assert flow.state.pipeline_degradations[-1] == (
            f"Idea check: {headline[0].lower()}{headline[1:]}")

    @staticmethod
    def _fields_read_by(fn, *args_per_case):
        """Every attribute name `fn` reads off the candidate, MEASURED by driving it over the
        whole corpus with a recording stand-in — not by set algebra over the tuples the
        function happens to name.

        This is trap 13's remedy applied to this pin. The previous version compared
        `_ROUTE_ASSERTION_FIELDS` against `_IDENTITY_FIELDS` and asserted the other half of the
        claim by walking `_AXIS_IDENTITY_FIELDS` — three hand-picked tuples, no execution. It
        therefore certified a sentence that is FALSE: `seed_clause_drift` does NOT read only
        snapshot fields. It computes `additive_mechanism` by calling
        `unpitched_core_dependencies(stated_text, candidate)`, which reads
        `differentiation_locus`, and `additive_mechanism` can add `mechanism` to the returned
        drift list on its own. The tuple walk cannot see a call.
        """
        class _Recorder:
            def __init__(self, data, log):
                object.__setattr__(self, "_data", data)
                object.__setattr__(self, "_log", log)

            def __getattr__(self, name):
                object.__getattribute__(self, "_log").add(name)
                return object.__getattribute__(self, "_data").get(name)

        seen: set[str] = set()
        for case, build_args in args_per_case:
            fn(*build_args(_Recorder(case["candidate"], seen)))
        return {name for name in seen if not name.startswith("_")}

    def test_the_snapshot_subsumes_the_lexical_re_checks_except_one_named_field(self):
        """Pins the invariant the comment at `research_flow.py:_inject_validate_seed` depends
        on. That comment claimed "every field they read is in the snapshot"; it is one field
        short, and a claim like that becomes inherited fact if nothing checks it.

        `differentiation_locus` is excluded from `_IDENTITY_FIELDS` deliberately and must stay
        excluded: the parity pass clears it (with `winning_angle` and the two rationales) to
        None in `UnifiedSolutionCrew._probe_mechanism_parity`
        (`unified_solution_crew.py:3259-3261`) so `_classify_idea_angles` can re-derive it
        against final capped scores, i.e. it changes after birth BY DESIGN on every run.
        Snapshotting it would refuse healthy paid runs in both directions, since
        `changed_seed_identity_fields` flags blank-fills too.

        So this asserts the difference is EXACTLY that one field, for BOTH lexical checks, and
        it asserts it by driving them rather than by inspecting the tuples they read from.
        Widening either tuple — or adding a call that reaches a new field — fails here instead
        of silently re-breaking the subsumption claim.

        THE SNAPSHOT SET IS READ FROM `seed_identity_snapshot`, NOT FROM `_IDENTITY_FIELDS`
        (2026-08-15, S19). Until the evaluation-field split it read the tuple, which happened
        to be the same set — and then stopped being, silently. That is trap 25 in this
        module's own file: a gate can drift off the path it gates, and the version of this
        test that walked `_IDENTITY_FIELDS` would have gone on passing while describing a
        snapshot the code no longer takes.

        THE RESIDUAL IS WIDER THAN IT WAS, and this states it rather than hiding it. Both
        lexical checks read the three `_EVALUATION_FIELDS` too, so a post-birth pass that
        introduced an unpitched core route ONLY in the critic's cited route, the verifier's
        access label, or the cost/ToS disclosure is not caught by the post-birth diff either.
        That is accepted for the same reason the fields left the lock: those three are where
        the pipeline writes its own conclusions, so no diff over them can distinguish our
        machinery from the user's product. Note the mitigation, which `differentiation_locus`
        does not have: `data_acquisition_notes` is already barred from MINTING a route
        assertion (`_ROUTE_ASSERTION_FIELDS` excludes it), and `market_fit_claimed_route` is
        code-populated from the critic rather than from candidate copy.
        """
        from nicheiq.utils import seed_fidelity as sf

        class _Recorder:
            def __getattr__(self, name):
                _snapshot_reads.add(name)
                return "x"

        _snapshot_reads: set[str] = set()
        sf.seed_identity_snapshot(_Recorder())
        snapshot = _snapshot_reads
        evaluation = set(sf._EVALUATION_FIELDS)
        assert evaluation and not evaluation & snapshot, (
            "`_EVALUATION_FIELDS` must be exactly what the snapshot does NOT read; if the "
            "snapshot starts reading one again, the 8580c179 kill is back")

        route_read = self._fields_read_by(
            sf.unpitched_core_dependencies,
            *[(c, lambda cand, c=c: (c["pitch"], cand))
              for c in _CORPUS["honest"] + _CORPUS["adversarial"]],
        )
        assert route_read - snapshot - evaluation == {"differentiation_locus"}, (
            "the post-birth snapshot no longer subsumes `unpitched_core_dependencies` in the "
            f"way research_flow's comment describes — fields it reads that the birth snapshot "
            "does not lock and that are not declared evaluation evidence: "
            f"{sorted(route_read - snapshot - evaluation)}. Correct that comment, or justify "
            "the new field the same way `differentiation_locus` is justified.")

        # The other half of the claim, which the tuple-walking version of this test got WRONG.
        # `seed_clause_drift` reads `differentiation_locus` too, through the
        # `unpitched_core_dependencies` call behind `additive_mechanism` — so the sentence
        # "`seed_clause_drift` reads only snapshot fields, so it IS subsumed" is false and is
        # corrected at both of its call-site comments. The residual is the SAME single field
        # for both checks, which is the honest statement.
        drift_read = self._fields_read_by(
            sf.seed_clause_drift,
            *[(c, lambda cand, c=c: (c["identity_terms"], cand, c.get("inferred_fields")))
              for c in _CORPUS["adversarial"] if c.get("identity_terms")],
        )
        assert drift_read - snapshot - evaluation == {"differentiation_locus"}, (
            "`seed_clause_drift` now reads "
            f"{sorted(drift_read - snapshot - evaluation)} outside the birth snapshot and "
            "outside the declared evaluation evidence — the post-birth diff no longer "
            "subsumes it, and both `_inject_validate_seed`'s comment and "
            "`execute_seed_pipeline`'s say it does")

        # And the axis tuples specifically, kept because they catch a different thing: a
        # re-widened axis that no corpus case happens to exercise would not show up above.
        for clause, axis in sf._DRIFT_AXIS_BY_CLAUSE.items():
            unsnapshotted = set(sf._AXIS_IDENTITY_FIELDS[axis]) - snapshot - evaluation
            assert not unsnapshotted, (
                f"the `{clause}` drift clause now reads {sorted(unsnapshotted)}, which the "
                "birth snapshot does not lock — the post-birth diff no longer subsumes it")


def test_corpus_acceptance_rates_are_reported():
    """The two headline numbers. Point any proposed change at this and compare, instead of
    arguing — that is what the corpus is for."""
    recon = [p for p in _CORPUS["honest"] if p["kind"] == "reconstructed_from_log"]
    accepted = [_deterministic_verdict(p["pitch"], _candidate(p["candidate"]))[0] for p in recon]
    must_block = [c for c in _CORPUS["adversarial"] if c["axis"] != "must_pass"]
    blocked = []
    for c in must_block:
        cand = _candidate(c["candidate"])
        passed, _ = _deterministic_verdict(c["pitch"], cand)
        blocked.append((not passed) or bool(seed_clause_drift(c.get("identity_terms"), cand)))
    must_pass = [c for c in _CORPUS["adversarial"] if c["axis"] == "must_pass"]
    kept = [_deterministic_verdict(c["pitch"], _candidate(c["candidate"]))[0] for c in must_pass]

    print("\n  ADVISORY EVIDENCE LAYER (the lexical checks, alone — a verdict nowhere):")
    print(f"    KNOWN FALSE POSITIVES accepted:   {sum(accepted)}/{len(accepted)}")
    print(f"    SUBSTITUTIONS blocked:            {sum(blocked)}/{len(blocked)}")
    print(f"    LEGITIMATE elaboration kept:      {sum(kept)}/{len(kept)}")
    print("  ^ these describe the EVIDENCE handed to the judge, not any outcome: nothing in "
          "the birth path is decided on these numbers any more, an outage included. The "
          "verdict is the judge's; see tests/integration/test_seed_identity_judge_eval.py.")
    assert accepted and blocked and kept
    # Pin the layer's profile so a change to it is visible. NOTE what this does NOT establish:
    # blocking 8/8 corpus substitutions is not evidence that the layer catches substitutions in
    # general — every one of these was hand-built to trip a lexical rule. `_CLEAN_SUBSTITUTION`
    # is the counterexample, and it is why this layer no longer decides anything.
    assert sum(blocked) == len(blocked), (
        "the advisory layer stopped flagging a substitution the corpus was built around; the "
        "judge now sees strictly less evidence than it was measured with")


class TestCaptureIsFaithfulEnoughToReplay:
    """`capture_gate_input` is the artifact that makes honest pairs assertable. If it were lossy,
    the corpus would replay differently from the run it came from — and would certify changes
    against a shape that never existed, which is the failure this whole corpus exists to avoid."""

    @staticmethod
    def _cand(**kw):
        base = dict(solution_name="X", description="a web app that monitors visibility",
                    value_proposition="see what AI assistants say", headline="",
                    core_features=[], seo_scalability_score=0.4, market_fit_score=0.7)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_a_captured_record_replays_to_the_same_verdict(self):
        from nicheiq.utils.seed_fidelity import capture_gate_input

        pitch = "A web app that monitors what AI assistants say about local businesses."
        for cand in (
            self._cand(),
            self._cand(data_sources=["OpenAI API", "Google Business Profile"]),
            self._cand(data_acquisition_notes="requires paid OpenAI API access"),
            self._cand(market_fit_claimed_route="USDA APHIS directory",
                       innovation_angle="USDA APHIS is the required differentiator."),
            self._cand(description="something entirely different about shipping pallets"),
        ):
            live = (unpitched_core_dependencies(pitch, cand), is_seed_faithful(pitch, cand))
            replayed = SimpleNamespace(**capture_gate_input(cand))
            got = (unpitched_core_dependencies(pitch, replayed),
                   is_seed_faithful(pitch, replayed))
            assert live == got, (
                f"capture is lossy — live {live} vs replayed {got} for "
                f"{getattr(cand, 'solution_name', '?')}")

    def test_capture_records_the_field_the_post_birth_lock_cannot_see(self):
        """S11's field is the one `capture_gate_input` used to drop, which made a refusal
        caused by it unreplayable from the trace.

        `differentiation_locus` is read by `unpitched_core_dependencies` (it is the
        `promoted_core` signal: "has this declared external source been promoted into the
        product's differentiation?") and is in none of `_IDENTITY_FIELDS`, `_ROUTE_FIELDS` or
        `_SUPPORTING_ROUTE_FIELDS` — the three tuples the capture used to union. The sibling
        test above could not catch it because none of its five candidates carries the field,
        which is trap 8: not-asserted, not not-covered.

        The probe is built so the field is the ONLY thing carrying the route's required role:
        `Acme Compliance Registry` is a declared `data_source` and nothing else in the copy
        says it is required. MEASURED against the old union: live
        `['Acme Compliance Registry']`, replayed `[]`.
        """
        from nicheiq.utils.seed_fidelity import capture_gate_input

        pitch = "A web app that monitors what AI assistants say about local businesses."
        cand = self._cand(
            data_sources=["Acme Compliance Registry"],
            differentiation_locus=(
                "The edge is that the product requires the external Acme Compliance "
                "Registry feed as its primary source."),
        )
        live = unpitched_core_dependencies(pitch, cand)
        assert live, (
            "the probe stopped exercising the gate at all — it can no longer detect a lossy "
            "capture, so fix the probe rather than deleting the assertion below")
        replayed = unpitched_core_dependencies(
            pitch, SimpleNamespace(**capture_gate_input(cand)))
        assert live == replayed, (
            f"capture is lossy on the role-bearing field — live {live} vs replayed {replayed}; "
            "a refusal this field caused cannot be reproduced from the birth trace")

    def test_capture_keeps_full_text_not_a_summary(self):
        """Token-overlap verdicts depend on the whole string; truncating in the capture layer
        would make a replay disagree with the run it recorded."""
        from nicheiq.utils.seed_fidelity import capture_gate_input

        long_desc = "word " * 400
        cap = capture_gate_input(self._cand(description=long_desc))
        assert cap["description"] == long_desc

    def test_capture_drops_empties_and_non_identity_fields(self):
        from nicheiq.utils.seed_fidelity import capture_gate_input

        cap = capture_gate_input(self._cand())
        assert "headline" not in cap and "core_features" not in cap  # empty
        assert "seo_scalability_score" not in cap  # a score, not identity
        assert "market_fit_score" not in cap
        assert "description" in cap and "solution_name" in cap
