"""Typed red-team finding and normalization regressions (RT-1)."""

from types import SimpleNamespace
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from nicheiq.models.research_state import AlternativeSolution, ResearchState
from nicheiq.models.solution_idea import (
    BaseSolutionIdea,
    IdeaGenerationResult,
    RedTeamFinding,
    effective_red_team_state,
    effective_red_team_verdict,
    has_affirmative_red_team_findings,
)
from nicheiq.report.idea_validation_block import resolve_idea_validation_outcome
from nicheiq.utils.red_team_review import (
    _RedTeamVerdict,
    _is_actionable,
    _normalize_verdict,
)
from nicheiq.utils.score_helpers import choose_auto_pick, red_team_killed
from nicheiq.validators.score_validators import ScoreThresholds, VerdictValidator


def _finding(kind: str, claim: str = "Observed claim") -> RedTeamFinding:
    return RedTeamFinding(kind=kind, claim=claim)


def _idea(name: str, **updates) -> BaseSolutionIdea:
    data = {
        "solution_name": name,
        "description": "A sufficiently concrete product description.",
        "value_proposition": "Useful outcome",
        "pain_points_addressed": ["Pain"],
        "core_features": ["Feature"],
        "target_personas": ["Buyer"],
        "market_fit_score": 0.6,
        "technical_feasibility_score": 0.7,
        "novelty_score": 0.5,
        "seo_scalability_score": 0.4,
        "project_type": "saas",
    }
    data.update(updates)
    return BaseSolutionIdea(**data)


def test_gap_only_requested_kill_normalizes_to_weakened_and_stays_selectable():
    normalized = _normalize_verdict(_RedTeamVerdict(
        verdict="killed",
        findings=[_finding("evidence_gap", "Search did not establish a buyer")],
    ))

    assert normalized.verdict == "weakened"
    assert not red_team_killed(SimpleNamespace(red_team_verdict=normalized.verdict))
    outcome, _ = resolve_idea_validation_outcome(
        idea_name="BuyerGap",
        demoted=False,
        parity_raw=None,
        unanchored=False,
        red_team_verdict=normalized.verdict,
        refinement_present=False,
        brief_parity_hit=False,
    )
    assert outcome == "worth_testing"


def test_adverse_empty_verdict_and_legacy_caveats_extra_are_rejected():
    for verdict in ("weakened", "killed"):
        with pytest.raises(ValidationError):
            _RedTeamVerdict(verdict=verdict, findings=[])

    assert _RedTeamVerdict(verdict="survives", findings=[]).verdict == "survives"
    with pytest.raises(ValidationError):
        _RedTeamVerdict(
            verdict="survives",
            findings=[],
            caveats=["old untyped output"],
        )


def test_shared_authority_preserves_legacy_and_downgrades_only_gap_kill():
    gap = [_finding("evidence_gap")]
    mixed = [*_finding_list("evidence_gap"), *_finding_list("verified_payer_mismatch")]

    assert effective_red_team_verdict("killed", None) == "killed"
    assert effective_red_team_verdict("killed", gap) == "weakened"
    assert effective_red_team_verdict("killed", mixed) == "killed"
    assert effective_red_team_verdict(
        "killed", [{"kind": "verified_payer_mismatch"}]
    ) == "weakened"
    assert effective_red_team_verdict("weakened", gap) == "weakened"


def _finding_list(kind: str) -> list[RedTeamFinding]:
    return [_finding(kind)]


def test_base_generation_checkpoint_and_alternative_normalize_typed_gap_kill():
    gap = [_finding("evidence_gap", "Search did not establish a buyer")]
    ideas = [
        _idea("Gap", red_team_verdict="killed", red_team_findings=gap),
        _idea("Other A"),
        _idea("Other B"),
    ]

    assert ideas[0].red_team_verdict == "weakened"
    generation = IdeaGenerationResult(solution_ideas=ideas)
    restored = ResearchState.model_validate_json(
        ResearchState(idea_generation=generation).model_dump_json()
    )
    assert restored.idea_generation.solution_ideas[0].red_team_verdict == "weakened"
    assert restored.idea_generation.solution_ideas[0].red_team_findings == gap

    alternative = AlternativeSolution(
        solution_name="Gap",
        summary="Summary",
        key_differentiator="Difference",
        best_suited_for="Buyer",
        pivot_trigger="Trigger",
        red_team_verdict="killed",
        red_team_findings=gap,
    )
    assert alternative.red_team_verdict == "weakened"


def test_raw_gap_kill_remains_auto_pick_eligible_and_outcome_is_incomplete():
    gap = [{"kind": "evidence_gap", "claim": "Search found no proof"}]
    raw = {"solution_name": "Gap", "red_team_verdict": "killed",
           "red_team_findings": gap}
    pick, note = choose_auto_pick([SimpleNamespace(solution_name="Gap")], [raw])

    assert pick.solution_name == "Gap"
    assert note is None
    outcome, headline = resolve_idea_validation_outcome(
        idea_name="Gap",
        demoted=False,
        parity_raw=None,
        unanchored=False,
        red_team_verdict="killed",
        red_team_findings=gap,
        refinement_present=False,
        brief_parity_hit=False,
    )
    assert outcome == "worth_testing"
    assert "incomplete evidence" in headline
    assert "counterevidence" not in headline


def test_raw_gap_kill_report_floor_is_weakened_incomplete_not_counterevidence():
    validator = VerdictValidator(ScoreThresholds())
    verdict, risk, concern, context = validator.apply_red_team_downgrade(
        verdict="Go",
        risk_level="Low",
        primary_concern=None,
        red_team_verdict="killed",
        red_team_caveats=["Search found no proof"],
        red_team_findings=[{
            "kind": "evidence_gap",
            "claim": "Search found no proof",
        }],
    )

    assert (verdict, risk) == ("Conditional", "Medium")
    assert "incomplete evidence" in concern.lower()
    assert "incomplete evidence" in context.lower()
    assert "counterevidence" not in context.lower()


def test_legacy_kill_without_findings_keeps_historical_semantics():
    idea = _idea("Legacy", red_team_verdict="killed", red_team_findings=None)

    assert idea.red_team_verdict == "killed"
    assert red_team_killed(idea)


@pytest.mark.parametrize("raw_verdict", [7, False, [], {}, object()])
def test_nonstring_raw_verdict_is_absent_and_never_crashes(raw_verdict):
    verdict, findings = effective_red_team_state({
        "red_team_verdict": raw_verdict,
        "red_team_findings": [{"kind": "evidence_gap", "claim": "No proof"}],
    })

    assert verdict is None
    assert findings == [_finding("evidence_gap", "No proof")]
    assert red_team_killed({"red_team_verdict": raw_verdict}) is False


def test_effective_state_preserves_legacy_none_vs_typed_empty_and_drops_bad_rows():
    assert effective_red_team_state({
        "red_team_verdict": "killed", "red_team_findings": None,
    }) == ("killed", None)

    verdict, findings = effective_red_team_state({
        "red_team_verdict": "killed",
        "red_team_findings": [
            {"kind": "evidence_gap", "claim": "No proof"},
            {"kind": "not_a_kind", "claim": "Bad row"},
        ],
    })
    assert verdict == "weakened"
    assert findings == [_finding("evidence_gap", "No proof")]
    assert effective_red_team_state({
        "red_team_verdict": "killed", "red_team_findings": [],
    }) == ("weakened", [])
    assert effective_red_team_state(MappingProxyType({
        "red_team_verdict": "killed", "red_team_findings": [],
    })) == ("weakened", [])


def test_findings_container_boundary_is_shared_by_authority_outcome_and_floor():
    malformed_values = [
        "not-a-collection",
        7,
        {"kind": "verified_payer_mismatch", "claim": "Looks affirmative but is not an array."},
        SimpleNamespace(kind="verified_payer_mismatch", claim="Not an array."),
    ]
    validator = VerdictValidator(ScoreThresholds())

    for raw_findings in malformed_values:
        assert has_affirmative_red_team_findings(raw_findings) is False
        assert effective_red_team_verdict("killed", raw_findings) == "killed"
        assert effective_red_team_state({
            "red_team_verdict": "killed",
            "red_team_findings": raw_findings,
        }) == ("killed", None)

        outcome, headline = resolve_idea_validation_outcome(
            idea_name="Malformed legacy idea",
            demoted=False,
            parity_raw=None,
            unanchored=False,
            red_team_verdict="killed",
            red_team_findings=raw_findings,
            refinement_present=False,
            brief_parity_hit=False,
        )
        assert outcome == "premise_unproven"
        assert "could not confirm the premise" in headline
        assert "incomplete evidence" not in headline
        assert "verified counterevidence" not in headline

        _verdict, risk, concern, context = validator.apply_red_team_downgrade(
            verdict="Conditional",
            risk_level="Medium",
            primary_concern=None,
            red_team_verdict="killed",
            red_team_caveats=["Legacy prose-only caveat."],
            red_team_findings=raw_findings,
        )
        assert risk == "High"
        assert context and "could not find evidence" in context
        assert concern and "refuted" in concern
        assert "incomplete evidence" not in context
        assert "verified counterevidence" not in context


def test_only_list_or_tuple_marks_an_explicit_typed_findings_collection():
    gap = {"kind": "evidence_gap", "claim": "Search did not establish a buyer."}
    invalid = {"kind": "not_a_kind", "claim": "Invalid row."}

    assert effective_red_team_state({
        "red_team_verdict": "killed", "red_team_findings": (),
    }) == ("weakened", [])
    assert effective_red_team_state({
        "red_team_verdict": "killed", "red_team_findings": (gap,),
    }) == ("weakened", [_finding("evidence_gap", "Search did not establish a buyer.")])
    assert effective_red_team_state({
        "red_team_verdict": "killed", "red_team_findings": [invalid],
    }) == ("weakened", [])


@pytest.mark.parametrize("kinds", [
    ["verified_incumbent_overlap"],
    ["evidence_gap", "verified_payer_mismatch"],
])
def test_affirmative_or_mixed_requested_kill_remains_killed(kinds):
    normalized = _normalize_verdict(_RedTeamVerdict(
        verdict="killed",
        findings=[_finding(kind) for kind in kinds],
    ))

    assert normalized.verdict == "killed"


def test_actionability_uses_kinds_not_claim_keywords():
    gap = _RedTeamVerdict(
        verdict="weakened",
        findings=[_finding("evidence_gap", "No free tool appeared in the results")],
    )
    free_alternative = _RedTeamVerdict(
        verdict="weakened",
        findings=[_finding(
            "verified_free_or_bundled_alternative",
            "The incumbent includes the workflow in its free tier",
        )],
    )

    assert _is_actionable(gap) is False
    assert _is_actionable(free_alternative) is True


def test_invalid_kind_and_blank_claim_are_rejected():
    with pytest.raises(ValidationError):
        RedTeamFinding(kind="buyer_not_found", claim="No buyer found")
    with pytest.raises(ValidationError):
        RedTeamFinding(kind="evidence_gap", claim="   ")


def test_verdict_findings_are_capped_at_three():
    with pytest.raises(ValidationError):
        _RedTeamVerdict(
            verdict="weakened",
            findings=[_finding("evidence_gap", str(i)) for i in range(4)],
        )
