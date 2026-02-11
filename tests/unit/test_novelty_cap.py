"""
Tests for novelty_score capping post-processing logic.

The novelty cap is applied in UnifiedSolutionCrew.execute_pipeline() after Task 3
output is parsed. This test validates the capping logic in isolation.
"""

import pytest

from nicheiq.models.solution_idea import BaseSolutionIdea


def _make_solution(**overrides) -> BaseSolutionIdea:
    """Helper to create a minimal BaseSolutionIdea for testing."""
    defaults = {
        "solution_name": "TestSolution",
        "description": "A test solution that does something useful for users.",
        "value_proposition": "Test value prop",
        "pain_points_addressed": ["Pain point 1"],
        "core_features": ["Feature 1", "Feature 2"],
        "target_personas": ["Persona 1"],
        "technical_approach": "Standard web app",
        "differentiation_factors": ["Factor 1"],
        "requires_data_aggregation": False,
        "data_sources": [],
        "estimated_development_time": "2-3 months",
        "pricing_strategy": "Freemium model",
        "market_fit_score": 0.7,
        "technical_feasibility_score": 0.8,
        "project_type": "saas",
        "programmatic_seo_opportunity": "Good opportunity",
        "content_generation_model": "Template-based",
        "organic_discovery_queries": ["query 1", "query 2"],
        "estimated_cac_organic": "$5-15",
        "estimated_cac_paid": "$20-40",
        "seo_scalability_score": 0.7,
        "novelty_score": 0.5,
        "conventional_approach": "Most would build a generic tool.",
        "innovation_angle": "This uses a unique data source.",
        "why_it_works": "Evidence from community discussions.",
        "solo_dev_feasibility": 0.8,
    }
    defaults.update(overrides)
    return BaseSolutionIdea(**defaults)


def _apply_novelty_cap(solutions: list[BaseSolutionIdea]) -> list[BaseSolutionIdea]:
    """
    Replicate the post-processing logic from execute_pipeline().

    This is extracted to test independently without mocking the entire crew pipeline.
    """
    for solution in solutions:
        if solution.novelty_score and solution.novelty_score > 0.45:
            ca = (solution.conventional_approach or "").strip()
            ia = (solution.innovation_angle or "").strip()
            wiw = (solution.why_it_works or "").strip()
            if len(ca) < 30 or len(ia) < 30 or len(wiw) < 30:
                solution.novelty_score = 0.45
    return solutions


class TestNoveltyCap:
    """Tests for novelty_score capping post-processing."""

    def test_high_novelty_with_short_conventional_approach_capped(self):
        """novelty_score 0.8 with short conventional_approach → capped to 0.45."""
        solution = _make_solution(
            novelty_score=0.8,
            conventional_approach="Standard tool.",  # < 30 chars
            innovation_angle="This uses a completely different data pipeline architecture with novel aggregation.",
            why_it_works="Community data shows 85% of users want this specific feature badly.",
        )
        _apply_novelty_cap([solution])
        assert solution.novelty_score == 0.45

    def test_high_novelty_with_short_innovation_angle_capped(self):
        """novelty_score 0.8 with short innovation_angle → capped to 0.45."""
        solution = _make_solution(
            novelty_score=0.8,
            conventional_approach="Most would build a full-featured comparison platform with reviews and editorial.",
            innovation_angle="Better UX design.",  # < 30 chars
            why_it_works="Community data shows 85% of users want this specific feature badly.",
        )
        _apply_novelty_cap([solution])
        assert solution.novelty_score == 0.45

    def test_high_novelty_with_short_why_it_works_capped(self):
        """novelty_score 0.8 with short why_it_works → capped to 0.45."""
        solution = _make_solution(
            novelty_score=0.8,
            conventional_approach="Most would build a full-featured comparison platform with reviews and editorial.",
            innovation_angle="This uses a completely different data pipeline architecture with novel aggregation.",
            why_it_works="Users want this.",  # < 30 chars
        )
        _apply_novelty_cap([solution])
        assert solution.novelty_score == 0.45

    def test_high_novelty_with_long_text_fields_not_capped(self):
        """novelty_score 0.8 with all long text fields → not capped."""
        solution = _make_solution(
            novelty_score=0.8,
            conventional_approach="Most would build a full-featured comparison platform with user reviews and editorial content.",
            innovation_angle="This focuses exclusively on automated speed tests from 50+ global locations publishing objective data.",
            why_it_works="Community threads show users distrust subjective reviews and specifically ask for real-world speed data.",
        )
        _apply_novelty_cap([solution])
        assert solution.novelty_score == 0.8

    def test_low_novelty_not_affected(self):
        """novelty_score <= 0.45 → not touched regardless of text quality."""
        solution = _make_solution(
            novelty_score=0.4,
            conventional_approach="Short.",
            innovation_angle="Short.",
            why_it_works="Short.",
        )
        _apply_novelty_cap([solution])
        assert solution.novelty_score == 0.4

    def test_none_novelty_score_not_affected(self):
        """novelty_score is None → not touched."""
        solution = _make_solution(novelty_score=None)
        _apply_novelty_cap([solution])
        assert solution.novelty_score is None

    def test_multiple_solutions_capped_independently(self):
        """Each solution is evaluated independently."""
        good = _make_solution(
            solution_name="GoodSolution",
            novelty_score=0.8,
            conventional_approach="Most would build a full-featured comparison platform with editorial.",
            innovation_angle="This uses automated speed tests from 50+ global locations publishing data.",
            why_it_works="Community threads show users distrust reviews and ask for speed data.",
        )
        weak = _make_solution(
            solution_name="WeakSolution",
            novelty_score=0.75,
            conventional_approach="Generic tool.",  # < 30 chars
            innovation_angle="This uses automated speed tests from 50+ global locations publishing data.",
            why_it_works="Community threads show users distrust reviews and ask for speed data.",
        )
        _apply_novelty_cap([good, weak])
        assert good.novelty_score == 0.8
        assert weak.novelty_score == 0.45
