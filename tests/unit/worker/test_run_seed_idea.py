"""Tests for worker.tasks.run_seed_idea — the outcome-delivery path fixes:

- A DEMOTED seed's ruled-out record must land in `state.idea_ruled_out` (not just the
  crew-local `ruled_out_pains` list, which the worker never read before this fix), filtered
  to THIS dispatch's own entry, and the preview report must be re-materialized so the
  cached/DB-pointed asset the UI reads actually reflects it (Blocker 1).
- On a delivery failure (`notify_seed_complete` exhausts retries and is tagged
  `seed_delivery_only`), the merge must be REVERTED from the checkpoint — the automatic
  refund that follows (heartbeat -> cancelSeedIdeaDispatch) must be honest, and no unpaid
  ghost idea may survive in the checkpoint (Amend 4).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest

from nicheiq.config.settings import settings


def _make_flow():
    flow = MagicMock()
    flow.progress_callback = None
    state = MagicMock()
    state.idea_generation = MagicMock(solution_ideas=[])
    state.idea_ruled_out = []
    flow.state = state
    flow.resume_from_checkpoint.return_value = True
    flow.checkpoint_mgr = MagicMock()
    flow.checkpoint_mgr.checkpoint_folder = "/tmp/cp"
    flow.allowed_project_types = None
    flow.idea_focus = "auto"
    flow.cost_tracker = None
    flow._materialize_preview_report.return_value = "/tmp/preview_report_job-1.json"
    return flow


def _make_idea(candidate_status="active", solution_name="Seed Idea"):
    idea = MagicMock()
    idea.candidate_status = candidate_status
    idea.solution_name = solution_name
    idea.duplicate_of = None
    # Explicit None (not auto-MagicMock attrs) so detect_catalog_duplicate's real fuzzy/
    # structural checks behave sanely if old_solutions is non-empty.
    idea.mechanism_tag = None
    idea.data_source_tag = None
    idea.journey_tag = None
    return idea


class TestRunSeedIdeaRuledOutMerge:
    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_demoted_seed_merges_only_this_dispatchs_ruled_out_record(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea(candidate_status="demoted")
            crew.execute_seed_pipeline.return_value = idea
            crew.ruled_out_pains = [
                {"pain_title": "P1", "dispatch_id": "d-this", "source_frame": "user_seed"},
                {"pain_title": "P2", "dispatch_id": "other-dispatch", "source_frame": "user_seed"},
            ]

            from worker.tasks import run_seed_idea

            result = run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="d-this",
            )

            assert result == {"status": "seed_settled", "job_id": "job-1", "outcome": "demoted"}
            # Only THIS dispatch's ruled-out record was merged in — not the other dispatch's.
            assert flow.state.idea_ruled_out == [
                {"pain_title": "P1", "dispatch_id": "d-this", "source_frame": "user_seed"}
            ]
            # The idea itself is still merged into the checkpoint pool (Python-side keeps the
            # full outcome pair for audit; the BACKEND is what gates it out of the selectable
            # `solutionIdeas` array for a demoted outcome — see workers.ts /seed-complete).
            assert idea in flow.state.idea_generation.solution_ideas
            flow.checkpoint_mgr.save_stage.assert_any_call(
                "stage_5_3_refinement", flow.state.idea_generation
            )
            flow._materialize_preview_report.assert_called_once_with(str(settings.checkpoint_dir))
            mock_notify.assert_called_once()

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_accepted_seed_merges_into_pool_and_ignores_unrelated_ruled_out(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea(candidate_status="active")
            crew.execute_seed_pipeline.return_value = idea
            # Nothing in the crew's list belongs to THIS dispatch.
            crew.ruled_out_pains = [{"pain_title": "P2", "dispatch_id": "other-dispatch"}]

            from worker.tasks import run_seed_idea

            result = run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="d-this",
            )

            assert result["outcome"] == "accepted"
            assert idea in flow.state.idea_generation.solution_ideas
            assert flow.state.idea_ruled_out == []
            flow._materialize_preview_report.assert_called_once()


class TestRunSeedIdeaDeliveryFailureRevert:
    @patch(
        "nicheiq.utils.validation.crew_guardrails.detect_catalog_duplicate",
        return_value=False,
    )
    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete", side_effect=RuntimeError("could not be delivered"))
    @patch("worker.tasks.create_progress_callback")
    def test_delivery_failure_reverts_merge_so_no_ghost_survives(
        self, mock_progress, mock_notify, mock_preview, mock_dup
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            existing = _make_idea(candidate_status="active", solution_name="Existing")
            flow.state.idea_generation.solution_ideas = [existing]
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea(candidate_status="demoted")
            crew.execute_seed_pipeline.return_value = idea
            crew.ruled_out_pains = [{"pain_title": "P1", "dispatch_id": "d-this"}]

            from worker.tasks import run_seed_idea

            with pytest.raises(RuntimeError, match="could not be delivered"):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="d-this",
                )

            # The merge (and its ruled-out record) is REVERTED — back to exactly the pre-seed
            # pool, so an eventual refund (heartbeat -> cancelSeedIdeaDispatch) is honest and no
            # unpaid ghost idea survives in the checkpoint.
            assert flow.state.idea_generation.solution_ideas == [existing]
            assert flow.state.idea_ruled_out == []
            # Saved at least twice: once with the merge, once with the revert.
            assert flow.checkpoint_mgr.save_stage.call_count >= 2

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete", side_effect=RuntimeError("could not be delivered"))
    @patch("worker.tasks.create_progress_callback")
    def test_non_delivery_failure_does_not_revert(self, mock_progress, mock_notify, mock_preview):
        """A genuine pipeline failure (birth raised BEFORE any merge/save) must not be treated
        as seed_delivery_only, and must not trigger the revert path at all."""
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            crew.execute_seed_pipeline.return_value = None  # birth produced nothing

            from worker.tasks import run_seed_idea

            with pytest.raises(RuntimeError, match="did not produce an idea"):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="d-this",
                )

            # Never reached the merge/save/notify block at all.
            flow.checkpoint_mgr.save_stage.assert_not_called()
            mock_notify.assert_not_called()
