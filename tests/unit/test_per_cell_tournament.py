"""Hermetic tests for the per-cell tournament architecture (enable_per_cell_tournament).

Covers the two pure helpers (_group_pool_by_cell, _build_cell_grounding_from_cell) and the per-cell
unit (_tournament_cell). LLM (_refine_single_concept, tournament_refine_cell_v4) is mocked.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


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
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: None)
    import nicheiq.crews.idea_improvement_loop_v4 as v4
    monkeypatch.setattr(v4, "tournament_refine_cell_v4", fake_tournament)

    cell = {"pain": _pain("Desk load cell"), "segment": _seg("Budget")}
    candidates = [_concept("novel", obv=0.2, mech="calc"), _concept("obvious", obv=0.8)]
    winner = _crew()._tournament_cell(cell=cell, candidates=candidates, search=None, usages=[])

    assert captured["seed"].concept_name == "novel"          # lowest obviousness seeded
    assert winner.solution_name == "Renamed By Loop"
    assert winner.source_pain == "Desk load cell"            # stamped from cell, not name-join
    assert winner.source_segment == "Budget"
    assert winner.mechanism_tag == "calc"                    # carried from seed concept
    assert winner.obviousness_score == 0.2                   # critic value carried


def test_tournament_cell_drops_blocked_with_floor(monkeypatch):
    seeds = []
    monkeypatch.setattr(UnifiedSolutionCrew, "_refine_single_concept",
                        lambda self, c, p: seeds.append(c) or SimpleNamespace(
                            solution_name="X", source_pain=None, source_segment=None,
                            mechanism_tag=None, data_source_tag=None, journey_tag=None,
                            obviousness_score=None, data_feasibility_score=None, build_feasibility_score=None))
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_cell_winner", lambda self, w, **kw: None)
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
