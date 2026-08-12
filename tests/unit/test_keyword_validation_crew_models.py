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


class TestDifficultyAdjustedScore:
    """Demand rescale (flow-weakness fix plan 2026-08, Step 2): the Stage 6-KV
    difficulty-adjusted recompute mirrors the producer formula in
    seed_generation.calculate_validation_from_expansion, and emits None (not the
    stale scalar) on an empty validated set."""

    def _make_result(self, **overrides):
        defaults = dict(
            solution_name="Test Solution",
            validated_count=10,
            total_volume=10000,
            avg_competition=40.0,
            keyword_demand_score=0.61,
            demand_signal="moderate",
            validation_signals={"has_search_demand": True},
            attempts_made=1,
            best_relevance_score=0.7,
        )
        defaults.update(overrides)
        return CrewKeywordValidationResult(**defaults)

    def test_producer_formula_recompute_from_validated_keywords(self):
        """Case (a): per-keyword producer formula — volume_factor × competition_factor
        × saturation_check, averaged — plus volume_score = min(validated_count/20, 1)."""
        from nicheiq.flows.research_flow import _calculate_difficulty_adjusted_score

        result = self._make_result(
            validated_count=10,
            validated_keywords=[
                # vf=0.5, cf=0.7, sat=1.0 (competition 30 <= 60) -> 0.35
                {"keyword": "a", "search_volume": 500, "competition_index": 30, "keyword_difficulty": 20},
                # vf=1.0 (capped), cf=0.3, sat=0.7 (competition 70 > 60) -> 0.21
                {"keyword": "b", "search_volume": 2000, "competition_index": 70, "keyword_difficulty": 40},
            ],
        )
        score, avg_diff, rankability = _calculate_difficulty_adjusted_score(result)
        # volume_score = len(validated_keywords)/20 = 2/20 = 0.1 — the numerator is
        # the GRADED set, not validated_count (=10, the unfiltered expansion pool).
        # avg_opportunity = (0.35+0.21)/2 = 0.28; rankability = 1 - 30/100 = 0.7
        # score = 0.55*0.1 + 0.25*0.28 + 0.20*0.7 = 0.265
        assert score == pytest.approx(0.265)
        assert avg_diff == pytest.approx(30.0)
        assert rankability == pytest.approx(0.7)

    def test_no_difficulty_data_falls_back_to_60_40(self):
        """Without any keyword_difficulty, the producer's 60/40 weights apply."""
        from nicheiq.flows.research_flow import _calculate_difficulty_adjusted_score

        # volume_score uses len(validated_keywords) (the graded, on-idea set) —
        # NOT validated_count, which counts the unfiltered expansion pool.
        result = self._make_result(
            validated_count=40,  # deliberately large: must NOT influence the score
            validated_keywords=[
                {"keyword": f"kw{i}", "search_volume": 1000, "competition_index": 0}
                for i in range(20)  # 20 graded keywords -> volume_score caps at 1.0
            ],
        )
        score, avg_diff, rankability = _calculate_difficulty_adjusted_score(result)
        assert score == pytest.approx(0.60 * 1.0 + 0.40 * 1.0)
        assert avg_diff is None
        assert rankability is None

    def test_empty_validated_keywords_emits_measured_zero(self):
        """Case (b): a completed, relevance-qualified search with no matches is measured zero."""
        from nicheiq.flows.research_flow import _calculate_difficulty_adjusted_score

        result = self._make_result(validated_count=0, validated_keywords=[])
        assert _calculate_difficulty_adjusted_score(result) == (0.0, None, None)

    def test_legacy_record_missing_validated_keywords_no_crash(self):
        """Case (c): legacy checkpoints have validated_keywords=None — unmeasured, no crash."""
        from nicheiq.flows.research_flow import _calculate_difficulty_adjusted_score

        result = self._make_result()  # validated_keywords defaults to None
        assert result.validated_keywords is None
        assert _calculate_difficulty_adjusted_score(result) == (None, None, None)

    def test_measurement_state_distinguishes_zero_from_unmeasured(self):
        from nicheiq.flows.research_flow import _keyword_demand_measurement_state

        measured = self._make_result(validated_count=0, validated_keywords=[])
        legacy = self._make_result()
        assert _keyword_demand_measurement_state(measured) == (0.0, False)
        assert _keyword_demand_measurement_state(legacy) == (None, True)

    def test_missing_metric_keys_treated_as_zero(self):
        """Keywords lacking search_volume/competition_index (or carrying None) are
        None-safe: volume 0 -> vf 0; competition 0 -> cf 1.0, sat 1.0."""
        from nicheiq.flows.research_flow import _calculate_difficulty_adjusted_score

        result = self._make_result(
            validated_count=4,
            validated_keywords=[
                {"keyword": "bare"},
                {"keyword": "nulls", "search_volume": None, "competition_index": None},
            ],
        )
        score, avg_diff, rankability = _calculate_difficulty_adjusted_score(result)
        # volume_score = len(validated_keywords)/20 = 2/20 = 0.1 (validated_count=4
        # is the unfiltered pool count and must not be used); avg_opportunity = 0.0;
        # no difficulty -> 60/40
        assert score == pytest.approx(0.60 * 0.1)
        assert avg_diff is None
        assert rankability is None


class TestValidatedCountContract:
    """`validated_count` means the GRADED, on-idea keyword set — never the unfiltered
    expansion pool (Codex review 2026-08 §4b). Measured live 2026-08-02:
    validated_count=50 while len(validated_keywords)=1, and every consumer
    (selection rationale, progress payload, report table, market-sizing prompt)
    republished the 50 as validated evidence."""

    def _make_result(self, **overrides):
        defaults = dict(
            solution_name="Test Solution",
            validated_count=3,
            total_volume=10000,
            avg_competition=40.0,
            keyword_demand_score=0.61,
            demand_signal="moderate",
            validation_signals={"has_search_demand": True},
            attempts_made=1,
            best_relevance_score=0.7,
        )
        defaults.update(overrides)
        return CrewKeywordValidationResult(**defaults)

    def test_graded_count_uses_validated_keywords(self):
        result = self._make_result(
            validated_count=3,
            validated_keywords=[{"keyword": "a"}, {"keyword": "b"}, {"keyword": "c"}],
        )
        assert result.graded_keyword_count == 3

    def test_graded_count_heals_legacy_pool_count(self):
        """Legacy checkpoint shape: pool count stored in validated_count. The graded
        list wins, so old checkpoints stop inflating the reports they feed."""
        result = self._make_result(
            validated_count=50,
            validated_keywords=[{"keyword": "the one on-idea keyword"}],
        )
        assert result.graded_keyword_count == 1

    def test_graded_count_zero_for_graded_and_empty(self):
        """Graded-and-empty is 0 evidence, not the stale pre-grading count."""
        result = self._make_result(validated_count=50, validated_keywords=[])
        assert result.graded_keyword_count == 0

    def test_graded_count_falls_back_when_list_never_persisted(self):
        """validated_keywords=None means the list predates the field — only then may
        validated_count stand in."""
        result = self._make_result(validated_count=7)
        assert result.validated_keywords is None
        assert result.graded_keyword_count == 7


class TestFinalizeGradedValidation:
    """research_flow.finalize_graded_validation() is the single place the producer's
    expansion-pool count is swapped for the graded count."""

    def _raw_metrics(self, pool_count=50):
        return {
            "solution_name": "Test Solution",
            "expansion_pool_count": pool_count,
            "total_volume": 10000,
            "avg_competition": 40.0,
            "keyword_demand_score": 0.61,
            "top_keywords": [],
            "top_geographic_keywords": [],
            "demand_signal": "moderate",
            "validation_signals": {"has_search_demand": True},
            "attempts_made": 1,
            "best_relevance_score": 0.7,
        }

    def test_stamps_graded_count_and_drops_pool_count(self):
        from nicheiq.flows.research_flow import finalize_graded_validation

        graded = [{"keyword": "vet medication audit", "search_volume": 90}]
        out = finalize_graded_validation(self._raw_metrics(pool_count=50), graded)

        assert out["validated_count"] == 1
        assert out["accumulated_keywords_count"] == 1
        assert out["validated_keywords"] == graded
        assert "expansion_pool_count" not in out

    def test_result_is_model_constructible(self):
        from nicheiq.flows.research_flow import finalize_graded_validation

        out = finalize_graded_validation(self._raw_metrics(), [{"keyword": "a"}])
        model = CrewKeywordValidationResult(**out)
        assert model.validated_count == model.graded_keyword_count == 1

    def test_raw_producer_dict_cannot_build_the_model(self):
        """extra='forbid' is the enforcement: skipping the swap fails loudly instead
        of silently republishing the pool count as validated evidence."""
        with pytest.raises(Exception):
            CrewKeywordValidationResult(**self._raw_metrics())

    def test_empty_graded_set_stamps_zero(self):
        from nicheiq.flows.research_flow import finalize_graded_validation

        out = finalize_graded_validation(self._raw_metrics(pool_count=50), [])
        assert out["validated_count"] == 0
