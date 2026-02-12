"""
RQ Task definitions for NicheIQ research jobs.

These tasks are enqueued by the Node.js backend and processed by RQ workers.
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from rq import get_current_job

from .progress import (
    create_progress_callback,
    publish_job_completed,
    publish_report_ready,
    notify_job_quality_gate_stop,
    notify_ideas_ready,
    notify_regeneration_complete,
)
from .status import mark_job_running


def run_research_job(
    job_id: str,
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None,
    resume: bool = False,
    generate_landing_page: bool = True,
) -> dict:
    """
    Main RQ task - runs the complete research pipeline + landing page generation.

    This task is enqueued by the Node.js backend when a user submits a job.
    Progress updates are published to Redis pub/sub for real-time SSE updates.
    Email notifications are handled by the Node.js backend (fetched from DB).

    Args:
        job_id: UUID of the job (from Node.js)
        niche: User's niche description
        user_id: Optional user ID for authenticated users
        allowed_project_types: Optional constraint on project types

    Returns:
        Dict with status, report_path, and optional landing_path
    """
    rq_job = get_current_job()
    logger.info(f"[Worker] Starting job {job_id} for user {user_id or 'anonymous'}, niche: {niche[:100]}...")

    # Set up output directory for this job
    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        # Import here to avoid loading heavy dependencies until needed
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.crews.landing_page_crew import LandingPageCrew
        from nicheiq.models.research_state import FinalReport

        # Create progress callback for real-time updates
        progress_callback = create_progress_callback(job_id)

        # Initialize and run research flow
        logger.info(f"[Worker] Initializing ResearchFlow for job {job_id}")
        flow = ResearchFlow(
            niche_description=niche,
            allowed_project_types=allowed_project_types,
            job_id=job_id,
        )

        # Attach progress callback to flow
        flow.progress_callback = progress_callback

        # Update job status to RUNNING in database (race-condition safe)
        # This ensures status is updated even if SSE connection isn't established yet
        mark_job_running(job_id)

        # Publish "job started" event for SSE clients (only for fresh runs)
        # For resume, the flow will emit the correct stage after loading checkpoint
        if not resume:
            progress_callback(1, "Niche Analysis", "running")

        # Run the research pipeline (resume from checkpoint if requested)
        logger.info(f"[Worker] Running research pipeline for job {job_id} (resume={resume})")
        report_path = flow.run_with_resume(auto_resume=resume)

        if not report_path or not Path(report_path).exists():
            raise RuntimeError("Research flow did not produce a report")

        logger.info(f"[Worker] Research complete for job {job_id}: {report_path}")

        # Copy report to job output directory
        job_report_path = output_dir / "report.json"
        with open(report_path) as src:
            report_data = json.load(src)
        with open(job_report_path, "w") as dst:
            json.dump(report_data, dst, indent=2)

        # Notify backend that the report is ready (triggers email notification)
        publish_report_ready(job_id, str(job_report_path))

        landing_path = None

        if generate_landing_page:
            # Generate landing page (isolated - errors don't crash the job)
            try:
                logger.info(f"[Worker] Generating landing page for job {job_id}")
                progress_callback(11, "Landing Page Generation", "running")

                # Load report for landing page generation
                report = FinalReport(**report_data)

                # Generate landing page
                crew = LandingPageCrew()
                result = crew.generate(report, page_mode="coming_soon")

                # Handle None result (guardrail failure)
                if result is None:
                    logger.warning(f"[Worker] Landing page generation returned None for job {job_id}")
                    progress_callback(11, "Landing Page Generation", "completed")
                else:
                    # Save landing page
                    job_landing_path = output_dir / "landing_page.html"
                    job_landing_path.write_text(result.html_output)
                    landing_path = str(job_landing_path)
                    progress_callback(11, "Landing Page Generation", "completed")
                    logger.info(f"[Worker] Landing page generated for job {job_id}: {landing_path}")

            except Exception as landing_err:
                # Import here to avoid circular imports
                from .heartbeat import JobCancelledException
                # Re-raise cancellation - it's not a landing page error
                if isinstance(landing_err, JobCancelledException):
                    raise
                logger.error(f"[Worker] Landing page generation failed for job {job_id}: {landing_err}")
                # Mark stage 11 as failed but don't crash the job
                try:
                    progress_callback(11, "Landing Page Generation", "failed")
                except Exception:
                    pass
        else:
            logger.info(f"[Worker] Skipping landing page generation for job {job_id} (not requested)")

        # Publish completion (always - landing page failure doesn't prevent this)
        publish_job_completed(job_id, str(job_report_path), landing_path)

        return {
            "status": "completed",
            "job_id": job_id,
            "report_path": str(job_report_path),
            "landing_path": landing_path,
        }

    except Exception as e:
        # Import here to avoid circular imports
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        # Re-raise cancellation exceptions for the queue_consumer to handle
        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] Job {job_id} cancelled by user during execution")
            raise

        # Handle quality gate stops separately - these are intentional, not errors
        if isinstance(e, QualityGateStopException):
            logger.info(f"[Worker] Job {job_id} stopped by quality gate: {e.reason}")
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            # Return None to indicate job stopped cleanly (not an error)
            return None

        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"[Worker] Job {job_id} failed: {error_msg}\n{error_traceback}")

        # Try to determine which stage failed and attach to exception
        # so queue_consumer can access it for the failure notification
        failed_stage = None
        if hasattr(flow, 'state') and flow.state:
            failed_stage = flow.state.current_stage
        e.failed_stage = failed_stage  # type: ignore

        # Re-raise - queue_consumer handles all failure notification via notify_job_failed()
        raise

    finally:
        # Clean up ChromaDB collections to prevent cross-job data leakage
        try:
            if flow is not None:
                flow.cleanup_collections()
        except Exception as cleanup_err:
            logger.debug(f"Knowledge cleanup error (non-fatal): {cleanup_err}")


def run_landing_page_only(
    job_id: str,
    report_path: str,
    page_mode: str = "coming_soon"
) -> dict:
    """
    Generate only the landing page from an existing report.

    Used when a user clicks "Generate Landing Page" on a completed job.
    The main job stays COMPLETED - this only affects landingPageStatus.

    Args:
        job_id: UUID of the job
        report_path: Path to existing report JSON
        page_mode: Landing page mode ('coming_soon' or 'full')

    Returns:
        Dict with status and landing_path
    """
    logger.info(f"[Worker] Generating landing page for job {job_id} from {report_path}")

    try:
        from nicheiq.crews.landing_page_crew import LandingPageCrew
        from nicheiq.models.research_state import FinalReport

        # Load report
        with open(report_path) as f:
            report_data = json.load(f)
        report = FinalReport(**report_data)

        # Create progress callback
        progress_callback = create_progress_callback(job_id)
        progress_callback(11, "Landing Page Generation", "running")

        # Generate landing page
        crew = LandingPageCrew()
        result = crew.generate(report, page_mode=page_mode)

        # Handle None result (guardrail failure)
        if result is None:
            logger.warning(f"[Worker] Landing page generation returned None for job {job_id}")
            progress_callback(11, "Landing Page Generation", "completed")
            # Complete without landing_path - backend will just mark landingPageStatus=COMPLETED
            publish_job_completed(job_id, report_path, None)
            return {
                "status": "completed",
                "job_id": job_id,
                "landing_path": None,
            }

        # Save to job directory
        output_dir = Path(report_path).parent
        landing_path = output_dir / "landing_page.html"
        landing_path.write_text(result.html_output)

        progress_callback(11, "Landing Page Generation", "completed")

        # Publish completion with landing_path
        publish_job_completed(job_id, report_path, str(landing_path))

        return {
            "status": "completed",
            "job_id": job_id,
            "landing_path": str(landing_path),
        }

    except Exception as e:
        logger.error(f"[Worker] Landing page generation failed for job {job_id}: {e}")
        # Attach stage 11 (Landing Page Generation) to exception for queue_consumer
        e.failed_stage = 11  # type: ignore
        # Re-raise - queue_consumer handles all failure notification via notify_job_failed()
        raise


def _solution_to_preview_dict(solution) -> dict:
    """Convert a BaseSolutionIdea or dict to a preview dict for the frontend."""
    if hasattr(solution, "model_dump"):
        d = solution.model_dump()
    elif isinstance(solution, dict):
        d = dict(solution)
    else:
        d = {"solution_name": str(solution)}

    # Normalize name field
    name = d.get("solution_name") or d.get("name", "Unknown")
    d["name"] = name
    d["solution_name"] = name
    return d


def run_interactive_research(
    job_id: str,
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None,
    generate_landing_page: bool = True,
    resume: bool = False,
) -> dict:
    """
    Interactive research task: runs Phase 1, validates solutions, waits for user selection.

    Phase 1: stages 1→5 (idea generation)
    Validation: pricing + keyword scoring per solution
    If user selects during validation → immediately continue to Phase 2
    If validation completes without selection → return awaiting_selection

    Returns:
        {"status": "completed", "report_path": str} or {"status": "awaiting_selection"}
    """
    logger.info(f"[Worker] Starting interactive research job {job_id} for niche: {niche[:100]}...")

    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.crews.landing_page_crew import LandingPageCrew
        from nicheiq.models.research_state import FinalReport

        progress_callback = create_progress_callback(job_id)

        # Initialize research flow
        flow = ResearchFlow(
            niche_description=niche,
            allowed_project_types=allowed_project_types,
            job_id=job_id,
        )
        flow.progress_callback = progress_callback

        mark_job_running(job_id)

        if not resume:
            progress_callback(1, "Niche Analysis", "running")

        # ======= PHASE 1: Run stages 1→5 (idea generation) =======
        logger.info(f"[Worker] Running Phase 1 for job {job_id} (resume={resume})")
        flow.run_with_resume(auto_resume=resume, stop_after_phase=1)

        # At this point Phase 1 (stages 1→5) is done.
        state = flow.state
        idea_gen = getattr(state, "idea_generation", None)
        if not idea_gen or not hasattr(idea_gen, "solution_ideas") or not idea_gen.solution_ideas:
            raise RuntimeError("Phase 1 did not produce solution ideas")

        solutions = idea_gen.solution_ideas
        solution_previews = [_solution_to_preview_dict(s) for s in solutions]

        # Get checkpoint path
        checkpoint_path = ""
        if flow.checkpoint_mgr and flow.checkpoint_mgr.checkpoint_folder:
            checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)

        # Notify backend: ideas ready, skip to AWAITING_SELECTION directly
        notify_ideas_ready(job_id, solution_previews, checkpoint_path, len(solutions), skip_validation=True)

        logger.info(f"[Worker] Job {job_id} entering AWAITING_SELECTION")
        return {"status": "awaiting_selection", "job_id": job_id}

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] Interactive job {job_id} cancelled by user")
            raise

        if isinstance(e, QualityGateStopException):
            logger.info(f"[Worker] Interactive job {job_id} stopped by quality gate: {e.reason}")
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            return None

        error_msg = str(e)
        logger.error(f"[Worker] Interactive job {job_id} failed: {error_msg}\n{traceback.format_exc()}")

        failed_stage = None
        if hasattr(flow, "state") and flow.state:
            failed_stage = flow.state.current_stage
        e.failed_stage = failed_stage  # type: ignore
        raise

    finally:
        try:
            if flow is not None:
                flow.cleanup_collections()
        except Exception as cleanup_err:
            logger.debug(f"Knowledge cleanup error (non-fatal): {cleanup_err}")


def _run_phase2_continuation(
    flow, job_id, selected_solutions, selection_rationale, output_dir, progress_callback, generate_landing_page
) -> dict:
    """
    Continue from Phase 1 to Phase 2 with the selected solution(s).
    Runs stages 8.55→10 and optionally stage 11 (landing page).
    """
    from nicheiq.models.research_state import FinalReport
    from nicheiq.crews.landing_page_crew import LandingPageCrew

    logger.info(f"[Worker] Running Phase 2 for job {job_id} with solutions: {selected_solutions}")

    state = flow.state
    selected_solution = selected_solutions[0]

    # Update the existing SolutionSelection with the user's choice
    rationale_text = selection_rationale if len(selection_rationale or "") >= 100 else (
        f"User selected '{selected_solution}' via interactive flow. "
        f"Rationale: {selection_rationale or 'Not provided'}. "
        "Selected after reviewing AI-generated solution ideas, "
        "pricing/keyword validation data, and competitive landscape analysis."
    )

    if state.solution_selection is not None:
        selected_set = set(selected_solutions)

        # Filter all_solution_scores to only user-selected solutions
        # (all solutions guaranteed to have entries after Phase 1 backfill)
        if state.solution_selection.all_solution_scores:
            state.solution_selection.all_solution_scores = [
                s for s in state.solution_selection.all_solution_scores
                if getattr(s, 'solution_name', '') in selected_set
            ]

        # Pick highest-scored as primary
        scores = state.solution_selection.all_solution_scores
        if scores:
            best = max(scores, key=lambda s: getattr(s, 'composite_score', 0))
            state.solution_selection.selected_solution_name = best.solution_name
        else:
            state.solution_selection.selected_solution_name = selected_solution

        # Runner-ups = other selected solutions (not primary)
        primary = state.solution_selection.selected_solution_name
        state.solution_selection.runner_up_solutions = [
            n for n in selected_solutions if n != primary
        ]
        state.solution_selection.selection_rationale = rationale_text
    else:
        # No prior selection — build minimal SolutionSelection
        from nicheiq.models.solution_selection import SolutionSelection
        state.solution_selection = SolutionSelection(
            selected_solution_name=selected_solution,
            selection_rationale=rationale_text,
            recommended_focus=f"Build and launch {selected_solution} targeting identified market gaps.",
            runner_up_solutions=[n for n in selected_solutions[1:]],
        )

    # Store user selections for downstream keyword validation guard
    state._user_selected_solutions = set(selected_solutions)

    # No bulk replay here — in the interactive flow the frontend already has
    # Phase 1 stages as green from the live run.  Phase 2 skipped stages are
    # replayed progressively inside _execute_remaining_stages(skip_bulk_replay=True).

    # Run competitive analysis for ALL selected solutions (with progress tracking)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    flow._emit_progress(5.5, "Competitive Analysis", "running")

    if len(selected_solutions) == 1:
        try:
            flow.analyze_single_solution_competitors(selected_solutions[0])
        except Exception as e:
            logger.warning(f"Competitive analysis failed for {selected_solutions[0]}: {e}")
    else:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(flow.analyze_single_solution_competitors, sol_name): sol_name
                for sol_name in selected_solutions
            }
            for future in as_completed(futures):
                sol_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.warning(f"Competitive analysis failed for {sol_name}: {e}")

    flow._emit_progress(5.5, "Competitive Analysis", "completed")

    # Ensure top_solutions_for_validation config >= len(selected_solutions)
    from nicheiq.config.settings import settings as app_settings
    app_settings.top_solutions_for_validation = max(
        app_settings.top_solutions_for_validation, len(selected_solutions)
    )

    # Continue executing remaining stages (6 → 14)
    # skip_bulk_replay=True: Phase 2 stages replay progressively (not all at once)
    report_path = flow._execute_remaining_stages(skip_bulk_replay=True)

    if not report_path or not Path(report_path).exists():
        raise RuntimeError("Phase 2 did not produce a report")

    # Copy report to job output directory
    job_report_path = output_dir / "report.json"
    with open(report_path) as src:
        report_data = json.load(src)
    with open(job_report_path, "w") as dst:
        json.dump(report_data, dst, indent=2)

    # Read final winner from state (keyword validation re-ranking may have changed it)
    final_winner = state.solution_selection.selected_solution_name if state.solution_selection else selected_solution
    publish_report_ready(job_id, str(job_report_path), winner_name=final_winner)

    landing_path = None
    if generate_landing_page:
        try:
            progress_callback(11, "Landing Page Generation", "running")
            report = FinalReport(**report_data)
            crew = LandingPageCrew()
            result = crew.generate(report, page_mode="coming_soon")
            if result is not None:
                job_landing_path = output_dir / "landing_page.html"
                job_landing_path.write_text(result.html_output)
                landing_path = str(job_landing_path)
            progress_callback(11, "Landing Page Generation", "completed")
        except Exception as landing_err:
            from .heartbeat import JobCancelledException
            if isinstance(landing_err, JobCancelledException):
                raise
            logger.error(f"[Worker] Landing page failed for job {job_id}: {landing_err}")
            try:
                progress_callback(11, "Landing Page Generation", "failed")
            except Exception:
                pass

    publish_job_completed(job_id, str(job_report_path), landing_path)

    return {
        "status": "completed",
        "job_id": job_id,
        "report_path": str(job_report_path),
        "landing_path": landing_path,
    }


def run_research_phase2(
    job_id: str,
    checkpoint_path: str,
    selected_solutions: list[str] = None,
    selected_solution: str = "",
    selection_rationale: str = "",
    generate_landing_page: bool = True,
) -> dict:
    """
    Phase 2 task: runs deep investigation for user-selected solution(s).
    Loaded from checkpoint, runs stages 8.55→10 + optional landing page.

    Supports multi-select via selected_solutions list, with backward compat
    via selected_solution string.
    """
    solutions = selected_solutions or ([selected_solution] if selected_solution else [])
    if not solutions:
        raise RuntimeError("No solution selected for Phase 2")
    primary_solution = solutions[0]

    logger.info(f"[Worker] Starting Phase 2 for job {job_id}, solutions: {solutions}")

    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow

        progress_callback = create_progress_callback(job_id)

        # Create flow and load from checkpoint
        flow = ResearchFlow(
            niche_description="",  # Will be loaded from checkpoint
            job_id=job_id,
        )
        flow.progress_callback = progress_callback

        mark_job_running(job_id)

        # Load checkpoint
        loaded = flow.resume_from_checkpoint(checkpoint_path)
        if not loaded:
            raise RuntimeError(f"Failed to load checkpoint from {checkpoint_path}")

        return _run_phase2_continuation(
            flow, job_id, solutions, selection_rationale,
            output_dir, progress_callback, generate_landing_page
        )

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            raise

        if isinstance(e, QualityGateStopException):
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            return None

        logger.error(f"[Worker] Phase 2 failed for job {job_id}: {e}\n{traceback.format_exc()}")
        failed_stage = None
        if hasattr(flow, "state") and flow.state:
            failed_stage = flow.state.current_stage
        e.failed_stage = failed_stage  # type: ignore
        raise

    finally:
        try:
            if flow is not None:
                flow.cleanup_collections()
        except Exception as cleanup_err:
            logger.debug(f"Knowledge cleanup error (non-fatal): {cleanup_err}")


def run_regenerate_ideas(
    job_id: str,
    checkpoint_path: str,
    existing_solution_names: list[str],
    niche: str,
) -> dict:
    """
    Regeneration task: generates new solution ideas avoiding existing names.
    Loaded from checkpoint, runs solution crew with exclusion list.
    """
    logger.info(f"[Worker] Regenerating ideas for job {job_id}, excluding: {existing_solution_names}")

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow

        progress_callback = create_progress_callback(job_id)

        # Create flow and load from checkpoint
        flow = ResearchFlow(
            niche_description=niche,
            job_id=job_id,
        )
        flow.progress_callback = progress_callback

        # Load checkpoint
        loaded = flow.resume_from_checkpoint(checkpoint_path)
        if not loaded:
            raise RuntimeError(f"Failed to load checkpoint from {checkpoint_path}")

        # Re-run the solution generation stage with exclusion list
        state = flow.state
        progress_callback(5, "Solution Pipeline", "running")

        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

        pain_points = getattr(state, "pain_point_analysis", None)
        social_content = getattr(state, "social_content", None)
        niche_context = getattr(state, "niche_context", None)
        audience = getattr(state, "audience_mapping", None)

        crew = UnifiedSolutionCrew(
            pain_point_analysis=pain_points,
            social_content=social_content,
            allowed_project_types=flow.allowed_project_types,
            niche_context=niche_context,
            audience_mapping=audience,
            checkpoint_mgr=flow.checkpoint_mgr,
            job_id=job_id,
        )

        # Execute pipeline (will generate new ideas)
        # The crew doesn't have a built-in exclusion mechanism,
        # so we'll filter out existing names from the results
        result = crew.execute_pipeline()
        idea_gen = result[0]  # IdeaGenerationResult

        if not idea_gen or not hasattr(idea_gen, "solution_ideas"):
            raise RuntimeError("Regeneration did not produce solution ideas")

        # Filter out solutions with names matching existing ones
        new_solutions = [
            s for s in idea_gen.solution_ideas
            if (getattr(s, "solution_name", "") not in existing_solution_names
                and getattr(s, "name", "") not in existing_solution_names)
        ]

        if not new_solutions:
            # If all were duplicates, keep them anyway (best effort)
            new_solutions = idea_gen.solution_ideas

        # Merge old (loaded from checkpoint) + new solutions so future
        # validate/analyze finds solutions from ALL batches
        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            old_solutions = list(state.idea_generation.solution_ideas)
        else:
            old_solutions = []
        merged_solutions = old_solutions + list(new_solutions)
        logger.info(
            f"Merged solutions: {len(old_solutions)} existing + {len(new_solutions)} new = {len(merged_solutions)} total"
        )

        # Update state in-place and re-save checkpoint
        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            state.idea_generation.solution_ideas = merged_solutions
        if flow.checkpoint_mgr and state.idea_generation:
            flow.checkpoint_mgr.save_stage("stage_5_3_refinement", state.idea_generation)

        # Send only NEW previews — backend appends to existing list
        new_previews = [_solution_to_preview_dict(s) for s in new_solutions]

        progress_callback(5, "Solution Pipeline", "completed")

        # Notify backend with new solutions
        notify_regeneration_complete(job_id, new_previews)

        return {"status": "regenerated", "job_id": job_id, "new_count": len(new_previews)}

    except Exception as e:
        from .heartbeat import JobCancelledException

        if isinstance(e, JobCancelledException):
            raise

        logger.error(f"[Worker] Regeneration failed for job {job_id}: {e}\n{traceback.format_exc()}")
        e.failed_stage = 7  # type: ignore
        raise

    finally:
        try:
            if flow is not None:
                flow.cleanup_collections()
        except Exception as cleanup_err:
            logger.debug(f"Knowledge cleanup error (non-fatal): {cleanup_err}")
