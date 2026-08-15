"""The seed-identity birth capture, driven END TO END and asserted ON THE FILESYSTEM.

WHY THIS FILE EXISTS. S9 built `_write_seed_identity_trace` so the gates could be tuned against
real captured (pitch, candidate) pairs instead of by shipping a change and waiting for a user to
paste a log. Two later rounds were then blocked by the artifact's absence, and round 16 recorded
the mechanism as dead — "the birth capture built in S9 has never written a file" — on the strength
of `find output -name "seed_identity_trace*"` returning nothing.

That conclusion was wrong, and the way it was wrong is the reason this file drives the real path.
The mechanism worked; the search looked in the wrong directory, because the writer built its own
path out of `settings.output_dir` while every run's checkpoints go to `settings.checkpoint_dir`,
and the shipped local `.env` sets `OUTPUT_DIR=../output` — one level above the repo. "Never wired"
and "never run" and "written somewhere nobody looked" are three different states that look
identical from a green suite and from an empty `find`.

WHAT THESE TESTS REFUSE TO DO, and why each refusal is load-bearing:

  * They do not assert on a mock. Every test here reads bytes off the disk and parses them. A
    recorded call proves the flow reached the writer; it does not prove the writer wrote, which
    is the entire question two rounds could not answer.
  * They do not use the `FakeCrew` from `test_validate_idea_stage5.py`. That double never sets
    `_seed_identity_trace`, so `_write_seed_identity_trace` hits its `if not trace: return` guard
    in every one of those ~15 tests — the write is untouched by all of them, and severing it
    leaves them byte-identical green. These build a real `UnifiedSolutionCrew` and call the real
    `execute_seed_pipeline`, stubbing the provider boundary and the generator and nothing else.
  * They do not assert the trace is non-empty and stop there. A trace that fires and omits the
    one field the next question needs is worth almost nothing, which is exactly the state S18
    found. `test_the_trace_carries_the_generators_delivery_format` is the field-level pin.

The fail-soft `except` in the writer is deliberate and stays: telemetry must never break a paid
run. It is also why these tests must look at the filesystem — under that `except`, a silent
failure and a success are indistinguishable from the caller's side.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import nicheiq.crews.idea_improvement_loop_v4 as _v4
import nicheiq.crews.unified_solution_crew as usc
import nicheiq.flows.research_flow as rf
from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.research_state import ResearchState

_CORPUS = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "seed_identity_corpus.json").read_text()
)
_CASE = next(p for p in _CORPUS["honest"] if p["id"] == "056b2c68")

# Deliberately not a real delivery format. `infer_delivery_format` cannot produce it and
# `normalize_delivery_format` cannot round-trip to it, so its presence in a trace record can
# ONLY mean the record was taken before the pitch stamp overwrote the generator's value.
_GENERATOR_MARKER = "generator-emitted-marker-not-a-real-format"


def _candidate(**over):
    spec = dict(_CASE["candidate"])
    # `execute_seed_pipeline` reads these on the accepted path; the corpus fixture is a
    # gate-input capture and carries only identity/route fields.
    spec.update(
        incumbent_parity="unclear",  # neither the pivot branch nor the brief probe
        candidate_status="active",
        generation_operation_id=None,
        duplicate_of=None,
        delivery_format=_GENERATOR_MARKER,
    )
    spec.update(over)
    return SimpleNamespace(**spec)


@pytest.fixture
def trace_dir(tmp_path, monkeypatch):
    """Point the writer's directory at a clean tmp dir, THROUGH the setting it really reads.

    Patching `checkpoint_dir` (not `output_dir`) is itself part of the pin: if the writer is
    ever pointed back at a hand-built `output_dir / "checkpoints"`, these tests find an empty
    directory and fail, instead of silently passing because both happened to resolve alike on
    a machine with no `OUTPUT_DIR` set.

    `output_dir` is redirected too, and not for symmetry: during the revert proof for the
    location fix these tests wrote six real trace files into `<repo>/../output/checkpoints`,
    the live harvest directory, because only `checkpoint_dir` was redirected. A test that can
    write outside `tmp_path` when the code under test regresses is a test that contaminates the
    corpus it exists to protect.
    """
    d = tmp_path / "checkpoints"
    monkeypatch.setattr(rf.settings, "checkpoint_dir", d)
    monkeypatch.setattr(rf.settings, "output_dir", tmp_path / "output")
    return d


def _crew(monkeypatch, *, same_product=True, candidate=None, on_tail=None):
    """A real `UnifiedSolutionCrew` with only the provider boundary and generator replaced."""
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    cand = candidate if candidate is not None else _candidate()

    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **kw: cand)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail",
                        on_tail or (lambda self, wave: None))
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)

    def fake_invoke(**kwargs):
        return SimpleNamespace(
            same_product=same_product, changed_axes=[], rationale="stub"), None

    monkeypatch.setattr(usc.LLMService, "invoke_structured", fake_invoke)
    monkeypatch.setattr(usc, "_SEED_JUDGE_RETRY_DELAY_S", 0)
    return crew, cand


def _flow(job_id):
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.entry_mode = "validate_idea"
    flow._state = ResearchState()
    flow._state.user_idea_text = _CASE["pitch"]
    flow.job_id = job_id
    flow._emit_progress = lambda *a, **k: None
    return flow


def _drive(monkeypatch, job_id, **crew_kw):
    crew, cand = _crew(monkeypatch, **crew_kw)
    flow = _flow(job_id)
    pool = SimpleNamespace(solution_ideas=[])
    flow._inject_validate_seed(crew, pool)
    return flow, crew, pool, cand


def _written(trace_dir) -> dict:
    """The single trace file on disk, parsed. Fails loudly on absence — the whole point."""
    files = sorted(trace_dir.glob("seed_identity_trace_*.json"))
    assert files, (
        f"no seed_identity_trace_*.json under {trace_dir} — the birth capture wrote nothing. "
        "The writer is fail-soft by design, so check the [SeedTrace] WARNING it logs.")
    assert len(files) == 1, f"expected one trace file, found {[f.name for f in files]}"
    raw = files[0].read_bytes()
    assert raw, f"{files[0]} exists but is empty"
    return json.loads(raw)


# ── the two exits the brief named ──────────────────────────────────────────────────────────

def test_the_refused_path_writes_a_trace_file(monkeypatch, trace_dir):
    """A refusal is the more valuable record: the candidate is discarded and lost otherwise."""
    _drive(monkeypatch, "job-refused", same_product=False)

    payload = _written(trace_dir)
    assert payload["outcome"] == "judged_a_different_product"
    assert payload["pitch"] == _CASE["pitch"]
    assert payload["job_id"] == "job-refused"
    gates = {g["gate"]: g for g in payload["gates"]}
    assert "semantic" in gates and gates["semantic"]["verdict"] == "refused"
    # The record must carry the candidate the gate SAW, not an empty dict. A stale artifact
    # found outside the repo had `"candidate": {}` on every record, which is why this asserts
    # on the payload rather than on the gate list's length.
    assert gates["semantic"]["candidate"], "the refusing gate recorded no candidate"


def test_the_accepted_path_writes_a_trace_file(monkeypatch, trace_dir):
    _, _, pool, _ = _drive(monkeypatch, "job-accepted", same_product=True)
    assert len(pool.solution_ideas) == 1, "precondition: the seed must have been injected"

    payload = _written(trace_dir)
    assert payload["outcome"] == "accepted"
    verdicts = {g["gate"]: g["verdict"] for g in payload["gates"]}
    assert verdicts.get("final_accepted") == "accepted", verdicts


# ── the field S18 needed, and could not get ────────────────────────────────────────────────

def test_the_trace_carries_the_generators_delivery_format(monkeypatch, trace_dir):
    """The one field the NEXT question needs, captured BEFORE the pitch stamp overwrites it.

    `execute_seed_pipeline` stamps `delivery_format = infer_delivery_format(fidelity_brief)`
    shortly after generation, and that stamp is not a fallback — it overrides a typed value on
    38 of 38 refined candidates. Every `_trace` call except the first sits below it, so before
    the `generated` record existed the generator's value appeared in ZERO trace records on both
    exits, measured with this same marker. S18 had to reason from fixture material instead.

    Both halves are asserted deliberately. Dropping the `generated` record fails the first;
    moving it below the stamp fails it too, since the marker cannot survive `infer`. The second
    half pins that this is a CAPTURE and not a behaviour change — the stamp still wins in the
    candidate the pipeline actually grades, which the S18 measurement says it must.
    """
    _drive(monkeypatch, "job-df", same_product=True)

    payload = _written(trace_dir)
    by_gate = {g["gate"]: (g["candidate"] or {}) for g in payload["gates"]}

    assert "generated" in by_gate, (
        "no `generated` record: the trace has nothing taken before the delivery stamp, so it "
        "cannot answer what the generator produced — the S18 blocker, unmoved. "
        f"gates present: {sorted(by_gate)}")
    assert by_gate["generated"].get("delivery_format") == _GENERATOR_MARKER, (
        "the `generated` record was taken AFTER the pitch stamp overwrote the generator's "
        f"delivery_format (got {by_gate['generated'].get('delivery_format')!r})")

    post = [g for g in ("birth_evidence", "birth_accepted", "final_accepted") if g in by_gate]
    assert post, "no post-stamp gate recorded; this test would be vacuous"
    for gate in post:
        assert by_gate[gate].get("delivery_format") != _GENERATOR_MARKER, (
            f"`{gate}` still carries the generator's value — the pitch stamp no longer runs, "
            "which is a behaviour change this capture was not supposed to make")


# ── the location (why round 16 concluded the mechanism was dead) ───────────────────────────

def test_the_trace_lands_in_the_checkpoint_directory(tmp_path, monkeypatch):
    """Not in a path hand-built from `output_dir`, which diverges under the shipped `.env`.

    Driven with the two settings pointed at DIFFERENT directories, which is the shipped local
    configuration (`OUTPUT_DIR=../output`, `checkpoint_dir` at its own default) and the exact
    condition under which the artifact went unfound. If the writer is repointed at
    `output_dir / "checkpoints"`, the file lands in `elsewhere` and this fails.
    """
    checkpoints = tmp_path / "checkpoints"
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setattr(rf.settings, "checkpoint_dir", checkpoints)
    monkeypatch.setattr(rf.settings, "output_dir", elsewhere)

    _drive(monkeypatch, "job-loc", same_product=True)

    assert sorted(p.name for p in checkpoints.glob("seed_identity_trace_*.json")) == [
        "seed_identity_trace_job-loc.json"], (
        "the trace is not in settings.checkpoint_dir — this is precisely the defect that made "
        "round 16 record the capture as never written")
    assert not list(elsewhere.rglob("seed_identity_trace_*.json")), (
        "the trace was written under output_dir, one level away from every run's checkpoints")


# ── the two exits the docstring claimed and the code did not honour ────────────────────────

def test_the_post_birth_drift_refusal_writes_a_trace(monkeypatch, trace_dir):
    """A candidate that cleared birth and was then rewritten before pool injection.

    This is the richest trace the method can produce — the candidate passed every birth gate,
    so the record carries `birth_accepted` — and it is the refusal nobody can reconstruct from
    anything else, because the drifted candidate is dropped and never persisted. Until this
    round the exit returned without writing, while the writer's own docstring said it wrote on
    both paths.

    THE OUTCOME STRING ALONE CANNOT TELL YOU WHICH EXIT RAN, and the first version of this test
    was fooled by that. Rewriting `solution_name` inside `_finalize_seed_tail` does produce
    `outcome == "identity_changed_in_final_evaluation"` — but from the CREW, whose own
    post-tail check (`unified_solution_crew.py`, `final_changes = ...`) runs immediately after
    the tail against the same lock and refuses first. The run then leaves by the `seed is None`
    exit, which already wrote a trace before this round, so the test passed with the fix
    reverted. The flow's branch deliberately REUSES the crew's cause string, so the two exits
    are indistinguishable by outcome; they are distinguishable by the TRACE, which is the point
    of having one. A crew refusal ends in `post_tail`/`refused`; a flow refusal ends in
    `final_accepted`/`accepted` — the crew said yes and our diff said no.

    So the drive substitutes the lock ATTRIBUTE the flow reads. The crew's two checks use the
    LOCAL `identity_lock`, so birth completes normally; the flow then diffs an accepted
    candidate against a snapshot that disagrees with it, which is exactly the branch's premise.

    Reachability, stated plainly: in production this branch needs something to mutate the seed
    between the crew returning and the flow's diff, i.e. `_attempt_validate_pivot` (parity
    `shipped`/`partial`) or `_probe_seed_brief_parity` (parity `none`). Under any other parity
    nothing runs in between and the branch cannot fire. That is a narrow window, not an absent
    one, and it is the window in which the trace is the only surviving record of the candidate.
    """
    def substitute_lock_after_birth(self, wave):
        # Same fields, one deliberately different value. The crew's local lock is untouched.
        self._seed_identity_lock = dict(
            self._seed_identity_lock,
            solution_name="a snapshot that disagrees with the candidate")

    _, _, pool, _ = _drive(monkeypatch, "job-drift", same_product=True,
                           on_tail=substitute_lock_after_birth)
    assert not pool.solution_ideas, "precondition: the drifted seed must have been refused"

    payload = _written(trace_dir)
    assert payload["outcome"] == "identity_changed_in_final_evaluation"
    gates = [g["gate"] for g in payload["gates"]]
    assert gates[-1] == "final_accepted", (
        "this refusal came from the CREW, not from the flow's post-birth diff — the exit under "
        f"test was never reached. gates: {gates}")
    assert "birth_accepted" in gates, (
        "the record should show the candidate cleared birth before the flow refused it")


def test_the_comparison_failure_refusal_writes_a_trace(monkeypatch, trace_dir):
    """OUR field diff raised. Deterministic and network-free, so the trace is the only record.

    Driven by corrupting the lock ATTRIBUTE the flow reads, rather than by monkeypatching
    `changed_seed_identity_fields`. Patching the function was the first attempt and it does not
    reach this exit: the crew calls the same function twice itself (post-wave and post-tail,
    against a LOCAL `identity_lock`), so a raising stub kills birth instead and the run leaves
    by the `seed is None` exit with cause `unknown`. The test passed through the wrong door and
    said so. Corrupting `crew._seed_identity_lock` inside the tail leaves the crew's own two
    calls untouched — they use the local — and raises in exactly one place: the flow's diff.
    """
    def corrupt_lock_after_birth(self, wave):
        # A non-dict, non-empty value: truthy, so the flow's `if lock` guard passes, and
        # `changed_seed_identity_fields` raises AttributeError on `.items()`.
        self._seed_identity_lock = ["not a snapshot mapping"]

    _, _, pool, _ = _drive(monkeypatch, "job-boom", same_product=True,
                           on_tail=corrupt_lock_after_birth)
    assert not pool.solution_ideas, "precondition: the seed must have been refused"

    payload = _written(trace_dir)
    assert payload["outcome"] == "identity_check_could_not_run", (
        "wrong exit — this test must reach the flow's `except`, not a crew-level refusal")
    assert payload["gates"], "the trace was written empty"


# ── the guard on the guard ────────────────────────────────────────────────────────────────

def test_the_writer_stays_fail_soft(monkeypatch, tmp_path):
    """Telemetry must never break a paid run — but it must SAY so, not vanish.

    The `except` is deliberate and must not be removed. What this pins is that a write failure
    is LOUD, because under a silent fail-soft `except` "wrote nothing" and "wrote fine" are the
    same observation from the caller's side, and that ambiguity is what cost this program two
    rounds. This is also the check that would have answered "has that warning ever appeared in
    the worker logs?" — it never had, and now its absence means something.

    The failure is a real OS error, not a patched `Path.mkdir`: `checkpoint_dir` is placed
    UNDER a regular file, so `mkdir(parents=True)` raises NotADirectoryError from the kernel.
    Patching `Path.mkdir` globally was the first attempt and it is too broad — it fires inside
    unrelated pipeline code and stops proving anything about this writer.

    `caplog` cannot see this: the project logs through loguru, which does not propagate to the
    stdlib `logging` root that pytest's fixture captures. A `caplog`-based version of this test
    passed vacuously in neither direction — it simply never saw a record, which reads exactly
    like a missing warning.
    """
    from loguru import logger as loguru_logger

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setattr(rf.settings, "checkpoint_dir", blocker / "cp")
    # Redirected for the same reason as in `trace_dir`: without it, a regression that repoints
    # the writer at `output_dir` sends this test's artifact into the live harvest directory.
    monkeypatch.setattr(rf.settings, "output_dir", tmp_path / "output")

    lines: list[str] = []
    sink_id = loguru_logger.add(lines.append, level="WARNING", format="{message}")
    try:
        _, _, pool, _ = _drive(monkeypatch, "job-failsoft", same_product=True)
    finally:
        loguru_logger.remove(sink_id)

    assert len(pool.solution_ideas) == 1, (
        "a telemetry write failure killed the seed injection — the `except` must stay fail-soft")
    assert any("[SeedTrace] write skipped" in line for line in lines), (
        "the write failed silently; a fail-soft telemetry path must still leave a WARNING or "
        f"its absence is unfalsifiable. warnings seen: {lines}")


# ── S24: the walk's verdicts, ON DISK ─────────────────────────────────────────────────────

def test_the_written_trace_describes_every_candidate_the_walk_judged(monkeypatch, trace_dir):
    """D-4, asserted where this module always asserts: on the bytes.

    Every other test in this file stubs `_run_seed_cell`, so none of them can see the walk S23
    put inside the cell. That is precisely how the gap survived: all 12 `_trace` sites live in
    `execute_seed_pipeline`, `_expand_seed_until_judged` only LOGGED, and the persisted artifact
    therefore described ONE candidate on a run that judged several. The refused expansions are
    discarded inside the cell and nothing else in the pipeline persists them, so if they are not
    in this file they do not exist anywhere.

    This test keeps the REAL `_run_seed_cell` -> `_tournament_cell` -> `_expand_seed_until_judged`
    chain and replaces only the generator, the refiner and the provider boundary.
    """
    accepted = "TheRealProduct"
    seed = ("A simple web app that monitors your visibility across AI assistants for local "
            "businesses in London")

    def concept(name, one_liner):
        return SimpleNamespace(
            concept_name=name, one_liner=one_liner, project_type="saas",
            delivery_format="web-app", target_keywords=[], why_non_obvious="w",
            source_pain=None, source_segment=None, obviousness_score=0.3,
            data_feasibility_score=0.7, build_feasibility_score=0.8,
            data_access_model="public", critic_no_route=False,
            mechanism_tag=f"m-{name}", data_source_tag=f"d-{name}", journey_tag=f"j-{name}")

    def spec(c):
        name = c.concept_name
        return SimpleNamespace(
            solution_name=f"spec-of-{name}",
            short_description=f"{name}: monitors AI assistant answers for London businesses.",
            description=f"{name} runs local-intent prompts across AI assistants.",
            value_proposition=f"{name} shows how AI assistants describe a London business.",
            project_type="saas", delivery_format="web-app", data_access_model="public",
            data_acquisition_notes=f"{name} reads public assistant answers.",
            source_pain=None, source_segment=None, mechanism_tag=None, data_source_tag=None,
            journey_tag=None, obviousness_score=None, data_feasibility_score=None,
            build_feasibility_score=None, pain_points_addressed=[], unanchored_hypothesis=None,
            incumbent_parity="unclear", candidate_status="active",
            generation_operation_id=None, duplicate_of=None)

    pool = [concept("EchoOfThePitch", seed),
            concept(accepted, "A web app that monitors visibility across AI assistants")]

    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    judged: list[str] = []

    def judge(_self, _seed, candidate, evidence=None):
        judged.append(candidate.solution_name)
        return candidate.solution_name == f"spec-of-{accepted}"

    crew._semantic_seed_identity_matches = judge.__get__(crew, UnifiedSolutionCrew)

    monkeypatch.setattr(UnifiedSolutionCrew, "_build_seed_crew_inputs", lambda _s: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_one_sample", lambda _s, *a, **kw: (pool, []))
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_concepts",
                        lambda _s, concepts, idx=None: [])
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept",
                        lambda _s, c, p, **kw: spec(c))
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda _s, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda _s, i: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda _s, wave, **kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda _s, wave: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda _s, u: None, raising=False)
    monkeypatch.setattr(_v4, "tournament_refine_cell_v4",
                        lambda cands, grounding, **kw: cands[0])

    flow = _flow("job-walk")
    flow._state.user_idea_text = seed
    flow._inject_validate_seed(crew, SimpleNamespace(solution_ideas=[]))

    assert judged[:2] == ["spec-of-EchoOfThePitch", f"spec-of-{accepted}"], (
        "precondition: the walk must have advanced past a refused candidate")

    payload = _written(trace_dir)
    walk = [g for g in payload["gates"] if g["gate"] == "cell_pre_check"]
    assert [(g["verdict"], g["reason"]) for g in walk] == [
        ("refused", "fidelity_rank_1_of_2:EchoOfThePitch"),
        ("accepted", f"fidelity_rank_2_of_2:{accepted}"),
    ], f"gates on disk: {[(g['gate'], g['verdict']) for g in payload['gates']]}"
    assert walk[0]["candidate"]["solution_name"] == "spec-of-EchoOfThePitch", (
        "the refused expansion was recorded without the candidate it was a verdict about — "
        "which is the one object nothing else in the pipeline persists")
