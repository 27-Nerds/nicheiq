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


@pytest.fixture(autouse=True)
def _isolate_paid_pool_artifact_protocol():
    """These task fixtures have no real checkpoint files; recovery I/O is tested separately."""
    with patch("worker.paid_pool_recovery.PaidPoolMutationGuard") as guard_class:
        yield guard_class.return_value


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
    idea.idea_id = None
    idea.idea_revision = None
    idea.identity_origin = None
    idea.identity_operation_id = None
    return idea


class TestRunSeedIdeaRuledOutMerge:
    @patch("worker.tasks.create_progress_callback")
    def test_seed_rejects_a_checkpoint_pool_that_no_longer_matches_admission(
        self, mock_progress
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            flow.state.idea_generation.solution_ideas = [
                _make_idea(solution_name="Existing")
            ]
            MockFlow.return_value = flow

            from worker.tasks import run_seed_idea

            with pytest.raises(RuntimeError, match="base candidate refs do not match"):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="dispatch-1",
                    base_candidate_refs=[{
                        "idea_id": "idea_wrong",
                        "idea_revision": 1,
                    }],
                    pool_identity_map=[{
                        "idea_id": "idea_expected",
                        "idea_revision": 1,
                        "solution_name": "Existing",
                    }],
                )

            MockCrew.assert_not_called()

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_seed_admission_ignores_absorbed_duplicate_name(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            hidden = _make_idea(candidate_status="absorbed", solution_name="Appliance Ledger")
            hidden.idea_id = "idea-hidden"
            hidden.idea_revision = 1
            hidden.identity_origin = "phase1"
            hidden.identity_operation_id = "initial"
            visible = _make_idea(solution_name="Appliance Ledger")
            flow.state.idea_generation.solution_ideas = [hidden, visible]
            MockFlow.return_value = flow
            MockCrew.return_value.execute_seed_pipeline.return_value = _make_idea()
            MockCrew.return_value.ruled_out_pains = []

            from worker.tasks import run_seed_idea

            result = run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="dispatch-1",
                base_candidate_refs=[{
                    "idea_id": "idea-visible",
                    "idea_revision": 1,
                }],
                pool_identity_map=[{
                    "idea_id": "idea-visible",
                    "idea_revision": 1,
                    "solution_name": "Appliance Ledger",
                }],
            )

            assert result["outcome"] == "accepted"
            assert hidden.idea_id == "idea-hidden"
            assert visible.idea_id == "idea-visible"
            mock_notify.assert_called_once()

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Synthesized Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_exact_synthesis_uses_backend_identity_namespace(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow
            idea = _make_idea(solution_name="Synthesized Idea")
            MockCrew.return_value.execute_seed_pipeline.return_value = idea
            MockCrew.return_value.ruled_out_pains = []

            from nicheiq.utils.idea_identity import deterministic_idea_id
            from worker.tasks import run_seed_idea

            result = run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={
                    "seed_text": "exact direction",
                    "synthesis_evaluation": {"evaluation_id": "dispatch-synth"},
                },
                niche="test niche",
                dispatch_id="dispatch-synth",
            )

            assert result["outcome"] == "accepted"
            assert idea.idea_id == deterministic_idea_id(
                "job-1", "synthesis", "dispatch-synth", 0
            )
            assert idea.identity_origin == "synthesis"
            assert idea.identity_operation_id == "dispatch-synth"
            mock_notify.assert_called_once()

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_checkpoint_failure_prevents_seed_completion(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            flow.checkpoint_mgr.save_stage.return_value = False
            MockFlow.return_value = flow
            idea = _make_idea()
            MockCrew.return_value.execute_seed_pipeline.return_value = idea
            MockCrew.return_value.ruled_out_pains = []

            from worker.tasks import run_seed_idea

            with pytest.raises(RuntimeError, match="authoritative checkpoint"):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="dispatch-1",
                )

            mock_notify.assert_not_called()
            flow._materialize_preview_report.assert_not_called()
            assert flow.state.idea_generation.solution_ideas == []
            assert flow.state.idea_ruled_out == []

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_preview_failure_restores_seed_before_settlement(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            existing = _make_idea(solution_name="Existing")
            flow.state.idea_generation.solution_ideas = [existing]
            flow.checkpoint_mgr.save_stage.side_effect = [True, True]
            flow._materialize_preview_report.side_effect = [
                None,
                "/tmp/preview_report_job-1.json",
            ]
            MockFlow.return_value = flow
            MockCrew.return_value.execute_seed_pipeline.return_value = _make_idea()
            MockCrew.return_value.ruled_out_pains = []

            from worker.tasks import run_seed_idea

            with pytest.raises(RuntimeError, match="idea preview"):
                run_seed_idea(
                    job_id="job-1",
                    checkpoint_path="/tmp/cp",
                    seed={"seed_text": "my idea"},
                    niche="test niche",
                    dispatch_id="dispatch-1",
                )

            assert flow.state.idea_generation.solution_ideas == [existing]
            assert flow.state.idea_ruled_out == []
            assert flow.checkpoint_mgr.save_stage.call_count == 2
            assert flow._materialize_preview_report.call_count == 2
            mock_notify.assert_not_called()

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
            assert len(flow.state.idea_ruled_out) == 1
            ruled_out = flow.state.idea_ruled_out[0]
            assert {
                "pain_title": ruled_out["pain_title"],
                "dispatch_id": ruled_out["dispatch_id"],
                "source_frame": ruled_out["source_frame"],
            } == {
                "pain_title": "P1",
                "dispatch_id": "d-this",
                "source_frame": "user_seed",
            }
            assert ruled_out["idea_id"] == idea.idea_id
            assert ruled_out["idea_revision"] == idea.idea_revision
            assert ruled_out["identity_origin"] == "seed"
            assert ruled_out["identity_operation_id"] == "d-this"
            assert ruled_out["finding_id"].startswith("finding_")
            assert ruled_out["finding_revision"] == 1
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
    def test_red_team_killed_seed_at_visible_cap_is_still_selectable_and_accepted(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea(candidate_status="active")
            # Intentional policy: a shipped-parity red-team kill caps market fit at 0.45,
            # above the strict <0.40 demotion bar. "Killed" is a downstream risk floor,
            # not a visibility status, so the evaluated seed remains selectable.
            idea.market_fit_score = 0.45
            idea.red_team_verdict = "killed"
            idea.incumbent_parity = "shipped by evidence: modal mechanism mismatch"
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
            assert idea.candidate_status == "active"
            assert idea.market_fit_score == 0.45
            assert idea.red_team_verdict == "killed"
            assert idea in flow.state.idea_generation.solution_ideas
            assert flow.state.idea_ruled_out == []
            assert mock_notify.call_args.args[2] == "accepted"
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
            # Forward commit succeeds; a fault on the first rollback write must be retried
            # before the tagged exception reaches queue_consumer's refund path.
            flow.checkpoint_mgr.save_stage.side_effect = [True, False, True]
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
            # Saved once with the merge, then rollback was retried after one injected fault.
            assert flow.checkpoint_mgr.save_stage.call_count == 3
            # Materialized once with the evaluated result and again after reverting,
            # so an asset-cache refresh cannot resurrect a ghost candidate.
            assert flow._materialize_preview_report.call_count == 2

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


class TestSeedBatchProvenance:
    """A seed is its own paid append-only operation, so it must carry batch provenance —
    the UI's "new in this batch" marker reads these two fields and skipped chat-born ideas
    entirely while they were null. Live run 8ef396eb (2026-08-02) persisted a seed with
    both fields null; these tests pin the stamp so the next null is a code failure rather
    than an unfalsifiable one."""

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_seed_takes_the_next_ordinal_after_the_pool(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            # A realistic pool: original-run ideas (null ordinal) plus one added batch.
            pool = []
            for name, ordinal in (
                ("Phase One A", None), ("Phase One B", None),
                ("Batch One A", 1), ("Batch One B", 1),
            ):
                existing = _make_idea(solution_name=name)
                existing.generation_batch_ordinal = ordinal
                existing.generation_operation_id = "batch-dispatch" if ordinal else None
                pool.append(existing)
            flow.state.idea_generation.solution_ideas = pool
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea()
            idea.generation_batch_ordinal = None
            idea.generation_operation_id = None
            crew.execute_seed_pipeline.return_value = idea
            crew.ruled_out_pains = []

            from worker.tasks import run_seed_idea

            run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="d-seed",
            )

            # Its own ordinal, after everything already in the pool — so it, and only it,
            # reads as new.
            assert idea.generation_batch_ordinal == 2
            assert idea.generation_operation_id == "d-seed"
            # Nothing already in the pool was re-stamped as part of this operation.
            assert [p.generation_batch_ordinal for p in pool] == [None, None, 1, 1]

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_first_seed_into_an_unbatched_pool_is_ordinal_one(
        self, mock_progress, mock_notify, mock_preview
    ):
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            existing = _make_idea(solution_name="Phase One A")
            existing.generation_batch_ordinal = None
            existing.generation_operation_id = None
            flow.state.idea_generation.solution_ideas = [existing]
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea()
            idea.generation_batch_ordinal = None
            idea.generation_operation_id = None
            crew.execute_seed_pipeline.return_value = idea
            crew.ruled_out_pains = []

            from worker.tasks import run_seed_idea

            run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="d-seed",
            )

            assert idea.generation_batch_ordinal == 1
            assert idea.generation_operation_id == "d-seed"

    @patch("worker.tasks._solution_to_preview_dict", return_value={"solution_name": "Seed Idea"})
    @patch("worker.tasks.notify_seed_complete")
    @patch("worker.tasks.create_progress_callback")
    def test_demoted_seeds_ruled_out_record_carries_the_same_provenance(
        self, mock_progress, mock_notify, mock_preview
    ):
        """`_record_ruled_out` copies provenance off the idea, but it runs inside
        execute_seed_pipeline — before the stamp — so the worker mirrors it onto the
        finding. A demoted seed that lost its provenance would be unattributable in
        "Examined & ruled out"."""
        mock_progress.return_value = MagicMock()
        with patch("nicheiq.flows.research_flow.ResearchFlow") as MockFlow, \
                patch("nicheiq.crews.unified_solution_crew.UnifiedSolutionCrew") as MockCrew:
            flow = _make_flow()
            MockFlow.return_value = flow

            crew = MockCrew.return_value
            idea = _make_idea(candidate_status="demoted")
            idea.generation_batch_ordinal = None
            idea.generation_operation_id = None
            crew.execute_seed_pipeline.return_value = idea
            crew.ruled_out_pains = [
                {"pain_title": "P1", "dispatch_id": "d-seed", "idea": {"solution_name": "Seed Idea"}},
            ]

            from worker.tasks import run_seed_idea

            run_seed_idea(
                job_id="job-1",
                checkpoint_path="/tmp/cp",
                seed={"seed_text": "my idea"},
                niche="test niche",
                dispatch_id="d-seed",
            )

            finding = flow.state.idea_ruled_out[0]
            assert finding["generation_operation_id"] == "d-seed"
            assert finding["generation_batch_ordinal"] == idea.generation_batch_ordinal
            assert finding["idea"]["generation_operation_id"] == "d-seed"
