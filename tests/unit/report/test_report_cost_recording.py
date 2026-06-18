"""ReportGenerator records Stage-14 LLM usage into the cost tracker."""

from nicheiq.report.report_generator import ReportGenerator
from nicheiq.utils.token_monitor import CostTracker
from nicheiq.utils.llm_service import TokenUsage


def _bare_generator(cost_tracker):
    # Bypass the heavy __init__ (needs a full ResearchState); we only exercise the
    # cost-recording helper + the cost_tracker wiring.
    gen = ReportGenerator.__new__(ReportGenerator)
    gen.cost_tracker = cost_tracker
    return gen


def test_record_cost_records_into_tracker():
    ct = CostTracker()
    gen = _bare_generator(ct)
    gen._record_cost("Stage 14 - Test", TokenUsage(100, 50, "gpt-4o", cost=None))
    assert len(ct.stage_usages) == 1
    assert ct.stage_usages[0].stage == "Stage 14 - Test"
    assert ct.stage_usages[0].cost_source == "estimated"


def test_record_cost_prefers_actual_cost():
    ct = CostTracker()
    gen = _bare_generator(ct)
    gen._record_cost(
        "Stage 14 - OR",
        TokenUsage(100, 50, "openrouter/google/gemma-2-27b-it", cost=0.004),
    )
    assert ct.stage_usages[0].total_cost == 0.004
    assert ct.stage_usages[0].cost_source == "actual"


def test_record_cost_noop_without_tracker():
    gen = _bare_generator(None)
    # Should not raise when no tracker is configured.
    gen._record_cost("Stage 14 - Test", TokenUsage(1, 1, "gpt-4o"))
