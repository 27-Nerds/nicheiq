"""Portfolio funnel F3 — synthesis bundles (A/B-validated, always on)."""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.niche_context = SimpleNamespace(niche_description="cottage food bakers")
    crew.pain_point_analysis = SimpleNamespace(pain_points=[
        SimpleNamespace(title="Cannot calculate COGS", severity_score=0.7, commercial_intent=0.45),
        SimpleNamespace(title="Labor time in pricing", severity_score=0.65, commercial_intent=0.45),
    ])
    # expansion is exercised by TestExpandBundle; composition tests pin the fail-soft
    # path (expansion None -> the slim composition ships unchanged)
    crew._expand_bundle = lambda b: None
    return crew


def _winner(name):
    return SimpleNamespace(solution_name=name, value_proposition=f"{name} does one thing")


def _fake_bundle(name="BakePrice Pro", pains=("Cannot calculate COGS", "Labor time in pricing")):
    return SimpleNamespace(model_dump=lambda: {
        "solution_name": name, "project_type": "saas",
        "value_proposition": "costing + labor + compliance in one workflow",
        "description": "", "core_features": [], "target_personas": [],
        "pain_points_addressed": list(pains), "conventional_approach": "",
        "innovation_angle": "bundle", "why_it_works": "sev 0.7 pains", "technical_approach": "deterministic",
        "requires_data_aggregation": False, "data_access_model": "public",
        "build_feasibility_score": 0.8, "data_feasibility_score": 0.9,
        "programmatic_seo_opportunity": "", "content_generation_model": "",
    })


class TestSynthesizeBundles:
    def test_bundles_tagged_and_defaults_filled(self):
        crew = _crew()
        fake = SimpleNamespace(bundles=[_fake_bundle()])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1"), _winner("W2")])
        assert len(out) == 1
        b = out[0]
        assert b.idea_tier == "bundle"
        assert b.description  # backfilled from value_proposition
        assert b.core_features and b.target_personas  # required fields defaulted
        assert b.pain_points_addressed == ["Cannot calculate COGS", "Labor time in pricing"]

    def test_cap_respected(self, monkeypatch):
        monkeypatch.setattr(settings, "synthesis_max_bundles", 1)
        crew = _crew()
        fake = SimpleNamespace(bundles=[_fake_bundle("B1"), _fake_bundle("B2")])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert [b.solution_name for b in out] == ["B1"]

    def test_data_menu_flows_into_prompt_when_present(self):
        crew = _crew()
        crew._data_menu_text = "- state pages (official)"
        captured = {}
        def _cap(**kw):
            captured["prompt"] = kw.get("prompt")
            return (SimpleNamespace(bundles=[]), None)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured", side_effect=_cap):
            crew._synthesize_bundles([_winner("W1")])
        assert "VERIFIED DATA ROUTES" in captured["prompt"]

    def test_percent_style_scores_normalized(self):
        # brainstorm models intermittently emit 85 instead of 0.85 — must not fail the 0-1 bounds
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d["build_feasibility_score"] = 85
        d["data_feasibility_score"] = 0.9
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert len(out) == 1 and out[0].build_feasibility_score == 0.85

    def test_bundle_passes_idea_generation_result_validator(self):
        # IdeaGenerationResult requires non-None market_fit_score + technical_feasibility_score on
        # EVERY idea (observed live 2026-07-02: a scoreless bundle killed the whole Stage 5).
        # Bundles must construct valid even when the LLM omits both scores — and the backfill
        # must be LOGGED, not silent.
        from nicheiq.models.solution_idea import IdeaGenerationResult
        crew = _crew()
        fake = SimpleNamespace(bundles=[_fake_bundle()])  # _fake_bundle has no *_fit/_feasibility pair
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)), \
             patch("nicheiq.crews.unified_solution_crew.logger.warning") as warn:
            out = crew._synthesize_bundles([_winner("W1")])
        b = out[0]
        assert b.market_fit_score is not None
        assert b.technical_feasibility_score is not None
        assert any("backfilled defaults" in str(c.args[0]) for c in warn.call_args_list)
        # pad to the container's min-3 floor with score-complete singles
        filler = b.model_copy(update={"solution_name": "S1", "idea_tier": "single"})
        filler2 = b.model_copy(update={"solution_name": "S2", "idea_tier": "single"})
        IdeaGenerationResult(solution_ideas=[b, filler, filler2])  # must not raise

    def test_prose_data_access_model_moved_to_notes(self):
        # codex-review finding: bundles carried prose where singles use the closed tier vocab
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d["data_access_model"] = "Read-only aggregation from Hugging Face Hub metadata"
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        # abstains to 'unverified' (never None: a null label reads as "no data barrier")
        assert out[0].data_access_model == "unverified"
        assert "Hugging Face Hub" in (out[0].data_acquisition_notes or "")

    def test_valid_tier_kept_and_normalized(self):
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d["data_access_model"] = " Public "
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert out[0].data_access_model == "public"

    def test_indexable_pages_parsed_and_seo_cap_binds(self):
        # codex-review finding: bundles had seo=0.9 with pages=None — Rule B never bound
        from nicheiq.config.settings import settings as _s
        from nicheiq.utils.seo_helpers import cap_idea_seo_realism
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d["estimated_indexable_pages"] = "90"     # string from the LLM → int
        d["programmatic_seo_opportunity"] = "aggregated model pages"
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        bundle = out[0]
        assert bundle.estimated_indexable_pages == 90
        bundle.seo_scalability_score = 0.9
        capped, _reason = cap_idea_seo_realism(bundle, _s)
        assert capped is not None and capped < 0.9    # thin-pages rule now binds on bundles

    def test_junk_pages_none(self):
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d["estimated_indexable_pages"] = "a few thousand"
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert out[0].estimated_indexable_pages is None

    def test_fail_soft(self):
        crew = _crew()
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            assert crew._synthesize_bundles([_winner("W1")]) == []

    def test_expansion_result_replaces_composition(self):
        # same-scope (2026-07-03): every bundle goes through _expand_bundle; the expanded
        # idea ships, the slim composition is only the fail-soft fallback.
        crew = _crew()
        marker = SimpleNamespace(solution_name="Expanded BakePrice Pro")
        crew._expand_bundle = lambda b: marker
        fake = SimpleNamespace(bundles=[_fake_bundle()])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert out == [marker]

    def test_expansion_failure_ships_composition(self):
        crew = _crew()  # _expand_bundle -> None
        fake = SimpleNamespace(bundles=[_fake_bundle()])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        assert len(out) == 1 and out[0].solution_name == "BakePrice Pro"


class TestExpandBundle:
    """The expansion must be an EXPANSION, not a redesign: composition-owned fields come
    back verbatim no matter what the LLM returns."""

    def _slim(self):
        from nicheiq.models.solution_idea import BaseSolutionIdea
        return BaseSolutionIdea(
            solution_name="BakePrice Pro", idea_tier="bundle", project_type="saas",
            description="costing + labor + compliance in one workflow",
            value_proposition="costing + labor + compliance",
            pain_points_addressed=["Cannot calculate COGS", "Labor time in pricing"],
            core_features=["bundled workflow"], target_personas=["bakers"],
            market_fit_score=0.6, technical_feasibility_score=0.7,
            data_access_model="public", estimated_indexable_pages=90,
            build_feasibility_score=0.8, data_feasibility_score=0.9,
        )

    def _expanded_llm_idea(self, **kw):
        from nicheiq.models.solution_idea import BaseSolutionIdea
        base = dict(
            solution_name="Renamed By LLM", project_type="saas",
            description="d" * 40, value_proposition="v",
            pain_points_addressed=["totally different pain"],
            core_features=["f1", "f2"], target_personas=["t"],
            headline="One dashboard for compliant pricing",
            short_description="Price bakes with COGS and rules included.",
            pricing_strategy="$15/mo", differentiation_factors=["a", "b"],
            market_fit_score=0.8, technical_feasibility_score=0.8,
        )
        base.update(kw)
        return BaseSolutionIdea(**base)

    def test_carries_composition_owned_fields(self):
        crew = _crew()
        del crew._expand_bundle  # use the real method, not the fixture stub
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(self._expanded_llm_idea(), None)):
            crew._record_divergent_usage = lambda u: None
            out = crew._expand_bundle(self._slim())
        assert out.solution_name == "BakePrice Pro"                # name never redesigned
        assert out.idea_tier == "bundle"
        assert out.pain_points_addressed == ["Cannot calculate COGS", "Labor time in pricing"]
        assert out.data_access_model == "public"
        assert out.estimated_indexable_pages == 90
        # presentation depth comes from the expansion
        assert out.headline and out.pricing_strategy and out.differentiation_factors

    def test_prompt_uses_shared_spec_and_pins_constraints(self):
        from nicheiq.crews.unified_solution_crew import _FULL_FIELD_SPEC
        crew = _crew()
        del crew._expand_bundle
        crew._record_divergent_usage = lambda u: None
        captured = {}
        def _cap(**kw):
            captured["prompt"] = kw.get("prompt")
            return self._expanded_llm_idea(), None
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=_cap):
            crew._expand_bundle(self._slim())
        p = captured["prompt"]
        assert _FULL_FIELD_SPEC in p                     # SAME spec as every other birth path
        assert "NOT a redesign" in p
        assert "keep VERBATIM" in p and "BakePrice Pro" in p
        assert '"Cannot calculate COGS"' in p

    def test_llm_failure_returns_none(self):
        crew = _crew()
        del crew._expand_bundle
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   side_effect=RuntimeError("down")):
            assert crew._expand_bundle(self._slim()) is None

    def test_refine_single_concept_shares_the_spec(self):
        # parity pin: both expansion consumers reference the ONE field spec — adding a
        # field to _FULL_FIELD_SPEC covers winners, re-injections AND bundles.
        import inspect
        src_refine = inspect.getsource(UnifiedSolutionCrew._refine_single_concept)
        src_bundle = inspect.getsource(UnifiedSolutionCrew._expand_bundle)
        assert "_FULL_FIELD_SPEC" in src_refine
        assert "_FULL_FIELD_SPEC" in src_bundle


def test_tunable_default():
    # synthesis is unconditional (flag removed after the 2026-07-02 production A/B)
    assert settings.synthesis_max_bundles == 2
