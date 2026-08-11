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
                 brief_probe_result=(None, 0)):
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
    assert any("could not be evaluated" in d for d in flow.state.pipeline_degradations)
    _assert_scratch_restored(crew)


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
