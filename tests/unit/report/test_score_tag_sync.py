from types import SimpleNamespace
from unittest.mock import MagicMock

from nicheiq.models.research_state import ResearchState
from nicheiq.models.solution_idea import BaseSolutionIdea, IdeaGenerationResult, IdeaTags
from nicheiq.models.solution_selection import SolutionScores, SolutionSelection
from nicheiq.report.report_generator import ReportGenerator


def test_score_sync_rederives_code_owned_tags_from_authoritative_scores():
    generator = ReportGenerator.__new__(ReportGenerator)
    generator.score_accessor = MagicMock()
    generator.score_accessor.get_market_fit.return_value = 0.55
    generator.score_accessor.get_technical_feasibility.return_value = 0.90
    generator.score_accessor.get_seo_score_canonical.return_value = None

    solution = SimpleNamespace(
        market_fit_score=0.90,
        technical_feasibility_score=0.90,
        seo_scalability_score=None,
        novelty_score=0.45,
        obviousness_score=None,
        solo_dev_feasibility=0.85,
        build_feasibility_score=None,
        project_type="saas",
        data_access_model="public",
        estimated_indexable_pages=0,
        estimated_cac_organic=None,
        estimated_cac_organic_refined=None,
        programmatic_seo_opportunity=None,
        programmatic_seo_opportunity_refined=None,
        tags=IdeaTags(
            target_market="b2b",
            monetization="subscription",
            growth_channels=["content"],
            build_complexity="medium",
            strengths=["market-fit"],
            primary_strength="market-fit",
        ),
    )

    synced = generator._sync_solution_scores(solution)

    assert synced.market_fit_score == 0.55
    assert "market-fit" not in synced.tags.strengths
    assert synced.tags.strengths == ["quick-build", "solo-friendly"]
    assert synced.tags.primary_strength == "solo-friendly"
    assert synced.tags.build_complexity == "low"
    assert synced.tags.target_market == "b2b"
    assert synced.tags.monetization == "subscription"


def _idea(name: str, **overrides) -> BaseSolutionIdea:
    values = {
        "solution_name": name,
        "description": "A concrete solution.",
        "value_proposition": "A useful outcome.",
        "pain_points_addressed": ["A validated pain"],
        "core_features": ["Core feature"],
        "target_personas": ["Buyer"],
        "market_fit_score": 0.60,
        "technical_feasibility_score": 0.70,
        "novelty_score": 0.45,
        "seo_scalability_score": 0.50,
        "project_type": "saas",
    }
    values.update(overrides)
    return BaseSolutionIdea(**values)


def test_alternative_tags_follow_the_authoritative_scores():
    selected = _idea("Selected idea")
    runner_up = _idea(
        "Runner-up idea",
        market_fit_score=0.90,
        technical_feasibility_score=0.90,
        solo_dev_feasibility=0.85,
        tags=IdeaTags(
            target_market="b2b",
            monetization="subscription",
            strengths=["market-fit"],
            primary_strength="market-fit",
        ),
    )
    state = ResearchState(
        idea_generation=IdeaGenerationResult(
            solution_ideas=[selected, runner_up, _idea("Third idea")]
        ),
        solution_selection=SolutionSelection(
            selected_solution_name=selected.solution_name,
            selection_rationale="The selected idea is the strongest grounded choice. " * 3,
            runner_up_solutions=[runner_up.solution_name],
            recommended_focus="Start with the narrowest validated buyer.",
            all_solution_scores=[
                SolutionScores(
                    solution_name=selected.solution_name,
                    market_fit_score=0.60,
                    technical_feasibility_score=0.70,
                    competitive_advantage_score=0.45,
                    seo_growth_potential_score=0.50,
                    composite_score=0.56,
                    rank=1,
                ),
                SolutionScores(
                    solution_name=runner_up.solution_name,
                    market_fit_score=0.55,
                    technical_feasibility_score=0.90,
                    competitive_advantage_score=0.45,
                    seo_growth_potential_score=0.50,
                    composite_score=0.60,
                    rank=2,
                ),
            ],
        ),
    )

    alternative = ReportGenerator(state)._generate_alternative_solutions()[0]

    assert alternative.market_fit_score == 0.55
    assert alternative.tags is not None
    assert "market-fit" not in alternative.tags.strengths
    assert alternative.tags.strengths == ["quick-build", "solo-friendly"]
    assert alternative.tags.primary_strength == "solo-friendly"
    assert alternative.tags.target_market == "b2b"
    assert alternative.tags.monetization == "subscription"
