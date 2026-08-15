"""Hermetic tests for the per-cell tournament architecture (enable_per_cell_tournament).

Covers the two pure helpers (_group_pool_by_cell, _build_cell_grounding_from_cell) and the per-cell
unit (_tournament_cell). LLM (_refine_single_concept, tournament_refine_cell_v4) is mocked.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.utils.frames import FrameFocus


def _crew():
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c.niche_context = SimpleNamespace(niche_description="A test niche")
    c.audience_mapping = None
    c.competitor_mentions_text = "Competitor A, Competitor B"
    c.search_tool = None
    return c


def _pain(title, sev=0.6):
    return SimpleNamespace(
        title=title, description=f"desc for {title}",
        representative_quotes=[f"quote about {title}"],
        opportunity_level=SimpleNamespace(value="medium"), severity_score=sev,
    )


def _seg(name):
    return SimpleNamespace(segment_name=name, motivation_drivers=["save money"],
                           expertise_level="Beginner", budget_sensitivity="High")


def _concept(name, obv=0.5, blocked=False, no_route=False, mech="lookup"):
    return SimpleNamespace(
        concept_name=name, one_liner="ol", project_type="aggregator", target_keywords=[],
        why_non_obvious="why", source_pain=None, source_segment=None,
        obviousness_score=obv, data_feasibility_score=0.7, build_feasibility_score=0.8,
        data_access_model="blocked" if blocked else "public", critic_no_route=no_route,
        mechanism_tag=mech, data_source_tag="ds", journey_tag="jt",
    )


# --- _group_pool_by_cell ---------------------------------------------------

def test_group_pool_by_cell():
    pa, pb = _pain("Desk load cell"), _pain("Wheelbase flex")
    sa = _seg("Budget")
    cells = [{"pain": pa, "segment": sa}, {"pain": pb, "segment": sa}]
    pool = [
        SimpleNamespace(source_pain="Desk load cell", source_segment="Budget", concept_name="A"),
        SimpleNamespace(source_pain="Desk load cell", source_segment="Budget", concept_name="B"),
        SimpleNamespace(source_pain="Wheelbase flex", source_segment="Budget", concept_name="C"),
    ]
    groups = UnifiedSolutionCrew._group_pool_by_cell(pool, cells)
    assert [(c["pain"].title, [x.concept_name for x in cs]) for c, cs in groups] == [
        ("Desk load cell", ["A", "B"]), ("Wheelbase flex", ["C"])]


def test_group_pool_by_cell_skips_empty_cells():
    pa = _pain("Has concepts"); pb = _pain("No concepts")
    cells = [{"pain": pa, "segment": None}, {"pain": pb, "segment": None}]
    pool = [SimpleNamespace(source_pain="Has concepts", source_segment=None, concept_name="A")]
    groups = UnifiedSolutionCrew._group_pool_by_cell(pool, cells)
    assert len(groups) == 1 and groups[0][0]["pain"].title == "Has concepts"


# --- _build_cell_grounding_from_cell --------------------------------------

def test_build_cell_grounding_from_cell():
    cell = {"pain": _pain("Desk load cell"), "segment": _seg("Budget")}
    g = _crew()._build_cell_grounding_from_cell(cell)
    assert g.pain_title == "Desk load cell"
    assert "quote about Desk load cell" in g.pain_evidence
    assert g.audience_segment == "Budget"
    assert "save money" in g.segment_profile
    assert "Competitor A" in g.competitor_mentions


# --- _tournament_cell ------------------------------------------------------

def test_tournament_cell_picks_lowest_obviousness_and_stamps_provenance(monkeypatch):
    expanded = SimpleNamespace(solution_name="Expanded", source_pain=None, source_segment=None,
                               mechanism_tag=None, data_source_tag=None, journey_tag=None,
                               obviousness_score=None, data_feasibility_score=None,
                               build_feasibility_score=None)
    captured = {}

    def fake_refine(self, concept, pain):
        captured["seed"] = concept
        return expanded

    def fake_tournament(cands, grounding, **kw):
        # the loop renames the idea mid-flight (the reason name-join breaks)
        cands[0].solution_name = "Renamed By Loop"
        return cands[0]

    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", fake_refine)
    monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    # Fix #3b: the winner's source_segment is now RE-DERIVED from the pain (honest affinity), not
    # the raw load-balanced cell segment. Stub the re-derivation to a known value for this stamp test.
    monkeypatch.setattr(UnifiedSolutionCrew, "_provenance_segment_for_pain",
                        lambda self, p: "Budget-rederived", raising=False)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", fake_tournament)

    cell = {"pain": _pain("Desk load cell"), "segment": _seg("Budget")}
    candidates = [_concept("novel", obv=0.2, mech="calc"), _concept("obvious", obv=0.8)]
    winner = _crew()._tournament_cell(cell=cell, candidates=candidates, search=None, usages=[])

    assert captured["seed"].concept_name == "novel"          # lowest obviousness seeded
    assert winner.solution_name == "Renamed By Loop"
    assert winner.source_pain == "Desk load cell"            # stamped from cell, not name-join
    assert winner.source_segment == "Budget-rederived"       # Fix #3b: re-derived from pain, not raw cell
    assert winner.mechanism_tag == "calc"                    # carried from seed concept
    assert winner.obviousness_score == 0.2                   # critic value carried


def test_user_seed_tournament_prioritizes_fidelity_over_novelty(monkeypatch):
    expanded = SimpleNamespace(
        solution_name="Esports Fantasy Cards",
        source_pain=None,
        source_segment=None,
        mechanism_tag=None,
        data_source_tag=None,
        journey_tag=None,
        obviousness_score=None,
        data_feasibility_score=None,
        build_feasibility_score=None,
        pain_points_addressed=[],
    )
    captured = {}

    def fake_refine(self, concept, pain, **kwargs):
        captured["seed"] = concept
        return expanded

    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", fake_refine)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_stamp_payability", lambda self, i: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    # S23: a `user_seed` cell with more than one concept now asks the BIRTH JUDGE whether the
    # highest-fidelity concept's refinement is still the submitted product, and only walks on if
    # it says no. Accepting here keeps this test measuring exactly what its name says — that
    # FIDELITY, not novelty, decides which concept the cell reaches for FIRST. Without the stub
    # the call went live: the `_no_live_http` guard turned it into a TEARDOWN error while the
    # assertions still passed, because `_expand_seed_until_judged` fails soft to the
    # highest-fidelity expansion. That is trap 3's shape, and the guard is what caught it.
    monkeypatch.setattr(UnifiedSolutionCrew, "_semantic_seed_identity_matches",
                        lambda self, seed, candidate, evidence=None: True)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])

    seed = "A fantasy cards collection game for esports fans."
    focus = FrameFocus(
        frame="user_seed",
        key="submitted-idea",
        payload={"seed_text": seed},
        anchor_pain_titles=[],
    )
    off_seed = _concept("PatchZero", obv=0.1)
    off_seed.one_liner = "A Wayback Machine wrapper for esports reporting"
    faithful = _concept("Esports Fantasy Cards", obv=0.8)
    faithful.one_liner = "A collectible fantasy card game for esports fans"

    winner = _crew()._tournament_cell(
        cell={"frame": "user_seed", "focus": focus, "pain": None, "segment": None},
        candidates=[off_seed, faithful],
        search=None,
        usages=[],
    )

    assert winner is expanded
    assert captured["seed"] is faithful


def test_tournament_cell_drops_blocked_with_floor(monkeypatch):
    seeds = []
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept",
                        lambda self, c, p: seeds.append(c) or SimpleNamespace(
                            solution_name="X", source_pain=None, source_segment=None,
                            mechanism_tag=None, data_source_tag=None, journey_tag=None,
                            obviousness_score=None, data_feasibility_score=None, build_feasibility_score=None))
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])

    cell = {"pain": _pain("P"), "segment": None}
    # one blocked (better obviousness) + one usable -> usable wins
    cands = [_concept("blocked-better", obv=0.1, blocked=True), _concept("usable", obv=0.6)]
    _crew()._tournament_cell(cell=cell, candidates=cands, search=None, usages=[])
    assert seeds[-1].concept_name == "usable"


def test_tournament_cell_fail_soft_returns_none(monkeypatch):
    def boom(self, c, p):
        raise RuntimeError("expand failed")
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", boom)
    cell = {"pain": _pain("P"), "segment": None}
    out = _crew()._tournament_cell(cell=cell, candidates=[_concept("a")], search=None, usages=[])
    assert out is None


def test_tournament_cell_backfills_project_type_from_candidate(monkeypatch):
    # The refiner often drops project_type (RawConcept has it, the refined idea doesn't) — the cell
    # must backfill it from the seed concept so the idea/UI/angle keep the type signal.
    refined = SimpleNamespace(solution_name="X", source_pain=None, source_segment=None,
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              project_type=None,  # refiner dropped it
                              obviousness_score=None, data_feasibility_score=None,
                              build_feasibility_score=None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", lambda self, c, p: refined)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])
    cell = {"pain": _pain("P"), "segment": _seg("Budget")}
    cand = _concept("c", obv=0.3)  # _concept defaults project_type="aggregator"
    winner = _crew()._tournament_cell(cell=cell, candidates=[cand], search=None, usages=[])
    assert winner.project_type == "aggregator"  # carried from the candidate, not left None


def test_tournament_cell_keeps_refiner_project_type(monkeypatch):
    # If the refiner DID set a project_type, the backfill must not overwrite it.
    refined = SimpleNamespace(solution_name="X", source_pain=None, source_segment=None,
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              project_type="saas",
                              obviousness_score=None, data_feasibility_score=None,
                              build_feasibility_score=None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", lambda self, c, p: refined)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])
    cell = {"pain": _pain("P"), "segment": None}
    winner = _crew()._tournament_cell(cell=cell, candidates=[_concept("c", obv=0.3)], search=None, usages=[])
    assert winner.project_type == "saas"  # refiner value preserved


def test_tournament_cell_repairs_winner_before_scoring(monkeypatch):
    # The blank-field repair must run on the loop winner, BEFORE the scorer chain — so the
    # critic / angle classifier / weak-text cap see the repaired text.
    refined = SimpleNamespace(solution_name="X", source_pain=None, source_segment=None,
                              mechanism_tag=None, data_source_tag=None, journey_tag=None,
                              obviousness_score=None, data_feasibility_score=None,
                              build_feasibility_score=None)
    order = []
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", lambda self, c, p: refined)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields",
                        lambda self, i: order.append(("repair", i)))
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner",
                        lambda self, w, **kw: order.append(("score", w)) or w)
    monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])
    cell = {"pain": _pain("P"), "segment": None}
    _crew()._tournament_cell(cell=cell, candidates=[_concept("c", obv=0.3)], search=None, usages=[])
    assert [step for step, _ in order] == ["repair", "score"]
    assert order[0][1] is refined  # repair received the loop winner


# --- focus-aware winner-pick (Stage 4) -------------------------------------

def _pick_seed(monkeypatch, candidates, *, focus="auto"):
    """Run _tournament_cell with downstream mocked; return the SEED concept the winner-pick chose."""
    captured = {}

    def fake_refine(self, concept, pain):
        captured["seed"] = concept
        return SimpleNamespace(solution_name="X", source_pain=None, source_segment=None,
                               mechanism_tag=None, data_source_tag=None, journey_tag=None,
                               obviousness_score=None, data_feasibility_score=None,
                               build_feasibility_score=None)

    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept", fake_refine)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: w)
    monkeypatch.setattr(UnifiedSolutionCrew, "_repair_blank_idea_fields", lambda self, i: None)
    monkeypatch.setattr(usc.UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", lambda cands, g, **kw: cands[0])
    c = _crew()
    c.idea_focus = focus
    cell = {"pain": _pain("P"), "segment": _seg("Budget")}
    c._tournament_cell(cell=cell, candidates=candidates, search=None, usages=[])
    return captured["seed"]


def _typed(name, obv, project_type):
    c = _concept(name, obv=obv)
    c.project_type = project_type
    return c


def test_winner_pick_auto_is_pure_obviousness(monkeypatch):
    # focus=auto -> lowest obviousness wins regardless of project_type (regression-lock behaviour).
    cands = [_typed("novel-saas", 0.20, "saas"), _typed("dir", 0.50, "directory")]
    assert _pick_seed(monkeypatch, cands, focus="auto").concept_name == "novel-saas"


def test_winner_pick_distribution_prefers_directory_in_band(monkeypatch):
    # focus=distribution -> within the obviousness band, the directory beats the (slightly more novel) saas.
    cands = [_typed("novel-saas", 0.20, "saas"), _typed("dir", 0.25, "directory")]
    assert _pick_seed(monkeypatch, cands, focus="distribution").concept_name == "dir"


def test_winner_pick_focus_respects_quality_floor(monkeypatch):
    # the directory is FAR outside the obviousness band (0.6 vs 0.2) -> focus must NOT override the gap.
    cands = [_typed("novel-saas", 0.20, "saas"), _typed("dir", 0.60, "directory")]
    assert _pick_seed(monkeypatch, cands, focus="distribution").concept_name == "novel-saas"


def test_focus_matches_type_helper():
    assert usc._focus_matches_type("distribution", "directory")
    assert usc._focus_matches_type("distribution", "aggregator")
    assert not usc._focus_matches_type("distribution", "saas")
    assert usc._focus_matches_type("novelty", "saas")
    assert usc._focus_matches_type("novelty", "marketplace")
    assert not usc._focus_matches_type("novelty", "directory")
    assert not usc._focus_matches_type("auto", "directory")  # auto never biases
    assert not usc._focus_matches_type("distribution", None)
