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
        "requires_data_aggregation": False, "data_access_model": "none",
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
        assert out[0].data_access_model is None                       # no invented tier
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

    def test_presentation_fields_flow_through(self):
        # run-2 review: bundles shipped with headline/pricing/differentiators all None because
        # the _Bundle schema simply didn't carry them (only birth path with no full expansion).
        crew = _crew()
        b = _fake_bundle()
        d = b.model_dump()
        d.update({
            "headline": "One dashboard for compliant home-bakery pricing",
            "short_description": "Price bakes with COGS, labor and state rules included.",
            "pricing_strategy": "$15/mo subscription with free calculator tier",
            "differentiation_factors": ["labor-inclusive costing", "state compliance built in"],
            "organic_discovery_queries": ["cottage food pricing calculator", "home bakery cogs"],
            "estimated_cac_organic": "low ($0-5)",
            "estimated_cac_paid": "moderate ($20-40)",
        })
        fake = SimpleNamespace(bundles=[SimpleNamespace(model_dump=lambda: dict(d))])
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        bundle = out[0]
        assert bundle.headline.startswith("One dashboard")
        assert bundle.pricing_strategy and bundle.short_description
        assert len(bundle.differentiation_factors) == 2
        assert len(bundle.organic_discovery_queries) == 2
        assert bundle.estimated_cac_organic and bundle.estimated_cac_paid

    def test_omitted_presentation_fields_become_none_not_empty(self):
        # empty-string schema defaults must land as None so {#if} guards / audits see the gap
        crew = _crew()
        fake = SimpleNamespace(bundles=[_fake_bundle()])  # no presentation fields at all
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured",
                   return_value=(fake, None)):
            out = crew._synthesize_bundles([_winner("W1")])
        b = out[0]
        assert b.headline is None
        assert b.short_description is None
        assert b.pricing_strategy is None
        assert b.differentiation_factors is None
        assert b.organic_discovery_queries is None

    def test_prompt_demands_presentation_fields(self):
        crew = _crew()
        captured = {}
        def _cap(**kw):
            captured["prompt"] = kw.get("prompt")
            return (SimpleNamespace(bundles=[]), None)
        with patch("nicheiq.crews.unified_solution_crew.LLMService.invoke_structured", side_effect=_cap):
            crew._synthesize_bundles([_winner("W1")])
        p = captured["prompt"]
        for needle in ("headline", "short_description", "pricing_strategy",
                       "differentiation_factors", "organic_discovery_queries"):
            assert needle in p, needle


def test_tunable_default():
    # synthesis is unconditional (flag removed after the 2026-07-02 production A/B)
    assert settings.synthesis_max_bundles == 2
