"""
Component integration tests for LLMService usage across the codebase.

Verifies that QueryGenerator, KeywordSeedGenerator, and validators
correctly use the centralized LLMService.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import BaseModel, Field

from nicheiq.utils.generation.query_generator import QueryGenerator
from nicheiq.utils.generation.keyword_seed_generator import KeywordSeedGenerator
from nicheiq.utils.validation.thread_validator import ThreadRelevanceValidator, BatchValidationResponse
from nicheiq.utils.validation.keyword_validator import KeywordRelevanceValidator, KeywordBatchValidation
from nicheiq.models.research_state import NicheContext
from nicheiq.models.solution_idea import SolutionIdea


class TestQueryGeneratorIntegration:
    """Verify QueryGenerator uses LLMService correctly."""

    @patch('nicheiq.utils.generation.query_generator.LLMService.invoke_plain')
    def test_uses_llm_service_invoke_plain(self, mock_invoke_plain):
        """Verify QueryGenerator calls LLMService.invoke_plain()."""
        # Setup
        mock_invoke_plain.return_value = '[]'  # Empty JSON array
        generator = QueryGenerator()

        # Test
        generator.generate_queries("test niche", num_queries=5)

        # Assert
        assert mock_invoke_plain.called
        assert mock_invoke_plain.call_count == 1

    @patch('nicheiq.utils.generation.query_generator.LLMService.invoke_plain')
    def test_passes_correct_temperature(self, mock_invoke_plain):
        """Verify temperature=0.7 is passed."""
        # Setup
        mock_invoke_plain.return_value = '[]'
        generator = QueryGenerator()

        # Test
        generator.generate_queries("test niche")

        # Assert
        call_kwargs = mock_invoke_plain.call_args[1]
        assert call_kwargs['temperature'] == 0.7

    @patch('nicheiq.utils.generation.query_generator.LLMService.invoke_plain')
    @patch('nicheiq.utils.generation.query_generator.settings')
    def test_passes_settings_model_name(self, mock_settings, mock_invoke_plain):
        """Verify settings.openai_model_name is passed."""
        # Setup
        mock_settings.openai_model_name = "gpt-4o"
        mock_invoke_plain.return_value = '[]'
        generator = QueryGenerator()

        # Test
        generator.generate_queries("test niche")

        # Assert
        call_kwargs = mock_invoke_plain.call_args[1]
        assert call_kwargs['model_name'] == "gpt-4o"

    @patch('nicheiq.utils.generation.query_generator.LLMService.invoke_plain')
    def test_handles_llm_service_errors(self, mock_invoke_plain):
        """Verify error handling when LLMService raises exception."""
        # Setup - LLMService raises exception
        mock_invoke_plain.side_effect = Exception("API error")
        generator = QueryGenerator()

        # Test
        result = generator.generate_queries("test niche")

        # Assert - should return empty list on error
        assert result == []


class TestKeywordSeedGeneratorIntegration:
    """Verify KeywordSeedGenerator uses LLMService correctly."""

    @patch('nicheiq.utils.generation.keyword_seed_generator.LLMService.invoke_structured')
    def test_uses_llm_service_invoke_structured(self, mock_invoke_structured):
        """Verify KeywordSeedGenerator calls LLMService.invoke_structured()."""
        # Setup
        from nicheiq.models.seo_strategy import ExpandedKeywordList, ConceptualKeyword, ConceptualTopicCluster
        mock_result = ExpandedKeywordList(
            keywords=[
                ConceptualKeyword(keyword="test", priority=1, cluster="test cluster")
            ],
            topic_clusters=[
                ConceptualTopicCluster(name="test", description="test", strategic_importance=1)
            ],
            expansion_rationale="test rationale"
        )
        mock_invoke_structured.return_value = mock_result

        generator = KeywordSeedGenerator()
        solution = SolutionIdea(
            solution_name="TestSolution",
            description="Test description for testing. This is a detailed description. It has multiple sentences. The solution provides value.",
            value_proposition="Test value prop",
            pain_points_addressed=["pain1"],
            core_features=["feature1"],
            target_personas=["persona1"],
            project_type="saas",
            market_fit_score=0.8
        )

        # Test
        generator.generate_seeds(solution=solution)

        # Assert
        assert mock_invoke_structured.called
        assert mock_invoke_structured.call_count == 1

    @patch('nicheiq.utils.generation.keyword_seed_generator.LLMService.invoke_structured')
    def test_passes_correct_temperature(self, mock_invoke_structured):
        """Verify temperature=0.5 is passed."""
        # Setup
        from nicheiq.models.seo_strategy import ExpandedKeywordList, ConceptualKeyword, ConceptualTopicCluster
        mock_result = ExpandedKeywordList(
            keywords=[ConceptualKeyword(keyword="test", priority=1, cluster="test")],
            topic_clusters=[ConceptualTopicCluster(name="t", description="t", strategic_importance=1)],
            expansion_rationale="test"
        )
        mock_invoke_structured.return_value = mock_result

        generator = KeywordSeedGenerator()
        solution = SolutionIdea(
            solution_name="Test",
            description="Test description. More text. Another sentence. Final sentence for length.",
            value_proposition="Test",
            pain_points_addressed=["p"],
            core_features=["f"],
            target_personas=["t"],
            project_type="saas",
            market_fit_score=0.8
        )

        # Test
        generator.generate_seeds(solution)

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['temperature'] == 0.5

    @patch('nicheiq.utils.generation.keyword_seed_generator.LLMService.invoke_structured')
    def test_passes_expanded_keyword_list_model(self, mock_invoke_structured):
        """Verify ExpandedKeywordList is passed as output_model."""
        # Setup
        from nicheiq.models.seo_strategy import ExpandedKeywordList, ConceptualKeyword, ConceptualTopicCluster
        mock_result = ExpandedKeywordList(
            keywords=[ConceptualKeyword(keyword="test", priority=1, cluster="test")],
            topic_clusters=[ConceptualTopicCluster(name="t", description="t", strategic_importance=1)],
            expansion_rationale="test"
        )
        mock_invoke_structured.return_value = mock_result

        generator = KeywordSeedGenerator()
        solution = SolutionIdea(
            solution_name="Test",
            description="Descr. More. Again. Final.",
            value_proposition="V",
            pain_points_addressed=["p"],
            core_features=["f"],
            target_personas=["t"],
            project_type="saas",
            market_fit_score=0.8
        )

        # Test
        generator.generate_seeds(solution)

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['output_model'] == ExpandedKeywordList


class TestValidatorsIntegration:
    """Verify validators use LLMService correctly."""

    @patch('nicheiq.utils.validation.thread_validator.LLMService.invoke_structured')
    def test_thread_validator_uses_llm_service(self, mock_invoke_structured):
        """Verify ThreadRelevanceValidator uses LLMService."""
        # Setup
        from nicheiq.models.research_state import SearchResultItem
        from nicheiq.utils.validation.thread_validator import ValidationResult

        mock_result = BatchValidationResponse(
            results=[ValidationResult(thread_index=0, is_relevant=True, confidence=0.9, reason="test")]
        )
        mock_invoke_structured.return_value = mock_result

        validator = ThreadRelevanceValidator()
        search_results = [
            SearchResultItem(
                url="http://test.com",
                title="Test",
                snippet="test snippet"
            )
        ]

        # Test
        validator.validate_batch("test niche", search_results)

        # Assert
        assert mock_invoke_structured.called

    @patch('nicheiq.utils.validation.thread_validator.LLMService.invoke_structured')
    @patch('nicheiq.utils.validation.thread_validator.settings')
    def test_thread_validator_uses_thread_validation_llm(self, mock_settings, mock_invoke_structured):
        """Verify settings.thread_validation_llm is used."""
        # Setup
        mock_settings.thread_validation_llm = "gpt-4o-mini"
        from nicheiq.models.research_state import SearchResultItem
        from nicheiq.utils.validation.thread_validator import ValidationResult

        mock_result = BatchValidationResponse(
            results=[ValidationResult(thread_index=0, is_relevant=True, confidence=0.9, reason="test")]
        )
        mock_invoke_structured.return_value = mock_result

        validator = ThreadRelevanceValidator()
        search_results = [
            SearchResultItem(
                url="http://test.com",
                title="Test",
                snippet="test snippet"
            )
        ]

        # Test
        validator.validate_batch("test niche", search_results)

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['model_name'] == "gpt-4o-mini"

    @patch('nicheiq.utils.validation.thread_validator.LLMService.invoke_structured')
    def test_thread_validator_temperature_zero(self, mock_invoke_structured):
        """Verify thread validator uses temperature=0 for deterministic validation."""
        # Setup
        from nicheiq.models.research_state import SearchResultItem
        from nicheiq.utils.validation.thread_validator import ValidationResult

        mock_result = BatchValidationResponse(
            results=[ValidationResult(thread_index=0, is_relevant=True, confidence=0.9, reason="test")]
        )
        mock_invoke_structured.return_value = mock_result

        validator = ThreadRelevanceValidator()
        search_results = [
            SearchResultItem(url="http://t", title="T", snippet="s")
        ]

        # Test
        validator.validate_batch("niche", search_results)

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['temperature'] == 0

    @patch('nicheiq.utils.validation.keyword_validator.LLMService.invoke_structured')
    def test_keyword_validator_uses_llm_service(self, mock_invoke_structured):
        """Verify KeywordRelevanceValidator uses LLMService."""
        # Setup
        from nicheiq.utils.validation.keyword_validator import KeywordRelevance

        mock_result = KeywordBatchValidation(
            results=[
                KeywordRelevance(
                    keyword="test keyword",
                    is_relevant=True,
                    relevance_score=0.9,
                    reason="relevant"
                )
            ]
        )
        mock_invoke_structured.return_value = mock_result

        validator = KeywordRelevanceValidator()
        keywords = [{"keyword": "test keyword"}]

        # Test
        validator.validate_batch(
            keywords=keywords,
            niche_description="test niche",
            solution_name="test solution",
            solution_description="test solution description",
            project_type="saas"
        )

        # Assert
        assert mock_invoke_structured.called

    @patch('nicheiq.utils.validation.keyword_validator.LLMService.invoke_structured')
    @patch('nicheiq.utils.validation.keyword_validator.settings')
    def test_keyword_validator_uses_keyword_validation_llm(self, mock_settings, mock_invoke_structured):
        """Verify settings.keyword_validation_llm is used."""
        # Setup
        mock_settings.keyword_validation_llm = "gpt-4o-mini"
        from nicheiq.utils.validation.keyword_validator import KeywordRelevance

        mock_result = KeywordBatchValidation(
            results=[
                KeywordRelevance(
                    keyword="test",
                    is_relevant=True,
                    relevance_score=0.8,
                    reason="test"
                )
            ]
        )
        mock_invoke_structured.return_value = mock_result

        validator = KeywordRelevanceValidator()
        keywords = [{"keyword": "test keyword"}]  # Multi-word to pass pre-filter

        # Test
        validator.validate_batch(
            keywords=keywords,
            niche_description="niche",
            solution_name="solution",
            solution_description="solution description",
            project_type="saas"
        )

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['model_name'] == "gpt-4o-mini"

    @patch('nicheiq.utils.validation.keyword_validator.LLMService.invoke_structured')
    def test_keyword_validator_temperature_zero(self, mock_invoke_structured):
        """Verify keyword validator uses temperature=0 for deterministic validation."""
        # Setup
        from nicheiq.utils.validation.keyword_validator import KeywordRelevance

        mock_result = KeywordBatchValidation(
            results=[
                KeywordRelevance(keyword="test", is_relevant=True, relevance_score=0.8, reason="t")
            ]
        )
        mock_invoke_structured.return_value = mock_result

        validator = KeywordRelevanceValidator()
        keywords = [{"keyword": "test keyword"}]  # Multi-word to pass pre-filter

        # Test
        validator.validate_batch(
            keywords=keywords,
            niche_description="n",
            solution_name="s",
            solution_description="desc",
            project_type="saas"
        )

        # Assert
        call_kwargs = mock_invoke_structured.call_args[1]
        assert call_kwargs['temperature'] == 0
