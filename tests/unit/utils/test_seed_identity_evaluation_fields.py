"""The post-birth identity lock must watch PRODUCT AXES, not EVALUATION EVIDENCE.

WHAT THIS IS ABOUT. `_IDENTITY_FIELDS` conflated two kinds of field:

  * a PRODUCT AXIS — what the thing IS. `solution_name`, `description`, `core_features`.
    A change here means a different product, and the post-birth diff must keep watching it.
  * EVALUATION EVIDENCE — what we CONCLUDED about it. `market_fit_claimed_route` is the
    route the calibration critic cited; `data_access_model` is the route verifier's verdict;
    `data_acquisition_notes` is the cost/ToS disclosure. The pipeline writes these AFTER
    birth by design, so a diff over them measures our own machinery.

THE ORACLE IS A REAL PRODUCTION RUN, not a hand-written fixture. Job
8580c179-5fcb-441f-8fee-5e14fd0eaf43 is a completed, ~40-minute, fully paid "Check my idea"
run on the 268-character pitch that motivated this whole program. Its birth trace is the
first this program ever captured, and it records the failure exactly:

    [0] generated       advisory   candidate_as_generated
    [1] birth_evidence  advisory   drift ['mechanism'], retention 17/23 (floor 14) MET
    [2] birth_accepted  accepted   <- the judge said yes
    [3] post_wave       refused    identity_changed_during_scoring

with the log naming the cause: `fields=['market_fit_claimed_route']`. Nothing about the
user's product changed. The trace is vendored at `tests/fixtures/seed_identity_trace_8580c179.json`
byte for byte, and the fixture-shape guard below is what keeps it that way — trap 1 and
trap 9 in the ledger are both "a fixture in a shape the producer cannot emit", and they cost
this program six rounds.

WHY THE TESTS DRIVE THE WRITER RATHER THAN COMPARING TUPLES. Trap 13: a test whose only
inputs are two literals declared in the test file asserts that a LIST IS CORRECT, never that
the list is TRUE. So the load-bearing test here runs the real `_finalize_idea_pool` — the
FIRST post-birth wave step, and the pass that actually cleared the field on the live run —
over the real captured candidate, and asks the real `changed_seed_identity_fields` what it
sees. It goes red if a future pass starts writing a locked product axis, and it goes red if
a field is moved out of the lock that the pool contract never touches.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nicheiq.utils import seed_fidelity as sf
from nicheiq.utils.seed_fidelity import (
    _EVALUATION_FIELDS,
    _IDENTITY_FIELDS,
    _PRODUCT_IDENTITY_FIELDS,
    capture_gate_input,
    changed_seed_identity_fields,
    seed_identity_snapshot,
)

_TRACE = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures"
     / "seed_identity_trace_8580c179.json").read_text()
)
_GATES = {g["gate"]: g for g in _TRACE["gates"]}


def _replay(gate: str) -> SimpleNamespace:
    """The candidate exactly as `capture_gate_input` recorded it at that gate.

    `capture_gate_input` drops empties, so a field cleared between two gates is ABSENT from
    the later record rather than present-and-None. `SimpleNamespace` + the gates' own
    `getattr(..., None)` reproduces that faithfully, which is the whole point of replaying
    from the capture instead of from a reconstruction.
    """
    return SimpleNamespace(**(_GATES[gate]["candidate"] or {}))


def _as_solution_idea(spec: dict):
    """The captured candidate rebuilt as the real model the pipeline mutates.

    Only the fields the capture omits BECAUSE THEY ARE REQUIRED are defaulted; nothing that
    the gates read is invented here.
    """
    from nicheiq.models.solution_idea import SolutionIdea

    s = dict(spec)
    for required, blank in (("pain_points_addressed", []), ("core_features", []),
                            ("target_personas", [])):
        s.setdefault(required, blank)
    idea = SolutionIdea(**{k: v for k, v in s.items() if k in SolutionIdea.model_fields})
    # As the seed path stamps them at birth, so the pool contract's validate-marker
    # keep-guard takes the branch production takes.
    idea.source_frame = "user_seed"
    idea.generation_operation_id = "validate"
    return idea


def _pool_contract(idea) -> None:
    """The real first post-birth wave step, on a bare instance.

    `_finalize_idea_pool` reads no crew state beyond two canonicalizer methods, and the two
    network-ish helpers it imports are only reached for restrictively-labelled routes, so it
    runs offline. This is the pass that cleared `market_fit_claimed_route` on the live run
    (the Q-030/Q-035 guarded reset for never-calibrated ideas — the `*_score_raw` branch inside
    `UnifiedSolutionCrew._finalize_idea_pool`; named rather than cited by line, because the
    range this docstring used to carry, `unified_solution_crew.py:10453-10456`, was the
    `_keep_validate_marker` tuple and not the reset at all).
    """
    from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

    UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)._finalize_idea_pool([idea])


class TestTheVendoredTraceIsTheProducersShape:
    """Trap 1 / trap 9: a hand-authored or hand-CORRECTED fixture is the same root cause with
    a longer fuse. This trace was copied byte for byte off `output/checkpoints/`; these
    assertions are what makes an edit to it fail rather than quietly retune the test."""

    def test_the_trace_records_the_four_gates_the_live_run_recorded(self):
        assert [(g["gate"], g["verdict"]) for g in _TRACE["gates"]] == [
            ("generated", "advisory"),
            ("birth_evidence", "advisory"),
            ("birth_accepted", "accepted"),
            ("post_wave", "refused"),
        ]
        assert _TRACE["outcome"] == "identity_changed_during_scoring"

    def test_every_captured_key_is_one_capture_gate_input_can_emit(self):
        emittable = set(capture_gate_input(SimpleNamespace(
            **{f: "x" for f in
               set(_IDENTITY_FIELDS) | set(sf._ROUTE_FIELDS)
               | set(sf._SUPPORTING_ROUTE_FIELDS) | set(sf._ROUTE_ASSERTION_FIELDS)})))
        for gate in _TRACE["gates"]:
            unknown = set(gate["candidate"] or {}) - emittable
            assert not unknown, (
                f"gate {gate['gate']} carries {sorted(unknown)}, which `capture_gate_input` "
                "cannot produce — the fixture has been hand-edited and no longer replays the "
                "run it claims to be")

    def test_the_judge_accepted_this_candidate(self):
        """The refusal under test happened AFTER the only authority ruled. If this ever
        stopped being true the test below would be measuring a candidate the birth gate
        rejected, which is a different question entirely."""
        assert _GATES["birth_accepted"]["verdict"] == "accepted"
        assert _GATES["birth_evidence"]["verdict"] == "advisory"


class TestTheLiveRefusalIsGone:
    def test_the_post_birth_diff_no_longer_refuses_job_8580c179(self):
        """Record [3] turns from `refused` into an acceptance, driven from the real trace.

        Before the split this returned `['market_fit_claimed_route']` and destroyed the run.
        """
        lock = seed_identity_snapshot(_replay("birth_accepted"))
        assert changed_seed_identity_fields(lock, _replay("post_wave")) == []

    def test_the_only_thing_that_moved_was_evidence_the_pipeline_owns(self):
        """States what DID change, so this is not read as "nothing happened". Both movers are
        fields the pipeline re-derives after birth by design: the critic's cited route, and
        `differentiation_locus`, which the parity pass clears on every run and which is
        already excluded from `_IDENTITY_FIELDS` for that reason."""
        born, scored = _replay("birth_accepted"), _replay("post_wave")
        moved = {
            f for f in set(vars(born)) | set(vars(scored))
            if getattr(born, f, None) != getattr(scored, f, None)
        }
        assert moved == {"market_fit_claimed_route", "differentiation_locus"}
        assert not moved & set(_PRODUCT_IDENTITY_FIELDS)


class TestThePostBirthWriterCannotMoveALockedField:
    """THE CLASS, not the instance. `_IDENTITY_FIELDS` had one evaluation field in it that we
    know of; the next critic pass writing the next one would reproduce this failure exactly.
    So rather than assert "market_fit_claimed_route is unlocked", drive the real writer and
    assert it moves NOTHING the lock watches."""

    def test_the_pool_contract_moves_nothing_the_lock_watches(self):
        idea = _as_solution_idea(_GATES["birth_accepted"]["candidate"])
        lock = seed_identity_snapshot(idea)
        _pool_contract(idea)
        assert changed_seed_identity_fields(lock, idea) == [], (
            "the FIRST post-birth pass moved a field the post-birth diff refuses on — this "
            "is the shape of the 8580c179 kill. Either the field is evaluation evidence and "
            "belongs in `_EVALUATION_FIELDS` with its reason, or the pass should not be "
            "writing a product axis after birth.")

    @pytest.mark.parametrize("declared,expected", [
        # A prose value the closed-vocab screen rejects: dropped, and the prose is relocated
        # into the disclosure note. Two evaluation fields move in one branch.
        ("partner feed, negotiated", None),
        # A legacy vocabulary alias. Pure renaming — 'licensed' and 'paywalled' are the same
        # access model, and under the old snapshot this alone refused a fully paid run.
        ("licensed", "paywalled"),
    ])
    def test_the_route_verdict_vocabulary_is_not_a_product_change(self, declared, expected):
        spec = dict(_GATES["birth_accepted"]["candidate"])
        spec["data_access_model"] = declared
        idea = _as_solution_idea(spec)
        lock = seed_identity_snapshot(idea)
        _pool_contract(idea)
        assert idea.data_access_model == expected, (
            "this test is only meaningful while the pool contract still rewrites the field")
        assert changed_seed_identity_fields(lock, idea) == []


class TestTheLockStillCatchesAProductChange:
    """The stop condition, made permanent. This change is a LOOSENING, so the risk runs the
    other way from most rounds here: the thing to prove is that what the tighter lock
    correctly blocked is still blocked."""

    @pytest.mark.parametrize("field", _PRODUCT_IDENTITY_FIELDS)
    def test_a_post_birth_rewrite_of_a_product_axis_is_still_refused(self, field):
        born = _replay("birth_accepted")
        lock = seed_identity_snapshot(born)
        rewritten = _replay("birth_accepted")
        setattr(rewritten, field, "a different product entirely")
        assert field in changed_seed_identity_fields(lock, rewritten)

    def test_the_S3_S4_class_of_wholesale_replacement_is_still_refused(self):
        """The failure the lock exists for: a later pass swapping the user's product for
        another one (red-team revision, parity pivot). Every product axis moves at once."""
        born = _replay("birth_accepted")
        lock = seed_identity_snapshot(born)
        replacement = SimpleNamespace(
            solution_name="LondonReviewReplyWriter",
            headline="Writes replies to Google reviews for London shops",
            description="Drafts and posts review replies on behalf of local businesses.",
            value_proposition="Never write a review reply by hand again.",
        )
        assert "solution_name" in changed_seed_identity_fields(lock, replacement)

    def test_a_blank_fill_of_a_product_axis_is_still_refused(self):
        """`changed_seed_identity_fields` flags blank-fills as well as rewrites, and that is
        load-bearing: a pass that INVENTS a `technical_approach` the user never submitted is
        the same defect as one that rewrites it."""
        born = _replay("birth_accepted")
        born.mechanism_tag = None
        lock = seed_identity_snapshot(born)
        filled = _replay("birth_accepted")
        filled.mechanism_tag = "invented-by-a-later-pass"
        assert "mechanism_tag" in changed_seed_identity_fields(lock, filled)


class TestTheClassificationIsWellFormed:
    def test_every_evaluation_field_is_actually_an_identity_field(self):
        """Not tautological, and the reason this exists: `_PRODUCT_IDENTITY_FIELDS` is derived
        by EXCLUSION, so a misspelled or renamed entry in `_EVALUATION_FIELDS` silently
        excludes nothing and the lock quietly goes back to refusing paid runs."""
        stray = set(_EVALUATION_FIELDS) - set(_IDENTITY_FIELDS)
        assert not stray, (
            f"{sorted(stray)} is in `_EVALUATION_FIELDS` but not in `_IDENTITY_FIELDS`, so it "
            "excludes nothing — check the spelling against the model field")

    def test_the_snapshot_reads_the_product_tuple_and_only_it(self):
        """Driven, not compared: build a recording candidate and see which names the snapshot
        actually asks for. A tuple walk cannot see which tuple the function reads."""
        seen: set[str] = set()

        class _Recorder:
            def __getattr__(self, name):
                seen.add(name)
                return "x"

        seed_identity_snapshot(_Recorder())
        assert seen == set(_PRODUCT_IDENTITY_FIELDS)
        assert not seen & set(_EVALUATION_FIELDS)
