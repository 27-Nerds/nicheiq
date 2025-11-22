"""
Tests for Pydantic data models.
"""

from datetime import datetime

import pytest
from nicheiq.models.keyword_data import Keyword, KeywordIntent, KeywordResearchReport, OpportunityLevel
from nicheiq.models.pain_point import PainPoint, PainPointAnalysisResult
from nicheiq.models.solution_idea import IdeaGenerationResult, SolutionIdea


class TestPainPointModel:
    """Tests for PainPoint model."""

    def test_pain_point_creation(self):
        """Test creating a valid PainPoint."""
        pain_point = PainPoint(
            title="Manual data entry is time-consuming",
            description="Users spend 3-5 hours daily on manual data entry",
            mention_count=15,
            severity_score=0.8,
            willingness_to_pay=0.7,
            representative_quotes=["I waste so much time on this", "Need automation ASAP"],
            source_platforms=["reddit", "twitter"],
            categories=["workflow inefficiency"],
            opportunity_level=OpportunityLevel.HIGH,
        )

        assert pain_point.title == "Manual data entry is time-consuming"
        assert pain_point.mention_count == 15
        assert 0.0 <= pain_point.severity_score <= 1.0
        assert 0.0 <= pain_point.willingness_to_pay <= 1.0

    def test_pain_point_score_validation(self):
        """Test that scores are validated within 0-1 range."""
        with pytest.raises(ValueError):
            PainPoint(
                title="Test",
                description="Test description",
                mention_count=5,
                severity_score=1.5,  # Invalid: > 1.0
                willingness_to_pay=0.5,
                representative_quotes=["quote"],
                source_platforms=["reddit"],
                categories=["test"],
            )

    def test_pain_point_analysis_result(self):
        """Test PainPointAnalysisResult aggregation."""
        pain_points = [
            PainPoint(
                title="Problem 1",
                description="Description 1",
                mention_count=10,
                severity_score=0.8,
                willingness_to_pay=0.7,
                representative_quotes=["quote"],
                source_platforms=["reddit"],
                categories=["category1"],
                opportunity_level=OpportunityLevel.HIGH,
            ),
            PainPoint(
                title="Problem 2",
                description="Description 2",
                mention_count=5,
                severity_score=0.6,
                willingness_to_pay=0.5,
                representative_quotes=["quote"],
                source_platforms=["twitter"],
                categories=["category2"],
                opportunity_level=OpportunityLevel.MEDIUM,
            ),
        ]

        result = PainPointAnalysisResult(
            niche="test niche",
            pain_points=pain_points,
            total_mentions=15,
            top_categories=["category1", "category2"],
            analysis_summary="Test summary",
        )

        assert len(result.pain_points) == 2
        assert result.total_mentions == 15


class TestKeywordModel:
    """Tests for Keyword model."""

    def test_keyword_creation(self):
        """Test creating a valid Keyword."""
        keyword = Keyword(
            keyword="project management software",
            search_volume=5000,
            competition=0.4,
            search_intent=KeywordIntent.COMMERCIAL,
            opportunity_level=OpportunityLevel.HIGH,
        )

        assert keyword.keyword == "project management software"
        assert keyword.search_volume == 5000
        assert keyword.opportunity_level == OpportunityLevel.HIGH

    def test_opportunity_levels(self):
        """Test OpportunityLevel enum values."""
        assert OpportunityLevel.HIGH.value == "high"
        assert OpportunityLevel.MEDIUM.value == "medium"
        assert OpportunityLevel.LOW.value == "low"

    def test_keyword_intent_types(self):
        """Test KeywordIntent enum values."""
        assert KeywordIntent.COMMERCIAL.value == "commercial"
        assert KeywordIntent.INFORMATIONAL.value == "informational"
        assert KeywordIntent.TRANSACTIONAL.value == "transactional"
        assert KeywordIntent.NAVIGATIONAL.value == "navigational"


class TestSolutionIdeaModel:
    """Tests for SolutionIdea model."""

    def test_solution_idea_creation(self):
        """Test creating a valid SolutionIdea."""
        idea = SolutionIdea(
            solution_name="TaskFlow Pro",
            value_proposition="Automate project management for remote teams",
            pain_points_addressed=["Manual task tracking", "Poor team visibility"],
            description="A comprehensive project management solution",
            target_personas=["Remote team managers", "Startup founders"],
            core_features=["Task automation", "Real-time dashboards", "Slack integration"],
            technical_approach="React frontend with Python backend",
            differentiation_factors=["AI-powered task prioritization"],
            estimated_development_time="4-6 months",
            pricing_strategy="$29/user/month with 14-day trial",
            market_fit_score=0.85,
            technical_feasibility_score=0.9,
        )

        assert idea.solution_name == "TaskFlow Pro"
        assert len(idea.pain_points_addressed) == 2
        assert 0.0 <= idea.market_fit_score <= 1.0
        assert 0.0 <= idea.technical_feasibility_score <= 1.0
