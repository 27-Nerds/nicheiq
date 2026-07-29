import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaTags
from worker.tasks import _solution_to_preview_dict


def test_solution_preview_refreshes_score_derived_tags():
    idea = BaseSolutionIdea(
        solution_name="Preview idea",
        description="A concrete solution.",
        value_proposition="A useful outcome.",
        pain_points_addressed=["A validated pain"],
        core_features=["Core feature"],
        target_personas=["Buyer"],
        market_fit_score=0.55,
        technical_feasibility_score=0.90,
        novelty_score=0.45,
        solo_dev_feasibility=0.85,
        tags=IdeaTags(
            target_market="b2b",
            monetization="subscription",
            strengths=["market-fit"],
            primary_strength="market-fit",
        ),
    )

    preview = _solution_to_preview_dict(idea)

    assert "market-fit" not in preview["tags"]["strengths"]
    assert preview["tags"]["strengths"] == ["quick-build", "solo-friendly"]
    assert preview["tags"]["primary_strength"] == "solo-friendly"
    assert preview["tags"]["target_market"] == "b2b"
    assert preview["tags"]["monetization"] == "subscription"


def test_dict_solution_preview_refreshes_score_derived_tags():
    idea = BaseSolutionIdea(
        solution_name="Serialized preview idea",
        description="A concrete solution.",
        value_proposition="A useful outcome.",
        pain_points_addressed=["A validated pain"],
        core_features=["Core feature"],
        target_personas=["Buyer"],
        market_fit_score=0.55,
        technical_feasibility_score=0.90,
        novelty_score=0.45,
        solo_dev_feasibility=0.85,
        tags=IdeaTags(
            target_market="b2b",
            strengths=["market-fit"],
            primary_strength="market-fit",
        ),
    )

    preview = _solution_to_preview_dict(idea.model_dump())

    assert "market-fit" not in preview["tags"]["strengths"]
    assert preview["tags"]["strengths"] == ["quick-build", "solo-friendly"]
    assert preview["tags"]["primary_strength"] == "solo-friendly"
