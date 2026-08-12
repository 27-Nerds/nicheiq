"""Stage-1 behavior for "Check my idea" (entry_mode='validate_idea').

Covers the three load-bearing pieces of the intake:
- the idea-check pre-step parse (brief + inferred fields land on state; the returned
  context is rebuilt as the BASE NicheContext so checkpoints never carry subclass fields),
- the working-niche rebind (the raw pitch must never reach thread validation),
- checkpoint round-trip + resume rebind (worker retries rebuild the flow with the raw
  pitch; Stage 1 does not re-run, so resume_from_checkpoint must rebind).
"""

from types import SimpleNamespace
from unittest.mock import patch

from nicheiq.config.settings import settings
from nicheiq.flows.checkpoint_manager import CheckpointManager
from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.research_state import NicheContext, ResearchState

PITCH = (
    "A Chrome extension that drafts Reddit replies for community managers at small "
    "SaaS companies, so they stop spending evenings writing the same answers by hand"
)
DERIVED_MARKET = (
    "Community-management tooling for B2B SaaS: software that helps companies run, "
    "moderate, and grow their user communities across Reddit, Discord, and forums."
)
NAMED_PROJECT_TYPES = ["saas", "directory", "aggregator", "comparison-tool", "marketplace"]


def _ctx_fields() -> dict:
    return {
        "niche_input": "placeholder",  # required at construction; real path overwrites after parse
        "audience_scope": "segment_of_niche",
        "user_target_audience": "community managers at small SaaS companies",
        "niche_description": DERIVED_MARKET,
        "market_segments": ["Community managers", "DevRel teams", "Support leads"],
        "industry_boundaries": "In: community tooling. Out: generic social schedulers.",
    }


def _fake_invoke(captured: dict):
    """invoke_structured stand-in: records the prompt + output model, returns an instance
    of whatever model class the caller passed (base or idea-check subclass)."""

    def _invoke(prompt, output_model, **kwargs):
        captured["prompt"] = prompt
        captured["output_model"] = output_model
        fields = dict(_ctx_fields())
        if "idea_brief" in output_model.model_fields:
            fields.update(
                idea_name="Reddit Reply Drafter",
                idea_brief=(
                    "A Chrome extension that drafts Reddit replies for community "
                    "managers at small SaaS companies."
                ),
                # 'pricing' is not a recognized value — the branch must filter it out.
                idea_inferred_fields=["delivery", "pricing"],
                # blanks are dropped, lists clamp to 4 (quality pass Q4).
                idea_mechanism_terms=["drafts", "replies", "  ",
                                      "answering repetitive questions"],
                idea_audience_terms=["community managers", "small SaaS companies"],
                idea_problem_terms=[],
                idea_delivery_terms=["chrome extension", "browser add-on",
                                     "extension", "plugin", "fifth-term"],
            )
        usage = SimpleNamespace(to_dict=lambda: {})
        return output_model(**fields), usage

    return _invoke


def _bare_flow(entry_mode: str) -> ResearchFlow:
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.entry_mode = entry_mode
    flow._state = ResearchState()  # crewai Flow.state is a read-only property over _state
    flow.cost_tracker = None
    flow._extract_niche_anchors = lambda *a, **k: None
    flow._discover_anchor_subreddits = lambda *a, **k: None
    return flow


def test_idea_check_branch_parses_brief_and_returns_base_context():
    flow = _bare_flow("validate_idea")
    captured: dict = {}
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        side_effect=_fake_invoke(captured),
    ):
        context = flow._generate_niche_context(PITCH)

    assert "IDEA-CHECK PRE-STEP" in captured["prompt"]
    assert '"idea_brief"' in captured["prompt"]
    assert captured["output_model"] is not NicheContext  # the subclass was requested

    # Parse landed on state; unknown inferred values filtered.
    assert flow.state.user_idea_brief.startswith("A Chrome extension")
    # A model cannot mark a clause inferred while also quoting that clause from
    # the raw pitch; the raw submission is the identity authority.
    assert flow.state.user_idea_inferred_fields == []
    assert '"idea_mechanism_terms"' in captured["prompt"]
    assert flow.state.user_idea_identity_terms == {
        "mechanism": ["drafts", "replies"],
        "audience": ["community managers", "small SaaS companies"],
        "problem": [],
        "delivery": ["chrome extension", "extension"],
    }

    # The returned context is the CLEAN base model (checkpoints restore stage_1 as base).
    assert type(context) is NicheContext
    assert context.niche_input == PITCH
    assert context.niche_description == DERIVED_MARKET


def test_normal_mode_has_no_pre_step_and_leaves_idea_fields_none():
    flow = _bare_flow("idea")
    captured: dict = {}
    with patch(
        "nicheiq.utils.llm_service.LLMService.invoke_structured",
        side_effect=_fake_invoke(captured),
    ):
        context = flow._generate_niche_context("community tooling for SaaS")

    assert "IDEA-CHECK PRE-STEP" not in captured["prompt"]
    assert captured["output_model"] is NicheContext
    assert flow.state.user_idea_brief is None
    assert flow.state.user_idea_inferred_fields is None
    assert flow.state.user_idea_identity_terms is None
    assert type(context) is NicheContext


def test_stage1_rebinds_working_niche_to_derived_market():
    flow = _bare_flow("validate_idea")
    flow.niche_description = PITCH
    flow.allowed_project_types = None
    flow.idea_focus = "auto"
    flow._emit_progress = lambda *a, **k: None
    flow._mark_stage_complete = lambda *a, **k: None
    flow.checkpoint_mgr = SimpleNamespace(save_stage=lambda *a, **k: True)
    flow._generate_niche_context = lambda niche_input: NicheContext(
        **{**_ctx_fields(), "niche_input": niche_input}
    )

    flow.stage_1_validate_niche()

    assert flow.state.user_idea_text == PITCH
    assert flow.niche_description == DERIVED_MARKET


def test_validate_flow_discards_project_type_constraints_at_initialization():
    flow = ResearchFlow(
        niche_description=PITCH,
        allowed_project_types=NAMED_PROJECT_TYPES,
        job_id="job-validate-initial",
        entry_mode="validate_idea",
    )

    assert flow.allowed_project_types is None
    assert flow.checkpoint_mgr.allowed_project_types is None


def test_normal_flow_preserves_explicit_project_type_constraints():
    subset = ["saas", "directory"]
    flow = ResearchFlow(
        niche_description="Independent veterinary clinics",
        allowed_project_types=subset,
        job_id="job-normal-initial",
        entry_mode="idea",
    )

    assert flow.allowed_project_types == subset
    assert flow.checkpoint_mgr.allowed_project_types == subset


def test_round_trip_and_resume_rebind(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    save_state = ResearchState()
    save_state.niche_context = NicheContext(**{**_ctx_fields(), "niche_input": PITCH})
    save_state.current_stage = 2
    save_state.user_idea_text = PITCH
    save_state.user_idea_brief = "A Chrome extension that drafts Reddit replies."
    save_state.user_idea_inferred_fields = []  # all stated — must round-trip as [], not None
    save_state.user_idea_identity_terms = {
        "mechanism": ["drafts", "replies"], "audience": ["community managers"],
        "problem": [], "delivery": ["chrome extension"],
    }
    save_state.user_idea_brief_parity = "substitute (SomeTool): drafts AI replies"
    # In the real flow the CheckpointManager is created at flow init, BEFORE the Stage-1
    # rebind — so validate-run checkpoints are keyed by the raw pitch, same as the retry.
    cm = CheckpointManager(
        niche_description=PITCH, state=save_state,
        allowed_project_types=None, job_id="jobV",
    )
    cm.save_stage("stage_1_niche_context", save_state.niche_context)
    folder = cm.checkpoint_folder

    # Worker retry: the flow is rebuilt with the RAW PITCH as niche_description.
    flow = ResearchFlow(niche_description=PITCH, job_id="jobV")
    assert flow.resume_from_checkpoint(folder) is True

    assert flow.state.user_idea_text == PITCH
    assert flow.state.user_idea_brief == "A Chrome extension that drafts Reddit replies."
    assert flow.state.user_idea_inferred_fields == []
    assert flow.state.user_idea_identity_terms == {
        "mechanism": ["drafts", "replies"], "audience": ["community managers"],
        "problem": [], "delivery": ["chrome extension"],
    }
    assert flow.state.user_idea_brief_parity == "substitute (SomeTool): drafts AI replies"
    # The rebind: thread validation must see the derived market, never the pitch.
    assert flow.niche_description == DERIVED_MARKET


def test_legacy_validate_checkpoint_cannot_restore_project_type_constraints(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    save_state = ResearchState()
    save_state.niche_context = NicheContext(**{**_ctx_fields(), "niche_input": PITCH})
    save_state.current_stage = 2
    save_state.user_idea_text = PITCH
    save_state.allowed_project_types = NAMED_PROJECT_TYPES
    cm = CheckpointManager(
        niche_description=PITCH,
        state=save_state,
        allowed_project_types=NAMED_PROJECT_TYPES,
        job_id="job-validate-legacy",
        entry_mode="validate_idea",
    )
    cm.save_stage("stage_1_niche_context", save_state.niche_context)

    flow = ResearchFlow(
        niche_description=PITCH,
        allowed_project_types=NAMED_PROJECT_TYPES,
        job_id="job-validate-legacy",
    )
    assert flow.resume_from_checkpoint(cm.checkpoint_folder) is True

    assert flow.entry_mode == "validate_idea"
    assert flow.allowed_project_types is None
    assert flow.state.allowed_project_types is None
    assert flow.checkpoint_mgr.allowed_project_types is None


def test_normal_checkpoint_still_restores_project_type_constraints(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)
    subset = ["saas", "directory"]

    save_state = ResearchState()
    save_state.niche_context = NicheContext(**{**_ctx_fields(), "niche_input": "plain niche"})
    save_state.current_stage = 2
    save_state.allowed_project_types = subset
    cm = CheckpointManager(
        niche_description="plain niche",
        state=save_state,
        allowed_project_types=subset,
        job_id="job-normal-resume",
        entry_mode="idea",
    )
    cm.save_stage("stage_1_niche_context", save_state.niche_context)

    flow = ResearchFlow(niche_description="plain niche", job_id="job-normal-resume")
    assert flow.resume_from_checkpoint(cm.checkpoint_folder) is True

    assert flow.entry_mode == "idea"
    assert flow.allowed_project_types == subset
    assert flow.state.allowed_project_types == subset


def test_resume_without_idea_fields_keeps_niche_description(tmp_path, monkeypatch):
    """Normal runs are untouched: no user_idea_text → no rebind."""
    monkeypatch.setattr(settings, "checkpoint_dir", tmp_path)
    monkeypatch.setattr(settings, "checkpoint_enabled", True)

    save_state = ResearchState()
    save_state.niche_context = NicheContext(**{**_ctx_fields(), "niche_input": "plain niche"})
    save_state.current_stage = 2
    cm = CheckpointManager(
        niche_description="plain niche", state=save_state,
        allowed_project_types=None, job_id="jobN",
    )
    cm.save_stage("stage_1_niche_context", save_state.niche_context)

    flow = ResearchFlow(niche_description="plain niche", job_id="jobN")
    assert flow.resume_from_checkpoint(cm.checkpoint_folder) is True
    assert flow.niche_description == "plain niche"
