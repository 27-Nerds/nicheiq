import pytest

from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.models.research_state import ResearchState
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult
from nicheiq.utils.idea_identity import (
    apply_pool_identities,
    deterministic_idea_id,
    ensure_legacy_idea_identities,
    normalize_solution_name,
    selection_fingerprint,
    stamp_new_idea_identities,
    stamp_ruled_out_findings,
)


def _idea(name: str) -> BaseSolutionIdea:
    return BaseSolutionIdea(
        solution_name=name,
        description=f"{name} description",
        value_proposition=f"{name} value",
        pain_points_addressed=["Pain"],
        core_features=["Feature"],
        target_personas=["Persona"],
        market_fit_score=0.7,
        technical_feasibility_score=0.8,
    )


def test_identity_algorithm_matches_backend_seed_contract():
    assert deterministic_idea_id(
        "job-1", "legacy_backfill", "pool", 0
    ) == "idea_488183b23654db86bcfcfce28d8b46c1"


def test_operation_stamping_is_deterministic_and_code_owned():
    ideas = [_idea("A"), _idea("B")]
    ideas[0].idea_id = "model-supplied"

    stamp_new_idea_identities(
        "job-1",
        ideas,
        origin="regeneration",
        operation_key="dispatch-1",
        force=True,
    )

    assert ideas[0].idea_id == deterministic_idea_id(
        "job-1", "regeneration", "dispatch-1", 0
    )
    assert ideas[1].idea_id == deterministic_idea_id(
        "job-1", "regeneration", "dispatch-1", 1
    )
    assert all(idea.idea_revision == 1 for idea in ideas)
    assert all(idea.identity_origin == "regeneration" for idea in ideas)
    assert all(idea.identity_operation_id == "dispatch-1" for idea in ideas)


def test_legacy_hydration_matches_backend_projection_and_preserves_existing_id():
    ideas = [_idea("Legacy A"), _idea("Legacy B")]
    ideas[1].idea_id = "idea_existing"
    ideas[1].idea_revision = 4

    ensure_legacy_idea_identities("job-1", ideas)

    assert ideas[0].idea_id == deterministic_idea_id(
        "job-1", "legacy_backfill", "pool", 0
    )
    assert ideas[0].idea_revision == 1
    assert ideas[1].idea_id == "idea_existing"
    assert ideas[1].idea_revision == 4


def test_legacy_hydration_indexes_visible_pool_like_old_backend_payload():
    hidden = _idea("Hidden")
    hidden.candidate_status = "demoted"
    visible = _idea("Visible")

    ensure_legacy_idea_identities("job-1", [hidden, visible])

    assert visible.idea_id == deterministic_idea_id(
        "job-1", "legacy_backfill", "pool", 0
    )
    assert hidden.idea_id == deterministic_idea_id(
        "job-1", "legacy_hidden", "pool", 0
    )


def test_backend_pool_identity_preserves_matching_native_identity_and_provenance():
    idea = _idea("Native")
    idea.idea_id = "idea_native"
    idea.idea_revision = 3
    idea.identity_origin = "regeneration"
    idea.identity_operation_id = "batch-7"

    applied = apply_pool_identities(
        [idea],
        [{
            "idea_id": "idea_native",
            "idea_revision": 3,
            "solution_name": " Native ",
        }],
    )

    assert applied == 0
    assert idea.idea_id == "idea_native"
    assert idea.idea_revision == 3
    assert idea.identity_origin == "regeneration"
    assert idea.identity_operation_id == "batch-7"


def test_backend_pool_identity_replaces_legacy_backfill_placeholder():
    idea = _idea("Legacy")
    ensure_legacy_idea_identities("job-1", [idea])
    legacy_id = idea.idea_id

    applied = apply_pool_identities(
        [idea],
        [{
            "idea_id": "idea_backend",
            "idea_revision": 4,
            "solution_name": "Legacy",
        }],
    )

    assert applied == 1
    assert idea.idea_id != legacy_id
    assert idea.idea_id == "idea_backend"
    assert idea.idea_revision == 4
    assert idea.identity_origin == "backend_pool"
    assert idea.identity_operation_id is None


def test_backend_pool_identity_rejects_conflicting_native_identity():
    idea = _idea("Native")
    idea.idea_id = "idea_checkpoint"
    idea.idea_revision = 2
    idea.identity_origin = "phase1"
    idea.identity_operation_id = "initial"

    with pytest.raises(RuntimeError, match="conflicts with backend pool"):
        apply_pool_identities(
            [idea],
            [{
                "idea_id": "idea_backend",
                "idea_revision": 4,
                "solution_name": "Native",
            }],
        )

    assert idea.idea_id == "idea_checkpoint"
    assert idea.idea_revision == 2
    assert idea.identity_origin == "phase1"
    assert idea.identity_operation_id == "initial"


def test_ruled_out_finding_and_nested_idea_share_identity():
    finding = {
        "idea_name": "Demoted",
        "reason": "Did not clear the bar",
        "idea": {"solution_name": "Demoted"},
    }

    stamp_ruled_out_findings("job-1", [finding], operation_key="seed:dispatch-1")

    assert finding["finding_id"].startswith("finding_")
    assert finding["finding_revision"] == 1
    assert finding["idea_id"] == finding["idea"]["idea_id"]
    assert finding["idea_revision"] == finding["idea"]["idea_revision"] == 1


def test_selection_fingerprint_normalizes_whitespace_but_preserves_case():
    compact = [{"idea_id": "i", "idea_revision": 2, "solution_name": "Alpha Hub"}]
    spaced = [{"idea_id": "i", "idea_revision": 2, "solution_name": " Alpha   Hub "}]
    different_case = [{"idea_id": "i", "idea_revision": 2, "solution_name": "alpha hub"}]

    assert normalize_solution_name(" Alpha   Hub ") == "Alpha Hub"
    assert selection_fingerprint(compact) == selection_fingerprint(spaced)
    assert selection_fingerprint(spaced) == (
        "bfa42c9680dbb35a57f69817a3c967c8965948497f82aa397754ad3571db06c1"
    )
    assert selection_fingerprint(compact) != selection_fingerprint(different_case)


def test_checkpoint_reconstruction_hydrates_legacy_candidate_and_finding(tmp_path):
    state = ResearchState()
    manager = CheckpointManager("test", state, job_id="job-1")
    manager.validator.validate_stage_file = lambda _path: True
    generation = IdeaGenerationResult(
        solution_ideas=[_idea("A"), _idea("B"), _idea("C")]
    )
    (tmp_path / "stage_5_3_refinement.json").write_text(
        generation.model_dump_json(),
        encoding="utf-8",
    )
    metadata = {
        "current_stage": 5,
        "idea_ruled_out": [
            {
                "idea_name": "D",
                "reason": "Weak fit",
                "idea": {"solution_name": "D"},
            }
        ],
    }

    manager._reconstruct_state_from_checkpoint(tmp_path, metadata)

    assert state.idea_generation.solution_ideas[0].idea_id == deterministic_idea_id(
        "job-1", "legacy_backfill", "pool", 0
    )
    assert state.idea_ruled_out[0]["finding_id"].startswith("finding_")
    assert state.idea_ruled_out[0]["idea_id"] == state.idea_ruled_out[0]["idea"]["idea_id"]
