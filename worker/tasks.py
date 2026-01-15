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
    publish_job_failed,
    publish_progress,
)
from .status import mark_job_running


def run_research_job(
    job_id: str,
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None
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
        )

        # Attach progress callback to flow
        flow.progress_callback = progress_callback

        # Update job status to RUNNING in database (race-condition safe)
        # This ensures status is updated even if SSE connection isn't established yet
        mark_job_running(job_id)

        # Publish "job started" event for SSE clients
        progress_callback(1, "Niche Analysis", "running")

        # Run the research pipeline (no resume for web jobs)
        logger.info(f"[Worker] Running research pipeline for job {job_id}")
        report_path = flow.run_with_resume(auto_resume=False)

        if not report_path or not Path(report_path).exists():
            raise RuntimeError("Research flow did not produce a report")

        logger.info(f"[Worker] Research complete for job {job_id}: {report_path}")

        # Copy report to job output directory
        job_report_path = output_dir / "report.json"
        with open(report_path) as src:
            report_data = json.load(src)
        with open(job_report_path, "w") as dst:
            json.dump(report_data, dst, indent=2)

        # Generate landing page
        logger.info(f"[Worker] Generating landing page for job {job_id}")
        progress_callback(11, "Landing Page Generation", "running")

        # Load report for landing page generation
        report = FinalReport(**report_data)

        # Generate landing page
        crew = LandingPageCrew()
        result = crew.generate(report, page_mode="coming_soon")

        # Save landing page
        job_landing_path = output_dir / "landing_page.html"
        job_landing_path.write_text(result.html_output)
        landing_path = str(job_landing_path)

        progress_callback(11, "Landing Page Generation", "completed")
        logger.info(f"[Worker] Landing page generated for job {job_id}: {landing_path}")

        # Publish completion
        publish_job_completed(job_id, str(job_report_path), landing_path)

        return {
            "status": "completed",
            "job_id": job_id,
            "report_path": str(job_report_path),
            "landing_path": landing_path,
        }

    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"[Worker] Job {job_id} failed: {error_msg}\n{error_traceback}")

        # Try to determine which stage failed
        failed_stage = None
        if hasattr(flow, 'state') and flow.state:
            failed_stage = flow.state.current_stage

        # Publish failure
        publish_job_failed(job_id, error_msg, failed_stage)

        # Re-raise for RQ to mark as failed
        raise


def run_landing_page_only(
    job_id: str,
    report_path: str,
    page_mode: str = "coming_soon"
) -> dict:
    """
    Generate only the landing page from an existing report.

    Useful for regenerating landing pages with different settings.

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

        # Save to job directory
        output_dir = Path(report_path).parent
        landing_path = output_dir / "landing_page.html"
        landing_path.write_text(result.html_output)

        progress_callback(11, "Landing Page Generation", "completed")

        return {
            "status": "completed",
            "job_id": job_id,
            "landing_path": str(landing_path),
        }

    except Exception as e:
        logger.error(f"[Worker] Landing page generation failed for job {job_id}: {e}")
        publish_job_failed(job_id, str(e), 11)
        raise
