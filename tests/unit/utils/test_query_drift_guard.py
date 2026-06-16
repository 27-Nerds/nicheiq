"""Unit tests for the QueryGenerator anchor drift guard (Phase 2).

Pure-logic tests (no LLM): exercise _apply_anchor_drift_guard directly.
"""

from nicheiq.models.research_state import NicheContext
from nicheiq.utils.generation.query_generator import QueryGenerator


def _ctx(anchors=None, exclusions=None):
    return NicheContext(
        niche_input="x",
        niche_description="performance peptides for athletes",
        market_segments=["serious lifters"],
        industry_boundaries="b",
        anchor_entities=anchors or [],
        disambiguation_exclusions=exclusions or [],
    )


def test_exclusion_term_dropped_word_boundary():
    qg = QueryGenerator()
    ctx = _ctx(
        anchors=["BPC-157", "TB-500", "ipamorelin"],
        exclusions=["semaglutide", "GLP-1"],
    )
    queries = [
        {"query": "BPC-157 dosing schedule", "type": "pain"},
        {"query": "semaglutide weight loss plateau", "type": "pain"},
    ]
    kept, pct, dropped = qg._apply_anchor_drift_guard(queries, ctx)
    kept_text = [q["query"] for q in kept]
    assert "semaglutide weight loss plateau" not in kept_text
    assert "BPC-157 dosing schedule" in kept_text
    assert dropped == 1


def test_anchor_tagging_and_non_discovery_quota():
    qg = QueryGenerator()
    ctx = _ctx(anchors=["BPC-157", "TB-500", "ipamorelin"])
    queries = [
        {"query": "BPC-157 dosing schedule", "type": "pain"},       # anchored
        {"query": "how do you deload", "type": "help"},             # not anchored
        {"query": "biggest challenge recovery", "type": "discovery"},  # exempt
    ]
    kept, pct, dropped = qg._apply_anchor_drift_guard(queries, ctx)
    flags = {q["query"]: q.get("has_anchor") for q in kept}
    assert flags["BPC-157 dosing schedule"] is True
    assert flags["how do you deload"] is False
    # Non-discovery anchor pct = 1 anchored / 2 non-discovery = 0.5
    assert abs(pct - 0.5) < 1e-9
    assert dropped == 0


def test_word_boundary_does_not_false_drop():
    qg = QueryGenerator()
    # 'pro' exclusion must NOT drop 'protein' query.
    ctx = _ctx(anchors=["BPC-157", "TB-500", "ipamorelin"], exclusions=["pro"])
    queries = [{"query": "protein timing for lifters", "type": "pain"}]
    kept, _pct, dropped = qg._apply_anchor_drift_guard(queries, ctx)
    assert dropped == 0
    assert len(kept) == 1


def test_inactive_anchors_is_noop():
    qg = QueryGenerator()
    # Fewer than MIN_ANCHORS_ACTIVE entities => fail-open no-op.
    ctx = _ctx(anchors=["BPC-157"], exclusions=["semaglutide"])
    queries = [{"query": "semaglutide weight loss", "type": "pain"}]
    kept, pct, dropped = qg._apply_anchor_drift_guard(queries, ctx)
    assert dropped == 0
    assert pct == 1.0
    assert len(kept) == 1  # exclusion NOT applied when anchors inactive


def test_no_niche_context_is_noop():
    qg = QueryGenerator()
    queries = [{"query": "anything at all", "type": "pain"}]
    kept, pct, dropped = qg._apply_anchor_drift_guard(queries, None)
    assert (dropped, pct, len(kept)) == (0, 1.0, 1)
