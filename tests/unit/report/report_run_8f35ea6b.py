"""Loader for `tests/fixtures/report_run_8f35ea6b/` — one complete captured run, restored
into a REAL `ResearchState` through the REAL production restore path.

WHY A CHECKPOINT FOLDER AND NOT A HAND-BUILT STATE. Twenty-three unit-test files construct
a `ReportGenerator`; every one of them feeds it a `MagicMock()` or a `SimpleNamespace`, and
NOT ONE of them calls `_assemble_base_report()` or `generate_report()`. So the 63-field
artifact the frontend actually renders has never been produced in a test. A `MagicMock`
state auto-vivifies every attribute the assembler reads, which means a field renamed or
removed on `ResearchState` still yields a truthy `Mock` and the sub-generator tests stay
green over a report the real state can no longer produce.

The state here is not authored at all. `output/checkpoints/` is gitignored, so the run's
27 stage files are vendored VERBATIM (byte-identical to the capture; verify with
`diff -r`) and rebuilt by `CheckpointManager.load_checkpoint_folder` — the same code the
worker runs on resume. The state that reaches the producer is therefore a state the
pipeline demonstrably emitted, field for field.

THE RUN. job 8f35ea6b-0321-41fd-b747-e4d76605f50f, "small-batch coffee roasters managing
green coffee inventory and cupping scores", captured 2026-08-03. `entry_mode="idea"`,
stages 1-12 completed, stage 13 skipped by the pipeline's own branch, `current_stage=14` —
i.e. parked at exactly the point `ReportGenerator` is invoked in production.

NOTHING IS TRIMMED, and that is measured rather than assumed: removing a single one of the
116 captured Reddit posts changes the generated artifact (`research_metadata` and
`data_quality_summary` both count the corpus), so there is no smaller corpus that produces
the same output. `cost_tracker.json`, `stage_5_1_divergent.json`, the `stage_6a`-`6d`
intermediates and the two `_partial` files provably do NOT change it — they are kept
anyway, because a checkpoint folder missing them is a shape a completed run does not leave
behind, and a partial input is the same class of lie as a partial fixture.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.models.research_state import ResearchState

FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "report_run_8f35ea6b"
)
JOB_ID = "8f35ea6b-0321-41fd-b747-e4d76605f50f"


def load_run(tmp_dir: Path | None = None) -> tuple[ResearchState, CheckpointManager]:
    """Restore the captured run into a real `ResearchState` via the real checkpoint loader.

    Returns the manager too, because producers that persist (the preview materializer calls
    `checkpoint_mgr.save_stage`) should write through the real one rather than a `Mock` that
    accepts any argument shape.

    `tmp_dir` copies the folder first. `load_checkpoint_folder` only reads when `job_id` is
    None (the cross-job fork branch is the only writer), but a producer that saves must not
    be able to edit a committed fixture, so callers that can afford the copy should pass one.
    """
    folder = FIXTURE_DIR
    if tmp_dir is not None:
        folder = Path(tmp_dir) / FIXTURE_DIR.name
        shutil.copytree(FIXTURE_DIR, folder)

    state = ResearchState(niche_description="")
    manager = CheckpointManager(niche_description="", state=state)
    assert manager.load_checkpoint_folder(folder), (
        f"the vendored checkpoint at {folder} no longer restores. If a ResearchState model "
        "changed incompatibly, that is the finding — a real run's own checkpoint stopped "
        "deserializing, which is what happens to every user mid-run resume."
    )
    return state, manager


def load_state(tmp_dir: Path | None = None) -> ResearchState:
    """`load_run` for callers that only need the state."""
    return load_run(tmp_dir)[0]
