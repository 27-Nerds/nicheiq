"""Production-path coverage for recommendation-scoped audience drift.

These tests intentionally materialize the same preview JSON consumed by the job page. A direct
detector test cannot prove that recommendation inputs, checkpoint persistence, and the rendered
AudienceSnapshot payload stay connected.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.utils.audience_axes import AUDIENCE_DRIFT_CHALLENGE
from nicheiq.models.research_state import (
    AudienceMappingResult,
    NicheContext,
    NicheDifficultyVerdict,
)
from nicheiq.models.solution_idea import IdeaGenerationResult
from nicheiq.models.solution_selection import SolutionSelection


JOB_ID = "51a491dc-c095-4e21-befb-5cadf540629a"
# Vendored, not read out of `output/`. `output/checkpoints` is gitignored, so every test in this
# file used to raise FileNotFoundError on a clean clone — production-path coverage that existed
# only on the machine that captured the run.
EXEMPLAR = json.loads(
    Path("tests/fixtures/audience_drift_exemplar_51a491dc.json").read_text()
)
EXPECTED_MESSAGE = (
    "You asked to reach “independent veterinary clinics managing multi-location inventory "
    "and controlled-substance compliance”. This run's research settled on “Independent "
    "Single-Location General Practices with Manual Drug Logs”, and the recommendation is built "
    "for “Specialty, Emergency, and Referral Hospitals with High-Volume Controlled-Drug "
    "Workflows”. This run's research settled on a different operating scale than you asked for. "
    "The recommendation is built for a different type of practice than the research settled on. "
    "Confirm that buyer change before you fund or build the recommendation."
)


def _load(name: str) -> dict:
    return EXEMPLAR[name.removesuffix(".json")]


def _exemplar_flow() -> tuple[ResearchFlow, SimpleNamespace, Mock]:
    state = SimpleNamespace(
        job_id=JOB_ID,
        niche_context=NicheContext.model_validate(_load("stage_1_niche_context.json")),
        audience_mapping=AudienceMappingResult.model_validate(
            _load("stage_4_audience_mapping.json")
        ),
        idea_generation=IdeaGenerationResult.model_validate(
            _load("stage_5_3_refinement.json")
        ),
        solution_selection=SolutionSelection.model_validate(
            _load("stage_5_6_selection.json")
        ),
        niche_difficulty_verdict=NicheDifficultyVerdict.model_validate(
            _load("stage_5_niche_difficulty.json")
        ),
        idea_portfolio_summary=None,
        idea_portfolio_summary_fingerprint=None,
        idea_ruled_out=[],
        idea_overlap_groups=[],
    )
    save_stage = Mock()
    flow = ResearchFlow.__new__(ResearchFlow)
    flow.job_id = JOB_ID
    flow.niche_description = state.niche_context.niche_description
    flow._state = state
    flow.checkpoint_mgr = SimpleNamespace(save_stage=save_stage)
    # This test targets drift wiring. Avoid an unrelated summary LLM refresh while keeping the
    # real preview materializer, recommendation resolver, persistence, and JSON projection live.
    flow._refresh_idea_portfolio_summary = lambda **_kwargs: False
    return flow, state, save_stage


def _materialize(flow: ResearchFlow, output_dir: Path) -> dict:
    path = flow._materialize_preview_report(str(output_dir))
    assert path is not None
    return json.loads(Path(path).read_text())


def test_exemplar_persists_and_delivers_structured_notice_on_live_preview_path(tmp_path):
    flow, state, save_stage = _exemplar_flow()

    report = _materialize(flow, tmp_path)

    expected = {
        "requested_audience": (
            "independent veterinary clinics managing multi-location inventory and "
            "controlled-substance compliance"
        ),
        "dossier_primary_segment": (
            "Independent Single-Location General Practices with Manual Drug Logs"
        ),
        "recommended_source_segments": [
            "Specialty, Emergency, and Referral Hospitals with High-Volume "
            "Controlled-Drug Workflows"
        ],
        "message": EXPECTED_MESSAGE,
    }
    assert report["audience_mapping"]["audience_drift_notice"] == expected
    assert report["niche_difficulty_verdict"]["audience_drift_notice"] == expected
    assert state.audience_mapping.audience_drift_notice is not None
    assert state.niche_difficulty_verdict.audience_drift_notice is not None
    assert {call.args[0] for call in save_stage.call_args_list} == {
        "stage_4_audience_mapping",
        "stage_5_niche_difficulty",
    }


def _retarget_recommendation(state, segment: str) -> None:
    """Point every recommended idea's provenance at `segment`."""
    names = {
        state.solution_selection.selected_solution_name,
        *(state.solution_selection.runner_up_solutions or []),
    }
    for idea in state.idea_generation.solution_ideas:
        if idea.solution_name in names:
            idea.source_segment = segment


def test_the_reality_check_challenge_is_written_at_the_same_snapshot_as_the_notice(tmp_path):
    """Three surfaces show this warning, not two.

    The audience card and the verdict card read `audience_drift_notice`; `NicheRealityCheck`
    renders `verdict.key_challenges`. The exemplar's persisted verdict predates the challenge
    entirely, so the refresh has to put it there — the same refresh that binds the notice.
    """
    flow, _state, _save_stage = _exemplar_flow()

    report = _materialize(flow, tmp_path)

    assert report["niche_difficulty_verdict"]["audience_drift_notice"] is not None
    challenges = report["niche_difficulty_verdict"]["key_challenges"]
    assert AUDIENCE_DRIFT_CHALLENGE in challenges
    # The pointer, not the message: `key_challenges` is niche-scoped on the public-share
    # boundary while the notice is pool-scoped, so the message must not travel in this list.
    assert not any(EXPECTED_MESSAGE in point for point in challenges)


def test_a_recommendation_that_changes_after_stage_5_clears_every_surface(tmp_path):
    """The staleness the notice-only refresh left behind.

    Rebinding just `audience_drift_notice` cleared both cards and left `key_challenges` still
    warning about a buyer change the current recommendation no longer shows — a Reality Check
    contradicting the audience card on the same page.
    """
    flow, state, _save_stage = _exemplar_flow()
    first = _materialize(flow, tmp_path)
    assert AUDIENCE_DRIFT_CHALLENGE in first["niche_difficulty_verdict"]["key_challenges"]

    # The run now asks for, researches, and recommends one and the same buyer.
    settled = state.audience_mapping.primary_target_segment
    state.niche_context = state.niche_context.model_copy(
        update={"user_target_audience": settled}
    )
    _retarget_recommendation(state, settled)

    second = _materialize(flow, tmp_path)

    assert second["audience_mapping"]["audience_drift_notice"] is None
    assert second["niche_difficulty_verdict"]["audience_drift_notice"] is None
    assert AUDIENCE_DRIFT_CHALLENGE not in second["niche_difficulty_verdict"]["key_challenges"]
    # Nothing else in the list was disturbed on the way through.
    assert [
        point for point in first["niche_difficulty_verdict"]["key_challenges"]
        if point != AUDIENCE_DRIFT_CHALLENGE
    ] == second["niche_difficulty_verdict"]["key_challenges"]


def test_the_frontend_fixture_is_this_run_s_own_output(tmp_path):
    """The render tests assert on a fixture; this is what stops that fixture being fiction.

    `AudienceSnapshot` and `DecisionBrief` render the notice verbatim, so their tests are only
    worth anything if the string they render is the string this pipeline actually emits.
    """
    fixture = json.loads(
        Path(
            "frontend/src/lib/components/preview/__tests__/fixtures/"
            "audienceDriftNotice.exemplar.json"
        ).read_text()
    )
    flow, _state, _save_stage = _exemplar_flow()

    report = _materialize(flow, tmp_path)

    assert fixture == report["audience_mapping"]["audience_drift_notice"]


@pytest.mark.parametrize(
    ("save_behaviour", "expected_stage"),
    [
        (lambda stage, payload: stage != "stage_4_audience_mapping", "stage_4_audience_mapping"),
        (lambda stage, payload: stage != "stage_5_niche_difficulty", "stage_5_niche_difficulty"),
    ],
    ids=["audience-mapping-write", "verdict-write"],
)
def test_a_checkpoint_write_that_never_landed_is_reported_not_swallowed(
    tmp_path, save_behaviour, expected_stage
):
    """`save_stage` reports failure by RETURNING False, which used to read as success.

    Both writes are independent, so each is checked on its own. The preview is still published
    with the notice inside it — the notice is the warning, and withholding the preview would
    delete the thing being protected — but the run must say out loud that it will not survive
    a resume.
    """
    from loguru import logger as loguru_logger

    flow, _state, _save_stage = _exemplar_flow()
    flow.checkpoint_mgr = SimpleNamespace(save_stage=Mock(side_effect=save_behaviour))

    errors: list[str] = []
    sink_id = loguru_logger.add(lambda message: errors.append(str(message)), level="ERROR")
    try:
        report = _materialize(flow, tmp_path)
    finally:
        loguru_logger.remove(sink_id)

    assert report["audience_mapping"]["audience_drift_notice"]["message"] == EXPECTED_MESSAGE
    assert any(expected_stage in message and "resume" in message for message in errors), errors


def test_interactive_live_path_uses_the_fingerprint_bound_summary_recommendation(tmp_path):
    from nicheiq.utils.idea_portfolio_summary import idea_portfolio_fingerprint

    flow, state, _save_stage = _exemplar_flow()
    state.solution_selection = None
    state.idea_portfolio_summary = (
        "Several candidates deserve comparison. "
        "I recommend Fallback Ledger first because its buyer workflow is the clearest."
    )
    state.idea_portfolio_summary_fingerprint = idea_portfolio_fingerprint(
        state.idea_generation.solution_ideas,
        job_id=JOB_ID,
    )

    report = _materialize(flow, tmp_path)

    assert report["audience_mapping"]["audience_drift_notice"]["message"] == EXPECTED_MESSAGE


@pytest.mark.parametrize(
    ("requested", "primary", "recommended"),
    [
        (
            "Independent veterinary clinics",
            "Independent veterinary clinics",
            "Independent veterinary clinics",
        ),
        (
            "independent veterinary clinics managing medication inventory",
            "Independent vet practices managing medicine inventory",
            "Independent veterinary practices managing drug inventory",
        ),
    ],
    ids=["all-agree", "mild-wording"],
)
def test_live_preview_path_renders_nothing_for_agreement_or_mild_wording(
    tmp_path, requested, primary, recommended
):
    flow, state, _save_stage = _exemplar_flow()
    state.niche_context = state.niche_context.model_copy(
        update={"user_target_audience": requested}
    )
    state.audience_mapping = state.audience_mapping.model_copy(
        update={"primary_target_segment": primary}
    )
    recommendation_names = {
        state.solution_selection.selected_solution_name,
        *(state.solution_selection.runner_up_solutions or []),
    }
    for idea in state.idea_generation.solution_ideas:
        if idea.solution_name in recommendation_names:
            idea.source_segment = recommended

    report = _materialize(flow, tmp_path)

    assert report["audience_mapping"]["audience_drift_notice"] is None
    assert report["niche_difficulty_verdict"]["audience_drift_notice"] is None
