"""Phase B: `flows/gate_patches.py::apply_gate_patch` — G1/G2 whitelist validation +
mutation contract. Covers the test matrix item "apply_gate_patch whitelists accept/reject +
G1 re-derivation called".
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from nicheiq.flows.gate_patches import GatePatchError, GatePatchPersistError, apply_gate_patch
from nicheiq.models.pain_point import OpportunityLevel, PainPoint, PainPointAnalysisResult
from nicheiq.models.research_state import AudienceMappingResult, AudienceSegment, NicheContext, ResearchState

NICHE = "AI-powered inventory forecasting for boutique retailers"


def _niche_context():
    return NicheContext(
        niche_input=NICHE,
        niche_description="Boutique retailers need better demand-forecasting tools.",
        market_segments=["Independent boutiques", "Small chain retailers"],
        industry_boundaries="Retail inventory software; excludes enterprise ERP suites.",
    )


def _pain(title, **kw):
    base = dict(
        title=title, description=f"{title} description", mention_count=5,
        severity_score=0.6, commercial_intent=0.5, opportunity_level=OpportunityLevel.MEDIUM,
        representative_quotes=["quote"],
    )
    base.update(kw)
    return PainPoint(**base)


def _pain_point_analysis(*titles):
    return PainPointAnalysisResult(
        niche=NICHE,
        pain_points=[_pain(t) for t in titles],
        total_mentions=10,
        top_categories=["inventory"],
        analysis_summary="summary",
    )


def _segment(name, **kw):
    base = dict(
        segment_name=name, size_estimate="Medium", pain_point_alignment=["p1"],
        motivation_drivers=["save time"], expertise_level="Intermediate",
        budget_sensitivity="Medium", discovery_channels=["Reddit"],
    )
    base.update(kw)
    return AudienceSegment(**base)


def _audience_mapping(*segment_names):
    return AudienceMappingResult(
        audience_segments=[_segment(n) for n in segment_names],
        primary_target_segment=segment_names[0] if segment_names else "Independent boutique owners",
        segment_prioritization_rationale="rationale",
        community_hubs=["r/smallbusiness"],
        content_preferences="how-tos",
        messaging_frameworks=["Stop guessing"],
        tools_currently_used=["Spreadsheets"],
        frustrations_with_existing=["gut feel"],
        recommended_channels=["Instagram", "Email"],
    )


def _state_with_niche_context():
    state = ResearchState()
    state.niche_context = _niche_context()
    return state


class TestG1Whitelist:
    def test_accepts_whitelisted_fields_and_overwrites(self):
        state = _state_with_niche_context()
        result = apply_gate_patch(state, 1, {
            "niche_description": "Edited description",
            "market_segments": ["Segment A", "Segment B"],
            "industry_boundaries": "Edited boundaries",
            "user_target_audience": "Boutique owners with 1-5 employees",
        })
        assert result.niche_context.niche_description == "Edited description"
        assert result.niche_context.market_segments == ["Segment A", "Segment B"]
        assert result.niche_context.industry_boundaries == "Edited boundaries"
        assert result.niche_context.user_target_audience == "Boutique owners with 1-5 employees"
        assert result.user_adjusted is True

    def test_partial_patch_leaves_other_fields_untouched(self):
        state = _state_with_niche_context()
        original_boundaries = state.niche_context.industry_boundaries
        apply_gate_patch(state, 1, {"niche_description": "Only this changed"})
        assert state.niche_context.niche_description == "Only this changed"
        assert state.niche_context.industry_boundaries == original_boundaries

    def test_rejects_unknown_key(self):
        state = _state_with_niche_context()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 1, {"anchor_entities": ["hack"]})

    def test_rejects_oversized_niche_description(self):
        state = _state_with_niche_context()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 1, {"niche_description": "x" * 2001})

    def test_rejects_more_than_twelve_market_segments(self):
        state = _state_with_niche_context()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 1, {"market_segments": [f"seg{i}" for i in range(13)]})

    def test_rejects_when_niche_context_missing(self):
        state = ResearchState()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 1, {"niche_description": "x"})

    def test_g1_rederivation_called_when_core_field_changes(self):
        """review B1/Codex 2-3: editing a core field must re-derive Stage 1's dependent
        outputs via the flow, NOT silently leave anchor_entities/audience_scope stale."""
        state = _state_with_niche_context()
        flow = Mock()
        apply_gate_patch(state, 1, {"niche_description": "Edited description"}, flow=flow)
        flow._rederive_niche_context_dependents.assert_called_once_with(state.niche_context)
        flow.checkpoint_mgr.save_stage.assert_called_once_with("stage_1_niche_context", state.niche_context)

    def test_g1_rederivation_not_called_when_no_core_field_changes(self):
        """An empty/no-op patch (e.g. all fields already None) must not trigger the LLM
        re-derivation call — nothing changed to re-derive."""
        state = _state_with_niche_context()
        flow = Mock()
        apply_gate_patch(state, 1, {}, flow=flow)
        flow._rederive_niche_context_dependents.assert_not_called()
        # Still stamps user_adjusted + saves the checkpoint (an accepted no-op patch).
        assert state.user_adjusted is True
        flow.checkpoint_mgr.save_stage.assert_called_once()

    def test_flow_none_skips_rederivation_and_persistence(self):
        """Pure-validation mode (flow=None, e.g. a unit test or a dry-run) mutates state but
        never touches an LLM or the filesystem."""
        state = _state_with_niche_context()
        apply_gate_patch(state, 1, {"niche_description": "Edited"})
        assert state.niche_context.niche_description == "Edited"
        assert state.user_adjusted is True

    def test_raises_when_checkpoint_save_fails(self):
        """Codex review finding 5 (REGRESSION): CheckpointManager.save_stage swallows write
        errors and returns False instead of raising (by design, so ordinary pipeline saves
        never abort the run) — apply_gate_patch must check that return value and raise
        GatePatchPersistError, otherwise continue_from_gate would re-notify success for an
        edit that a later resume would silently discard."""
        state = _state_with_niche_context()
        flow = Mock()
        flow.checkpoint_mgr.save_stage.return_value = False
        with pytest.raises(GatePatchPersistError):
            apply_gate_patch(state, 1, {"niche_description": "Edited"}, flow=flow)
        # The patch WAS applied to in-memory state before the persistence check.
        assert state.niche_context.niche_description == "Edited"


class TestG2Whitelist:
    def _state(self):
        state = ResearchState()
        state.niche_context = _niche_context()
        state.pain_point_analysis = _pain_point_analysis("Pain A", "Pain B", "Pain C")
        state.audience_mapping = _audience_mapping("SegA", "SegB")
        return state

    def test_accepts_pain_scope_and_audience_scope(self):
        state = self._state()
        apply_gate_patch(state, 4, {
            "excluded_segments": ["SegB"],
            "segment_emphasis": {"SegA": "high"},
            "primary_target_segment": "SegA",
            "pain_scope": {"excluded_titles": ["Pain C"], "pinned_titles": ["Pain A"]},
            "user_target_audience": "Refined audience",
        })
        assert state.user_audience_scope.excluded_segments == ["SegB"]
        assert state.user_audience_scope.segment_emphasis == {"SegA": "high"}
        assert state.user_audience_scope.primary_target_segment == "SegA"
        assert state.user_pain_scope.excluded_titles == ["Pain C"]
        assert state.user_pain_scope.pinned_titles == ["Pain A"]
        assert state.niche_context.user_target_audience == "Refined audience"
        assert state.user_adjusted is True

    def test_non_destructive_never_mutates_audience_segments_or_pains(self):
        state = self._state()
        original_segment_names = [s.segment_name for s in state.audience_mapping.audience_segments]
        original_pain_titles = [p.title for p in state.pain_point_analysis.pain_points]
        apply_gate_patch(state, 4, {
            "excluded_segments": ["SegB"],
            "pain_scope": {"excluded_titles": ["Pain C"], "pinned_titles": []},
        })
        assert [s.segment_name for s in state.audience_mapping.audience_segments] == original_segment_names
        assert [p.title for p in state.pain_point_analysis.pain_points] == original_pain_titles

    def test_rejects_unknown_segment_in_excluded_segments(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"excluded_segments": ["NoSuchSegment"]})

    def test_rejects_unknown_segment_in_primary_target_segment(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"primary_target_segment": "NoSuchSegment"})

    def test_rejects_unknown_segment_in_segment_emphasis(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"segment_emphasis": {"NoSuchSegment": "high"}})

    def test_rejects_invalid_emphasis_value(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"segment_emphasis": {"SegA": "medium"}})

    # Codex review finding 14 (AMEND): Pydantic G2 field length caps now mirror
    # GateG2PatchSchema in backend/src/types/job.ts (previously G2Patch had NO caps at all).
    def test_rejects_oversized_user_target_audience(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"user_target_audience": "x" * 501})

    def test_rejects_oversized_primary_target_segment(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"primary_target_segment": "x" * 256})

    def test_rejects_oversized_excluded_segments_entry(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"excluded_segments": ["x" * 256]})

    def test_rejects_oversized_pain_scope_title(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {
                "pain_scope": {"excluded_titles": ["x" * 501], "pinned_titles": []}
            })

    def test_rejects_unknown_pain_title(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"pain_scope": {"excluded_titles": ["No such pain"], "pinned_titles": []}})

    def test_rejects_same_title_excluded_and_pinned(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {
                "pain_scope": {"excluded_titles": ["Pain A"], "pinned_titles": ["Pain A"]}
            })

    def test_rejects_unknown_key(self):
        state = self._state()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"audience_segments": []})

    def test_rejects_when_audience_mapping_missing(self):
        state = ResearchState()
        state.niche_context = _niche_context()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 4, {"excluded_segments": []})

    def test_saves_stage_4_and_flushes_metadata_when_flow_given(self):
        state = self._state()
        flow = Mock()
        apply_gate_patch(state, 4, {"excluded_segments": ["SegB"]}, flow=flow)
        flow.checkpoint_mgr.save_stage.assert_called_once_with(
            "stage_4_audience_mapping", state.audience_mapping)
        flow.checkpoint_mgr.flush_metadata.assert_called_once()
        # G2 never calls the G1-only re-derivation hook.
        flow._rederive_niche_context_dependents.assert_not_called()

    def test_raises_when_checkpoint_save_fails(self):
        """Codex review finding 5 (REGRESSION): same discipline as G1 — a swallowed
        stage_4_audience_mapping save failure must raise, not silently report success."""
        state = self._state()
        flow = Mock()
        flow.checkpoint_mgr.save_stage.return_value = False
        with pytest.raises(GatePatchPersistError):
            apply_gate_patch(state, 4, {"excluded_segments": ["SegB"]}, flow=flow)
        flow.checkpoint_mgr.flush_metadata.assert_not_called()

    def test_second_patch_merges_onto_existing_scope_not_reset(self):
        """Two sequential apply_stay applies (the plan's default apply mode) must accumulate,
        not clobber each other's untouched fields."""
        state = self._state()
        apply_gate_patch(state, 4, {"excluded_segments": ["SegB"]})
        apply_gate_patch(state, 4, {"segment_emphasis": {"SegA": "high"}})
        assert state.user_audience_scope.excluded_segments == ["SegB"]
        assert state.user_audience_scope.segment_emphasis == {"SegA": "high"}


class TestInvalidGateStage:
    def test_unsupported_gate_stage_raises(self):
        state = _state_with_niche_context()
        with pytest.raises(GatePatchError):
            apply_gate_patch(state, 99, {})
