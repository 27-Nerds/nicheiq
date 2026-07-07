"""Phase-2 originality overhaul: pool dedup, novelty critic, interpolation.

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
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    concepts = [_rc("Same Idea", obv=0.6), _rc("SameIdea", obv=0.2)]  # normalized-name collision
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == 1
    assert out[0].obviousness_score == 0.2  # kept the more-novel one


def test_pool_dedup_structural_floor_guard():
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    # 8 concepts all sharing M/D/J -> structural dups, but floor (6) must be preserved.
    concepts = [_rc(f"Idea{i}", obv=0.3 + i * 0.05) for i in range(8)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) >= 6  # not collapsed below floor despite structural collisions


def test_pool_dedup_keeps_half_of_generated():
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    # 20 distinct generated, keep_fraction 0.5 -> keep 10 (under the cap ceiling)
    concepts = [_rc(f"Idea{i}", obv=0.2, m=f"m{i}", d=f"d{i}", j=f"j{i}") for i in range(20)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == 10


def test_pool_dedup_clamps_to_cap_ceiling():
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    # 40 distinct generated, half=20 -> bounded by divergent_pool_cap (15)
    concepts = [_rc(f"Idea{i}", obv=0.2, m=f"m{i}", d=f"d{i}", j=f"j{i}") for i in range(40)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == M.settings.divergent_pool_cap


def test_pool_dedup_floor_when_few_generated():
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    # Single-model style: only 8 generated. half=4 but floor (6) keeps it from going too low.
    concepts = [_rc(f"Idea{i}", obv=0.2, m=f"m{i}", d=f"d{i}", j=f"j{i}") for i in range(8)]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    assert len(out) == 6  # floored at MIN_KEEP, not 4


def test_pool_dedup_sentinel_not_treated_as_most_novel():
    fake = SimpleNamespace(_semantic_dedup=lambda concepts, threshold: concepts)
    concepts = [_rc("Scored", obv=0.2, m="m1", d="d1", j="j1"),
                _rc("Unscored", obv=-1.0, m="m2", d="d2", j="j2")]
    out = UnifiedSolutionCrew._pool_and_dedup_raw_concepts(fake, concepts)
    # most-novel-first ordering: the genuinely-scored 0.2 must rank before the -1.0 sentinel
    assert out[0].concept_name == "Scored"


# ── novelty critic ──────────────────────────────────────────────────────────

def _bind_critic(fake):
    # The _score_pool_novelty wrapper now dispatches to _score_concepts + _finalize_critic_pool;
    # bind both onto the SimpleNamespace stub so the unbound-call pattern still works.
    fake._score_concepts = UnifiedSolutionCrew._score_concepts.__get__(fake)
    fake._finalize_critic_pool = UnifiedSolutionCrew._finalize_critic_pool.__get__(fake)
    return fake


def _critic_self():
    return _bind_critic(SimpleNamespace(
        _format_competitor_mentions=lambda: "ToolX: a known existing tool",
        audience_mapping=None,
        _record_divergent_usage=lambda u: None,
    ))


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


# ── convergent crew assembly (regression: must not rely on @crew's self.agents) ──

def test_convergent_crew_builds_with_explicit_agents():
    from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult
    pp = PainPoint(
        title="Sourcing", description="hard", severity_score=0.8,
        commercial_intent=0.5, mention_count=5, representative_quotes=["q"],
        opportunity_level="medium",
    )
    ppa = PainPointAnalysisResult(
        niche="x", pain_points=[pp], total_mentions=5, analysis_summary="s",
        top_categories=["c"],
    )
    crew = UnifiedSolutionCrew(pain_point_analysis=ppa, allowed_project_types=["saas", "aggregator"])
    # Convergent crew is refine → (select) — the LLM diversity filter was removed.
    c_skip = crew._convergent_crew(skip_selection=True)
    assert len(c_skip.tasks) == 1 and len(c_skip.agents) == 1   # refine only
    c_full = crew._convergent_crew(skip_selection=False)
    assert len(c_full.tasks) == 2 and len(c_full.agents) == 2   # refine + select
