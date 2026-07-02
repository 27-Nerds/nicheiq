"""Mechanism-parity probe (A/B-validated, always on) — web-verify whether incumbents already
SHIP the top ideas' core mechanisms, then re-score with the evidence in critic context."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _idea(name, mf, vp="route optimization for mobile groomers", mech="route-optimizer"):
    return SimpleNamespace(
        solution_name=name, market_fit_score=mf, technical_feasibility_score=mf,
        novelty_score=mf, seo_scalability_score=mf, value_proposition=vp,
        technical_approach="deterministic routing engine", mechanism_tag=mech,
        incumbent_parity=None)


def _crew(with_search=True):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="mobile dog groomers")
    crew.search_tool = (SimpleNamespace(run=lambda search_query: "MoeGo Smart Schedule route optimization")
                        if with_search else None)
    crew.cost_tracker = None
    crew._incumbent_probe_text = "### Web-probed incumbent products..."   # cached
    crew._incumbent_rows = [{"name": "MoeGo", "pricing": "$50/mo",
                             "focus": "grooming scheduling and route optimization", "gap": ""}]
    crew._recalibrated = []
    crew._calibrate_batch = lambda **kw: crew._recalibrated.append(kw) or (len(kw["batch"]), None)
    return crew


def _finding(idea_name, parity="shipped", covered_by="MoeGo",
             evidence="Smart Schedule route optimization"):
    return SimpleNamespace(idea_name=idea_name, covered_by=covered_by,
                           evidence=evidence, parity=parity)


class TestParityProbe:
    # probe is unconditional since the 2026-07-02 A/B (flag removed; groomers mean
    # panel-distance 0.083 -> 0.047); only the top-K tunable remains

    def test_top_k_probed_and_rescored_with_evidence(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_probe_top_k", 2)
        crew = _crew()
        ideas = [_idea("Top1", 0.75), _idea("Top2", 0.70), _idea("Low", 0.30)]
        fake = SimpleNamespace(findings=[_finding("Top1"), _finding("Top2", parity="none", covered_by="")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity(ideas)
        assert ideas[0].incumbent_parity == "shipped by MoeGo: Smart Schedule route optimization"
        assert ideas[1].incumbent_parity == "none found"
        assert ideas[2].incumbent_parity is None          # below top-K, untouched
        assert len(crew._recalibrated) == 1
        kw = crew._recalibrated[0]
        assert [i.solution_name for i in kw["batch"]] == ["Top1", "Top2"]
        assert "MECHANISM PARITY CHECK" in kw["extra_context"]
        assert "shipped by MoeGo" in kw["extra_context"]

    def test_fail_soft_no_search_tool(self, monkeypatch):
        crew = _crew(with_search=False)
        ideas = [_idea("A", 0.7)]
        crew._probe_mechanism_parity(ideas)
        assert ideas[0].incumbent_parity is None and crew._recalibrated == []

    def test_fail_soft_llm_error(self, monkeypatch):
        crew = _crew()
        ideas = [_idea("A", 0.7)]
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            crew._probe_mechanism_parity(ideas)   # must not raise
        assert ideas[0].incumbent_parity is None and crew._recalibrated == []

    def test_incumbent_overlap_drives_query(self, monkeypatch):
        monkeypatch.setattr(settings, "parity_probe_top_k", 1)
        crew = _crew()
        queries = []
        crew.search_tool = SimpleNamespace(
            run=lambda search_query: queries.append(search_query) or "results")
        fake = SimpleNamespace(findings=[])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._probe_mechanism_parity([_idea("A", 0.7)])
        # idea text overlaps MoeGo's focus ("route", "optimization", "grooming") → quoted-name query
        assert any('"MoeGo"' in q for q in queries)


class TestExtraContextByteIdentity:
    def test_default_prompt_unchanged(self):
        # extra_context='' must not alter the calibration prompt (regression anchor)
        import inspect
        src = inspect.getsource(UnifiedSolutionCrew._calibrate_batch)
        assert 'extra_context: str = ""' in src
        assert 'if extra_context else ""' in src


def test_mechanism_keywords():
    kw = UnifiedSolutionCrew._mechanism_keywords(SimpleNamespace(
        mechanism_tag="route-optimizer",
        value_proposition="Plan the most efficient daily route for your grooming van"))
    assert "route" in kw and "optimizer" in kw
    assert "the" not in kw.split() and "for" not in kw.split()
