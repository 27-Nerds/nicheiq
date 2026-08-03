"""Realism score-calibration critic (Stage 7, post-refinement).

Exercises `_calibrate_idea_scores` via a SimpleNamespace 'self' (avoids heavy __init__),
mirroring the merged-feasibility-critic test harness. Covers: the 5-field replace + raw
preservation, checkpoint round-trip, flag/abstain no-ops, the name allow-list, fail-open,
clamping, parallel batching, novelty↔obviousness consistency (→ Originality), and the
downstream feasibility-composite coupling when technical_feasibility is lowered.
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
import nicheiq.utils.llm_service as ls
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.idea_tags import _novelty_level
from nicheiq.utils.llm_service import LLMService, LLMSystemicError
from nicheiq.utils.score_helpers import feasibility_adjusted_composite


def _idea(name="A", **kw):
    base = dict(
        solution_name=name, description="d" * 30, value_proposition="v",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        market_fit_score=0.9, technical_feasibility_score=0.9, novelty_score=0.8,
        seo_scalability_score=0.8, obviousness_score=0.2,
    )
    base.update(kw)
    return BaseSolutionIdea(**base)


def _cal(name, **kw):
    return usc._ScoreCalibration(name=name, **kw)


def _crit_self(pain_points=None):
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing tool",
        pain_point_analysis=SimpleNamespace(pain_points=pain_points or []),
        _record_divergent_usage=lambda u: None,
    )
    fake._run_parallel = usc.UnifiedSolutionCrew._run_parallel.__get__(fake)
    fake._calibration_static_prompt = usc.UnifiedSolutionCrew._calibration_static_prompt.__get__(fake)
    fake._calibrate_batch = usc.UnifiedSolutionCrew._calibrate_batch.__get__(fake)
    fake._calibrate_idea_scores = usc.UnifiedSolutionCrew._calibrate_idea_scores.__get__(fake)
    return fake


def _run(monkeypatch, ideas, calibrations, *, flag=True, pain_points=None, fail=False):
    monkeypatch.setattr(usc.settings, "enable_score_calibration", flag)
    if fail:
        def _boom(**kw):
            raise RuntimeError("LLM down")
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_boom))
    else:
        result = usc._ScoreCalibrations(calibrations=calibrations)
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (result, SimpleNamespace())),
        )
    _crit_self(pain_points)._calibrate_idea_scores(ideas)
    return ideas


class TestReplaceAndProvenance:
    def test_replaces_five_fields_and_preserves_raw(self, monkeypatch):
        idea = _idea()
        _run(monkeypatch, [idea], [_cal(
            "A",
            market_fit_score=0.5, market_fit_reason="thin pain",
            technical_feasibility_score=0.55, technical_feasibility_reason="needs custom infra",
            novelty_score=0.4, novelty_reason="minor twist",
            seo_scalability_score=0.3, seo_scalability_reason="no corpus",
            obviousness_score=0.6, obviousness_reason="me-too",
        )])
        assert (idea.market_fit_score, idea.technical_feasibility_score, idea.novelty_score,
                idea.seo_scalability_score, idea.obviousness_score) == (0.5, 0.55, 0.4, 0.3, 0.6)
        # originals preserved
        assert idea.market_fit_score_raw == 0.9
        assert idea.technical_feasibility_score_raw == 0.9
        assert idea.novelty_score_raw == 0.8
        assert idea.seo_scalability_score_raw == 0.8
        assert idea.obviousness_score_raw == 0.2
        assert idea.calibration_notes and "market_fit" in idea.calibration_notes

    def test_rescores_solo_dev_and_preserves_raw(self, monkeypatch):
        # solo_dev_feasibility is now part of the re-grade (ops-burden-weighted second opinion);
        # the idea field name differs from the critic field, so this guards the mapping.
        idea = _idea(solo_dev_feasibility=0.9)
        _run(monkeypatch, [idea], [_cal(
            "A", solo_dev_feasibility_score=0.45,
            solo_dev_feasibility_reason="needs 24/7 moderation",
        )])
        assert idea.solo_dev_feasibility == 0.45
        assert idea.solo_dev_feasibility_raw == 0.9
        assert "solo_dev_feasibility" in (idea.calibration_notes or "")

    def test_solo_dev_abstain_keeps_generator_value(self, monkeypatch):
        idea = _idea(solo_dev_feasibility=0.85)
        _run(monkeypatch, [idea], [_cal("A", market_fit_score=0.4, market_fit_reason="x")])
        assert idea.solo_dev_feasibility == 0.85 and idea.solo_dev_feasibility_raw is None

    def test_raw_survives_checkpoint_round_trip(self, monkeypatch):
        idea = _idea()
        _run(monkeypatch, [idea], [_cal("A", market_fit_score=0.4, market_fit_reason="x")])
        # extra='ignore' would DROP undeclared extras — declared *_raw fields must round-trip.
        reloaded = BaseSolutionIdea.model_validate(idea.model_dump())
        assert reloaded.market_fit_score == 0.4
        assert reloaded.market_fit_score_raw == 0.9
        assert reloaded.calibration_notes == idea.calibration_notes

    def test_clamps_out_of_range(self, monkeypatch):
        idea = _idea()
        _run(monkeypatch, [idea], [_cal("A", market_fit_score=1.5, market_fit_reason="x")])
        assert idea.market_fit_score == 1.0


class TestNoOps:
    def test_abstain_keeps_generator_value(self, monkeypatch):
        idea = _idea()
        # all -1.0 sentinels => critic abstains on every criterion
        _run(monkeypatch, [idea], [_cal("A")])
        assert idea.market_fit_score == 0.9 and idea.market_fit_score_raw is None
        assert idea.obviousness_score == 0.2 and idea.obviousness_score_raw is None

    def test_flag_off_is_noop(self, monkeypatch):
        idea = _idea()
        _run(monkeypatch, [idea], [_cal("A", market_fit_score=0.1, market_fit_reason="x")],
             flag=False)
        assert idea.market_fit_score == 0.9 and idea.market_fit_score_raw is None

    def test_fail_open_keeps_raw_scores(self, monkeypatch):
        idea = _idea()
        _run(monkeypatch, [idea], [], fail=True)  # invoke_structured raises
        assert idea.market_fit_score == 0.9 and idea.market_fit_score_raw is None


class TestAllowList:
    def test_hallucinated_name_ignored_real_name_applied(self, monkeypatch):
        idea = _idea("Real")
        _run(monkeypatch, [idea], [
            _cal("GHOST", market_fit_score=0.01, market_fit_reason="injected"),
            _cal("Real", market_fit_score=0.5, market_fit_reason="ok"),
        ])
        assert idea.market_fit_score == 0.5  # the ghost calibration never touched it


class TestConsistencyAndParallel:
    def test_novelty_obviousness_consistency_drives_originality(self, monkeypatch):
        # Critic sets BOTH fields directly and coherently: original idea -> high novelty + low obv.
        idea = _idea("Orig", novelty_score=0.3, obviousness_score=0.7)
        _run(monkeypatch, [idea], [_cal(
            "Orig", novelty_score=0.8, novelty_reason="new mechanism",
            obviousness_score=0.25, obviousness_reason="few would propose",
        )])
        assert idea.novelty_score == 0.8 and idea.obviousness_score == 0.25
        # Originality (= 1 - obviousness) bucket reflects the post-refinement re-score.
        assert _novelty_level(idea) == "novel"

    def test_parallel_batches_cover_all_ideas(self, monkeypatch):
        # > _CRITIC_BATCH ideas => multiple batches run via _run_parallel; all get re-scored.
        n = usc._CRITIC_BATCH + 3
        ideas = [_idea(f"I{i}") for i in range(n)]
        cals = [_cal(f"I{i}", market_fit_score=0.42, market_fit_reason="r") for i in range(n)]
        _run(monkeypatch, ideas, cals)
        assert all(i.market_fit_score == 0.42 for i in ideas)
        assert all(i.market_fit_score_raw == 0.9 for i in ideas)


class TestDownstreamFeasibilityCoupling:
    def test_lowering_technical_shrinks_the_composite_drop(self, monkeypatch):
        # The composite drop term is (technical - build)/n. Calibrating technical DOWN (but still
        # above build) yields a SMALLER drop than the raw optimistic technical would. build < cal < raw.
        build, cal_tech, raw_tech = 0.5, 0.7, 0.9
        comp = 0.80
        adj_cal = feasibility_adjusted_composite(comp, 0.6, cal_tech, 0.6, 0.6, build)
        adj_raw = feasibility_adjusted_composite(comp, 0.6, raw_tech, 0.6, 0.6, build)
        assert adj_cal > adj_raw  # calibrated technical => smaller downgrade
        assert adj_cal < comp     # but build < calibrated technical still triggers a drop


class TestRouteReconcileFold:
    """4.4 — _median_calibrations folds market_fit_claimed_route: case-insensitive modal,
    FIRST-WINS on ties (at samples=3 free text every count is 1 => first sample wins)."""

    def _maps(self, routes):
        return [{"a": _cal("a", market_fit_score=0.5, market_fit_reason="r",
                           market_fit_claimed_route=rt)} for rt in routes]

    def test_samples3_free_text_degenerates_to_first_wins(self):
        out = usc._median_calibrations(
            self._maps(["DOT/NWS APIs", "OSM Overpass", "FAA registry"]))
        assert out["a"].market_fit_claimed_route == "DOT/NWS APIs"

    def test_case_insensitive_modal_beats_first(self):
        out = usc._median_calibrations(self._maps(["DOT API", "osm overpass", "OSM Overpass"]))
        assert out["a"].market_fit_claimed_route == "osm overpass"  # count 2, first casing kept

    def test_all_empty_routes_fold_to_none(self):
        out = usc._median_calibrations(self._maps([None, "", "   "]))
        assert out["a"].market_fit_claimed_route is None


def _run_capture(monkeypatch, ideas, calibrations, *, flag=True, reconcile=True):
    """Like _run but returns the fake crew-self so coverage_caveats can be asserted."""
    monkeypatch.setattr(usc.settings, "enable_score_calibration", flag)
    monkeypatch.setattr(usc.settings, "score_calibration_route_reconcile", reconcile)
    result = usc._ScoreCalibrations(calibrations=calibrations)
    monkeypatch.setattr(
        usc.LLMService, "invoke_structured",
        staticmethod(lambda **kw: (result, SimpleNamespace())),
    )
    fake = _crit_self()
    fake._calibrate_idea_scores(ideas)
    return fake


class TestRouteReconcileAnnotation:
    """4.4 — single-branch honesty rule: claimed route + unverified/blocked/restricted dam
    => '(route not confirmed: ...)' suffix on the market_fit note + a coverage caveat.
    Never mutates scores."""

    def _cal_with_route(self, route, mf=0.5):
        return _cal("A", market_fit_score=mf, market_fit_reason="leans on the route",
                    market_fit_claimed_route=route)

    def test_fires_for_audited_dot_nws_case(self, monkeypatch):
        # The audited run: critic cites "DOT/NWS APIs" (matches nothing on the allowlist),
        # verifier left dam unverified => annotate + caveat.
        idea = _idea(data_access_model="unverified")
        fake = _run_capture(monkeypatch, [idea], [self._cal_with_route("DOT/NWS APIs")])
        assert idea.market_fit_claimed_route == "DOT/NWS APIs"
        assert "route not confirmed" in idea.calibration_notes
        assert "access model: unverified" in idea.calibration_notes
        caveats = getattr(fake, "coverage_caveats", [])
        assert any('"DOT/NWS APIs"' in c and '"A"' in c for c in caveats)

    def test_no_route_claimed_is_noop(self, monkeypatch):
        idea = _idea(data_access_model="unverified")
        fake = _run_capture(monkeypatch, [idea],
                            [_cal("A", market_fit_score=0.5, market_fit_reason="x")])
        assert idea.market_fit_claimed_route is None
        assert "route not confirmed" not in (idea.calibration_notes or "")
        assert not getattr(fake, "coverage_caveats", [])

    def test_public_dam_stamps_route_without_annotation(self, monkeypatch):
        idea = _idea(data_access_model="public")
        fake = _run_capture(monkeypatch, [idea], [self._cal_with_route("OSM Overpass")])
        assert idea.market_fit_claimed_route == "OSM Overpass"
        assert "route not confirmed" not in (idea.calibration_notes or "")
        assert not getattr(fake, "coverage_caveats", [])

    def test_abstained_market_fit_loses_route_fail_open(self, monkeypatch):
        # Documented fail-open: abstained re-score (score -1) never reaches the reconcile
        # block => the route is silently dropped for that idea (no false annotation).
        idea = _idea(data_access_model="unverified")
        fake = _run_capture(monkeypatch, [idea], [
            _cal("A", market_fit_score=-1.0, novelty_score=0.4, novelty_reason="n",
                 market_fit_claimed_route="DOT/NWS APIs")])
        assert idea.market_fit_claimed_route is None
        assert "route not confirmed" not in (idea.calibration_notes or "")
        assert not getattr(fake, "coverage_caveats", [])

    def test_flag_off_disables_stamp_and_annotation(self, monkeypatch):
        idea = _idea(data_access_model="unverified")
        fake = _run_capture(monkeypatch, [idea], [self._cal_with_route("DOT/NWS APIs")],
                            reconcile=False)
        assert idea.market_fit_claimed_route is None
        assert "route not confirmed" not in (idea.calibration_notes or "")
        assert not getattr(fake, "coverage_caveats", [])

    def test_annotation_never_mutates_scores(self, monkeypatch):
        idea = _idea(data_access_model="unverified")
        _run_capture(monkeypatch, [idea], [self._cal_with_route("DOT/NWS APIs", mf=0.5)])
        assert idea.market_fit_score == 0.5  # exactly the critic's re-score, nothing more
        assert idea.market_fit_score_raw == 0.9

    def test_reset_clears_generator_fabrication_on_missed_idea(self, monkeypatch):
        # Reset-then-stamp: the reset sits ABOVE the c-is-None continue, so an idea the
        # critic returned nothing for still loses its fabricated route.
        idea = _idea("Missed", market_fit_claimed_route="fabricated route")
        _run_capture(monkeypatch, [idea],
                     [_cal("Other", market_fit_score=0.5, market_fit_reason="x")])
        assert idea.market_fit_claimed_route is None


class TestFinalizePoolRouteReset:
    """4.4 — guarded reset in _finalize_idea_pool: never-calibrated ideas (no *_score_raw on
    the same five-criterion tuple _calibrate_idea_scores uses) lose the route; in-cell
    calibrated stamps survive."""

    def _pool(self, ideas):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew._finalize_idea_pool(ideas)
        return ideas

    def test_in_cell_stamp_survives(self):
        idea = _idea(data_access_model="public",
                     market_fit_claimed_route="DOT/NWS APIs")
        idea.market_fit_score_raw = 0.9  # in-cell calibration evidence
        self._pool([idea])
        assert idea.market_fit_claimed_route == "DOT/NWS APIs"

    def test_never_calibrated_fabrication_cleared(self):
        idea = _idea(data_access_model="public",
                     market_fit_claimed_route="fabricated by generator")
        assert all(getattr(idea, f"{c}_score_raw", None) is None
                   for c in ("market_fit", "technical_feasibility", "novelty",
                             "seo_scalability", "obviousness"))
        self._pool([idea])
        assert idea.market_fit_claimed_route is None

    def test_any_single_raw_counts_as_calibrated(self):
        idea = _idea(data_access_model="public", market_fit_claimed_route="OSM Overpass")
        idea.obviousness_score_raw = 0.2  # partial in-cell calibration still counts
        self._pool([idea])
        assert idea.market_fit_claimed_route == "OSM Overpass"


class TestComplementCollapseCaveat:
    """4.6 — set-level novelty/obviousness complement-collapse methodology note."""

    _NOTE = ("Novelty/obviousness collapsed to exact complements this run — treat the "
             "two originality axes as one signal.")

    def _crew(self):
        crew = usc.UnifiedSolutionCrew.__new__(usc.UnifiedSolutionCrew)
        crew.coverage_caveats = []
        return crew

    def _pool_idea(self, name, nov, obv):
        return SimpleNamespace(
            solution_name=name, novelty_score=nov, obviousness_score=obv,
            market_fit_score=0.5, data_access_model="public",
            build_feasibility_score=0.9, solo_dev_feasibility=0.5,
            source_pain=f"pain {name}", winning_angle=None,
        )

    def test_fires_when_80pct_of_pool_collapses(self):
        crew = self._crew()
        ideas = [self._pool_idea(f"I{i}", 0.6, 0.4) for i in range(4)] + \
                [self._pool_idea("I4", 0.7, 0.2)]
        crew._validate_idea_scores(ideas)
        assert self._NOTE in crew.coverage_caveats

    def test_silent_below_80pct(self):
        crew = self._crew()
        ideas = [self._pool_idea(f"I{i}", 0.6, 0.4) for i in range(3)] + \
                [self._pool_idea("I3", 0.7, 0.2), self._pool_idea("I4", 0.8, 0.1)]
        crew._validate_idea_scores(ideas)
        assert self._NOTE not in crew.coverage_caveats

    def test_silent_below_5_idea_pool(self):
        crew = self._crew()
        ideas = [self._pool_idea(f"I{i}", 0.6, 0.4) for i in range(4)]
        crew._validate_idea_scores(ideas)
        assert self._NOTE not in crew.coverage_caveats

    def test_rule_a_capped_ideas_excluded(self):
        # Rule (a) forces novelty = 1 - obviousness EXACTLY on the ideas it caps — counting
        # them would let the cap manufacture the finding. 5 capped ideas + 1 clean
        # non-complement => post-exclusion pool of 1 => no note.
        crew = self._crew()
        capped = [self._pool_idea(f"C{i}", 0.9, 0.6) for i in range(5)]  # 0.9 > 0.4+0.25
        clean = [self._pool_idea("Clean", 0.7, 0.2)]
        crew._validate_idea_scores(capped + clean)
        assert all(i.novelty_score == 0.4 for i in capped)  # rule (a) fired => exact complement
        assert self._NOTE not in crew.coverage_caveats


class TestFailureIsNeverSilent:
    """A calibration failure must never end in a normal-looking pool. These scores are
    score-bearing (ranking, caps, verdict floors all read them), so an idea that misses the
    critic silently ships the generator's own optimistic self-score — measured live
    2026-08-03 at market_fit +0.227 vs the Opus benchmark, 38/67 "Go" where the reference
    gives 2. SYSTEMIC provider failures (402/401) halt; transient ones stay fail-open but are
    named in coverage_caveats."""

    @pytest.fixture(autouse=True)
    def _clean_breaker(self):
        LLMService.reset_systemic()
        yield
        LLMService.reset_systemic()

    @staticmethod
    def _402(**_kw):
        """Reproduces the live shape: the 402 trips the module breaker, then propagates."""
        exc = RuntimeError("Error code: 402 - This request requires more credits")
        exc.status_code = 402
        ls._detect_systemic(exc)
        raise exc

    def test_systemic_failure_raises_instead_of_shipping_self_scores(self, monkeypatch):
        monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(self._402))
        idea = _idea()
        with pytest.raises(LLMSystemicError):
            _crit_self()._calibrate_idea_scores([idea])
        # The self-score survived un-replaced — which is exactly why the run must fail.
        assert idea.market_fit_score == 0.9 and idea.market_fit_score_raw is None

    def test_partial_systemic_failure_never_ships_a_mixed_pool(self, monkeypatch):
        """The messiest case: one batch calibrated, one killed by the breaker."""
        monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
        monkeypatch.setattr(usc, "_CRITIC_BATCH", 1)  # one idea per batch
        ok = usc._ScoreCalibrations(calibrations=[
            _cal("Alpha", market_fit_score=0.3, market_fit_reason="thin pain")])

        def _half(**kw):
            if "Bravo" in kw.get("prompt", ""):
                return self._402(**kw)
            return (ok, SimpleNamespace())

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_half))
        alpha, bravo = _idea("Alpha"), _idea("Bravo")
        with pytest.raises(LLMSystemicError):
            _crit_self()._calibrate_idea_scores([alpha, bravo])
        assert alpha.market_fit_score == 0.3      # calibrated
        assert bravo.market_fit_score == 0.9      # never calibrated -> pool is mixed
        assert bravo.market_fit_score_raw is None

    def test_transient_failure_names_the_uncalibrated_ideas(self, monkeypatch):
        """Non-systemic: keep the fail-open, but the caveat ledger must say so."""
        monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
        monkeypatch.setattr(usc, "_CRITIC_BATCH", 1)
        ok = usc._ScoreCalibrations(calibrations=[
            _cal("Alpha", market_fit_score=0.3, market_fit_reason="thin pain")])

        def _half(**kw):
            if "Bravo" in kw.get("prompt", ""):
                raise RuntimeError("read timeout")
            return (ok, SimpleNamespace())

        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_half))
        crew = _crit_self()
        alpha, bravo = _idea("Alpha"), _idea("Bravo")
        crew._calibrate_idea_scores([alpha, bravo])   # fail-open: no raise
        assert alpha.market_fit_score == 0.3 and bravo.market_fit_score == 0.9
        caveats = getattr(crew, "coverage_caveats", None) or []
        assert any("1 of 2" in c and "self-assessed scores" in c for c in caveats)

    def test_full_success_adds_no_caveat(self, monkeypatch):
        crew = _crit_self()
        monkeypatch.setattr(usc.settings, "enable_score_calibration", True)
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (usc._ScoreCalibrations(calibrations=[
                _cal("Alpha", market_fit_score=0.3, market_fit_reason="thin pain")]),
                SimpleNamespace())),
        )
        crew._calibrate_idea_scores([_idea("Alpha")])
        assert not (getattr(crew, "coverage_caveats", None) or [])

    def test_pipeline_call_site_does_not_swallow_the_halt(self):
        """execute_pipeline's fail-soft wrapper must let LLMSystemicError through."""
        import inspect

        src = inspect.getsource(usc.UnifiedSolutionCrew.execute_pipeline)
        block = src[src.index("_calibrate_idea_scores("):]
        assert block.index("except LLMSystemicError:") < block.index("Score calibration skipped")
