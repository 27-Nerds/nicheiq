"""Candidate identity stamping for Stage-7 competitive landscapes."""

from types import SimpleNamespace

from nicheiq.flows.research_flow import ResearchFlow
from nicheiq.models.competitor import CompetitiveLandscape


class _Harness:
    _stamp_competitive_landscape_identity = (
        ResearchFlow._stamp_competitive_landscape_identity
    )

    def __init__(self, ideas):
        self.state = SimpleNamespace(
            idea_generation=SimpleNamespace(solution_ideas=ideas),
        )


def _idea(name: str, idea_id: str | None, revision: int):
    return SimpleNamespace(
        solution_name=name,
        idea_id=idea_id,
        idea_revision=revision,
    )


def test_stage7_stamps_unique_exact_candidate_identity():
    flow = _Harness([_idea("CoffeeRoute", "idea-coffee", 3)])
    landscape = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id=None,
        candidate_idea_revision=None,
    )

    flow._stamp_competitive_landscape_identity(landscape, "CoffeeRoute")

    assert landscape.candidate_idea_id == "idea-coffee"
    assert landscape.candidate_idea_revision == 3


def test_stage7_duplicate_names_are_ambiguous_and_receive_no_identity():
    flow = _Harness([
        _idea("CoffeeRoute", "idea-coffee-a", 1),
        _idea(" CoffeeRoute ", "idea-coffee-b", 2),
    ])
    landscape = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="stale-id",
        candidate_idea_revision=99,
    )

    flow._stamp_competitive_landscape_identity(landscape, "CoffeeRoute")

    assert landscape.candidate_idea_id is None
    assert landscape.candidate_idea_revision is None


def test_stage7_missing_durable_id_does_not_stamp_revision_only():
    flow = _Harness([_idea("CoffeeRoute", None, 3)])
    landscape = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id=None,
        candidate_idea_revision=None,
    )

    flow._stamp_competitive_landscape_identity(landscape, "CoffeeRoute")

    assert landscape.candidate_idea_id is None
    assert landscape.candidate_idea_revision is None


def test_competitive_landscape_identity_roundtrip_and_legacy_defaults():
    required = {
        "solution_name": "CoffeeRoute",
        "competitors": [],
        "market_gaps": ["Gap one", "Gap two"],
        "differentiation_opportunities": ["Niche workflow"],
        "competitive_intensity": "Medium",
        "recommended_positioning": "Serve independent wholesale roasters.",
        "pricing_insights": "Published prices remain sparse.",
    }
    legacy = CompetitiveLandscape.model_validate(required)
    assert legacy.candidate_idea_id is None
    assert legacy.candidate_idea_revision is None

    typed = CompetitiveLandscape.model_validate({
        **required,
        "candidate_idea_id": "idea-coffee",
        "candidate_idea_revision": 3,
    })
    restored = CompetitiveLandscape.model_validate_json(typed.model_dump_json())
    assert restored.candidate_idea_id == "idea-coffee"
    assert restored.candidate_idea_revision == 3
