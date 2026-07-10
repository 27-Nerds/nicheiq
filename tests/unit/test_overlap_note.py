"""Post-union variant-overlap grouping — LLM semantic grouping returning structured groups.
Deterministic detectors measured DEAD on the motivating pool (max embedding cosine 0.572,
zero >=2-tag matches) — see _group_variant_overlaps docstring. (Upgraded 2026-07-09 from the
caveat-string-only _note_idea_overlap: groups now drive the variant MERGE + grouped display.)"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _idea(name, vp="does a thing"):
    return SimpleNamespace(solution_name=name, value_proposition=vp)


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.coverage_caveats = []
    crew.overlap_groups = []
    return crew


class TestVariantOverlapGroups:
    def test_group_returned_and_stored(self):
        crew = _crew()
        fake = SimpleNamespace(groups=[SimpleNamespace(
            idea_names=["vllmConfigTracer", "inferenceEngineMatchmaker"],
            shared_product="vLLM configuration assistant")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            groups = crew._group_variant_overlaps(
                [_idea("vllmConfigTracer"), _idea("inferenceEngineMatchmaker"), _idea("Other")])
        assert groups == crew.overlap_groups
        assert len(groups) == 1
        assert groups[0]["shared_product"] == "vLLM configuration assistant"
        assert set(groups[0]["idea_names"]) == {"vllmConfigTracer", "inferenceEngineMatchmaker"}
        # No caveat string anymore — groups are structured output.
        assert crew.coverage_caveats == []

    def test_hallucinated_names_filtered_and_singletons_ignored(self):
        crew = _crew()
        fake = SimpleNamespace(groups=[SimpleNamespace(
            idea_names=["NotARealIdea", "vllmConfigTracer"], shared_product="x")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            groups = crew._group_variant_overlaps([_idea("vllmConfigTracer"), _idea("A"), _idea("B")])
        assert groups == [] and crew.overlap_groups == []   # only 1 valid member -> no group

    def test_small_pool_skips_llm(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured") as m:
            groups = crew._group_variant_overlaps([_idea("A"), _idea("B")])
        assert m.call_count == 0 and groups == []

    def test_fail_soft(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            groups = crew._group_variant_overlaps([_idea("A"), _idea("B"), _idea("C")])
        assert groups == []
