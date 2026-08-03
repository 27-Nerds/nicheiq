"""The preview payload's `idea_theses` must describe the CURRENT pool.

`_materialize_preview_report` also runs after a regenerate/seed batch merged new ideas in, so it
re-derives the thesis partition from the persisted buyer-job partition instead of projecting the
Stage-5 rollup. Projecting the stale rollup would leave a regenerated idea in no thesis at all —
a silent drop the partition contract forbids.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow

NICHE = "Independent veterinary clinics managing medication"
LEDGER = "Controlled-drug balances cannot be maintained"
STOCK = "Clinics discover stockouts only when items are needed"

PARTITION = {
    "source": "llm", "degraded": False, "degradation_reason": None,
    "families": [
        {"family_id": "ledger", "buyer": "Compliance officer",
         "triggering_job": "Keep a defensible controlled-drug record",
         "economic_outcome": "Clinic budget", "display_label": "Controlled-drug ledger",
         "member_pain_ids": [LEDGER], "inferred": False},
        {"family_id": "stockout", "buyer": "Inventory coordinator",
         "triggering_job": "Prevent stockouts", "economic_outcome": "Clinic budget",
         "display_label": "Stockout prevention", "member_pain_ids": [STOCK], "inferred": False},
    ],
}


def _idea(name, pain, **kw):
    idea = SimpleNamespace(
        solution_name=name, source_pain=pain, candidate_status="active",
        pain_points_addressed=[pain], market_fit_score=0.6, technical_feasibility_score=0.6,
        novelty_score=0.5, seo_scalability_score=0.5, winning_angle="vertical_workflow",
        idea_tier="single", source_frame="pain", incumbent_parity="none found",
        data_sources=["FDA NDC Directory"], idea_id=None, idea_revision=1,
    )
    for k, v in kw.items():
        setattr(idea, k, v)
    return idea


def _read_preview(tmp_path: Path) -> dict:
    files = list(tmp_path.glob("preview_report_*.json"))
    assert len(files) == 1, f"expected one preview report, got {files}"
    return json.loads(files[0].read_text())


def _flow(job_id, ideas, *, stale_theses=None):
    flow = ResearchFlow(niche_description=NICHE, job_id=job_id)
    flow.state.buyer_job_partition = PARTITION
    flow.state.idea_generation = SimpleNamespace(solution_ideas=ideas)
    if stale_theses is not None:
        flow.state.idea_theses = stale_theses
    return flow


def test_preview_theses_include_ideas_added_after_the_stage5_rollup(tmp_path):
    ideas = [_idea("NarcVault", LEDGER), _idea("Regenerated", STOCK)]
    # Stage-5 ran before "Regenerated" existed.
    stale = {"family_source": "llm", "unassigned": [], "uncovered_families": [],
             "theses": [{"family_id": "ledger", "display_label": "Controlled-drug ledger",
                         "members": [{"name": "NarcVault"}], "lead_idea_name": "NarcVault",
                         "incumbent_status": "open", "incumbent_vendors": [],
                         "fatal_assumptions": []}]}
    flow = _flow("test-job-theses-1", ideas, stale_theses=stale)

    assert flow._materialize_preview_report(str(tmp_path)) is not None
    theses = _read_preview(tmp_path)["idea_theses"]

    placed = {m["name"] for t in theses["theses"] for m in t["members"]}
    assert placed == {"NarcVault", "Regenerated"}
    assert theses["unassigned"] == []
    # Family ids come from the PERSISTED partition — stable across batches.
    assert {t["family_id"] for t in theses["theses"]} == {"ledger", "stockout"}


def test_preview_theses_fall_back_to_state_without_a_persisted_partition(tmp_path):
    flow = _flow("test-job-theses-2", [_idea("NarcVault", LEDGER)])
    flow.state.buyer_job_partition = {}
    flow.state.idea_theses = {"family_source": "llm", "theses": [], "uncovered_families": [],
                              "unassigned": []}

    assert flow._materialize_preview_report(str(tmp_path)) is not None
    assert _read_preview(tmp_path)["idea_theses"] == flow.state.idea_theses


def test_preview_theses_key_always_present(tmp_path):
    flow = ResearchFlow(niche_description=NICHE, job_id="test-job-theses-3")
    assert flow._materialize_preview_report(str(tmp_path)) is not None
    assert _read_preview(tmp_path)["idea_theses"] == {}
