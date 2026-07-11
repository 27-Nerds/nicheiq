"""Regression tests for the crew-level cost-tracking wiring bug.

Root cause: UnifiedSolutionCrew and PainPointCrew never accepted/stored a
cost_tracker, so their internal `hasattr(self, "cost_tracker")` recording
guards silently no-op'd in production and only flow-level LLM calls were
ever counted (admin panel showed ~$0.05 for runs that cost dollars).
"""

import re
from pathlib import Path
from unittest.mock import patch

from nicheiq.crews.pain_point_crew import PainPointCrew
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.pain_point import (
    BatchStanceResponse,
    ExtractedQuote,
    PainPoint,
    PainPointAnalysisResult,
    StanceVerdict,
    UnvalidatedPainPoint,
)
from nicheiq.utils.llm_service import TokenUsage
from nicheiq.utils.token_monitor import CostTracker


# ── UnifiedSolutionCrew ──────────────────────────────────────────────────────

def test_usc_constructor_stores_cost_tracker():
    pp = PainPoint(
        title="Sourcing", description="hard", severity_score=0.8,
        commercial_intent=0.5, mention_count=5, representative_quotes=["q"],
        opportunity_level="medium",
    )
    ppa = PainPointAnalysisResult(
        niche="x", pain_points=[pp], total_mentions=5, analysis_summary="s",
        top_categories=["c"],
    )
    tracker = CostTracker()
    crew = UnifiedSolutionCrew(pain_point_analysis=ppa, cost_tracker=tracker)
    assert crew.cost_tracker is tracker


def test_usc_constructor_defaults_cost_tracker_to_none():
    pp = PainPoint(
        title="Sourcing", description="hard", severity_score=0.8,
        commercial_intent=0.5, mention_count=5, representative_quotes=["q"],
        opportunity_level="medium",
    )
    ppa = PainPointAnalysisResult(
        niche="x", pain_points=[pp], total_mentions=5, analysis_summary="s",
        top_categories=["c"],
    )
    crew = UnifiedSolutionCrew(pain_point_analysis=ppa)
    assert crew.cost_tracker is None


def test_usc_recording_site_appends_to_shared_tracker():
    """A representative direct-LLM recording site (_record_divergent_usage,
    used by the tournament/divergent-sampling paths) must actually write into
    the tracker passed at construction, proving the hasattr guard is now
    truthy in production instead of silently no-op'ing."""
    pp = PainPoint(
        title="Sourcing", description="hard", severity_score=0.8,
        commercial_intent=0.5, mention_count=5, representative_quotes=["q"],
        opportunity_level="medium",
    )
    ppa = PainPointAnalysisResult(
        niche="x", pain_points=[pp], total_mentions=5, analysis_summary="s",
        top_categories=["c"],
    )
    tracker = CostTracker()
    crew = UnifiedSolutionCrew(pain_point_analysis=ppa, cost_tracker=tracker)

    crew._record_divergent_usage([TokenUsage(100, 50, "gpt-4o")])

    assert len(tracker.stage_usages) == 1
    assert tracker.stage_usages[0].stage == "Stage 7 - Divergent Sampling"


# ── PainPointCrew ────────────────────────────────────────────────────────────

def _bare_pain_crew(cost_tracker=None):
    crew = object.__new__(PainPointCrew)
    if cost_tracker is not None:
        crew.cost_tracker = cost_tracker
    return crew


def _pain():
    return UnvalidatedPainPoint(
        title="PT-141 causes debilitating nausea",
        description="Users report nausea severe enough to stop using PT-141",
        mention_count=3,
        anchor_keywords=["pt-141", "nausea"],
    )


def _quotes():
    return [
        ExtractedQuote(quote_text="This drug is very effective with no side effects", post_id="a"),
        ExtractedQuote(quote_text="Severe nausea made me stop using it completely", post_id="b"),
    ]


def test_pain_point_crew_constructor_stores_cost_tracker():
    tracker = CostTracker()
    crew = PainPointCrew(niche_description="niche", cost_tracker=tracker)
    assert crew.cost_tracker is tracker


def test_pain_point_crew_constructor_defaults_cost_tracker_to_none():
    crew = PainPointCrew(niche_description="niche")
    assert crew.cost_tracker is None


def test_stance_gate_records_usage_with_stage_prefix():
    verdicts = BatchStanceResponse(verdicts=[
        StanceVerdict(index=1, stance="CONTRADICTS", reason="positive"),
        StanceVerdict(index=2, stance="SUPPORTS", reason="reports nausea"),
    ])
    usage = TokenUsage(80, 20, "gpt-4o-mini")
    tracker = CostTracker()
    crew = _bare_pain_crew(cost_tracker=tracker)

    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(verdicts, usage),
    ):
        crew._stance_filter_quotes(_pain(), _quotes())

    assert len(tracker.stage_usages) == 1
    assert tracker.stage_usages[0].stage.startswith("Stage 6 -")


def test_audience_coverage_critic_records_usage_with_stage_label():
    """assess_audience_coverage() discards usage internally; PainPointCrew._run_audience_coverage_critic
    is the wrapper that threads usage_sink through and records it against the shared tracker (the
    fix for the 3rd cost-tracking gap: the critic's LLM call was previously silently unrecorded).

    Patches LLMService.invoke_structured (what assess_audience_coverage's default `invoke` calls
    through to) rather than the module-level `_default_invoke` — the latter is bound into
    assess_audience_coverage's signature at import time, so patching the module attribute
    afterwards would not affect the already-bound default."""
    from nicheiq.utils.audience_coverage import AudienceCoverageVerdict
    from nicheiq.utils.llm_service import TokenUsage

    tracker = CostTracker()
    crew = _bare_pain_crew(cost_tracker=tracker)

    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(AudienceCoverageVerdict(rebalance_needed=False), TokenUsage(60, 15, "gpt-4o-mini")),
    ):
        verdict = crew._run_audience_coverage_critic(
            ["a pain"], "fans", ["Seg"], {"composition": [("r/x", 5, ["t"])], "pain_sources": {}}
        )

    assert verdict.rebalance_needed is False
    assert len(tracker.stage_usages) == 1
    assert tracker.stage_usages[0].stage == "Stage 6 - Audience Coverage Critic"
    assert tracker.stage_usages[0].prompt_tokens == 60


def test_audience_coverage_critic_records_both_calls_on_retry():
    """The empty-directive guard retries once internally; both invokes' usage must be recorded."""
    from nicheiq.utils.audience_coverage import AudienceCoverageVerdict
    from nicheiq.utils.llm_service import TokenUsage

    tracker = CostTracker()
    crew = _bare_pain_crew(cost_tracker=tracker)

    responses = [
        (AudienceCoverageVerdict(
            rebalance_needed=True, under_covered_audiences=[], rebalance_directive=""
        ), TokenUsage(50, 10, "gpt-4o-mini")),
        (AudienceCoverageVerdict(
            rebalance_needed=True, under_covered_audiences=["Spectators"],
            rebalance_directive="surface spectator pains",
        ), TokenUsage(70, 20, "gpt-4o-mini")),
    ]

    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        side_effect=responses,
    ):
        crew._run_audience_coverage_critic(
            ["a pain"], "fans", ["Spectators"], {"composition": [("r/x", 5, ["t"])], "pain_sources": {}}
        )

    assert len(tracker.stage_usages) == 2
    assert all(u.stage == "Stage 6 - Audience Coverage Critic" for u in tracker.stage_usages)


def test_audience_coverage_critic_no_tracker_does_not_crash():
    from nicheiq.utils.audience_coverage import AudienceCoverageVerdict
    from nicheiq.utils.llm_service import TokenUsage

    crew = _bare_pain_crew()  # cost_tracker attribute never set

    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(AudienceCoverageVerdict(rebalance_needed=False), TokenUsage(10, 5, "gpt-4o-mini")),
    ):
        verdict = crew._run_audience_coverage_critic(
            ["a pain"], "fans", ["Seg"], {"composition": [("r/x", 5, ["t"])], "pain_sources": {}}
        )
    assert verdict.rebalance_needed is False


def test_stance_gate_no_tracker_does_not_crash():
    """Legacy / standalone construction (cost_tracker never set or None) must
    not raise — the recording guard is defensive via getattr."""
    verdicts = BatchStanceResponse(verdicts=[
        StanceVerdict(index=1, stance="SUPPORTS", reason="reports nausea"),
        StanceVerdict(index=2, stance="SUPPORTS", reason="reports nausea"),
    ])
    crew = _bare_pain_crew()  # cost_tracker attribute never set
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        return_value=(verdicts, TokenUsage(80, 20, "gpt-4o-mini")),
    ):
        kept = crew._stance_filter_quotes(_pain(), _quotes())
    assert len(kept) == 2


# ── Regression lock: every UnifiedSolutionCrew(...) site in research_flow.py ──
# must forward the flow's cost_tracker, so the next construction site can't
# silently repeat the original bug.

def test_every_usc_construction_site_in_research_flow_forwards_cost_tracker():
    flow_path = Path(__file__).parents[2] / "src" / "nicheiq" / "flows" / "research_flow.py"
    source = flow_path.read_text()

    # Find each `UnifiedSolutionCrew(` call and grab the balanced-paren argument block.
    sites = []
    for m in re.finditer(r"UnifiedSolutionCrew\(", source):
        start = m.end()
        depth = 1
        i = start
        while depth > 0:
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
            i += 1
        sites.append(source[start:i])

    assert len(sites) >= 2, "expected at least the two known UnifiedSolutionCrew(...) call sites"
    for i, args in enumerate(sites):
        assert "cost_tracker=self.cost_tracker" in args, (
            f"UnifiedSolutionCrew(...) call site #{i} in research_flow.py is missing "
            f"cost_tracker=self.cost_tracker — crew-level LLM usage would silently stop "
            f"reaching the flow's CostTracker again."
        )
