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

    def test_preserves_evaluated_payload_for_generated_idea(self):
        crew = _crew()
        idea = _idea("GeneratedConcept", mf=0.2, source_frame="pain")
        idea.model_dump = lambda mode="python": {
            "solution_name": "GeneratedConcept",
            "description": "Automates a researched workflow",
            "value_proposition": "Removes repetitive manual work",
        }

        crew._record_ruled_out(idea, source="demoted_winner")

        assert crew.ruled_out_pains[0]["idea"]["description"] == (
            "Automates a researched workflow"
        )

    def test_bar_zero_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.0)
        crew = _crew()
        ideas = [_idea("A", mf=0.0)]
        n = crew._sweep_demote(ideas)
        assert n == 0
        assert ideas[0].candidate_status == "active"


# ---------------------------------------------------------------------------
# _sweep_no_buyer_demote (TIScalperAudit case, 2026-07-12)
# ---------------------------------------------------------------------------

class TestNoBuyerDemote:
    def _wallet_crew(self, wallet_class="free-culture", **extra):
        pains = [_pain("Ticket scalping frustrates fans", tool_addressable="none")]
        crew = _crew(
            _niche_wallet_brief={"wallet_class": wallet_class} if wallet_class else {},
            **extra,
        )
        crew.pain_point_analysis = SimpleNamespace(pain_points=pains)
        return crew

    def test_tiscalperaudit_shaped_idea_demoted(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "no_buyer_demotion", True)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = self._wallet_crew(wallet_class="free-culture")
        idea = _idea(
            "TIScalperAudit", mf=0.40,  # exactly AT the demotion bar — survives it
            pain_points_addressed=["Ticket scalping frustrates fans"],
            source_segment_payability=0.2,
        )
        n = crew._sweep_demote([idea])
        assert n == 1
        assert idea.candidate_status == "demoted"
        assert len(crew.ruled_out_pains) == 1
        finding = crew.ruled_out_pains[0]
        assert finding["source"] == "no_buyer"
        assert "free alternatives" in finding["reason"]
        assert "low willingness to pay" in finding["reason"]
        assert "only partly addressable by software" in finding["reason"]

    def test_paying_niche_equivalent_not_demoted(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "no_buyer_demotion", True)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = self._wallet_crew(wallet_class="paying")
        idea = _idea(
            "TIScalperAudit", mf=0.40,
            pain_points_addressed=["Ticket scalping frustrates fans"],
            source_segment_payability=0.2,
        )
        n = crew._sweep_demote([idea])
        assert n == 0
        assert idea.candidate_status == "active"
        assert crew.ruled_out_pains == []

    def test_flag_off_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "no_buyer_demotion", False)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = self._wallet_crew(wallet_class="free-culture")
        idea = _idea(
            "TIScalperAudit", mf=0.40,
            pain_points_addressed=["Ticket scalping frustrates fans"],
            source_segment_payability=0.2,
        )
        n = crew._sweep_demote([idea])
        assert n == 0
        assert idea.candidate_status == "active"

    def test_fully_tool_addressable_pain_exempt(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "no_buyer_demotion", True)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = self._wallet_crew(wallet_class="free-culture")
        crew.pain_point_analysis.pain_points[0].tool_addressable = "full"
        idea = _idea(
            "BuildableIdea", mf=0.40,
            pain_points_addressed=["Ticket scalping frustrates fans"],
            source_segment_payability=0.2,
        )
        n = crew._sweep_demote([idea])
        assert n == 0
        assert idea.candidate_status == "active"

    def test_high_payability_exempt(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "no_buyer_demotion", True)
        monkeypatch.setattr(settings, "payability_low_threshold", 0.35)
        crew = self._wallet_crew(wallet_class="free-culture")
        idea = _idea(
            "WellFundedAdvocacy", mf=0.40,
            pain_points_addressed=["Ticket scalping frustrates fans"],
            source_segment_payability=0.8,
        )
        n = crew._sweep_demote([idea])
        assert n == 0
        assert idea.candidate_status == "active"


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
        crew._calibrate_idea_scores = lambda wave: None
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


# ---------------------------------------------------------------------------
# Wave consolidation (2026-07-10): pivot revisions + variant-merge composites are generated
# in parallel and scored together in ONE `_score_wave` call, with the overlap rule (pivot
# precedence over merge-group membership) resolved before generation.
# ---------------------------------------------------------------------------

def _run_parallel_sync(fn, jobs, **kw):
    """Deterministic stand-in for `_run_parallel`: runs every job synchronously, in order,
    instead of on a thread pool — keeps these tests free of real concurrency/timing."""
    return [fn(**job) for job in jobs]


class TestWaveConsolidation:
    def _base_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "demotion_market_fit_max", 0.4)
        monkeypatch.setattr(settings, "min_visible_candidates", 0)
        monkeypatch.setattr(settings, "backfill_target_visible", 0)
        monkeypatch.setattr(settings, "backfill_max_cells", 0)
        monkeypatch.setattr(settings, "variant_merge_max_groups", 2)

    def _pivot_and_merge_setup(self, monkeypatch):
        """One shipped/partial-capped idea (pivot candidate) + a 2-member variant group, wired
        so generation and scoring are fully mocked/deterministic."""
        self._base_settings(monkeypatch)
        crew = _crew()
        crew._tournament_ctx = {"crew_inputs": {}, "usages": [], "partition_cells": []}

        orig_pivot = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme")
        member_a = _idea("VariantA", mf=0.5)
        member_b = _idea("VariantB", mf=0.5)
        ideas = [orig_pivot, member_a, member_b]
        refined = SimpleNamespace(solution_ideas=ideas)

        crew._pivot_candidates = MagicMock(return_value=[orig_pivot])
        crew._group_variant_overlaps = lambda visible: [
            {"idea_names": ["VariantA", "VariantB"], "shared_product": "Widget"}]

        pivot_rev = _idea("PivotedApp", mf=0.7)
        merged_idea = _idea("MergedApp", mf=0.7)
        crew._generate_pivot_revision = MagicMock(return_value=pivot_rev)
        crew._synthesize_variant_merge = MagicMock(return_value=merged_idea)
        crew._run_parallel = MagicMock(side_effect=_run_parallel_sync)

        return crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev, merged_idea

    def test_pivot_and_merge_scored_in_one_wave_call(self, monkeypatch):
        (crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev,
         merged_idea) = self._pivot_and_merge_setup(monkeypatch)

        score_wave_calls: list = []
        crew._score_wave = MagicMock(
            side_effect=lambda wave, **kw: score_wave_calls.append(list(wave)))
        crew._pivot_acceptable = MagicMock(return_value=False)
        crew._merge_acceptable = MagicMock(return_value=False)

        crew._backfill_and_demote(refined, skip_selection=False)

        assert len(score_wave_calls) == 1
        assert pivot_rev in score_wave_calls[0]
        assert merged_idea in score_wave_calls[0]

    def test_winning_pivot_accepted_losing_merge_rejected(self, monkeypatch):
        (crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev,
         merged_idea) = self._pivot_and_merge_setup(monkeypatch)
        crew._score_wave = lambda wave, **kw: None
        crew._pivot_acceptable = MagicMock(return_value=True)
        crew._merge_acceptable = MagicMock(return_value=False)

        crew._backfill_and_demote(refined, skip_selection=False)

        assert pivot_rev in ideas
        assert orig_pivot not in ideas
        assert merged_idea not in ideas
        assert member_a.candidate_status == "active"
        assert member_b.candidate_status == "active"
        assert crew.funnel_counts["pivots_attempted"] == 1
        assert crew.funnel_counts["pivots_accepted"] == 1
        assert crew.funnel_counts["merge_groups"] == 0

    def test_losing_pivot_rejected_winning_merge_accepted(self, monkeypatch):
        (crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev,
         merged_idea) = self._pivot_and_merge_setup(monkeypatch)
        crew._score_wave = lambda wave, **kw: None
        crew._pivot_acceptable = MagicMock(return_value=False)
        crew._merge_acceptable = MagicMock(return_value=True)

        crew._backfill_and_demote(refined, skip_selection=False)

        assert orig_pivot in ideas
        assert pivot_rev not in ideas
        assert merged_idea in ideas
        assert member_a.candidate_status == "absorbed"
        assert member_b.candidate_status == "absorbed"
        assert crew.funnel_counts["pivots_accepted"] == 0
        assert crew.funnel_counts["merge_groups"] == 1
        assert crew.funnel_counts["variants_absorbed"] == 2

    def test_overlap_rule_two_member_group_dissolves(self, monkeypatch):
        self._base_settings(monkeypatch)
        crew = _crew()
        crew._tournament_ctx = {"crew_inputs": {}, "usages": [], "partition_cells": []}

        overlap_idea = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme")
        member_b = _idea("VariantB", mf=0.5)
        ideas = [overlap_idea, member_b]
        refined = SimpleNamespace(solution_ideas=ideas)

        crew._pivot_candidates = MagicMock(return_value=[overlap_idea])
        crew._group_variant_overlaps = lambda visible: [
            {"idea_names": ["Shipped", "VariantB"], "shared_product": "Widget"}]
        crew._generate_pivot_revision = MagicMock(return_value=None)
        crew._synthesize_variant_merge = MagicMock()
        crew._run_parallel = MagicMock(side_effect=_run_parallel_sync)
        crew._score_wave = lambda wave, **kw: None

        crew._backfill_and_demote(refined, skip_selection=False)

        # 'Shipped' is claimed by the pivot -> group left with only 'VariantB' (<2) dissolves;
        # no merge job is ever built, so synthesis is never called.
        crew._synthesize_variant_merge.assert_not_called()
        assert crew.funnel_counts["merge_groups"] == 0

    def test_overlap_rule_three_member_group_survives_with_two(self, monkeypatch):
        self._base_settings(monkeypatch)
        crew = _crew()
        crew._tournament_ctx = {"crew_inputs": {}, "usages": [], "partition_cells": []}

        overlap_idea = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme")
        member_b = _idea("VariantB", mf=0.5)
        member_c = _idea("VariantC", mf=0.5)
        ideas = [overlap_idea, member_b, member_c]
        refined = SimpleNamespace(solution_ideas=ideas)

        crew._pivot_candidates = MagicMock(return_value=[overlap_idea])
        crew._group_variant_overlaps = lambda visible: [
            {"idea_names": ["Shipped", "VariantB", "VariantC"], "shared_product": "Widget"}]
        crew._generate_pivot_revision = MagicMock(return_value=None)
        merged_idea = _idea("MergedApp", mf=0.6)
        crew._synthesize_variant_merge = MagicMock(return_value=merged_idea)
        crew._run_parallel = MagicMock(side_effect=_run_parallel_sync)
        crew._score_wave = lambda wave, **kw: None
        crew._merge_acceptable = MagicMock(return_value=False)

        crew._backfill_and_demote(refined, skip_selection=False)

        # 'Shipped' claimed by the pivot -> group left with 'VariantB'+'VariantC' (still >=2)
        # survives and a merge is attempted over exactly those two.
        crew._synthesize_variant_merge.assert_called_once()
        called_members = crew._synthesize_variant_merge.call_args[0][0]
        called_names = sorted(getattr(m, "solution_name") for m in called_members)
        assert called_names == ["VariantB", "VariantC"]

    # -- self.overlap_groups sync (codex review 2026-07-11 REGRESSION) --------------------
    # `self.overlap_groups` drives grouped-variant display in the report; the contract is
    # that it reflects RESOLVED groups (post pivot-precedence stripping, dissolved groups
    # dropped) and that an accepted merge's group is pruned so only rejected/never-attempted
    # groups linger.

    def test_overlap_groups_resolved_after_pivot_precedence_strip(self, monkeypatch):
        self._base_settings(monkeypatch)
        crew = _crew()
        crew._tournament_ctx = {"crew_inputs": {}, "usages": [], "partition_cells": []}

        overlap_idea = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme")
        member_b = _idea("VariantB", mf=0.5)
        member_c = _idea("VariantC", mf=0.5)
        ideas = [overlap_idea, member_b, member_c]
        refined = SimpleNamespace(solution_ideas=ideas)

        crew._pivot_candidates = MagicMock(return_value=[overlap_idea])
        crew._group_variant_overlaps = lambda visible: [
            {"idea_names": ["Shipped", "VariantB", "VariantC"], "shared_product": "Widget"}]
        crew._generate_pivot_revision = MagicMock(return_value=None)
        merged_idea = _idea("MergedApp", mf=0.6)
        crew._synthesize_variant_merge = MagicMock(return_value=merged_idea)
        crew._run_parallel = MagicMock(side_effect=_run_parallel_sync)
        crew._score_wave = lambda wave, **kw: None
        crew._merge_acceptable = MagicMock(return_value=False)  # rejected -> group retained

        crew._backfill_and_demote(refined, skip_selection=False)

        # 'Shipped' was stripped by pivot precedence -> self.overlap_groups reflects the
        # RESOLVED 2-member group, not the raw 3-member group _group_variant_overlaps returned.
        assert crew.overlap_groups == [
            {"idea_names": ["VariantB", "VariantC"], "shared_product": "Widget"}]

    def test_overlap_groups_dissolved_group_not_retained(self, monkeypatch):
        self._base_settings(monkeypatch)
        crew = _crew()
        crew._tournament_ctx = {"crew_inputs": {}, "usages": [], "partition_cells": []}

        overlap_idea = _idea("Shipped", mf=0.45, incumbent_parity="shipped by Acme")
        member_b = _idea("VariantB", mf=0.5)
        ideas = [overlap_idea, member_b]
        refined = SimpleNamespace(solution_ideas=ideas)

        crew._pivot_candidates = MagicMock(return_value=[overlap_idea])
        crew._group_variant_overlaps = lambda visible: [
            {"idea_names": ["Shipped", "VariantB"], "shared_product": "Widget"}]
        crew._generate_pivot_revision = MagicMock(return_value=None)
        crew._synthesize_variant_merge = MagicMock()
        crew._run_parallel = MagicMock(side_effect=_run_parallel_sync)
        crew._score_wave = lambda wave, **kw: None

        crew._backfill_and_demote(refined, skip_selection=False)

        # Group left with only 'VariantB' (<2) dissolves -> must not linger in overlap_groups.
        assert crew.overlap_groups == []

    def test_overlap_groups_accepted_merge_group_removed(self, monkeypatch):
        (crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev,
         merged_idea) = self._pivot_and_merge_setup(monkeypatch)
        crew._score_wave = lambda wave, **kw: None
        crew._pivot_acceptable = MagicMock(return_value=False)
        crew._merge_acceptable = MagicMock(return_value=True)

        crew._backfill_and_demote(refined, skip_selection=False)

        # The merge was accepted (members absorbed) -> its group must be pruned.
        assert crew.overlap_groups == []

    def test_overlap_groups_rejected_merge_group_retained(self, monkeypatch):
        (crew, refined, ideas, orig_pivot, member_a, member_b, pivot_rev,
         merged_idea) = self._pivot_and_merge_setup(monkeypatch)
        crew._score_wave = lambda wave, **kw: None
        crew._pivot_acceptable = MagicMock(return_value=False)
        crew._merge_acceptable = MagicMock(return_value=False)

        crew._backfill_and_demote(refined, skip_selection=False)

        # The merge was rejected (variants kept, still separate) -> group stays for the
        # frontend's pick-between-these hint.
        assert crew.overlap_groups == [
            {"idea_names": ["VariantA", "VariantB"], "shared_product": "Widget"}]


# ---------------------------------------------------------------------------
# _dedup_tournament_winners: post-tournament winner dedup determinism (2026-07-10 audit)
# ---------------------------------------------------------------------------

class TestDedupTournamentWinners:
    def test_keeps_higher_composite_duplicate_regardless_of_completion_order(self):
        weak = _idea("Widget", mf=0.3, technical_feasibility_score=0.3, novelty_score=0.3,
                     seo_scalability_score=0.3)
        strong = _idea("Widget", mf=0.9, technical_feasibility_score=0.9, novelty_score=0.9,
                       seo_scalability_score=0.9)
        # weak "completes" first
        out = UnifiedSolutionCrew._dedup_tournament_winners([weak, strong])
        assert len(out) == 1 and out[0] is strong
        # strong "completes" first — same result regardless of completion order
        out2 = UnifiedSolutionCrew._dedup_tournament_winners([strong, weak])
        assert len(out2) == 1 and out2[0] is strong

    def test_equal_composite_and_name_keeps_first_seen(self):
        first = _idea("Widget", mf=0.5, technical_feasibility_score=0.5, novelty_score=0.5,
                      seo_scalability_score=0.5)
        second = _idea("Widget", mf=0.5, technical_feasibility_score=0.5, novelty_score=0.5,
                       seo_scalability_score=0.5)
        out = UnifiedSolutionCrew._dedup_tournament_winners([first, second])
        assert len(out) == 1 and out[0] is first

    def test_distinct_names_and_empty_names_all_preserved(self):
        a = _idea("Alpha", mf=0.5)
        b = _idea("Beta", mf=0.5)
        no_name = _idea("", mf=0.5, solution_name=None)  # missing entirely — never deduped
        out = UnifiedSolutionCrew._dedup_tournament_winners([a, None, b, no_name])
        assert out == [a, b, no_name]


# ---------------------------------------------------------------------------
# _score_wave: `_birth_verified_names` in-place update (2026-07-10 parallelization audit)
# ---------------------------------------------------------------------------

class TestScoreWaveBirthVerifiedNames:
    def test_updates_in_place_preserving_set_identity(self):
        crew = _crew()
        self._install_noop_wave_methods(crew)
        crew._birth_verified_names = {"Pre-existing"}
        original_set = crew._birth_verified_names

        new_idea = _idea("New")
        crew._score_wave([new_idea], birth_verified=[new_idea])

        # Identity preserved (no reassignment) — only in-place additions.
        assert crew._birth_verified_names is original_set
        assert crew._birth_verified_names == {"Pre-existing", "New"}

    @staticmethod
    def _install_noop_wave_methods(crew):
        crew._finalize_feasibility = lambda wave: None
        crew._finalize_idea_pool = lambda wave: None
        crew._verify_pool_routes = lambda wave: None
        crew._filter_pain_relevance = lambda wave: None
        crew._stamp_payability = lambda w: None
        crew._finalize_dev_time = lambda wave: None
        crew._probe_mechanism_parity = lambda wave: None
        crew._validate_idea_caps = lambda w: None
        crew._classify_idea_angles = lambda wave: None
        crew._calibrate_idea_scores = lambda wave: None
