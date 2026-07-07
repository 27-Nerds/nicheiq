"""Hermetic tests for the in-cell scorer move (scorers run per-cell in the tournament; the
post-union passes finish only stragglers, idempotently).

Covers: the extracted per-idea scorers (`_calibrate_batch`, `_apply_tags_to`, `_validate_idea_caps`),
the in-cell chain (`_score_cell_winner`, order + the skip_selection SEO gate), and the post-union
idempotency skips. All LLM calls are mocked.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew


def _crew():
    c = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    c.niche_context = SimpleNamespace(niche_description="A test niche")
    c.competitor_mentions_text = "Competitor A, Competitor B"
    c.pain_point_analysis = None
    return c


def _idea(name, **over):
    base = dict(
        solution_name=name, source_pain="P", pain_points_addressed=["P"],
        value_proposition="vp", conventional_approach="ca", innovation_angle="ia",
        why_it_works="ww", technical_approach="ta", requires_data_aggregation=False,
        data_access_model="public", build_feasibility_score=0.8, data_feasibility_score=0.7,
        programmatic_seo_opportunity="seo", content_generation_model="cgm",
        market_fit_score=0.8, technical_feasibility_score=0.8, novelty_score=0.5,
        seo_scalability_score=0.6, obviousness_score=0.5,
        market_fit_score_raw=None, technical_feasibility_score_raw=None,
        novelty_score_raw=None, seo_scalability_score_raw=None, obviousness_score_raw=None,
        calibration_notes=None, tags=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


# --- _calibrate_batch (extraction parity) ----------------------------------

def test_calibrate_batch_sets_scores_and_preserves_raw(monkeypatch):
    # pin N=1: this test asserts SINGLE-call semantics (default is 3 since the P2 gate)
    monkeypatch.setattr(usc.settings, "score_calibration_samples", 1)
    idea = _idea("Idea A", market_fit_score=0.9)
    cal = SimpleNamespace(
        name="Idea A", market_fit_score=0.3, market_fit_reason="thin evidence",
        technical_feasibility_score=-1.0, novelty_score=-1.0,
        seo_scalability_score=-1.0, obviousness_score=-1.0,
    )
    monkeypatch.setattr(usc.LLMService, "invoke_structured",
                        lambda **kw: (SimpleNamespace(calibrations=[cal]), {"usage": 1}))
    applied, usage = _crew()._calibrate_batch(batch=[idea])
    assert applied == 1
    assert idea.market_fit_score == 0.3        # replaced with the critic's value
    assert idea.market_fit_score_raw == 0.9    # original preserved once
    assert usage == {"usage": 1}               # returned, not recorded inline


# --- _apply_tags_to (extraction parity) ------------------------------------

def test_apply_tags_to_sets_tags_and_returns_usage(monkeypatch):
    monkeypatch.setattr(usc.LLMService, "invoke_structured",
                        lambda **kw: (SimpleNamespace(tags=[]), {"u": 1}))
    monkeypatch.setattr("nicheiq.utils.idea_tags.derive_tag_facets", lambda idea, facets: "TAGS")
    monkeypatch.setattr("nicheiq.utils.idea_tags.validate_solution_tags", lambda tags, names: (True, ""))
    idea = _idea("Idea A")
    usage = _crew()._apply_tags_to([idea])
    assert idea.tags == "TAGS"
    assert usage == {"u": 1}


# --- _validate_idea_caps (pure: no shared-state mutation) -------------------

def test_validate_idea_caps_novelty_cap_no_caveats():
    c = _crew()
    idea = _idea("A", novelty_score=0.9, obviousness_score=0.5)  # 0.9 > (1-0.5)+0.25
    flags = c._validate_idea_caps(idea)
    assert idea.novelty_score == 0.5            # snapped to 1 - obviousness
    assert flags                                # returns the weakness reason
    assert not hasattr(c, "coverage_caveats")   # never touches shared state


def test_validate_idea_caps_market_fit_cap_on_unverified():
    idea = _idea("B", market_fit_score=0.8, data_access_model="blocked")
    _crew()._validate_idea_caps(idea)
    assert idea.market_fit_score == 0.4


def test_validate_idea_caps_idempotent():
    idea = _idea("C", novelty_score=0.9, obviousness_score=0.5)
    c = _crew()
    c._validate_idea_caps(idea)
    first = idea.novelty_score
    assert not c._validate_idea_caps(idea)      # already capped → no new flags
    assert idea.novelty_score == first


def test_validate_idea_scores_still_emits_concentration_caveat():
    c = _crew()
    cap = usc.settings.diversity_max_per_segment
    ideas = [_idea(f"I{n}", source_pain="Same pain") for n in range(cap + 1)]
    c._validate_idea_scores(ideas)
    assert any("address one pain" in cav for cav in getattr(c, "coverage_caveats", []))


# --- _novelty_enhance (gate + accept-guard) --------------------------------

def _ne_crew(monkeypatch, revised, *, calls=None):
    """Crew with the revise LLM + re-score steps stubbed so we test ONLY the gate + accept logic.
    `revised` is the (already re-scored) candidate returned by the revise step."""
    c = _crew()
    def _revise(idea, usages):
        if calls is not None:
            calls.append("revise")
        return revised
    monkeypatch.setattr(c, "_enhance_idea_mechanism", _revise)
    monkeypatch.setattr(c, "_finalize_feasibility", lambda one: None)
    monkeypatch.setattr(c, "_calibrate_batch", lambda batch: (1, None))
    monkeypatch.setattr(c, "_validate_idea_caps", lambda idea: [])
    return c


def test_novelty_enhance_gate_skips_already_novel(monkeypatch):
    calls = []
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.3, novelty_score=0.6)  # not obvious
    out = _ne_crew(monkeypatch, _idea("REV"), calls=calls)._novelty_enhance(idea, usages=[])
    assert out is idea and calls == []          # gated out, no revise call


def test_novelty_enhance_gate_skips_weak_demand(monkeypatch):
    calls = []
    idea = _idea("A", market_fit_score=0.3, obviousness_score=0.7, novelty_score=0.4)  # low mf
    out = _ne_crew(monkeypatch, _idea("REV"), calls=calls)._novelty_enhance(idea, usages=[])
    assert out is idea and calls == []


def test_novelty_enhance_accepts_strict_improvement(monkeypatch):
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 technical_feasibility_score=0.8)
    rev = _idea("REV", novelty_score=0.6, market_fit_score=0.7, technical_feasibility_score=0.8)
    out = _ne_crew(monkeypatch, rev)._novelty_enhance(idea, usages=[])
    assert out is rev                            # +0.2 novelty, no regression → kept


def test_novelty_enhance_rejects_insufficient_lift(monkeypatch):
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 technical_feasibility_score=0.8)
    rev = _idea("REV", novelty_score=0.45, market_fit_score=0.7, technical_feasibility_score=0.8)
    out = _ne_crew(monkeypatch, rev)._novelty_enhance(idea, usages=[])
    assert out is idea                           # +0.05 < 0.10 lift → original kept


def test_novelty_enhance_rejects_feasibility_regression(monkeypatch):
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 technical_feasibility_score=0.8)
    rev = _idea("REV", novelty_score=0.6, market_fit_score=0.7, technical_feasibility_score=0.7)
    out = _ne_crew(monkeypatch, rev)._novelty_enhance(idea, usages=[])
    assert out is idea                           # tf 0.8->0.7 drop > 0.05 tol → original kept


def test_novelty_enhance_rejects_seo_regression(monkeypatch):
    # A clever rewrite that lifts novelty but craters SEO (e.g. directory -> thin tool) must be rejected.
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 technical_feasibility_score=0.8, seo_scalability_score=0.8)
    rev = _idea("REV", novelty_score=0.7, market_fit_score=0.7, technical_feasibility_score=0.8,
                seo_scalability_score=0.4)  # SEO 0.8->0.4 collapse
    out = _ne_crew(monkeypatch, rev)._novelty_enhance(idea, usages=[])
    assert out is idea                           # SEO regression > tol → original directory kept


# --- _novelty_enhance angle-aware skip-gate (Stage 3) ----------------------

def test_novelty_enhance_skips_distribution_angle(monkeypatch):
    # validated + obvious (would normally enhance), but the agent's angle is distribution_seo -> skip
    # the mechanism rewrite (wrong lever; Phase 2b handles it). No revise call.
    calls = []
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 winning_angle="distribution_seo")
    out = _ne_crew(monkeypatch, _idea("REV"), calls=calls)._novelty_enhance(idea, usages=[])
    assert out is idea and calls == []


def test_novelty_enhance_skips_workflow_angle(monkeypatch):
    calls = []
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 winning_angle="vertical_workflow")
    out = _ne_crew(monkeypatch, _idea("REV"), calls=calls)._novelty_enhance(idea, usages=[])
    assert out is idea and calls == []


def test_novelty_enhance_runs_for_novel_angle(monkeypatch):
    # novel_differentiation is the RIGHT lever for the mechanism enhance -> not skipped; runs + accepts.
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 technical_feasibility_score=0.8, seo_scalability_score=0.6,
                 winning_angle="novel_differentiation")
    rev = _idea("REV", novelty_score=0.6, market_fit_score=0.7, technical_feasibility_score=0.8,
                seo_scalability_score=0.6)
    out = _ne_crew(monkeypatch, rev)._novelty_enhance(idea, usages=[])
    assert out is rev


def test_novelty_enhance_skip_heuristic_when_angle_unset(monkeypatch):
    # winning_angle unset (classify off/fail-soft) -> deterministic fallback: directory + high SEO +
    # programmatic_seo opportunity -> skip.
    calls = []
    idea = _idea("A", market_fit_score=0.7, obviousness_score=0.7, novelty_score=0.4,
                 winning_angle=None, project_type="directory", seo_scalability_score=0.6,
                 programmatic_seo_opportunity="per-entity pages")
    out = _ne_crew(monkeypatch, _idea("REV"), calls=calls)._novelty_enhance(idea, usages=[])
    assert out is idea and calls == []


# --- _enhance_idea_mechanism (rename propagation) --------------------------

def test_enhance_propagates_rename_into_description(monkeypatch):
    # The enhance pass renames the idea; description/short_description carry the OLD name and must
    # be updated so a stale name never leaks (the DiffTrace/UpdateBlastRadius bug).
    rev = SimpleNamespace(solution_name="DiffTrace", value_proposition="vp", conventional_approach="",
                          innovation_angle="ia", why_it_works="", technical_approach="ta", core_features=[])
    monkeypatch.setattr(usc.LLMService, "invoke_structured", lambda **kw: (rev, None))
    idea = _idea("UpdateBlastRadius")
    idea.description = "UpdateBlastRadius performs a static diff of UpdateBlastRadius's targets."
    idea.short_description = "UpdateBlastRadius catches breaking updates."
    idea.headline = "UpdateBlastRadius"
    out = _crew()._enhance_idea_mechanism(idea, usages=[])
    assert out.solution_name == "DiffTrace"
    assert "UpdateBlastRadius" not in out.description
    assert "DiffTrace performs a static diff of DiffTrace's targets." == out.description
    assert "UpdateBlastRadius" not in out.short_description and "UpdateBlastRadius" not in out.headline


def test_enhance_rewrites_display_fields_to_new_mechanism(monkeypatch):
    # The real fix: when the LLM returns rewritten display fields, they REPLACE the carried ones so
    # the card describes the NEW mechanism (not just the new name).
    rev = SimpleNamespace(
        solution_name="DiffTrace", value_proposition="vp", conventional_approach="",
        innovation_angle="static code diff", why_it_works="", technical_approach="ta", core_features=[],
        description="The tool statically cross-references HA Core code diffs against each card's source.",
        short_description="See which cards a release will break, by code diff.",
        headline="Static code-diff impact analysis")
    monkeypatch.setattr(usc.LLMService, "invoke_structured", lambda **kw: (rev, None))
    idea = _idea("UpdateBlastRadius")
    idea.description = "UpdateBlastRadius mines a database of breaking changes from GitHub issues."
    out = _crew()._enhance_idea_mechanism(idea, usages=[])
    # carried 'database of breaking changes' (old mechanism) is GONE; new code-diff description used
    assert "database of breaking changes" not in out.description
    assert out.description == rev.description
    assert out.headline == "Static code-diff impact analysis"


# --- _filter_pain_relevance (over-claimed pain trimming) -------------------

def _pain_idea(**over):
    base = dict(solution_name="X", source_pain="A", pain_points_addressed=["A", "B", "C"],
                value_proposition="vp", technical_approach="ta", core_features=["f1", "f2"])
    base.update(over)
    return SimpleNamespace(**base)


def test_pain_relevance_trims_to_kept(monkeypatch):
    monkeypatch.setattr(usc.LLMService, "invoke_structured",
                        lambda **kw: (usc._PainRelevance(keep=[1]), None))  # keep extra #1 = "B"
    idea = _pain_idea()
    _crew()._filter_pain_relevance([idea])
    assert idea.pain_points_addressed == ["A", "B"]      # source + kept extra; "C" dropped


def test_pain_relevance_always_keeps_source(monkeypatch):
    monkeypatch.setattr(usc.LLMService, "invoke_structured",
                        lambda **kw: (usc._PainRelevance(keep=[]), None))  # keep nothing
    idea = _pain_idea()
    _crew()._filter_pain_relevance([idea])
    assert idea.pain_points_addressed == ["A"]           # source pain is never dropped


def test_pain_relevance_failsoft_keeps_all(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("llm down")
    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_boom))
    idea = _pain_idea()
    _crew()._filter_pain_relevance([idea])
    assert idea.pain_points_addressed == ["A", "B", "C"]  # unchanged on error


# --- _score_cell_winner (in-cell chain order + SEO gate) -------------------

def _patch_chain(monkeypatch, order):
    monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_feasibility",
                        lambda self, ideas: order.append("feas"))
    monkeypatch.setattr(UnifiedSolutionCrew, "_calibrate_batch",
                        lambda self, *, batch: (order.append("cal"), (1, None))[1])
    monkeypatch.setattr(UnifiedSolutionCrew, "_validate_idea_caps",
                        lambda self, idea: order.append("val") or [])
    # Angle classify is a separate fail-soft concern (own tests); stub it out of the scored chain.
    monkeypatch.setattr(UnifiedSolutionCrew, "_classify_batch",
                        lambda self, *, batch: (0, None))
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seo_realism",
                        lambda self, ideas: order.append("seo"))


def test_score_cell_winner_runs_chain_in_order(monkeypatch):
    # In-cell tagging was removed 2026-07-06 (post-union clears + re-tags the FULL set from
    # final post-parity scores, so a per-cell tag call was pure discard).
    order: list = []
    _patch_chain(monkeypatch, order)
    _crew()._score_cell_winner(_idea("W"), skip_selection=True, usages=[])
    assert order == ["feas", "cal", "val", "seo"]


def test_score_cell_winner_skips_seo_on_legacy_path(monkeypatch):
    order: list = []
    _patch_chain(monkeypatch, order)
    _crew()._score_cell_winner(_idea("W"), skip_selection=False, usages=[])
    assert order == ["feas", "cal", "val"]   # no SEO on the one-shot path


def test_score_cell_winner_funnels_usage(monkeypatch):
    monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_feasibility", lambda self, ideas: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_validate_idea_caps", lambda self, idea: [])
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seo_realism", lambda self, ideas: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_calibrate_batch", lambda self, *, batch: (1, "CAL_U"))
    monkeypatch.setattr(UnifiedSolutionCrew, "_classify_batch", lambda self, *, batch: (0, None))
    usages: list = []
    _crew()._score_cell_winner(_idea("W"), skip_selection=True, usages=usages)
    assert usages == ["CAL_U"]   # LLM usage funnels into the shared sink


# --- post-union idempotency (finish only stragglers) ----------------------

def test_calibrate_idea_scores_skips_already_calibrated(monkeypatch):
    monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
    seen: list = []
    monkeypatch.setattr(UnifiedSolutionCrew, "_calibrate_batch",
                        lambda self, *, batch: seen.extend(batch) or (len(batch), None))
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel",
                        lambda self, fn, jobs, *a, **k: [fn(**j) for j in jobs])
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)
    done = _idea("Done", market_fit_score_raw=0.9)   # scored in-cell already
    todo = _idea("Todo")                             # coverage-net straggler
    _crew()._calibrate_idea_scores([done, todo])
    assert todo in seen and done not in seen


def test_apply_tags_tags_only_untagged(monkeypatch):
    seen: list = []
    monkeypatch.setattr(UnifiedSolutionCrew, "_apply_tags_to",
                        lambda self, ideas: seen.extend(ideas) or None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage",
                        lambda self, u: None, raising=False)
    tagged = _idea("Tagged", tags="X")
    untagged = _idea("Untagged", tags=None)
    _crew()._apply_tags(SimpleNamespace(solution_ideas=[tagged, untagged]))
    assert untagged in seen and tagged not in seen


# --- solo_dev cap + dev-time band (quick-win grounding fixes) ----------------

def test_validate_idea_caps_solo_dev_capped_to_build():
    from nicheiq.config.settings import settings as _s
    idea = _idea("Solo", solo_dev_feasibility=0.95, build_feasibility_score=0.3)
    flags = _crew()._validate_idea_caps(idea)
    assert idea.solo_dev_feasibility < 0.95  # capped down
    assert idea.solo_dev_feasibility <= 0.3 + _s.feasibility_build_data_coupling_margin + 1e-6
    assert any("solo_dev" in x for x in flags)


def test_validate_idea_caps_solo_dev_untouched_when_within_build():
    idea = _idea("Solo2", solo_dev_feasibility=0.5, build_feasibility_score=0.9)
    _crew()._validate_idea_caps(idea)
    assert idea.solo_dev_feasibility == 0.5  # already ≤ build + margin


def test_finalize_dev_time_sets_grounded_estimate(monkeypatch):
    from nicheiq.crews.unified_solution_crew import _DevTimeEstimate
    monkeypatch.setattr(usc.LLMService, "invoke_structured",
                        lambda **kw: (_DevTimeEstimate(rationale="data pipeline is the long pole",
                                                       estimate="6-10 weeks"), {"u": 1}))
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel",
                        lambda self, fn, jobs, *a, **k: [fn(**j) for j in jobs])
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    c = _crew(); c.search_tool = None  # no search → prompt still works (LLM mocked)
    idea = _idea("DT", core_features=["a", "b"], estimated_development_time="3-4 months")
    c._finalize_dev_time([idea])
    assert idea.estimated_development_time == "6-10 weeks"   # grounded range replaces the point guess


def test_finalize_dev_time_prompt_has_calibration_bands(monkeypatch):
    # run-2 review: estimates ran ~4x over for standard documented-API ideas (4-6 months for a
    # pip-audit + public API + arithmetic build). The bands tie the estimate to observable
    # component properties; data_feasibility now rides along as an anchor.
    from nicheiq.crews.unified_solution_crew import _DevTimeEstimate
    captured = {}
    def _cap(**kw):
        captured["prompt"] = kw.get("prompt")
        return _DevTimeEstimate(rationale="r", estimate="4-6 weeks"), None
    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_cap))
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel",
                        lambda self, fn, jobs, *a, **k: [fn(**j) for j in jobs])
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    c = _crew(); c.search_tool = None
    idea = _idea("DT3", core_features=["a"], data_feasibility_score=0.85)
    c._finalize_dev_time([idea])
    p = captured["prompt"]
    assert "classify FIRST" in p and "STANDARD" in p and "HARD" in p
    assert "3-6 weeks" in p and "2-4 months" in p and "4-6+ months" in p
    assert "DAYS each, not weeks" in p
    assert "WORKED EXAMPLE" in p and "SCOPE TO THE MVP" in p
    assert "DATA-FEASIBILITY" in p and "0.85" in p


def test_reconcile_dev_time_band_arithmetic():
    # the model classifies; CODE does the band arithmetic it kept getting wrong (3 replay
    # iterations: estimates contradicted the model's own component labels)
    from nicheiq.crews.unified_solution_crew import _parse_range_weeks, _reconcile_dev_time
    assert _parse_range_weeks("6-10 weeks") == (6, 10)
    lo, hi = _parse_range_weeks("2-4 months")
    assert 8 < lo < 9 and 17 < hi < 18
    assert _parse_range_weeks("soon") is None
    # 0 HARD -> weeks band: a months estimate gets overridden
    est, over = _reconcile_dev_time("4-6 months", ["parsing — STANDARD", "ui — STANDARD"])
    assert est == "3-6 weeks" and over
    # 1 HARD -> months band: consistent estimate kept verbatim
    est, over = _reconcile_dev_time("2-3 months", ["nlp — HARD", "ui — STANDARD"])
    assert est == "2-3 months" and not over
    # 2 HARD -> long band: a weeks estimate gets overridden
    est, over = _reconcile_dev_time("5-6 weeks", ["nlp — HARD", "resolution — HARD"])
    assert est == "4-6+ months" and over
    # no components (legacy response) -> estimate passes through untouched
    est, over = _reconcile_dev_time("7-9 weeks", [])
    assert est == "7-9 weeks" and not over


def test_finalize_dev_time_failsoft_keeps_prior(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_boom))
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel",
                        lambda self, fn, jobs, *a, **k: [fn(**j) for j in jobs])
    monkeypatch.setattr(UnifiedSolutionCrew, "_record_divergent_usage", lambda self, u: None, raising=False)
    c = _crew(); c.search_tool = None
    idea = _idea("DT2", core_features=["a"], estimated_development_time="2-3 months")
    c._finalize_dev_time([idea])
    assert idea.estimated_development_time == "2-3 months"   # fail-soft: prior estimate kept


def test_pipeline_clears_tags_before_full_retag():
    # 2026-07-06: generator LLMs can fabricate a whole `tags` object through the shared
    # BaseSolutionIdea schema (observed live on a bundle: invented 'market-fit' strength at
    # mf 0.6), and in-cell tags bucket on PRE-parity scores. The pipeline must clear tags for
    # the FULL set right before the post-union _apply_tags so every idea is re-derived once
    # from FINAL scores. Source-pin (execute_pipeline is too heavy to run hermetically).
    import inspect
    src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
    clear_idx = src.find("_idea.tags = None")
    apply_idx = src.find("self._apply_tags(refined_solutions)")
    assert clear_idx != -1 and apply_idx != -1 and clear_idx < apply_idx
    # and the in-cell chain no longer tags (pure discard once the post-union re-tag exists)
    cell_src = inspect.getsource(UnifiedSolutionCrew._score_cell_winner)
    assert "_apply_tags_to" not in cell_src
