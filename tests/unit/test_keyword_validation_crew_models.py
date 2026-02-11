"""
Tests for Keyword Validation Crew Pydantic models.

Validates model_dump() compatibility with Stage 5.8 expectations
and ensures proper serialization for solution refinement logic.
"""

import pytest
from nicheiq.models.keyword_data import (
    CrewKeywordValidationResult,
    EnrichedKeyword,
    KeywordAttemptResult,
)


class TestEnrichedKeyword:
    """Tests for EnrichedKeyword model."""

    def test_enriched_keyword_creation(self):
        """Test creating a valid EnrichedKeyword."""
        keyword = EnrichedKeyword(
            keyword="expat health insurance",
            search_volume=3200,
            competition=0.42,
            cpc=2.50,
            tier="quick_win",
            geography="spain"
        )

        assert keyword.keyword == "expat health insurance"
        assert keyword.search_volume == 3200
        assert keyword.competition == 0.42
        assert keyword.cpc == 2.50
        assert keyword.tier == "quick_win"
        assert keyword.geography == "spain"

    def test_enriched_keyword_optional_fields(self):
        """Test EnrichedKeyword with optional fields as None."""
        keyword = EnrichedKeyword(
            keyword="expat relocation",
            search_volume=1500,
            competition=0.35
        )

        assert keyword.cpc is None
        assert keyword.tier is None
        assert keyword.geography is None

    def test_enriched_keyword_validation(self):
        """Test that search_volume and competition are validated."""
        # Test negative search volume
        with pytest.raises(ValueError):
            EnrichedKeyword(
                keyword="test",
                search_volume=-10,
                competition=0.5
            )

        # Test competition out of range
        with pytest.raises(ValueError):
            EnrichedKeyword(
                keyword="test",
                search_volume=100,
                competition=1.5
            )


class TestKeywordAttemptResult:
    """Tests for KeywordAttemptResult model."""

    def test_keyword_attempt_result_creation(self):
        """Test creating a valid KeywordAttemptResult."""
        keywords = [
            EnrichedKeyword(keyword="expat health insurance", search_volume=3200, competition=0.42),
            EnrichedKeyword(keyword="relocation services", search_volume=2100, competition=0.38)
        ]

        result = KeywordAttemptResult(
            strategy_name="hybrid",
            keywords=keywords,
            total_keywords=2,
            avg_relevance_score=0.78,
            quality_flag="SUCCESS",
            error_log=None
        )

        assert result.strategy_name == "hybrid"
        assert len(result.keywords) == 2
        assert result.total_keywords == 2
        assert result.avg_relevance_score == 0.78
        assert result.quality_flag == "SUCCESS"
        assert result.error_log is None

    def test_keyword_attempt_result_insufficient_quality(self):
        """Test KeywordAttemptResult with INSUFFICIENT quality flag."""
        result = KeywordAttemptResult(
            strategy_name="competitor",
            keywords=[],
            total_keywords=0,
            avg_relevance_score=0.32,
            quality_flag="INSUFFICIENT",
            error_log="No competitors found in niche context"
        )

        assert result.quality_flag == "INSUFFICIENT"
        assert result.total_keywords == 0
        assert result.error_log is not None

    def test_keyword_attempt_result_relevance_validation(self):
        """Test that avg_relevance_score is validated within 0.0-1.0."""
        with pytest.raises(ValueError):
            KeywordAttemptResult(
                strategy_name="hybrid",
                keywords=[],
                total_keywords=0,
                avg_relevance_score=1.5,  # Invalid: > 1.0
                quality_flag="INSUFFICIENT"
            )


class TestCrewKeywordValidationResult:
    """Tests for CrewKeywordValidationResult model and model_dump() compatibility."""

    @pytest.fixture
    def sample_validation_result(self):
        """Create a sample CrewKeywordValidationResult for testing."""
        return CrewKeywordValidationResult(
            solution_name="ExpatEase Directory",
            validated_count=42,
            total_volume=18750,
            avg_competition=38.5,
            keyword_demand_score=0.78,
            top_keywords=[
                {"keyword": "expat health insurance", "volume": 3200, "competition": 0.42},
                {"keyword": "relocation services portugal", "volume": 2100, "competition": 0.38},
                {"keyword": "expat tax advisor spain", "volume": 1850, "competition": 0.35}
            ],
            top_geographic_keywords=[
                "expat services spain",
                "relocation portugal",
                "expat life barcelona"
            ],
            demand_signal="strong",
            validation_signals={
                "has_search_demand": True,
                "keyword_diversity": True,
                "high_volume_presence": True,
                "average_volume_per_keyword": 446.4
            },
            attempts_made=1,
            best_relevance_score=0.78,
            accumulated_keywords_count=42
        )

    def test_crew_keyword_validation_result_creation(self, sample_validation_result):
        """Test creating a valid CrewKeywordValidationResult."""
        result = sample_validation_result

        assert result.solution_name == "ExpatEase Directory"
        assert result.validated_count == 42
        assert result.total_volume == 18750
        assert result.avg_competition == 38.5
        assert result.keyword_demand_score == 0.78
        assert result.demand_signal == "strong"
        assert result.attempts_made == 1
        assert result.best_relevance_score == 0.78
        assert result.accumulated_keywords_count == 42

    def test_model_dump_produces_dict(self, sample_validation_result):
        """Test that model_dump() produces a dictionary."""
        result_dict = sample_validation_result.model_dump()

        assert isinstance(result_dict, dict)
        assert "solution_name" in result_dict
        assert "validated_count" in result_dict
        assert "total_volume" in result_dict

    def test_model_dump_contains_all_stage_5_8_fields(self, sample_validation_result):
        """Test that model_dump() contains ALL fields expected by Stage 5.8."""
        result_dict = sample_validation_result.model_dump()

        # Stage 5.8 compatibility fields (required for solution refinement)
        required_fields = [
            "solution_name",
            "validated_count",
            "total_volume",
            "avg_competition",
            "keyword_demand_score",
            "top_keywords",
            "top_geographic_keywords",
            "demand_signal",
            "validation_signals"
        ]

        for field in required_fields:
            assert field in result_dict, f"Missing required field: {field}"

    def test_model_dump_contains_crew_specific_fields(self, sample_validation_result):
        """Test that model_dump() contains crew-specific fields."""
        result_dict = sample_validation_result.model_dump()

        # Crew-specific fields (new in Stage 5.7)
        crew_fields = [
            "attempts_made",
            "best_relevance_score",
            "accumulated_keywords_count"
        ]

        for field in crew_fields:
            assert field in result_dict, f"Missing crew-specific field: {field}"

    def test_model_dump_values_match_input(self, sample_validation_result):
        """Test that model_dump() values match the original input values."""
        result_dict = sample_validation_result.model_dump()

        assert result_dict["solution_name"] == "ExpatEase Directory"
        assert result_dict["validated_count"] == 42
        assert result_dict["total_volume"] == 18750
        assert result_dict["keyword_demand_score"] == 0.78
        assert result_dict["demand_signal"] == "strong"
        assert result_dict["attempts_made"] == 1

    def test_model_dump_preserves_nested_structures(self, sample_validation_result):
        """Test that model_dump() preserves nested lists and dicts."""
        result_dict = sample_validation_result.model_dump()

        # Check top_keywords list structure
        assert isinstance(result_dict["top_keywords"], list)
        assert len(result_dict["top_keywords"]) == 3
        assert result_dict["top_keywords"][0]["keyword"] == "expat health insurance"
        assert result_dict["top_keywords"][0]["volume"] == 3200

        # Check top_geographic_keywords list
        assert isinstance(result_dict["top_geographic_keywords"], list)
        assert "expat services spain" in result_dict["top_geographic_keywords"]

        # Check validation_signals dict
        assert isinstance(result_dict["validation_signals"], dict)
        assert result_dict["validation_signals"]["has_search_demand"] is True
        assert result_dict["validation_signals"]["keyword_diversity"] is True

    def test_validation_score_bounds(self):
        """Test that validation scores are bounded correctly."""
        # Test valid boundaries
        result = CrewKeywordValidationResult(
            solution_name="Test Solution",
            validated_count=20,
            total_volume=5000,
            avg_competition=50.0,
            keyword_demand_score=0.0,  # Min valid
            demand_signal="weak",
            validation_signals={},
            attempts_made=4,
            best_relevance_score=1.0  # Max valid
        )
        assert result.keyword_demand_score == 0.0
        assert result.best_relevance_score == 1.0

        # Test invalid keyword_demand_score
        with pytest.raises(ValueError):
            CrewKeywordValidationResult(
                solution_name="Test",
                validated_count=0,
                total_volume=0,
                avg_competition=0.0,
                keyword_demand_score=1.5,  # Invalid: > 1.0
                demand_signal="weak",
                validation_signals={},
                attempts_made=1,
                best_relevance_score=0.5
            )

    def test_avg_competition_bounds(self):
        """Test that avg_competition is bounded 0.0-100.0."""
        with pytest.raises(ValueError):
            CrewKeywordValidationResult(
                solution_name="Test",
                validated_count=0,
                total_volume=0,
                avg_competition=150.0,  # Invalid: > 100.0
                keyword_demand_score=0.5,
                demand_signal="weak",
                validation_signals={},
                attempts_made=1,
                best_relevance_score=0.5
            )

    def test_attempts_made_bounds(self):
        """Test that attempts_made is bounded 1-4."""
        # Test max boundary
        result = CrewKeywordValidationResult(
            solution_name="Test",
            validated_count=0,
            total_volume=0,
            avg_competition=0.0,
            keyword_demand_score=0.0,
            demand_signal="weak",
            validation_signals={},
            attempts_made=4,  # Max valid
            best_relevance_score=0.0
        )
        assert result.attempts_made == 4

        # Test invalid (too many attempts)
        with pytest.raises(ValueError):
            CrewKeywordValidationResult(
                solution_name="Test",
                validated_count=0,
                total_volume=0,
                avg_competition=0.0,
                keyword_demand_score=0.0,
                demand_signal="weak",
                validation_signals={},
                attempts_made=5,  # Invalid: > 4
                best_relevance_score=0.0
            )

    def test_stage_5_8_compatibility_example(self):
        """
        Integration test: Verify model_dump() output can be used directly
        in Stage 5.8 solution refinement logic.
        """
        # Create result as crew would return it
        crew_result = CrewKeywordValidationResult(
            solution_name="NicheHire Marketplace",
            validated_count=35,
            total_volume=12500,
            avg_competition=42.3,
            keyword_demand_score=0.72,
            top_keywords=[
                {"keyword": "freelance platform rust", "volume": 2800, "competition": 0.38},
                {"keyword": "hire rust developers", "volume": 2100, "competition": 0.45}
            ],
            top_geographic_keywords=["freelance jobs remote", "tech talent berlin"],
            demand_signal="strong",
            validation_signals={
                "has_search_demand": True,
                "keyword_diversity": True,
                "high_volume_presence": True,
                "average_volume_per_keyword": 357.1
            },
            attempts_made=2,
            best_relevance_score=0.72,
            accumulated_keywords_count=68
        )

        # Convert to dict as Stage 5.8 expects
        refinement_input = crew_result.model_dump()

        # Verify Stage 5.8 can access all required fields
        assert refinement_input["solution_name"] == "NicheHire Marketplace"
        assert refinement_input["keyword_demand_score"] == 0.72
        assert refinement_input["demand_signal"] == "strong"
        assert refinement_input["validated_count"] == 35
        assert refinement_input["total_volume"] == 12500

        # Verify crew-specific metadata is preserved
        assert refinement_input["attempts_made"] == 2
        assert refinement_input["best_relevance_score"] == 0.72


class TestNicheRelevantVolume:
    """Tests for niche_relevant_volume field on CrewKeywordValidationResult."""

    def _make_result(self, **overrides):
        """Helper to create a CrewKeywordValidationResult with defaults."""
        defaults = dict(
            solution_name="Test Solution",
            validated_count=20,
            total_volume=10000,
            avg_competition=40.0,
            keyword_demand_score=0.6,
            demand_signal="moderate",
            validation_signals={"has_search_demand": True},
            attempts_made=1,
            best_relevance_score=0.7,
        )
        defaults.update(overrides)
        return CrewKeywordValidationResult(**defaults)

    def test_backward_compat_none_by_default(self):
        """Legacy data without niche_relevant_volume defaults to None."""
        result = self._make_result()
        assert result.niche_relevant_volume is None
        dumped = result.model_dump()
        assert dumped["niche_relevant_volume"] is None

    def test_with_value(self):
        """niche_relevant_volume can be set to a positive int."""
        result = self._make_result(niche_relevant_volume=5000)
        assert result.niche_relevant_volume == 5000

    def test_zero_is_valid(self):
        """niche_relevant_volume=0 is a valid value (no relevant keywords found)."""
        result = self._make_result(niche_relevant_volume=0)
        assert result.niche_relevant_volume == 0

    def test_negative_rejected(self):
        """Negative niche_relevant_volume is rejected by ge=0 constraint."""
        with pytest.raises(ValueError):
            self._make_result(niche_relevant_volume=-100)

    def test_model_dump_includes_field(self):
        """model_dump() includes niche_relevant_volume."""
        result = self._make_result(niche_relevant_volume=8000)
        dumped = result.model_dump()
        assert "niche_relevant_volume" in dumped
        assert dumped["niche_relevant_volume"] == 8000
