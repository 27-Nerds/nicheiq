"""Phase B: `stop_after_stage` guided-mode gate stops (G1 = after Stage 1, G2 = after Stage 4).

Distinct from `stop_after_phase` (which materializes a Phase-1 preview report): a gate stop
must NOT materialize a preview — the run isn't done with Phase 1 yet, it's paused mid-flight
for the user to review/patch and then continue. Covers the test matrix item "stop_after_stage
returns at 1 and 4 (no preview materialized)".
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock

from nicheiq.config.settings import settings
from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.pain_point import OpportunityLevel, PainPoint, PainPointAnalysisResult
from nicheiq.models.research_state import AudienceMappingResult, NicheContext, ResearchState
from nicheiq.models.social_content import SocialContentCollection, SocialPost

NICHE = "AI-powered inventory forecasting for boutique retailers"

STAGE_METHOD_NAMES = [
    "stage_1_validate_niche",
    "stage_2_search_and_discover",
    "stage_3_analyze_pain_points",
    "stage_4_audience_mapping",
    "stage_5_unified_solution_pipeline",
    "stage_6_seo_strategy",
]


def _mock_all_stages(flow, call_log, side_effects=None):
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


def _social_content():
    return SocialContentCollection(generic_posts=[
        SocialPost(
            post_id="p1", platform="hackernews", title="Inventory pain",
            body="We keep overordering stock and it kills our margin.", author="user1",
            url="https://example.com/1", score=10, num_responses=2,
            created_utc=datetime.now(timezone.utc),
        )
    ])


def _pain_point_analysis():
    return PainPointAnalysisResult(
        niche=NICHE,
        pain_points=[
            PainPoint(
                title="Manual stock counts eat a full day",
                description="Owners spend a full day each week counting inventory by hand.",
                mention_count=12,
                severity_score=0.8,
                commercial_intent=0.7,
                opportunity_level=OpportunityLevel.HIGH,
                representative_quotes=["I lose a whole Sunday to inventory counts"],
            )
        ],
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


class TestStopAfterStage1G1:
    def test_fresh_run_stops_after_stage_1_no_preview(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        flow = ResearchFlow(niche_description=NICHE, job_id="job-g1")
        call_log: list[str] = []

        def _set_niche_context():
            flow.state.niche_context = _niche_context()
            flow.state.current_stage = 2

        _mock_all_stages(flow, call_log, side_effects={"stage_1_validate_niche": _set_niche_context})
        flow._materialize_preview_report = Mock(side_effect=AssertionError(
            "a G1 gate stop must never materialize a preview report"))

        result = flow._execute_remaining_stages(stop_after_stage=1)

        assert call_log == ["stage_1_validate_niche"]
        assert "stage_2_search_and_discover" not in call_log
        flow._materialize_preview_report.assert_not_called()
        # Cost breakdown persisted so a later continue_from_gate reports cumulative cost.
        assert (flow.checkpoint_mgr.checkpoint_folder / "cost_tracker.json").exists()
        # Returns the Stage-1 artifact (JSON string), not a report path.
        artifact = json.loads(result)
        assert artifact.get("type") == "niche_validation"
        assert artifact.get("niche_description") == _niche_context().niche_description

    def test_returns_at_stage_1_via_run_with_resume(self, tmp_path, monkeypatch):
        """run_with_resume threads stop_after_stage through to _execute_remaining_stages on
        BOTH the resume and fresh-run branches."""
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        flow = ResearchFlow(niche_description=NICHE, job_id="job-g1b")
        call_log: list[str] = []

        def _set_niche_context():
            flow.state.niche_context = _niche_context()
            flow.state.current_stage = 2

        _mock_all_stages(flow, call_log, side_effects={"stage_1_validate_niche": _set_niche_context})
        flow._materialize_preview_report = Mock(side_effect=AssertionError("must not be called"))

        flow.run_with_resume(auto_resume=True, stop_after_stage=1)

        assert call_log == ["stage_1_validate_niche"]
        flow._materialize_preview_report.assert_not_called()


class TestStopAfterStage4G2:
    def _write_stage1_checkpoint(self, job_id):
        state = ResearchState()
        state.niche_context = _niche_context()
        state.current_stage = 2
        cm = CheckpointManager(niche_description=NICHE, state=state, job_id=job_id)
        cm.save_stage("stage_1_niche_context", state.niche_context)
        return cm.checkpoint_folder

    def test_resumed_run_stops_after_stage_4_no_preview(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = self._write_stage1_checkpoint(job_id="job-g2")
        flow = ResearchFlow(niche_description=NICHE, job_id="job-g2")
        assert flow.resume_from_checkpoint(folder) is True

        call_log: list[str] = []

        def _set_social_content():
            flow.state.social_content = _social_content()
            flow.state.current_stage = 3

        def _set_pains():
            flow.state.pain_point_analysis = _pain_point_analysis()
            flow.state.current_stage = 4

        def _set_audience():
            flow.state.audience_mapping = _audience_mapping()
            flow.state.current_stage = 5

        _mock_all_stages(flow, call_log, side_effects={
            "stage_2_search_and_discover": _set_social_content,
            "stage_3_analyze_pain_points": _set_pains,
            "stage_4_audience_mapping": _set_audience,
        })
        flow._materialize_preview_report = Mock(side_effect=AssertionError(
            "a G2 gate stop must never materialize a preview report"))

        result = flow._execute_remaining_stages(stop_after_stage=4)

        assert call_log == [
            "stage_2_search_and_discover", "stage_3_analyze_pain_points", "stage_4_audience_mapping",
        ]
        assert "stage_5_unified_solution_pipeline" not in call_log
        flow._materialize_preview_report.assert_not_called()

        artifact = json.loads(result)
        assert artifact.get("type") == "audience_mapping_gate"
        assert artifact.get("pains") and artifact["pains"][0]["title"] == "Manual stock counts eat a full day"
        assert artifact.get("primary_target") == "Independent boutique owners"

    def test_degenerate_g2_skips_gate_and_falls_through(self, tmp_path, monkeypatch):
        """Codex review finding 2 (BLOCKER): when NEITHER pain analysis nor audience mapping
        survive Stage 3/4, _build_g2_gate_artifact returns None — stopping here would produce
        an unusable AWAITING_GATE with an empty {} artifact (dead-end gate loop). The ladder
        must skip the G2 stop instead and continue toward the next bound (stop_after_phase=1,
        exactly as worker/tasks.py's continue_from_gate now passes to cap the fallthrough)."""
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        folder = self._write_stage1_checkpoint(job_id="job-g2-degenerate")
        flow = ResearchFlow(niche_description=NICHE, job_id="job-g2-degenerate")
        assert flow.resume_from_checkpoint(folder) is True

        call_log: list[str] = []

        def _set_social_content():
            flow.state.social_content = _social_content()
            flow.state.current_stage = 3

        # Stage 3 and Stage 4 both fail to produce data — pain_point_analysis and
        # audience_mapping stay None (the degenerate case).
        _mock_all_stages(flow, call_log, side_effects={
            "stage_2_search_and_discover": _set_social_content,
        })
        flow._materialize_preview_report = Mock(return_value=None)

        result = flow._execute_remaining_stages(stop_after_stage=4, stop_after_phase=1)

        # No unusable {} gate artifact was returned — the gate never stopped.
        assert result == ""
        flow._materialize_preview_report.assert_called_once()
        # Stage 3 was attempted (prerequisites met via social_content); Stage 4/5 were
        # skipped by their own unmet-prerequisite checks, not suppressed by a stuck gate.
        assert "stage_3_analyze_pain_points" in call_log
        assert flow.state.pain_point_analysis is None
        assert flow.state.audience_mapping is None


class TestG2GateArtifactSizeCap:
    """Codex review finding 3 (AMEND): the first truncation in _build_g2_gate_artifact caps
    LIST LENGTH (pains[:40], segments[:10]) but not per-item field length — a run with
    unusually long pain titles or segment names must still fit under 16KiB after a hard
    second check. The artifact must never be emitted oversized."""

    def test_size_cap_never_emits_oversized_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
        monkeypatch.setattr(settings, "checkpoint_enabled", True)

        flow = ResearchFlow(niche_description=NICHE, job_id="job-g2-size")
        long_title = "A" * 800
        pain_points = [
            PainPoint(
                title=f"{long_title} {i}",
                description="desc",
                mention_count=1,
                severity_score=0.5,
                commercial_intent=0.5,
                opportunity_level=OpportunityLevel.MEDIUM,
                representative_quotes=["quote"],
            )
            for i in range(60)
        ]
        flow.state.pain_point_analysis = PainPointAnalysisResult(
            niche=NICHE, pain_points=pain_points, total_mentions=60,
            top_categories=["x"], analysis_summary="summary",
        )
        flow.state.audience_mapping = _audience_mapping()

        artifact = flow._build_g2_gate_artifact()

        assert artifact is not None
        serialized = json.dumps(artifact)
        assert len(serialized) <= 16384
        # Still usable — at least one pain survives the last-resort floor.
        assert len(artifact["pains"]) >= 1
