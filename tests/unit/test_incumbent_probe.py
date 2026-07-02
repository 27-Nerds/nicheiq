"""Portfolio funnel F4 — incumbent probe (A/B-validated, always on)."""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew(with_search=True):
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="cottage food bakers")
    crew.competitor_mentions_text = "### Competitor & Tool Mentions\n- Canva (3 mentions)"
    crew.social_content = None
    crew.audience_mapping = None
    if with_search:
        crew.search_tool = SimpleNamespace(run=lambda search_query: "CakeBoss $15/mo bakery software")
    else:
        crew.search_tool = None
    return crew


def _fake_incumbents():
    return SimpleNamespace(incumbents=[
        SimpleNamespace(name="CakeBoss", pricing="$15-49/mo", focus="order mgmt + costing",
                        gap="no compliance axis")])


class TestIncumbentProbe:
    def test_appended_to_mentions(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(_fake_incumbents(), None)):
            out = crew._format_competitor_mentions()
        assert "Canva" in out                      # community block kept
        assert "CakeBoss ($15-49/mo)" in out       # probe appended
        assert "design the WEDGE" in out

    def test_cached_single_probe(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(_fake_incumbents(), None)) as m:
            crew._format_competitor_mentions()
            crew._format_competitor_mentions()
        assert m.call_count == 1

    def test_fail_soft_no_search_tool(self):
        out = _crew(with_search=False)._format_competitor_mentions()
        assert "Canva" in out and "WEDGE" not in out  # degraded to community block

    def test_fail_soft_llm_error(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            out = crew._format_competitor_mentions()
        assert "Canva" in out and "WEDGE" not in out

