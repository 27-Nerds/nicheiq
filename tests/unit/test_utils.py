"""
Tests for utility functions.
"""

import pytest


# Note: SearchHelper tests removed - extract_urls() method no longer exists
# URL extraction is now handled internally by the flow


# Note: QueryGenerator tests are skipped as they require OpenAI API
# Integration tests should cover the full query generation workflow
@pytest.mark.skip(reason="Requires OpenAI API key")
class TestQueryGenerator:
    """Tests for LLM-based query generation (requires API)."""

    def test_query_generation(self):
        """Test generating queries from niche description."""
        from nicheiq.utils.generation import QueryGenerator

        generator = QueryGenerator()
        queries = generator.generate_queries(
            niche_description="AI tools for content creators", num_queries=5
        )

        assert len(queries) <= 5
        assert all("query" in q for q in queries)
        assert all("type" in q for q in queries)
