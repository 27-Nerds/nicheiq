"""Review-3 fixes (2026-07-03): the CLI --stop-after-phase 1 path must produce the preview
report (it was dead code — worker-only), and the preview must carry build_feasibility_score."""

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaTags


def test_stop_branch_materializes_and_returns_path():
    src = inspect.getsource(ResearchFlow._execute_remaining_stages)
    # Slice to the END of the stop branch (its `return`), not a fixed character count —
    # a char window silently breaks when anything is inserted inside the branch.
    stop = src.index("Stopping after Phase")
    branch = src[stop:src.index("\n\n", stop)]
    assert "_materialize_preview_report" in branch
    assert 'return preview_path or ""' in branch


def test_preview_emits_build_feasibility():
    src = inspect.getsource(ResearchFlow._materialize_preview_report)
    assert '"build_feasibility_score"' in src
    assert '"data_feasibility_score"' in src


def test_preview_refreshes_score_derived_tags(tmp_path):
    idea = BaseSolutionIdea(
        solution_name="Preview report idea",
        description="A concrete solution.",
        value_proposition="A useful outcome.",
        pain_points_addressed=["A validated pain"],
        core_features=["Core feature"],
        target_personas=["Buyer"],
        market_fit_score=0.55,
        technical_feasibility_score=0.90,
        novelty_score=0.45,
        solo_dev_feasibility=0.85,
        tags=IdeaTags(
            target_market="b2b",
            monetization="subscription",
            strengths=["market-fit"],
            primary_strength="market-fit",
        ),
    )
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.niche_description = "A test market"
    flow.job_id = "job-tag-refresh"
    flow._state = SimpleNamespace(
        job_id=flow.job_id,
        idea_generation=SimpleNamespace(solution_ideas=[idea]),
        idea_ruled_out=[],
        idea_overlap_groups=[],
    )

    path = flow._materialize_preview_report(str(tmp_path))

    assert path is not None
    report = json.loads(Path(path).read_text())
    tags = report["alternative_solutions"][0]["tags"]
    assert "market-fit" not in tags["strengths"]
    assert tags["strengths"] == ["quick-build", "solo-friendly"]
    assert tags["primary_strength"] == "solo-friendly"
    assert tags["target_market"] == "b2b"
    assert tags["monetization"] == "subscription"


def test_preview_backfills_legacy_demoted_idea_details(tmp_path):
    idea = SimpleNamespace(
        solution_name="MetaDossier",
        candidate_status="demoted",
        model_dump=lambda mode="python": {
            "solution_name": "MetaDossier",
            "description": "A fantasy esports card collection game",
            "value_proposition": "Open packs and build esports rosters",
            "candidate_status": "demoted",
            "source_frame": "pain",
        },
    )
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.niche_description = "Competitive esports fans"
    flow.job_id = "job-seed-backfill"
    flow._state = SimpleNamespace(
        job_id=flow.job_id,
        idea_generation=SimpleNamespace(solution_ideas=[idea]),
        idea_ruled_out=[{
            "idea_name": "MetaDossier",
            "pain_title": "Cannot find reliable esports reporting",
            "reason": "Thin market",
            "market_fit": 0.35,
            "market_fit_band": "low",
            "prior_tier": "single",
            "source": "demoted_winner",
            "evidence": "",
            "source_frame": "pain",
        }],
        idea_overlap_groups=[],
    )

    path = flow._materialize_preview_report(str(tmp_path))

    assert path is not None
    report = json.loads(Path(path).read_text())
    assert report["examined_ruled_out"][0]["idea"]["solution_name"] == "MetaDossier"
