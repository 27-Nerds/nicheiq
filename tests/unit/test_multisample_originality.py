"""Phase-2 originality overhaul: pool dedup, novelty critic, bold slot, interpolation.

Methods are exercised by binding them to a lightweight fake `self` (SimpleNamespace),
avoiding the heavy UnifiedSolutionCrew.__init__.
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.crews import unified_solution_crew as M
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew, _interpolate_template
from nicheiq.models.solution_idea import BaseSolutionIdea, RawConcept


def _rc(name, obv=-1.0, m="m", d="d", j="j", tech="niche_drilling"):
    return RawConcept(
        concept_name=name,
        one_liner=f"{name} does a specific non-obvious thing for the niche audience.",
        ideation_technique=tech,
        project_type="saas",
        target_keywords=["kw one", "kw two"],
        why_non_obvious=f"{name} rests on Insight 2 and a real data wedge that incumbents lack here.",
        mechanism_tag=m, data_source_tag=d, journey_tag=j,
        obviousness_score=obv,
    )


def _idea(name, novelty=None):
    return BaseSolutionIdea(
        solution_name=name, description="d" * 40, value_proposition="v",
        pain_points_addressed=["p"], core_features=["f"], target_personas=["t"],
        market_fit_score=0.7, technical_feasibility_score=0.7, novelty_score=novelty,
    )


def _pain(title, sev=0.8):
    return SimpleNamespace(title=title, severity_score=sev, mention_count=5, categories=[])


# ── interpolation brace safety ──────────────────────────────────────────────

def test_interpolate_preserves_json_and_unknown():
    out = _interpolate_template('Hi {name}, {"k": "v"} {missing}', {"name": "X"})
    assert out == 'Hi X, {"k": "v"} {missing}'


def test_synthesized_idea_carries_obviousness():
    """Re-injected (stub) ideas must carry the obviousness signal for the Originality UI."""
    from nicheiq.utils.validation.crew_guardrails import _synthesize_idea_from_concept
    idea = _synthesize_idea_from_concept(_rc("X", obv=0.27), _pain("p"))
    assert idea.obviousness_score == 0.27
    # sentinel -1.0 -> None (not carried)
    idea2 = _synthesize_idea_from_concept(_rc("Y", obv=-1.0), _pain("p"))
    assert idea2.obviousness_score is None


# ── pool dedup ──────────────────────────────────────────────────────────────

def test_pool_dedup_name_keeps_lower_obviousness():
    fake = SimpleNamespace()
    concepts = [_rc("Same Idea", obv=0.6), _rc("SameIdea", obv=0.2)]  # normalized-name collision
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == 1
    assert out[0].obviousness_score == 0.2  # kept the more-novel one


def test_pool_dedup_structural_floor_guard():
    fake = SimpleNamespace()
    # 8 concepts all sharing M/D/J -> structural dups, but floor (6) must be preserved.
    concepts = [_rc(f"Idea{i}", obv=0.3 + i * 0.05) for i in range(8)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) >= 6  # not collapsed below floor despite structural collisions


def test_pool_dedup_clamps_to_cap():
    fake = SimpleNamespace()
    # distinct names + distinct tags -> no dedup; should clamp to divergent_pool_cap (12)
    concepts = [_rc(f"Idea{i}", obv=0.2, m=f"m{i}", d=f"d{i}", j=f"j{i}") for i in range(20)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == M.settings.divergent_pool_cap


def test_pool_dedup_sentinel_not_treated_as_most_novel():
    fake = SimpleNamespace()
    concepts = [_rc("Scored", obv=0.2, m="m1", d="d1", j="j1"),
                _rc("Unscored", obv=-1.0, m="m2", d="d2", j="j2")]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    # most-novel-first ordering: the genuinely-scored 0.2 must rank before the -1.0 sentinel
    assert out[0].concept_name == "Scored"


# ── novelty critic ──────────────────────────────────────────────────────────

def _critic_self():
    return SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: a known existing tool",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    )


def test_critic_overwrites_and_drops_existing():
    fake = _critic_self()
    concepts = [_rc("NovelOne", obv=0.4), _rc("ExistingTool", obv=0.4)]
    verdicts = M._NoveltyVerdicts(verdicts=[
        M._NoveltyVerdict(name="NovelOne", independent_obviousness=0.15, already_exists=False),
        M._NoveltyVerdict(name="ExistingTool", independent_obviousness=0.9, already_exists=True),
    ])
    with patch.object(M.LLMService, "invoke_structured", return_value=(verdicts, SimpleNamespace())):
        out = UnifiedSolutionCrew._score_pool_novelty(fake, concepts)
    names = [c.concept_name for c in out]
    assert "ExistingTool" not in names and "NovelOne" in names
    assert out[0].obviousness_score == 0.15  # overwritten by the independent critic


def test_critic_fail_open_on_error():
    fake = _critic_self()
    concepts = [_rc("A"), _rc("B")]
    with patch.object(M.LLMService, "invoke_structured", side_effect=RuntimeError("boom")):
        out = UnifiedSolutionCrew._score_pool_novelty(fake, concepts)
    assert len(out) == 2  # unchanged, never drops everything


def test_critic_noop_when_no_reality_anchor():
    fake = SimpleNamespace(
        _format_competitor_mentions=lambda: "",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    )
    concepts = [_rc("A"), _rc("B")]
    out = UnifiedSolutionCrew._score_pool_novelty(fake, concepts)
    assert out == concepts  # advisory skip, no call


# ── bold slot ───────────────────────────────────────────────────────────────

def _bold_self(pains):
    # _refine_single_concept is stubbed to return a COMPLETE idea (no real LLM call);
    # mirrors production where the boldest concept is fully refined, not a stub.
    def _refine(concept, pain):
        idea = _idea(concept.concept_name, novelty=0.55)
        idea.technical_approach = "approach"
        idea.why_it_works = "w" * 40
        idea.innovation_angle = "i" * 40
        idea.conventional_approach = "c" * 40
        return idea
    return SimpleNamespace(
        _BOLD_NOVELTY=UnifiedSolutionCrew._BOLD_NOVELTY,
        _BOLD_OBVIOUSNESS=UnifiedSolutionCrew._BOLD_OBVIOUSNESS,
        pain_point_analysis=SimpleNamespace(pain_points=pains),
        coverage_caveats=[],
        _refine_single_concept=_refine,
    )


def test_bold_slot_reinjects_when_all_safe():
    pains = [_pain("Sourcing safe peptides", 0.85)]
    raw = SimpleNamespace(concepts=[
        _rc("SafeIdea", obv=0.7), _rc("BoldIdea", obv=0.15),
    ])
    final = [_idea("SafeIdea", novelty=0.4)]  # only safe idea present
    fake = _bold_self(pains)
    UnifiedSolutionCrew._enforce_bold_slot(fake, final, raw)
    names = [i.solution_name for i in final]
    assert "BoldIdea" in names
    bold = next(i for i in final if i.solution_name == "BoldIdea")
    assert bold.novelty_score >= 0.6  # floored since it's the boldest concept
    # Fully refined (not a stub): narrative fields populated.
    assert len(bold.innovation_angle or "") >= 30 and len(bold.why_it_works or "") >= 30
    assert any("Bold slot" in c for c in fake.coverage_caveats)


def test_bold_slot_noop_when_low_obviousness_present():
    pains = [_pain("X", 0.8)]
    raw = SimpleNamespace(concepts=[_rc("AlreadyBold", obv=0.2)])
    final = [_idea("AlreadyBold", novelty=0.4)]  # traces to obviousness 0.2 -> bold already
    fake = _bold_self(pains)
    UnifiedSolutionCrew._enforce_bold_slot(fake, final, raw)
    assert len(final) == 1  # no re-injection


def test_bold_slot_noop_when_high_novelty_present():
    pains = [_pain("X", 0.8)]
    raw = SimpleNamespace(concepts=[_rc("WhateverSrc", obv=0.9)])
    final = [_idea("Whatever", novelty=0.7)]  # high novelty already
    fake = _bold_self(pains)
    UnifiedSolutionCrew._enforce_bold_slot(fake, final, raw)
    assert len(final) == 1


def test_bold_slot_sentinel_concept_ineligible():
    pains = [_pain("X", 0.8)]
    raw = SimpleNamespace(concepts=[_rc("OnlyUnscored", obv=-1.0)])  # sentinel only
    final = [_idea("Safe", novelty=0.3)]
    fake = _bold_self(pains)
    UnifiedSolutionCrew._enforce_bold_slot(fake, final, raw)
    assert len(final) == 1  # no eligible (scored) concept to re-inject


# ── convergent crew assembly (regression: must not rely on @crew's self.agents) ──

def test_convergent_crew_builds_with_explicit_agents():
    from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult
    pp = PainPoint(
        title="Sourcing", description="hard", severity_score=0.8,
        willingness_to_pay=0.5, mention_count=5, representative_quotes=["q"],
        opportunity_level="medium",
    )
    ppa = PainPointAnalysisResult(
        niche="x", pain_points=[pp], total_mentions=5, analysis_summary="s",
        top_categories=["c"],
    )
    crew = UnifiedSolutionCrew(pain_point_analysis=ppa, allowed_project_types=["saas", "aggregator"])
    c_skip = crew._convergent_crew(skip_selection=True)
    assert len(c_skip.tasks) == 2 and len(c_skip.agents) == 2
    c_full = crew._convergent_crew(skip_selection=False)
    assert len(c_full.tasks) == 3 and len(c_full.agents) == 3
