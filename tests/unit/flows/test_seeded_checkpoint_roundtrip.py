"""`seeded_from_catalog` must survive the awaiting-selection → Phase-2 checkpoint boundary."""

from nicheiq.config.settings import settings
from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.models.research_state import NicheContext, ResearchState


def test_seeded_from_catalog_survives_checkpoint_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    # Save side: a seeded run writes the flag into checkpoint metadata.
    save_state = ResearchState()
    save_state.niche_context = NicheContext(
        niche_input="x", niche_description="x desc", market_segments=["a"], industry_boundaries="b"
    )
    save_state.seeded_from_catalog = True
    save_state.current_stage = 5
    cm_save = CheckpointManager(
        niche_description="x", state=save_state, allowed_project_types=None, job_id="job1"
    )
    cm_save.save_stage("stage_1_niche_context", save_state.niche_context)
    folder = cm_save.checkpoint_folder

    # Load side (fresh state, as Phase 2 resume does): flag is restored.
    load_state = ResearchState()
    cm_load = CheckpointManager(
        niche_description="x", state=load_state, allowed_project_types=None, job_id="job1"
    )
    assert cm_load.load_checkpoint_folder(folder) is True
    assert load_state.seeded_from_catalog is True


def test_non_seeded_run_defaults_false(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    save_state = ResearchState()
    save_state.niche_context = NicheContext(
        niche_input="x", niche_description="x desc", market_segments=["a"], industry_boundaries="b"
    )
    cm_save = CheckpointManager(
        niche_description="x", state=save_state, allowed_project_types=None, job_id="job2"
    )
    cm_save.save_stage("stage_1_niche_context", save_state.niche_context)

    load_state = ResearchState()
    cm_load = CheckpointManager(
        niche_description="x", state=load_state, allowed_project_types=None, job_id="job2"
    )
    assert cm_load.load_checkpoint_folder(cm_save.checkpoint_folder) is True
    assert load_state.seeded_from_catalog is False
