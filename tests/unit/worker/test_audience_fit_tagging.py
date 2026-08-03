"""PR 10 / S4.1 — the two worker coverage holes for `audience_fit`.

The MAIN flow tags late-born ideas already (`_tag_audience_fit` runs after
`execute_pipeline` returns, so bundles/merges/salvage are covered). The two paths that
mint ideas OUTSIDE that flow — `run_regenerate_ideas` (additional idea batch) and
`run_seed_idea` (user-composed seed) — merged into
`state.idea_generation.solution_ideas` and checkpointed without ever tagging. Untagged
ideas don't just lose the "Adjacent audience" chip: they drag pool coverage below the
90% gate, which silently disables the ranking penalty for the WHOLE pool.

Both must therefore re-tag the FULL merged pool, after the merge and before the
authoritative `save_stage`.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture(autouse=True)
def _isolate_paid_pool_artifact_protocol():
    with patch("worker.paid_pool_recovery.PaidPoolMutationGuard") as guard_class:
        yield guard_class.return_value


def _idea(name, **kw):
    idea = MagicMock(
        solution_name=name, name=name, candidate_status="active", source_frame=None,
        duplicate_of=None, mechanism_tag=None, data_source_tag=None, journey_tag=None,
        idea_id=None, idea_revision=None, identity_origin=None,
        identity_operation_id=None, audience_fit=None, **kw
    )
    idea.model_dump.return_value = {"solution_name": name}
    return idea


def _flow_with_pool(old_solutions):
    flow = MagicMock()
    flow.resume_from_checkpoint.return_value = True
    flow.cleanup_collections = MagicMock()
    flow.allowed_project_types = None
    flow.idea_focus = "auto"
    flow.cost_tracker = None
    state = MagicMock()
    state.idea_generation = MagicMock(solution_ideas=list(old_solutions))
    state.idea_ruled_out = []
    flow.state = state
    flow.checkpoint_mgr = MagicMock()
    flow.checkpoint_mgr.checkpoint_folder = "/tmp/cp"
    flow.checkpoint_mgr.save_stage.return_value = True
    flow._materialize_preview_report.return_value = "/tmp/preview_report_job-1.json"
    return flow


def _record_pool_at_call_time(flow, seen):
    """Capture the pool `_tag_audience_fit` would see, plus the save count at that moment —
    proving it ran AFTER the merge and BEFORE the authoritative save."""
    def _tag(*args, **kwargs):
        seen["pool"] = list(flow.state.idea_generation.solution_ideas)
        seen["saves_before"] = flow.checkpoint_mgr.save_stage.call_count
        seen["kwargs"] = kwargs
    flow._tag_audience_fit.side_effect = _tag


class TestRegenerateTagsMergedPool:
    @patch("worker.tasks.notify_regeneration_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_tag_audience_fit_called_with_merged_pool_before_save(
        self, mock_progress, mock_notify
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            old_sol = _idea("OldSol")
            new_sol = _idea("NewSol")
            flow = _flow_with_pool([old_sol])
            MockFlow.return_value = flow
            MockCrew.return_value.execute_pipeline.return_value = [
                MagicMock(solution_ideas=[new_sol])
            ]
            MockCrew.return_value.ruled_out_pains = []
            seen: dict = {}
            _record_pool_at_call_time(flow, seen)

            from worker.tasks import run_regenerate_ideas

            with patch(
                "worker.tasks._solution_to_preview_dict",
                return_value={"solution_name": "NewSol"},
            ):
                run_regenerate_ideas(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    existing_solution_names=["OldSol"],
                    niche="test niche",
                    dispatch_id="dispatch-1",
                    batch_ordinal=2,
                )

            flow._tag_audience_fit.assert_called_once()
            # FULL merged pool, not just the new batch slice.
            assert seen["pool"] == [old_sol, new_sol]
            # Ran before the worker's authoritative save of the merged pool.
            assert seen["saves_before"] == 0
            # persist=False: the guarded save below is the ONLY write the refund path rolls back.
            assert seen["kwargs"] == {"persist": False}


class TestSeedTagsMergedPool:
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_tag_audience_fit_called_with_merged_pool_before_save(
        self, mock_progress, mock_notify
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            old_sol = _idea("Existing")
            seed_idea = _idea("Seed Idea")
            flow = _flow_with_pool([old_sol])
            MockFlow.return_value = flow
            MockCrew.return_value.execute_seed_pipeline.return_value = seed_idea
            MockCrew.return_value.ruled_out_pains = []
            seen: dict = {}
            _record_pool_at_call_time(flow, seen)

            from worker.tasks import run_seed_idea

            with patch(
                "worker.tasks._solution_to_preview_dict",
                return_value={"solution_name": "Seed Idea"},
            ):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="dispatch-1",
                )

            flow._tag_audience_fit.assert_called_once()
            assert seen["pool"] == [old_sol, seed_idea]
            assert seen["saves_before"] == 0
            assert seen["kwargs"] == {"persist": False}
