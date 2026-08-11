"""Portfolio guidance in the preview must describe the current visible candidate set."""

from __future__ import annotations

import json
from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.utils.idea_portfolio_summary import idea_portfolio_fingerprint


def _idea(name: str, idea_id: str, *, revision: int = 1, status: str = "active"):
    return SimpleNamespace(
        solution_name=name,
        idea_id=idea_id,
        idea_revision=revision,
        identity_origin="phase1",
        identity_operation_id="initial",
        candidate_status=status,
        source_pain="",
        pain_points_addressed=[],
        market_fit_score=0.6,
        technical_feasibility_score=0.6,
        novelty_score=0.5,
        seo_scalability_score=0.5,
        winning_angle="vertical_workflow",
        idea_tier="single",
        source_frame="pain",
        incumbent_parity="none found",
        data_sources=[],
    )


def _flow(job_id: str, ideas: list) -> ResearchFlow:
    flow = ResearchFlow(niche_description="Independent veterinary clinics", job_id=job_id)
    flow.state.idea_generation = SimpleNamespace(solution_ideas=ideas)
    flow.state.idea_funnel_counts = {"candidates_shown": len(ideas)}
    return flow


def _preview(tmp_path, job_id: str) -> dict:
    return json.loads((tmp_path / f"preview_report_{job_id}.json").read_text())


def test_mutated_pool_recomputes_before_preview_write(tmp_path, monkeypatch):
    old_pool = [_idea("Alpha", "idea-a"), _idea("Beta", "idea-b")]
    flow = _flow("portfolio-refresh", old_pool)
    flow.state.idea_portfolio_summary = "Old guidance recommends Beta."
    flow.state.idea_portfolio_summary_fingerprint = idea_portfolio_fingerprint(old_pool)
    flow.state.idea_generation.solution_ideas.append(_idea("Gamma", "idea-c"))
    calls = []

    def _generate(ideas, **kwargs):
        calls.append((list(ideas), kwargs))
        return "Fresh guidance covers Alpha, Beta, and Gamma.", None

    monkeypatch.setattr(
        "nicheiq.utils.idea_portfolio_summary.generate_idea_portfolio_summary",
        _generate,
    )

    assert flow._materialize_preview_report(str(tmp_path)) is not None
    assert len(calls) == 1
    assert calls[0][1]["funnel_counts"]["candidates_shown"] == 3
    current = idea_portfolio_fingerprint(flow.state.idea_generation.solution_ideas)
    assert flow.state.idea_portfolio_summary_fingerprint == current
    report = _preview(tmp_path, "portfolio-refresh")
    assert report["idea_portfolio_summary"] == "Fresh guidance covers Alpha, Beta, and Gamma."
    assert report["idea_portfolio_summary_fingerprint"] == current


def test_matching_pool_skips_the_paid_summary_call(tmp_path, monkeypatch):
    pool = [_idea("Alpha", "idea-a"), _idea("Beta", "idea-b")]
    flow = _flow("portfolio-match", pool)
    flow.state.idea_portfolio_summary = "Current guidance covers Alpha and Beta."
    flow.state.idea_portfolio_summary_fingerprint = idea_portfolio_fingerprint(pool)

    monkeypatch.setattr(
        "nicheiq.utils.idea_portfolio_summary.generate_idea_portfolio_summary",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected LLM call")),
    )

    assert flow._materialize_preview_report(str(tmp_path)) is not None
    assert _preview(tmp_path, "portfolio-match")["idea_portfolio_summary"] == (
        "Current guidance covers Alpha and Beta."
    )


def test_failed_refresh_keeps_stale_pair_detectably_stale(tmp_path, monkeypatch):
    old_pool = [_idea("Alpha", "idea-a"), _idea("Beta", "idea-b")]
    old_fingerprint = idea_portfolio_fingerprint(old_pool)
    flow = _flow("portfolio-fail-soft", old_pool)
    flow.state.idea_portfolio_summary = "Old guidance recommends Beta."
    flow.state.idea_portfolio_summary_fingerprint = old_fingerprint
    flow.state.idea_generation.solution_ideas.append(_idea("Gamma", "idea-c"))

    monkeypatch.setattr(
        "nicheiq.utils.idea_portfolio_summary.generate_idea_portfolio_summary",
        lambda *args, **kwargs: (None, None),
    )

    assert flow._materialize_preview_report(str(tmp_path)) is not None
    report = _preview(tmp_path, "portfolio-fail-soft")
    assert report["idea_portfolio_summary"] == "Old guidance recommends Beta."
    assert report["idea_portfolio_summary_fingerprint"] == old_fingerprint
    assert report["idea_portfolio_summary_fingerprint"] != idea_portfolio_fingerprint(
        flow.state.idea_generation.solution_ideas
    )
