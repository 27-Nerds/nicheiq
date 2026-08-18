"""Stage-5 seed injection for "Check my idea" (plan P4).

Covers: snapshot/restore of the crew's per-op scratch state (execute_seed_pipeline resets
it and the Stage-5 harvest reads it afterwards), marker stamping (AFTER the pipeline call),
append-not-replace pivot semantics with an always-written attempt record, degradation on
seed failure, systemic-breaker propagation, and the _finalize_idea_pool keep-guard that
protects the markers from later merged-pool re-scoring.
"""

from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.research_state import ResearchState
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.llm_service import LLMSystemicError

POOL_SCRATCH = {
    "_tournament_ctx": {"pool": True},
    "ruled_out_pains": [{"finding_id": "pool-1"}],
    "overlap_groups": ["g1"],
    "funnel_counts": {"pool": 9},
    "_ma_serper_calls": 7,
    "_birth_verified_names": {"PoolIdea"},
    "_route_label_counts": {"public": 3},
    "coverage_caveats": ["pool caveat"],
    "_current_seed_text": None,
    "_current_seed_dispatch_id": None,
    "_current_seed_evaluation": None,
}


def _seed_idea(parity="none found"):
    return SimpleNamespace(
        solution_name="Green Lot Freshness Tracker",
        description="Tracks green coffee lots and predicts staleness windows.",
        value_proposition="Roasters stop discovering flat inventory too late.",
        target_personas=["small-batch roasters"],
        pain_points_addressed=["stale green inventory"],
        incumbent_parity=parity,
        candidate_status="active",
        generation_operation_id=None,
        duplicate_of=None,
        innovation_angle=None,
    )


class FakeCrew:
    def __init__(self, seed_result="idea", parity="none found",
                 raise_systemic=False, pivot_rev=None, pivot_ok=False,
                 brief_probe_result=(None, 0), failure_reason=None):
        for attr, value in POOL_SCRATCH.items():
            setattr(self, attr, value if not isinstance(value, (list, dict, set))
                    else type(value)(value))
        self._ma_search_lock = object()
        self._pool_lock = self._ma_search_lock
        self._incumbent_rows = [{"name": "CompetX", "gap": "no support-history access"}]
        self._seed_result = seed_result
        self._parity = parity
        self._raise_systemic = raise_systemic
        self._pivot_rev = pivot_rev
        self._pivot_ok = pivot_ok
        self.gaps_seen = None
        self.scored = None
        self._brief_probe_result = brief_probe_result
        self.brief_probe_seen = None
        self._seed_failure_reason = failure_reason

    def _probe_seed_brief_parity(self, seed, mechanism_terms):
        # The real method is fail-soft internally — it returns (None, n), never raises.
        self.brief_probe_seen = (getattr(seed, "solution_name", None),
                                 list(mechanism_terms or []))
        return self._brief_probe_result

    def execute_seed_pipeline(self, req):
        self.seed_request_seen = req
        # Simulate the real entry reset (unified_solution_crew.py:8520-8527 + seed residue).
        self._tournament_ctx = {"seed": True}
        self.ruled_out_pains = [{"finding_id": "seed-1"}]
        self.overlap_groups = []
        self.funnel_counts = {}
        self._ma_serper_calls = 3
        self._birth_verified_names = set()
        self._route_label_counts = {}
        self.coverage_caveats = ["pool caveat", "bogus one-idea coverage caveat"]
        self._current_seed_text = getattr(req, "seed_text", None)
        self._current_seed_dispatch_id = getattr(req, "dispatch_id", None)
        if self._raise_systemic:
            raise LLMSystemicError("breaker tripped")
        if self._seed_result is None:
            return None
        return _seed_idea(self._parity)

    def _generate_pivot_revision(self, orig, gaps_by_name):
        self.gaps_seen = gaps_by_name
        return self._pivot_rev

    def _score_wave(self, ideas, **kwargs):
        self.scored = list(ideas)

    def _pivot_acceptable(self, orig, rev):
        return self._pivot_ok


def _flow():
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.entry_mode = "validate_idea"
    flow._state = ResearchState()
    flow._state.user_idea_brief = "Tracks green coffee lots for roasters."
    flow._emit_progress = lambda *a, **k: None
    return flow


def _pool():
    return SimpleNamespace(solution_ideas=[SimpleNamespace(
        solution_name="Roast Batch Planner",
        description="Plans roast batches from wholesale orders.",
        value_proposition="Fewer wasted roasts.",
        target_personas=["roasters"],
    )])


def _assert_scratch_restored(crew):
    for attr, value in POOL_SCRATCH.items():
        if attr == "_tournament_ctx":
            continue
        assert getattr(crew, attr) == value, f"{attr} not restored"
    assert crew._tournament_ctx is None  # seed path re-sets it; must be nulled


def test_seed_appended_with_marker_and_scratch_restored():
    flow, crew, pool = _flow(), FakeCrew(), _pool()
    flow._inject_validate_seed(crew, pool)

    assert len(pool.solution_ideas) == 2
    seed = pool.solution_ideas[-1]
    assert seed.solution_name == "Green Lot Freshness Tracker"
    assert seed.generation_operation_id == "validate"  # stamped AFTER the pipeline
    _assert_scratch_restored(crew)
    # Seed's own ruled-out entries merged; pool ledger untouched on the crew.
    assert {f["finding_id"] for f in flow.state.idea_ruled_out} == {"seed-1"}
    # No parity cap → pivot explicitly recorded as not attempted.
    assert flow.state.user_idea_pivot["outcome"] == "not_attempted"


def test_pivot_rejected_records_reason_and_is_not_appended():
    rev = _seed_idea()
    rev.solution_name = "Pivoted Tracker"
    flow = _flow()
    crew = FakeCrew(parity="shipped (Cropster): lot tracking shipped since 2021",
                    pivot_rev=rev, pivot_ok=False)
    pool = _pool()
    flow._inject_validate_seed(crew, pool)

    assert len(pool.solution_ideas) == 2  # seed only, no pivot
    record = flow.state.user_idea_pivot
    assert record["attempted"] is True
    assert record["outcome"] == "rejected"
    assert "scored no better" in record["reason_not_shown"]
    assert record["trigger_finding"].startswith("shipped")


def test_pivot_accepted_appended_not_swapped():
    rev = _seed_idea()
    rev.solution_name = "Support-History Wedge"
    rev.innovation_angle = "Attacks CompetX's missing support-history access"
    flow = _flow()
    crew = FakeCrew(parity="partial (CompetX): overlapping tracker",
                    pivot_rev=rev, pivot_ok=True)
    pool = _pool()
    flow._inject_validate_seed(crew, pool)

    names = [i.solution_name for i in pool.solution_ideas]
    assert names == ["Roast Batch Planner", "Green Lot Freshness Tracker",
                     "Support-History Wedge"]  # append, never replace
    assert pool.solution_ideas[1].generation_operation_id == "validate"
    assert pool.solution_ideas[2].generation_operation_id == "validate_pivot"
    record = flow.state.user_idea_pivot
    assert record["outcome"] == "accepted"
    assert record["name"] == "Support-History Wedge"
    assert record["ries_label"] in ("customer-segment", "zoom-in")
    assert crew.gaps_seen == {"competx": "no support-history access"}


def test_seed_request_carries_identity_terms_for_preservation():
    """The stated-clause gate lives in the crew — the flow must hand it the terms."""
    flow = _flow()
    terms = {"mechanism": ["drafts replies"], "audience": [], "problem": [],
             "delivery": ["chrome extension"]}
    flow.state.user_idea_identity_terms = terms
    flow.state.user_idea_inferred_fields = ["audience"]
    crew = FakeCrew()
    flow._inject_validate_seed(crew, _pool())

    req = crew.seed_request_seen
    assert req.identity_terms == terms
    assert req.inferred_fields == ["audience"]
    assert req.dispatch_id == "validate"


def test_brief_probe_runs_on_none_parity_and_is_display_only():
    """Q1: none-found seeds get a second probe of the PITCHED mechanism. The finding
    lands on state.user_idea_brief_parity ONLY — the seed's own parity and the pivot
    record must be untouched."""
    flow = _flow()
    flow.state.user_idea_identity_terms = {
        "mechanism": ["tracks", "green coffee lots"], "audience": [], "problem": [],
        "delivery": []}
    crew = FakeCrew(brief_probe_result=("substitute (ReplyGuy): drafts AI replies", 2))
    pool = _pool()
    flow._inject_validate_seed(crew, pool)

    assert crew.brief_probe_seen == ("Green Lot Freshness Tracker",
                                     ["tracks", "green coffee lots"])
    assert flow.state.user_idea_brief_parity == "substitute (ReplyGuy): drafts AI replies"
    seed = pool.solution_ideas[-1]
    assert seed.incumbent_parity == "none found"  # never overwritten
    assert flow.state.user_idea_pivot["outcome"] == "not_attempted"  # never triggers pivot


def test_brief_probe_not_run_when_seed_parity_hit():
    flow = _flow()
    flow.state.user_idea_identity_terms = {"mechanism": ["tracks"], "audience": [],
                                           "problem": [], "delivery": []}
    crew = FakeCrew(parity="shipped (Cropster): lot tracking shipped since 2021",
                    brief_probe_result=("shipped by X: y", 2))
    flow._inject_validate_seed(crew, _pool())

    assert crew.brief_probe_seen is None
    assert flow.state.user_idea_brief_parity is None


def test_brief_probe_failure_leaves_state_unchanged():
    flow = _flow()
    flow.state.user_idea_identity_terms = {"mechanism": ["tracks"], "audience": [],
                                           "problem": [], "delivery": []}
    crew = FakeCrew(brief_probe_result=(None, 1))
    pool = _pool()
    flow._inject_validate_seed(crew, pool)

    assert flow.state.user_idea_brief_parity is None
    assert pool.solution_ideas[-1].generation_operation_id == "validate"  # injection intact


def test_seed_none_degrades_without_touching_pool():
    flow, crew, pool = _flow(), FakeCrew(seed_result=None), _pool()
    flow._inject_validate_seed(crew, pool)

    assert len(pool.solution_ideas) == 1
    assert any("could not evaluate your idea" in d
               for d in flow.state.pipeline_degradations)
    _assert_scratch_restored(crew)


def test_a_refusal_merges_nothing_into_the_run_level_ruled_out_ledger():
    """The load-bearing ORDERING inside `_inject_validate_seed`, pinned.

    `state.idea_ruled_out` is merged at the very bottom of the method, after every refusal
    path has returned — and nothing enforces that but the line order. Three surfaces render
    that ledger as statements about THE USER'S IDEA (SelectionWorkbench's ruled-out rail,
    the analyst chat's ruled-out block, the `/new` prefill), so a merge that moved above the
    refusals would tell the user which of their idea's pains was ruled out on a run that
    never graded their idea — the same claim sixteen surfaces of this program have been
    spent removing, arriving through a data path instead of a copy string.

    Non-vacuous by construction: `FakeCrew.execute_seed_pipeline` sets `ruled_out_pains` to
    a seed finding BEFORE returning None, exactly as the real reset does, and the accepted
    path above proves that finding does reach the ledger when the seed survives.
    """
    # (1) the crew produced nothing to grade.
    flow, crew, pool = _flow(), FakeCrew(seed_result=None), _pool()
    flow._inject_validate_seed(crew, pool)
    assert flow.state.idea_ruled_out == []
    # The snapshot/restore half: the seed's findings never reach the POOL harvest either.
    assert crew.ruled_out_pains == POOL_SCRATCH["ruled_out_pains"]

    # (2) the post-birth identity refusal — a separate `return`, same requirement. The lock
    # records a value the returned candidate does not carry, so the drift check refuses.
    flow2, crew2, pool2 = _flow(), FakeCrew(), _pool()
    crew2._seed_identity_lock = {"solution_name": "a completely different product"}
    flow2._inject_validate_seed(crew2, pool2)
    assert len(pool2.solution_ideas) == 1, "drifted seed must not reach the pool"
    assert flow2.state.idea_ruled_out == []


def test_the_degradation_line_is_human_copy_not_the_internal_cause():
    """`pipeline_degradations` is appended VERBATIM to the report's quality caveats
    (report_generator `_generate_data_quality_summary`), so it is user-facing copy. It used to
    interpolate the raw typed cause — a paying user read "seed pipeline refused:
    judged_a_different_product". The machine-readable cause still travels, on
    `state.user_idea_failure_reason` and in the identity trace."""
    from nicheiq.report.idea_validation_block import SEED_FAILURE_COPY

    for reason, (headline, _next_step) in SEED_FAILURE_COPY.items():
        flow, crew, pool = _flow(), FakeCrew(seed_result=None, failure_reason=reason), _pool()
        flow._inject_validate_seed(crew, pool)

        assert flow.state.user_idea_failure_reason == reason  # the machine half survives
        line = flow.state.pipeline_degradations[-1]
        assert reason not in line and "_" not in line, line
        assert "refused" not in line, line
        # Same sentence the idea-check block's top line renders, so the two cannot drift.
        assert line == f"Idea check: {headline[0].lower()}{headline[1:]}"


def test_systemic_breaker_propagates_after_restore():
    flow, crew, pool = _flow(), FakeCrew(raise_systemic=True), _pool()
    with pytest.raises(LLMSystemicError):
        flow._inject_validate_seed(crew, pool)
    _assert_scratch_restored(crew)
    assert len(pool.solution_ideas) == 1


def test_finalize_idea_pool_keep_guard_preserves_validate_markers():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)

    def idea(**kw):
        base = dict(solution_name="X", description="d", value_proposition="v",
                    candidate_status="fabricated", project_type="saas",
                    data_access_model=None, technical_approach="",
                    source_frame="pain", generation_operation_id=None,
                    generation_batch_ordinal=None, rebuild_origin=None)
        base.update(kw)
        return BaseSolutionIdea.model_construct(**base)

    seed = idea(solution_name="UserIdea", source_frame="user_seed",
                generation_operation_id="validate")
    pivot = idea(solution_name="UserPivot", source_frame="user_seed",
                 generation_operation_id="validate_pivot")
    normal = idea(solution_name="PoolIdea", generation_operation_id="batch-uuid-123")
    chat_seed = idea(solution_name="ChatSeed", source_frame="user_seed",
                     generation_operation_id="some-dispatch-uuid")

    crew._finalize_idea_pool([seed, pivot, normal, chat_seed])

    assert seed.generation_operation_id == "validate"           # kept
    assert pivot.generation_operation_id == "validate_pivot"    # kept
    assert normal.generation_operation_id is None               # still reset
    assert chat_seed.generation_operation_id is None            # user_seed alone isn't enough
    assert seed.source_frame == "user_seed"                     # registry keeps the frame
    for i in (seed, pivot, normal, chat_seed):
        assert i.candidate_status == "active"                   # fabrication reset intact

    # The review-conflict oracle (plan P5 verify): after a later operation re-runs the
    # pool contract over the merged pool — the exact path reviews 3 and 4 disagreed
    # about — the idea_validation block must still find the marked seed.
    from nicheiq.report.idea_validation_block import build_idea_validation_block
    state = SimpleNamespace(
        user_idea_text="pitch", user_idea_brief="brief", user_idea_inferred_fields=[],
        user_idea_pivot=None,
        idea_generation=SimpleNamespace(solution_ideas=[seed, pivot, normal, chat_seed]),
        pain_point_analysis=SimpleNamespace(pain_points=[]),
        social_content=SimpleNamespace(reddit_posts=[], generic_posts=[]),
        niche_context=SimpleNamespace(niche_description="m", user_target_audience=None,
                                      resolved_primary_audience=None),
        niche_incumbent_map=[], idea_ruled_out=[],
    )
    block = build_idea_validation_block(state, "validate_idea")
    assert block is not None and block["idea_name"] == "UserIdea"
    assert block["pivot"]["idea_id"] == getattr(pivot, "idea_id", None)


# ── pivot rejection codes (Maya pass F3) ──

def _scored_rev(name="Pivoted Tracker", mf=0.4, tf=0.4, nov=0.4, seo=0.4,
                parity="none found"):
    rev = _seed_idea(parity)
    rev.solution_name = name
    rev.value_proposition = "Pivoted value proposition for the same roasters."
    rev.market_fit_score = mf
    rev.technical_feasibility_score = tf
    rev.novelty_score = nov
    rev.seo_scalability_score = seo
    rev.winning_angle = None
    return rev


def _crew_with_scored_seed(crew, scores=0.8):
    """Give the injected seed a full score vector so the not-better comparison is real."""
    orig_execute = crew.execute_seed_pipeline

    def _scored(req):
        seed = orig_execute(req)
        seed.market_fit_score = scores
        seed.technical_feasibility_score = scores
        seed.novelty_score = scores
        seed.seo_scalability_score = scores
        seed.winning_angle = None
        return seed

    crew.execute_seed_pipeline = _scored
    return crew


def test_pivot_rejection_not_better_records_the_decision_numbers():
    flow = _flow()
    crew = _crew_with_scored_seed(FakeCrew(
        parity="shipped by Cropster: lot tracking shipped since 2021",
        pivot_rev=_scored_rev(mf=0.4, tf=0.4, nov=0.4, seo=0.4), pivot_ok=False))
    flow._inject_validate_seed(crew, _pool())

    record = flow.state.user_idea_pivot
    assert record["rejection_code"] == "not_better"
    assert record["reason_not_shown"] == (
        "It scored no better than your original, so we're not proposing it.")
    assert record["rejected_name"] == "Pivoted Tracker"
    assert record["rejected_pitch"].startswith("Pivoted value proposition")
    assert isinstance(record["rejected_composite"], int)
    assert isinstance(record["original_composite"], int)
    assert record["rejected_composite"] < record["original_composite"]


def test_pivot_rejection_parity_not_cleared_never_claims_scored_no_better():
    flow = _flow()
    crew = FakeCrew(
        parity="shipped by Cropster: lot tracking shipped since 2021",
        pivot_rev=_scored_rev(mf=0.9, tf=0.9, nov=0.9, seo=0.9,
                              parity="partial by Cropster: still overlaps"),
        pivot_ok=False)
    flow._inject_validate_seed(crew, _pool())

    record = flow.state.user_idea_pivot
    assert record["rejection_code"] == "parity_not_cleared"
    assert "scored no better" not in record["reason_not_shown"]
    assert record["reason_not_shown"] == (
        "It scored better, but a named product already ships the revised mechanism "
        "too, so we're not proposing it.")
    # scored branch still records the decision's own numbers (component won't render
    # them for this code, but the record is honest)
    assert record["rejected_composite"] > record["original_composite"]


def test_pivot_rejection_incomplete_scores_keeps_copy_and_no_fields():
    rev = _seed_idea()
    rev.solution_name = "Unscored Pivot"   # no score dims at all
    flow = _flow()
    crew = FakeCrew(parity="shipped by Cropster: lot tracking", pivot_rev=rev,
                    pivot_ok=False)
    flow._inject_validate_seed(crew, _pool())

    record = flow.state.user_idea_pivot
    assert record["rejection_code"] == "incomplete_scores"
    assert "scored no better" in record["reason_not_shown"]
    assert "rejected_name" not in record
    assert "rejected_composite" not in record


def test_pivot_no_design_code_and_accepted_record_carries_no_code():
    flow = _flow()
    crew = FakeCrew(parity="shipped by Cropster: lot tracking", pivot_rev=None)
    flow._inject_validate_seed(crew, _pool())
    record = flow.state.user_idea_pivot
    assert record["rejection_code"] == "no_design"
    assert "usable design" in record["reason_not_shown"]
    assert "rejected_name" not in record

    flow2 = _flow()
    rev = _seed_idea()
    rev.solution_name = "Accepted Wedge"
    crew2 = FakeCrew(parity="partial by CompetX: overlapping tracker",
                     pivot_rev=rev, pivot_ok=True)
    flow2._inject_validate_seed(crew2, _pool())
    record2 = flow2.state.user_idea_pivot
    assert record2["outcome"] == "accepted"
    assert "rejection_code" not in record2


def test_trigger_incumbent_parsed_from_paren_format_stamp():
    """The old token loop returned the CLASS word for paren stamps — trigger_incumbent
    then named no product ('shipped')."""
    flow = _flow()
    crew = FakeCrew(parity="shipped (Cropster): lot tracking shipped since 2021",
                    pivot_rev=None)
    flow._inject_validate_seed(crew, _pool())
    assert flow.state.user_idea_pivot["trigger_incumbent"] == "Cropster"


# ──────────────────────────────────────────────────────────────────────────────────────
# Round 8 — every refusal path is typed, and none of them writes its own copy.
# ──────────────────────────────────────────────────────────────────────────────────────

def _post_birth_drift_refusal():
    """The `changed` branch: the crew returned a candidate the birth lock does not match."""
    flow, crew, pool = _flow(), FakeCrew(), _pool()
    crew._seed_identity_lock = {"solution_name": "a completely different product"}
    flow._inject_validate_seed(crew, pool)
    return flow, pool


def _post_birth_check_failed_refusal(monkeypatch):
    """The `except` branch: our own identity check could not run at all."""
    import nicheiq.utils.seed_fidelity as sf

    def boom(*_a, **_k):
        raise RuntimeError("identity check exploded")

    monkeypatch.setattr(sf, "changed_seed_identity_fields", boom)
    flow, crew, pool = _flow(), FakeCrew(), _pool()
    crew._seed_identity_lock = {"solution_name": "anything at all"}
    flow._inject_validate_seed(crew, pool)
    return flow, pool


def test_every_refusal_path_stamps_a_typed_cause_with_single_source_copy(monkeypatch):
    """THE TYPED-CAUSE DISCIPLINE COVERED ONE OF THREE REFUSAL PATHS.

    All six causes are assigned inside `execute_seed_pipeline`, and the birth refusal
    carried the crew's value to state. The two POST-BIRTH refusals set only
    `pipeline_degradations` and returned, so `user_idea_failure_reason` fell through to
    `"unknown"` -> the GENERIC copy pair on the report page — while a FOURTH independently
    authored refusal sentence ("Idea check: the evaluated candidate drifted from your
    submitted product and was withheld") rendered in `quality_caveats` on that same page,
    describing "the EVALUATED candidate" under a heading stamped "Not evaluated".

    The property, not the list: for EVERY way this method can refuse, the typed cause must
    be one the copy map knows, and the user-facing caveat must be DERIVED from that map's
    headline rather than written at the call site.
    """
    from nicheiq.report.idea_validation_block import SEED_FAILURE_COPY, seed_failure_headline

    refusals = {
        "birth": (lambda: (_flow_refused_at_birth())),
        "post_birth_drift": (lambda: _post_birth_drift_refusal()),
        "post_birth_check_failed": (lambda: _post_birth_check_failed_refusal(monkeypatch)),
    }
    for label, run in refusals.items():
        flow, pool = run()
        assert len(pool.solution_ideas) == 1, f"{label}: refused seed reached the pool"

        reason = flow.state.user_idea_failure_reason
        assert reason in SEED_FAILURE_COPY, (
            f"{label}: refusal cause {reason!r} is not a typed cause, so the report renders "
            "the generic pair for a defect we can name")

        headline = seed_failure_headline(reason)
        assert flow.state.pipeline_degradations[-1] == (
            f"Idea check: {headline[0].lower()}{headline[1:]}"), (
            f"{label}: the caveat is authored here instead of derived from SEED_FAILURE_COPY")


def _flow_refused_at_birth():
    flow, crew, pool = _flow(), FakeCrew(seed_result=None,
                                        failure_reason="judged_a_different_product"), _pool()
    flow._inject_validate_seed(crew, pool)
    return flow, pool


def test_the_two_hand_written_post_birth_refusal_sentences_are_gone(monkeypatch):
    """Named literally, because they are what a user actually read. Both were the FOURTH and
    FIFTH refusal sentences in a program whose single source is `SEED_FAILURE_COPY`."""
    dead = (
        "the evaluated candidate drifted from your submitted product and was withheld",
        "the submitted-product identity check failed, so the candidate was withheld",
    )
    for run in (lambda: _post_birth_drift_refusal(),
                lambda: _post_birth_check_failed_refusal(monkeypatch)):
        flow, _pool_ = run()
        joined = " ".join(flow.state.pipeline_degradations)
        for sentence in dead:
            assert sentence not in joined, joined
        # And it never says "evaluated" about a run that evaluated nothing.
        assert "evaluated candidate" not in joined


# ─────────────────────────────────────────────────────────────────────────────
# S15 — THE COMMERCIAL CONTRACT OF A REFUSAL. PINNED, NOT ENDORSED.
# ─────────────────────────────────────────────────────────────────────────────


def test_every_refusal_path_returns_normally_so_no_failure_signal_ever_reaches_billing(
        monkeypatch):
    """THE MECHANISM BY WHICH A REFUSED RUN KEEPS THE USER'S MONEY.

    A `validate_idea` job is charged the FULL `discovery` stage at creation
    (`creditService.ts:906`: `entryStage = chatMode ? 'guided_s1' : 'discovery'`, and
    `types/job.ts` rejects `chatMode` on an idea check, so it is always the plain
    discovery price). Every refund path in the backend is keyed on a FAILURE or a
    DISPATCH settlement — `refundChargeInTx` is called from `jobService`,
    `dispatchService`, `paidPoolRecoveryService` and `workers.ts`, and not one of those
    call sites can see an idea-check outcome. `not_evaluated` appears nowhere in any of
    them; it exists in the backend only in copy and prompt surfaces.

    So the ONLY thing that could return the money is a refusal that presents itself as a
    failure. This test pins that none of them does: all three `_refuse_seed` call sites
    (`research_flow.py:5478`, `:5525`, `:5544`) `return` after it, `_refuse_seed` itself
    (`:5596`) sets two state fields and returns `None`, and so `_inject_validate_seed`
    returns normally. The run then completes Phase 1 and terminates through the ordinary
    success endpoint `POST /api/workers/ideas-ready`, which contains no reference to a
    charge or a refund at all.

    THIS IS DELIBERATE AND IT IS NOT THE BUG. The refusal is non-fatal on purpose — the
    alternatives pool ships and has value, and raising here would destroy a paid Phase 1
    to report a defect that is ours (that is S3/S4, already fixed once in this program).
    What was never a decision is the COMMERCIAL half: nothing anywhere asserted what
    happens to the charge, so the current outcome — user pays in full, run grades nothing
    — arrived by accident and could change in either direction silently.

    The contrast that proves this is a choice and not a mechanism: the adjacent
    in-selection seed op refuses by RAISING (`worker/tasks.py::run_seed_idea` — "Only a
    TOTAL birth failure is a pipeline failure"), lands on `POST /api/workers/seed-failed`
    (`workers.ts:2479`) and DOES refund its `seed_idea_N` charge.

    If you are changing this, see ledger item S15 in `docs/SEED_IDENTITY_REMEDIATION.md`:
    full refund / no refund with disclosure / partial, with what each costs and what each
    requires in code. Decide it; do not let it drift.
    """
    refusals = {
        "birth": lambda: (_flow_refused_at_birth()),
        "post_birth_drift": lambda: (_post_birth_drift_refusal()),
        "post_birth_check_failed": lambda: (_post_birth_check_failed_refusal(monkeypatch)),
    }
    for label, run in refusals.items():
        # (1) It does not raise. A raise is the only signal that could reach a refund.
        flow, pool = run()

        # (2) It refused: a typed cause is stamped and nothing was graded into the pool.
        assert flow.state.user_idea_failure_reason, f"{label}: no typed cause stamped"
        assert len(pool.solution_ideas) == 1, f"{label}: refused seed reached the pool"

        # (3) And the flow carries NO field that any billing consumer could key on — no
        #     refund request, no charge annotation, no "this run should not have been paid
        #     for" marker of any spelling. Derived from the state's own field names rather
        #     than a hand-written list of two, so a field added later is covered.
        money_fields = [
            name for name in type(flow.state).model_fields
            if any(token in name.lower() for token in
                   ("refund", "credit", "charge", "billing", "price", "cost"))
            and getattr(flow.state, name, None)
        ]
        assert money_fields == [], (
            f"{label}: the refusal now sets {money_fields} — if this is a deliberate "
            "billing signal, S15 has been decided and the ledger must say so")


def test_the_refusal_next_step_copy_still_tells_the_user_to_re_run(monkeypatch):
    """Every typed cause ends by telling the user to run the check again — and a re-run is a
    NEW job, so it is charged the full discovery stage a second time at creation. That is
    the disclosure obligation S15 turns on, and it is why the price/balance line on the
    refusal card (`ValidationVerdict.svelte`) is load-bearing rather than decorative.

    Pinned so the copy and the commercial fact cannot drift apart: if a future cause stops
    inviting a re-run, the disclosure requirement changes with it.
    """
    from nicheiq.report.idea_validation_block import SEED_FAILURE_COPY

    assert SEED_FAILURE_COPY, "no typed causes at all — the scan or the import moved"
    for reason, (_headline, next_step) in SEED_FAILURE_COPY.items():
        assert "run the check again" in next_step.lower() or "run it again" in next_step.lower(), (
            f"{reason}: next_step no longer invites a re-run ({next_step!r}) — a re-run is a "
            "second full charge, so S15's disclosure requirement changes with this copy")


# ── Pivot text is stored verbatim (no producer-side character slice) ──────────
#
# `rejected_pitch` and `changes` were each cut with a different guessed magnitude
# ([:160] and [:200]) off the SAME source field. The report then shipped mid-word
# stumps ("…so practices stuck on Eaglesoft or D") that users read as corrupted
# data. Both slices are gone; the length limit lives in ValidationVerdict.svelte's
# line-clamp. These tests pin the PROPERTY (stored == producer's value, verbatim)
# rather than any number — an assertion on 160/200/any N would reintroduce the
# defect as a test.

# Longer than either deleted slice, and shaped so a [:160] or [:200] cut lands
# mid-word (a length assertion would pass while the text is still mangled).
_LONG_PITCH = (
    "A standalone, PMS-agnostic denial-recovery queue that converts insurer EOBs "
    "into evidence-specific resubmission checklists, so practices stuck on legacy "
    "practice-management software can rework a denial in one pass instead of "
    "rebuilding the whole claim from scratch inside the incumbent's own screens."
)


def _mid_word_cut(stored: str, source: str) -> bool:
    """True when `stored` is a prefix of `source` that stops inside a word."""
    return (
        stored != source
        and source.startswith(stored)
        and bool(stored)
        and not stored[-1].isspace()
        and not source[len(stored)].isspace()
    )


def test_rejected_pitch_is_stored_verbatim_not_character_sliced():
    rev = _scored_rev(mf=0.4, tf=0.4, nov=0.4, seo=0.4)
    rev.value_proposition = _LONG_PITCH
    flow = _flow()
    crew = _crew_with_scored_seed(FakeCrew(
        parity="shipped by Cropster: lot tracking shipped since 2021",
        pivot_rev=rev, pivot_ok=False))
    flow._inject_validate_seed(crew, _pool())

    stored = flow.state.user_idea_pivot["rejected_pitch"]
    assert stored == rev.value_proposition, (
        "rejected_pitch is no longer the producer's value verbatim — a character "
        "slice has been re-added; presentation limits belong in the renderer's "
        "line-clamp (.iv-pivot-rejected), not here")
    assert not _mid_word_cut(stored, rev.value_proposition), (
        f"rejected_pitch stops mid-word: ...{stored[-30:]!r}")


def test_accepted_changes_is_stored_verbatim_not_character_sliced():
    rev = _seed_idea()
    rev.solution_name = "Support-History Wedge"
    rev.innovation_angle = _LONG_PITCH
    flow = _flow()
    crew = FakeCrew(parity="partial (CompetX): overlapping tracker",
                    pivot_rev=rev, pivot_ok=True)
    flow._inject_validate_seed(crew, _pool())

    stored = flow.state.user_idea_pivot["changes"]
    assert stored == rev.innovation_angle, (
        "pivot `changes` is no longer verbatim — a character slice has been "
        "re-added; the clamp lives on .iv-echo-row dd.iv-clamp-3 instead")
    assert not _mid_word_cut(stored, rev.innovation_angle)


def test_changes_falls_back_to_value_proposition_verbatim():
    """The fallback arm reads the same field `rejected_pitch` does — it must not
    reacquire a slice either (that is how the two magnitudes diverged)."""
    rev = _seed_idea()
    rev.solution_name = "Support-History Wedge"
    rev.innovation_angle = None
    rev.value_proposition = _LONG_PITCH
    flow = _flow()
    crew = FakeCrew(parity="partial (CompetX): overlapping tracker",
                    pivot_rev=rev, pivot_ok=True)
    flow._inject_validate_seed(crew, _pool())

    assert flow.state.user_idea_pivot["changes"] == _LONG_PITCH


def test_ries_label_truthiness_survives_the_unsliced_changes_value():
    """`ries_label` is decided by `elif record["changes"]:` — a TRUTHINESS test.
    Dropping the slice must not move it in either direction:
      * a long value proposition is truthy sliced or whole → "zoom-in" still set;
      * an empty one still maps to None via the trailing `or None` → no label.
    """
    # (a) long, no persona change → zoom-in, exactly as before the slice went.
    rev = _seed_idea()
    rev.solution_name = "Support-History Wedge"
    rev.innovation_angle = None
    rev.value_proposition = _LONG_PITCH
    flow = _flow()
    flow._inject_validate_seed(
        FakeCrew(parity="partial (CompetX): overlapping tracker",
                 pivot_rev=rev, pivot_ok=True), _pool())
    record = flow.state.user_idea_pivot
    assert record["changes"]  # truthy
    assert record["ries_label"] == "zoom-in"

    # (b) both source fields empty → changes is None, so no label is claimed.
    rev2 = _seed_idea()
    rev2.solution_name = "Blank Wedge"
    rev2.innovation_angle = None
    rev2.value_proposition = ""
    flow2 = _flow()
    flow2._inject_validate_seed(
        FakeCrew(parity="partial (CompetX): overlapping tracker",
                 pivot_rev=rev2, pivot_ok=True), _pool())
    record2 = flow2.state.user_idea_pivot
    assert record2["changes"] is None
    assert record2["ries_label"] is None

    # (c) persona change still wins over the zoom-in fallback.
    rev3 = _seed_idea()
    rev3.solution_name = "Segment Wedge"
    rev3.innovation_angle = _LONG_PITCH
    rev3.target_personas = ["enterprise green buyers"]
    flow3 = _flow()
    flow3._inject_validate_seed(
        FakeCrew(parity="partial (CompetX): overlapping tracker",
                 pivot_rev=rev3, pivot_ok=True), _pool())
    assert flow3.state.user_idea_pivot["ries_label"] == "customer-segment"


def test_keeps_still_selects_two_personas_and_one_pain():
    """The neighbouring LIST slices (`[:2]` personas, `[:1]` pain) are selection,
    not character truncation — they stay. Pinned so the char-slice removal above
    is not later "completed" by deleting these too."""
    rev = _seed_idea()
    rev.solution_name = "Support-History Wedge"
    seed_personas = ["roaster A", "roaster B", "roaster C"]
    flow = _flow()
    crew = FakeCrew(parity="partial (CompetX): overlapping tracker",
                    pivot_rev=rev, pivot_ok=True)
    orig_execute = crew.execute_seed_pipeline

    def _wide(req):
        seed = orig_execute(req)
        seed.target_personas = list(seed_personas)
        seed.pain_points_addressed = ["stale green inventory", "second pain", "third"]
        return seed

    crew.execute_seed_pipeline = _wide
    flow._inject_validate_seed(crew, _pool())

    keeps = flow.state.user_idea_pivot["keeps"]
    assert keeps == "roaster A; roaster B; stale green inventory"
    assert "roaster C" not in keeps and "second pain" not in keeps
