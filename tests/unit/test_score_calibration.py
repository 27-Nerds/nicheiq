"""Realism score-calibration critic (Stage 7, post-refinement).

Exercises `_calibrate_idea_scores` via a SimpleNamespace 'self' (avoids heavy __init__),
mirroring the merged-feasibility-critic test harness. Covers: the 5-field replace + raw
preservation, checkpoint round-trip, flag/abstain no-ops, the name allow-list, fail-open,
clamping, parallel batching, novelty↔obviousness consistency (→ Originality), and the
downstream feasibility-composite coupling when technical_feasibility is lowered.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.models.solution_idea import BaseSolutionIdea
from nicheiq.utils.idea_tags import _novelty_level
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
        monkeypatch.setattr(usc.settings, "enable_feasibility_critic", True)
        from nicheiq.config.settings import settings as live
        monkeypatch.setattr(live, "enable_feasibility_critic", True)
        build, cal_tech, raw_tech = 0.5, 0.7, 0.9
        comp = 0.80
        adj_cal = feasibility_adjusted_composite(comp, 0.6, cal_tech, 0.6, 0.6, build)
        adj_raw = feasibility_adjusted_composite(comp, 0.6, raw_tech, 0.6, 0.6, build)
        assert adj_cal > adj_raw  # calibrated technical => smaller downgrade
        assert adj_cal < comp     # but build < calibrated technical still triggers a drop
