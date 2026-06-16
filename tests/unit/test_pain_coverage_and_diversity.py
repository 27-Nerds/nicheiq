"""Phase-3 tests: post-crew pain-coverage re-injection + self-limiting diversity nudge."""

from types import SimpleNamespace

from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult, RawConcept
from nicheiq.utils.validation.crew_guardrails import (
    create_diversity_guardrail,
    enforce_pain_coverage,
)


def _raw(name, one_liner, ptype="saas", keywords=None, why=None):
    return RawConcept(
        concept_name=name,
        one_liner=one_liner,
        ideation_technique="niche_drilling",
        project_type=ptype,
        target_keywords=keywords or ["kw one", "kw two"],
        why_non_obvious=why,
        mechanism_tag="m",
        data_source_tag="d",
        journey_tag="j",
    )


def _idea(name, vp, pains, ptype="saas"):
    return BaseSolutionIdea(
        solution_name=name,
        description=f"{vp} described in detail here for the user journey.",
        value_proposition=vp,
        pain_points_addressed=pains,
        core_features=["feature one"],
        target_personas=["persona"],
        project_type=ptype,
        market_fit_score=0.7,
        technical_feasibility_score=0.7,
    )


def _pain(title, severity=0.8, mentions=10, categories=None):
    return SimpleNamespace(
        title=title, severity_score=severity, mention_count=mentions,
        categories=categories or [],
    )


# ── Coverage re-injection ───────────────────────────────────────────────────

def test_uncovered_pain_reinjects_best_concept():
    pains = [_pain("Reconstitution and dosing math confusion for injectable peptides")]
    ideas = [_idea("PlateauAtlas", "GLP-1 weight loss plateau runbooks",
                   ["Weight loss plateau on medications"])]
    concepts = [
        _raw("ReconCardBuilder",
             "Peptide reconstitution and dosing math calculator with printable vial labels",
             keywords=["peptide reconstitution", "dosing math calculator"]),
        _raw("UnrelatedThing", "something about gardening tools"),
    ]
    caveats = enforce_pain_coverage(ideas, concepts, pains)
    names = [i.solution_name for i in ideas]
    assert "ReconCardBuilder" in names  # re-injected
    assert caveats == []
    # Re-injected idea must render completely (no blank "--" cards in the UI).
    injected = next(i for i in ideas if i.solution_name == "ReconCardBuilder")
    assert injected.short_description and injected.headline
    assert injected.seo_scalability_score is not None
    assert injected.solo_dev_feasibility is not None
    assert injected.novelty_score is not None
    assert injected.market_fit_score is not None and injected.technical_feasibility_score is not None


def test_covered_pain_is_noop():
    pains = [_pain("Reconstitution and dosing math confusion")]
    ideas = [_idea("ReconCardBuilder", "Peptide reconstitution and dosing math calculator",
                   ["Reconstitution and dosing math confusion"])]
    before = len(ideas)
    caveats = enforce_pain_coverage(ideas, [_raw("X", "y")], pains)
    assert len(ideas) == before
    assert caveats == []


def test_uncovered_pain_no_concept_yields_caveat():
    pains = [_pain("Reconstitution and dosing math confusion for injectable peptides")]
    ideas = [_idea("PlateauAtlas", "GLP-1 plateau runbooks", ["other pain"])]
    concepts = [_raw("GardenTool", "completely unrelated gardening planner widget")]
    caveats = enforce_pain_coverage(ideas, concepts, pains)
    assert len(ideas) == 1  # nothing re-injected
    assert len(caveats) == 1
    assert "Reconstitution" in caveats[0]


def test_low_severity_pain_ignored():
    pains = [_pain("Minor nitpick", severity=0.3, mentions=2)]
    ideas = [_idea("Whatever", "unrelated", ["nope"])]
    caveats = enforce_pain_coverage(ideas, [_raw("X", "y")], pains)
    assert caveats == []  # not high-severity → not enforced
    assert len(ideas) == 1


# ── Self-limiting diversity nudge ───────────────────────────────────────────

def _task_output(ideas):
    result = IdeaGenerationResult(solution_ideas=ideas)
    return SimpleNamespace(pydantic=result, raw=None)


def test_project_type_nudge_fails_once_then_passes():
    guardrail = create_diversity_guardrail(["saas", "directory", "aggregator"])
    # All same project_type, all distinct value props (so similarity rule won't fire).
    ideas = [
        _idea("A", "alpha distinct value proposition", ["p1"], ptype="saas"),
        _idea("B", "beta different value proposition entirely", ["p2"], ptype="saas"),
        _idea("C", "gamma wholly unrelated value proposition", ["p3"], ptype="saas"),
    ]
    out = _task_output(ideas)
    ok1, msg1 = guardrail(out)
    assert ok1 is False
    assert "monotony" in msg1.lower()
    # Second invocation (retry exhausted): must PASS, never loop/crash.
    ok2, _ = guardrail(_task_output(ideas))
    assert ok2 is True


def test_project_type_diverse_passes_first_time():
    guardrail = create_diversity_guardrail(["saas", "directory"])
    ideas = [
        _idea("A", "alpha distinct value proposition", ["p1"], ptype="saas"),
        _idea("B", "beta different value proposition entirely", ["p2"], ptype="directory"),
        _idea("C", "gamma wholly unrelated value proposition", ["p3"], ptype="saas"),
    ]
    ok, _ = guardrail(_task_output(ideas))
    assert ok is True


def test_obviousness_score_sentinel_default_and_roundtrip():
    c = _raw("X", "y")
    assert c.obviousness_score == -1.0  # sentinel = "not scored"
    c2 = RawConcept.model_validate({**c.model_dump(), "obviousness_score": 0.2})
    assert c2.obviousness_score == 0.2
