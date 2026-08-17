"""The post-union pass sequence must leave every idea with a `winning_angle`.

Regression pinned here (live 2026-08-13 -> 2026-08-16, commit b7d9f3a): `_probe_mechanism_parity`
re-scores the pool and then CLEARS `winning_angle` + the three rationales, by design, so they can be
re-derived against the final capped scores. b7d9f3a moved a classification pass in FRONT of the probe
(so `_select_serp_probe_candidates` could read `winning_angle`) and left nothing behind it, so the
clear became terminal. Measured over `output/checkpoints/*/stage_5_3_refinement.json`, the share of
ideas shipping `winning_angle is None` went 5.0% (76 runs, pre-2026-08-13) to 84.8% (40 runs, after).

These tests drive the REAL `execute_pipeline` post-union block with only its I/O boundaries stubbed,
and assert PROPERTIES of the pool that comes out — never "call X precedes call Y", which the next
reorder would satisfy while shipping the same outage. The three properties are:

  1. every idea leaves the crew classified;
  2. the surviving label was derived from POST-parity scores (the reason the clear exists);
  3. the SERP probe still saw angles (the allow-case b7d9f3a's reorder was FOR — over-blocking it
     to fix (1) would be a different regression, not a fix).
"""

from types import SimpleNamespace

import pytest

import nicheiq.crews.unified_solution_crew as usc
from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
from nicheiq.models.research_state import NicheContext
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult, RawConcept

# Chosen so rule (a) of `_validate_idea_caps` has a VISIBLE, opposite outcome depending on whether
# `winning_angle` survived: with the distribution_seo label the coherence lock is suspended and the
# moderate SEO ceiling (0.55) applies, leaving novelty at 0.50; without it the lock caps novelty at
# 1 - obviousness = 0.10. That is the downstream damage the missing re-derivation actually does.
_GENERATOR_NOVELTY = 0.8
_POST_PARITY_NOVELTY = 0.5
_OBVIOUSNESS = 0.9
_LOCKED_NOVELTY = round(1.0 - _OBVIOUSNESS, 2)


def _concept(name: str) -> RawConcept:
    return RawConcept(
        concept_name=name,
        one_liner=f"A useful, specific workflow for {name}.",
        ideation_technique="atomic_feature",
        project_type="saas",
        target_keywords=[f"{name} software", f"{name} workflow"],
        why_non_obvious=f"{name} uses an uncommon but obtainable workflow signal.",
    )


def _idea(name: str) -> BaseSolutionIdea:
    return BaseSolutionIdea(
        solution_name=name,
        description=f"{name} gives operators a concrete workflow with auditable outcomes.",
        value_proposition=f"Resolve {name} work faster.",
        pain_points_addressed=["Test pain"],
        core_features=["Workflow", "Audit trail"],
        target_personas=["Operator"],
        technical_approach="A conventional web application backed by a relational database.",
        differentiation_factors=["Narrow workflow focus"],
        requires_data_aggregation=False,
        data_sources=[],
        estimated_development_time="4-6 weeks",
        pricing_strategy="$29 per month",
        market_fit_score=0.65,
        technical_feasibility_score=0.8,
        project_type="saas",
        programmatic_seo_opportunity=f"One landing page per {name} workflow variant.",
        content_generation_model="Template-driven pages",
        organic_discovery_queries=[f"{name} workflow", f"{name} software"],
        estimated_cac_organic="$10-20",
        estimated_cac_paid="$40-60",
        seo_scalability_score=0.55,
        novelty_score=_GENERATOR_NOVELTY,
        obviousness_score=_OBVIOUSNESS,
        conventional_approach="Teams usually coordinate this work in generic spreadsheets.",
        innovation_angle="The product owns one decision and records its supporting evidence.",
        why_it_works="The workflow is repeated often enough to support a focused product.",
        solo_dev_feasibility=0.8,
        build_feasibility_score=0.9,
        data_access_model="official",
    )


class _Recorder:
    """Everything the fake LLM/search boundaries observed, so the tests can assert on evidence."""

    def __init__(self):
        self.classify_calls: list[list[tuple[str, float | None]]] = []
        self.serp_candidates: list[list[str]] = []
        self.angles_right_after_parity: dict[str, str | None] = {}


def _wire(monkeypatch: pytest.MonkeyPatch, ideas: list[BaseSolutionIdea]) -> tuple:
    """Drive the real broad-fallback `execute_pipeline` with only I/O boundaries stubbed.

    LEFT REAL (this is the code under test): `_classify_idea_angles`, `_probe_serp_composition`,
    `_select_serp_probe_candidates`, `_probe_mechanism_parity`, `_validate_idea_caps`,
    `_validate_idea_scores`, and the post-union call sequence in `execute_pipeline` itself.
    """
    rec = _Recorder()
    pain = SimpleNamespace(
        title="Test pain",
        description="A repeated operational pain.",
        representative_quotes=["This process wastes hours every week."],
        opportunity_level=SimpleNamespace(value="high"),
        severity_score=0.8,
    )
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.pain_point_analysis = SimpleNamespace(
        pain_points=[pain], content_categorization=None, analysis_summary="Test analysis",
        top_categories=[], total_mentions=10,
    )
    crew.niche_context = NicheContext(
        niche_input="mobile dog groomers",
        niche_description="mobile dog groomers",
        market_segments=["solo groomers"],
        industry_boundaries="pet grooming services",
    )
    crew.audience_mapping = None
    crew.allowed_project_types = None
    crew.existing_ideas = []
    crew.idea_focus = "auto"
    crew.search_tool = SimpleNamespace(run=lambda search_query: "MoeGo ships route optimization")
    crew.checkpoint_mgr = None
    crew.competitor_mentions_text = ""
    crew.cost_tracker = None
    crew.user_audience_scope = None
    crew.coverage_caveats = []
    crew._incumbent_probe_text = "### Web-probed incumbent products..."
    crew._incumbent_rows = [{"name": "MoeGo", "pricing": "$50/mo",
                             "focus": "grooming scheduling and route optimization", "gap": ""}]

    import nicheiq.utils.niche_difficulty as niche_difficulty
    import nicheiq.utils.pain_point_formatters as pain_formatters
    import nicheiq.utils.validation.crew_guardrails as crew_guardrails

    monkeypatch.setattr(pain_formatters, "extract_pain_points_by_priority",
                        lambda analysis: ([pain], [], []))
    monkeypatch.setattr(pain_formatters, "select_diverse_pain_points", lambda pains: pains)
    monkeypatch.setattr(pain_formatters, "format_pain_points_for_agents", lambda **kw: "pain")
    monkeypatch.setattr(niche_difficulty, "derive_monetization_directive", lambda *a: "")
    monkeypatch.setattr(crew_guardrails, "enforce_pain_coverage", lambda *a, **kw: [])

    # --- generation front half: not under test, shortest path to a refined union ------------
    monkeypatch.setattr(UnifiedSolutionCrew, "_build_partition_cells", lambda self, *a: [])
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_audience_context", lambda self: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_regeneration_directive", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_segment_payability_map", lambda self: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_wallet_prompt_line", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_format_competitor_mentions", lambda self: "")
    monkeypatch.setattr(UnifiedSolutionCrew, "_ensure_tool_glosses", lambda self: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_generate_divergent_pool",
                        lambda self, inputs, partition_cells=None: ([], []))
    monkeypatch.setattr(UnifiedSolutionCrew, "_divergent_fallback",
                        lambda self, inputs: [_concept(f"Fallback {i}") for i in range(10)])
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_critic_pool", lambda self, c: c)
    monkeypatch.setattr(UnifiedSolutionCrew, "_pool_and_dedup_raw_concepts",
                        lambda self, c, keep_fraction=None: list(c[:6]))
    refined = IdeaGenerationResult(solution_ideas=ideas)
    monkeypatch.setattr(UnifiedSolutionCrew, "_convergent_crew", lambda self, skip: SimpleNamespace(
        usage_metrics=None,
        kickoff=lambda inputs: SimpleNamespace(
            tasks_output=[SimpleNamespace(pydantic=refined)], pydantic=None),
    ))

    # --- post-union passes that are orthogonal to angle survival ------------------------------
    for name in ("_carry_provenance", "_finalize_idea_pool", "_enforce_diversity_caps",
                 "_finalize_feasibility", "_verify_pool_routes", "_filter_pain_relevance",
                 "_finalize_dev_time", "_stamp_payability", "_probe_incumbents",
                 "_record_divergent_usage", "_emit_pipeline_progress",
                 "_finalize_evaluator_passes", "_backfill_and_demote"):
        monkeypatch.setattr(UnifiedSolutionCrew, name, lambda self, *a, **kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_probe_adjacent_markets", lambda self, top: ([], 0))
    monkeypatch.setattr(UnifiedSolutionCrew, "_probe_toolbelt_free_bundle",
                        lambda self, top: ([], 0))
    monkeypatch.setattr(UnifiedSolutionCrew, "_capability_phrases", lambda self, top: {})
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_parallel",
                        lambda self, fn, jobs, deadline, max_workers, label="P":
                        [fn(**job) for job in jobs])

    # --- LLM/search boundaries, faithful to each real method's contract -----------------------
    def _classify_batch(self, *, batch):
        """Mimics the real `_classify_batch`: reads the CURRENT scores, writes angle + rationales.

        Deterministic by name so the pool is MIXED — only "Page*" ideas earn `distribution_seo`,
        which is what makes the SERP-probe selection in property 3 a real discrimination rather
        than "everything was eligible anyway".
        """
        rec.classify_calls.append(
            [(i.solution_name, getattr(i, "novelty_score", None)) for i in batch])
        for i in batch:
            i.winning_angle = ("distribution_seo" if i.solution_name.startswith("Page")
                               else "vertical_workflow")
            i.angle_rationale = f"angle read against novelty {i.novelty_score}"
            i.novelty_rationale = f"mechanism is ordinary; novelty read as {i.novelty_score}"
            i.differentiation_locus = "page corpus"
        return (len(batch), None)

    def _calibrate_batch(self, *, batch, extra_context=""):
        """The parity re-score. Moves novelty, which is exactly what makes the old label stale."""
        for i in batch:
            i.novelty_score = _POST_PARITY_NOVELTY
            i.novelty_score_raw = _GENERATOR_NOVELTY
        return (len(batch), None)

    monkeypatch.setattr(UnifiedSolutionCrew, "_classify_batch", _classify_batch)
    monkeypatch.setattr(UnifiedSolutionCrew, "_calibrate_batch", _calibrate_batch)
    # The parity probe's only LLM call. It returns one finding per idea because a probe that
    # matches nothing returns EARLY, before the re-score/cap/clear tail these tests exercise.
    monkeypatch.setattr(usc.LLMService, "invoke_structured", staticmethod(
        lambda **kw: (SimpleNamespace(findings=[
            SimpleNamespace(idea_name=i.solution_name, covered_by="", evidence="", parity="none")
            for i in ideas]), None)))

    real_serp = UnifiedSolutionCrew._select_serp_probe_candidates

    def _spy_select(self, ideas_):
        picked = real_serp(self, ideas_)
        rec.serp_candidates.append([i.solution_name for i in picked])
        return picked

    monkeypatch.setattr(UnifiedSolutionCrew, "_select_serp_probe_candidates", _spy_select)
    monkeypatch.setattr(UnifiedSolutionCrew, "_ma_search_batch",
                        lambda self, queries, budget_exempt=False: {q: "" for q in queries})

    real_parity = UnifiedSolutionCrew._probe_mechanism_parity

    def _spy_parity(self, ideas_):
        real_parity(self, ideas_)
        rec.angles_right_after_parity = {
            i.solution_name: getattr(i, "winning_angle", None) for i in ideas_}

    monkeypatch.setattr(UnifiedSolutionCrew, "_probe_mechanism_parity", _spy_parity)

    monkeypatch.setattr(usc.settings, "enable_per_cell_tournament", True)
    monkeypatch.setattr(usc.settings, "enable_score_calibration", False)
    monkeypatch.setattr(usc.settings, "enable_direction_aware_eval", True)
    monkeypatch.setattr(usc.settings, "serp_probe_queries_per_idea", 2)
    monkeypatch.setattr(usc.settings, "serp_probe_distribution_candidate_cap", 3)
    monkeypatch.setattr(usc.settings, "divergent_max_workers", 1)
    return crew, rec


def test_every_idea_leaves_the_post_union_sequence_classified(monkeypatch):
    """PROPERTY 1: the pool the crew returns carries an angle on every idea.

    Order-agnostic on purpose. Whatever the post-union passes are and in whatever order they run,
    an idea that reaches ranking without a `winning_angle` is a shipped outage.
    """
    crew, rec = _wire(monkeypatch, [_idea(f"Idea {i}") for i in range(3)])

    result, _ = crew.execute_pipeline(skip_selection=True)

    unclassified = [i.solution_name for i in result.solution_ideas
                    if not getattr(i, "winning_angle", None)]
    assert unclassified == [], (
        f"{len(unclassified)}/{len(result.solution_ideas)} idea(s) left the post-union sequence "
        f"with winning_angle unset: {unclassified}. Something cleared the classifier outputs "
        "without re-deriving them (see the RE-DERIVATION CONTRACT on _probe_mechanism_parity)."
    )
    # ...and the clear really did happen, so the assertion above is not passing vacuously because
    # someone deleted it. The clear is load-bearing; see property 2.
    assert set(rec.angles_right_after_parity.values()) == {None}, (
        "the parity probe no longer clears the classifier outputs — it must, or the shipped "
        "rationales cite scores it just superseded")


def test_surviving_angle_is_derived_from_post_parity_scores(monkeypatch):
    """PROPERTY 2: the label + rationales that ship describe the FINAL scores, not pre-parity ones.

    This is why the clear exists, and it is what rules out the cheaper "keep the angle, clear only
    the prose" shape: `_classify_batch` feeds market_fit/novelty/seo/technical/solo_dev straight
    into the classifier prompt, so the angle is score-dependent too.
    """
    crew, rec = _wire(monkeypatch, [_idea(f"Idea {i}") for i in range(3)])

    result, _ = crew.execute_pipeline(skip_selection=True)

    for idea in result.solution_ideas:
        seen = [nov for call in rec.classify_calls for name, nov in call
                if name == idea.solution_name]
        assert seen, f"{idea.solution_name} was never classified at all"
        # The generator's own novelty was 0.8; parity re-scoring + caps moved it. If the only
        # classification happened before that, the label ships a judgment on a dead number.
        assert seen[0] == _GENERATOR_NOVELTY, "fixture drift: pass 1 should read the birth score"
        assert seen[-1] != _GENERATOR_NOVELTY, (
            f"{idea.solution_name}: the last classification read novelty {seen[-1]}, the same "
            "value the parity probe superseded — nothing re-derived after the re-score")
        assert seen[-1] == idea.novelty_score, (
            f"{idea.solution_name}: classifier last read {seen[-1]} but the idea ships "
            f"{idea.novelty_score}")
        assert str(idea.novelty_score) in (idea.novelty_rationale or ""), (
            f"{idea.solution_name}: shipped novelty_rationale {idea.novelty_rationale!r} was "
            f"written against a superseded score (final novelty is {idea.novelty_score})")


def test_serp_probe_still_sees_angles_and_its_consumer_cap_still_fires(monkeypatch):
    """PROPERTY 3: the allow-case b7d9f3a's reorder existed for.

    `_select_serp_probe_candidates` picks `distribution_seo` ideas BY LABEL, and these fixtures
    carry no `commercial_route`, so the angle-independent reserve slot abstains — if angles were
    not classified before the probe, it would select nothing. The tail assertion pins the other
    consumer: rule (a) of `_validate_idea_caps` suspends the novelty coherence lock for a
    distribution_seo idea, so novelty survives at 0.50 instead of being locked to 1 - obviousness.
    """
    crew, rec = _wire(
        monkeypatch, [_idea("Pagestack"), _idea("Workbench"), _idea("Dispatchly")])

    result, _ = crew.execute_pipeline(skip_selection=True)
    pagestack = next(i for i in result.solution_ideas if i.solution_name == "Pagestack")

    assert rec.serp_candidates and rec.serp_candidates[0] == ["Pagestack"], (
        f"the SERP-composition probe selected {rec.serp_candidates} — it must still see "
        "classified distribution_seo ideas; over-blocking it is a different regression, not a fix")
    assert pagestack.novelty_score == _POST_PARITY_NOVELTY, (
        f"novelty was locked to {pagestack.novelty_score} (expected {_POST_PARITY_NOVELTY}) — "
        "rule (a)'s distribution_seo exemption reads winning_angle, so an unclassified idea "
        f"silently gets the {_LOCKED_NOVELTY} coherence lock instead")
