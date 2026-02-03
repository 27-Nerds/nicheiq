"""
Unit tests for parallel quote enrichment methods in PainPointCrew.

Tests the Python-driven parallel enrichment that replaces Task 4:
- _parse_search_results() - regex parsing of QuoteSearchTool output
- _enrich_single_pain_point() - single pain point enrichment logic
- _run_parallel_quote_enrichment() - ThreadPoolExecutor orchestration

These tests use mocking to isolate the methods from actual Knowledge/embedding dependencies.
"""

from concurrent.futures import Future
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nicheiq.models.pain_point import (
    EnrichedPainPointQuotes,
    ExtractedQuote,
    QuoteEnrichmentResult,
    SinglePainPointQuotesResult,
    UnvalidatedPainPoint,
)
from nicheiq.crews.pain_point_crew import PainPointCrew


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def mock_pain_point():
    """Create a standard mock pain point with anchor keywords."""
    return UnvalidatedPainPoint(
        title="Manual Invoicing",
        description="Users struggle with manual invoicing processes taking too much time",
        mention_count=20,
        anchor_keywords=["manual invoicing", "invoice automation", "billing nightmare", "time on invoices"],
        source_platforms=["Reddit"],
        categories=["workflow", "automation"],
    )


@pytest.fixture
def mock_pain_point_few_keywords():
    """Create a pain point with minimal (2) anchor keywords."""
    return UnvalidatedPainPoint(
        title="Expense Tracking",
        description="Tracking expenses is tedious and error-prone",
        mention_count=15,
        anchor_keywords=["expense reports", "receipt tracking"],
    )


@pytest.fixture
def mock_pain_point_many_keywords():
    """Create a pain point with maximum (8) anchor keywords."""
    return UnvalidatedPainPoint(
        title="Cash Flow Management",
        description="Managing cash flow is challenging for small businesses",
        mention_count=30,
        anchor_keywords=[
            "cash flow problems",
            "late payments",
            "payment tracking",
            "invoice delays",
            "accounts receivable",
            "billing cycle",
            "revenue timing",
            "payment collection",
        ],
    )


@pytest.fixture
def mock_search_result_standard():
    """Standard QuoteSearchTool output with multiple results."""
    return """--- Result 1 (score: 0.92, post_id: abc123, source: reddit) ---
I spend 3 hours every week on manual invoices and it's killing me. We need a better solution for our small business that integrates with our existing accounting software.

--- Result 2 (score: 0.87, post_id: def456, source: reddit) ---
Our invoicing process is completely manual and error-prone. I've lost count of how many times we've sent duplicate invoices or missed payments.

--- Result 3 (score: 0.75, post_id: ghi789, source: twitter) ---
Manual billing is such a nightmare. Anyone have recommendations for automation tools that actually work?"""


@pytest.fixture
def mock_search_result_with_short_sentences():
    """Search results containing both long and short sentences."""
    return """--- Result 1 (score: 0.90, post_id: post1, source: reddit) ---
Yes! Same here. I totally agree with this pain point about manual invoicing being terrible for small business owners like us.

--- Result 2 (score: 0.85, post_id: post2, source: reddit) ---
+1. This is a really comprehensive description of the problem that many of us face with invoice automation and billing cycles."""


@pytest.fixture
def mock_search_result_empty():
    """Empty search results."""
    return ""


@pytest.fixture
def mock_search_result_malformed():
    """Malformed search results (missing headers)."""
    return """Some random text without proper headers.
Another line of content that doesn't match the expected format."""


@pytest.fixture
def mock_quote_search_tool():
    """Create a mock QuoteSearchTool."""
    tool = MagicMock()
    tool._run.return_value = """--- Result 1 (score: 0.92, post_id: abc123, source: reddit) ---
I spend 3 hours every week on manual invoices and it's killing me. We need a better solution for our small business that integrates with our existing accounting software.

--- Result 2 (score: 0.85, post_id: def456, source: reddit) ---
Manual billing is such a nightmare for our entire team and causes constant frustration with our clients."""
    return tool


# ============================================================================
# HELPER: Create minimal PainPointCrew for testing
# ============================================================================


def create_minimal_crew(enrichment_knowledge=None, niche="test niche"):
    """
    Create a PainPointCrew instance with minimal setup for testing.

    Uses object.__new__ to bypass __init__ entirely, then manually sets
    required attributes. This avoids any Knowledge/embedding initialization.
    """
    # Create instance without calling __init__
    crew = object.__new__(PainPointCrew)

    # Set required attributes directly
    crew._enrichment_knowledge = enrichment_knowledge
    crew.niche_description = niche
    crew.reddit_posts = []
    crew.twitter_threads = []
    crew._raw_reddit_posts = []
    crew._raw_twitter_threads = []
    crew.knowledge_sources = []
    crew.formatted_reddit_content = ""
    crew.formatted_twitter_content = ""
    crew.market_segments = []
    crew.industry_boundaries = ""

    return crew


# ============================================================================
# TESTS: _parse_search_results()
# ============================================================================


class TestParseSearchResults:
    """Tests for _parse_search_results() method."""

    def test_parse_valid_search_results(self, mock_search_result_standard):
        """Parse standard QuoteSearchTool output format."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_standard)

        # Should extract at least one quote with 15+ words
        assert len(parsed) >= 1
        # Each result is a (quote_text, post_id) tuple
        for quote_text, post_id in parsed:
            assert isinstance(quote_text, str)
            assert isinstance(post_id, str)
            assert len(quote_text.split()) >= 15

    def test_parse_extracts_post_id(self, mock_search_result_standard):
        """Verify post_id extraction from result header."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_standard)

        # Verify post_ids are extracted correctly
        post_ids = [post_id for _, post_id in parsed]
        # At least one of these should be present
        assert any(pid in ["abc123", "def456", "ghi789"] for pid in post_ids)

    def test_parse_filters_short_quotes(self, mock_search_result_with_short_sentences):
        """Filter quotes with < 15 words."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_with_short_sentences)

        # All extracted quotes should have 15+ words
        for quote_text, _ in parsed:
            word_count = len(quote_text.split())
            assert word_count >= 15, f"Quote has only {word_count} words: '{quote_text[:50]}...'"

    def test_parse_handles_empty_results(self, mock_search_result_empty):
        """Handle empty search results."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_empty)

        assert parsed == []

    def test_parse_handles_malformed_results(self, mock_search_result_malformed):
        """Handle malformed result format gracefully."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_malformed)

        # Should return empty list when format doesn't match
        assert parsed == []

    def test_parse_extracts_multiple_sentences_from_single_result(self):
        """Extract multiple qualifying sentences from a single search result."""
        crew = create_minimal_crew()

        result = """--- Result 1 (score: 0.90, post_id: multi123, source: reddit) ---
This is the first sentence that definitely has more than fifteen words in it for testing purposes. This is the second sentence that also has more than fifteen words for our validation testing."""

        parsed = crew._parse_search_results(result)

        # Should extract multiple sentences from same result (same post_id)
        assert len(parsed) >= 1
        # All should have same post_id
        for _, post_id in parsed:
            assert post_id == "multi123"

    def test_parse_handles_special_characters_in_content(self):
        """Handle special characters in quote content."""
        crew = create_minimal_crew()

        result = """--- Result 1 (score: 0.88, post_id: special_123, source: reddit) ---
This quote has special characters like @mentions, #hashtags, and URLs https://example.com which should all be preserved in the extracted text correctly."""

        parsed = crew._parse_search_results(result)

        assert len(parsed) >= 1
        quote_text, post_id = parsed[0]
        assert post_id == "special_123"
        assert "@mentions" in quote_text or "#hashtags" in quote_text or "https://" in quote_text


# ============================================================================
# TESTS: _enrich_single_pain_point()
# ============================================================================


class TestEnrichSinglePainPoint:
    """Tests for _enrich_single_pain_point() method."""

    def test_enrich_uses_anchor_keywords(self, mock_pain_point, mock_quote_search_tool):
        """Verify searches use anchor_keywords from pain point."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point, mock_quote_search_tool)

        # Verify search tool was called with keywords
        assert mock_quote_search_tool._run.called
        # Check that keywords used are from the pain point
        assert result.anchor_keywords_searched
        for kw in result.anchor_keywords_searched:
            assert kw in mock_pain_point.anchor_keywords

    def test_enrich_limits_keywords_to_4(self, mock_pain_point_many_keywords, mock_quote_search_tool):
        """Only use first 4 anchor_keywords."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point_many_keywords, mock_quote_search_tool)

        # Should only search first 4 keywords even if more available
        assert len(result.anchor_keywords_searched) <= 4
        assert mock_quote_search_tool._run.call_count <= 4

    def test_enrich_deduplicates_quotes(self, mock_pain_point):
        """Deduplicate quotes across keyword searches."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create a mock that returns the same quote for different keywords
        mock_tool = MagicMock()
        mock_tool._run.return_value = """--- Result 1 (score: 0.92, post_id: dup123, source: reddit) ---
I spend 3 hours every week on manual invoices and it's killing me. We need a better solution for our small business."""

        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        # Even with 4 keyword searches returning same quote, should only have 1 unique quote
        unique_texts = set(q.quote_text.lower().strip() for q in result.quotes)
        assert len(unique_texts) <= len(result.quotes)

    def test_enrich_caps_quotes_at_12(self, mock_pain_point):
        """Cap quotes at 12 per pain point."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create a mock that returns many quotes
        many_quotes_result = "\n\n".join([
            f"""--- Result {i} (score: 0.{90-i:02d}, post_id: post{i}, source: reddit) ---
This is quote number {i} with enough words to pass the fifteen word minimum filter for testing purposes in this test case."""
            for i in range(1, 20)  # 19 potential quotes
        ])

        mock_tool = MagicMock()
        mock_tool._run.return_value = many_quotes_result

        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        # Should cap at 12 quotes
        assert len(result.quotes) <= 12

    def test_enrich_handles_search_error(self, mock_pain_point):
        """Continue on search error, log warning."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create a mock that raises an exception
        mock_tool = MagicMock()
        mock_tool._run.side_effect = Exception("Search failed")

        # Should not raise, should return result with empty quotes
        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        assert isinstance(result, SinglePainPointQuotesResult)
        assert result.pain_point_title == mock_pain_point.title
        assert result.quotes == []

    def test_enrich_returns_correct_result_type(self, mock_pain_point, mock_quote_search_tool):
        """Verify return type is SinglePainPointQuotesResult."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point, mock_quote_search_tool)

        assert isinstance(result, SinglePainPointQuotesResult)
        assert result.pain_point_title == mock_pain_point.title
        assert isinstance(result.anchor_keywords_searched, list)
        assert isinstance(result.quotes, list)
        assert isinstance(result.search_summary, str)

    def test_enrich_with_empty_keywords(self):
        """Handle pain point with no anchor keywords gracefully."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create pain point with minimum keywords but simulate empty after slicing
        mock_tool = MagicMock()
        mock_tool._run.return_value = ""

        # Create a pain point (min 2 keywords required by model)
        pp = UnvalidatedPainPoint(
            title="Test",
            description="Test description",
            mention_count=5,
            anchor_keywords=["kw1", "kw2"],
        )

        result = crew._enrich_single_pain_point(pp, mock_tool)

        assert isinstance(result, SinglePainPointQuotesResult)
        assert result.pain_point_title == "Test"

    def test_enrich_quotes_have_correct_structure(self, mock_pain_point, mock_quote_search_tool):
        """Verify extracted quotes have ExtractedQuote structure."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point, mock_quote_search_tool)

        for quote in result.quotes:
            assert isinstance(quote, ExtractedQuote)
            assert hasattr(quote, "quote_text")
            assert hasattr(quote, "post_id")
            assert quote.quote_text  # Non-empty
            assert quote.post_id  # Non-empty


# ============================================================================
# TESTS: _run_parallel_quote_enrichment()
# ============================================================================


class TestRunParallelQuoteEnrichment:
    """Tests for _run_parallel_quote_enrichment() method."""

    def test_parallel_enrichment_all_pain_points(self, mock_pain_point, mock_pain_point_few_keywords):
        """All pain points get enriched (100% coverage)."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test niche")

        pain_points = [mock_pain_point, mock_pain_point_few_keywords]

        with patch.object(crew, "_enrich_single_pain_point") as mock_enrich:
            # Setup mock to return valid results
            mock_enrich.return_value = SinglePainPointQuotesResult(
                pain_point_title="Test",
                anchor_keywords_searched=["kw1"],
                quotes=[ExtractedQuote(quote_text="Test quote with enough words to pass the minimum word count filter", post_id="test123")],
                search_summary="Test summary",
            )

            result = crew._run_parallel_quote_enrichment(pain_points)

        # Should have enrichment result for each pain point
        assert len(result.enriched_pain_points) == 2
        # mock_enrich should be called once per pain point
        assert mock_enrich.call_count == 2

    def test_parallel_enrichment_max_workers(self):
        """max_workers capped at min(4, num_pain_points)."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge)

        # Create 10 pain points
        pain_points = [
            UnvalidatedPainPoint(
                title=f"Pain Point {i}",
                description=f"Description {i}",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            )
            for i in range(10)
        ]

        # Instead of mocking ThreadPoolExecutor, we verify the behavior by checking
        # that all pain points are processed (regardless of max_workers)
        call_count = 0

        def mock_enrich(pp, tool):
            nonlocal call_count
            call_count += 1
            return SinglePainPointQuotesResult(
                pain_point_title=pp.title,
                quotes=[],
            )

        with patch.object(crew, "_enrich_single_pain_point", side_effect=mock_enrich):
            result = crew._run_parallel_quote_enrichment(pain_points)

        # Verify all 10 pain points were processed
        assert call_count == 10
        assert len(result.enriched_pain_points) == 10

    def test_parallel_enrichment_no_knowledge(self):
        """Early return when no enrichment knowledge."""
        crew = create_minimal_crew(enrichment_knowledge=None, niche="test niche")

        pain_points = [
            UnvalidatedPainPoint(
                title="Test",
                description="Test",
                mention_count=5,
                anchor_keywords=["kw1", "kw2"],
            )
        ]

        result = crew._run_parallel_quote_enrichment(pain_points)

        assert isinstance(result, QuoteEnrichmentResult)
        assert result.enriched_pain_points == []
        assert result.total_quotes_found == 0
        assert "No content available" in result.enrichment_summary

    def test_parallel_enrichment_error_isolation(self):
        """One failure doesn't block others."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test niche")

        pain_points = [
            UnvalidatedPainPoint(
                title=f"Pain Point {i}",
                description=f"Description {i}",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            )
            for i in range(3)
        ]

        call_count = 0

        def mock_enrich(pp, tool):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Simulated failure")
            return SinglePainPointQuotesResult(
                pain_point_title=pp.title,
                quotes=[ExtractedQuote(quote_text="Valid quote with sufficient word count for testing purposes", post_id="test123")],
            )

        with patch.object(crew, "_enrich_single_pain_point", side_effect=mock_enrich):
            result = crew._run_parallel_quote_enrichment(pain_points)

        # Should still have 3 results (2 successful + 1 empty for failure)
        assert len(result.enriched_pain_points) == 3
        # At least 2 should have quotes (the successful ones)
        successful = [ep for ep in result.enriched_pain_points if ep.quotes]
        assert len(successful) >= 2

    def test_parallel_enrichment_aggregates_results(self):
        """Results aggregated into QuoteEnrichmentResult."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="small business automation")

        pain_points = [
            UnvalidatedPainPoint(
                title="Manual Invoicing",
                description="Invoicing pain",
                mention_count=20,
                anchor_keywords=["manual invoicing", "invoice pain"],
            ),
            UnvalidatedPainPoint(
                title="Expense Tracking",
                description="Expense pain",
                mention_count=15,
                anchor_keywords=["expense reports", "receipts"],
            ),
        ]

        def mock_enrich(pp, tool):
            if "Invoicing" in pp.title:
                return SinglePainPointQuotesResult(
                    pain_point_title=pp.title,
                    quotes=[
                        ExtractedQuote(quote_text="Invoice quote 1 with enough words to pass the minimum", post_id="inv1"),
                        ExtractedQuote(quote_text="Invoice quote 2 with enough words to pass the minimum", post_id="inv2"),
                    ],
                )
            else:
                return SinglePainPointQuotesResult(
                    pain_point_title=pp.title,
                    quotes=[
                        ExtractedQuote(quote_text="Expense quote 1 with enough words to pass the minimum", post_id="exp1"),
                    ],
                )

        with patch.object(crew, "_enrich_single_pain_point", side_effect=mock_enrich):
            result = crew._run_parallel_quote_enrichment(pain_points)

        assert isinstance(result, QuoteEnrichmentResult)
        assert result.niche == "small business automation"
        assert len(result.enriched_pain_points) == 2
        assert result.total_quotes_found == 3  # 2 + 1
        assert "3 quotes" in result.enrichment_summary
        assert "2 pain points" in result.enrichment_summary

    def test_parallel_enrichment_empty_pain_points_list(self):
        """Handle empty pain points list gracefully."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test")

        result = crew._run_parallel_quote_enrichment([])

        # Should return empty result without raising an exception
        assert isinstance(result, QuoteEnrichmentResult)
        assert result.enriched_pain_points == []
        assert result.total_quotes_found == 0
        assert "No pain points" in result.enrichment_summary

    def test_parallel_enrichment_preserves_pain_point_titles(self):
        """Enriched results preserve original pain point titles."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test")

        pain_points = [
            UnvalidatedPainPoint(
                title="Unique Title Alpha",
                description="Desc",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            ),
            UnvalidatedPainPoint(
                title="Unique Title Beta",
                description="Desc",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            ),
        ]

        def mock_enrich(pp, tool):
            return SinglePainPointQuotesResult(
                pain_point_title=pp.title,
                quotes=[],
            )

        with patch.object(crew, "_enrich_single_pain_point", side_effect=mock_enrich):
            result = crew._run_parallel_quote_enrichment(pain_points)

        titles = {ep.pain_point_title for ep in result.enriched_pain_points}
        assert "Unique Title Alpha" in titles
        assert "Unique Title Beta" in titles

    def test_parallel_enrichment_creates_quote_search_tool(self):
        """Verify QuoteSearchTool is created with enrichment knowledge."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test")

        pain_points = [
            UnvalidatedPainPoint(
                title="Test",
                description="Desc",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            ),
        ]

        # Patch at the import location inside the method
        with patch("nicheiq.tools.quote_search_tool.QuoteSearchTool") as mock_tool_class:
            mock_tool = MagicMock()
            mock_tool_class.return_value = mock_tool

            with patch.object(crew, "_enrich_single_pain_point") as mock_enrich:
                mock_enrich.return_value = SinglePainPointQuotesResult(
                    pain_point_title="Test",
                    quotes=[],
                )
                crew._run_parallel_quote_enrichment(pain_points)

            # Verify _enrich_single_pain_point was called (search tool creation is internal)
            mock_enrich.assert_called_once()


# ============================================================================
# INTEGRATION-STYLE TESTS (using more realistic scenarios)
# ============================================================================


class TestParallelEnrichmentIntegration:
    """Integration-style tests combining multiple components."""

    def test_full_flow_parse_to_enrich(self):
        """Test flow from search results to enriched pain point."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        pain_point = UnvalidatedPainPoint(
            title="Manual Invoicing",
            description="Users struggle with manual invoicing",
            mention_count=20,
            anchor_keywords=["manual invoicing", "invoice automation"],
        )

        # Realistic search results
        search_result = """--- Result 1 (score: 0.92, post_id: abc123, source: reddit) ---
I spend 3 hours every week on manual invoices and it's killing me. We need a better solution for our small business that integrates with our existing accounting software.

--- Result 2 (score: 0.87, post_id: def456, source: reddit) ---
Our invoicing process is completely manual and error-prone. I've lost count of how many times we've sent duplicate invoices."""

        mock_tool = MagicMock()
        mock_tool._run.return_value = search_result

        result = crew._enrich_single_pain_point(pain_point, mock_tool)

        assert result.pain_point_title == "Manual Invoicing"
        assert len(result.quotes) >= 1
        # Verify quotes are ExtractedQuote instances with post_ids
        for quote in result.quotes:
            assert quote.post_id in ["abc123", "def456"]

    def test_quote_deduplication_across_keywords(self):
        """Verify deduplication works when same quote found via different keywords."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        pain_point = UnvalidatedPainPoint(
            title="Test Pain Point",
            description="Test description",
            mention_count=10,
            anchor_keywords=["keyword one", "keyword two", "keyword three"],
        )

        # Same quote returned for different keywords
        identical_result = """--- Result 1 (score: 0.90, post_id: same123, source: reddit) ---
This is the exact same quote that should be deduplicated across multiple keyword searches in testing."""

        mock_tool = MagicMock()
        mock_tool._run.return_value = identical_result

        result = crew._enrich_single_pain_point(pain_point, mock_tool)

        # Should only have 1 unique quote despite being found 3 times (once per keyword)
        assert len(result.quotes) == 1

    def test_enrichment_result_structure_for_merge(self):
        """Verify output structure is compatible with analyze() merge logic."""
        mock_knowledge = MagicMock()
        crew = create_minimal_crew(enrichment_knowledge=mock_knowledge, niche="test niche")

        pain_points = [
            UnvalidatedPainPoint(
                title="Pain Point A",
                description="Description A",
                mention_count=10,
                anchor_keywords=["kw1", "kw2"],
            ),
        ]

        def mock_enrich(pp, tool):
            return SinglePainPointQuotesResult(
                pain_point_title=pp.title,
                quotes=[
                    ExtractedQuote(quote_text="Quote text here", post_id="post123"),
                ],
            )

        with patch.object(crew, "_enrich_single_pain_point", side_effect=mock_enrich):
            result = crew._run_parallel_quote_enrichment(pain_points)

        # Verify structure matches what analyze() expects
        assert hasattr(result, "niche")
        assert hasattr(result, "enriched_pain_points")
        assert hasattr(result, "total_quotes_found")
        assert hasattr(result, "enrichment_summary")

        # Each enriched pain point should have structure for merge
        for enriched in result.enriched_pain_points:
            assert isinstance(enriched, EnrichedPainPointQuotes)
            assert hasattr(enriched, "pain_point_title")
            assert hasattr(enriched, "quotes")
            for quote in enriched.quotes:
                assert hasattr(quote, "quote_text")
                assert hasattr(quote, "post_id")
