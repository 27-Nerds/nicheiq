"""Guided-mode (chatMode) gate patch application — G1 (Stage 1) / G2 (Stage 4).

Called by `worker/tasks.py::continue_from_gate` after resuming a checkpoint, BEFORE the
stage ladder re-enters. The patch itself has already been Zod-validated on the backend
(jobs.ts POST /:jobId/gate-action) and cross-checked against the last-delivered
gateArtifact; this module is the second, authoritative validation layer (Pydantic
whitelists, shared valid/invalid fixtures with the backend's Zod schemas — R4) plus the
actual state mutation.

Design (Decisions in plans/eager-meandering-feather.md):
- G1 patches OVERWRITE niche_context's whitelisted fields directly (the user's edit wins),
  then re-derive Stage 1's DEPENDENT outputs (anchor_entities et al + audience_scope) via
  `ResearchFlow._rederive_niche_context_dependents` so they stay consistent with the edit
  before Stage 2 consumes them.
- G2 patches are STRICTLY NON-DESTRUCTIVE: `audience_mapping.audience_segments` and
  `pain_point_analysis.pain_points` are NEVER mutated (pains reference segments by name;
  deleting a segment would orphan that reference). Exclusions/emphasis/pins are recorded
  onto `state.user_pain_scope` / `state.user_audience_scope`, consumed ONLY at the
  ideation allocation choke point (`UnifiedSolutionCrew._build_partition_cells`).

Both branches stamp `state.user_adjusted = True` and save the relevant stage checkpoint
(+ flush metadata so the scope fields round-trip through resume).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..models.research_state import AudienceScope, PainScope, ResearchState


class GatePatchError(ValueError):
    """A patch failed whitelist validation or referenced non-existent data.

    Callers (the `continue_from_gate` worker task) should treat this as a 400-equivalent:
    the gate must NOT advance and the checkpoint must be left untouched.
    """


class GatePatchPersistError(RuntimeError):
    """The patch was valid and applied to in-memory state, but the checkpoint write that
    persists it failed (Codex review finding 5). `CheckpointManager.save_stage` swallows
    write errors by design (ordinary pipeline stage saves must never abort the run) and
    returns False instead — apply_gate_patch raises this so the worker routes to
    notify_gate_failed (job reverted, retryable) instead of re-notifying success for an edit
    that a later resume would silently lose.
    """


class G1Patch(BaseModel):
    """Whitelist for a G1 (post-Stage-1) patch. Unknown keys rejected (extra='forbid')."""

    model_config = ConfigDict(extra="forbid")

    niche_description: Optional[str] = Field(default=None, max_length=2000)
    market_segments: Optional[list[str]] = Field(default=None, max_length=12)
    industry_boundaries: Optional[str] = Field(default=None, max_length=2000)
    user_target_audience: Optional[str] = Field(default=None, max_length=500)

    @field_validator("market_segments")
    @classmethod
    def _check_segment_lengths(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            for s in v:
                if len(s) > 120:
                    raise ValueError("each market_segments entry must be <=120 chars")
        return v


class G2PainScopePatch(BaseModel):
    """Nested `pain_scope` field of a G2 patch."""

    model_config = ConfigDict(extra="forbid")

    excluded_titles: list[str] = Field(default_factory=list)
    pinned_titles: list[str] = Field(default_factory=list)

    @field_validator("excluded_titles", "pinned_titles")
    @classmethod
    def _check_title_lengths(cls, v: list[str]) -> list[str]:
        # Mirrors GateG2PatchSchema.pain_scope.{excluded,pinned}_titles in backend/src/types/job.ts
        # (Codex review finding 14 — Pydantic/Zod caps must stay in lockstep, R4).
        for t in v:
            if len(t) > 500:
                raise ValueError("each pain_scope title must be <=500 chars")
        return v


class G2Patch(BaseModel):
    """Whitelist for a G2 (post-Stage-4) patch. Unknown keys rejected. NO add-segment in v1
    — `excluded_segments`/`segment_emphasis`/`primary_target_segment` must reference EXISTING
    `audience_mapping.audience_segments` entries (validated in `_apply_g2`, not here, since
    it needs `state` to check against).

    Field length caps mirror GateG2PatchSchema in backend/src/types/job.ts (Codex review
    finding 14 — the Pydantic layer previously had NO caps at all on these fields)."""

    model_config = ConfigDict(extra="forbid")

    user_target_audience: Optional[str] = Field(default=None, max_length=500)
    primary_target_segment: Optional[str] = Field(default=None, max_length=255)
    excluded_segments: Optional[list[str]] = None
    segment_emphasis: Optional[dict[str, str]] = None
    pain_scope: Optional[G2PainScopePatch] = None

    @field_validator("excluded_segments")
    @classmethod
    def _check_excluded_segment_lengths(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            for s in v:
                if len(s) > 255:
                    raise ValueError("each excluded_segments entry must be <=255 chars")
        return v

    @field_validator("segment_emphasis")
    @classmethod
    def _check_emphasis_values(cls, v: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
        if v:
            bad = {name: level for name, level in v.items() if level not in ("high", "low")}
            if bad:
                raise ValueError(f"segment_emphasis values must be 'high' or 'low': {bad}")
        return v


def apply_gate_patch(
    state: ResearchState,
    gate_stage: int,
    patch: dict[str, Any],
    flow: Optional[Any] = None,
) -> ResearchState:
    """Validate + apply a gate patch to `state` (mutated in place, also returned).

    Args:
        state: The ResearchFlow's ResearchState (already resumed from checkpoint).
        gate_stage: 1 (G1, post-Stage-1) or 4 (G2, post-Stage-4).
        patch: The raw patch dict (already Zod-validated on the backend; re-validated
            here against the Pydantic whitelist as the authoritative layer — R4).
        flow: The owning ResearchFlow. When provided: G1 re-derives niche-context
            dependents (one LLM call) and both branches save the updated stage
            checkpoint + flush metadata. When None (unit tests), validation/mutation
            still runs but nothing is persisted or re-derived.

    Raises:
        GatePatchError: unknown keys, invalid values, or a reference (segment/pain title)
            that does not exist in the current state. Never partially applies — validation
            happens before any mutation.
    """
    if gate_stage == 1:
        return _apply_g1(state, patch, flow)
    if gate_stage == 4:
        return _apply_g2(state, patch, flow)
    raise GatePatchError(f"No patch handler for gate_stage={gate_stage!r} (expected 1 or 4)")


def _apply_g1(state: ResearchState, patch: dict[str, Any], flow: Optional[Any]) -> ResearchState:
    if state.niche_context is None:
        raise GatePatchError("Cannot apply a G1 patch: state.niche_context is not set (Stage 1 has not run)")

    try:
        parsed = G1Patch.model_validate(patch)
    except ValidationError as e:
        raise GatePatchError(f"Invalid G1 patch: {e}") from e

    nc = state.niche_context
    changed_core = False
    if parsed.niche_description is not None:
        nc.niche_description = parsed.niche_description
        changed_core = True
    if parsed.market_segments is not None:
        nc.market_segments = parsed.market_segments
        changed_core = True
    if parsed.industry_boundaries is not None:
        nc.industry_boundaries = parsed.industry_boundaries
        changed_core = True
    if parsed.user_target_audience is not None:
        nc.user_target_audience = parsed.user_target_audience
        changed_core = True

    if changed_core and flow is not None:
        flow._rederive_niche_context_dependents(nc)

    state.user_adjusted = True

    if flow is not None:
        if not flow.checkpoint_mgr.save_stage("stage_1_niche_context", nc):
            raise GatePatchPersistError(
                "Failed to persist G1 patch: stage_1_niche_context checkpoint save failed"
            )

    return state


def _apply_g2(state: ResearchState, patch: dict[str, Any], flow: Optional[Any]) -> ResearchState:
    if state.audience_mapping is None:
        raise GatePatchError("Cannot apply a G2 patch: state.audience_mapping is not set (Stage 4 has not run)")

    try:
        parsed = G2Patch.model_validate(patch)
    except ValidationError as e:
        raise GatePatchError(f"Invalid G2 patch: {e}") from e

    am = state.audience_mapping
    existing_segment_names = {s.segment_name for s in am.audience_segments}

    if parsed.primary_target_segment is not None and parsed.primary_target_segment not in existing_segment_names:
        raise GatePatchError(
            f"primary_target_segment {parsed.primary_target_segment!r} does not match an existing audience segment"
        )

    if parsed.excluded_segments:
        unknown = [s for s in parsed.excluded_segments if s not in existing_segment_names]
        if unknown:
            raise GatePatchError(f"excluded_segments references unknown segment(s): {unknown}")

    if parsed.segment_emphasis:
        unknown = [s for s in parsed.segment_emphasis if s not in existing_segment_names]
        if unknown:
            raise GatePatchError(f"segment_emphasis references unknown segment(s): {unknown}")

    existing_pain_titles: set[str] = set()
    if state.pain_point_analysis:
        existing_pain_titles = {p.title for p in state.pain_point_analysis.pain_points}

    if parsed.pain_scope is not None:
        referenced = list(parsed.pain_scope.excluded_titles) + list(parsed.pain_scope.pinned_titles)
        unknown = [t for t in referenced if t not in existing_pain_titles]
        if unknown:
            raise GatePatchError(f"pain_scope references unknown pain title(s): {unknown}")
        overlap = set(parsed.pain_scope.excluded_titles) & set(parsed.pain_scope.pinned_titles)
        if overlap:
            raise GatePatchError(f"pain_scope cannot both exclude and pin the same title(s): {sorted(overlap)}")

    # Non-destructive: audience_mapping.audience_segments / pain_point_analysis.pain_points
    # are NEVER mutated here — only the scope overlays the ideation choke point reads.
    scope = state.user_audience_scope or AudienceScope()
    if parsed.excluded_segments is not None:
        scope.excluded_segments = parsed.excluded_segments
    if parsed.segment_emphasis is not None:
        scope.segment_emphasis = parsed.segment_emphasis
    if parsed.primary_target_segment is not None:
        scope.primary_target_segment = parsed.primary_target_segment
    state.user_audience_scope = scope

    if parsed.pain_scope is not None:
        pain_scope = state.user_pain_scope or PainScope()
        pain_scope.excluded_titles = parsed.pain_scope.excluded_titles
        pain_scope.pinned_titles = parsed.pain_scope.pinned_titles
        state.user_pain_scope = pain_scope

    if parsed.user_target_audience is not None and state.niche_context is not None:
        state.niche_context.user_target_audience = parsed.user_target_audience

    state.user_adjusted = True

    if flow is not None:
        if not flow.checkpoint_mgr.save_stage("stage_4_audience_mapping", am):
            raise GatePatchPersistError(
                "Failed to persist G2 patch: stage_4_audience_mapping checkpoint save failed"
            )
        # Flush metadata so user_pain_scope/user_audience_scope/user_adjusted (state fields,
        # not a stage file) round-trip through a later resume — mirrors idea_focus etc.
        flow.checkpoint_mgr.flush_metadata()

    return state
