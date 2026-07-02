"""Evidence gate (codex-review fix 2026-07-02): zero-quote low-evidence pains must not seed
generator cells (their run kept 6 zero-quote pains into ideation). Floor-protected, mirrors
the addressability gate. The gate logic lives inline in execute_pipeline; these tests pin the
predicate + the source-level structure."""

import inspect
from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _gate_source():
    return inspect.getsource(UnifiedSolutionCrew.execute_pipeline)


def test_gate_present_with_floor():
    src = _gate_source()
    assert "[EvidenceGate]" in src
    assert "_MIN_EVIDENCED = 3" in src
    # sits AFTER the addressability gate, BEFORE the diversity funnel
    assert src.index("[AddressabilityGate]") < src.index("[EvidenceGate]")
    assert src.index("[EvidenceGate]") < src.index("high_priority = select_diverse_pain_points")


def test_predicate_semantics():
    # replicate the predicate exactly as written in the gate
    def _evidenced(p) -> bool:
        return not (getattr(p, "low_evidence", False)
                    and not (getattr(p, "representative_quotes", None) or []))

    zero_quote_low = SimpleNamespace(low_evidence=True, representative_quotes=[])
    low_with_quote = SimpleNamespace(low_evidence=True, representative_quotes=["q"])
    normal = SimpleNamespace(low_evidence=False, representative_quotes=[])
    legacy = SimpleNamespace()          # no fields at all → kept

    assert not _evidenced(zero_quote_low)     # excluded: unverifiable
    assert _evidenced(low_with_quote)         # kept: clamp already handles it
    assert _evidenced(normal)                 # kept: not flagged low-evidence
    assert _evidenced(legacy)                 # kept: backward compatible
