"""Per-sample critic pipelining (Phase: pipeline the novelty/feasibility critic).

Covers the split of the old monolithic `_score_pool_novelty` into the per-sample scorer
`_score_concepts` (runs in the generator thread) + the post-barrier `_finalize_critic_pool`:
- the two drop-marks are excluded from serialization,
- already_exists takes precedence over no_route when a concept is BOTH (refill order),
- the pipelined path (score per sample → finalize) is equivalent to the pooled wrapper,
- the finalizer is pure code (no LLM call).
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import RawConcept


def _rc(name):
    return RawConcept(
        concept_name=name, one_liner=f"{name} does a thing",
        ideation_technique="niche_drilling", project_type="saas",
        target_keywords=["a", "b"],
    )


def _verdict(name, **kw):
    base = dict(
        name=name, independent_obviousness=0.3, already_exists=False,
        data_feasibility=0.7, build_feasibility=0.6, data_access_model="public",
        bulk_route="official public API", data_notes="ok",
    )
    base.update(kw)
    return usc._NoveltyVerdict(**base)


def _critic_self():
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing tool",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    )
    fake._score_concepts = UnifiedSolutionCrew._score_concepts.__get__(fake)
    fake._finalize_critic_pool = UnifiedSolutionCrew._finalize_critic_pool.__get__(fake)
    return fake


def test_drop_marks_excluded_from_dump():
    rc = _rc("X")
    rc.critic_already_exists = True
    rc.critic_no_route = True
    d = rc.model_dump()
    assert "critic_already_exists" not in d and "critic_no_route" not in d
    assert "critic_already_exists" not in rc.model_dump_json()


def test_already_exists_precedes_no_route_in_refill(monkeypatch):
    """A concept marked BOTH already_exists and no_route is classified as already_exists
    (matches the monolith's short-circuit) → refilled AFTER the pure no_route drop."""
    monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
    fake = SimpleNamespace(_critic_feasibility=None)
    finalize = UnifiedSolutionCrew._finalize_critic_pool.__get__(fake)

    both = _rc("Both"); both.critic_already_exists = True; both.critic_no_route = True
    noroute = _rc("NoRoute"); noroute.critic_no_route = True
    clean = [_rc(f"C{i}") for i in range(4)]
    pool = [both, noroute, *clean]  # 6 total → floor-guard refill is active

    kept = finalize(pool)
    assert len(kept) == 6  # MIN_KEEP floor refills both drops
    # already_exists is refilled after no_route → the both-marked concept lands LAST.
    assert kept.index(both) > kept.index(noroute)


def test_pipelined_equals_pooled(monkeypatch):
    """score-per-sample → finalize is equivalent to the pooled wrapper (kept set + stash)."""
    monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
    verdicts = usc._NoveltyVerdicts(verdicts=[
        _verdict("A", independent_obviousness=0.2),
        _verdict("B", already_exists=True, independent_obviousness=0.9),
    ], drop_names=[])
    monkeypatch.setattr(
        usc.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (verdicts, SimpleNamespace())),
    )

    # Path 1: pooled compat wrapper (score + finalize in one call).
    p1 = _critic_self()
    out1 = UnifiedSolutionCrew._score_pool_novelty(p1, [_rc("A"), _rc("B")])

    # Path 2: per-sample scorer then post-barrier finalizer.
    p2 = _critic_self()
    cs = [_rc("A"), _rc("B")]
    p2._score_concepts(cs)
    out2 = p2._finalize_critic_pool(cs)

    assert {c.concept_name for c in out1} == {c.concept_name for c in out2} == {"A"}  # B already_exists, dropped
    # Both scored concepts contribute to the rebuilt feasibility stash, identically.
    assert p1._critic_feasibility == p2._critic_feasibility
    assert set(p1._critic_feasibility) == {"a", "b"}


def test_finalizer_is_pure_no_llm_call(monkeypatch):
    monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
    called = []
    monkeypatch.setattr(
        usc.LLMService, "invoke_structured",
        staticmethod(lambda **kw: called.append(1) or (None, None)),
    )
    fake = SimpleNamespace(_critic_feasibility=None)
    finalize = UnifiedSolutionCrew._finalize_critic_pool.__get__(fake)
    finalize([_rc("A"), _rc("B")])
    assert called == []  # the finalizer is deterministic code — it must not call the LLM
