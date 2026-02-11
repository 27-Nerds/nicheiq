"""
Tests for crew guardrails - content categorization, quote enrichment, and solution selection validation.

Tests:
- validate_content_categorization: checks anchor_keywords on themes
- validate_quote_enrichment: checks post_id presence and quote quality
- validate_solution_selection: checks JSON parsing and field validation
"""

import json
from unittest.mock import MagicMock

import pytest

from nicheiq.utils.validation.crew_guardrails import (
    validate_content_categorization,
    validate_quote_enrichment,
    validate_solution_selection,
)


class TestValidateContentCategorization:
    """Tests for validate_content_categorization guardrail."""

    def test_validate_content_categorization_checks_anchor_keywords(self):
        """Fails if theme has < 3 anchor_keywords."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": "Theme 1",
                    "definition": "Definition",
                    "frequency": "High",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2"],  # Only 2, needs 3
                },
                {
                    "category_name": "Theme 2",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 8,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 3",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 6,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 4",
                    "definition": "Definition",
                    "frequency": "Low",
                    "mention_count": 5,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                {"segment_name": "Admins", "primary_concerns": ["admin"], "mention_frequency": "Medium"},
                {"segment_name": "Devs", "primary_concerns": ["dev"], "mention_frequency": "Low"},
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "anchor_keywords" in result.lower()

    def test_validate_content_categorization_passes_valid(
        self, mock_task_output_valid_categorization
    ):
        """Passes with valid themes (3+ anchor_keywords each)."""
        success, result = validate_content_categorization(mock_task_output_valid_categorization)

        assert success
        # On success, returns raw for CrewAI to re-parse
        assert result == mock_task_output_valid_categorization.raw

    def test_validate_content_categorization_fails_few_themes(self):
        """Fails if < 4 theme_categories."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": "Theme 1",
                    "definition": "Definition",
                    "frequency": "High",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                {
                    "category_name": "Theme 2",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 8,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                },
                # Only 2 themes, need 4
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                {"segment_name": "Admins", "primary_concerns": ["admin"], "mention_frequency": "Medium"},
                {"segment_name": "Devs", "primary_concerns": ["dev"], "mention_frequency": "Low"},
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "at least 4" in result.lower()

    def test_validate_content_categorization_fails_few_segments(self):
        """Fails if < 3 user_segments."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "executive_summary": "Test summary",
            "theme_categories": [
                {
                    "category_name": f"Theme {i}",
                    "definition": "Definition",
                    "frequency": "Medium",
                    "mention_count": 10,
                    "primary_user_segments": ["Users"],
                    "anchor_keywords": ["kw1", "kw2", "kw3"],
                }
                for i in range(4)
            ],
            "user_segments": [
                {"segment_name": "Users", "primary_concerns": ["concern"], "mention_frequency": "High"},
                # Only 1 segment, need 3
            ],
            "overall_quality": "High",
        })

        success, result = validate_content_categorization(output)

        assert not success
        assert "at least 3" in result.lower() or "user_segments" in result.lower()


class TestValidateQuoteEnrichment:
    """Tests for validate_quote_enrichment guardrail."""

    def test_validate_quote_enrichment_passes_valid(
        self, mock_task_output_valid_quote_enrichment
    ):
        """Valid QuoteEnrichmentResult -> (True, raw)."""
        success, result = validate_quote_enrichment(mock_task_output_valid_quote_enrichment)

        assert success
        assert result == mock_task_output_valid_quote_enrichment.raw

    def test_validate_quote_enrichment_fails_empty_list(
        self, mock_task_output_empty_enrichment
    ):
        """Empty enriched_pain_points -> failure."""
        success, result = validate_quote_enrichment(mock_task_output_empty_enrichment)

        assert not success
        assert "empty" in result.lower() or "enriched_pain_points" in result.lower()

    def test_validate_quote_enrichment_fails_missing_post_id(
        self, mock_task_output_missing_post_id
    ):
        """Quote with post_id='' or 'unknown' -> failure."""
        success, result = validate_quote_enrichment(mock_task_output_missing_post_id)

        assert not success
        assert "post_id" in result.lower()

    def test_validate_quote_enrichment_fails_short_quote(
        self, mock_task_output_short_quotes
    ):
        """Quote < 15 chars -> warning (fails if many)."""
        success, result = validate_quote_enrichment(mock_task_output_short_quotes)

        # With 4 short quotes for 1 pain point, this should fail
        assert not success
        assert "short" in result.lower()

    def test_validate_quote_enrichment_parses_from_raw(self):
        """Handles CrewAI 1.7.0 (pydantic=None, parse from raw)."""
        output = MagicMock()
        output.pydantic = None  # CrewAI 1.7.0 behavior
        output.raw = json.dumps({
            "niche": "test niche",
            "enriched_pain_points": [
                {
                    "pain_point_title": "Test Pain",
                    "quotes": [
                        {
                            "quote_text": "This is a valid quote that is long enough",
                            "post_id": "abc123",
                        }
                    ],
                }
            ],
            "total_quotes_found": 1,
            "enrichment_summary": "Found 1 quote.",
        })

        success, result = validate_quote_enrichment(output)

        assert success

    def test_validate_quote_enrichment_accepts_some_short_quotes(self):
        """A few short quotes among many substantive ones should pass."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "niche": "test",
            "enriched_pain_points": [
                {
                    "pain_point_title": "Pain 1",
                    "quotes": [
                        {"quote_text": "This is a long enough quote about the problem", "post_id": "p1"},
                        {"quote_text": "me too", "post_id": "p2"},  # Short but okay if minority
                    ],
                },
                {
                    "pain_point_title": "Pain 2",
                    "quotes": [
                        {"quote_text": "Another substantive quote here that makes sense", "post_id": "p3"},
                    ],
                },
            ],
            "total_quotes_found": 3,
            "enrichment_summary": "Found quotes.",
        })

        success, result = validate_quote_enrichment(output)

        # Should pass because majority of quotes are substantive
        assert success


class TestValidateQuoteEnrichmentEdgeCases:
    """Edge case tests for validate_quote_enrichment."""

    def test_empty_raw_returns_error(self):
        """No pydantic and empty raw -> error."""
        output = MagicMock()
        output.pydantic = None
        output.raw = ""

        success, result = validate_quote_enrichment(output)

        assert not success
        assert "empty" in result.lower()

    def test_invalid_json_returns_error(self):
        """Malformed JSON -> error."""
        output = MagicMock()
        output.pydantic = None
        output.raw = "{ invalid json }"

        success, result = validate_quote_enrichment(output)

        assert not success
        assert "json" in result.lower() or "parse" in result.lower()

    def test_missing_required_fields_returns_error(self):
        """JSON missing required fields -> error."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "niche": "test",
            # Missing: enriched_pain_points, total_quotes_found, enrichment_summary
        })

        success, result = validate_quote_enrichment(output)

        assert not success

    def test_quotes_at_15_char_boundary(self):
        """Quote exactly at 15 chars should pass."""
        output = MagicMock()
        output.pydantic = None
        output.raw = json.dumps({
            "niche": "test",
            "enriched_pain_points": [
                {
                    "pain_point_title": "Test",
                    "quotes": [
                        {"quote_text": "Exactly 15chars", "post_id": "p1"},  # Exactly 15 chars
                    ],
                }
            ],
            "total_quotes_found": 1,
            "enrichment_summary": "Found 1 quote.",
        })

        success, result = validate_quote_enrichment(output)

        assert success


class TestValidateContentCategorizationEdgeCases:
    """Edge case tests for validate_content_categorization."""

    def test_empty_raw_returns_error(self):
        """No pydantic and empty raw -> error."""
        output = MagicMock()
        output.pydantic = None
        output.raw = ""

        success, result = validate_content_categorization(output)

        assert not success

    def test_pydantic_available_uses_it(self):
        """When pydantic is available, uses it directly."""
        from nicheiq.models.pain_point import (
            ContentCategorizationReport,
            ThemeCategory,
            UserSegment,
        )

        report = ContentCategorizationReport(
            executive_summary="Test",
            theme_categories=[
                ThemeCategory(
                    category_name=f"Theme {i}",
                    definition="Def",
                    frequency="High",
                    mention_count=10,
                    primary_user_segments=["Users"],
                    anchor_keywords=["kw1", "kw2", "kw3"],
                )
                for i in range(4)
            ],
            user_segments=[
                UserSegment(segment_name=f"Seg {i}", primary_concerns=["c"], mention_frequency="High")
                for i in range(3)
            ],
            overall_quality="High",
        )

        output = MagicMock()
        output.pydantic = report
        output.raw = "unused"

        success, result = validate_content_categorization(output)

        # Should pass using pydantic directly
        assert success


def _make_valid_selection_raw(**overrides) -> str:
    """Helper to build valid SolutionSelection JSON with optional overrides."""
    data = {
        "selected_solution_name": "NicheTracker Pro",
        "selection_rationale": (
            "NicheTracker Pro was selected because it addresses the strongest validated pain point "
            "in the market with a clear competitive gap. The solution scores highest on market fit "
            "(0.85) and competitive advantage (0.78), while maintaining strong technical feasibility."
        ),
        "recommended_focus": "Enterprise segment first, then SMB expansion",
        "runner_up_solutions": ["CompetitorRadar", "MarketPulse"],
    }
    data.update(overrides)
    return json.dumps(data)


class TestValidateSolutionSelection:
    """Tests for validate_solution_selection guardrail."""

    def test_valid_selection(self):
        """Valid SolutionSelection JSON -> (True, raw)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw()

        success, result = validate_solution_selection(output)

        assert success
        assert result == output.raw

    def test_invalid_json(self):
        """Malformed JSON (the actual production crash scenario) -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        # Unescaped quote inside selection_rationale - the real crash scenario
        output.raw = '{"selected_solution_name": "Test", "selection_rationale": "It\'s the "best" solution because reasons", "recommended_focus": "focus"}'

        success, result = validate_solution_selection(output)

        assert not success
        assert "json" in result.lower() or "parse" in result.lower()

    def test_short_rationale(self):
        """selection_rationale < 100 chars -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            selection_rationale="Too short rationale."
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "selection_rationale" in result.lower()

    def test_short_name(self):
        """selected_solution_name < 3 chars -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            selected_solution_name="AB"
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "selected_solution_name" in result.lower()

    def test_empty_focus(self):
        """Empty recommended_focus -> (False, error)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_valid_selection_raw(
            recommended_focus=""
        )

        success, result = validate_solution_selection(output)

        assert not success
        assert "recommended_focus" in result.lower()
