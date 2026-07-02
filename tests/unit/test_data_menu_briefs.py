"""Portfolio funnel F2 — verified data-route menu (A/B-validated, always on)."""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _build_partitioned_block


class TestPartitionedBlockRendering:
    def test_empty_menu_is_byte_identical_legacy(self):
        base = _build_partitioned_block("PAIN", "persona", 3, False)
        with_kw = _build_partitioned_block("PAIN", "persona", 3, False, data_menu="")
        assert base == with_kw
        assert "VERIFIED DATA ROUTES" not in base

    def test_menu_section_rendered_before_pain(self):
        b = _build_partitioned_block("THE-PAIN", "persona", 3, False,
                                     data_menu="- state agency pages (official)")
        assert "VERIFIED DATA ROUTES" in b
        assert b.index("VERIFIED DATA ROUTES") < b.index("THE-PAIN")
        assert "state agency pages" in b


class TestBuildDataMenu:
    def _crew(self):
        crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
        crew.niche_context = SimpleNamespace(niche_description="cottage food bakers")
        crew.pain_point_analysis = SimpleNamespace(pain_points=[SimpleNamespace(title="pricing")])
        return crew

    def test_appends_deterministic_routes_and_caches(self):
        crew = self._crew()
        fake = SimpleNamespace(routes=["State cottage-food pages (official) — allowed foods"])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)) as m:
            menu1 = crew._build_data_menu()
            menu2 = crew._build_data_menu()
        assert m.call_count == 1                      # cached after first build
        assert menu1 == menu2
        assert "State cottage-food pages" in menu1
        assert "DataForSEO (licensed)" in menu1       # deterministic always-available routes appended
        assert "Deterministic arithmetic" in menu1

    def test_fail_soft_empty(self):
        crew = self._crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            assert crew._build_data_menu() == ""


class TestCriticMenuInjection:
    def _prompt(self, menu: str | None):
        fake = SimpleNamespace(_format_competitor_mentions=lambda: "",
                               pain_point_analysis=SimpleNamespace(pain_points=[]))
        if menu is not None:
            fake._data_menu_text = menu
        return UnifiedSolutionCrew._calibration_static_prompt(fake)[0]

    def test_menu_in_critic_when_built(self):
        p = self._prompt("- official pages")
        assert "VERIFIED DATA ROUTES" in p and "official pages" in p

    def test_absent_when_menu_failed_soft(self):
        assert "VERIFIED DATA ROUTES" not in self._prompt(None)
