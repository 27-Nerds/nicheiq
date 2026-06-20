"""Phase 1 — merged feasibility critic + verdict-boundary caps (flagged).

Exercises the critic via a SimpleNamespace 'self' (avoids heavy __init__), and the
verdict caps via the static/instance helpers on ReportGenerator with a stub state.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.models.solution_idea import RawConcept


def _rc(name, obv=0.3):
    return RawConcept(
        concept_name=name,
        one_liner=f"{name} does a thing",
        ideation_technique="niche_drilling",
        project_type="saas",
        target_keywords=["a", "b"],
    )


def _critic_self():
    return SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing tool",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    )


def _verdicts(items, drop_names=None):
    return usc._NoveltyVerdicts(
        verdicts=[usc._NoveltyVerdict(**it) for it in items],
        drop_names=drop_names or [],
    )


class TestMergedCriticFlagOn:
    def _run(self, monkeypatch, concepts, result):
        monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (result, SimpleNamespace())),
        )
        return usc.UnifiedSolutionCrew._score_pool_novelty(_critic_self(), concepts)

    def test_writes_feasibility_fields_and_keeps_unofficial(self, monkeypatch):
        concepts = [_rc("A"), _rc("B")]
        result = _verdicts([
            {"name": "A", "independent_obviousness": 0.2, "build_feasibility": 0.7,
             "data_feasibility": 0.65, "data_access_model": "unofficial",
             "data_notes": "via community scraper; ToS-gray"},
            {"name": "B", "independent_obviousness": 0.3, "build_feasibility": 0.8,
             "data_feasibility": 0.9, "data_access_model": "public", "data_notes": "public API"},
        ])
        out = self._run(monkeypatch, concepts, result)
        names = {c.concept_name for c in out}
        assert names == {"A", "B"}  # unofficial KEPT, nothing dropped
        a = next(c for c in out if c.concept_name == "A")
        assert a.build_feasibility_score == 0.7
        assert a.data_feasibility_score == 0.65
        assert a.data_access_model == "unofficial"

    def test_drop_names_allowlisted_and_applied(self, monkeypatch):
        concepts = [_rc(f"c{i}") for i in range(8)]  # >= MIN_KEEP so a drop survives
        result = _verdicts(
            [{"name": f"c{i}", "independent_obviousness": 0.3, "build_feasibility": 0.7,
              "data_feasibility": 0.5, "data_access_model": "public"} for i in range(8)],
            drop_names=["c0", "NONEXISTENT-INJECTED"],  # second is not an input → ignored
        )
        out = self._run(monkeypatch, concepts, result)
        names = {c.concept_name for c in out}
        assert "c0" not in names          # legit no-route drop applied
        assert len(out) == 7              # only one dropped; injected name ignored
        assert "NONEXISTENT-INJECTED" not in names

    def test_floor_guard_refills_large_pool(self, monkeypatch):
        concepts = [_rc(f"c{i}") for i in range(8)]
        # drop 5 → would leave 3 (<6) → floor refills back to 6
        result = _verdicts(
            [{"name": f"c{i}", "independent_obviousness": 0.3} for i in range(8)],
            drop_names=[f"c{i}" for i in range(5)],
        )
        out = self._run(monkeypatch, concepts, result)
        assert len(out) == 6

    def test_fail_open(self, monkeypatch):
        monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
        def boom(**kw):
            raise RuntimeError("x")
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(boom))
        concepts = [_rc("A"), _rc("B")]
        out = usc.UnifiedSolutionCrew._score_pool_novelty(_critic_self(), concepts)
        assert len(out) == 2  # unchanged

    def test_flag_off_runs_novelty_only(self, monkeypatch):
        monkeypatch.setattr(usc.settings, "enable_feasibility_critic", False)
        result = _verdicts([{"name": "A", "independent_obviousness": 0.2, "already_exists": False}])
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (result, SimpleNamespace())),
        )
        out = usc.UnifiedSolutionCrew._score_pool_novelty(_critic_self(), [_rc("A")])
        a = out[0]
        assert a.obviousness_score == 0.2
        # feasibility fields untouched (sentinels)
        assert a.build_feasibility_score == -1.0 and a.data_access_model is None


# ---- verdict-boundary caps ----

import nicheiq.report.report_generator as rg


def _gen_with_pains(pains):
    gen = rg.ReportGenerator.__new__(rg.ReportGenerator)
    gen.state = SimpleNamespace(pain_point_analysis=SimpleNamespace(pain_points=pains))
    return gen


def _pain(title, opp):
    return SimpleNamespace(title=title, opportunity_level=opp)


def _sol(name="S", pains=None, mfs=None, tf=None, bf=None):
    return SimpleNamespace(
        solution_name=name, pain_points_addressed=pains or [],
        market_fit_score=mfs, technical_feasibility_score=tf, build_feasibility_score=bf,
    )


class TestVerdictCaps:
    def test_build_cap_downgrade_only(self):
        gen = _gen_with_pains([])
        sol = _sol(bf=0.4)
        mf, tf, note = gen._apply_verdict_data_caps(sol, market_fit=0.8, tech_feasibility=0.9)
        assert tf == 0.4 and note and "build feasibility" in note  # lowered

    def test_build_cap_never_raises(self):
        gen = _gen_with_pains([])
        sol = _sol(bf=0.95)
        _mf, tf, _note = gen._apply_verdict_data_caps(sol, market_fit=0.8, tech_feasibility=0.7)
        assert tf == 0.7  # critic higher → keep self

    def test_sentinel_never_caps(self):
        gen = _gen_with_pains([])
        sol = _sol(bf=-1.0)
        _mf, tf, _note = gen._apply_verdict_data_caps(sol, market_fit=0.8, tech_feasibility=0.7)
        assert tf == 0.7  # sentinel ignored

    def test_market_fit_ceiling_low_pain(self):
        gen = _gen_with_pains([_pain("invoicing is painful", "low")])
        sol = _sol(pains=["invoicing is painful"])
        mf, _tf, note = gen._apply_verdict_data_caps(sol, market_fit=0.9, tech_feasibility=0.8)
        assert mf == 0.55 and note and "market fit" in note

    def test_market_fit_high_pain_uncapped(self):
        gen = _gen_with_pains([_pain("invoicing is painful", "high")])
        sol = _sol(pains=["invoicing is painful"])
        mf, _tf, _note = gen._apply_verdict_data_caps(sol, market_fit=0.9, tech_feasibility=0.8)
        assert mf == 0.9  # high → ceiling 1.0 → no cap

    def test_market_fit_no_match_floor(self):
        gen = _gen_with_pains([_pain("totally different topic", "high")])
        sol = _sol(pains=["unrelated idea about gardening robots"])
        mf, _tf, _note = gen._apply_verdict_data_caps(sol, market_fit=0.9, tech_feasibility=0.8)
        assert mf == 0.45  # no pain clears → floor


# ---- Phase 5: trend longevity downgrade-only reconcile ----

from nicheiq.crews.trend_longevity_crew import reconcile_longevity_verdict as _recon


class TestTrendReconcile:
    def test_llm_may_not_raise_above_grounded(self):
        assert _recon("Risky", "Sustainable") == "Risky"  # clamped down

    def test_llm_may_lower(self):
        assert _recon("Sustainable", "Fad") == "Fad"      # LLM worse → kept
        assert _recon("Sustainable", "Risky") == "Risky"

    def test_equal_kept(self):
        assert _recon("Risky", "Risky") == "Risky"

    def test_undetermined_keeps_llm(self):
        assert _recon("Undetermined", "Sustainable") == "Sustainable"
        assert _recon("Undetermined", "Fad") == "Fad"


# ---- Phase 4: Stage-13 data-feasibility reconcile (downgrade-only) ----

from nicheiq.crews.data_source_crew import reconcile_data_feasibility as _recon_data


class TestDataReconcile:
    def test_harder_lowers_and_caveats(self):
        # critic said public (0.95); Stage-13 verified 'paid' → harder
        score, access, caveat = _recon_data(0.95, "public", "paid")
        assert score == 0.65 and access == "paid" and caveat and "harder" in caveat

    def test_unofficial_estimate_to_paid(self):
        score, access, caveat = _recon_data(0.6, "unofficial", "partner-only")
        assert score <= 0.4 and access == "partner-only" and caveat

    def test_not_harder_no_change(self):
        # Stage-13 'public' is easier than critic 'paywalled' → no downgrade
        score, access, caveat = _recon_data(0.65, "paywalled", "public")
        assert score == 0.65 and access == "paywalled" and caveat is None

    def test_never_raises_score(self):
        # critic already low; verified 'freemium' (0.8) must NOT raise it
        score, _access, caveat = _recon_data(0.3, "restricted", "freemium")
        # restricted(1) vs freemium(4): verified easier → no change
        assert score == 0.3 and caveat is None

    def test_unknown_verified_noop(self):
        assert _recon_data(0.9, "public", None) == (0.9, "public", None)
