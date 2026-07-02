"""Post-union overlap note (codex-review fix 2026-07-02) — LLM semantic grouping, note-only.
Deterministic detectors measured DEAD on the motivating pool (max embedding cosine 0.572,
zero >=2-tag matches) — see _note_idea_overlap docstring."""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _idea(name, vp="does a thing"):
    return SimpleNamespace(solution_name=name, value_proposition=vp)


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.coverage_caveats = []
    return crew


class TestOverlapNote:
    def test_group_becomes_caveat(self):
        crew = _crew()
        fake = SimpleNamespace(groups=[SimpleNamespace(
            idea_names=["vllmConfigTracer", "inferenceEngineMatchmaker"],
            shared_product="vLLM configuration assistant")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._note_idea_overlap([_idea("vllmConfigTracer"),
                                     _idea("inferenceEngineMatchmaker"), _idea("Other")])
        assert len(crew.coverage_caveats) == 1
        assert "vLLM configuration assistant" in crew.coverage_caveats[0]
        assert "vllmConfigTracer" in crew.coverage_caveats[0]

    def test_hallucinated_names_filtered_and_singletons_ignored(self):
        crew = _crew()
        fake = SimpleNamespace(groups=[SimpleNamespace(
            idea_names=["NotARealIdea", "vllmConfigTracer"], shared_product="x")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            crew._note_idea_overlap([_idea("vllmConfigTracer"), _idea("A"), _idea("B")])
        assert crew.coverage_caveats == []   # only 1 valid member -> no group

    def test_small_pool_skips_llm(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured") as m:
            crew._note_idea_overlap([_idea("A"), _idea("B")])
        assert m.call_count == 0 and crew.coverage_caveats == []

    def test_fail_soft(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            crew._note_idea_overlap([_idea("A"), _idea("B"), _idea("C")])
        assert crew.coverage_caveats == []
