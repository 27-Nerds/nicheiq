"""
Tests for QuoteSearchTool - vector search wrapper for Task 4 quote enrichment.

Tests:
- Tool name and description
- Search result formatting with post_id
- Error handling (empty query, no knowledge, no results, exceptions)
"""

from unittest.mock import MagicMock

import pytest

from nicheiq.tools.quote_search_tool import QuoteSearchTool


class TestQuoteSearchToolBasics:
    """Tests for QuoteSearchTool basic properties."""

    def test_tool_name_and_description(self, mock_knowledge):
        """Verify tool name is 'search_discussions'."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        assert tool.name == "search_discussions"
        assert "search" in tool.description.lower()
        assert "post_id" in tool.description.lower()


class TestQuoteSearchToolRun:
    """Tests for QuoteSearchTool._run() method."""

    def test_run_returns_formatted_results_with_post_id(self, mock_knowledge):
        """Check output format includes post_id: xyz header."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        result = tool._run("manual invoicing pain")

        # Should contain post_id in result headers
        assert "post_id: abc123" in result
        assert "post_id: thread_xyz" in result

        # Should contain the content
        assert "3 hours every week" in result
        assert "Manual expense tracking" in result

    def test_run_formats_score_metadata(self, mock_knowledge):
        """Check score and source_type in output."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        result = tool._run("invoicing")

        # Should include score
        assert "score:" in result.lower()
        assert "0.92" in result

        # Should include source type
        assert "source: reddit" in result.lower()
        assert "source: twitter" in result.lower()

    def test_run_result_indexing(self, mock_knowledge):
        """Check result numbering (Result 1, Result 2, etc.)."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        result = tool._run("test query")

        assert "Result 1" in result
        assert "Result 2" in result


class TestQuoteSearchToolErrors:
    """Tests for QuoteSearchTool error handling."""

    def test_run_empty_query_returns_error(self, mock_knowledge):
        """Empty/whitespace query -> error message."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        # Empty string
        result = tool._run("")
        assert "error" in result.lower()
        assert "empty" in result.lower()

        # Whitespace only
        result = tool._run("   ")
        assert "error" in result.lower()

    def test_run_no_knowledge_returns_error(self):
        """knowledge=None -> 'not initialized' error."""
        tool = QuoteSearchTool(knowledge=None)

        result = tool._run("test query")

        assert "error" in result.lower()
        assert "not initialized" in result.lower()

    def test_run_no_results_returns_message(self, mock_knowledge_no_results):
        """No matches -> helpful retry message."""
        tool = QuoteSearchTool(knowledge=mock_knowledge_no_results)

        result = tool._run("obscure query nobody talks about")

        assert "no match" in result.lower()
        # Should suggest rephrasing or trying different keywords
        assert "try" in result.lower() or "rephrase" in result.lower()

    def test_run_handles_exception_gracefully(self, mock_knowledge_error):
        """Exception in query -> error message (not crash)."""
        tool = QuoteSearchTool(knowledge=mock_knowledge_error)

        # Should not raise, should return error message
        result = tool._run("test query")

        assert "error" in result.lower()
        assert "search" in result.lower() or "failed" in result.lower()


class TestQuoteSearchToolQueryParameters:
    """Tests for QuoteSearchTool query parameters."""

    def test_run_calls_knowledge_query_with_correct_params(self, mock_knowledge):
        """Verify query is passed to Knowledge correctly."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        tool._run("manual invoicing")

        # Verify query was called
        mock_knowledge.query.assert_called_once()

        # Check call args
        call_args = mock_knowledge.query.call_args
        assert call_args[1]["query"] == ["manual invoicing"]
        # Widened retrieval: more candidates at a lower similarity floor, with quality
        # enforced downstream (relevance floor + per-post cap + stance gate).
        assert call_args[1]["results_limit"] == 25
        assert call_args[1]["score_threshold"] == 0.60

    def test_run_strips_query_whitespace(self, mock_knowledge):
        """Query whitespace should be stripped."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        tool._run("  padded query  ")

        call_args = mock_knowledge.query.call_args
        assert call_args[1]["query"] == ["padded query"]


class TestQuoteSearchToolResultFormat:
    """Tests for result formatting details."""

    def test_result_separator_format(self, mock_knowledge):
        """Results should be separated with clear markers."""
        tool = QuoteSearchTool(knowledge=mock_knowledge)

        result = tool._run("test")

        # Should have separator between results
        assert "---" in result

    def test_result_includes_all_metadata(self):
        """All metadata fields should be included in output."""
        # Custom mock with specific metadata
        knowledge = MagicMock()
        knowledge.query.return_value = [
            {
                "content": "Test content here",
                "metadata": {
                    "post_id": "custom_id_123",
                    "source_type": "reddit",
                    "subreddit": "testsubreddit",
                },
                "score": 0.95,
            }
        ]

        tool = QuoteSearchTool(knowledge=knowledge)
        result = tool._run("test")

        assert "custom_id_123" in result
        assert "reddit" in result
        assert "0.95" in result

    def test_handles_missing_metadata_gracefully(self):
        """Missing metadata fields should default to 'unknown'."""
        knowledge = MagicMock()
        knowledge.query.return_value = [
            {
                "content": "Content without full metadata",
                "metadata": {},  # Empty metadata
                "score": 0.80,
            }
        ]

        tool = QuoteSearchTool(knowledge=knowledge)
        result = tool._run("test")

        # Should show 'unknown' for missing fields
        assert "unknown" in result

    def test_handles_context_vs_content_key(self):
        """Should handle both 'context' and 'content' keys."""
        knowledge = MagicMock()
        knowledge.query.return_value = [
            {
                "content": "Using content key instead of context",
                "metadata": {"post_id": "p1", "source_type": "reddit"},
                "score": 0.90,
            }
        ]

        tool = QuoteSearchTool(knowledge=knowledge)
        result = tool._run("test")

        assert "Using content key" in result
