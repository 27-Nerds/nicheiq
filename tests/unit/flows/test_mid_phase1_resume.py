"""R1/R2 pytest spike (Phase B pre-check — see plans/eager-meandering-feather.md).

Validates, BEFORE any stop_after_stage/gate machinery is built, that resuming from a
mid-Phase-1 checkpoint actually works:

- R1: a Stage-1-only checkpoint (the shape a future G1 stop would leave behind) resumes
  cleanly and the stage ladder re-enters at Stage 2 (nothing re-runs, nothing is skipped).
- R2: a G2-shaped checkpoint (stages 1-4 complete, current_stage=5 — the shape a future G2
  stop would leave behind) resumes with BOTH pain_point_analysis and audience_mapping
  present, and the ladder re-enters at Stage 5 without re-running stages 1-4.
- Cross-job fork semantics: resuming under a different job_id forks the checkpoint; the
  effective (possibly-forked) path lives at ``flow.checkpoint_mgr.checkpoint_folder``.
- Rewind interaction: a schema-drift stage-3 file prunes BOTH current_stage and
  completed_stages (stage 3 AND 4 correctly re-run); the quality-gate path (empty pain
  count) now does the same (Phase B cascade fix in checkpoint_manager.py) — stage 4's
  "already completed" marker is pruned too, so it re-runs against regenerated pains.
- Cost continuity: a saved cost_tracker.json round-trips through resume and accumulates.

Every checkpoint here is hand-built via CheckpointManager.save_stage(...) (the same code
path a real run uses), never via bespoke JSON — see test_resume_lost_fields.py /
test_selection_consistency.py for the established pattern this file follows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock

from nicheiq.config.settings import settings
from nicheiq.flows.checkpoint_manager import CHECKPOINT_SCHEMA_VERSION, CheckpointManager
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.pain_point import OpportunityLevel, PainPoint, PainPointAnalysisResult
from nicheiq.models.research_state import AudienceMappingResult, NicheContext, ResearchState
from nicheiq.models.social_content import SocialContentCollection, SocialPost
from nicheiq.utils.token_monitor import CostTracker

NICHE = "AI-powered inventory forecasting for boutique retailers"

# Every stage method the ladder in _execute_remaining_stages can dispatch to. Mocking all of
# them (never a subset) keeps every test hermetic regardless of which prerequisite checks
# happen to pass for the checkpoint shape under test.
STAGE_METHOD_NAMES = [
    "stage_1_validate_niche",
    "stage_2_search_and_discover",
    "stage_3_analyze_pain_points",
    "stage_4_audience_mapping",
    "stage_5_unified_solution_pipeline",
    "stage_6_seo_strategy",
    "stage_7_pricing_validation",
    "stage_8_traffic_monetization",
    "stage_9_market_sizing",
    "stage_10_solution_refinement",
    "stage_11_trend_longevity",
    "stage_12_refine_seo_scores",
    "stage_13_research_data_sources",
    "stage_14_generate_report",
]


def _mock_all_stages(flow, call_log, side_effects=None):
    """Replace every stage_N_* method on `flow` with a Mock that appends its name to
    `call_log` (in invocation order) and optionally runs an extra side effect."""
    side_effects = side_effects or {}

    for name in STAGE_METHOD_NAMES:
        extra = side_effects.get(name)

        def _fn(*_a, _name=name, _extra=extra, **_k):
            call_log.append(_name)
            if _extra:
                _extra()

        setattr(flow, name, Mock(side_effect=_fn))
    return flow


def _niche_context():
    return NicheContext(
        niche_input=NICHE,
        niche_description="Boutique retailers need better demand-forecasting tools.",
        market_segments=["Independent boutiques", "Small chain retailers"],
        industry_boundaries="Retail inventory software; excludes enterprise ERP suites.",
    )


def _social_content(n=3):
    posts = [
        SocialPost(
            post_id=f"p{i}",
            platform="hackernews",
            title=f"Inventory pain point {i}",
            body="We keep overordering stock and it kills our margin every quarter.",
            author=f"user{i}",
            url=f"https://example.com/{i}",
            score=10,
            num_responses=2,
            created_utc=datetime.now(timezone.utc),
        )
        for i in range(n)
    ]
    return SocialContentCollection(generic_posts=posts)


def _pain_point_analysis(pain_points=None):
    if pain_points is None:
        pain_points = [
            PainPoint(
                title="Manual stock counts eat a full day",
                description="Owners spend a full day each week counting inventory by hand.",
                mention_count=12,
                severity_score=0.8,
                commercial_intent=0.7,
                opportunity_level=OpportunityLevel.HIGH,
                representative_quotes=["I lose a whole Sunday to inventory counts"],
            )
        ]
    return PainPointAnalysisResult(
        niche=NICHE,
        pain_points=pain_points,
        total_mentions=12,
        top_categories=["inventory"],
        analysis_summary="Owners struggle with manual, error-prone inventory tracking.",
    )


def _audience_mapping():
    return AudienceMappingResult(
        primary_target_segment="Independent boutique owners",
        segment_prioritization_rationale="Highest pain, fastest sales cycle.",
        community_hubs=["r/smallbusiness"],
        content_preferences="Short how-to videos on stock counting pain",
        messaging_frameworks=["Stop guessing, start forecasting"],
        tools_currently_used=["Spreadsheets"],
        frustrations_with_existing=["No real forecasting, just gut feel"],
        recommended_channels=["Instagram", "Email"],
    )


def _write_stage1_checkpoint(job_id):
    """Stage-1-only checkpoint: the shape a future G1 stop leaves behind."""
    state = ResearchState()
    state.niche_context = _niche_context()
    state.current_stage = 2
    cm = CheckpointManager(niche_description=NICHE, state=state, job_id=job_id)
    cm.save_stage("stage_1_niche_context", state.niche_context)
    return cm.checkpoint_folder


def _write_g2_checkpoint(job_id, current_stage=5, pain_points=None, corrupt_stage3=False):
    """G2-shaped checkpoint: stages 1-4 complete, the shape a future G2 stop leaves behind."""
    state = ResearchState()
    state.niche_context = _niche_context()
    state.social_content = _social_content()
    state.pain_point_analysis = _pain_point_analysis(pain_points)
    state.audience_mapping = _audience_mapping()
    state.current_stage = current_stage
    cm = CheckpointManager(niche_description=NICHE, state=state, job_id=job_id)
    cm.save_stage("stage_1_niche_context", state.niche_context)
    cm.save_stage("stage_2_social_content", state.social_content)
    cm.save_stage("stage_3_pain_points", state.pain_point_analysis)
    cm.save_stage("stage_4_audience_mapping", state.audience_mapping)
    folder = cm.checkpoint_folder
    if corrupt_stage3:
        # Schema-valid JSON (dict), but does not satisfy PainPointAnalysisResult's required
        # fields — triggers the reconstruction-failure (schema-drift) rewind, not a plain
        # JSON-parse failure (which validate_stage_file would catch earlier and just skip).
        (folder / "stage_3_pain_points.json").write_text(
            json.dumps({"drifted_schema": True, "unexpected_field": "x"})
        )
    return folder


class TestR1Stage1OnlyResume:
    """R1 — mid-Phase-1 resume is novel; validate before building the G1 gate."""

    def test_stage1_only_checkpoint_resumes_into_stage2(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = _write_stage1_checkpoint(job_id="job-r1")

        meta = json.loads((folder / "metadata.json").read_text())
        assert meta["current_stage"] == 2
        assert meta["completed_stages"] == ["stage_1_niche_context"]
        assert meta["schema_version"] == CHECKPOINT_SCHEMA_VERSION

        flow = ResearchFlow(niche_description=NICHE, job_id="job-r1")
        assert flow.resume_from_checkpoint(folder) is True

        assert flow.state.niche_context is not None
        assert flow.state.niche_context.niche_description == _niche_context().niche_description
        assert flow.state.current_stage == 2
        assert flow._validate_stage_prerequisites(2) is True

        call_log: list[str] = []
        _mock_all_stages(flow, call_log)
        flow._execute_remaining_stages()

        assert "stage_1_validate_niche" not in call_log  # nothing re-runs Stage 1
        assert call_log[0] == "stage_2_search_and_discover"  # ladder re-enters at 2


class TestR2G2ShapedResume:
    """R2 — Stage-4-not-skipped on G2 resume: pains+audience both present at the stop."""

    def test_g2_checkpoint_resumes_into_stage5_with_pains_and_audience(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = _write_g2_checkpoint(job_id="job-r2", current_stage=5)
        meta = json.loads((folder / "metadata.json").read_text())
        assert meta["current_stage"] == 5
        assert meta["completed_stages"] == [
            "stage_1_niche_context",
            "stage_2_social_content",
            "stage_3_pain_points",
            "stage_4_audience_mapping",
        ]

        flow = ResearchFlow(niche_description=NICHE, job_id="job-r2")
        assert flow.resume_from_checkpoint(folder) is True

        assert flow.state.pain_point_analysis is not None
        assert flow.state.pain_point_analysis.pain_points  # non-empty
        assert flow.state.audience_mapping is not None
        assert flow.state.audience_mapping.primary_target_segment == "Independent boutique owners"
        assert flow.state.current_stage == 5

        call_log: list[str] = []
        _mock_all_stages(flow, call_log)
        flow._execute_remaining_stages()

        assert "stage_1_validate_niche" not in call_log
        assert "stage_2_search_and_discover" not in call_log
        assert "stage_3_analyze_pain_points" not in call_log
        assert "stage_4_audience_mapping" not in call_log  # completed_stages gating: not re-run
        assert "stage_5_unified_solution_pipeline" in call_log  # ladder attempts Stage 5

    def test_replay_progress_fires_unless_skip_bulk_replay(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = _write_g2_checkpoint(job_id="job-r2-replay", current_stage=5)

        # Mode 1: default (skip_bulk_replay=False) -> bulk replay fires once.
        flow = ResearchFlow(niche_description=NICHE, job_id="job-r2-replay")
        assert flow.resume_from_checkpoint(folder) is True
        _mock_all_stages(flow, [])
        replay_calls: list[int] = []
        flow._replay_completed_stages_progress = Mock(side_effect=lambda *_a, **_k: replay_calls.append(1))
        flow._execute_remaining_stages()
        assert len(replay_calls) == 1

        # Mode 2: skip_bulk_replay=True -> no bulk replay (interactive Phase-2 continuation).
        flow2 = ResearchFlow(niche_description=NICHE, job_id="job-r2-replay")
        assert flow2.resume_from_checkpoint(folder) is True
        _mock_all_stages(flow2, [])
        replay_calls2: list[int] = []
        flow2._replay_completed_stages_progress = Mock(side_effect=lambda *_a, **_k: replay_calls2.append(1))
        flow2._execute_remaining_stages(skip_bulk_replay=True)
        assert len(replay_calls2) == 0


class TestCrossJobForkSemantics:
    """Codex 10: resuming under a DIFFERENT job_id forks the checkpoint. Phase B's
    continue_from_gate must report the EFFECTIVE post-resume path — that is
    ``flow.checkpoint_mgr.checkpoint_folder`` (a pathlib.Path), NOT the path it was given.
    It equals the input path for a same-job resume and the fresh forked folder otherwise."""

    def test_resume_under_different_job_id_forks_checkpoint(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        source_folder = _write_stage1_checkpoint(job_id="job-src")

        fork_flow = ResearchFlow(niche_description=NICHE, job_id="job-fork")
        assert fork_flow.resume_from_checkpoint(source_folder) is True

        effective_path = fork_flow.checkpoint_mgr.checkpoint_folder
        assert effective_path != source_folder
        assert effective_path.exists()
        assert effective_path.name.startswith(
            f"checkpoint_{fork_flow.checkpoint_mgr._get_niche_slug()}_job-fork_"
        )

        forked_meta = json.loads((effective_path / "metadata.json").read_text())
        assert forked_meta["job_id"] == "job-fork"
        assert forked_meta["forked_from"] == source_folder.name

        # Source untouched — still owned by job-src.
        source_meta = json.loads((source_folder / "metadata.json").read_text())
        assert source_meta["job_id"] == "job-src"

        # State restored via the fork.
        assert fork_flow.state.niche_context is not None
        assert fork_flow.state.current_stage == 2


class TestRewindInteractionSchemaDriftVsQualityGate:
    """Codex 5 / Phase B cascade fix: two different rewind mechanisms fire on a poisoned
    Stage-3 checkpoint file. Both lower current_stage to 3 AND prune
    metadata['completed_stages'] the same way — the quality-gate path used to leave stage 4's
    'already completed' marker in place (silently suppressing its re-run against stale
    audience data); checkpoint_manager.py's quality-gate rewind now mirrors the schema-drift
    pruning cascade so G2 gate resumes cannot reuse audience_mapping computed against
    discarded pains."""

    def test_schema_drift_prunes_completed_stages_and_reruns_stage3_and_4(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = _write_g2_checkpoint(job_id="job-drift", current_stage=5, corrupt_stage3=True)

        flow = ResearchFlow(niche_description=NICHE, job_id="job-drift")
        assert flow.resume_from_checkpoint(folder) is True

        assert flow.state.pain_point_analysis is None  # cleared by the reconstruction rewind
        assert flow.state.current_stage == 3

        completed = flow.checkpoint_mgr.get_completed_stages()
        assert completed == ["stage_1_niche_context", "stage_2_social_content"]
        assert "stage_3_pain_points" not in completed
        assert "stage_4_audience_mapping" not in completed  # pruned too — cascades downstream

        call_log: list[str] = []

        def _regenerate_pains():
            flow.state.pain_point_analysis = _pain_point_analysis()

        _mock_all_stages(
            flow, call_log, side_effects={"stage_3_analyze_pain_points": _regenerate_pains}
        )
        flow._execute_remaining_stages()

        assert "stage_3_analyze_pain_points" in call_log  # always re-attempted at current<=3
        assert "stage_4_audience_mapping" in call_log  # NOT suppressed — the safe path

    def test_quality_gate_prunes_stage4_marker_and_reruns_stage4(self, tmp_path, monkeypatch):
        """FIXED behavior (was a discrepancy pre-Phase-B): the below-minimum-pain-count
        quality gate now prunes metadata['completed_stages'] the same way the schema-drift
        path does. Stage 4's 'already completed' marker is removed, so it re-runs against
        the regenerated pains instead of reusing stale audience_mapping."""
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = _write_g2_checkpoint(job_id="job-qgate", current_stage=5, pain_points=[])

        flow = ResearchFlow(niche_description=NICHE, job_id="job-qgate")
        assert flow.resume_from_checkpoint(folder) is True

        assert flow.state.pain_point_analysis is None  # discarded by the quality gate
        assert flow.state.current_stage == 3  # same rewind target as schema-drift

        completed = flow.checkpoint_mgr.get_completed_stages()
        # Fixed: cascade pruning matches schema-drift — stage 3 and 4 markers both removed.
        assert completed == ["stage_1_niche_context", "stage_2_social_content"]
        assert "stage_3_pain_points" not in completed
        assert "stage_4_audience_mapping" not in completed

        call_log: list[str] = []

        def _regenerate_pains():
            flow.state.pain_point_analysis = _pain_point_analysis()

        _mock_all_stages(
            flow, call_log, side_effects={"stage_3_analyze_pain_points": _regenerate_pains}
        )
        flow._execute_remaining_stages()

        assert "stage_3_analyze_pain_points" in call_log  # unconditionally re-attempted
        assert "stage_4_audience_mapping" in call_log  # no longer suppressed by a stale marker


class TestG2GateStopFlushesCheckpoint:
    """Codex review finding 1 (REGRESSION): the G2 gate stop must flush current_stage=5 to
    metadata.json BEFORE returning. In the real Stage-3 parallel-execution path,
    save_stage("stage_4_audience_mapping", ...) (research_flow.py:3772) runs BEFORE
    self.state.current_stage is advanced to 5 (:3784) — so metadata.json's current_stage is
    stamped with the stale pre-advance value unless the G2 stop explicitly re-flushes.
    Without the fix, a G2-stopped checkpoint reloads at the stale current_stage and re-runs
    Stage 3 (pains) + Stage 4 (audience) on continuation (duplicate LLM cost, identifier
    drift vs. the validated G2 patch)."""

    def test_g2_stop_flushes_current_stage_5_before_returning(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        # Stage-2-complete checkpoint (current_stage=3) — the shape BEFORE stage 3/4 run.
        state = ResearchState()
        state.niche_context = _niche_context()
        state.social_content = _social_content()
        state.current_stage = 3
        cm = CheckpointManager(niche_description=NICHE, state=state, job_id="job-g2-flush")
        cm.save_stage("stage_1_niche_context", state.niche_context)
        cm.save_stage("stage_2_social_content", state.social_content)
        folder = cm.checkpoint_folder

        flow = ResearchFlow(niche_description=NICHE, job_id="job-g2-flush")
        assert flow.resume_from_checkpoint(folder) is True
        assert flow.state.current_stage == 3

        def _run_stage_3():
            # Mirrors research_flow.py's real ordering: save_stage() calls happen BEFORE the
            # in-memory current_stage advance — the exact sequencing this test pins.
            flow.state.pain_point_analysis = _pain_point_analysis()
            flow.checkpoint_mgr.save_stage("stage_3_pain_points", flow.state.pain_point_analysis)
            flow.state.audience_mapping = _audience_mapping()
            flow.checkpoint_mgr.save_stage("stage_4_audience_mapping", flow.state.audience_mapping)
            flow.state.current_stage = 5  # advanced AFTER both saves, in-memory only

        _mock_all_stages(flow, [], side_effects={"stage_3_analyze_pain_points": _run_stage_3})

        result = flow._execute_remaining_stages(stop_after_stage=4)
        artifact = json.loads(result)
        assert artifact.get("type") == "audience_mapping_gate"

        meta = json.loads((flow.checkpoint_mgr.checkpoint_folder / "metadata.json").read_text())
        assert meta["current_stage"] == 5
        assert meta["completed_stages"] == [
            "stage_1_niche_context",
            "stage_2_social_content",
            "stage_3_pain_points",
            "stage_4_audience_mapping",
        ]

        # Continuation from THIS checkpoint must not re-run stages 3/4.
        flow2 = ResearchFlow(niche_description=NICHE, job_id="job-g2-flush")
        assert flow2.resume_from_checkpoint(flow.checkpoint_mgr.checkpoint_folder) is True
        assert flow2.state.current_stage == 5
        assert flow2.state.pain_point_analysis is not None
        assert flow2.state.audience_mapping is not None

        call_log2: list[str] = []
        _mock_all_stages(flow2, call_log2)
        flow2._execute_remaining_stages()
        assert "stage_3_analyze_pain_points" not in call_log2
        assert "stage_4_audience_mapping" not in call_log2


class TestCostContinuity:
    """A saved cost_tracker.json round-trips through resume and further usage accumulates
    on top (cumulative Phase-1 + Phase-2 cost reporting depends on this)."""

    def test_cost_tracker_restored_and_accumulates_after_resume(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        state = ResearchState()
        state.niche_context = _niche_context()
        state.current_stage = 2
        cm = CheckpointManager(niche_description=NICHE, state=state, job_id="job-cost")
        cm.save_stage("stage_1_niche_context", state.niche_context)

        tracker = CostTracker()
        tracker.record_llm_usage(
            "Niche Context", {"prompt_tokens": 1000, "completion_tokens": 200, "model": "gpt-4o-mini"}
        )
        cm.save_cost_breakdown(tracker.export_state())

        flow = ResearchFlow(niche_description=NICHE, job_id="job-cost")
        assert flow.resume_from_checkpoint(cm.checkpoint_folder) is True

        assert len(flow.cost_tracker.stage_usages) == 1
        assert flow.cost_tracker.stage_usages[0].stage == "Niche Context"
        restored_cost = flow.cost_tracker.get_summary()["total_cost"]
        assert restored_cost > 0

        flow.cost_tracker.record_llm_usage(
            "Stage 2", {"prompt_tokens": 500, "completion_tokens": 100, "model": "gpt-4o-mini"}
        )
        assert len(flow.cost_tracker.stage_usages) == 2
        assert flow.cost_tracker.get_summary()["total_cost"] > restored_cost
