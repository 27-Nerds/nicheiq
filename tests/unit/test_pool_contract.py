"""Pool-assembly contract (2026-07-03): one choke point over all four idea birth paths.
Every prior shape bug (bundle scores, prose data_access_model, free-text project_type
chips) was a per-birth-path escape — this retires the class."""

import inspect
from types import SimpleNamespace

from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.coverage_caveats = []
    return crew


def _idea(**kw):
    base = dict(solution_name="X", project_type="saas", data_access_model="public",
                technical_approach="", data_acquisition_notes="",
                winning_angle="distribution_seo", novelty_score=0.5,
                calibration_notes="market_fit: ok")
    base.update(kw)
    return SimpleNamespace(**base)


class TestProjectTypeNormalizer:
    def test_observed_malformed_strings_clamp(self):
        # the exact strings from the crashed astro run that broke the frontend chips
        crew = _crew()
        a = _idea(project_type="Desktop app + lightweight local agent (Windows/macOS)")
        b = _idea(project_type="Desktop app (with optional cloud fetch of model metadata)")
        crew._finalize_idea_pool([a, b])
        assert a.project_type == "saas" and b.project_type == "saas"
        assert "Desktop app + lightweight local agent" in a.technical_approach

    def test_keyword_mapping(self):
        crew = _crew()
        ideas = [_idea(project_type="Curated aggregator of benchmarks"),
                 _idea(project_type="A public directory site"),
                 _idea(project_type="Comparison engine"),
                 _idea(project_type="Niche marketplace platform")]
        crew._finalize_idea_pool(ideas)
        assert [i.project_type for i in ideas] == [
            "aggregator", "directory", "comparison-tool", "marketplace"]

    def test_valid_types_untouched(self):
        crew = _crew()
        i = _idea(project_type="comparison-tool", technical_approach="orig")
        crew._finalize_idea_pool([i])
        assert i.project_type == "comparison-tool" and i.technical_approach == "orig"


class TestWellKnownSourceUpgrade:
    """Only tournament winners pass the web route-verifier; bundles/salvaged carry the
    critic's model-knowledge label — observed wrong on famous sources (run-2: a bundle
    shipped SAM.gov as 'paywalled'). Two-step (retrieval + LLM confirm), upgrade-only,
    all-sources-must-match."""

    def _confirm(self, monkeypatch, answer):
        import nicheiq.utils.public_data_sources as pds
        if answer:
            monkeypatch.setattr(pds, "llm_confirm_known_route",
                                lambda m, **kw: ", ".join(dict.fromkeys(n for _, n in m)))
        else:
            monkeypatch.setattr(pds, "llm_confirm_known_route", lambda m, **kw: None)

    def test_famous_sources_lift_restrictive_label(self, monkeypatch):
        self._confirm(monkeypatch, True)
        crew = _crew()
        i = _idea(data_access_model="paywalled",
                  data_sources=["SAM.gov opportunity notices", "SEC EDGAR full-text search API"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "public"
        assert "SAM.gov" in i.data_acquisition_notes

    def test_confirm_rejection_keeps_label(self, monkeypatch):
        self._confirm(monkeypatch, False)
        crew = _crew()
        i = _idea(data_access_model="paywalled", data_sources=["SAM.gov opportunity notices"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "paywalled"   # LLM said the match is superficial

    def test_mixed_sources_do_not_upgrade(self, monkeypatch):
        def _no_confirm(*a, **kw):
            raise AssertionError("confirm must not run when retrieval fails")
        import nicheiq.utils.public_data_sources as pds
        monkeypatch.setattr(pds, "llm_confirm_known_route", _no_confirm)
        crew = _crew()
        i = _idea(data_access_model="restricted",
                  data_sources=["GitHub Issues API", "VendorMetrics partner feed"])
        crew._finalize_idea_pool([i])
        assert i.data_access_model == "restricted"

    def test_public_label_untouched_and_no_sources_noop(self, monkeypatch):
        self._confirm(monkeypatch, True)
        crew = _crew()
        a = _idea(data_access_model="public", data_sources=["SAM.gov"],
                  data_acquisition_notes="rich note")
        b = _idea(data_access_model="unverified", data_sources=[])
        crew._finalize_idea_pool([a, b])
        assert a.data_acquisition_notes == "rich note"   # upgrade path never ran
        assert b.data_access_model == "unverified"


class TestDataAccessAndCompleteness:
    def test_prose_data_access_moved_to_notes(self):
        crew = _crew()
        i = _idea(data_access_model="Read-only aggregation from GitHub issues")
        crew._finalize_idea_pool([i])
        assert i.data_access_model is None
        assert "GitHub issues" in i.data_acquisition_notes

    def test_under_evaluated_ideas_get_one_caveat(self):
        crew = _crew()
        ideas = [_idea(),
                 _idea(solution_name="Ghost1", winning_angle=None, novelty_score=None,
                       calibration_notes=None)]
        crew._finalize_idea_pool(ideas)
        assert len(crew.coverage_caveats) == 1
        assert "Ghost1" in crew.coverage_caveats[0]
        assert "generator self-assessment" in crew.coverage_caveats[0]

    def test_fully_evaluated_pool_no_caveat(self):
        crew = _crew()
        crew._finalize_idea_pool([_idea(), _idea(solution_name="Y")])
        assert crew.coverage_caveats == []


def test_contract_runs_after_reinjection():
    # order pin: the contract must cover coverage-net re-injections (they join LAST)
    src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
    assert src.index("enforce_pain_coverage(") < src.index("_finalize_idea_pool(")
