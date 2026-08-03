"""Phase-1 state fields must survive the awaiting-selection → Phase-2 / --resume boundary.

Regression guard for the `idea_focus`-class of bugs: fields set in stages 1-5 and read by the
report/preview after resume were reset to their model default because they round-tripped through
neither the stage-payload nor the metadata channel.
"""

from nicheiq.config.settings import settings
from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.models.research_state import (
    AudienceScope,
    NicheContext,
    NicheDifficultyVerdict,
    PainScope,
    ResearchState,
)


def _niche_ctx():
    return NicheContext(
        niche_input="x", niche_description="x desc", market_segments=["a"], industry_boundaries="b"
    )


def test_phase1_fields_survive_checkpoint_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    # Save side: a run populates the previously-lost fields, then checkpoints.
    save_state = ResearchState()
    save_state.niche_context = _niche_ctx()
    save_state.current_stage = 5
    save_state.idea_focus = "novelty"
    save_state.idea_coverage_caveats = ["Very broad audience — narrow it."]
    save_state.pipeline_degradations = ["Quote stance filter unavailable for 3/24 pain points."]
    save_state.niche_drift_telemetry = {"anchored_pct": 12, "dropped": 0}
    save_state.skipped_stages = [10.0, 11.0]
    save_state.sources_searched = {"reddit": 26, "hackernews": 14}
    save_state.niche_incumbent_map = [
        {"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling", "gap": "no galleries",
         "source": "web"}
    ]
    save_state.niche_wallet_brief = {"wallet_class": "mixed", "evidence": "most tools $10-30/mo",
                                      "free_density": "few free routes"}
    save_state.niche_data_menu_text = "- Public permit records (city open-data portal)"
    save_state.niche_dissatisfaction_text = ""  # probed, found nothing — must round-trip as '', not None
    save_state.idea_portfolio_summary = "AlphaTool and BetaTracker both show moderate market fit."
    # The partition itself must survive: regenerate/seed batches REUSE it so family_id (the
    # thesis identity) stays stable instead of being re-labeled per batch.
    save_state.buyer_job_partition = {
        "source": "llm", "degraded": False, "degradation_reason": None,
        "families": [{"family_id": "f1", "buyer": "Photographer",
                      "triggering_job": "Cull a shoot", "economic_outcome": "Studio budget",
                      "display_label": "Cull a shoot", "member_pain_ids": ["Culling is slow"],
                      "inferred": False}],
    }
    save_state.idea_theses = {
        "family_source": "llm",
        "theses": [{"family_id": "f1", "display_label": "Cull a shoot",
                    "members": [{"name": "AlphaTool", "winning_angle": "vertical_workflow"}],
                    "lead_idea_name": "AlphaTool",
                    "incumbent_status": "occupied", "incumbent_vendors": ["Aftershoot"],
                    "fatal_assumptions": []}],
        "uncovered_families": [{"family_id": "f2", "display_label": "Deliver galleries",
                                "member_pain_ids": ["Galleries expire"],
                                "reason": "no_cell_allocated", "reason_detail": "budget_exhausted"}],
        "unassigned": [],
    }
    save_state.user_pain_scope = PainScope(excluded_titles=["Noisy pain"], pinned_titles=["Keep this"])
    save_state.user_audience_scope = AudienceScope(
        excluded_segments=["Enterprise buyers"], segment_emphasis={"Solo founders": "high"},
        primary_target_segment="Solo founders",
    )
    save_state.user_adjusted = True
    verdict = NicheDifficultyVerdict(
        difficulty_level="low",
        software_addressability=0.74,
        headline="Software Fit: Strong",
        narrative_summary="Software can own most of the workflow pains.",
    )
    save_state.niche_difficulty_verdict = verdict

    cm_save = CheckpointManager(
        niche_description="x", state=save_state, allowed_project_types=None, job_id="jobA"
    )
    cm_save.save_stage("stage_1_niche_context", save_state.niche_context)   # flushes metadata
    cm_save.save_stage("stage_5_niche_difficulty", verdict)                 # stage payload
    folder = cm_save.checkpoint_folder

    # Load side (fresh state, as Phase 2 / --resume does):
    load_state = ResearchState()
    cm_load = CheckpointManager(
        niche_description="x", state=load_state, allowed_project_types=None, job_id="jobA"
    )
    assert cm_load.load_checkpoint_folder(folder) is True

    assert load_state.idea_focus == "novelty"          # NOT clobbered back to "auto"
    assert load_state.idea_coverage_caveats == ["Very broad audience — narrow it."]
    assert load_state.pipeline_degradations == ["Quote stance filter unavailable for 3/24 pain points."]
    assert load_state.niche_drift_telemetry == {"anchored_pct": 12, "dropped": 0}
    assert load_state.skipped_stages == [10.0, 11.0]
    assert load_state.sources_searched == {"reddit": 26, "hackernews": 14}
    assert load_state.niche_incumbent_map == [
        {"name": "Aftershoot", "pricing": "$29/mo", "focus": "AI culling", "gap": "no galleries",
         "source": "web"}
    ]
    assert load_state.niche_wallet_brief == {
        "wallet_class": "mixed", "evidence": "most tools $10-30/mo", "free_density": "few free routes"
    }
    assert load_state.niche_data_menu_text == "- Public permit records (city open-data portal)"
    assert load_state.niche_dissatisfaction_text == ""  # not None — the '' round-tripped, not just truthy text
    assert load_state.idea_portfolio_summary == (
        "AlphaTool and BetaTracker both show moderate market fit."
    )
    assert load_state.idea_theses == save_state.idea_theses
    assert load_state.buyer_job_partition == save_state.buyer_job_partition
    assert load_state.niche_difficulty_verdict is not None
    assert load_state.niche_difficulty_verdict.difficulty_level == "low"
    assert load_state.niche_difficulty_verdict.headline == "Software Fit: Strong"
    assert load_state.user_pain_scope is not None
    assert load_state.user_pain_scope.excluded_titles == ["Noisy pain"]
    assert load_state.user_pain_scope.pinned_titles == ["Keep this"]
    assert load_state.user_audience_scope is not None
    assert load_state.user_audience_scope.excluded_segments == ["Enterprise buyers"]
    assert load_state.user_audience_scope.segment_emphasis == {"Solo founders": "high"}
    assert load_state.user_audience_scope.primary_target_segment == "Solo founders"
    assert load_state.user_adjusted is True


def test_idea_focus_defaults_auto_when_never_set(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)
    save_state = ResearchState()
    save_state.niche_context = _niche_ctx()
    cm = CheckpointManager(niche_description="x", state=save_state, allowed_project_types=None, job_id="jobB")
    cm.save_stage("stage_1_niche_context", save_state.niche_context)

    load_state = ResearchState()
    cm2 = CheckpointManager(niche_description="x", state=load_state, allowed_project_types=None, job_id="jobB")
    assert cm2.load_checkpoint_folder(cm.checkpoint_folder) is True
    assert load_state.idea_focus == "auto"


# ── Durable coverage guard: every ResearchState field must be persisted or explicitly transient ──

# state attrs restored from a stage-payload file (checkpoint_manager stage_mapping values)
_PERSISTED_VIA_STAGE = {
    "niche_context", "social_content", "pain_point_analysis", "audience_mapping",
    "competitor_mentions_formatted", "idea_generation", "competitive_analysis",
    "solution_selection", "niche_difficulty_verdict", "seo_expanded_keywords",
    "seo_validation_results", "seo_enriched_keywords", "seo_strategy_report",
    "keyword_validation_results", "pricing_strategies", "traffic_monetization_results",
    "market_sizing", "solution_refinement", "trend_longevity", "seo_enrichment",
    "data_source_research",
}
# fields written to + restored from metadata.json
_PERSISTED_VIA_METADATA = {
    "current_stage", "errors", "started_at", "allowed_project_types",
    "social_content_quality_tier", "pain_point_quality_tier", "pain_point_confidence_score",
    "filtering_stats", "completed_stages", "fallback_stages", "social_content_metrics",
    "seeded_from_catalog", "stage_completion_timestamps", "idea_focus",
    "idea_coverage_caveats", "pipeline_degradations", "niche_drift_telemetry", "skipped_stages",
    "sources_searched", "idea_ruled_out", "idea_funnel_counts", "idea_cell_allocation",
    "idea_overlap_groups", "idea_theses", "buyer_job_partition",
    "niche_incumbent_map", "niche_wallet_brief", "idea_portfolio_summary",
    "user_pain_scope", "user_audience_scope", "user_adjusted",
    "niche_data_menu_text", "niche_dissatisfaction_text",
}
# intentionally NOT persisted (re-derived, terminal, unused, or re-set on construction)
_TRANSIENT = {
    "job_id", "search_queries", "cost_summary", "final_report", "seed_keywords",
    "completed_at", "competitive_enhancements", "keyword_validation",
}


def test_every_research_state_field_is_persisted_or_transient():
    """If this fails, a newly-added ResearchState field is not wired into checkpoint round-trip.
    Either persist it (metadata whitelist or a stage payload) and add it to the matching set
    above, or add it to _TRANSIENT if it genuinely need not survive resume."""
    covered = _PERSISTED_VIA_STAGE | _PERSISTED_VIA_METADATA | _TRANSIENT
    all_fields = set(ResearchState.model_fields)
    uncovered = all_fields - covered
    assert not uncovered, (
        f"ResearchState fields not wired into checkpoint round-trip: {sorted(uncovered)}. "
        f"Persist them (see checkpoint_manager _update_checkpoint_metadata / stage_mapping) or "
        f"add to _TRANSIENT."
    )
