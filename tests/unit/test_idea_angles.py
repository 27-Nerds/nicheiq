"""In-cell angle classifier (Stage 1 of angle-aware idea evaluation).

Exercises `_classify_batch` + the post-union `_classify_idea_angles` straggler-finisher via a
SimpleNamespace 'self' (avoids heavy __init__), mirroring the score-calibration test harness.
Covers: the verdict apply + user-facing rationales, the enum allow-list (off-vocabulary angle
rejected → fail-soft None), case/whitespace normalization, flag/fail-open no-ops, the name
allow-list, idempotent skip of already-classified ideas, parallel batching, and field round-trip.
"""

from types import SimpleNamespace

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaTags


def _idea(name="A", **kw):
    base = dict(
        solution_name=name, description="d" * 30, value_proposition="v",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        market_fit_score=0.7, technical_feasibility_score=0.8, novelty_score=0.4,
        seo_scalability_score=0.6, obviousness_score=0.6,
    )
    base.update(kw)
    return BaseSolutionIdea(**base)


def _verdict(name, **kw):
    return usc._AngleVerdict(name=name, **kw)


def _angle_self(pain_points=None):
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: an existing tool",
        pain_point_analysis=SimpleNamespace(pain_points=pain_points or []),
        _record_divergent_usage=lambda u: None,
    )
    fake._run_parallel = usc.UnifiedSolutionCrew._run_parallel.__get__(fake)
    fake._angle_static_prompt = usc.UnifiedSolutionCrew._angle_static_prompt.__get__(fake)
    fake._classify_batch = usc.UnifiedSolutionCrew._classify_batch.__get__(fake)
    fake._classify_idea_angles = usc.UnifiedSolutionCrew._classify_idea_angles.__get__(fake)
    return fake


def _run(monkeypatch, ideas, verdicts, *, fail=False, pain_points=None):
    if fail:
        def _boom(**kw):
            raise RuntimeError("LLM down")
        monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_boom))
    else:
        result = usc._AngleVerdicts(verdicts=verdicts)
        monkeypatch.setattr(
            usc.LLMService, "invoke_structured",
            staticmethod(lambda **kw: (result, SimpleNamespace())),
        )
    _angle_self(pain_points)._classify_idea_angles(ideas)
    return ideas


class TestApply:
    def test_sets_angle_and_user_facing_rationales(self, monkeypatch):
        idea = _idea("A", project_type="directory")
        _run(monkeypatch, [idea], [_verdict(
            "A", rival_angle="novel_differentiation",
            rival_rejected_because="mechanism is obvious",
            winning_angle="distribution_seo",
            differentiation_locus="freshness of a community-scored slice",
            angle_rationale="A distribution play — its edge is data freshness, not a clever mechanism.",
            novelty_rationale="Low mechanism-novelty is normal for a directory.",
        )])
        assert idea.winning_angle == "distribution_seo"
        assert "distribution play" in idea.angle_rationale
        assert "directory" in idea.novelty_rationale
        assert idea.differentiation_locus == "freshness of a community-scored slice"  # persisted for Stage 2

    def test_off_vocab_angle_rejected_failsoft(self, monkeypatch):
        idea = _idea("A")
        _run(monkeypatch, [idea], [_verdict(
            "A", winning_angle="seo_catalog", angle_rationale="should not apply")])
        assert idea.winning_angle is None
        assert idea.angle_rationale is None  # rationale not applied once the angle is rejected

    def test_normalizes_case_and_whitespace(self, monkeypatch):
        idea = _idea("A")
        _run(monkeypatch, [idea], [_verdict(
            "A", winning_angle="  Novel_Differentiation ", angle_rationale="m")])
        assert idea.winning_angle == "novel_differentiation"

    def test_fields_round_trip_through_model_dump(self, monkeypatch):
        idea = _idea("A")
        _run(monkeypatch, [idea], [_verdict(
            "A", winning_angle="vertical_workflow", angle_rationale="r", novelty_rationale="n")])
        reloaded = BaseSolutionIdea.model_validate(idea.model_dump())
        assert reloaded.winning_angle == "vertical_workflow"
        assert reloaded.angle_rationale == "r"
        assert reloaded.novelty_rationale == "n"

    def test_novelty_rationale_prompt_bans_numeric_citation(self):
        # scores can be re-capped/re-calibrated after the classifier writes (parity pass) —
        # a quoted number goes stale (live 2026-07-05: "0.45" cited against a final 0.7).
        prompt, _ = _angle_self()._angle_static_prompt()
        assert "NEVER" in prompt and "cite the numeric score" in prompt


class TestNoOps:
    def test_fail_open_leaves_angle_none(self, monkeypatch):
        idea = _idea("A")
        _run(monkeypatch, [idea], [], fail=True)  # invoke_structured raises
        assert idea.winning_angle is None


def test_classifier_prompt_ignores_provisional_generated_tags(monkeypatch):
    captured = {}

    def _capture(**kw):
        captured["prompt"] = kw["prompt"]
        return usc._AngleVerdicts(verdicts=[]), SimpleNamespace()

    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(_capture))
    idea = _idea("A", tags=IdeaTags(growth_channels=["network-effects"]))

    _angle_self()._classify_batch(batch=[idea])

    assert "- growth channels:" not in captured["prompt"]
    assert "network-effects" not in captured["prompt"]


class TestAllowListAndIdempotent:
    def test_hallucinated_name_ignored_real_applied(self, monkeypatch):
        idea = _idea("Real")
        _run(monkeypatch, [idea], [
            _verdict("GHOST", winning_angle="distribution_seo", angle_rationale="injected"),
            _verdict("Real", winning_angle="novel_differentiation", angle_rationale="ok"),
        ])
        assert idea.winning_angle == "novel_differentiation"

    def test_already_classified_idea_is_skipped(self, monkeypatch):
        done = _idea("Done", winning_angle="vertical_workflow", angle_rationale="orig")
        fresh = _idea("Fresh")
        _run(monkeypatch, [done, fresh], [
            _verdict("Done", winning_angle="distribution_seo", angle_rationale="must not apply"),
            _verdict("Fresh", winning_angle="novel_differentiation", angle_rationale="applied"),
        ])
        assert done.winning_angle == "vertical_workflow"  # untouched by the finisher
        assert done.angle_rationale == "orig"
        assert fresh.winning_angle == "novel_differentiation"


class TestParallel:
    def test_parallel_batches_cover_all_stragglers(self, monkeypatch):
        # > _CRITIC_BATCH ideas => multiple batches run via _run_parallel; all get classified.
        n = usc._CRITIC_BATCH + 3
        ideas = [_idea(f"I{i}") for i in range(n)]
        verdicts = [_verdict(f"I{i}", winning_angle="distribution_seo", angle_rationale="r")
                    for i in range(n)]
        _run(monkeypatch, ideas, verdicts)
        assert all(i.winning_angle == "distribution_seo" for i in ideas)


def test_rationales_sanitized_of_numeric_scores(monkeypatch):
    # Defense-in-depth beyond the prompt ban: any decimal the classifier sneaks into the
    # user-facing comments is banded deterministically at stamping time.
    idea = _idea("A")
    _run(monkeypatch, [idea], [_verdict(
        "A", winning_angle="distribution_seo",
        angle_rationale="Edge is the data slice; novelty sits at 0.45 which is fine here.",
        novelty_rationale="Low mechanism-novelty (0.45) is expected for an aggregator.",
        differentiation_locus="freshness beats rivals scoring 0.30 on updates",
    )])
    import re
    for f in (idea.angle_rationale, idea.novelty_rationale, idea.differentiation_locus):
        assert not re.search(r"\d\.\d", f), f
    assert "(limited)" in idea.novelty_rationale     # banded, not deleted
