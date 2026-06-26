"""Part 4 audience-coverage critic — structure + fail-soft (no live LLM; injected `invoke`).

Behavioural validation (it correctly flags fan/spectator under-coverage on the cached 6a4600ca run,
citing real corpus titles) is in scripts; here we lock in the contract and the safety properties.
"""
from nicheiq.utils.audience_coverage import AudienceCoverageVerdict, assess_audience_coverage


def _mk(**kw):
    def invoke(prompt, model_name, reasoning_effort):
        return AudienceCoverageVerdict(**kw), None
    return invoke


def test_flags_under_covered_audiences():
    invoke = _mk(under_covered_audiences=["Spectators", "Collectors"],
                 rebalance_directive="surface spectator + collector pains from the corpus",
                 rebalance_needed=True, rationale="corpus is fan-heavy; pains are player-heavy")
    v = assess_audience_coverage(["a player pain"], "fans", ["Spectators", "Collectors"],
                                 ["watching the major", "skin prices crashed"], invoke=invoke)
    assert v.rebalance_needed and "Spectators" in v.under_covered_audiences


def test_balanced_returns_no_rebalance():
    invoke = _mk(rebalance_needed=False)
    v = assess_audience_coverage(["p"], "fans", ["Seg"], ["title"], invoke=invoke)
    assert not v.rebalance_needed and v.under_covered_audiences == []


def test_empty_inputs_short_circuit_without_invoke():
    # no pains or no corpus → never calls the model (cost + nothing to judge)
    called = {"n": 0}
    def invoke(*a, **k):
        called["n"] += 1
        return AudienceCoverageVerdict(rebalance_needed=True), None
    assert assess_audience_coverage([], "fans", ["s"], ["t"], invoke=invoke).rebalance_needed is False
    assert assess_audience_coverage(["p"], "fans", ["s"], [], invoke=invoke).rebalance_needed is False
    assert called["n"] == 0


def test_fail_soft_on_invoke_error():
    def invoke(*a, **k):
        raise RuntimeError("model down")
    v = assess_audience_coverage(["p"], "fans", ["s"], ["t"], invoke=invoke)
    assert v.rebalance_needed is False  # never raises; degrades to no-rebalance
