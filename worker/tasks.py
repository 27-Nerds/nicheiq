"""
RQ Task definitions for NicheIQ research jobs.

These tasks are enqueued by the Node.js backend and processed by RQ workers.
"""

import hmac
import json
import os
import re
import traceback
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
    notify_gate_reached,
    notify_gate_failed,
    notify_seed_complete,
)
from .status import mark_job_running


def _resolve_cost_summary(flow) -> Optional[dict]:
    """Return the run's LLM cost breakdown for the admin pricing view.

    Prefers the finalized state.cost_summary (set at Stage 14); falls back to the live
    tracker so cost is still reported if finalization didn't stamp state.
    """
    summary = getattr(getattr(flow, "state", None), "cost_summary", None)
    if not summary and getattr(flow, "cost_tracker", None):
        summary = flow.cost_tracker.get_summary()
    return summary or None


def _canonical_solution_snapshot(solutions: list) -> str:
    """Stable full-model snapshot used to enforce append-only batch semantics."""
    rows = []
    for solution in solutions:
        if hasattr(solution, "model_dump"):
            rows.append(solution.model_dump(mode="json"))
        elif isinstance(solution, dict):
            rows.append(dict(solution))
        else:
            rows.append(str(solution))
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)


def _ensure_phase1_identities(flow, job_id: str) -> None:
    """Stamp and persist any Phase-1 records missed by an older generation path."""
    state = flow.state
    idea_gen = getattr(state, "idea_generation", None)
    ideas = list(getattr(idea_gen, "solution_ideas", None) or [])
    findings = list(getattr(state, "idea_ruled_out", None) or [])
    needs_save = any(
        not getattr(idea, "identity_origin", None)
        or not getattr(idea, "idea_id", None)
        for idea in ideas
    ) or any(
        not finding.get("finding_id") or not finding.get("idea_id")
        for finding in findings
    )
    if not needs_save:
        return

    from nicheiq.utils.idea_identity import (
        link_legacy_findings_to_ideas,
        stamp_new_idea_identities,
        stamp_ruled_out_findings,
    )

    stamp_new_idea_identities(
        job_id,
        ideas,
        origin="phase1",
        operation_key="initial",
        force=True,
        only_unowned=True,
    )
    state.idea_ruled_out = link_legacy_findings_to_ideas(findings, ideas)
    state.idea_ruled_out = stamp_ruled_out_findings(
        job_id,
        state.idea_ruled_out,
        operation_key="phase1",
    )
    if flow.checkpoint_mgr and idea_gen:
        if not flow.checkpoint_mgr.save_stage("stage_5_3_refinement", idea_gen):
            raise RuntimeError("Failed to persist durable Phase-1 candidate identities")


_PHASE2_REVIEWED_FIELDS = (
    "idea_id",
    "idea_revision",
    "solution_name",
    "headline",
    "short_description",
    "description",
    "value_proposition",
    "pain_points_addressed",
    "core_features",
    "target_personas",
    "technical_approach",
    "estimated_development_time",
    "dev_time_rationale",
    "pricing_strategy",
    "market_fit_score",
    "technical_feasibility_score",
    "data_feasibility_score",
    "build_feasibility_score",
    "novelty_score",
    "seo_scalability_score",
    "solo_dev_feasibility",
    "winning_angle",
    "angle_rationale",
    "novelty_rationale",
    "differentiation_locus",
    "critic_concern",
    "incumbent_parity",
    "adjacent_market_parity",
    "candidate_status",
    "source_frame",
)


def _resolve_phase2_selection(
    state,
    job_id: str,
    *,
    selected_solution_refs: Optional[list[dict]] = None,
    selected_solution_snapshots: Optional[list[dict]] = None,
    provided_selection_fingerprint: Optional[str] = None,
    legacy_solution_names: Optional[list[str]] = None,
) -> tuple[list[str], list[dict]]:
    """Resolve the paid Phase-2 request to exact hydrated checkpoint revisions."""
    from nicheiq.models.solution_idea import visible_ideas
    from nicheiq.utils.idea_identity import (
        ensure_legacy_idea_identities,
        normalize_solution_name,
        normalized_solution_name_key,
        selection_fingerprint,
    )

    pool = list(
        getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or []
    )
    ensure_legacy_idea_identities(job_id, pool)
    visible = visible_ideas(pool)
    by_ref: dict[tuple[str, int], object] = {}
    for idea in visible:
        key = (
            str(getattr(idea, "idea_id", "") or "").strip(),
            int(getattr(idea, "idea_revision", 0) or 0),
        )
        if not key[0] or key[1] < 1:
            raise RuntimeError("Checkpoint candidate is missing a durable identity")
        if key in by_ref:
            raise RuntimeError(
                f"Checkpoint contains duplicate candidate identity {key[0]}:{key[1]}"
            )
        by_ref[key] = idea

    if selected_solution_refs:
        normalized_refs: list[dict] = []
        seen_refs: set[tuple[str, int]] = set()
        for raw in selected_solution_refs:
            if not isinstance(raw, dict):
                raise RuntimeError("selected_solution_refs must contain objects")
            idea_id = str(raw.get("idea_id") or "").strip()
            revision = raw.get("idea_revision")
            name = normalize_solution_name(raw.get("solution_name"))
            if (
                not idea_id
                or isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 1
                or not name
            ):
                raise RuntimeError("Each selected_solution_ref must contain a valid exact reference")
            key = (idea_id, revision)
            if key in seen_refs:
                raise RuntimeError(f"Duplicate selected candidate reference {idea_id}:{revision}")
            seen_refs.add(key)
            normalized_refs.append(
                {
                    "idea_id": idea_id,
                    "idea_revision": revision,
                    "solution_name": name,
                }
            )

        if not 1 <= len(normalized_refs) <= 3:
            raise RuntimeError("Phase 2 requires 1-3 exact candidate references")

        if provided_selection_fingerprint is not None:
            supplied = provided_selection_fingerprint.strip().lower()
            if not re.fullmatch(r"[a-f0-9]{64}", supplied):
                raise RuntimeError("selection_fingerprint must be a SHA-256 hex digest")
            expected = selection_fingerprint(normalized_refs)
            if not hmac.compare_digest(supplied, expected):
                raise RuntimeError("selection_fingerprint does not match selected_solution_refs")

        resolved: list[object] = []
        canonical_refs: list[dict] = []
        for ref in normalized_refs:
            key = (ref["idea_id"], ref["idea_revision"])
            candidate = by_ref.get(key)
            if candidate is None:
                raise RuntimeError(
                    f"Selected candidate revision not found: {key[0]}:{key[1]}"
                )
            canonical_name = normalize_solution_name(
                getattr(candidate, "solution_name", "")
            )
            if (
                normalized_solution_name_key(ref["solution_name"])
                != normalized_solution_name_key(canonical_name)
            ):
                raise RuntimeError(
                    f"Selected candidate name does not match {key[0]}:{key[1]}"
                )
            resolved.append(candidate)
            canonical_refs.append(
                {
                    "idea_id": key[0],
                    "idea_revision": key[1],
                    "solution_name": canonical_name,
                }
            )

        name_keys = [
            normalized_solution_name_key(ref["solution_name"]) for ref in canonical_refs
        ]
        if len(set(name_keys)) != len(name_keys):
            raise RuntimeError(
                "Phase 2 cannot safely join two selected candidates with the same name"
            )

        if selected_solution_snapshots is not None:
            if (
                not isinstance(selected_solution_snapshots, list)
                or len(selected_solution_snapshots) != len(resolved)
            ):
                raise RuntimeError(
                    "selected_solution_snapshots must align one-for-one with exact refs"
                )
            for index, (snapshot, candidate, ref) in enumerate(
                zip(selected_solution_snapshots, resolved, canonical_refs)
            ):
                if not isinstance(snapshot, dict):
                    raise RuntimeError(
                        f"selected_solution_snapshots[{index}] must be an object"
                    )
                current = _solution_to_preview_dict(candidate)
                for field in _PHASE2_REVIEWED_FIELDS:
                    if field not in snapshot:
                        continue
                    left = json.dumps(
                        snapshot.get(field),
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    )
                    right = json.dumps(
                        current.get(field),
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    )
                    if left != right:
                        raise RuntimeError(
                            f"Selected candidate snapshot is stale at index {index}: {field}"
                        )

        return [ref["solution_name"] for ref in canonical_refs], canonical_refs

    legacy = [
        normalize_solution_name(name)
        for name in (legacy_solution_names or [])
        if normalize_solution_name(name)
    ]
    if not 1 <= len(legacy) <= 3:
        raise RuntimeError("No solution selected for Phase 2")
    if len({normalized_solution_name_key(name) for name in legacy}) != len(legacy):
        raise RuntimeError("Legacy Phase-2 selection contains duplicate solution names")

    canonical_refs = []
    for requested_name in legacy:
        matches = [
            idea for idea in visible
            if normalized_solution_name_key(getattr(idea, "solution_name", ""))
            == normalized_solution_name_key(requested_name)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Legacy selected solution must resolve exactly once: {requested_name!r}"
            )
        candidate = matches[0]
        canonical_refs.append(
            {
                "idea_id": candidate.idea_id,
                "idea_revision": candidate.idea_revision,
                "solution_name": normalize_solution_name(candidate.solution_name),
            }
        )
    return [ref["solution_name"] for ref in canonical_refs], canonical_refs


def _resolve_phase2_winner_ref(
    selected_solution_refs: list[dict],
    winner_name: str,
) -> dict:
    """Map the downstream name-only winner back to one exact selected revision."""
    from nicheiq.utils.idea_identity import normalized_solution_name_key

    matches = [
        ref for ref in selected_solution_refs
        if normalized_solution_name_key(ref["solution_name"])
        == normalized_solution_name_key(winner_name)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Final winner {winner_name!r} does not map to exactly one selected revision"
        )
    return matches[0]


def _validate_regeneration_base_candidate_refs(
    state,
    job_id: str,
    base_candidate_refs: Optional[list[dict]],
) -> None:
    """Authorize regeneration against the exact selectable checkpoint pool.

    Pool order is deliberately ignored: ordering is presentation/ranking state, while an
    additional batch depends on membership in the immutable candidate revisions. The exact
    ``{idea_id, idea_revision}`` set must match. Backend-supplied snapshot hashes are not
    inspected here; arbitrary cross-language full-JSON hashes are not worker authority.
    ``None`` preserves compatibility with queue messages created before this contract.
    """
    if base_candidate_refs is None:
        return
    if not isinstance(base_candidate_refs, list):
        raise RuntimeError("base_candidate_refs must be a list")

    from nicheiq.models.solution_idea import visible_ideas
    from nicheiq.utils.idea_identity import ensure_legacy_idea_identities

    pool = list(
        getattr(getattr(state, "idea_generation", None), "solution_ideas", None) or []
    )
    ensure_legacy_idea_identities(job_id, pool)
    current_refs: set[tuple[str, int]] = set()
    for idea in visible_ideas(pool):
        idea_id = str(getattr(idea, "idea_id", "") or "").strip()
        revision = getattr(idea, "idea_revision", None)
        if (
            not idea_id
            or isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 1
        ):
            raise RuntimeError("Checkpoint candidate is missing a durable identity")
        key = (idea_id, revision)
        if key in current_refs:
            raise RuntimeError(
                f"Checkpoint contains duplicate candidate identity {idea_id}:{revision}"
            )
        current_refs.add(key)

    authorized_refs: set[tuple[str, int]] = set()
    for raw in base_candidate_refs:
        if not isinstance(raw, dict):
            raise RuntimeError("base_candidate_refs must contain objects")
        idea_id = str(raw.get("idea_id") or "").strip()
        revision = raw.get("idea_revision")
        if (
            not idea_id
            or isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 1
        ):
            raise RuntimeError(
                "Each base_candidate_ref must contain idea_id and idea_revision"
            )
        key = (idea_id, revision)
        if key in authorized_refs:
            raise RuntimeError(
                f"base_candidate_refs contains duplicate identity {idea_id}:{revision}"
            )
        authorized_refs.add(key)

    if authorized_refs != current_refs:
        missing = sorted(authorized_refs - current_refs)
        unexpected = sorted(current_refs - authorized_refs)
        raise RuntimeError(
            "Additional-batch base candidate refs do not match the resumed checkpoint "
            f"(missing={missing}, unexpected={unexpected})"
        )


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
        publish_report_ready(job_id, str(job_report_path), cost_summary=_resolve_cost_summary(flow))

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
        from nicheiq.models.solution_idea import BaseSolutionIdea
        if isinstance(solution, BaseSolutionIdea):
            from nicheiq.utils.idea_tags import refresh_tag_facets
            d["tags"] = refresh_tag_facets(solution).model_dump()
    elif isinstance(solution, dict):
        d = dict(solution)
        # Queue/resume boundaries can hand us the same full idea as a plain dict.
        # Re-validate when possible so stale score-owned tags cannot bypass the
        # model-instance refresh path. Partial legacy dicts remain fail-soft.
        from pydantic import ValidationError

        from nicheiq.models.solution_idea import BaseSolutionIdea
        from nicheiq.utils.idea_tags import refresh_tag_facets
        try:
            parsed = BaseSolutionIdea.model_validate(d)
        except ValidationError as e:
            # A partial legacy dict is the expected miss; keep its stored tags as-is.
            logger.debug(
                f"[Worker] Preview dict for {d.get('solution_name') or d.get('name')!r} "
                f"is not a full idea, keeping stored tags: {e.error_count()} field(s) invalid"
            )
        else:
            d["tags"] = refresh_tag_facets(parsed).model_dump()
    else:
        d = {"solution_name": str(solution)}

    # Normalize name field
    name = d.get("solution_name") or d.get("name", "Unknown")
    d["name"] = name
    d["solution_name"] = name

    # Angle-aware ranking on the surface the user actually picks from: the selection grid
    # short-circuits to adjusted_composite_score when present, so stamp the angle-weighted composite
    # (each idea by its own winning_angle; angle=None ideas fall back to an equal-weight mean).
    from nicheiq.utils.score_helpers import angle_ranked_composite
    d["adjusted_composite_score"] = angle_ranked_composite(d)

    # Distill the calibration critic's market_fit reason into ONE user-facing note
    # (mirrors the alternatives path in research_flow) and DROP the raw
    # calibration_notes. The raw string is an internal per-criterion audit,
    # model-flagged not-user-facing; model_dump() would otherwise leak it to the
    # selection payload. The overlay's "How we scored it" card renders critic_concern.
    from nicheiq.utils.calibration_notes import extract_criterion_reason
    d["critic_concern"] = (
        extract_criterion_reason(d.get("calibration_notes"), "market_fit", max_len=280)
        or None
    )
    d.pop("calibration_notes", None)
    return d


def run_interactive_research(
    job_id: str,
    niche: str,
    user_id: Optional[str] = None,
    allowed_project_types: Optional[list[str]] = None,
    resume: bool = False,
    entry_mode: Optional[str] = None,
    idea_focus: Optional[str] = None,
    chat_mode: bool = False,
) -> dict:
    """
    Interactive research task: runs Phase 1, validates solutions, waits for user selection.

    Phase 1: stages 1→5 (idea generation)
    Validation: pricing + keyword scoring per solution
    If user selects during validation → immediately continue to Phase 2
    If validation completes without selection → return awaiting_selection

    chat_mode (guided research, Phase B): stops after Stage 1 instead of running the full
    Phase 1 (stages 1→5) — the G1 gate. Subsequent gate continuations (G1→G2, G2→rest of
    Phase 1) are handled entirely by `continue_from_gate`; this task is only ever the FIRST
    dispatch of a guided-mode job.

    Returns:
        {"status": "completed", "report_path": str} or {"status": "awaiting_selection"}
        or (chat_mode) {"status": "awaiting_gate", "gate_stage": 1, ...}
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
            idea_focus=idea_focus or "auto",
        )
        flow.progress_callback = progress_callback

        mark_job_running(job_id)

        if not resume:
            progress_callback(1, "Niche Analysis", "running")

        if chat_mode:
            # ======= Guided mode: stop after Stage 1 (G1 gate) =======
            logger.info(f"[Worker] Running Stage 1 only for job {job_id} (chat_mode, resume={resume})")
            flow.run_with_resume(auto_resume=resume, stop_after_stage=1)

            # DR B2: branch BEFORE the "Phase 1 did not produce solution ideas" hard-raise
            # below — a G1 stop means solution_ideas don't exist yet (Stage 5 hasn't run), so
            # that check would instantly fail a guided-mode job.
            checkpoint_path = ""
            if flow.checkpoint_mgr and flow.checkpoint_mgr.checkpoint_folder:
                checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)
            gate_artifact = flow._extract_stage_artifact(1) or {}
            notify_gate_reached(
                job_id, gate_stage=1, checkpoint_path=checkpoint_path,
                gate_artifact=gate_artifact, cost_summary=_resolve_cost_summary(flow),
            )
            logger.info(f"[Worker] Job {job_id} entering AWAITING_GATE (stage 1)")
            return {
                "status": "awaiting_gate", "job_id": job_id, "gate_stage": 1,
                "checkpoint_path": checkpoint_path,
            }

        # ======= PHASE 1: Run stages 1→5 (idea generation) =======
        logger.info(f"[Worker] Running Phase 1 for job {job_id} (resume={resume})")
        flow.run_with_resume(auto_resume=resume, stop_after_phase=1)

        # At this point Phase 1 (stages 1→5) is done.
        state = flow.state
        idea_gen = getattr(state, "idea_generation", None)
        if not idea_gen or not hasattr(idea_gen, "solution_ideas") or not idea_gen.solution_ideas:
            raise RuntimeError("Phase 1 did not produce solution ideas")

        _ensure_phase1_identities(flow, job_id)
        from nicheiq.models.solution_idea import visible_ideas

        solutions = visible_ideas(idea_gen.solution_ideas)
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

        # Notify backend: ideas ready, skip to AWAITING_SELECTION directly.
        # Phase-1 cost has no state.cost_summary yet (set at Stage 14), so this reports
        # the live tracker (stages 1-5) for the admin pricing view.
        notify_ideas_ready(job_id, solution_previews, checkpoint_path, len(solutions), skip_validation=True, discovery_data_path=discovery_data_path, preview_report_path=preview_report_path, cost_summary=_resolve_cost_summary(flow))

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
            delivered = notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            if delivered:
                return None
            # Delivery failed — don't silently leave the job stuck in RUNNING/QUEUED (Codex
            # review finding 6). Re-raise so queue_consumer's generic notify_job_failed path
            # takes over instead of treating this as a recovered stop.
            logger.error(
                f"[Worker] Quality-gate-stop not delivered for {job_id} — re-raising to "
                "fall through to notify_job_failed"
            )
            if hasattr(flow, "state") and flow.state:
                e.failed_stage = flow.state.current_stage  # type: ignore
            raise

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


def _notify_phase1_complete_from_gate(job_id: str, flow) -> dict:
    """Shared tail for continue_from_gate's transition to AWAITING_SELECTION — used both by
    the normal gate_stage==4 continuation and the degenerate-G2 fallback (gate_stage==1 whose
    G2 gate artifact came back None, so the flow already skipped the gate stop and ran through
    to the Phase-1-completion stop instead — Codex review finding 2)."""
    state = flow.state
    idea_gen = getattr(state, "idea_generation", None)
    if not idea_gen or not hasattr(idea_gen, "solution_ideas") or not idea_gen.solution_ideas:
        raise RuntimeError("Phase 1 did not produce solution ideas")

    _ensure_phase1_identities(flow, job_id)
    from nicheiq.models.solution_idea import visible_ideas

    solutions = visible_ideas(idea_gen.solution_ideas)
    solution_previews = [_solution_to_preview_dict(s) for s in solutions]
    final_checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)

    discovery_data_path = ""
    preview_report_path = ""
    preview_output_dir = str(settings.checkpoint_dir)
    try:
        result = flow._materialize_discovery_data(preview_output_dir)
        if result:
            discovery_data_path = result
            logger.info(f"[Worker] Discovery data materialized: {discovery_data_path}")
    except Exception as e:
        logger.warning(f"[Worker] Failed to materialize discovery data: {e}")
    try:
        result = flow._materialize_preview_report(preview_output_dir)
        if result:
            preview_report_path = result
            logger.info(f"[Worker] Preview report materialized: {preview_report_path}")
    except Exception as e:
        logger.warning(f"[Worker] Failed to materialize preview report: {e}")

    notify_ideas_ready(
        job_id, solution_previews, final_checkpoint_path, len(solutions),
        skip_validation=True, discovery_data_path=discovery_data_path,
        preview_report_path=preview_report_path, cost_summary=_resolve_cost_summary(flow),
    )
    logger.info(f"[Worker] Job {job_id} entering AWAITING_SELECTION (from G2)")
    return {"status": "awaiting_selection", "job_id": job_id}


def continue_from_gate(
    job_id: str,
    checkpoint_path: str,
    gate_stage: int,
    mode: str = "continue",
    patch: Optional[dict] = None,
) -> dict:
    """
    Continue a guided-mode (chatMode) job from a G1 (Stage 1) or G2 (Stage 4) gate.

    mode='continue' (default): apply an optional patch, then run to the NEXT stop —
        G1 -> stop_after_stage=4 (G2); G2 -> stop_after_phase=1 (Phase 1 complete,
        AWAITING_SELECTION, same shape as `run_interactive_research`'s non-chat-mode path).
    mode='apply_stay': apply the (required) patch, then re-notify the SAME gate with a
        refreshed artifact — the run does NOT advance past this gate (the regeneration
        round-trip shape: gate -> QUEUED -> worker -> same gate, per the plan's Decisions).

    Replicates `run_research_phase2`/`_run_phase2_continuation`'s full setup sequence:
    progress callback binding, mark_job_running, resume_from_checkpoint (restores cost
    rows via load_state — NEVER manually load state or construct crews without the
    tracker), skip_bulk_replay=True (the interactive frontend already has prior stages
    rendered green from the live run, DR N2). Reports the EFFECTIVE post-resume checkpoint
    path back on every notification (fork semantics — a cross-job resume forks to a new
    folder, Codex 10), never the input `checkpoint_path`.

    A GatePatchError (invalid/stale patch) or any other failure here is NOT retried as a
    generic job failure — the caller (queue_consumer) intercepts this task_type's exception
    and calls notify_gate_failed, reverting the job QUEUED -> AWAITING_GATE (retryable,
    preserves the existing gate artifact/patch history) instead of FAILED.
    """
    logger.info(f"[Worker] continue_from_gate job={job_id} gate_stage={gate_stage} mode={mode}")

    if mode == "apply_stay" and not patch:
        raise RuntimeError("apply_stay requires a patch")

    output_base = Path(os.environ.get("NICHEIQ_OUTPUT_DIR", "./output/jobs"))
    output_dir = output_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow
        from nicheiq.flows.gate_patches import GatePatchError, apply_gate_patch

        progress_callback = create_progress_callback(job_id)

        # niche_description="" — loaded from checkpoint, mirrors run_research_phase2.
        flow = ResearchFlow(niche_description="", job_id=job_id)
        flow.progress_callback = progress_callback

        mark_job_running(job_id)

        loaded = flow.resume_from_checkpoint(checkpoint_path)
        if not loaded:
            raise RuntimeError(f"Failed to load checkpoint from {checkpoint_path}")

        if patch:
            try:
                apply_gate_patch(flow.state, gate_stage, patch, flow=flow)
            except GatePatchError as e:
                raise RuntimeError(f"Invalid gate patch: {e}") from e

        if mode == "apply_stay":
            if gate_stage == 1:
                gate_artifact = flow._extract_stage_artifact(1) or {}
            elif gate_stage == 4:
                gate_artifact = flow._build_g2_gate_artifact()
                if gate_artifact is None:
                    # Neither pain analysis nor audience mapping survived the patch — there
                    # is nothing left to gate on. Route to the failure path (queue_consumer
                    # -> notify_gate_failed -> revert QUEUED -> AWAITING_GATE, retryable)
                    # instead of silently re-notifying an empty {} card (finding 2).
                    raise RuntimeError("G2 gate artifact unavailable after apply_stay patch")
            else:
                raise RuntimeError(f"Unsupported gate_stage for apply_stay: {gate_stage}")
            effective_checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)
            notify_gate_reached(
                job_id, gate_stage=gate_stage, checkpoint_path=effective_checkpoint_path,
                gate_artifact=gate_artifact, cost_summary=_resolve_cost_summary(flow),
            )
            logger.info(f"[Worker] Job {job_id} apply_stay complete — re-notified gate {gate_stage}")
            return {
                "status": "awaiting_gate", "job_id": job_id, "gate_stage": gate_stage,
                "checkpoint_path": effective_checkpoint_path,
            }

        # mode == "continue": run to the NEXT stop.
        if gate_stage == 1:
            # stop_after_phase=1 bounds the degenerate-G2 fallthrough (finding 2): if the
            # flow skips the G2 stop because neither pain analysis nor audience mapping
            # survived, it would otherwise run the ENTIRE remaining pipeline unattended
            # inside this one task. Passing both is safe in the normal case — the
            # stop_after_stage==4 return inside the ladder fires first, so stop_after_phase=1
            # is never reached.
            flow._execute_remaining_stages(
                stop_after_stage=4, stop_after_phase=1, skip_bulk_replay=True)
            effective_checkpoint_path = str(flow.checkpoint_mgr.checkpoint_folder)
            gate_artifact = flow._build_g2_gate_artifact()
            if gate_artifact is not None:
                notify_gate_reached(
                    job_id, gate_stage=4, checkpoint_path=effective_checkpoint_path,
                    gate_artifact=gate_artifact, cost_summary=_resolve_cost_summary(flow),
                )
                logger.info(f"[Worker] Job {job_id} entering AWAITING_GATE (stage 4)")
                return {
                    "status": "awaiting_gate", "job_id": job_id, "gate_stage": 4,
                    "checkpoint_path": effective_checkpoint_path,
                }
            # Degenerate G2 — the flow already skipped the gate stop and continued to the
            # Phase-1-completion stop instead. Finish exactly like gate_stage==4 does.
            logger.warning(
                f"[Worker] Job {job_id} G2 gate unavailable (no pain analysis or audience "
                "mapping) — skipped the gate and continued to Phase-1 completion"
            )
            return _notify_phase1_complete_from_gate(job_id, flow)

        if gate_stage == 4:
            flow._execute_remaining_stages(stop_after_phase=1, skip_bulk_replay=True)
            return _notify_phase1_complete_from_gate(job_id, flow)

        raise RuntimeError(f"Unsupported gate_stage: {gate_stage}")

    except Exception as e:
        from .heartbeat import JobCancelledException
        from nicheiq.flows.research_flow import QualityGateStopException

        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] continue_from_gate job {job_id} cancelled by user")
            raise

        if isinstance(e, QualityGateStopException):
            logger.info(f"[Worker] continue_from_gate job {job_id} stopped by quality gate: {e.reason}")
            delivered = notify_job_quality_gate_stop(job_id, e.reason, e.details, e.stage)
            if delivered:
                return None
            # Delivery failed — don't silently leave the job stuck in RUNNING/QUEUED (Codex
            # review finding 6, "same discipline" as notify_gate_failed). Re-raise so this
            # falls through to queue_consumer's TASK_TYPE_CONTINUE_FROM_GATE handling
            # (notify_gate_failed, and ultimately notify_job_failed if that also fails).
            logger.error(
                f"[Worker] Quality-gate-stop not delivered for {job_id} — re-raising to "
                "fall through to the gate-failure/job-failure safety net"
            )
            e.gate_stage = gate_stage  # type: ignore
            raise

        error_msg = str(e)
        logger.error(
            f"[Worker] continue_from_gate failed for job {job_id}: {error_msg}\n{traceback.format_exc()}"
        )
        e.gate_stage = gate_stage  # type: ignore
        raise

    finally:
        try:
            if flow is not None:
                flow.cleanup_collections()
        except Exception as cleanup_err:
            logger.debug(f"Knowledge cleanup error (non-fatal): {cleanup_err}")


def _run_phase2_continuation(
    flow,
    job_id,
    selected_solutions,
    selected_solution_refs,
    selection_rationale,
    output_dir,
    progress_callback,
) -> dict:
    """
    Continue from Phase 1 to Phase 2 with the selected solution(s).
    Runs stages 8.55→10 and optionally stage 11 (landing page).
    """

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
    from nicheiq.models.solution_idea import visible_ideas
    if state.idea_generation and state.idea_generation.solution_ideas:
        all_scores = compute_solution_scores(visible_ideas(state.idea_generation.solution_ideas))
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
    winner_ref = _resolve_phase2_winner_ref(
        selected_solution_refs, final_winner,
    )
    publish_report_ready(
        job_id, str(job_report_path), winner_name=final_winner,
        winner_ref=winner_ref,
        cost_summary=_resolve_cost_summary(flow),
    )

    # Publish completion (landing pages are on-demand only)
    publish_job_completed(job_id, str(job_report_path), None)

    return {
        "status": "completed",
        "job_id": job_id,
        "report_path": str(job_report_path),
        "winner_name": final_winner,
        "winner_ref": winner_ref,
    }


def run_research_phase2(
    job_id: str,
    checkpoint_path: str,
    selected_solutions: list[str] = None,
    selected_solution: str = "",
    selected_solution_refs: Optional[list[dict]] = None,
    selected_solution_snapshots: Optional[list[dict]] = None,
    selection_fingerprint: Optional[str] = None,
    selection_rationale: str = "",
) -> dict:
    """
    Phase 2 task: runs deep investigation for user-selected solution(s).
    Loaded from checkpoint, runs stages 8.55→10 + optional landing page.

    Supports multi-select via selected_solutions list, with backward compat
    via selected_solution string.
    """
    legacy_solutions = selected_solutions or (
        [selected_solution] if selected_solution else []
    )
    if not selected_solution_refs and not legacy_solutions:
        raise RuntimeError("No solution selected for Phase 2")

    logger.info(
        f"[Worker] Starting Phase 2 for job {job_id}, "
        f"exact_refs={len(selected_solution_refs or [])}, legacy={legacy_solutions}"
    )

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

        solutions, canonical_refs = _resolve_phase2_selection(
            flow.state,
            job_id,
            selected_solution_refs=selected_solution_refs,
            selected_solution_snapshots=selected_solution_snapshots,
            provided_selection_fingerprint=selection_fingerprint,
            legacy_solution_names=legacy_solutions,
        )

        return _run_phase2_continuation(
            flow, job_id, solutions, canonical_refs, selection_rationale,
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
        from nicheiq.models.solution_idea import visible_ideas

        solutions = visible_ideas(idea_gen.solution_ideas)
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
            cost_summary=_resolve_cost_summary(flow),
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
        publish_report_ready(
            job_id, str(job_report_path), winner_name=final_winner,
            cost_summary=_resolve_cost_summary(flow),
        )
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
    idea_focus: Optional[str] = None,
    dispatch_id: Optional[str] = None,
    batch_ordinal: Optional[int] = None,
    base_candidate_refs: Optional[list[dict]] = None,
) -> dict:
    """
    Regeneration task: generates new solution ideas avoiding existing names.
    Loaded from checkpoint, runs solution crew with exclusion list.

    idea_focus, when provided, is a BATCH-SCOPED override for this regeneration only — the user
    changing the GTM focus for the new batch. It does NOT overwrite the run-level state.idea_focus
    (kept immutable); it's passed straight to the crew. None → fall back to the checkpoint's focus.
    """
    logger.info(
        f"[Worker] Adding idea batch for job {job_id} "
        f"(operation={dispatch_id or 'legacy'}, ordinal={batch_ordinal}), "
        f"excluding: {existing_solution_names}"
    )

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
        _validate_regeneration_base_candidate_refs(
            state,
            job_id,
            base_candidate_refs,
        )
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
                        # M/D/J structural tags enable catching REWORDED duplicates
                        # (text-based dedup misses those).
                        "mechanism_tag": getattr(s, "mechanism_tag", None),
                        "data_source_tag": getattr(s, "data_source_tag", None),
                        "journey_tag": getattr(s, "journey_tag", None),
                        # Critic scoreboard: lets the regen directive steer new ideators
                        # toward angles the calibration critic actually rewarded.
                        "market_fit_score": getattr(s, "market_fit_score", None),
                        "calibration_notes": getattr(s, "calibration_notes", None),
                    }
        # existing_solution_names (backend-provided) is visible-only. Union in demoted/absorbed
        # names from the checkpoint so hidden ideas can't be regenerated as "new" — they were
        # already tried and ruled out / folded into a merge.
        hidden_names = []
        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            hidden_names = [
                getattr(s, "solution_name", "")
                for s in state.idea_generation.solution_ideas
                if getattr(s, "candidate_status", None) in ("demoted", "absorbed") and getattr(s, "solution_name", "")
            ]
        blacklist_names = list(dict.fromkeys(list(existing_solution_names) + hidden_names))

        existing_ideas_for_crew = [
            {
                "name": n,
                "description": idea_lookup.get(n.lower(), {}).get("description", ""),
                "project_type": idea_lookup.get(n.lower(), {}).get("project_type", ""),
                "mechanism_tag": idea_lookup.get(n.lower(), {}).get("mechanism_tag"),
                "data_source_tag": idea_lookup.get(n.lower(), {}).get("data_source_tag"),
                "journey_tag": idea_lookup.get(n.lower(), {}).get("journey_tag"),
                "market_fit_score": idea_lookup.get(n.lower(), {}).get("market_fit_score"),
                "calibration_notes": idea_lookup.get(n.lower(), {}).get("calibration_notes"),
            }
            for n in blacklist_names
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
            # Batch override > restored run-level focus > default. Run-level state stays immutable.
            idea_focus=(idea_focus or getattr(flow, "idea_focus", "auto") or "auto"),
            cost_tracker=flow.cost_tracker,
        )

        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            old_solutions = list(state.idea_generation.solution_ideas)
        else:
            old_solutions = []
        original_snapshot = _canonical_solution_snapshot(old_solutions)
        # Captured before the batch runs so the delivery-failure handler can restore the
        # exact pre-batch ruled-out list without relying on a per-finding dispatch stamp
        # (legacy callers pass dispatch_id=None, which no filter can distinguish).
        pre_batch_findings = list(getattr(state, "idea_ruled_out", None) or [])

        # Execute pipeline with skip_selection=True (no Task 4 needed for regeneration)
        result = crew.execute_pipeline(skip_selection=True)
        idea_gen = result[0]  # IdeaGenerationResult (result[1] is None)

        if not idea_gen or not hasattr(idea_gen, "solution_ideas"):
            raise RuntimeError("Regeneration did not produce solution ideas")

        # Post-hoc safety-net: filter out solutions that duplicate existing ones.
        # Exact-name match (cheap) PLUS structural duplicate detection (a renamed
        # same-idea passed the exact-name filter before — detect_catalog_duplicate
        # compares mechanism/value-prop/personas against the existing catalog).
        from nicheiq.utils.validation.crew_guardrails import detect_catalog_duplicate
        existing_names_lower = {n.lower() for n in blacklist_names}

        def _duplicate_target(s) -> Optional[str]:
            name = getattr(s, "solution_name", "") or getattr(s, "name", "")
            if name.lower() in existing_names_lower:
                return next(
                    (existing for existing in blacklist_names if existing.lower() == name.lower()),
                    name,
                )
            try:
                for existing in existing_ideas_for_crew:
                    if detect_catalog_duplicate(s, existing):
                        return existing.get("name") or name
            except Exception:
                pass
            return None

        generated_solutions = list(idea_gen.solution_ideas)
        from nicheiq.utils.idea_identity import (
            normalized_solution_name_key,
            stamp_new_idea_identities,
            stamp_ruled_out_findings,
        )

        batch_operation_key = dispatch_id or f"batch_{batch_ordinal or 1}"
        stamp_new_idea_identities(
            job_id,
            generated_solutions,
            origin="regeneration",
            operation_key=batch_operation_key,
            force=True,
        )
        for solution in generated_solutions:
            # source_frame is the GENERATION LENS (gap / data_asset / workflow) and drives
            # the lens chip. Batch provenance lives in the two fields below, so overwriting
            # the lens here would only strip batch ideas of a chip first-batch ideas keep.
            # Fill it in only when the generator left it unset.
            if not solution.source_frame:
                solution.source_frame = "additional_batch"
            solution.generation_operation_id = dispatch_id
            solution.generation_batch_ordinal = batch_ordinal

        duplicate_solutions = []
        new_solutions = []
        for solution in generated_solutions:
            duplicate_of = _duplicate_target(solution)
            if duplicate_of:
                solution.candidate_status = "demoted"
                solution.duplicate_of = duplicate_of
                crew._record_ruled_out(
                    solution,
                    source="backfill_rejected",
                    reason_override=(
                        f"This batch result duplicated the existing candidate "
                        f"'{duplicate_of}', so it was not appended."
                    ),
                )
                duplicate_solutions.append(solution)
            else:
                new_solutions.append(solution)

        if duplicate_solutions:
            logger.info(
                f"[Worker] Excluded {len(duplicate_solutions)} duplicate result(s) "
                f"from append-only batch {dispatch_id or 'legacy'}"
            )

        # Merge old (loaded from checkpoint) + new solutions so future
        # validate/analyze finds solutions from ALL batches
        if _canonical_solution_snapshot(old_solutions) != original_snapshot:
            raise RuntimeError(
                "Append-only invariant violated: an existing candidate changed "
                "during additional-batch generation"
            )
        merged_solutions = old_solutions + list(new_solutions)
        logger.info(
            f"Merged solutions: {len(old_solutions)} existing + {len(new_solutions)} new = {len(merged_solutions)} total"
        )

        # Update state in-place and re-save checkpoint
        if state.idea_generation and hasattr(state.idea_generation, "solution_ideas"):
            state.idea_generation.solution_ideas = merged_solutions
        # Empty names are excluded: a blank entry would otherwise match every finding whose
        # idea_name is missing, sweeping unrelated rows into this batch's receipt.
        batch_names = {
            name for name in (
                getattr(solution, "solution_name", "") for solution in generated_solutions
            ) if name
        }
        batch_findings = []
        from collections import defaultdict, deque

        generated_by_name = defaultdict(deque)
        ruled_out_by_name = defaultdict(deque)
        for solution in generated_solutions:
            name_key = normalized_solution_name_key(solution.solution_name)
            if name_key:
                generated_by_name[name_key].append(solution)
                if getattr(solution, "candidate_status", "active") in {
                    "demoted",
                    "absorbed",
                }:
                    ruled_out_by_name[name_key].append(solution)
        for finding in list(crew.ruled_out_pains or []):
            if finding.get("idea_name") not in batch_names:
                continue
            # Lens-preserving, same reasoning as the candidate stamping above.
            if not finding.get("source_frame"):
                finding["source_frame"] = "additional_batch"
            finding["generation_operation_id"] = dispatch_id
            finding["generation_batch_ordinal"] = batch_ordinal
            finding_name_key = normalized_solution_name_key(finding.get("idea_name"))
            candidates_for_name = (
                ruled_out_by_name[finding_name_key]
                if finding_name_key in ruled_out_by_name
                else generated_by_name.get(finding_name_key)
            )
            matched_idea = (
                candidates_for_name.popleft() if candidates_for_name else None
            )
            if matched_idea is not None:
                finding["idea_id"] = matched_idea.idea_id
                finding["idea_revision"] = matched_idea.idea_revision
                finding["identity_origin"] = matched_idea.identity_origin
                finding["identity_operation_id"] = matched_idea.identity_operation_id
            nested_idea = finding.get("idea")
            if isinstance(nested_idea, dict):
                if not nested_idea.get("source_frame"):
                    nested_idea["source_frame"] = "additional_batch"
                nested_idea["generation_operation_id"] = dispatch_id
                nested_idea["generation_batch_ordinal"] = batch_ordinal
                if matched_idea is not None:
                    nested_idea["idea_id"] = matched_idea.idea_id
                    nested_idea["idea_revision"] = matched_idea.idea_revision
                    nested_idea["identity_origin"] = matched_idea.identity_origin
                    nested_idea["identity_operation_id"] = (
                        matched_idea.identity_operation_id
                    )
            batch_findings.append(finding)
        stamp_ruled_out_findings(
            job_id,
            batch_findings,
            operation_key=f"regeneration:{batch_operation_key}",
        )
        state.idea_ruled_out = pre_batch_findings + batch_findings
        if flow.checkpoint_mgr and state.idea_generation:
            flow.checkpoint_mgr.save_stage("stage_5_3_refinement", state.idea_generation)

        # Regeneration updates the same preview-report asset used by the selection UI,
        # analyst chat, and decision tools. Rewrite it from the merged state before
        # notifying the backend; otherwise those readers keep the pre-regeneration
        # candidate pool even though Job.solutionIdeas already contains the new batch.
        try:
            flow._materialize_preview_report(str(settings.checkpoint_dir))
        except Exception as e:
            logger.warning(
                f"[Worker] Failed to re-materialize preview report after regeneration "
                f"for job {job_id}: {e}"
            )

        # Send only NEW previews — backend appends to existing list. Filter through the
        # visibility projection (regenerated ideas default candidate_status='active' so this
        # is currently a no-op, but it future-proofs the boundary).
        from nicheiq.models.solution_idea import visible_ideas

        visible_new_solutions = visible_ideas(new_solutions)
        new_previews = [_solution_to_preview_dict(s) for s in visible_new_solutions]

        if not new_previews:
            logger.warning(f"[Worker] Regenerate produced 0 visible ideas for job {job_id}")

        progress_callback(5, "Solution Pipeline", "completed")

        # Notify backend with new solutions. Delivery raises on exhausted retries; the tag
        # lets the handler below tell "batch is saved but nobody was told" apart from a real
        # pipeline failure, so the saved-but-unpaid batch is reverted before it is refunded.
        try:
            notify_regeneration_complete(
                job_id,
                new_previews,
                cost_summary=_resolve_cost_summary(flow),
                batch_ordinal=batch_ordinal,
                generated_count=len(generated_solutions),
                ruled_out_count=len(batch_findings),
            )
        except Exception as delivery_err:
            delivery_err.regeneration_delivery_only = True  # type: ignore
            raise

        return {
            "status": "regenerated",
            "job_id": job_id,
            "new_count": len(new_previews),
            "generated_count": len(generated_solutions),
            "ruled_out_count": len(batch_findings),
        }

    except Exception as e:
        from .heartbeat import JobCancelledException

        if isinstance(e, JobCancelledException):
            raise

        if getattr(e, "regeneration_delivery_only", False):
            logger.error(
                f"[Worker] Idea batch for job {job_id} completed and was saved, but delivery to "
                f"the backend failed: {e}. Reverting the undelivered batch before the "
                "regeneration dispatch is settled and refunded."
            )
            # Same contract as run_seed_idea's seed_delivery_only handler: Phase 2 resolves
            # selections from this checkpoint, so a batch the backend never accepted — and
            # which queue_consumer is about to have refunded — must not survive there or in
            # the separately materialized preview asset.
            try:
                if flow.checkpoint_mgr and state.idea_generation:
                    state.idea_generation.solution_ideas = old_solutions
                    state.idea_ruled_out = pre_batch_findings
                    flow.checkpoint_mgr.save_stage("stage_5_3_refinement", state.idea_generation)
                    flow._materialize_preview_report(str(settings.checkpoint_dir))
                    logger.info(
                        f"[Worker] Reverted unpaid idea batch for job {job_id} pending refund "
                        "(delivery never landed)"
                    )
            except Exception as revert_err:
                logger.error(
                    f"[Worker] Failed to revert idea-batch checkpoint for {job_id}: {revert_err}"
                )
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


def run_seed_idea(
    job_id: str,
    checkpoint_path: str,
    seed: dict,
    niche: str,
    dispatch_id: Optional[str] = None,
) -> dict:
    """
    User-seed pipeline (eager-meandering-feather.md Phase 5): birth + score exactly ONE
    user-composed idea and merge it into the existing pool. Clones `run_regenerate_ideas`'s
    spine (resume checkpoint -> build ONE crew -> run -> merge -> re-save), but:

    - The crew is HYDRATED (`crew.hydrate_from_state`), never re-run cold — a seed must not
      re-probe paid Phase-1 evidence (incumbents, wallet brief, data menu, payability) the user
      already paid for.
    - Birth/tournament/scoring/finalization all live in `UnifiedSolutionCrew.
      execute_seed_pipeline` (Phase 4) — the REAL per-cell birth path
      (`_run_seed_cell` -> `_tournament_cell` -> `_score_cell_winner`), never a hand-built idea.
    - The seed may come back ACTIVE or DEMOTED — both are sent; the UI shows a demoted seed in
      Examined & ruled out rather than hiding it. Only a TOTAL birth failure (`execute_seed_
      pipeline` returns None) is a pipeline failure.
    - Dedup is keep-with-caveat, NEVER drop: a paid request must not vanish from the pool. A
      seed that structurally duplicates an existing pool idea (`detect_catalog_duplicate`) is
      merged anyway, with `duplicate_of` stamped naming the existing idea.
    - This function does the WORKER's own authoritative `save_stage("stage_5_3_refinement")`
      post-merge — `execute_seed_pipeline`'s own tail (`_finalize_seed_tail`) deliberately never
      saves, so the seed can't race/overwrite the pool checkpoint mid-evaluation.

    `seed` is `{'seed_text': str, 'pain_ref': str | None, 'tool_ref': str | None}` — the
    chat-composed idea (free text required, refs optional; pain/tool resolution itself happens
    inside `execute_seed_pipeline` via `resolve_seed_anchors`, not here).

    Delivery of the outcome (`notify_seed_complete`) raises on exhausted retries rather than
    swallowing. The exception is tagged `seed_delivery_only` so this task can revert the
    saved checkpoint/preview and queue_consumer can settle/refund the seed dispatch without
    treating the whole research job as failed.
    """
    logger.info(f"[Worker] Seed idea for job {job_id}: {(seed.get('seed_text') or '')[:80]!r}")

    flow = None
    try:
        from nicheiq.flows.research_flow import ResearchFlow

        progress_callback = create_progress_callback(job_id)

        flow = ResearchFlow(niche_description=niche, job_id=job_id)
        flow.progress_callback = progress_callback

        loaded = flow.resume_from_checkpoint(checkpoint_path)
        if not loaded:
            raise RuntimeError(f"Failed to load checkpoint from {checkpoint_path}")

        state = flow.state
        progress_callback(5, "Solution Pipeline", "running")

        from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew

        pain_points = getattr(state, "pain_point_analysis", None)
        social_content = getattr(state, "social_content", None)
        niche_context = getattr(state, "niche_context", None)
        audience = getattr(state, "audience_mapping", None)
        competitor_mentions = getattr(state, "competitor_mentions_formatted", None)

        crew = UnifiedSolutionCrew(
            pain_point_analysis=pain_points,
            social_content=social_content,
            allowed_project_types=flow.allowed_project_types,
            niche_context=niche_context,
            audience_mapping=audience,
            checkpoint_mgr=flow.checkpoint_mgr,
            job_id=job_id,
            competitor_mentions_text=competitor_mentions,
            idea_focus=(getattr(flow, "idea_focus", "auto") or "auto"),
            cost_tracker=flow.cost_tracker,
        )
        # No crew survives a checkpoint resume — restore the Phase-1 evidence caches this
        # process already paid for instead of cold-re-probing them (Phase 4 section C).
        crew.hydrate_from_state(state)

        seed_operation_key = dispatch_id or "seed"
        idea = crew.execute_seed_pipeline(SeedRequest(
            seed_text=seed.get("seed_text") or "",
            pain_ref=seed.get("pain_ref"),
            tool_ref=seed.get("tool_ref"),
            dispatch_id=seed_operation_key,
            synthesis_evaluation=seed.get("synthesis_evaluation"),
        ))

        if idea is None:
            raise RuntimeError("Seed pipeline did not produce an idea")

        from nicheiq.utils.idea_identity import (
            stamp_new_idea_identities,
            stamp_ruled_out_findings,
        )

        stamp_new_idea_identities(
            job_id,
            [idea],
            origin="seed",
            operation_key=seed_operation_key,
            force=True,
        )
        old_solutions = list(getattr(state.idea_generation, "solution_ideas", None) or [])

        # Dedup: keep-with-caveat, NEVER drop. A paid seed is merged regardless of whether it
        # structurally duplicates an existing pool idea — only stamped, mirroring
        # run_regenerate_ideas's detect_catalog_duplicate check but with the opposite outcome
        # (regeneration may discard a batch duplicate; a lone paid seed never does).
        try:
            from nicheiq.utils.validation.crew_guardrails import detect_catalog_duplicate

            for existing in old_solutions:
                existing_dict = {
                    "name": getattr(existing, "solution_name", "") or getattr(existing, "name", ""),
                    "description": getattr(existing, "description", ""),
                    "mechanism_tag": getattr(existing, "mechanism_tag", None),
                    "data_source_tag": getattr(existing, "data_source_tag", None),
                    "journey_tag": getattr(existing, "journey_tag", None),
                }
                if detect_catalog_duplicate(idea, existing_dict):
                    idea.duplicate_of = existing_dict["name"] or None
                    logger.info(
                        f"[Seed] job {job_id}: seed idea structurally duplicates "
                        f"'{idea.duplicate_of}' — kept, caveat stamped"
                    )
                    break
        except Exception as e:
            logger.warning(f"[Seed] duplicate check skipped (non-fatal): {e}")

        merged_solutions = old_solutions + [idea]
        if state.idea_generation:
            state.idea_generation.solution_ideas = merged_solutions

        # A DEMOTED seed must land in "Examined & ruled out", not the selectable pool —
        # merge this dispatch's ruled-out record(s) into the state ledger (mirrors
        # research_flow.py's post-Stage-5 merge at :4371-4374). Filtered to `dispatch_id`
        # since a reused crew instance could in principle carry more than this seed's own
        # entry. `save_stage` below flushes this via its metadata side effect — no separate
        # persistence call needed (checkpoint_manager.py's `_update_checkpoint_metadata`
        # reads `self.state.idea_ruled_out` directly, not the `stage_data` argument).
        seed_findings = [
            r for r in (crew.ruled_out_pains or [])
            if r.get("dispatch_id") == seed_operation_key
        ]
        for finding in seed_findings:
            finding["idea_id"] = idea.idea_id
            finding["idea_revision"] = idea.idea_revision
            finding["identity_origin"] = idea.identity_origin
            finding["identity_operation_id"] = idea.identity_operation_id
            nested = finding.get("idea")
            if isinstance(nested, dict):
                nested["idea_id"] = idea.idea_id
                nested["idea_revision"] = idea.idea_revision
                nested["identity_origin"] = idea.identity_origin
                nested["identity_operation_id"] = idea.identity_operation_id
        stamp_ruled_out_findings(
            job_id,
            seed_findings,
            operation_key=f"seed:{seed_operation_key}",
        )
        state.idea_ruled_out = (
            list(getattr(state, "idea_ruled_out", None) or []) + seed_findings
        )

        # The WORKER's own authoritative save — execute_seed_pipeline/_finalize_seed_tail
        # deliberately never saves, so this is the ONLY write of the merged pool.
        if flow.checkpoint_mgr and state.idea_generation:
            flow.checkpoint_mgr.save_stage("stage_5_3_refinement", state.idea_generation)

        # Re-materialize the preview report so the SAME asset the UI reads
        # (assetService.ts / AssetType.PREVIEW_REPORT) reflects the new ruled-out record —
        # `_materialize_preview_report` is keyed by job_id, so this overwrites the exact
        # file the earlier Phase-1 materialization wrote (research_flow.py's
        # `_materialize_preview_report` call sites at ~:474/968 use the same output_dir).
        try:
            flow._materialize_preview_report(str(settings.checkpoint_dir))
        except Exception as e:
            logger.warning(f"[Seed] Failed to re-materialize preview report for job {job_id}: {e}")

        progress_callback(5, "Solution Pipeline", "completed")

        outcome = "accepted" if getattr(idea, "candidate_status", "active") == "active" else "demoted"
        preview = _solution_to_preview_dict(idea)
        if outcome == "demoted":
            finding = next(
                (
                    r for r in (crew.ruled_out_pains or [])
                    if r.get("dispatch_id") == seed_operation_key
                ),
                None,
            )
            if finding:
                preview["evaluation_reason"] = finding.get("reason")

        # Save first so a successful callback can expose an internally consistent checkpoint.
        # If callback delivery exhausts its retries, the tagged handler below rolls both assets
        # back before queue_consumer settles/refunds this seed-only operation.
        try:
            notify_seed_complete(job_id, preview, outcome, cost_summary=_resolve_cost_summary(flow))
        except Exception as delivery_err:
            delivery_err.seed_delivery_only = True  # type: ignore
            raise

        return {"status": "seed_settled", "job_id": job_id, "outcome": outcome}

    except Exception as e:
        from .heartbeat import JobCancelledException

        if isinstance(e, JobCancelledException):
            raise

        if getattr(e, "seed_delivery_only", False):
            logger.error(
                f"[Worker] Seed idea for job {job_id} completed and was saved, but delivery to "
                f"the backend failed: {e}. Reverting the undelivered result before the seed "
                "dispatch is settled and refunded."
            )
            # Revert the merge and ruled-out record before queue_consumer reports seed-failed.
            # Phase 2 resolves selections from this checkpoint, so an undelivered/unpaid result
            # must not survive there or in the separately materialized preview asset.
            try:
                if flow.checkpoint_mgr and state.idea_generation:
                    state.idea_generation.solution_ideas = old_solutions
                    state.idea_ruled_out = [
                        r for r in (getattr(state, "idea_ruled_out", None) or [])
                        if r.get("dispatch_id") != seed_operation_key
                    ]
                    flow.checkpoint_mgr.save_stage("stage_5_3_refinement", state.idea_generation)
                    # The preview asset was materialized with the now-reverted idea before
                    # delivery was attempted. Rewrite it from the reverted state too, or the
                    # backend can invalidate its cache and still reload a ghost candidate.
                    flow._materialize_preview_report(str(settings.checkpoint_dir))
                    logger.info(
                        f"[Worker] Reverted unpaid seed merge for job {job_id} pending refund "
                        "(delivery never landed)"
                    )
            except Exception as revert_err:
                logger.error(f"[Worker] Failed to revert seed checkpoint for {job_id}: {revert_err}")
            raise

        logger.error(f"[Worker] Seed idea failed for job {job_id}: {e}\n{traceback.format_exc()}")
        e.failed_stage = 5  # type: ignore
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
                commercial_intent=pp_data.get("commercialIntentScore", pp_data.get("commercial_intent", 0.5)),
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
        from nicheiq.utils.token_monitor import CostTracker

        tracker = CostTracker()
        crew = UnifiedSolutionCrew(
            pain_point_analysis=pain_analysis,
            social_content=None,
            niche_context=None,
            audience_mapping=None,
            job_id=job_id,
            existing_ideas=existing_ideas,
            cost_tracker=tracker,
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
            cost_summary = tracker.get_summary()
            logger.info(f"[CatalogIdeas] LLM cost: ${cost_summary['total_cost']}")
            return {"status": "completed", "job_id": job_id, "idea_count": 0, "cost_summary": cost_summary}

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
                cost_summary = tracker.get_summary()
                logger.info(f"[CatalogIdeas] LLM cost: ${cost_summary['total_cost']}")
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "idea_count": 0,
                    "note": "regeneration produced only duplicates of existing ideas",
                    "cost_summary": cost_summary,
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

        cost_summary = tracker.get_summary()
        logger.info(f"[CatalogIdeas] LLM cost: ${cost_summary['total_cost']}")
        logger.info(f"[Worker] Catalog ideas complete for job {job_id}: {len(idea_previews)} ideas")
        return {"status": "completed", "job_id": job_id, "idea_count": len(idea_previews), "cost_summary": cost_summary}

    except Exception as e:
        from .heartbeat import JobCancelledException

        if isinstance(e, JobCancelledException):
            logger.info(f"[Worker] Catalog ideas job {job_id} cancelled")
            raise

        logger.error(f"[Worker] Catalog ideas job {job_id} failed: {e}\n{traceback.format_exc()}")
        e.failed_stage = 5  # type: ignore
        raise
