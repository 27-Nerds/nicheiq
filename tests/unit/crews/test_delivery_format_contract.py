from types import SimpleNamespace

import pytest

from nicheiq.crews.unified_solution_crew import SeedRequest, UnifiedSolutionCrew
from nicheiq.models.solution_idea import BaseSolutionIdea, RawConcept
from nicheiq.utils.validation.crew_guardrails import _synthesize_idea_from_concept


def _idea(**overrides):
    data = {
        "solution_name": "Reply Draft",
        "description": "Drafts concise support replies.",
        "value_proposition": "Reply faster.",
        "pain_points_addressed": [],
        "core_features": ["Draft reply"],
        "target_personas": ["Independent merchants"],
    }
    data.update(overrides)
    return BaseSolutionIdea.model_validate(data)


def _seed_crew():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew.cost_tracker = None
    crew.pain_point_analysis = SimpleNamespace(pain_points=[])
    crew.audience_mapping = SimpleNamespace(
        audience_segments=[], tools_currently_used=[], frustrations_with_existing=[]
    )
    crew.niche_context = SimpleNamespace(niche_description="")
    crew.competitor_mentions_text = ""
    crew.allowed_project_types = None
    crew.search_tool = None
    crew._semantic_seed_identity_matches = lambda *_args, **_kwargs: True
    crew._record_divergent_usage = lambda _usages: None
    return crew


def _keep_real_score_wave(monkeypatch):
    def no_op(*_args, **_kwargs):
        return None

    for method in (
        "_verify_pool_routes",
        "_finalize_feasibility",
        "_filter_pain_relevance",
        "_stamp_payability",
        "_finalize_dev_time",
        "_probe_mechanism_parity",
        "_calibrate_idea_scores",
        "_validate_idea_caps",
        "_classify_idea_angles",
    ):
        monkeypatch.setattr(UnifiedSolutionCrew, method, no_op)


def test_pool_contract_normalizes_delivery_format_and_uses_other_for_missing():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    extension = _idea(delivery_format="Chrome extension")
    missing = _idea(solution_name="Ambiguous tool")

    crew._finalize_idea_pool([extension, missing])

    assert extension.delivery_format == "browser-extension"
    assert missing.delivery_format == "other"


def test_pool_contract_does_not_backfill_a_legacy_artifact():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    legacy = _idea(identity_origin="legacy_backfill")

    crew._finalize_idea_pool([legacy])

    assert legacy.delivery_format is None


def test_provenance_carries_delivery_format_from_raw_concept():
    crew = UnifiedSolutionCrew.__new__(UnifiedSolutionCrew)
    crew._provenance_segment_for_pain = lambda _pain: None
    refined = SimpleNamespace(solution_ideas=[_idea()])
    raw = SimpleNamespace(
        concepts=[RawConcept(
            concept_name="Reply Draft",
            one_liner="Drafts concise support replies.",
            ideation_technique="atomic_feature",
            project_type="other",
            delivery_format="browser-extension",
            target_keywords=["support reply writer", "reply drafting tool"],
        )]
    )

    crew._carry_provenance(refined, raw)

    assert refined.solution_ideas[0].delivery_format == "browser-extension"


def test_coverage_reinjection_carries_delivery_format():
    concept = RawConcept(
        concept_name="Reply Draft",
        one_liner="Drafts concise support replies.",
        ideation_technique="atomic_feature",
        project_type="other",
        delivery_format="browser-extension",
        target_keywords=["support reply writer", "reply drafting tool"],
    )

    idea = _synthesize_idea_from_concept(
        concept, SimpleNamespace(title="Support replies take too long")
    )

    assert idea.delivery_format == "browser-extension"


def test_single_surface_pitch_wins_over_conflicting_typed_birth_before_identity_lock(monkeypatch):
    seed = "A browser extension that drafts concise customer-support replies."
    idea = _idea(description=seed, value_proposition=seed, delivery_format="web-app")
    crew = _seed_crew()
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **_kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    result = crew.execute_seed_pipeline(SeedRequest(seed_text=seed))

    assert result is idea
    assert result.delivery_format == "browser-extension"


def test_silent_pitch_preserves_valid_typed_birth_before_identity_lock(monkeypatch):
    seed = "A tool that drafts concise customer-support replies."
    idea = _idea(description=seed, value_proposition=seed, delivery_format="browser-extension")
    crew = _seed_crew()
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **_kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    result = crew.execute_seed_pipeline(SeedRequest(seed_text=seed))

    assert result is idea
    assert result.delivery_format == "browser-extension"


def test_single_surface_pitch_fills_missing_typed_birth_before_identity_lock(monkeypatch):
    seed = "A browser extension that drafts concise customer-support replies."
    idea = _idea(description=seed, value_proposition=seed)
    crew = _seed_crew()
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)
    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", lambda self, wave, **_kw: None)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    result = crew.execute_seed_pipeline(SeedRequest(seed_text=seed))

    assert result is idea
    assert result.delivery_format == "browser-extension"


def test_seed_delivery_format_mutation_after_lock_is_rejected(monkeypatch):
    seed = "A browser extension that drafts concise customer-support replies."
    idea = _idea(description=seed, value_proposition=seed, delivery_format="browser-extension")
    crew = _seed_crew()
    monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)

    def mutate_delivery(_self, wave, **_kwargs):
        wave[0].delivery_format = "web-app"

    monkeypatch.setattr(UnifiedSolutionCrew, "_score_wave", mutate_delivery)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    assert crew.execute_seed_pipeline(SeedRequest(seed_text=seed)) is None


@pytest.mark.parametrize("exact", [False, True], ids=["free-seed", "exact-synthesis"])
@pytest.mark.parametrize(
    "seed",
    [
        "A primary iOS mobile app with a companion browser extension for desktop lookup.",
        "A companion browser extension for desktop lookup plus a primary iOS mobile app.",
    ],
)
def test_mixed_surface_seed_uses_other_despite_typed_birth_through_real_score_wave(
    monkeypatch, exact, seed,
):
    idea = _idea(
        description=seed,
        value_proposition=seed,
        technical_approach=seed,
        project_type="other",
        delivery_format="mobile-app",
        source_frame="user_seed",
    )
    crew = _seed_crew()
    _keep_real_score_wave(monkeypatch)
    if exact:
        evaluation = {
            "evaluation_id": "eval-1",
            "proposal": {"proposedTitle": "Mobile Reply Draft"},
        }
        monkeypatch.setattr(
            UnifiedSolutionCrew,
            "_run_exact_synthesis_cell",
            lambda self, **_kw: (idea, seed),
        )
        monkeypatch.setattr(
            "nicheiq.utils.seed_fidelity.structured_synthesis_fidelity_failures",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            "nicheiq.utils.seed_fidelity.unpitched_core_dependencies",
            lambda *_args, **_kwargs: [],
        )
    else:
        evaluation = None
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    result = crew.execute_seed_pipeline(
        SeedRequest(seed_text=seed, synthesis_evaluation=evaluation)
    )

    assert result is idea
    assert result.delivery_format == "other"


@pytest.mark.parametrize("exact", [False, True], ids=["free-seed", "exact-synthesis"])
@pytest.mark.parametrize(
    "seed",
    [
        "The main problem browser extension users face is solved by a mobile app.",
        "A companion browser extension is the primary delivery surface, alongside an iOS mobile app.",
        "A mobile app and browser extension are co-primary delivery surfaces.",
        "A primary iOS mobile app with a companion browser extension that produces a monthly PDF report.",
        "A monthly PDF report produced by an iOS mobile app.",
    ],
)
def test_mixed_surface_pitch_without_typed_birth_falls_back_to_other_through_real_score_wave(
    monkeypatch, exact, seed,
):
    idea = _idea(
        description=seed,
        value_proposition=seed,
        project_type="other",
        source_frame="user_seed",
    )
    crew = _seed_crew()
    _keep_real_score_wave(monkeypatch)
    if exact:
        evaluation = {
            "evaluation_id": "eval-1",
            "proposal": {"proposedTitle": "Mixed Surface Reply Draft"},
        }
        monkeypatch.setattr(
            UnifiedSolutionCrew,
            "_run_exact_synthesis_cell",
            lambda self, **_kw: (idea, seed),
        )
        monkeypatch.setattr(
            "nicheiq.utils.seed_fidelity.structured_synthesis_fidelity_failures",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            "nicheiq.utils.seed_fidelity.unpitched_core_dependencies",
            lambda *_args, **_kwargs: [],
        )
    else:
        evaluation = None
        monkeypatch.setattr(UnifiedSolutionCrew, "_run_seed_cell", lambda self, **_kw: idea)
    monkeypatch.setattr(UnifiedSolutionCrew, "_finalize_seed_tail", lambda self, wave: None)

    result = crew.execute_seed_pipeline(
        SeedRequest(seed_text=seed, synthesis_evaluation=evaluation)
    )

    assert result is idea
    assert result.delivery_format == "other"
