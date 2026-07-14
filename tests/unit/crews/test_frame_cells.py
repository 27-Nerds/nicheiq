"""Multi-Frame Idea Generation Portfolio: allocator reserve-carve, seed gates, anchor linkage,
provenance stamping, and the reviewer's two-clause frame lock.

Covers: `_build_partition_cells` byte-identical-at-zero + floors-preserved-with-frames-on,
`_mint_frame_cells` seed gates, `anchor_pains_for_frame_focus`, `_group_pool_by_cell` frame/focus
grouping, `_carry_provenance` source_frame stamping, `CellGrounding.as_block` pain verbatim lock,
and the v4 reviewer's frame directive.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nicheiq.config.settings import settings
from nicheiq.crews.idea_improvement_loop import CellGrounding
from nicheiq.crews.idea_improvement_loop_v4 import _reviewer_system
from nicheiq.crews.unified_solution_crew import (
    _GENERIC_DATA_ROUTES, UnifiedSolutionCrew, _assign_generator_cells,
)
from nicheiq.utils.frames import FRAME_REGISTRY, FrameFocus, anchor_pains_for_frame_focus


def _crew(**extra):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _pain(title, severity=0.5, commercial=0.5, opportunity="medium", **kw):
    base = dict(title=title, severity_score=severity, commercial_intent=commercial,
                opportunity_level=opportunity, affected_segments=None,
                pain_point_alignment=None, representative_quotes=[], description="",
                parent_theme_id=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _segment(name, **kw):
    base = dict(segment_name=name, pain_point_alignment=None, motivation_drivers=[],
                expertise_level="Intermediate", budget_sensitivity="Medium")
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# _build_partition_cells: byte-identical when no frame seeds mint, floors preserved with
# frames on
# ---------------------------------------------------------------------------

class TestBuildPartitionCellsAllocator:
    def test_no_frame_seed_data_stays_byte_identical_to_legacy_allocator(self, monkeypatch):
        # gap/data_asset/workflow are ALWAYS ON (permanent, adopted 2026-07-10 after the
        # Multi-Frame A/B concluded) — but with no incumbent rows, no data-route menu, and no
        # synthesized job-map, `_mint_frame_cells` mints zero cells, so the pain allocation must
        # be untouched (Fix #1: no additive "frame"/"focus" stamp at all when nothing minted).
        monkeypatch.setattr(settings, "divergent_target_generators", 3)
        monkeypatch.setattr(settings, "divergent_max_generators", 6)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain(f"P{i}", severity=0.5 - i * 0.05) for i in range(4)]
        segA, segB = _segment("SegA"), _segment("SegB")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA, segB]))
        crew._segment_payability_map = lambda: {}
        crew._build_data_menu = lambda: ""
        crew._build_dissatisfaction_block = lambda: ""
        crew._workflow_focus_cache = []

        cells = crew._build_partition_cells(pains, [])
        legacy = _assign_generator_cells(pains, [segA, segB], target=3, max_gen=6,
                                         relevance=None, severity_floor=0, commercial_floor=0,
                                         commercial_min_intent=settings.divergent_commercial_floor_min_intent)

        assert [c["pain"] for c in cells] == [c["pain"] for c in legacy]
        assert [c.get("segment") for c in cells] == [c.get("segment") for c in legacy]
        # Fix #1: at all-zero frame counts the cells must be byte-identical to the legacy
        # allocator's raw dicts — no additive "frame"/"focus" stamp at all.
        assert all("frame" not in c and "focus" not in c for c in cells)

    def test_floors_preserved_when_frames_carve_the_budget(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 3)
        monkeypatch.setattr(settings, "divergent_max_generators", 5)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 1)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        # Floored pain has by far the top severity but LOW opportunity, so plain
        # opportunity-ranked allocation would never pick it without the Round-0 floor.
        floored = _pain("Floored pain", severity=0.95, opportunity="low")
        others = [_pain(f"P{i}", severity=0.3, opportunity="high") for i in range(3)]
        pains = [floored] + others
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]))
        gap_focus = FrameFocus(frame="gap", key="gap:acme", payload={"incumbent_name": "Acme"},
                               anchor_pain_titles=["P0"])
        crew._mint_frame_cells = lambda pains, segments, budget: [
            {"frame": "gap", "focus": gap_focus, "segment": segA, "pain": None}
        ]

        cells = crew._build_partition_cells(pains, [])
        pain_titles = [getattr(c["pain"], "title", None) for c in cells if c["frame"] == "pain"]
        frame_count = sum(1 for c in cells if c["frame"] != "pain")

        assert "Floored pain" in pain_titles
        assert frame_count == 1
        # Budget respected: pain cells + frame cells never exceed max_gen.
        assert len(cells) <= settings.divergent_max_generators


# ---------------------------------------------------------------------------
# _build_partition_cells: stated-audience floor (Round 0c, workstream D of the audience-rebalance
# plan) — mirrors the severity/commercial floor injection + reserve-math tests above.
# ---------------------------------------------------------------------------

class TestStatedAudienceFloorAllocator:
    def test_floor_lifts_matching_pain_not_in_selected(self, monkeypatch):
        # max_gen == target (no slack) so the multi-frame widen loop can never fire and confound
        # the assertion — the ONLY way "Commission pain" (outside selected_pains, only reachable
        # via extra_pains -> all_pains) can appear is the Round-0c injection.
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 1)
        selected = [_pain("P0", severity=0.5), _pain("P1", severity=0.45)]
        matching = _pain("Commission pain", severity=0.3, affected_segments=["Insurance Agents"])
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=selected + [matching]),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     niche_context=SimpleNamespace(niche_description="",
                                                    resolved_primary_audience="insurance agents",
                                                    user_target_audience=None))

        cells = crew._build_partition_cells(selected, [matching])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Commission pain" in titles

    def test_no_stated_audience_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 1)
        selected = [_pain("P0", severity=0.5), _pain("P1", severity=0.45)]
        matching = _pain("Commission pain", severity=0.3, affected_segments=["Insurance Agents"])
        segA = _segment("SegA")
        # Both resolved_primary_audience and user_target_audience are None (plain-niche run) —
        # the whole floor block must no-op even though the count is 1 and a matching pain exists.
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=selected + [matching]),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     niche_context=SimpleNamespace(niche_description="",
                                                    resolved_primary_audience=None,
                                                    user_target_audience=None))

        cells = crew._build_partition_cells(selected, [matching])
        titles = [getattr(c["pain"], "title", None) for c in cells if c.get("frame", "pain") == "pain"]

        assert "Commission pain" not in titles

    def test_reserve_math_accounts_for_audience_floor_pain(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 3)
        monkeypatch.setattr(settings, "divergent_max_generators", 5)
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        monkeypatch.setattr(settings, "divergent_stated_audience_floor_count", 1)
        # Floored pain matches the stated audience but has LOW severity/opportunity, so plain
        # opportunity-ranked allocation would never pick it without the Round-0c floor — the frame
        # reserve math must still leave it room (unique_floor_ids must fold in the audience floor).
        floored = _pain("Commission pain", severity=0.2, opportunity="low",
                        affected_segments=["Insurance Agents"])
        others = [_pain(f"P{i}", severity=0.6 - i * 0.05, opportunity="high") for i in range(3)]
        pains = [floored] + others
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]),
                     niche_context=SimpleNamespace(niche_description="",
                                                    resolved_primary_audience="insurance agents",
                                                    user_target_audience=None))
        gap_focus = FrameFocus(frame="gap", key="gap:acme", payload={"incumbent_name": "Acme"},
                               anchor_pain_titles=["P0"])
        crew._mint_frame_cells = lambda pains, segments, budget: [
            {"frame": "gap", "focus": gap_focus, "segment": segA, "pain": None}
        ]

        cells = crew._build_partition_cells(pains, [])
        pain_titles = [getattr(c["pain"], "title", None) for c in cells if c["frame"] == "pain"]
        frame_count = sum(1 for c in cells if c["frame"] != "pain")

        assert "Commission pain" in pain_titles
        assert frame_count == 1
        assert len(cells) <= settings.divergent_max_generators


# ---------------------------------------------------------------------------
# _mint_frame_cells: seed gates
# ---------------------------------------------------------------------------

class TestSeedGates:
    def test_empty_incumbent_map_yields_no_gap_cell(self):
        crew = _crew(_incumbent_rows=None)
        assert crew._seed_gap_focuses() == []

    def test_incumbent_rows_without_a_real_gap_yields_no_gap_cell(self):
        crew = _crew(_incumbent_rows=[
            {"name": "Acme", "pricing": "$10/mo", "gap": "", "focus": "x"},
            {"name": "Bolt", "pricing": "free", "gap": "n/a", "focus": "y"},
        ])
        assert crew._seed_gap_focuses() == []

    def test_generic_only_data_menu_yields_no_data_asset_cell(self):
        crew = _crew()
        crew._build_data_menu = lambda: "\n".join(f"- {r}" for r in _GENERIC_DATA_ROUTES)
        assert crew._seed_data_asset_focuses() == []

    def test_niche_specific_data_route_yields_a_data_asset_cell(self):
        crew = _crew()
        crew._build_data_menu = lambda: "- USDA public registry (official) — ingredient safety data"
        focuses = crew._seed_data_asset_focuses()
        assert len(focuses) == 1
        assert focuses[0].payload["route_text"].startswith("USDA")

    def test_data_asset_focus_carries_cadence_note(self):
        # Fix 2 (2026-07-10, live-motivated): a merged data_asset idea assumed a WEEKLY feed off
        # a source that was actually a 1908-2017 HISTORICAL index — the seeded focus's payload
        # must carry the cadence-check instruction, and the rendered brief must include it.
        from nicheiq.utils.frames import FRAME_REGISTRY, _DATA_ASSET_CADENCE_NOTE

        crew = _crew()
        crew._build_data_menu = lambda: "- USDA public registry (official) — ingredient safety data"
        focuses = crew._seed_data_asset_focuses()
        assert focuses[0].payload["cadence_note"] == _DATA_ASSET_CADENCE_NOTE
        brief = FRAME_REGISTRY["data_asset"].brief_formatter(focuses[0])
        assert _DATA_ASSET_CADENCE_NOTE in brief


# ---------------------------------------------------------------------------
# spend_adjacent: deleted permanently 2026-07-10 (Multi-Frame A/B concluded)
# ---------------------------------------------------------------------------

class TestSpendAdjacentRemoved:
    def test_not_in_frame_registry(self):
        assert "spend_adjacent" not in FRAME_REGISTRY
        assert set(FRAME_REGISTRY.keys()) == {"pain", "gap", "data_asset", "workflow", "user_seed"}

    def test_seeder_method_removed(self):
        assert not hasattr(UnifiedSolutionCrew, "_seed_spend_focuses")


# ---------------------------------------------------------------------------
# anchor_pains_for_frame_focus: SPECIFIC linkage gate (Codex BLOCKER-2)
# ---------------------------------------------------------------------------

class TestAnchorPainsForFrameFocus:
    def test_unrelated_focus_yields_no_anchor_pains(self):
        focus = FrameFocus(
            frame="gap", key="gap:x",
            payload={"incumbent_name": "Zyphon Analytics",
                     "gap": "no mobile offline sync capability"},
            anchor_pain_titles=[])
        pains = [_pain("Cake pricing takes forever to calculate",
                       description="Bakers spend hours on spreadsheet pricing math.")]
        assert anchor_pains_for_frame_focus(focus, pains) == []

    def test_specific_overlap_anchors_the_matching_pain(self):
        focus = FrameFocus(
            frame="gap", key="gap:x",
            payload={"incumbent_name": "CakeCost Pro",
                     "gap": "no bulk ingredient pricing import"},
            anchor_pain_titles=[])
        matching = _pain("Bulk ingredient pricing import is manual",
                         description="Bakers manually re-enter bulk ingredient pricing every batch.")
        unrelated = _pain("Wedding date scheduling conflicts",
                          description="Couples double-book venues on peak wedding season weekends.")
        titles = anchor_pains_for_frame_focus(focus, [matching, unrelated])
        assert titles == [matching.title]

    def test_a_focus_dropped_at_mint_time_when_anchor_empty(self):
        crew = _crew()
        crew._segment_payability_map = lambda: {}
        unrelated_focus = FrameFocus(
            frame="gap", key="gap:zyphon", payload={"incumbent_name": "Zyphon", "gap": "no API"},
            anchor_pain_titles=[])
        crew._seed_gap_focuses = lambda: [unrelated_focus]
        crew._seed_data_asset_focuses = lambda: []
        crew._seed_workflow_focuses = lambda: []
        pains = [_pain("Totally unrelated pain about invoicing",
                       description="Freelancers hate manually formatting PDF invoices.")]
        minted = crew._mint_frame_cells(pains, [], budget=1)
        assert minted == []


# ---------------------------------------------------------------------------
# _group_pool_by_cell: frame/focus grouping key separates two frames on one segment
# ---------------------------------------------------------------------------

class TestGroupPoolByCell:
    def test_two_frames_same_segment_stay_separate_groups(self):
        segA = _segment("SegA")
        gap_focus = FrameFocus(frame="gap", key="gap:acme", payload={}, anchor_pain_titles=["P0"])
        data_focus = FrameFocus(frame="data_asset", key="data_asset:usda", payload={},
                                anchor_pain_titles=["P0"])
        cells = [
            {"frame": "gap", "pain": None, "focus": gap_focus, "segment": segA},
            {"frame": "data_asset", "pain": None, "focus": data_focus, "segment": segA},
        ]
        c1 = SimpleNamespace(source_frame="gap", source_focus_key="gap:acme",
                             source_pain=None, source_segment="SegA")
        c2 = SimpleNamespace(source_frame="data_asset", source_focus_key="data_asset:usda",
                             source_pain=None, source_segment="SegA")
        groups = UnifiedSolutionCrew._group_pool_by_cell([c1, c2], cells)
        assert len(groups) == 2
        by_frame = {cell["frame"]: cands for cell, cands in groups}
        assert by_frame["gap"] == [c1]
        assert by_frame["data_asset"] == [c2]

    def test_pain_cells_group_exactly_as_before(self):
        pain = _pain("P0")
        segA = _segment("SegA")
        cells = [{"frame": "pain", "pain": pain, "focus": None, "segment": segA}]
        c1 = SimpleNamespace(source_frame="pain", source_focus_key=None,
                             source_pain="P0", source_segment="SegA")
        groups = UnifiedSolutionCrew._group_pool_by_cell([c1], cells)
        assert len(groups) == 1
        assert groups[0][1] == [c1]


# ---------------------------------------------------------------------------
# source_frame survives stamp -> _carry_provenance
# ---------------------------------------------------------------------------

class TestCarryProvenance:
    def test_source_frame_survives_stamp_to_carry(self):
        crew = _crew()
        concept = SimpleNamespace(
            concept_name="GapWedge", mechanism_tag="m", data_source_tag="d", journey_tag="j",
            obviousness_score=0.4, source_pain=None, source_segment="SegA", source_frame="gap")
        raw_concepts = SimpleNamespace(concepts=[concept])
        idea = SimpleNamespace(solution_name="GapWedge", mechanism_tag=None, data_source_tag=None,
                               journey_tag=None, obviousness_score=None, source_pain=None,
                               source_segment=None, source_frame=None,
                               pain_points_addressed=["stale"])
        refined = SimpleNamespace(solution_ideas=[idea])

        crew._carry_provenance(refined, raw_concepts)

        assert idea.source_frame == "gap"
        assert idea.source_pain is None
        assert idea.source_segment == "SegA"
        # No source_pain -> pain_points_addressed is left untouched (convergent-path limitation,
        # tournament-path frame ideas are already grounded before this ever runs).
        assert idea.pain_points_addressed == ["stale"]

    def test_pain_concept_still_grounds_pain_points_addressed(self, monkeypatch):
        crew = _crew()
        crew._provenance_segment_for_pain = lambda title: "SegA"
        crew._grounded_pains_for = lambda src_pain, seg: [src_pain]
        concept = SimpleNamespace(
            concept_name="PainWinner", mechanism_tag="m", data_source_tag="d", journey_tag="j",
            obviousness_score=0.4, source_pain="P0", source_segment="SegA", source_frame="pain")
        raw_concepts = SimpleNamespace(concepts=[concept])
        idea = SimpleNamespace(solution_name="PainWinner", mechanism_tag=None, data_source_tag=None,
                               journey_tag=None, obviousness_score=None, source_pain=None,
                               source_segment=None, source_frame=None,
                               pain_points_addressed=["stale"])
        refined = SimpleNamespace(solution_ideas=[idea])

        crew._carry_provenance(refined, raw_concepts)

        assert idea.source_frame == "pain"
        assert idea.source_pain == "P0"
        assert idea.pain_points_addressed == ["P0"]


# ---------------------------------------------------------------------------
# CellGrounding.as_block: pain path verbatim lock
# ---------------------------------------------------------------------------

class TestCellGroundingAsBlock:
    def test_pain_cell_block_is_byte_identical_to_the_original_template(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers",
            segment_profile="motivations: side income; expertise: Beginner; budget: High",
            pain_title="Pricing takes too long", pain_evidence="Bakers hate manual pricing.\n  \"ugh\"",
            pain_severity="high", competitor_mentions="- CakeCost", wallet_norm="",
        )
        expected = (
            f"NICHE: {g.niche}\n"
            f"TARGET AUDIENCE SEGMENT: {g.audience_segment}\n"
            f"SEGMENT PROFILE: {g.segment_profile}\n"
            f"SOURCE PAIN: {g.pain_title}\n"
            f"PAIN EVIDENCE (severity {g.pain_severity}):\n{g.pain_evidence}\n"
            f"COMPETITORS ALREADY IN THIS SPACE:\n{g.competitor_mentions}\n"
            f"DETERMINISTIC SCORE FLAGS (hard signal — treat as ground truth):\n  (none)"
        )
        assert g.as_block() == expected

    def test_frame_cell_block_renders_the_new_sections(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_evidence="  - Pricing takes too long: bakers hate manual pricing",
            competitor_mentions="", wallet_norm="",
            frame_type="gap", focus_block="INCUMBENT: CakeCost Pro\n  Structural gap: no bulk import",
        )
        block = g.as_block()
        assert "PRODUCT FRAME: gap" in block
        assert "THE FOCUS:\nINCUMBENT: CakeCost Pro" in block
        assert "VALIDATED ANCHOR PAINS" in block
        assert "SOURCE PAIN:" not in block


# ---------------------------------------------------------------------------
# Reviewer prompt: two-clause frame lock (Codex BLOCKER-2 reviewer side)
# ---------------------------------------------------------------------------

class TestReviewerFrameDirective:
    def test_gap_frame_reviewer_prompt_has_both_clauses(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_evidence="  - Pricing takes too long: bakers hate manual pricing",
            competitor_mentions="", wallet_norm="",
            frame_type="gap", focus_block="INCUMBENT: CakeCost Pro\n  Structural gap: no bulk import",
        )
        content = _reviewer_system(g)["content"]
        assert "PRODUCT FRAME = GAP" in content
        assert FRAME_REGISTRY["gap"].mf_anchor in content
        assert "ANCHOR PAINS listed (exact titles)" in content
        assert "market_fit ≤ 0.3" in content

    def test_pain_cell_reviewer_prompt_has_no_frame_directive(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_title="Pricing takes too long", pain_evidence="evidence", pain_severity="high",
            competitor_mentions="", wallet_norm="",
        )
        content = _reviewer_system(g)["content"]
        assert "PRODUCT FRAME" not in content


class TestOlderLoopReviewerFrameDirective:
    """Fix #5: the OLDER ideator<->reviewer loop's `_reviewer_system` still scored only "THE
    SOURCE PAIN BELOW" despite `CellGrounding` already being frame-aware — `_frame_directive` was
    ported from _v4 and prepended here too."""

    def test_gap_frame_reviewer_prompt_has_both_clauses(self):
        from nicheiq.crews.idea_improvement_loop import _reviewer_system as _older_reviewer_system

        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_evidence="  - Pricing takes too long: bakers hate manual pricing",
            competitor_mentions="", wallet_norm="",
            frame_type="gap", focus_block="INCUMBENT: CakeCost Pro\n  Structural gap: no bulk import",
        )
        content = _older_reviewer_system(g)["content"]
        assert "PRODUCT FRAME = GAP" in content
        assert FRAME_REGISTRY["gap"].mf_anchor in content
        assert "ANCHOR PAINS listed (exact titles)" in content
        assert "market_fit ≤ 0.3" in content

    def test_pain_cell_reviewer_prompt_has_no_frame_directive(self):
        from nicheiq.crews.idea_improvement_loop import _reviewer_system as _older_reviewer_system

        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_title="Pricing takes too long", pain_evidence="evidence", pain_severity="high",
            competitor_mentions="", wallet_norm="",
        )
        content = _older_reviewer_system(g)["content"]
        assert "PRODUCT FRAME" not in content
        assert "THE SOURCE PAIN BELOW" in content  # original pain-path prompt untouched


class TestReviewerModalCaseInstruction:
    """The v4 reviewer's `_reviewer_system` prompt includes a MODAL CASE bullet (2026-07-10)
    telling the reviewer to state the most common concrete instance of the source pain and
    score market_fit ≤ 0.4 (flag NEEDS-VERIFY: modal-case) when the specced mechanism wouldn't
    handle it."""

    def test_modal_case_instruction_present(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_title="Pricing takes too long", pain_evidence="evidence", pain_severity="high",
            competitor_mentions="", wallet_norm="",
        )
        content = _reviewer_system(g)["content"]
        assert "MODAL CASE" in content
        assert "NEEDS-VERIFY: modal-case" in content


# ---------------------------------------------------------------------------
# _mint_frame_cells: lazy enumeration respects the reserve budget (fix #2)
# ---------------------------------------------------------------------------

class TestMintFrameCellsLazyEnumeration:
    def test_budget_zero_returns_immediately_with_no_enumerator_calls(self):
        crew = _crew()
        gap_calls = MagicMock(return_value=[])
        crew._seed_gap_focuses = gap_calls

        minted = crew._mint_frame_cells([], [], budget=0)

        assert minted == []
        gap_calls.assert_not_called()

    def test_capacity_one_with_three_frames_only_calls_the_first_priority_enumerator(self):
        # FRAME_REGISTRY priority order is gap, data_asset, workflow — with a budget of 1 the
        # gap cell alone fills capacity, so data_asset/workflow's seed enumerators (search/LLM
        # calls in production) must never run at all.
        crew = _crew()
        crew._segment_payability_map = lambda: {}

        pain = _pain("Bulk ingredient pricing import is manual",
                     description="Bakers manually re-enter bulk ingredient pricing every batch.")
        gap_focus = FrameFocus(
            frame="gap", key="gap:x",
            payload={"incumbent_name": "CakeCost Pro", "gap": "no bulk ingredient pricing import"},
            anchor_pain_titles=[])

        gap_calls = MagicMock(return_value=[gap_focus])
        data_asset_calls = MagicMock(return_value=[])
        workflow_calls = MagicMock(return_value=[])
        crew._seed_gap_focuses = gap_calls
        crew._seed_data_asset_focuses = data_asset_calls
        crew._seed_workflow_focuses = workflow_calls

        minted = crew._mint_frame_cells([pain], [], budget=1)

        assert len(minted) == 1
        assert minted[0]["frame"] == "gap"
        gap_calls.assert_called_once()
        data_asset_calls.assert_not_called()
        workflow_calls.assert_not_called()

    def test_gap_data_asset_workflow_each_mint_one_cell_when_seeds_and_anchors_exist(self):
        # Locks the new permanent behavior (2026-07-10): with enough budget and real anchor-
        # linked seed data for all three, each ALWAYS-ON frame mints exactly 1 cell.
        crew = _crew()
        crew._segment_payability_map = lambda: {}

        pain = _pain("Bulk ingredient pricing import is manual",
                     description="Bakers manually re-enter bulk ingredient pricing every batch.")
        gap_focus = FrameFocus(
            frame="gap", key="gap:x",
            payload={"incumbent_name": "CakeCost Pro", "gap": "no bulk ingredient pricing import"},
            anchor_pain_titles=[])
        data_focus = FrameFocus(
            frame="data_asset", key="data_asset:x",
            payload={"route_text": "bulk ingredient pricing import registry"},
            anchor_pain_titles=[])
        workflow_focus = FrameFocus(
            frame="workflow", key="workflow:x",
            payload={"job_statement": "bulk ingredient pricing import for a batch"},
            anchor_pain_titles=[])
        crew._seed_gap_focuses = lambda: [gap_focus]
        crew._seed_data_asset_focuses = lambda: [data_focus]
        crew._seed_workflow_focuses = lambda: [workflow_focus]

        minted = crew._mint_frame_cells([pain], [], budget=3)

        assert len(minted) == 3
        assert {c["frame"] for c in minted} == {"gap", "data_asset", "workflow"}
        for c in minted:
            assert c["pain"] is None
            assert c["focus"].anchor_pain_titles == [pain.title]

    def test_all_three_frames_skipped_cleanly_when_no_seed_data(self):
        # (e) a frame with no candidate seeds is SKIPPED, never a crash.
        crew = _crew()
        crew._segment_payability_map = lambda: {}
        crew._seed_gap_focuses = lambda: []
        crew._seed_data_asset_focuses = lambda: []
        crew._seed_workflow_focuses = lambda: []

        minted = crew._mint_frame_cells([], [], budget=3)

        assert minted == []


# ---------------------------------------------------------------------------
# pain_min clamp (fix #3): floors+2 must never exceed max_gen
# ---------------------------------------------------------------------------

class TestPainMinClamp:
    def test_pain_min_clamps_to_max_gen_and_warns(self, monkeypatch):
        monkeypatch.setattr(settings, "divergent_target_generators", 2)
        monkeypatch.setattr(settings, "divergent_max_generators", 2)
        # unique_floor_count + 2 = 3 + 2 = 5, but max_gen is only 2 -> pain_min must clamp to 2,
        # forcing max_frames (the budget handed to _mint_frame_cells) to 0.
        monkeypatch.setattr(settings, "divergent_severity_floor_count", 3)
        monkeypatch.setattr(settings, "divergent_commercial_floor_count", 0)
        pains = [_pain(f"P{i}", severity=0.9 - i * 0.05) for i in range(3)]
        segA = _segment("SegA")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=pains),
                     audience_mapping=SimpleNamespace(audience_segments=[segA]))
        mint_calls = MagicMock(return_value=[])
        crew._mint_frame_cells = mint_calls

        from loguru import logger
        messages = []
        capture_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
        try:
            cells = crew._build_partition_cells(pains, [])
        finally:
            logger.remove(capture_id)

        assert mint_calls.call_args.kwargs["budget"] == 0
        assert any("pain_min clamped" in m for m in messages)
        assert len(cells) <= settings.divergent_max_generators


# ---------------------------------------------------------------------------
# Pre-dedup top-up (fix #7): must never fall back to non-pain cells
# ---------------------------------------------------------------------------

class TestTopupSkippedWhenNoPainCells:
    def test_all_frame_cell_pool_never_top_ups_from_a_frame_cell(self):
        crew = _crew()
        crew._build_data_menu = lambda: ""
        crew._build_dissatisfaction_block = lambda: ""
        crew._probe_niche_wallet = lambda: {}
        crew._wallet_prompt_line = lambda: ""
        crew._build_market_reality_block = lambda: ""
        crew._run_divergent_fanout = lambda jobs, deadline, max_workers: ([], [])
        one_sample_calls = MagicMock()
        crew._one_sample = one_sample_calls

        gap_focus = FrameFocus(frame="gap", key="gap:acme", payload={"incumbent_name": "Acme"},
                               anchor_pain_titles=["P0"])
        data_focus = FrameFocus(frame="data_asset", key="data_asset:usda", payload={},
                                anchor_pain_titles=["P0"])
        cells = [
            {"frame": "gap", "pain": None, "focus": gap_focus, "segment": None},
            {"frame": "data_asset", "pain": None, "focus": data_focus, "segment": None},
        ]

        pooled, usages = crew._generate_divergent_pool_partitioned(
            inputs={}, cells=cells, pool=[("some-model", "medium")], deadline=None)

        # Fanout returned an empty (well below the 9-target) pool, but with ZERO pain cells the
        # top-up loop must skip entirely rather than falling back to a frame cell.
        assert pooled == []
        one_sample_calls.assert_not_called()


# ---------------------------------------------------------------------------
# Loser-stub anchors (fix #4): non-pain cell stubs use anchor_pain_titles, not source_pain
# ---------------------------------------------------------------------------

class TestLoserStubAnchors:
    @staticmethod
    def _concept(**kw):
        base = dict(concept_name="Concept", one_liner="does the thing", mechanism_tag="m",
                    source_segment="SegA", source_pain=None, why_non_obvious="",
                    data_route="", data_acquisition_notes="", data_access_model=None,
                    build_feasibility_score=0.7, data_feasibility_score=0.7,
                    target_keywords=[], project_type=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_pain_cell_stub_stamps_source_pain_and_frame(self):
        c = self._concept(source_pain="P0")
        cell = {"frame": "pain", "pain": _pain("P0"), "focus": None, "segment": None}
        stub = UnifiedSolutionCrew._loser_stub_idea(c, cell=cell)
        assert stub.source_frame == "pain"
        assert stub.source_pain == "P0"
        assert stub.pain_points_addressed == ["P0"]

    def test_frame_cell_stub_uses_anchor_pain_titles_not_source_pain(self):
        c = self._concept(source_pain=None)
        focus = FrameFocus(frame="gap", key="gap:acme", payload={},
                           anchor_pain_titles=["Anchor pain A", "Anchor pain B"])
        cell = {"frame": "gap", "pain": None, "focus": focus, "segment": None}
        stub = UnifiedSolutionCrew._loser_stub_idea(c, cell=cell)
        assert stub.source_frame == "gap"
        assert stub.source_pain is None
        assert stub.pain_points_addressed == ["Anchor pain A", "Anchor pain B"]

    def test_no_cell_arg_defaults_to_legacy_pain_behavior(self):
        c = self._concept(source_pain="P0")
        stub = UnifiedSolutionCrew._loser_stub_idea(c)
        assert stub.source_frame == "pain"
        assert stub.pain_points_addressed == ["P0"]


# ---------------------------------------------------------------------------
# Parity pivot preserves source_frame (fix #6)
# ---------------------------------------------------------------------------

class _FakePivotResult:
    """Stand-in for the LLM-returned `_Pivot` pydantic model — only `.model_dump()` is used."""

    def __init__(self, **kw):
        self._data = kw

    def model_dump(self):
        return dict(self._data)


class TestParityPivotPreservesSourceFrame:
    def test_accepted_pivot_of_a_frame_idea_keeps_its_source_frame(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_pivot_max_revisions", 3)
        crew = _crew(_incumbent_rows=[])

        def _stamp_scored_cleared(wave):
            # mimics _score_wave's calibration critic (novelty/seo) + parity re-probe
            for rev in wave:
                rev.incumbent_parity = "none found"
                rev.novelty_score = 0.6
                rev.seo_scalability_score = 0.6
        crew._score_wave = _stamp_scored_cleared

        orig = SimpleNamespace(
            solution_name="GapIdea", value_proposition="attacks the incumbent's gap",
            technical_approach="", incumbent_parity="shipped by Acme",
            candidate_status="active", market_fit_score=0.45, technical_feasibility_score=0.5,
            novelty_score=0.5, seo_scalability_score=0.5, winning_angle=None,
            source_pain=None, source_segment="SegA", source_frame="gap",
            idea_tier="single", pain_points_addressed=["Anchor pain A"], target_personas=["Bakers"],
        )
        ideas = [orig]
        refined = SimpleNamespace(solution_ideas=ideas)
        fake = _FakePivotResult(
            solution_name="PivotedGapIdea", value_proposition="wedge into the gap",
            description="Attacks the incumbent's known gap.", core_features=["gap-filling workflow"],
            conventional_approach="", innovation_angle="", why_it_works="", technical_approach="",
            data_access_model="public", market_fit_score=0.75, technical_feasibility_score=0.8,
            build_feasibility_score=0.7, data_feasibility_score=0.7, programmatic_seo_opportunity="",
        )
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            attempted, accepted = crew._parity_pivot_revisions(refined)

        assert attempted == 1
        assert accepted == 1
        assert len(ideas) == 1
        assert ideas[0].solution_name == "PivotedGapIdea"
        # Fix #6: the pivot reconstruction must carry the ORIGINAL idea's source_frame forward —
        # without it, an accepted pivot of a frame idea silently resets to 'pain'.
        assert ideas[0].source_frame == "gap"
