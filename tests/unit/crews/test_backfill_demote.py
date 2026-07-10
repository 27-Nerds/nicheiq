"""Weak-winner demotion / variant merge / backfill block (post-parity deliverable-quality gate).

Covers: visible_ideas() projection, _sweep_demote, _compose_ruled_out_reason,
_pick_backfill_cells, _merge_acceptable, and the _backfill_and_demote orchestration.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.solution_idea import visible_ideas


def _crew(**extra):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[])
    crew.coverage_caveats = []
    crew.ruled_out_pains = []
    crew.overlap_groups = []
    crew.funnel_counts = {}
    crew._birth_verified_names = set()
    crew._tournament_ctx = None
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _idea(name, mf=0.6, status="active", tier="single", **kw):
    base = dict(
        solution_name=name, market_fit_score=mf, candidate_status=status,
        idea_tier=tier, source_pain=None, source_segment=None,
        source_segment_payability=None, incumbent_parity=None,
        data_access_model=None, build_feasibility_score=None,
        pain_points_addressed=None,
        technical_feasibility_score=0.6, novelty_score=0.5,
        seo_scalability_score=0.5, winning_angle=None,
        data_feasibility_score=0.7, solo_dev_feasibility=0.7,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _pain(title, severity=0.5, opportunity="medium", **kw):
    base = dict(title=title, severity_score=severity, opportunity_level=opportunity,
                affected_segments=None, pain_point_alignment=None,
                representative_quotes=None, description="")
    base.update(kw)
    return SimpleNamespace(**base)


def _segment(name, **kw):
    base = dict(segment_name=name, pain_point_alignment=None)
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# visible_ideas()
# ---------------------------------------------------------------------------

class TestVisibleIdeas:
    def test_excludes_demoted_and_absorbed(self):
        ideas = [
            _idea("A", status="active"),
            _idea("B", status="demoted"),
            _idea("C", status="absorbed"),
            _idea("D", status="restored"),
        ]
        out = [i.solution_name for i in visible_ideas(ideas)]
        assert out == ["A", "D"]

    def test_missing_candidate_status_attr_defaults_active(self):
        bare = SimpleNamespace(solution_name="Bare")  # no candidate_status attr at all
        out = visible_ideas([bare])
        assert out == [bare]

    def test_works_on_dicts(self):
        ideas = [
            {"solution_name": "A", "candidate_status": "active"},
            {"solution_name": "B", "candidate_status": "demoted"},
            {"solution_name": "C"},  # missing key -> defaults active
        ]
        out = [i["solution_name"] for i in visible_ideas(ideas)]
        assert out == ["A", "C"]

    def test_empty_and_none(self):
        assert visible_ideas([]) == []
        assert visible_ideas(None) == []


# ---------------------------------------------------------------------------
# _sweep_demote
# ---------------------------------------------------------------------------

class TestSweepDemote:
    def test_demotes_below_bar_across_tiers(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        crew = _crew()
        ideas = [
            _idea("Single", mf=0.2, tier="single"),
            _idea("Salvaged", mf=0.3, tier="salvaged"),
            _idea("Bundle", mf=0.1, tier="bundle"),
            _idea("StrongSingle", mf=0.7, tier="single"),
        ]
        n = crew._sweep_demote(ideas)
        assert n == 3
        assert [i.candidate_status for i in ideas] == ["demoted", "demoted", "demoted", "active"]
        assert len(crew.ruled_out_pains) == 3
        for finding, idea, tier in zip(
            crew.ruled_out_pains, ideas[:3], ["single", "salvaged", "bundle"]
        ):
            assert finding["source"] == "demoted_winner"
            assert finding["prior_tier"] == tier

    def test_skips_non_active_status(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        crew = _crew()
        ideas = [_idea("AlreadyDemoted", mf=0.1, status="demoted")]
        n = crew._sweep_demote(ideas)
        assert n == 0
        assert ideas[0].candidate_status == "demoted"  # unchanged
        assert crew.ruled_out_pains == []

    def test_bar_zero_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.0)
        crew = _crew()
        ideas = [_idea("A", mf=0.0)]
        n = crew._sweep_demote(ideas)
        assert n == 0
        assert ideas[0].candidate_status == "active"


# ---------------------------------------------------------------------------
# _compose_ruled_out_reason
# ---------------------------------------------------------------------------

class TestComposeRuledOutReason:
    def test_incumbent_parity_shipped(self):
        crew = _crew()
        idea = _idea("A", mf=0.3, incumbent_parity="shipped by Acme: route optimization")
        reason, band = crew._compose_ruled_out_reason(idea)
        assert "well-served" in reason
        assert "shipped by Acme" in reason
        assert band == "low"

    def test_incumbent_parity_substitute(self):
        crew = _crew()
        idea = _idea("A", mf=0.3, incumbent_parity="substitute: spreadsheets")
        reason, band = crew._compose_ruled_out_reason(idea)
        assert "without paid tooling" in reason
        assert "substitute: spreadsheets" in reason

    def test_low_segment_payability(self, monkeypatch):
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = _crew()
        idea = _idea("A", mf=0.3, source_segment_payability=0.1, source_segment="Hobbyists")
        reason, band = crew._compose_ruled_out_reason(idea)
        assert "wallet is thin" in reason
        assert "Hobbyists" in reason

    def test_blocked_data_access_model(self):
        crew = _crew()
        idea = _idea("A", mf=0.3, data_access_model="blocked")
        reason, band = crew._compose_ruled_out_reason(idea)
        assert "can't be built" in reason

    def test_low_build_feasibility(self):
        crew = _crew()
        idea = _idea("A", mf=0.3, build_feasibility_score=0.3)
        reason, band = crew._compose_ruled_out_reason(idea)
        assert "can't be built" in reason

    def test_mild_demand_default(self):
        crew = _crew()
        idea = _idea("A", mf=0.3)
        reason, band = crew._compose_ruled_out_reason(idea)
        assert reason.startswith("Mild demand")

    def test_band_very_low_below_quarter(self):
        crew = _crew()
        idea = _idea("A", mf=0.1)
        _, band = crew._compose_ruled_out_reason(idea)
        assert band == "very-low"

    def test_band_low_at_or_above_quarter(self):
        crew = _crew()
        idea = _idea("A", mf=0.3)
        _, band = crew._compose_ruled_out_reason(idea)
        assert band == "low"


# ---------------------------------------------------------------------------
# _pick_backfill_cells
# ---------------------------------------------------------------------------

class TestPickBackfillCells:
    def test_ranks_untried_by_opportunity_then_severity(self):
        crew = _crew()
        pLow = _pain("Low opp", severity=0.9, opportunity="low")
        pMedHighSev = _pain("Med opp high sev", severity=0.9, opportunity="medium")
        pMedLowSev = _pain("Med opp low sev", severity=0.2, opportunity="medium")
        pHigh = _pain("High opp", severity=0.1, opportunity="high")
        crew.pain_point_analysis = SimpleNamespace(
            pain_points=[pLow, pMedHighSev, pMedLowSev, pHigh])
        crew.audience_mapping = SimpleNamespace(audience_segments=[])
        out = crew._pick_backfill_cells(ideas=[], cells=[], max_n=4)
        titles = [c["pain"].title for c in out]
        assert titles == ["High opp", "Med opp high sev", "Med opp low sev", "Low opp"]

    def test_tried_pains_excluded_via_cells_and_source_pain(self):
        crew = _crew()
        pTriedByCell = _pain("Tried via cell", opportunity="high")
        pTriedByIdea = _pain("Tried via idea", opportunity="high")
        pUntried = _pain("Untried", opportunity="high")
        crew.pain_point_analysis = SimpleNamespace(
            pain_points=[pTriedByCell, pTriedByIdea, pUntried])
        crew.audience_mapping = SimpleNamespace(audience_segments=[])
        ideas = [_idea("I1", source_pain="Tried via idea")]
        cells = [{"pain": pTriedByCell, "segment": None}]
        out = crew._pick_backfill_cells(ideas=ideas, cells=cells, max_n=5)
        titles = [c["pain"].title for c in out]
        assert titles == ["Untried"]

    def test_fallback_strong_pain_different_segment_when_untried_short(self):
        crew = _crew()
        pUntried = _pain("Untried", opportunity="high")
        pTried = _pain("Tried", opportunity="high",
                        affected_segments=["SegA", "SegB"])
        crew.pain_point_analysis = SimpleNamespace(pain_points=[pUntried, pTried])
        segA = _segment("SegA")
        segB = _segment("SegB")
        crew.audience_mapping = SimpleNamespace(audience_segments=[segA, segB])
        strong_idea = _idea("Strong", mf=0.9, status="active",
                             source_pain="Tried", source_segment="SegA")
        out = crew._pick_backfill_cells(ideas=[strong_idea], cells=[], max_n=2)
        assert len(out) == 2
        assert out[0]["pain"].title == "Untried"
        assert out[1]["pain"] is pTried
        assert out[1]["segment"] is segB  # different segment than the one already used

    def test_returns_at_most_max_n(self):
        crew = _crew()
        pains = [_pain(f"P{i}", opportunity="high") for i in range(5)]
        crew.pain_point_analysis = SimpleNamespace(pain_points=pains)
        crew.audience_mapping = SimpleNamespace(audience_segments=[])
        out = crew._pick_backfill_cells(ideas=[], cells=[], max_n=2)
        assert len(out) == 2

    def test_empty_inputs_returns_empty(self):
        crew = _crew()
        crew.pain_point_analysis = SimpleNamespace(pain_points=[])
        crew.audience_mapping = SimpleNamespace(audience_segments=[])
        out = crew._pick_backfill_cells(ideas=[], cells=[], max_n=3)
        assert out == []


# ---------------------------------------------------------------------------
# _merge_acceptable
# ---------------------------------------------------------------------------

class TestMergeAcceptable:
    def _member(self):
        return _idea("Member", mf=0.5, technical_feasibility_score=0.6, novelty_score=0.5,
                     seo_scalability_score=0.5, winning_angle=None,
                     build_feasibility_score=0.7, data_feasibility_score=0.7,
                     solo_dev_feasibility=0.7)

    def test_merged_beats_best_no_regression_accepted(self):
        members = [self._member()]
        merged = _idea("Merged", mf=0.6, technical_feasibility_score=0.65, novelty_score=0.6,
                       seo_scalability_score=0.6, winning_angle=None,
                       build_feasibility_score=0.7, data_feasibility_score=0.7,
                       solo_dev_feasibility=0.7)
        assert UnifiedSolutionCrew._merge_acceptable(merged, members, bar=0.4) is True

    def test_merged_composite_below_best_rejected(self):
        members = [self._member()]
        merged = _idea("Merged", mf=0.45, technical_feasibility_score=0.45, novelty_score=0.4,
                       seo_scalability_score=0.4, winning_angle=None,
                       build_feasibility_score=0.7, data_feasibility_score=0.7,
                       solo_dev_feasibility=0.7)
        assert UnifiedSolutionCrew._merge_acceptable(merged, members, bar=0.4) is False

    def test_per_dimension_regression_rejected(self):
        members = [self._member()]
        merged = _idea("Merged", mf=0.6, technical_feasibility_score=0.65, novelty_score=0.6,
                       seo_scalability_score=0.6, winning_angle=None,
                       build_feasibility_score=0.6,  # best=0.7, regresses by 0.1 > 0.05
                       data_feasibility_score=0.7, solo_dev_feasibility=0.7)
        assert UnifiedSolutionCrew._merge_acceptable(merged, members, bar=0.4) is False

    def test_market_fit_below_bar_rejected(self):
        members = [self._member()]
        merged = _idea("Merged", mf=0.3, technical_feasibility_score=0.65, novelty_score=0.6,
                       seo_scalability_score=0.6, winning_angle=None,
                       build_feasibility_score=0.7, data_feasibility_score=0.7,
                       solo_dev_feasibility=0.7)
        assert UnifiedSolutionCrew._merge_acceptable(merged, members, bar=0.4) is False


# ---------------------------------------------------------------------------
# _backfill_and_demote orchestration
# ---------------------------------------------------------------------------

class TestBackfillAndDemote:
    def _noop_wave_methods(self, crew):
        """No-op every expensive per-idea pass so a non-empty wave doesn't try real work."""
        crew._finalize_feasibility = lambda wave: None
        crew._finalize_idea_pool = lambda wave: None
        crew._verify_pool_routes = lambda wave: None
        crew._filter_pain_relevance = lambda wave: None
        crew._stamp_payability = lambda w: None
        crew._finalize_dev_time = lambda wave: None
        crew._probe_mechanism_parity = lambda wave: None
        crew._validate_idea_caps = lambda w: None
        crew._classify_idea_angles = lambda wave: None
        crew._validate_idea_scores = lambda ideas: None

    def _minimal_ctx(self):
        """Smallest tournament ctx the block reads (search/usages/partition_cells optional)."""
        return {"crew_inputs": {}, "usages": [], "partition_cells": []}

    def test_convergent_path_is_a_complete_noop(self, monkeypatch):
        """_tournament_ctx=None (legacy/convergent path) -> the ENTIRE block is a no-op: no
        demotion, no merge/backfill, no funnel counts, statuses untouched (codex-review fix:
        the legacy path captures its selection before this point, so even the sweep is unsafe)."""
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        crew = _crew()
        crew._tournament_ctx = None
        group_mock = MagicMock()
        crew._group_variant_overlaps = group_mock
        ideas = [
            _idea("A", mf=0.6), _idea("B", mf=0.6), _idea("C", mf=0.6),
            _idea("D", mf=0.2), _idea("E", mf=0.1),
        ]
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._backfill_and_demote(refined, skip_selection=False)

        assert group_mock.call_count == 0
        assert crew.funnel_counts == {}
        assert crew.ruled_out_pains == []
        assert all(i.candidate_status == "active" for i in ideas)
        assert len(visible_ideas(ideas)) == 5

    def test_floor_guard_restores_highest_mf_demoted_and_retracts_findings(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        monkeypatch.setattr(settings, "backfill_target_visible", 0)
        monkeypatch.setattr(settings, "backfill_max_cells", 0)
        crew = _crew()
        crew._tournament_ctx = self._minimal_ctx()
        crew._group_variant_overlaps = lambda visible: []
        self._noop_wave_methods(crew)
        ideas = [
            _idea("Weakest", mf=0.05), _idea("Weak", mf=0.15),
            _idea("Mid", mf=0.25), _idea("Strong", mf=0.35),
        ]
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._backfill_and_demote(refined, skip_selection=False)

        # All 4 started below the 0.4 bar -> all demoted, then floor guard restores the
        # 3 highest-mf ones (floor=3, visible=0 after demotion).
        by_name = {i.solution_name: i for i in ideas}
        assert by_name["Weakest"].candidate_status == "demoted"
        assert by_name["Weak"].candidate_status == "restored"
        assert by_name["Mid"].candidate_status == "restored"
        assert by_name["Strong"].candidate_status == "restored"
        assert len(crew.coverage_caveats) == 3
        assert len(visible_ideas(ideas)) == 3
        # Restored ideas' ruled-out findings are RETRACTED (codex-review fix): only the
        # still-demoted idea remains in the ledger.
        assert [f["idea_name"] for f in crew.ruled_out_pains] == ["Weakest"]

    def test_funnel_counts_include_demoted_shown_and_pains(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        monkeypatch.setattr(settings, "backfill_target_visible", 3)
        monkeypatch.setattr(settings, "backfill_max_cells", 3)
        crew = _crew()
        crew._tournament_ctx = self._minimal_ctx()
        crew._group_variant_overlaps = lambda visible: []
        crew._pick_backfill_cells = lambda *a, **k: []
        self._noop_wave_methods(crew)
        crew.pain_point_analysis = SimpleNamespace(
            pain_points=[_pain("P1"), _pain("P2"), _pain("P3")])
        ideas = [_idea("A", mf=0.6), _idea("B", mf=0.6), _idea("C", mf=0.6), _idea("D", mf=0.1)]
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._backfill_and_demote(refined, skip_selection=False)

        assert crew.funnel_counts["pains_identified"] == 3
        assert crew.funnel_counts["demoted"] == 1
        assert crew.funnel_counts["merge_groups"] == 0
        assert crew.funnel_counts["candidates_shown"] == len(visible_ideas(ideas)) == 3

    def test_backfill_not_triggered_when_visible_meets_target(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        monkeypatch.setattr(settings, "backfill_target_visible", 6)
        monkeypatch.setattr(settings, "backfill_max_cells", 3)
        crew = _crew()
        crew._group_variant_overlaps = lambda visible: []
        pick_mock = MagicMock(return_value=[])
        crew._pick_backfill_cells = pick_mock
        ideas = [_idea(f"I{i}", mf=0.6) for i in range(6)]  # visible == target
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._tournament_ctx = {
            "search": None, "usages": [], "partition_cells": [],
            "crew_inputs": {}, "cells_run": 6, "concepts_generated": 10,
            "survived_critics": 6, "winners": 6, "salvaged": 0,
        }
        crew._backfill_and_demote(refined, skip_selection=False)

        assert pick_mock.call_count == 0
        assert crew.funnel_counts["backfill_run"] == 0

    def test_backfill_triggered_with_min_needed_cap(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        monkeypatch.setattr(settings, "backfill_target_visible", 6)
        monkeypatch.setattr(settings, "backfill_max_cells", 3)
        crew = _crew()
        crew._group_variant_overlaps = lambda visible: []
        pick_mock = MagicMock(return_value=[])
        crew._pick_backfill_cells = pick_mock
        ideas = [_idea(f"I{i}", mf=0.6) for i in range(4)]  # visible=4, needed=2
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._tournament_ctx = {
            "search": None, "usages": [], "partition_cells": [],
            "crew_inputs": {}, "cells_run": 4, "concepts_generated": 8,
            "survived_critics": 4, "winners": 4, "salvaged": 0,
        }
        crew._backfill_and_demote(refined, skip_selection=False)

        pick_mock.assert_called_once()
        call_args = pick_mock.call_args
        assert call_args[0][0] is ideas
        assert call_args[0][1] == []  # ctx.get("partition_cells") or []
        assert call_args[0][2] == 2  # min(needed=2, cap=3)
        assert crew.funnel_counts["backfill_run"] == 0  # cells returned [] -> no jobs run

    def test_backfill_accept_and_reject_recorded(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 3)
        monkeypatch.setattr(settings, "backfill_target_visible", 6)
        monkeypatch.setattr(settings, "backfill_max_cells", 3)
        crew = _crew()
        crew._group_variant_overlaps = lambda visible: []
        self._noop_wave_methods(crew)

        crew._pick_backfill_cells = MagicMock(
            return_value=[{"pain": None, "segment": None}, {"pain": None, "segment": None}])

        accepted_winner = _idea("Accepted", mf=0.7)
        rejected_winner = _idea("Rejected", mf=0.2)
        crew._run_parallel = MagicMock(return_value=[accepted_winner, rejected_winner])

        ideas = [_idea(f"I{i}", mf=0.6) for i in range(4)]  # visible=4, needed=2
        refined = SimpleNamespace(solution_ideas=ideas)
        crew._tournament_ctx = {
            "search": None, "usages": [], "partition_cells": [],
            "crew_inputs": {}, "cells_run": 4, "concepts_generated": 8,
            "survived_critics": 4, "winners": 4, "salvaged": 0,
        }
        crew._backfill_and_demote(refined, skip_selection=False)

        assert accepted_winner in ideas
        assert rejected_winner not in ideas
        assert crew.funnel_counts["backfill_run"] == 2
        assert crew.funnel_counts["backfill_accepted"] == 1

        rejected_findings = [f for f in crew.ruled_out_pains if f["source"] == "backfill_rejected"]
        assert len(rejected_findings) == 1
        assert rejected_findings[0]["pain_title"] == "Rejected"
        assert rejected_findings[0]["market_fit"] == 0.2
        assert not any(f["source"] == "backfill_rejected" and f["pain_title"] == "Accepted"
                       for f in crew.ruled_out_pains)
