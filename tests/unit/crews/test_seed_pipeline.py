"""User-seed pipeline (eager-meandering-feather.md Phase 4): the `user_seed` reviewer rule,
`_run_seed_cell` (real birth path), `execute_seed_pipeline` (orchestration), and
`hydrate_from_state` (Phase-1 cache restore, no cold re-probe).

LLM-touching internals (`_one_sample`, `tournament_refine_cell_v4`, `_score_cell_winner`,
`_score_wave`, `_finalize_seed_tail`) are mocked — this module tests WIRING, not their own
already-covered internals (see test_per_cell_tournament.py / test_backfill_demote.py).
"""

from types import SimpleNamespace

import nicheiq.crews.idea_improvement_loop_v4 as v4
import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.idea_improvement_loop import CellGrounding
from nicheiq.crews.idea_improvement_loop_v4 import _ideator_system, _reviewer_system
from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew
from nicheiq.utils.frames import FRAME_REGISTRY, FrameFocus
from nicheiq.utils.seed_fidelity import is_seed_faithful


def _crew(**extra):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(audience_segments=[], tools_currently_used=[],
                                            frustrations_with_existing=[])
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._incumbent_rows = None
    crew._niche_wallet_brief = {}
    crew._dissatisfaction_signals = []
    for k, v in extra.items():
        setattr(crew, k, v)
    return crew


def _pain(title, description="", quotes=None):
    return SimpleNamespace(title=title, description=description,
                           representative_quotes=quotes or [])


# ---------------------------------------------------------------------------
# _frame_directive / CellGrounding: the user_seed unanchored reviewer rule
# ---------------------------------------------------------------------------

class TestUnanchoredSeedReviewerRule:
    def test_unanchored_user_seed_gets_no_cap_and_no_fabrication_instruction(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="the niche audience", segment_profile="",
            pain_evidence="  n/a", competitor_mentions="", wallet_norm="",
            frame_type="user_seed", focus_block="A satellite tracker for amateur astronomers",
            unanchored=True,
        )
        content = _reviewer_system(g)["content"]
        assert "PRODUCT FRAME = USER_SEED (UNANCHORED HYPOTHESIS)" in content
        assert "market_fit ≤ 0.3" not in content
        assert "do NOT claim" in content.lower() or "do not claim" in content.lower()
        assert "UNGROUNDED hypothesis" in content

    def test_anchored_user_seed_gets_the_same_two_clause_treatment_as_other_frames(self):
        g = CellGrounding(
            niche="cottage food", audience_segment="Home bakers", segment_profile="",
            pain_evidence="  - Cakes take too long to price: bakers hate manual pricing",
            competitor_mentions="", wallet_norm="",
            frame_type="user_seed", focus_block="A tool that prices custom cakes",
            unanchored=False,
        )
        content = _reviewer_system(g)["content"]
        assert "PRODUCT FRAME = USER_SEED" in content
        assert "UNANCHORED HYPOTHESIS" not in content
        assert FRAME_REGISTRY["user_seed"].mf_anchor in content
        assert "ANCHOR PAINS listed (exact titles)" in content
        assert "market_fit ≤ 0.3" in content

    def test_as_block_unanchored_header_never_implies_a_required_anchor(self):
        g = CellGrounding(
            niche="n", audience_segment="the niche audience", segment_profile="",
            pain_evidence="  n/a", competitor_mentions="", wallet_norm="",
            frame_type="user_seed", focus_block="idea text", unanchored=True,
        )
        block = g.as_block()
        assert "NO VALIDATED PAIN MATCHED" in block
        assert "must serve at least one of these" not in block

    def test_as_block_anchored_keeps_the_existing_anchor_pains_header(self):
        g = CellGrounding(
            niche="n", audience_segment="Home bakers", segment_profile="",
            pain_evidence="  - Cakes take too long", competitor_mentions="", wallet_norm="",
            frame_type="user_seed", focus_block="idea text", unanchored=False,
        )
        block = g.as_block()
        assert "VALIDATED ANCHOR PAINS (the idea must serve at least one of these)" in block


class TestUserSeedIdentityLock:
    seed = "A fantasy cards collection game for esports fans."

    def test_prompts_make_the_product_immutable_and_the_anchor_an_evaluation_lens(self):
        g = CellGrounding(
            niche="esports", audience_segment="esports fans", segment_profile="",
            pain_evidence="  - Reliable reporting is hard to find", competitor_mentions="",
            frame_type="user_seed", focus_block=self.seed, user_seed_text=self.seed,
        )

        reviewer = _reviewer_system(g)["content"]
        ideator = _ideator_system(g)["content"]

        for prompt in (reviewer, ideator):
            assert "USER-SEED IDENTITY LOCK" in prompt
            assert "must NEVER replace the submitted product" in prompt
            assert self.seed in prompt

    def test_patchzero_is_not_faithful_to_the_fantasy_card_product(self):
        patchzero = SimpleNamespace(
            solution_name="PatchZero",
            short_description=(
                "An investigative tool that mines Wayback Machine snapshots of Valve pages "
                "to expose roster changes before mainstream media reports them."),
        )
        cards = SimpleNamespace(
            solution_name="Esports Fantasy Cards",
            short_description=(
                "Fans collect fantasy player cards and build esports tournament game lineups."),
        )

        assert not is_seed_faithful(self.seed, patchzero)
        assert is_seed_faithful(self.seed, cards)

    def test_refinement_rejects_an_off_seed_improvement(self, monkeypatch):
        start = SimpleNamespace(
            solution_name="Esports Fantasy Cards",
            short_description="Fans collect fantasy esports cards and play a lineup game.",
        )
        drift = SimpleNamespace(
            solution_name="PatchZero",
            short_description="A Wayback Machine monitor for investigative esports reporting.",
        )
        critique = SimpleNamespace(
            market_fit=0.5, binding_constraint="market_fit", directive="pivot",
            meets_bar=False, composite=lambda angle: 0.5,
        )
        grounding = CellGrounding(
            frame_type="user_seed", focus_block=self.seed, user_seed_text=self.seed,
        )
        monkeypatch.setattr(v4, "_idea_to_text", lambda idea: idea.short_description)
        monkeypatch.setattr(v4, "_review", lambda *a, **kw: (critique, None))
        monkeypatch.setattr(v4, "_improve", lambda *a, **kw: (drift, None))
        monkeypatch.setattr(v4, "verify_data_routes", lambda *a, **kw: None)

        result = v4.tournament_refine_cell_v4([start], grounding, rounds=2)

        assert result is start


class TestBuildCellGroundingFromCellSetsUnanchored:
    def test_user_seed_cell_with_no_anchor_titles_is_marked_unanchored(self):
        focus = FrameFocus(frame="user_seed", key="seed-1",
                           payload={"seed_text": "an idea"}, anchor_pain_titles=[])
        cell = {"frame": "user_seed", "focus": focus, "pain": None, "segment": None}
        g = _crew()._build_cell_grounding_from_cell(cell)
        assert g.unanchored is True

    def test_user_seed_cell_with_anchor_titles_is_not_unanchored(self):
        focus = FrameFocus(frame="user_seed", key="seed-2", payload={"seed_text": "an idea"},
                           anchor_pain_titles=["Some validated pain"])
        cell = {"frame": "user_seed", "focus": focus, "pain": None, "segment": None}
        g = _crew()._build_cell_grounding_from_cell(cell)
        assert g.unanchored is False

    def test_gap_frame_cell_is_never_marked_unanchored(self):
        focus = FrameFocus(frame="gap", key="gap:acme", payload={"incumbent_name": "Acme"},
                           anchor_pain_titles=["Some validated pain"])
        cell = {"frame": "gap", "focus": focus, "pain": None, "segment": None}
        g = _crew()._build_cell_grounding_from_cell(cell)
        assert g.unanchored is False


# ---------------------------------------------------------------------------
# _tournament_cell: pain_points_addressed force-empty + unanchored_hypothesis stamp
# ---------------------------------------------------------------------------

class TestTournamentCellUnanchoredStamp:
    def _run(self, monkeypatch, anchor_titles):
        expanded = SimpleNamespace(
            solution_name="X", source_pain=None, source_segment=None,
            mechanism_tag=None, data_source_tag=None, journey_tag=None,
            obviousness_score=None, data_feasibility_score=None, build_feasibility_score=None,
            pain_points_addressed=["A fabricated pain the LLM made up"],
            unanchored_hypothesis=True,  # simulate a fabricated/leftover value from the LLM
        )
        monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept",
                            lambda self, c, p, **kw: expanded)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
        monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)
        import nicheiq.crews.idea_improvement_loop_v4 as v4
        monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])

        focus = FrameFocus(frame="user_seed", key="seed-1", payload={"seed_text": "an idea"},
                           anchor_pain_titles=anchor_titles)
        cell = {"frame": "user_seed", "focus": focus, "pain": None, "segment": None}
        concept = SimpleNamespace(concept_name="c", one_liner="ol", project_type="saas",
                                  target_keywords=[], why_non_obvious="w", source_pain=None,
                                  source_segment=None, obviousness_score=0.3,
                                  data_feasibility_score=0.7, build_feasibility_score=0.8,
                                  data_access_model="public", critic_no_route=False,
                                  mechanism_tag="m", data_source_tag="d", journey_tag="j")
        return _crew()._tournament_cell(cell=cell, candidates=[concept], search=None, usages=[])

    def test_unanchored_seed_force_empties_pain_points_and_marks_the_flag(self, monkeypatch):
        winner = self._run(monkeypatch, anchor_titles=[])
        assert winner.pain_points_addressed == []  # fabrication from the LLM is discarded
        assert winner.unanchored_hypothesis is True
        assert winner.source_pain is None

    def test_anchored_seed_gets_honest_parity_not_the_unanchored_flag(self, monkeypatch):
        winner = self._run(monkeypatch, anchor_titles=["Real validated pain"])
        assert winner.pain_points_addressed == ["Real validated pain"]  # code-filled truth
        assert winner.unanchored_hypothesis is None  # reset-then-stamp: cleared, never left True


# ---------------------------------------------------------------------------
# _run_seed_cell: builds the cell/focus and runs the real per-cell birth path
# ---------------------------------------------------------------------------

class TestRunSeedCell:
    def _stub_birth(self, monkeypatch, winner):
        captured = {}

        def fake_one_sample(self, inputs, idx, lens, model, effort, **kw):
            captured["one_sample_kwargs"] = kw
            return [SimpleNamespace(concept_name="c")], []

        def fake_tournament_cell(self, *, cell, candidates, search, usages, skip_selection=False):
            captured["cell"] = cell
            captured["candidates"] = candidates
            captured["skip_selection"] = skip_selection
            return winner

        monkeypatch.setattr(UnifiedSolutionCrew, "_one_sample", fake_one_sample)
        monkeypatch.setattr(UnifiedSolutionCrew, "_tournament_cell", fake_tournament_cell)
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_data_menu", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_dissatisfaction_block", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_wallet_prompt_line", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_market_reality_block", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_seed_crew_inputs", lambda self: {})
        return captured

    def test_anchored_seed_resolves_and_wires_the_cell(self, monkeypatch):
        pain = _pain("Cakes take too long to price manually",
                     description="home bakers spend hours pricing custom cakes")
        crew = _crew(pain_point_analysis=SimpleNamespace(pain_points=[pain]))
        winner = SimpleNamespace(idea_tier=None)
        captured = self._stub_birth(monkeypatch, winner)

        result = crew._run_seed_cell(
            seed_text="A tool that prices custom cakes for home bakers automatically",
            dispatch_id="dispatch-123", usages=[])

        assert result is winner
        assert result.idea_tier == "single"
        cell = captured["cell"]
        assert cell["frame"] == "user_seed"
        assert cell["pain"] is None
        assert cell["focus"].anchor_pain_titles == ["Cakes take too long to price manually"]
        assert cell["focus"].key == "dispatch-123"
        assert captured["skip_selection"] is True

    def test_unanchored_seed_still_births_with_empty_anchor_titles(self, monkeypatch):
        crew = _crew()
        winner = SimpleNamespace(idea_tier=None)
        captured = self._stub_birth(monkeypatch, winner)

        result = crew._run_seed_cell(
            seed_text="A satellite tracker for amateur astronomers", usages=[])

        assert result is winner
        assert captured["cell"]["focus"].anchor_pain_titles == []
        assert captured["cell"]["segment"] is None

    def test_off_seed_generation_falls_back_to_the_submitted_product(self, monkeypatch):
        crew = _crew()
        winner = SimpleNamespace(idea_tier=None)
        captured = self._stub_birth(monkeypatch, winner)
        seed = "A fantasy cards collection game for esports fans."

        result = crew._run_seed_cell(
            seed_text=seed, dispatch_id="d1", search=None, usages=[])

        assert result is winner
        assert len(captured["candidates"]) == 1
        fallback = captured["candidates"][0]
        assert fallback.one_liner == seed
        assert is_seed_faithful(seed, fallback)

    def test_seed_variant_prompt_filters_before_critic_scoring(self, monkeypatch):
        crew = _crew()
        winner = SimpleNamespace(idea_tier=None)
        captured = self._stub_birth(monkeypatch, winner)
        seed = "A fantasy cards collection game for esports fans."
        off_seed = SimpleNamespace(
            concept_name="PatchZero",
            one_liner="A Wayback Machine reporting tool for esports journalists",
        )
        faithful = SimpleNamespace(
            concept_name="Esports Fantasy Cards",
            one_liner="A fantasy card collection game for esports fans who open packs",
        )

        def fake_one_sample(self, inputs, idx, lens, model, effort, **kw):
            captured["lens"] = lens
            captured["one_sample_kwargs"] = kw
            return [off_seed, faithful], ["generator-usage"]

        scored = []

        def fake_score(self, concepts, idx=None):
            scored.extend(concepts)
            return ["critic-usage"]

        monkeypatch.setattr(UnifiedSolutionCrew, "_one_sample", fake_one_sample)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_concepts", fake_score)
        usages = []

        result = crew._run_seed_cell(seed_text=seed, usages=usages)

        assert result is winner
        assert captured["candidates"] == [faithful]
        assert scored == [faithful]
        assert usages == ["generator-usage", "critic-usage"]
        assert captured["one_sample_kwargs"]["score_inline"] is False
        assert captured["one_sample_kwargs"]["concept_count"] == "4"
        assert "SAME PRODUCT, DIFFERENT EXECUTION" in captured["lens"]
        assert "VARIANTS OF THE SAME PRODUCT" in captured["one_sample_kwargs"]["partitioned_block"]

    def test_zero_concepts_also_falls_back_to_the_submitted_product(self, monkeypatch):
        crew = _crew()
        winner = SimpleNamespace(idea_tier=None)
        captured = self._stub_birth(monkeypatch, winner)
        monkeypatch.setattr(UnifiedSolutionCrew, "_one_sample",
                            lambda self, *a, **kw: ([], []))
        seed = "A fantasy cards collection game for esports fans."

        result = crew._run_seed_cell(seed_text=seed, usages=[])

        assert result is winner
        assert captured["candidates"][0].one_liner == seed

    def test_cell_failure_is_fail_soft(self, monkeypatch):
        crew = _crew()

        def boom(self, *a, **kw):
            raise RuntimeError("resolver blew up")

        monkeypatch.setattr("nicheiq.utils.seed_resolver.resolve_seed_anchors", boom)
        monkeypatch.setattr(UnifiedSolutionCrew, "_one_sample",
                            lambda self, *a, **kw: ([SimpleNamespace(concept_name="c")], []))
        monkeypatch.setattr(UnifiedSolutionCrew, "_tournament_cell",
                            lambda self, **kw: SimpleNamespace(idea_tier=None))
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_data_menu", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_dissatisfaction_block", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_wallet_prompt_line", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_market_reality_block", lambda self: "")
        monkeypatch.setattr(UnifiedSolutionCrew, "_build_seed_crew_inputs", lambda self: {})

        # resolve_seed_anchors raising is caught INSIDE _run_seed_cell (treated as unanchored) —
        # the cell must still birth successfully, never propagate the exception.
        result = crew._run_seed_cell(seed_text="anything", usages=[])
        assert result is not None


# ---------------------------------------------------------------------------
# execute_seed_pipeline: orchestration — reset, birth, wave, tail, no backfill, no save
# ---------------------------------------------------------------------------

class TestExecuteSeedPipeline:
    def test_returns_exactly_one_idea_and_runs_wave_then_tail(self, monkeypatch):
        crew = _crew()
        idea = SimpleNamespace(solution_name="Seed Idea")
        calls = []

        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: idea)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave",
                            lambda self, wave, **kw: calls.append(("score_wave", wave, kw)))
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail",
                            lambda self, wave: calls.append(("finalize_seed_tail", wave)))
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)
        # Sentinel: if execute_seed_pipeline ever called portfolio maintenance, this would fire.
        monkeypatch.setattr(UnifiedSolutionCrew, "_backfill_and_demote",
                            lambda self, *a, **kw: calls.append(("backfill_and_demote",)))

        result = crew.execute_seed_pipeline(
            SeedRequest(seed_text="an idea", dispatch_id="d1"))

        assert result is idea
        assert ("score_wave", [idea], {"birth_verified": [idea]}) in calls
        assert ("finalize_seed_tail", [idea]) in calls
        assert not any(c[0] == "backfill_and_demote" for c in calls)  # NEVER portfolio maintenance

    def test_resets_per_op_state_and_sets_tournament_ctx(self, monkeypatch):
        crew = _crew(ruled_out_pains=["stale"], overlap_groups=["stale"],
                     funnel_counts={"stale": 1}, _tournament_ctx={"stale": True})
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: SimpleNamespace(short_description="an idea"))
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        crew.execute_seed_pipeline(SeedRequest(seed_text="an idea"))

        assert crew.ruled_out_pains == []
        assert crew.overlap_groups == []
        assert crew.funnel_counts == {}
        assert crew._tournament_ctx is not None and "stale" not in crew._tournament_ctx

    def test_does_not_touch_checkpoint_mgr(self, monkeypatch):
        checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("execute_seed_pipeline must never save a checkpoint")))
        crew = _crew(checkpoint_mgr=checkpoint_mgr)
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: SimpleNamespace(short_description="an idea"))
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        crew.execute_seed_pipeline(SeedRequest(seed_text="an idea"))  # must not raise

    def test_refuses_a_replacement_introduced_during_scoring(self, monkeypatch):
        seed = "A fantasy cards collection game for esports fans."
        idea = SimpleNamespace(
            solution_name="Esports Fantasy Cards",
            short_description="Fans collect fantasy esports cards and play a lineup game.",
        )
        tail_called = []
        crew = _crew()
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: idea)
        monkeypatch.setattr(
            UnifiedSolutionCrew, "_score_wave",
            lambda self, wave, **kw: (
                setattr(wave[0], "solution_name", "PatchZero"),
                setattr(wave[0], "short_description",
                        "A Wayback Machine monitor for investigative esports reporting."),
            ))
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail",
                            lambda self, wave: tail_called.append(True))
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        assert crew.execute_seed_pipeline(SeedRequest(seed_text=seed)) is None
        assert tail_called == []

    def test_birth_failure_returns_none_without_running_wave_or_tail(self, monkeypatch):
        crew = _crew()
        calls = []
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave",
                            lambda self, wave, **kw: calls.append("score_wave"))
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail",
                            lambda self, wave: calls.append("finalize_seed_tail"))
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        result = crew.execute_seed_pipeline(SeedRequest(seed_text="an idea"))
        assert result is None
        assert calls == []


# ---------------------------------------------------------------------------
# _record_ruled_out: source_frame + dispatch id provenance (eager-meandering-feather.md
# Phase 6 — the frontend badges a demoted seed "Your idea" off these two fields).
# ---------------------------------------------------------------------------

class TestRuledOutSeedProvenance:
    def test_execute_seed_pipeline_stamps_current_seed_dispatch_id(self, monkeypatch):
        crew = _crew()
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: SimpleNamespace(short_description="an idea"))
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        crew.execute_seed_pipeline(SeedRequest(seed_text="an idea", dispatch_id="dispatch-42"))

        assert crew._current_seed_dispatch_id == "dispatch-42"

    def test_demoted_seed_ruled_out_finding_carries_source_frame_and_dispatch_id(self):
        crew = _crew(ruled_out_pains=[], _current_seed_dispatch_id="dispatch-42")
        idea = SimpleNamespace(
            solution_name="Seed Idea", source_frame="user_seed",
            market_fit_score=0.2, source_pain=None, pain_points_addressed=[],
            idea_tier="single", unanchored_hypothesis=True,
            model_dump=lambda *, mode: {
                "solution_name": "Seed Idea",
                "description": "Evaluated submitted product",
                "value_proposition": "Tests the user's thesis",
            },
        )

        crew._record_ruled_out(idea, source="demoted_winner")

        finding = crew.ruled_out_pains[0]
        assert finding["source_frame"] == "user_seed"
        assert finding["dispatch_id"] == "dispatch-42"
        assert finding["pain_title"] == "No validated pain match"
        assert finding["idea"]["solution_name"] == "Seed Idea"

    def test_non_seed_ruled_out_finding_has_no_dispatch_id(self):
        # A demoted POOL idea (never inside a seed request) must never inherit a stale seed
        # dispatch id from a crew instance that happens to still carry one from an earlier op.
        crew = _crew(ruled_out_pains=[])
        idea = SimpleNamespace(
            solution_name="Pool Idea", source_frame="pain",
            market_fit_score=0.2, source_pain=None, pain_points_addressed=[],
            idea_tier="single",
        )

        crew._record_ruled_out(idea, source="demoted_winner")

        finding = crew.ruled_out_pains[0]
        assert finding["source_frame"] == "pain"
        assert finding["dispatch_id"] is None

    def test_accepts_a_plain_dict_seed(self, monkeypatch):
        crew = _crew()
        idea = SimpleNamespace(short_description="an idea")
        captured = {}
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell",
                            lambda self, **kw: captured.update(kw) or idea)
        monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **kw: None)
        monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)
        monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                            lambda self, u: None, raising=False)

        result = crew.execute_seed_pipeline(
            {"seed_text": "an idea", "pain_ref": "p", "tool_ref": "t", "dispatch_id": "d9"})
        assert result is idea
        assert captured["seed_text"] == "an idea"
        assert captured["pain_ref"] == "p"
        assert captured["tool_ref"] == "t"
        assert captured["dispatch_id"] == "d9"


# ---------------------------------------------------------------------------
# hydrate_from_state: restores caches from persisted state, no cold re-probe
# ---------------------------------------------------------------------------

class TestHydrateFromState:
    def test_restores_all_five_caches_from_state(self):
        crew = _crew(_incumbent_rows=None, _niche_wallet_brief=None, _data_menu_text=None,
                     _dissatisfaction_text=None, _payability_map=None)
        seg = SimpleNamespace(segment_name="Home bakers", payability_score=0.7,
                              payability_class="prosumer-wallet", payability_rationale="pays for tools")
        crew.audience_mapping = SimpleNamespace(audience_segments=[seg])
        state = SimpleNamespace(
            niche_incumbent_map=[{"name": "Acme", "pricing": "$10/mo", "focus": "f", "gap": "g"}],
            niche_wallet_brief={"wallet_class": "mixed"},
            niche_data_menu_text="- some verified route",
            niche_dissatisfaction_text="Acme — \"too expensive\" (reddit)",
        )

        crew.hydrate_from_state(state)

        assert crew._incumbent_rows == state.niche_incumbent_map
        assert crew._niche_wallet_brief == {"wallet_class": "mixed"}
        assert crew._data_menu_text == "- some verified route"
        assert crew._dissatisfaction_text == 'Acme — "too expensive" (reddit)'
        assert crew._payability_map["home bakers"].payability_score == 0.7
        assert crew._payability_map["home bakers"].payability_class == "prosumer-wallet"

    def test_hydration_prevents_cold_reprobe(self, monkeypatch):
        # If any of these methods tried to cold-probe after hydration, they would call
        # LLMService.invoke_structured — make that raise so a re-probe fails the test loudly.
        from nicheiq.utils import llm_service

        def boom(*a, **kw):
            raise AssertionError("cold re-probe: LLMService.invoke_structured must not be called")

        monkeypatch.setattr(llm_service.LLMService, "invoke_structured", boom)

        crew = _crew(_incumbent_rows=None, _niche_wallet_brief=None, _data_menu_text=None,
                     _dissatisfaction_text=None, _payability_map=None, search_tool=None)
        state = SimpleNamespace(
            niche_incumbent_map=[{"name": "Acme", "pricing": "$10/mo", "focus": "f", "gap": "g"}],
            niche_wallet_brief={"wallet_class": "mixed", "free_density": ""},
            niche_data_menu_text="- some verified route",
            niche_dissatisfaction_text="",
        )
        crew.hydrate_from_state(state)

        assert crew._build_data_menu() == "- some verified route"
        assert crew._build_dissatisfaction_block() == ""
        assert crew._probe_niche_wallet() == {"wallet_class": "mixed", "free_density": ""}

    def test_never_clobbers_a_value_this_process_already_probed(self):
        crew = _crew(_data_menu_text="already probed this run", _dissatisfaction_text=None,
                     _incumbent_rows=None, _niche_wallet_brief={}, _payability_map=None)
        state = SimpleNamespace(
            niche_incumbent_map=[], niche_wallet_brief={},
            niche_data_menu_text="stale persisted value", niche_dissatisfaction_text=None,
        )
        crew.hydrate_from_state(state)
        assert crew._data_menu_text == "already probed this run"  # not clobbered

    def test_skips_segments_never_stage4_scored(self):
        # No segment has a real score -> Stage-7 payability scoring never actually ran for this
        # job, so there is no paid work to protect. Leave `_payability_map` unset (None) rather
        # than stamping a lying `{}` ("checked, nobody's payable") — a later hydrated crew that
        # genuinely needs payability should still be free to run the real probe.
        crew = _crew(_payability_map=None, _niche_wallet_brief=None)
        unscored = SimpleNamespace(segment_name="Unscored", payability_score=None,
                                   payability_class=None, payability_rationale=None)
        crew.audience_mapping = SimpleNamespace(audience_segments=[unscored])
        state = SimpleNamespace(niche_incumbent_map=[], niche_wallet_brief={},
                                niche_data_menu_text=None, niche_dissatisfaction_text=None)
        crew.hydrate_from_state(state)
        assert crew._payability_map is None
