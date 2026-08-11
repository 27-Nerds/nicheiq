"""Durable Stage-5 sub-progress producer contract."""

from nicheiq.flows.research_flow import ResearchFlow


def test_stage5_subprogress_bridge_keeps_public_stage_and_emits_stable_artifact():
    flow = ResearchFlow.__new__(ResearchFlow)
    emitted = []
    flow._emit_progress = lambda *args: emitted.append(args)

    callback = flow._stage5_subprogress_callback()
    callback("candidate_refinement", "Refining candidate solutions")

    assert emitted == [(
        5,
        "Solution Ideation",
        "running",
        {
            "type": "stage_subprogress",
            "stage": 5,
            "code": "candidate_refinement",
            "label": "Refining candidate solutions",
        },
    )]

