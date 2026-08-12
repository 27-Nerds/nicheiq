"""RT-1 typed finding persistence and legacy compatibility."""

from nicheiq.models.research_state import ResearchState
from nicheiq.models.solution_idea import (
    BaseSolutionIdea,
    IdeaGenerationResult,
    RedTeamFinding,
)
from nicheiq.utils.idea_carryover import carry_forward_idea_fields


def _idea(name: str, **overrides) -> BaseSolutionIdea:
    values = {
        "solution_name": name,
        "description": "A concrete product description.",
        "value_proposition": "A useful result.",
        "pain_points_addressed": ["A validated pain"],
        "core_features": ["Core workflow"],
        "target_personas": ["Named buyer"],
        "market_fit_score": 0.6,
        "technical_feasibility_score": 0.7,
    }
    values.update(overrides)
    return BaseSolutionIdea(**values)


def test_findings_survive_idea_generation_and_research_state_roundtrip():
    finding = RedTeamFinding(
        kind="verified_payer_mismatch",
        claim="The observed users are not the budget owner.",
    )
    state = ResearchState(idea_generation=IdeaGenerationResult(solution_ideas=[
        _idea(
            "Typed",
            red_team_verdict="killed",
            red_team_findings=[finding],
            red_team_caveats=[finding.claim],
        ),
        _idea("Second"),
        _idea("Third"),
    ]))

    restored = ResearchState.model_validate_json(state.model_dump_json())
    typed = restored.idea_generation.solution_ideas[0]
    assert typed.red_team_findings == [finding]
    assert typed.red_team_caveats == [finding.claim]


def test_legacy_prose_only_idea_stays_unclassified():
    payload = _idea(
        "Legacy",
        red_team_verdict="killed",
        red_team_caveats=["No buyer was found"],
    ).model_dump(mode="json")
    payload.pop("red_team_findings", None)

    restored = BaseSolutionIdea.model_validate(payload)

    assert restored.red_team_verdict == "killed"
    assert restored.red_team_caveats == ["No buyer was found"]
    assert restored.red_team_findings is None


def test_identity_changing_rebuild_must_reearn_typed_findings():
    original = _idea(
        "Original",
        red_team_verdict="killed",
        red_team_findings=[RedTeamFinding(
            kind="verified_modal_failure",
            claim="The mechanism misses the modal workflow.",
        )],
        red_team_caveats=["The mechanism misses the modal workflow."],
    )
    rebuilt = _idea("Rebuilt")

    carry_forward_idea_fields(original, rebuilt)

    assert rebuilt.red_team_verdict is None
    assert rebuilt.red_team_caveats is None
    assert rebuilt.red_team_findings is None
