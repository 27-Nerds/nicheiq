"""The worker→backend HTTP bodies, GENERATED from the real producers and vendored.

WHY THIS EXISTS. Every one of these bodies is `.parse()`d by a Zod schema in
`backend/src/routes/workers.ts` (`GateReachedSchema`, `IdeasReadySchema`) and then rendered
by the SvelteKit gate card and selection grid. On the Python side the bodies' *contents*
are hand-written today:

  * `tests/unit/worker/test_tasks_interactive.py` passes `{"type": "niche_validation"}` and
    `{"type": "audience_mapping_gate"}` where the real gate artifact goes. Those two dicts
    are the `degraded`/type marker only — `_build_g1_gate_artifact` and
    `_build_g2_gate_artifact` emit eight and five more keys, and the G2 patch whitelist is
    cross-checked by the backend against `artifact.pains[].title` and
    `artifact.segments[].segment_name`, neither of which any Python test has ever seen a
    real value of.
  * the same file replaces `_solution_to_preview_dict` with
    `model_dump.return_value = {"solution_name": "Sol1", "name": "Sol1"}` — a two-key stand-in
    for the ~40-key object the selection grid ranks and renders.
  * `_dispatch_payload` is `@patch(..., return_value={"dispatch_id": "dispatch-1"})` in about
    fifteen places. It is the anti-replay guard merged into EVERY worker callback; if it ever
    stopped emitting that key, all fifteen would stay green while the back door reopened.

Each of those is the same generator that cost this repo six rounds of vacuous assertions on
`idea_validation`: the fixture records the author's belief about the producer's shape.

So the bodies below are not authored. They are captured off the wire — the real notify
functions run against an intercepted transport, carrying artifacts built by the real
producers over the real captured 8f35ea6b run state (see
`tests/unit/report/report_run_8f35ea6b.py`). `_dispatch_payload` is NOT patched here; the
real `set_active_dispatch` registry drives it, so the key name is the producer's, not mine.

Regenerate after any deliberate change to a callback body:

    WORKER_PAYLOAD_FIXTURE_REGEN=1 pytest tests/unit/worker/test_worker_payload_fixture_contract.py

and commit the JSON. Any other drift fails here.

NORMALIZED, and only these: `worker_id` (process/host identity, not payload shape — the
existing notify tests patch it the same way) and the three filesystem paths, which are
passed in as literals so the vendored body has no machine-local absolute path in it. The
dispatch id is a fixed literal fed to the REAL registry.

THE RUN IS NOT A GUIDED RUN, and that is deliberate rather than overlooked. 8f35ea6b ran
`entry_mode="idea"` to completion, so it never stopped at G1/G2 — but both artifact builders
are pure functions of `niche_context` / `pain_point_analysis` / `audience_mapping`, all of
which this run captured in full. `user_audience_scope` is None, so G2 takes its unpatched
branch (`primary_target` falls back to the Stage-4 value), which is exactly the state a
guided run is in the FIRST time it reaches G2.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import responses

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from nicheiq.flows.research_flow import ResearchFlow  # noqa: E402
from nicheiq.models.solution_idea import visible_ideas  # noqa: E402
from nicheiq.utils.score_helpers import audience_fit_coverage  # noqa: E402

from ..report.report_run_8f35ea6b import load_state  # noqa: E402

VENDORED_PATH = (
    project_root / "tests" / "fixtures" / "generated" / "workerCallbackBodies.generated.json"
)

_GATE_REACHED = re.compile(r".+/api/workers/gate-reached$")
_IDEAS_READY = re.compile(r".+/api/workers/ideas-ready$")

JOB_ID = "8f35ea6b-0321-41fd-b747-e4d76605f50f"
DISPATCH_ID = "3f8b1c2d-0000-4000-8000-000000000001"
WORKER_ID = "worker-fixture"
CHECKPOINT_PATH = "/checkpoints/report_run_8f35ea6b"
DISCOVERY_DATA_PATH = "/jobs/8f35ea6b/discovery_data.json"
PREVIEW_REPORT_PATH = "/jobs/8f35ea6b/preview_report.json"


def _flow(state) -> ResearchFlow:
    """A ResearchFlow positioned on the captured state, without re-running __init__.

    Same construction the existing production-path test
    (`tests/unit/flows/test_audience_drift_live_path.py`) uses; the difference is that the
    state here is a real `ResearchState` restored by the real checkpoint loader rather than
    a `SimpleNamespace`.
    """
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.job_id = JOB_ID
    flow.niche_description = state.niche_context.niche_description
    flow._state = state
    return flow


def _capture(register, send) -> dict:
    """Run a real notify function against an intercepted transport, return the sent body."""
    with responses.RequestsMock() as mock:
        mock.add(responses.POST, register, json={"status": "ok"}, status=200)
        send()
        assert len(mock.calls) == 1
        return json.loads(mock.calls[0].request.body)


def _build(tmp_path) -> dict:
    from worker.progress import (
        clear_active_dispatch,
        notify_gate_reached,
        notify_ideas_ready,
        set_active_dispatch,
    )
    from worker.tasks import _solution_to_preview_dict

    state = load_state(tmp_path)
    flow = _flow(state)

    # The REAL dispatch registry, not a patch of the function that reads it.
    set_active_dispatch(JOB_ID, DISPATCH_ID)
    try:
        with patch("worker.progress._get_worker_id", return_value=WORKER_ID):
            g1_artifact = flow._build_g1_gate_artifact()
            g1 = _capture(
                _GATE_REACHED,
                lambda: notify_gate_reached(JOB_ID, 1, CHECKPOINT_PATH, g1_artifact),
            )

            g2_artifact = flow._build_g2_gate_artifact()
            g2 = _capture(
                _GATE_REACHED,
                lambda: notify_gate_reached(JOB_ID, 4, CHECKPOINT_PATH, g2_artifact),
            )

            # Mirrors worker/tasks.py's own three lines, in order: visible ideas ->
            # pool-level audience-fit coverage -> per-idea preview dict.
            solutions = visible_ideas(state.idea_generation.solution_ideas)
            coverage = audience_fit_coverage(solutions)
            previews = [_solution_to_preview_dict(s, coverage) for s in solutions]
            ideas_ready = _capture(
                _IDEAS_READY,
                lambda: notify_ideas_ready(
                    JOB_ID,
                    previews,
                    CHECKPOINT_PATH,
                    total_to_validate=len(previews),
                    discovery_data_path=DISCOVERY_DATA_PATH,
                    preview_report_path=PREVIEW_REPORT_PATH,
                ),
            )
    finally:
        clear_active_dispatch(JOB_ID)

    return {"gate_reached_g1": g1, "gate_reached_g2": g2, "ideas_ready": ideas_ready}


def _check(path: Path, generated: dict) -> None:
    if os.environ.get("WORKER_PAYLOAD_FIXTURE_REGEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")

    assert json.loads(path.read_text()) == generated, (
        f"The vendored worker callback bodies ({path.name}) have drifted from what the "
        f"worker actually POSTs. Regenerate them:\n  "
        f"WORKER_PAYLOAD_FIXTURE_REGEN=1 pytest tests/unit/worker/{Path(__file__).name}\n"
        "Do NOT hand-edit the JSON — and check backend/src/routes/workers.ts before "
        "regenerating: these bodies are Zod-parsed there, so a key this file gains or loses "
        "is a key the backend gains or loses too."
    )


def test_vendored_callback_bodies_match_the_real_producers(tmp_path):
    _check(VENDORED_PATH, _build(tmp_path))


def test_the_dispatch_guard_rides_on_every_body(tmp_path):
    """The key ~15 tests hand-write, read off the real `_dispatch_payload` instead.

    `_dispatch_payload` exists because a callback from a superseded attempt must match
    nothing on the backend. Patching it out of every test means the one thing it guarantees
    — that the id is present on every callback — is the one thing nothing checks.
    """
    bodies = _build(tmp_path)
    assert set(bodies) == {"gate_reached_g1", "gate_reached_g2", "ideas_ready"}
    for name, body in bodies.items():
        assert body["dispatch_id"] == DISPATCH_ID, f"{name} lost the dispatch guard"


def test_the_gate_artifacts_carry_the_identifiers_the_backend_cross_checks(tmp_path):
    """The G2 patch whitelist is validated against these exact lists on the backend.

    `{"type": "audience_mapping_gate"}` — the hand-written stand-in in
    test_tasks_interactive.py — satisfies every assertion that file makes while carrying
    none of them, so a builder that stopped emitting `pains` or `segments` would ship a
    gate whose every patch is rejected as unknown, with the Python suite green.
    """
    bodies = _build(tmp_path)

    g1 = bodies["gate_reached_g1"]["gate_artifact"]
    assert g1["type"] == "niche_validation"
    assert "degraded" not in g1
    assert g1["market_segments"] and g1["niche_description"]

    g2 = bodies["gate_reached_g2"]["gate_artifact"]
    assert g2["type"] == "audience_mapping_gate"
    assert "degraded" not in g2
    assert all(p["title"] for p in g2["pains"])
    assert all(s["segment_name"] for s in g2["segments"])
    # The un-patched branch: no G1 patch was applied, so the effective primary is Stage 4's.
    assert g2["primary_target"] == g2["primary_target_stage4"]


def test_the_preview_dicts_are_the_full_idea_not_a_name_pair(tmp_path):
    """`{"solution_name": ..., "name": ...}` is what the interactive tests substitute.

    The real producer stamps the ranking score the selection grid short-circuits to, the
    refreshed tag facets, and the distilled critic note — and it DROPS `calibration_notes`,
    an internal per-criterion audit that `model_dump()` would otherwise leak to a payload
    the browser receives. A two-key stub can prove none of that.
    """
    solutions = _build(tmp_path)["ideas_ready"]["solutions"]
    assert len(solutions) > 1
    for preview in solutions:
        assert preview["name"] == preview["solution_name"]
        assert "calibration_notes" not in preview, "internal audit prose leaked to the browser"
        assert "adjusted_composite_score" in preview
        assert "critic_concern" in preview
        assert "tags" in preview
    # The control: this is a real pool, not one idea repeated.
    assert len({p["solution_name"] for p in solutions}) == len(solutions)
