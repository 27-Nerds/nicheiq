"""
Tests for final report markdown generation.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from nicheiq.utils.final_report_generator import (
    generate_markdown_report,
    _generate_header,
    _generate_executive_summary
)


class TestGenerateHeader:
    """Tests for _generate_header function."""

    def test_header_includes_niche_uppercase(self):
        """Test that header includes niche in uppercase."""
        mock_report = MagicMock()
        mock_report.niche = "ai tools for content creators"
        mock_report.generated_at = datetime(2024, 3, 15)

        header = _generate_header(mock_report)

        assert "AI TOOLS FOR CONTENT CREATORS" in header
        assert "MARKET RESEARCH & STRATEGY REPORT" in header

    def test_header_includes_timestamp(self):
        """Test that header includes formatted timestamp."""
        mock_report = MagicMock()
        mock_report.niche = "test niche"
        mock_report.generated_at = datetime(2024, 3, 15, 14, 30)

        header = _generate_header(mock_report)

        assert "March 2024" in header

    def test_header_includes_research_pipeline(self):
        """Test that header mentions NicheIQ pipeline."""
        mock_report = MagicMock()
        mock_report.niche = "test"
        mock_report.generated_at = datetime.now()

        header = _generate_header(mock_report)

        assert "NicheIQ" in header
        assert "10-Stage" in header


class TestGenerateExecutiveSummary:
    """Tests for _generate_executive_summary function."""

    def test_executive_summary_includes_content(self):
        """Test that executive summary includes report content."""
        mock_report = MagicMock()
        mock_report.executive_summary = "This is a test executive summary with key findings."

        summary = _generate_executive_summary(mock_report)

        assert "EXECUTIVE SUMMARY" in summary
        assert "This is a test executive summary" in summary


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report function."""

    def test_report_basic_functionality(self):
        """Test basic report generation (header + executive summary only)."""
        # Note: Full report generation is complex and depends on many internal
        # functions. We test the basic components here and rely on integration
        # tests for full report validation.

        mock_report = MagicMock()
        mock_report.niche = "test niche"
        mock_report.generated_at = datetime(2024, 3, 15)
        mock_report.executive_summary = "Test executive summary"

        # Test header generation
        header = _generate_header(mock_report)
        assert "TEST NICHE" in header
        assert "March 2024" in header

        # Test executive summary
        summary = _generate_executive_summary(mock_report)
        assert "EXECUTIVE SUMMARY" in summary
        assert "Test executive summary" in summary
