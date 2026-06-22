"""
Unit tests for helper function validation and formatting enhancements.

Tests coverage for Phase 1 & 2 improvements:
- Type hints validation
- Input validation with clear error messages
- Format type handling (detailed, compact, metrics_only)
- Priority filtering
- Sort options
- Edge cases (empty lists, invalid parameters)
"""

import pytest

from nicheiq.models.pain_point import PainPoint, OpportunityLevel
from nicheiq.models.solution_idea import SolutionIdea
from nicheiq.utils.helpers import find_solution_by_name, sanitize_collection_name
from nicheiq.utils.pain_point_formatters import (
    format_pain_points_for_agents,
    extract_pain_points_by_priority,
)


# Test fixtures
@pytest.fixture
def sample_pain_points() -> list[PainPoint]:
    """Create sample pain points for testing."""
    return [
        PainPoint(
            title="High Priority Issue",
            description="Critical problem affecting users",
            severity_score=0.9,
            willingness_to_pay=0.8,
            mention_count=50,
            opportunity_level=OpportunityLevel.HIGH,
            representative_quotes=["Quote 1", "Quote 2"],
            source_platforms=["Reddit"],
            categories=["Technical"],
            source_post_ids=["post123"],
        ),
        PainPoint(
            title="Medium Priority Issue",
            description="Moderate problem",
            severity_score=0.6,
            willingness_to_pay=0.5,
            mention_count=25,
            opportunity_level=OpportunityLevel.MEDIUM,
            representative_quotes=["Quote 3"],
            source_platforms=["Twitter"],
            categories=["UX"],
            source_post_ids=["post456"],
        ),
        PainPoint(
            title="Low Priority Issue",
            description="Minor annoyance",
            severity_score=0.3,
            willingness_to_pay=0.2,
            mention_count=10,
            opportunity_level=OpportunityLevel.LOW,
            representative_quotes=["Quote 4"],
            source_platforms=["Reddit", "Twitter"],
            categories=["Feature Request"],
            source_post_ids=["post789"],
        ),
    ]


@pytest.fixture
def sample_solutions() -> list[SolutionIdea]:
    """Create sample solutions for testing."""
    return [
        SolutionIdea(
            solution_name="Solution A",
            description="Detailed description of Solution A - at least four sentences to meet requirements. Users can access the platform and perform key actions. The solution delivers clear value through its core features. Results are immediate and measurable.",
            value_proposition="One-line value proposition for Solution A",
            pain_points_addressed=["Pain 1", "Pain 2"],
            core_features=["Feature 1", "Feature 2"],
            target_personas=["Persona A"],
            project_type="SaaS",
            market_fit_score=0.9,
        ),
        SolutionIdea(
            solution_name="Solution B",
            description="Detailed description of Solution B - at least four sentences to meet requirements. Users can access the marketplace and browse listings. The platform connects buyers with sellers efficiently. Value is delivered through seamless transactions.",
            value_proposition="One-line value proposition for Solution B",
            pain_points_addressed=["Pain 3", "Pain 4"],
            core_features=["Feature 3", "Feature 4"],
            target_personas=["Persona B"],
            project_type="Marketplace",
            market_fit_score=0.7,
        ),
    ]


class TestFormatPainPointsForAgents:
    """Test format_pain_points_for_agents() with Phase 1 & 2 enhancements."""

    def test_empty_list_returns_empty_string(self):
        """Test that empty pain point list returns empty string."""
        result = format_pain_points_for_agents([])
        assert result == ""

    def test_none_list_returns_empty_string(self):
        """Test that None pain point list returns empty string."""
        result = format_pain_points_for_agents(None)
        assert result == ""

    def test_invalid_format_type_raises_error(self, sample_pain_points):
        """Test that invalid format_type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown format_type"):
            format_pain_points_for_agents(
                sample_pain_points, format_type="invalid_format"
            )

    def test_invalid_priority_filter_raises_error(self, sample_pain_points):
        """Test that invalid priority_filter raises ValueError."""
        with pytest.raises(ValueError, match="Invalid priority_filter"):
            format_pain_points_for_agents(
                sample_pain_points, priority_filter="invalid_priority"
            )

    def test_invalid_sort_by_raises_error(self, sample_pain_points):
        """Test that invalid sort_by raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sort_by"):
            format_pain_points_for_agents(
                sample_pain_points, sort_by="invalid_sort"
            )

    def test_detailed_format_includes_all_fields(self, sample_pain_points):
        """Test that detailed format includes description, metrics, quotes."""
        result = format_pain_points_for_agents(
            sample_pain_points, format_type="detailed", include_quotes=True
        )

        # Should include title
        assert "High Priority Issue" in result
        # Should include description
        assert "Critical problem affecting users" in result
        # Should include metrics
        assert "Severity:" in result
        assert "WTP:" in result
        # Should include quotes
        assert "Quote 1" in result

    def test_compact_format_is_concise(self, sample_pain_points):
        """Test that compact format is concise: inline metrics + ONE short quote per pain."""
        result = format_pain_points_for_agents(
            sample_pain_points, format_type="compact"
        )

        # Should include title and metrics
        assert "High Priority Issue" in result
        assert "Severity:" in result or "8" in result  # Metrics present

        # Stays concise: NO full description, and only the FIRST quote per pain (§6b) —
        # not the full quote list.
        assert "Critical problem affecting users" not in result
        assert "Quote 1" in result   # one short voice-of-customer quote now included
        assert "Quote 2" not in result  # but only one — not the whole quote list

    def test_metrics_only_format(self, sample_pain_points):
        """Test that metrics_only format shows title and standardized metrics."""
        result = format_pain_points_for_agents(
            sample_pain_points, format_type="metrics_only"
        )

        # Should include title and metrics
        assert "High Priority Issue" in result
        assert "Severity:" in result or "/10" in result  # Standardized format

    def test_metrics_only_scores_scaled_to_10(self, sample_pain_points):
        """Scores are 0.0-1.0 internally but must display as X.Y/10."""
        result = format_pain_points_for_agents(
            sample_pain_points, format_type="metrics_only"
        )
        # sample_pain_points has severity_score=0.9, wtp=0.8
        assert "Severity: 9.0/10" in result
        assert "WTP: 8.0/10" in result
        # Must NOT show raw 0-1 values
        assert "Severity: 0.9/10" not in result
        assert "WTP: 0.8/10" not in result

    def test_priority_filter_high(self, sample_pain_points):
        """Test that priority_filter='high' returns only high-priority pain points."""
        result = format_pain_points_for_agents(
            sample_pain_points, priority_filter="high"
        )

        assert "High Priority Issue" in result
        assert "Medium Priority Issue" not in result
        assert "Low Priority Issue" not in result

    def test_priority_filter_medium(self, sample_pain_points):
        """Test that priority_filter='medium' returns only medium-priority pain points."""
        result = format_pain_points_for_agents(
            sample_pain_points, priority_filter="medium"
        )

        assert "High Priority Issue" not in result
        assert "Medium Priority Issue" in result
        assert "Low Priority Issue" not in result

    def test_priority_filter_low(self, sample_pain_points):
        """Test that priority_filter='low' returns only low-priority pain points."""
        result = format_pain_points_for_agents(
            sample_pain_points, priority_filter="low"
        )

        assert "High Priority Issue" not in result
        assert "Medium Priority Issue" not in result
        assert "Low Priority Issue" in result

    def test_sort_by_severity(self, sample_pain_points):
        """Test that sort_by='severity' orders by severity_score descending."""
        result = format_pain_points_for_agents(
            sample_pain_points, sort_by="severity", format_type="metrics_only"
        )

        # High Priority (0.9) should appear before Medium (0.6) and Low (0.3)
        high_pos = result.find("High Priority Issue")
        medium_pos = result.find("Medium Priority Issue")
        low_pos = result.find("Low Priority Issue")

        assert high_pos < medium_pos < low_pos

    def test_sort_by_wtp(self, sample_pain_points):
        """Test that sort_by='wtp' orders by willingness_to_pay descending."""
        result = format_pain_points_for_agents(
            sample_pain_points, sort_by="wtp", format_type="metrics_only"
        )

        # High Priority (0.8 WTP) should appear before Medium (0.5) and Low (0.2)
        high_pos = result.find("High Priority Issue")
        medium_pos = result.find("Medium Priority Issue")
        low_pos = result.find("Low Priority Issue")

        assert high_pos < medium_pos < low_pos

    def test_sort_by_mentions(self, sample_pain_points):
        """Test that sort_by='mentions' orders by mention_count descending."""
        result = format_pain_points_for_agents(
            sample_pain_points, sort_by="mentions", format_type="metrics_only"
        )

        # High Priority (50 mentions) should appear before Medium (25) and Low (10)
        high_pos = result.find("High Priority Issue")
        medium_pos = result.find("Medium Priority Issue")
        low_pos = result.find("Low Priority Issue")

        assert high_pos < medium_pos < low_pos

    def test_sort_by_title(self, sample_pain_points):
        """Test that sort_by='title' orders alphabetically."""
        result = format_pain_points_for_agents(
            sample_pain_points, sort_by="title", format_type="metrics_only"
        )

        # Alphabetical: High, Low, Medium
        high_pos = result.find("High Priority Issue")
        low_pos = result.find("Low Priority Issue")
        medium_pos = result.find("Medium Priority Issue")

        assert high_pos < low_pos < medium_pos


class TestExtractPainPointsByPriority:
    """Test extract_pain_points_by_priority() type hints validation."""

    def test_returns_three_lists(self, sample_pain_points):
        """Test that function returns three separate lists."""
        from nicheiq.models.pain_point import PainPointAnalysisResult

        analysis = PainPointAnalysisResult(
            pain_points=sample_pain_points,
            niche="Test Niche",
            total_mentions=100,
            top_categories=["Technical", "UX", "Feature Request"],
            analysis_summary="Test summary",
        )

        high, medium, low = extract_pain_points_by_priority(analysis)

        assert isinstance(high, list)
        assert isinstance(medium, list)
        assert isinstance(low, list)

    def test_correct_priority_distribution(self, sample_pain_points):
        """Test that pain points are correctly distributed by priority."""
        from nicheiq.models.pain_point import PainPointAnalysisResult

        analysis = PainPointAnalysisResult(
            pain_points=sample_pain_points,
            niche="Test Niche",
            total_mentions=100,
            top_categories=["Technical", "UX", "Feature Request"],
            analysis_summary="Test summary",
        )

        high, medium, low = extract_pain_points_by_priority(analysis)

        # Verify counts
        assert len(high) == 1
        assert len(medium) == 1
        assert len(low) == 1

        # Verify correct assignment
        assert high[0].title == "High Priority Issue"
        assert medium[0].title == "Medium Priority Issue"
        assert low[0].title == "Low Priority Issue"

    def test_handles_empty_analysis(self):
        """Test that function handles empty pain point analysis."""
        from nicheiq.models.pain_point import PainPointAnalysisResult

        analysis = PainPointAnalysisResult(
            pain_points=[],
            niche="Test Niche",
            total_mentions=0,
            top_categories=[],
            analysis_summary="No pain points found",
        )

        high, medium, low = extract_pain_points_by_priority(analysis)

        assert high == []
        assert medium == []
        assert low == []


class TestFindSolutionByName:
    """Test find_solution_by_name() type hints validation."""

    def test_finds_existing_solution(self, sample_solutions):
        """Test that function finds existing solution by exact name."""
        result = find_solution_by_name("Solution A", sample_solutions)

        assert result is not None
        assert result.solution_name == "Solution A"
        assert result.value_proposition == "One-line value proposition for Solution A"

    def test_returns_none_for_nonexistent_solution(self, sample_solutions):
        """Test that function returns None for non-existent solution."""
        result = find_solution_by_name("Nonexistent Solution", sample_solutions)

        assert result is None

    def test_fuzzy_matching(self, sample_solutions):
        """Test that function performs fuzzy matching for case insensitivity."""
        result = find_solution_by_name("solution a", sample_solutions)

        # Should match via fuzzy matching (case insensitive)
        assert result is not None
        assert result.solution_name == "Solution A"

    def test_handles_empty_solution_list(self):
        """Test that function handles empty solution list."""
        result = find_solution_by_name("Any Solution", [])

        assert result is None

    def test_handles_none_solution_list(self):
        """Test that function handles None solution list gracefully."""
        result = find_solution_by_name("Any Solution", None)

        assert result is None

    def test_finds_solution_with_special_characters(self):
        """Test that function finds solutions with special characters in name."""
        special_solution = SolutionIdea(
            solution_name="Solution-X (Beta)",
            description="Special solution with detailed description. Users access the beta platform. Features are tested and validated. Value is delivered consistently.",
            value_proposition="Special solution value proposition",
            pain_points_addressed=["Pain 1"],
            core_features=["Feature 1"],
            target_personas=["Persona"],
            project_type="SaaS",
            market_fit_score=0.8,
        )

        result = find_solution_by_name("Solution-X (Beta)", [special_solution])

        assert result is not None
        assert result.solution_name == "Solution-X (Beta)"


class TestSanitizeCollectionName:
    """Test sanitize_collection_name() ChromaDB collection name generation."""

    def test_basic_sanitization(self):
        """Test basic collection name generation."""
        result = sanitize_collection_name("AI tools for content creators", "pain")

        assert result.startswith("pain_")
        assert "ai_tools_for_content_creators" in result
        assert len(result) >= 3
        assert len(result) <= 63

    def test_invalid_characters_replaced_with_underscore(self):
        """Test that invalid characters are replaced with underscores."""
        result = sanitize_collection_name("AI/ML & Data Science!", "seo")

        # Should replace /, &, and ! with underscores
        assert "/" not in result
        assert "&" not in result
        assert "!" not in result
        assert "_" in result

    def test_consecutive_underscores_removed(self):
        """Test that consecutive underscores are collapsed to single underscore."""
        result = sanitize_collection_name("test___multiple___underscores", "crew")

        # Should not have triple underscores
        assert "___" not in result

    def test_length_limit_enforced(self):
        """Test that collection name is truncated to 63 chars max."""
        long_niche = "a" * 100  # Very long niche
        result = sanitize_collection_name(long_niche, "solution")

        assert len(result) <= 63

    def test_minimum_length_enforced(self):
        """Test that collection name is at least 3 chars."""
        result = sanitize_collection_name("a", "p")  # Very short inputs

        assert len(result) >= 3

    def test_minimum_length_padding(self):
        """Test that very short names are padded with '_kb'."""
        result = sanitize_collection_name("a", "p")  # Would be "p_a" = 3 chars

        # Should be at least 3 characters
        assert len(result) >= 3

    def test_crew_name_prefix(self):
        """Test that crew name is used as prefix."""
        result = sanitize_collection_name("test niche", "pain")
        assert result.startswith("pain_")

        result = sanitize_collection_name("test niche", "seo")
        assert result.startswith("seo_")

    def test_lowercase_conversion(self):
        """Test that niche is converted to lowercase."""
        result = sanitize_collection_name("AI Tools For CONTENT", "crew")

        # Should be all lowercase
        assert result.islower()

    def test_special_characters_handling(self):
        """Test various special characters are replaced correctly."""
        result = sanitize_collection_name("test@#$%^&*()niche", "crew")

        # All special chars should be replaced with underscores
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result

    def test_ipv4_pattern_avoidance(self):
        """Test that IPv4-like patterns are avoided (ChromaDB requirement)."""
        # ChromaDB doesn't allow IPv4 patterns like "192_168_1_1"
        # Our function should sanitize but not explicitly check for this
        # (This is more of a documentation test)
        result = sanitize_collection_name("192.168.1.1", "crew")

        # Should be valid (dots replaced with underscores)
        assert result == "crew_192_168_1_1"

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved (valid ChromaDB char)."""
        result = sanitize_collection_name("test-niche-name", "crew")

        # Hyphens should be preserved
        assert "-" in result
        assert "test-niche-name" in result


class TestPerformanceOptimizations:
    """Test that Phase 2 performance optimizations don't break functionality."""

    def test_format_handles_large_pain_point_list(self):
        """Test that formatting handles large pain point lists efficiently."""
        # Create 100 pain points
        large_list = [
            PainPoint(
                title=f"Pain Point {i}",
                description=f"Description {i}",
                severity_score=0.5,
                willingness_to_pay=0.5,
                mention_count=10,
                opportunity_level=OpportunityLevel.MEDIUM,
                representative_quotes=[f"Quote {i}"],
                source_platforms=["Reddit"],
                categories=["Category"],
                source_post_ids=[f"post{i}"],
            )
            for i in range(100)
        ]

        # Should complete without error (with limit=100 to get all)
        result = format_pain_points_for_agents(
            large_list, format_type="compact", priority_filter="medium", limit=100
        )

        # Verify all pain points are included
        assert "Pain Point 0" in result
        assert "Pain Point 99" in result

    def test_extract_handles_large_analysis(self):
        """Test that extraction handles large pain point analysis efficiently."""
        from nicheiq.models.pain_point import PainPointAnalysisResult

        # Create 300 pain points (100 per priority)
        large_list = []
        for i in range(100):
            large_list.append(
                PainPoint(
                    title=f"High {i}",
                    description="desc",
                    severity_score=0.9,
                    willingness_to_pay=0.8,
                    mention_count=50,
                    opportunity_level=OpportunityLevel.HIGH,
                    representative_quotes=["quote"],
                    source_platforms=["Reddit"],
                    categories=["cat"],
                    source_post_ids=["post"],
                )
            )
            large_list.append(
                PainPoint(
                    title=f"Medium {i}",
                    description="desc",
                    severity_score=0.6,
                    willingness_to_pay=0.5,
                    mention_count=25,
                    opportunity_level=OpportunityLevel.MEDIUM,
                    representative_quotes=["quote"],
                    source_platforms=["Reddit"],
                    categories=["cat"],
                    source_post_ids=["post"],
                )
            )
            large_list.append(
                PainPoint(
                    title=f"Low {i}",
                    description="desc",
                    severity_score=0.3,
                    willingness_to_pay=0.2,
                    mention_count=10,
                    opportunity_level=OpportunityLevel.LOW,
                    representative_quotes=["quote"],
                    source_platforms=["Reddit"],
                    categories=["cat"],
                    source_post_ids=["post"],
                )
            )

        analysis = PainPointAnalysisResult(
            pain_points=large_list,
            niche="Test",
            total_mentions=3000,
            top_categories=["Category"],
            analysis_summary="Large test analysis",
        )

        # Should complete without error
        high, medium, low = extract_pain_points_by_priority(analysis)

        assert len(high) == 100
        assert len(medium) == 100
        assert len(low) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
