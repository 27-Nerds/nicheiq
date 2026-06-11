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

from nicheiq.config.settings import settings

from .progress import (
    create_progress_callback,
    publish_job_completed,
    publish_report_ready,
    notify_job_quality_gate_stop,
    notify_ideas_ready,
    notify_regeneration_complete,
    notify_catalog_pain_points_ready,
    notify_catalog_ideas_ready,
)
from .status import mark_job_running


def run_research_job(
    job_id: str,
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None,
    resume: bool = False,
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

        # Publish completion (landing pages are on-demand only)
        publish_job_completed(job_id, str(job_report_path), None)

        return {
            "status": "completed",
            "job_id": job_id,
            "report_path": str(job_report_path),
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
        progress_callback(15, "Landing Page Generation", "running")

        # Generate landing page
        crew = LandingPageCrew()
        result = crew.generate(report, page_mode=page_mode)

        # Handle None result (guardrail failure)
        if result is None:
            logger.warning(f"[Worker] Landing page generation returned None for job {job_id}")
            progress_callback(15, "Landing Page Generation", "completed")
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

        progress_callback(15, "Landing Page Generation", "completed")

        # Publish completion with landing_path
        publish_job_completed(job_id, report_path, str(landing_path))

        return {
            "status": "completed",
            "job_id": job_id,
            "landing_path": str(landing_path),
        }

    except Exception as e:
        logger.error(f"[Worker] Landing page generation failed for job {job_id}: {e}")
        # Attach stage 15 (Landing Page Generation) to exception for queue_consumer
        e.failed_stage = 15  # type: ignore
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
    resume: bool = False,
    entry_mode: Optional[str] = None,
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

        progress_callback = create_progress_callback(job_id)

        # Initialize research flow
        flow = ResearchFlow(
            niche_description=niche,
            allowed_project_types=allowed_project_types,
            job_id=job_id,
            entry_mode=entry_mode,
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

        # Materialize discovery data for frontend evidence UI
        discovery_data_path = ""
        preview_report_path = ""
        output_dir = str(settings.checkpoint_dir)
        try:
            result = flow._materialize_discovery_data(output_dir)
            if result:
                discovery_data_path = result
                logger.info(f"[Worker] Discovery data materialized: {discovery_data_path}")
        except Exception as e:
            logger.warning(f"[Worker] Failed to materialize discovery data: {e}")

        # Materialize preview report for frontend preview page
        try:
            result = flow._materialize_preview_report(output_dir)
            if result:
                preview_report_path = result
                logger.info(f"[Worker] Preview report materialized: {preview_report_path}")
        except Exception as e:
            logger.warning(f"[Worker] Failed to materialize preview report: {e}")

        # Notify backend: ideas ready, skip to AWAITING_SELECTION directly
        notify_ideas_ready(job_id, solution_previews, checkpoint_path, len(solutions), skip_validation=True, discovery_data_path=discovery_data_path, preview_report_path=preview_report_path)

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
    flow, job_id, selected_solutions, selection_rationale, output_dir, progress_callback
) -> dict:
    """
    Continue from Phase 1 to Phase 2 with the selected solution(s).
    Runs stages 8.55→10 and optionally stage 11 (landing page).
    """
    from nicheiq.models.research_state import FinalReport

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
        state.solution_selection.selected_solution_name = selected_solution
        state.solution_selection.runner_up_solutions = [n for n in selected_solutions if n != selected_solution]
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

    # Validate selected solution exists in merged ideas
    if state.idea_generation and state.idea_generation.solution_ideas:
        names = {s.solution_name for s in state.idea_generation.solution_ideas}
        if selected_solution not in names:
            logger.error(f"Selected solution '{selected_solution}' not found in solution_ideas. Available: {names}")

    # Compute all_solution_scores from Task 3 fields, then filter to selected solutions
    from nicheiq.utils.score_helpers import compute_solution_scores
    if state.idea_generation and state.idea_generation.solution_ideas:
        all_scores = compute_solution_scores(state.idea_generation.solution_ideas)
        # Keep only selected solutions' scores (stages 7-8 use top N from this list)
        selected_set = set(selected_solutions)
        state.solution_selection.all_solution_scores = [
            s for s in all_scores if s.solution_name in selected_set
        ]
        # Re-rank filtered list
        for i, s in enumerate(
            sorted(state.solution_selection.all_solution_scores, key=lambda x: x.composite_score, reverse=True), 1
        ):
            s.rank = i

    # Store user selections for downstream keyword validation guard
    state._user_selected_solutions = set(selected_solutions)

    # Save scoring checkpoint so _execute_remaining_stages sees it
    flow.checkpoint_mgr.save_stage("stage_5_6_selection", state.solution_selection)

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

    # Publish completion (landing pages are on-demand only)
    publish_job_completed(job_id, str(job_report_path), None)

    return {
        "status": "completed",
        "job_id": job_id,
        "report_path": str(job_report_path),
    }


def run_research_phase2(
    job_id: str,
    checkpoint_path: str,
    selected_solutions: list[str] = None,
    selected_solution: str = "",
    selection_rationale: str = "",
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
            output_dir, progress_callback
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


def run_catalog_pain_research(
    job_id: str,
    pain_seeds: list[dict],
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None,
) -> dict:
    """
    Catalog "pain research" (single or remix): seed Phase-1 discovery with 1-5
    catalog pain points, skip stages 1-4, run stage 5 only, land awaiting-selection.
    The user then selects + pays for deep research via the existing select-solution path.
    """
    logger.info(f"[Worker] Starting catalog pain research job {job_id} ({len(pain_seeds)} pain(s))")

    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.flows.catalog_seed import build_pain_seed_state, sanitize_label

        progress_callback = create_progress_callback(job_id)
        # The label arrives built from raw catalog titles — sanitize before it
        # feeds crew inputs (the DB display label stays raw on the backend).
        niche = sanitize_label(niche) or "Catalog research"
        flow = ResearchFlow(
            niche_description=niche,
            allowed_project_types=allowed_project_types,
            job_id=job_id,
            entry_mode="pain_research",
        )
        flow.progress_callback = progress_callback
        mark_job_running(job_id)

        # Seed niche_context + pain_point_analysis; persist as checkpoints so the
        # flow treats stages 1-4 as done, then emit SKIPPED progress for them.
        niche_context, pain_point_analysis = build_pain_seed_state(pain_seeds, niche)
        if len(pain_seeds) > 1:
            # Remix: replace the template context with an LLM-synthesized
            # cross-niche market definition; the template stays on any failure.
            try:
                from nicheiq.flows.seed_enrichment import synthesize_remix_niche_context

                niche_context, usage = synthesize_remix_niche_context(pain_seeds, niche)
                try:
                    if getattr(flow, "cost_tracker", None):
                        flow.cost_tracker.record_llm_usage(
                            "Remix - Niche Context Synthesis", usage.to_dict()
                        )
                except Exception:
                    pass  # cost bookkeeping must not discard a successful synthesis
                logger.info(f"[Worker] Remix niche context synthesized for job {job_id}")
            except Exception as e:
                logger.warning(
                    f"[Worker] Remix niche-context synthesis failed, keeping template: {e}"
                )
        flow.state.niche_context = niche_context
        flow.state.pain_point_analysis = pain_point_analysis
        # Set BEFORE the first save_stage so it persists to checkpoint metadata and
        # survives into the Phase-2 report (transparency badge).
        flow.state.seeded_from_catalog = True
        flow.checkpoint_mgr.save_stage("stage_1_niche_context", niche_context)
        flow.checkpoint_mgr.save_stage("stage_3_pain_points", pain_point_analysis)
        for num, label in [
            (1, "Niche Validation"),
            (2, "Search & Discovery"),
            (3, "Pain Point Analysis"),
            (4, "Audience Mapping"),
        ]:
            flow._skip_stage(num, label, "Seeded from catalog")
        flow.state.current_stage = 5

        # Best-effort live-evidence enrichment (HN): populates social_content +
        # the stage_2 checkpoint so stage 5 / Phase 2 don't run evidence-blind.
        from nicheiq.flows.seed_enrichment import maybe_enrich_seed
        from .heartbeat import check_cancellation

        maybe_enrich_seed(
            flow,
            [p.title for p in pain_point_analysis.pain_points],
            niche_context.niche_description,
            cancel_check=check_cancellation,
        )

        # Run ONLY stage 5 (solution pipeline), then stop (interactive).
        flow._execute_remaining_stages(stop_after_phase=1)

        state = flow.state
        idea_gen = getattr(state, "idea_generation", None)
        if not idea_gen or not getattr(idea_gen, "solution_ideas", None):
            raise RuntimeError("Pain research did not produce solution ideas")
        solutions = idea_gen.solution_ideas
        solution_previews = [_solution_to_preview_dict(s) for s in solutions]

        checkpoint_path = ""
        if flow.checkpoint_mgr and flow.checkpoint_mgr.checkpoint_folder:
            checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)

        materialize_dir = str(settings.checkpoint_dir)
        discovery_data_path = ""
        preview_report_path = ""
        try:
            r = flow._materialize_discovery_data(materialize_dir)
            if r:
                discovery_data_path = r
        except Exception as e:
            logger.warning(f"[Worker] Failed to materialize discovery data: {e}")
        try:
            r = flow._materialize_preview_report(materialize_dir)
            if r:
                preview_report_path = r
        except Exception as e:
            logger.warning(f"[Worker] Failed to materialize preview report: {e}")

        notify_ideas_ready(
            job_id,
            solution_previews,
            checkpoint_path,
            len(solutions),
            skip_validation=True,
            discovery_data_path=discovery_data_path,
            preview_report_path=preview_report_path,
        )
        logger.info(f"[Worker] Pain research job {job_id} entering AWAITING_SELECTION")
        return {"status": "awaiting_selection", "job_id": job_id}

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            raise
        if isinstance(e, QualityGateStopException):
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            return None

        logger.error(f"[Worker] Pain research job {job_id} failed: {e}\n{traceback.format_exc()}")
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


def run_catalog_deep_research(
    job_id: str,
    idea_seed: dict,
    niche: str,
    user_id: Optional[str] = None,
) -> dict:
    """
    Catalog "deep research on an idea": seed a solution from a catalog idea, skip
    stages 1-5, run Phase 2 (5.5 Competitive Analysis -> 14) in one shot, produce
    an owned report.
    """
    logger.info(f"[Worker] Starting catalog deep research job {job_id} for niche: {niche[:100]}...")

    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.flows.catalog_seed import build_idea_seed_state, sanitize_label

        progress_callback = create_progress_callback(job_id)
        # The label arrives built from the raw catalog headline — sanitize before
        # it feeds crew inputs (the DB display label stays raw on the backend).
        niche = sanitize_label(niche) or "Catalog research"
        flow = ResearchFlow(
            niche_description=niche,
            job_id=job_id,
            entry_mode="deep_idea",
        )
        flow.progress_callback = progress_callback
        mark_job_running(job_id)

        niche_context, idea_generation, solution_selection, pain_point_analysis = build_idea_seed_state(
            idea_seed, niche
        )
        flow.state.niche_context = niche_context
        flow.state.idea_generation = idea_generation
        flow.state.solution_selection = solution_selection
        flow.state.pain_point_analysis = pain_point_analysis
        # Guard for downstream keyword-validation (mirrors _run_phase2_continuation).
        flow.state._user_selected_solutions = {solution_selection.selected_solution_name}
        # Set before save_stage so report_generator emits the transparency badge.
        flow.state.seeded_from_catalog = True

        # Persist seeded artifacts so the flow treats stages 1-5 as done.
        flow.checkpoint_mgr.save_stage("stage_1_niche_context", niche_context)
        flow.checkpoint_mgr.save_stage("stage_3_pain_points", pain_point_analysis)
        flow.checkpoint_mgr.save_stage("stage_5_6_selection", solution_selection)
        for num, label in [
            (1, "Niche Validation"),
            (2, "Search & Discovery"),
            (3, "Pain Point Analysis"),
            (4, "Audience Mapping"),
            (5, "Solution Pipeline"),
        ]:
            flow._skip_stage(num, label, "Seeded from catalog idea")
        # current_stage is an int; the 5.5 competitive analysis auto-runs because
        # solution_selection is seeded (gated by solution presence, not stage number).
        flow.state.current_stage = 6

        # Best-effort live-evidence enrichment (HN). Queries lead with the
        # solution name + headline — the addressed-pain titles are symptom
        # phrases that search poorly on their own.
        from nicheiq.flows.seed_enrichment import maybe_enrich_seed
        from .heartbeat import check_cancellation

        enrich_candidates = [
            solution_selection.selected_solution_name,
            str(idea_seed.get("headline") or ""),
            *[str(t) for t in (idea_seed.get("addressed_pain_titles") or [])[:2]],
        ]
        maybe_enrich_seed(
            flow,
            enrich_candidates,
            niche_context.niche_description,
            cancel_check=check_cancellation,
        )

        report_path = flow._execute_remaining_stages(skip_bulk_replay=True)
        if not report_path or not Path(report_path).exists():
            raise RuntimeError("Deep research did not produce a report")

        job_report_path = output_dir / "report.json"
        with open(report_path) as src:
            report_data = json.load(src)
        # seeded_from_catalog is set on the report by report_generator (state flag),
        # so no manual injection here — single source of truth.
        with open(job_report_path, "w") as dst:
            json.dump(report_data, dst, indent=2)

        final_winner = (
            flow.state.solution_selection.selected_solution_name
            if flow.state.solution_selection
            else solution_selection.selected_solution_name
        )
        publish_report_ready(job_id, str(job_report_path), winner_name=final_winner)
        publish_job_completed(job_id, str(job_report_path), None)

        return {"status": "completed", "job_id": job_id, "report_path": str(job_report_path)}

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            raise
        if isinstance(e, QualityGateStopException):
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            return None

        logger.error(f"[Worker] Deep research job {job_id} failed: {e}\n{traceback.format_exc()}")
        failed_stage = None
        if hasattr(flow, "state") and flow.state:
            failed_stage = flow.state.current_stage
        # A deep_idea job only ever charged 'deep_research'. current_stage defaults
        # to 1 until the seed block finishes, and a stage <= 5 makes the backend
        # resolve the refund to 'discovery' — a charge this job never made, so the
        # refund would silently no-op and the user would keep paying 15 credits
        # for a failed job. Floor to Phase 2 so the refund maps to 'deep_research'.
        if failed_stage is not None and failed_stage <= 5:
            failed_stage = 6
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

        # Build existing_ideas list for prompt-level blacklisting
        # Enrich with descriptions and project_type from checkpoint state when available
        idea_lookup: dict[str, dict] = {}
        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            for s in state.idea_generation.solution_ideas:
                name = getattr(s, "solution_name", "")
                if name:
                    idea_lookup[name.lower()] = {
                        "description": getattr(s, "description", ""),
                        "project_type": getattr(s, "project_type", ""),
                    }
        existing_ideas_for_crew = [
            {
                "name": n,
                "description": idea_lookup.get(n.lower(), {}).get("description", ""),
                "project_type": idea_lookup.get(n.lower(), {}).get("project_type", ""),
            }
            for n in existing_solution_names
        ]

        competitor_mentions = getattr(state, "competitor_mentions_formatted", None)

        crew = UnifiedSolutionCrew(
            pain_point_analysis=pain_points,
            social_content=social_content,
            allowed_project_types=flow.allowed_project_types,
            niche_context=niche_context,
            audience_mapping=audience,
            checkpoint_mgr=flow.checkpoint_mgr,
            job_id=job_id,
            existing_ideas=existing_ideas_for_crew,
            competitor_mentions_text=competitor_mentions,
        )

        # Execute pipeline with skip_selection=True (no Task 4 needed for regeneration)
        result = crew.execute_pipeline(skip_selection=True)
        idea_gen = result[0]  # IdeaGenerationResult (result[1] is None)

        if not idea_gen or not hasattr(idea_gen, "solution_ideas"):
            raise RuntimeError("Regeneration did not produce solution ideas")

        # Post-hoc safety-net: filter out solutions with names matching existing ones (case-insensitive)
        existing_names_lower = {n.lower() for n in existing_solution_names}
        new_solutions = [
            s for s in idea_gen.solution_ideas
            if (getattr(s, "solution_name", "").lower() not in existing_names_lower
                and getattr(s, "name", "").lower() not in existing_names_lower)
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


def run_catalog_pain_points(
    job_id: str,
    category_id: str,
    category_name: str,
    category_description: str,
    parent_category_name: str = "",
) -> dict:
    """
    Generate pain points for a catalog category using the research pipeline.

    Runs stages 1-3 (niche validation, social scraping, pain point analysis)
    and sends results to backend for merge/dedup into CatalogPainPoint records.

    Args:
        job_id: UUID of the tracking job
        category_id: UUID of the catalog category
        category_name: Category name (used to build niche)
        category_description: Category description (used to build niche)
        parent_category_name: Parent category name for hierarchy context

    Returns:
        Dict with status and pain point count
    """
    if parent_category_name:
        niche = f"{parent_category_name} > {category_name}: {category_description}" if category_description else f"{parent_category_name} > {category_name}"
    else:
        niche = f"{category_name}: {category_description}" if category_description else category_name
    logger.info(f"[Worker] Generating catalog pain points for job {job_id}, category: {category_name}")

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow

        progress_callback = create_progress_callback(job_id)

        flow = ResearchFlow(
            niche_description=niche,
            job_id=job_id,
        )
        flow.progress_callback = progress_callback

        mark_job_running(job_id)
        progress_callback(1, "Niche Analysis", "running")

        # Stage 1: Validate niche / generate NicheContext
        flow.stage_1_validate_niche()

        # Stage 2: Social scraping (Reddit/Twitter)
        flow.stage_2_search_and_discover()

        # Stage 3: Pain point analysis (PainPointCrew + AudienceMappingCrew)
        flow.stage_3_analyze_pain_points()

        # Phase 5.4 — materialize preview report BEFORE the no-pain-points
        # early-return. Backend projection layer reads this asset to populate
        # CatalogResearchContext. Load-bearing: if materialization fails, we
        # raise so RQ retries the job.
        output_dir = os.path.join("output", "jobs", job_id)
        os.makedirs(output_dir, exist_ok=True)
        try:
            preview_path = flow._materialize_preview_report(output_dir)
        except Exception as mat_err:
            logger.error(
                f"[Worker] Preview materialization raised for job {job_id}: {mat_err}\n"
                f"{traceback.format_exc()}"
            )
            raise RuntimeError(
                f"[Worker] Preview report materialization failed for job {job_id}; "
                f"aborting so RQ retries"
            ) from mat_err
        if not preview_path:
            raise RuntimeError(
                f"[Worker] Preview report materialization returned None for job {job_id}; "
                f"aborting so RQ retries"
            )

        # Extract pain points
        state = flow.state
        pain_analysis = getattr(state, "pain_point_analysis", None)
        if not pain_analysis or not pain_analysis.pain_points:
            logger.warning(f"[Worker] No pain points generated for job {job_id}")
            notify_catalog_pain_points_ready(
                job_id, category_id, [], niche, preview_report_path=preview_path
            )
            return {"status": "completed", "job_id": job_id, "pain_point_count": 0}

        # Serialize pain points
        pain_point_dicts = []
        for pp in pain_analysis.pain_points:
            d = pp.model_dump()
            # Convert enum to string value
            if hasattr(d.get("opportunity_level"), "value"):
                d["opportunity_level"] = d["opportunity_level"].value
            pain_point_dicts.append(d)

        # Notify backend
        notify_catalog_pain_points_ready(
            job_id, category_id, pain_point_dicts, niche, preview_report_path=preview_path
        )

        logger.info(f"[Worker] Catalog pain points complete for job {job_id}: {len(pain_point_dicts)} pain points")
        return {"status": "completed", "job_id": job_id, "pain_point_count": len(pain_point_dicts)}

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] Catalog pain points job {job_id} cancelled")
            raise

        if isinstance(e, QualityGateStopException):
            logger.info(f"[Worker] Catalog pain points job {job_id} stopped by quality gate: {e.reason}")
            notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            return None

        logger.error(f"[Worker] Catalog pain points job {job_id} failed: {e}\n{traceback.format_exc()}")
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


def run_catalog_ideas(
    job_id: str,
    category_id: str,
    pain_points: list[dict],
    niche: str,
    parent_category_name: str = "",
    existing_ideas: list[dict[str, str]] | None = None,
    parent_source_job_id: str | None = None,
    content_categorization: dict | None = None,
) -> dict:
    """
    Generate solution ideas from admin-selected pain points for a catalog category.

    Reconstructs PainPoint objects and runs UnifiedSolutionCrew to generate ideas.

    Args:
        job_id: UUID of the tracking job
        category_id: UUID of the catalog category
        pain_points: List of pain point dicts (camelCase from DB)
        niche: The niche description
        parent_category_name: Parent category name for hierarchy context
        existing_ideas: Optional list of dicts with "name" and "description" keys
            for previously generated ideas to avoid duplicating
        parent_source_job_id: Phase 5.4 — sourceJobId of the pain-points-job
            the ideas were generated from. Forwarded to backend so generated
            ideas FK into the same CatalogResearchContext row as the pain
            points. None for legacy callers (ideas use their own job_id).

    Returns:
        Dict with status and idea count
    """
    if parent_category_name:
        niche = f"{parent_category_name} > {niche}"
    logger.info(f"[Worker] Generating catalog ideas for job {job_id} from {len(pain_points)} pain points")

    try:
        from nicheiq.models.pain_point import (
            ContentCategorizationReport,
            PainPoint,
            PainPointAnalysisResult,
        )
        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew

        progress_callback = create_progress_callback(job_id)
        mark_job_running(job_id)
        progress_callback(5, "Solution Pipeline", "running")

        # Reconstruct PainPoint objects from camelCase DB fields
        reconstructed = []
        for pp_data in pain_points:
            reconstructed.append(PainPoint(
                title=pp_data.get("title", ""),
                description=pp_data.get("description", ""),
                mention_count=pp_data.get("mentionCount", pp_data.get("mention_count", 0)),
                severity_score=pp_data.get("severityScore", pp_data.get("severity_score", 0.5)),
                willingness_to_pay=pp_data.get("willingnessToPayScore", pp_data.get("willingness_to_pay", 0.5)),
                opportunity_level=pp_data.get("opportunityLevel", pp_data.get("opportunity_level", "medium")),
                representative_quotes=pp_data.get("representativeQuotes", pp_data.get("representative_quotes", [])) or [],
                source_platforms=pp_data.get("sourcePlatforms", pp_data.get("source_platforms")) or [],
                categories=pp_data.get("categories") or [],
                affected_segments=pp_data.get("affectedSegments", pp_data.get("affected_segments")) or [],
            ))

        # Rehydrate ContentCategorizationReport from the pain-points-job's
        # research context, if present. UnifiedSolutionCrew uses themes +
        # user_segments to sharpen segment targeting. min_length validators
        # may reject older payloads — degrade silently instead of failing.
        content_cat = None
        if content_categorization:
            try:
                content_cat = ContentCategorizationReport.model_validate(content_categorization)
            except Exception as e:
                logger.warning(
                    f"[Worker] Failed to rehydrate content_categorization for job {job_id}: {e}"
                )

        # Build PainPointAnalysisResult
        total_mentions = sum(pp.mention_count for pp in reconstructed)
        pain_analysis = PainPointAnalysisResult(
            niche=niche,
            pain_points=reconstructed,
            total_mentions=total_mentions,
            top_categories=[],
            analysis_summary=f"Catalog pain point analysis for {niche}",
            content_categorization=content_cat,
        )

        # Create UnifiedSolutionCrew with pain points and existing ideas blacklist
        crew = UnifiedSolutionCrew(
            pain_point_analysis=pain_analysis,
            social_content=None,
            niche_context=None,
            audience_mapping=None,
            job_id=job_id,
            existing_ideas=existing_ideas,
        )

        # Execute pipeline (skip_selection=True → no Task 4)
        result = crew.execute_pipeline(skip_selection=True)
        idea_gen = result[0]  # IdeaGenerationResult

        if not idea_gen or not hasattr(idea_gen, "solution_ideas"):
            logger.warning(f"[Worker] No ideas generated for job {job_id}")
            notify_catalog_ideas_ready(
                job_id, category_id, [], niche,
                parent_source_job_id=parent_source_job_id,
            )
            return {"status": "completed", "job_id": job_id, "idea_count": 0}

        # Post-hoc safety-net: structural dedup against existing catalog ideas.
        # Exact-name matching alone let RENAMED structural duplicates through —
        # the precise threat for a regeneration feature (the crew blacklist is
        # prompt-only and the backend insert dedup is exact-name too).
        if existing_ideas:
            from nicheiq.utils.validation.crew_guardrails import detect_catalog_duplicate

            filtered = []
            duplicates: list[str] = []
            for s in idea_gen.solution_ideas:
                match = next(
                    (i for i in existing_ideas if detect_catalog_duplicate(s, i)),
                    None,
                )
                if match is None:
                    filtered.append(s)
                else:
                    duplicates.append(
                        f"{getattr(s, 'solution_name', '?')} ~ {match.get('name', '?')}"
                    )
            if duplicates:
                logger.info(
                    f"[Worker] Structural dedup: {len(idea_gen.solution_ideas)} → {len(filtered)} ideas "
                    f"(removed: {'; '.join(duplicates)})"
                )
            if not filtered:
                # Surface the honest outcome instead of silently keeping
                # duplicates (the backend would re-dedup them to created=0 anyway)
                logger.warning(
                    f"[Worker] Regeneration produced only structural duplicates of existing "
                    f"catalog ideas for job {job_id} — returning no new ideas."
                )
                notify_catalog_ideas_ready(
                    job_id, category_id, [], niche,
                    parent_source_job_id=parent_source_job_id,
                )
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "idea_count": 0,
                    "note": "regeneration produced only duplicates of existing ideas",
                }
            idea_gen.solution_ideas = filtered

        # Serialize ideas
        idea_previews = [_solution_to_preview_dict(s) for s in idea_gen.solution_ideas]

        progress_callback(5, "Solution Pipeline", "completed")

        # Notify backend
        notify_catalog_ideas_ready(
            job_id, category_id, idea_previews, niche,
            parent_source_job_id=parent_source_job_id,
        )

        logger.info(f"[Worker] Catalog ideas complete for job {job_id}: {len(idea_previews)} ideas")
        return {"status": "completed", "job_id": job_id, "idea_count": len(idea_previews)}

    except Exception as e:
        from .heartbeat import JobCancelledException

        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] Catalog ideas job {job_id} cancelled")
            raise

        logger.error(f"[Worker] Catalog ideas job {job_id} failed: {e}\n{traceback.format_exc()}")
        e.failed_stage = 5  # type: ignore
        raise
