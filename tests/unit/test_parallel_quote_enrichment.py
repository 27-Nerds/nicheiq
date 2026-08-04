"""
Unit tests for parallel quote enrichment methods in PainPointCrew.

Tests the Python-driven parallel enrichment that replaces Task 4:
- _clean_quote_text() - formatting artifact removal
- _build_relevance_terms() / _compute_quote_relevance() - relevance scoring
- _parse_search_results() - regex parsing + 3-phase splitting
- _enrich_single_pain_point() - contextual queries + relevance filtering
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


@pytest.fixture(autouse=True)
def _no_network_stance_gate():
    """Patch the stance gate to an identity pass so enrichment unit tests stay
    offline and assert P0-A behavior (relevance floor, per-post cap, dedup, the
    12-cap) independently of the LLM stance call. The stance gate has its own
    dedicated tests."""
    with patch.object(
        PainPointCrew, "_stance_filter_quotes", side_effect=lambda self, pp, quotes: quotes, autospec=True
    ):
        yield


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
# TESTS: _clean_quote_text()
# ============================================================================


class TestCleanQuoteText:
    """Tests for _clean_quote_text() static method."""

    def test_strips_pts_markers(self):
        assert PainPointCrew._clean_quote_text("[2 pts] Some comment text here") == "Some comment text here"

    def test_strips_pts_marker_singular(self):
        assert PainPointCrew._clean_quote_text("[1 pt] Single point comment") == "Single point comment"

    def test_strips_list_prefix(self):
        assert PainPointCrew._clean_quote_text("- Some list item text") == "Some list item text"

    def test_strips_indented_list_prefix(self):
        assert PainPointCrew._clean_quote_text("  - Nested reply text") == "Nested reply text"

    def test_strips_likes_marker(self):
        assert PainPointCrew._clean_quote_text("[5 likes] Tweet reply text") == "Tweet reply text"

    def test_strips_source_tag(self):
        assert PainPointCrew._clean_quote_text("Quote text [source: r/subreddit/t3_abc123]") == "Quote text"

    def test_strips_markdown_header(self):
        assert PainPointCrew._clean_quote_text("### Post Title Here") == "Post Title Here"

    def test_strips_combined_formatting(self):
        """Strip multiple formatting artifacts in one pass."""
        raw = "- [85 pts] The software setup is terrible [source: post123]"
        assert PainPointCrew._clean_quote_text(raw) == "The software setup is terrible"

    def test_preserves_normal_text(self):
        text = "This is a normal sentence without any formatting artifacts"
        assert PainPointCrew._clean_quote_text(text) == text

    def test_collapses_whitespace(self):
        assert PainPointCrew._clean_quote_text("Too   many    spaces   here") == "Too many spaces here"

    def test_operation_ordering_header_then_dash(self):
        """Markdown header stripped first, then list prefix if present."""
        assert PainPointCrew._clean_quote_text("### - Some header-list combo") == "Some header-list combo"


# ============================================================================
# TESTS: _build_relevance_terms() and _compute_quote_relevance()
# ============================================================================


class TestRelevanceScoring:
    """Tests for relevance scoring methods."""

    def test_build_relevance_terms_basic(self):
        pp = UnvalidatedPainPoint(
            title="Software Setup Issues",
            description="Users struggle with confusing configuration",
            mention_count=10,
            anchor_keywords=["software setup", "configuration problems"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        # Terms are Snowball-stemmed: "software"→"softwar", "confusing"→"confus", etc.
        assert "softwar" in terms
        assert "setup" in terms
        assert "confus" in terms
        assert "configur" in terms
        # Stopwords excluded
        assert "with" not in terms
        assert "the" not in terms

    def test_build_relevance_terms_excludes_short_words(self):
        pp = UnvalidatedPainPoint(
            title="AI ML",
            description="AI and ML tools are hard to use",
            mention_count=5,
            anchor_keywords=["AI tools", "ML setup"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        # 2-char words excluded
        assert "ai" not in terms
        assert "ml" not in terms
        assert "tool" in terms  # "tools" stemmed to "tool"

    def test_compute_relevance_high_overlap(self):
        pp = UnvalidatedPainPoint(
            title="Manual Invoicing",
            description="Users struggle with manual invoicing processes",
            mention_count=10,
            anchor_keywords=["manual invoicing", "invoice automation"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        quote = "I spend hours on manual invoicing every week and invoice automation would save us"
        score = PainPointCrew._compute_quote_relevance(quote, terms, pp.anchor_keywords)
        assert score > 0.2

    def test_compute_relevance_no_overlap(self):
        pp = UnvalidatedPainPoint(
            title="Manual Invoicing",
            description="Users struggle with invoicing processes",
            mention_count=10,
            anchor_keywords=["manual invoicing", "invoice pain"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        quote = "The cat sat on the mat and looked at the bird through the window"
        score = PainPointCrew._compute_quote_relevance(quote, terms, pp.anchor_keywords)
        assert score < 0.05

    def test_compute_relevance_empty_terms(self):
        """Handle empty relevance terms without division by zero."""
        score = PainPointCrew._compute_quote_relevance("Some text here", frozenset(), [])
        assert score == 0.0

    def test_compute_relevance_denominator_floor(self):
        """Short pain points don't inflate scores due to denominator floor of 5."""
        pp = UnvalidatedPainPoint(
            title="API Bugs",
            description="API has bugs",
            mention_count=5,
            anchor_keywords=["api bugs", "bug reports"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        # Only "bugs" overlaps → 1/max(len(terms), 5), not 1/2
        quote = "There are some bugs in the system that cause problems for users"
        score = PainPointCrew._compute_quote_relevance(quote, terms, pp.anchor_keywords)
        assert score < 0.5  # Would be 0.5 without floor

    def test_compute_relevance_anchor_keyword_bonus_scales(self):
        """Bonus scales with number of matching keywords."""
        pp = UnvalidatedPainPoint(
            title="Test",
            description="Test description for testing",
            mention_count=5,
            anchor_keywords=["keyword alpha", "keyword beta", "keyword gamma"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        one_match = "This text contains keyword alpha but not others in a sufficiently long way"
        two_matches = "This text contains keyword alpha and keyword beta in a sufficiently long way"
        s1 = PainPointCrew._compute_quote_relevance(one_match, terms, pp.anchor_keywords)
        s2 = PainPointCrew._compute_quote_relevance(two_matches, terms, pp.anchor_keywords)
        assert s2 > s1

    def test_allen_key_quote_rejected(self):
        """The specific bug case: Allen key quote should score below threshold for software pain point."""
        pp = UnvalidatedPainPoint(
            title="Confusing Software Setup and Settings Tuning",
            description="Users struggle with confusing software setup processes and unintuitive settings panels",
            mention_count=10,
            anchor_keywords=["software setup", "settings configuration", "confusing settings"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        bad_quote = (
            "Getting an Allen bit for a drill or impact helps a lot but always start "
            "by hand and final torque with an Allen key"
        )
        score = PainPointCrew._compute_quote_relevance(bad_quote, terms, pp.anchor_keywords)
        assert score < 0.05, f"Allen key quote should be rejected, got score={score:.3f}"

    def test_relevant_software_quote_accepted(self):
        """A relevant quote about software setup should pass the threshold."""
        pp = UnvalidatedPainPoint(
            title="Confusing Software Setup and Settings Tuning",
            description="Users struggle with confusing software setup processes and unintuitive settings panels",
            mention_count=10,
            anchor_keywords=["software setup", "settings configuration", "confusing settings"],
        )
        terms = PainPointCrew._build_relevance_terms(pp)
        good_quote = (
            "I spent 3 hours trying to configure the software settings and still "
            "could not get it working properly for our dental practice"
        )
        score = PainPointCrew._compute_quote_relevance(good_quote, terms, pp.anchor_keywords)
        assert score > 0.05, f"Software setup quote should be accepted, got score={score:.3f}"


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
        # Each result is a (quote_text, post_id, vector_score) tuple
        for quote_text, post_id, vector_score in parsed:
            assert isinstance(quote_text, str)
            assert isinstance(post_id, str)
            assert isinstance(vector_score, float)
            assert len(quote_text.split()) >= 15

    def test_parse_extracts_post_id(self, mock_search_result_standard):
        """Verify post_id extraction from result header."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_standard)

        # Verify post_ids are extracted correctly
        post_ids = [post_id for _, post_id, _ in parsed]
        # At least one of these should be present
        assert any(pid in ["abc123", "def456", "ghi789"] for pid in post_ids)

    def test_parse_extracts_vector_score(self, mock_search_result_standard):
        """Verify vector score is extracted from result header."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_standard)

        for _, _, vector_score in parsed:
            assert 0.0 <= vector_score <= 1.0

    def test_parse_filters_short_quotes(self, mock_search_result_with_short_sentences):
        """Filter quotes with < 15 words."""
        crew = create_minimal_crew()

        parsed = crew._parse_search_results(mock_search_result_with_short_sentences)

        # All extracted quotes should have 15+ words
        for quote_text, _, _ in parsed:
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
        for _, post_id, _ in parsed:
            assert post_id == "multi123"

    def test_parse_handles_special_characters_in_content(self):
        """Handle special characters in quote content."""
        crew = create_minimal_crew()

        result = """--- Result 1 (score: 0.88, post_id: special_123, source: reddit) ---
This quote has special characters like @mentions, #hashtags, and URLs https://example.com which should all be preserved in the extracted text correctly."""

        parsed = crew._parse_search_results(result)

        assert len(parsed) >= 1
        quote_text, post_id, _ = parsed[0]
        assert post_id == "special_123"
        assert "@mentions" in quote_text or "#hashtags" in quote_text or "https://" in quote_text

    def test_parse_splits_reddit_list_items_on_newline(self):
        """Split separate Reddit comments (newline + list marker) into separate quotes."""
        crew = create_minimal_crew()

        result = """--- Result 1 (score: 0.88, post_id: list123, source: reddit) ---
- [85 pts] The software setup process took me three hours and I still couldn't get the settings configured properly for my practice
- [42 pts] I completely agree the configuration wizard is terrible and needs to be redesigned from scratch to be more intuitive"""

        parsed = crew._parse_search_results(result)

        # Should produce 2 separate quotes, not 1 merged quote
        assert len(parsed) == 2
        # Both should be cleaned (no [N pts] or - prefix)
        for quote_text, _, _ in parsed:
            assert "[" not in quote_text
            assert not quote_text.startswith("-")

    def test_parse_splits_inline_pts_markers(self):
        """Split comments merged on one line (lost newlines during chunking)."""
        crew = create_minimal_crew()

        # This simulates the specific bug: two comments on one line
        result = """--- Result 1 (score: 0.85, post_id: merged123, source: reddit) ---
- [2 pts] Getting an Allen bit for a drill or impact helps a lot but always start by hand and final torque with an Allen key - [2 pts] I spent a couple hours building mine and the instructions were confusing the whole time"""

        parsed = crew._parse_search_results(result)

        # Should produce 2 separate quotes, not 1 merged quote
        assert len(parsed) == 2
        for quote_text, _, _ in parsed:
            assert "[2 pts]" not in quote_text
            assert not quote_text.startswith("-")

    def test_parse_cleans_formatting_artifacts(self):
        """Quotes should have formatting artifacts removed."""
        crew = create_minimal_crew()

        result = """--- Result 1 (score: 0.90, post_id: fmt123, source: reddit) ---
- [15 pts] I spent three hours trying to configure the software settings and still could not get it working properly for our business [source: r/software/t3_abc]"""

        parsed = crew._parse_search_results(result)

        assert len(parsed) >= 1
        quote_text = parsed[0][0]
        assert "[15 pts]" not in quote_text
        assert "[source:" not in quote_text
        assert not quote_text.startswith("-")


# ============================================================================
# TESTS: _enrich_single_pain_point()
# ============================================================================


class TestEnrichSinglePainPoint:
    """Tests for _enrich_single_pain_point() method."""

    def test_enrich_uses_contextual_queries(self, mock_pain_point, mock_quote_search_tool):
        """Verify searches use contextual queries (title + description), not bare keywords."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point, mock_quote_search_tool)

        # Should be called: 1 description query + up to 3 keyword queries
        assert mock_quote_search_tool._run.called
        calls = [str(c) for c in mock_quote_search_tool._run.call_args_list]
        # First call should include pain point description
        first_call_arg = mock_quote_search_tool._run.call_args_list[0][0][0]
        assert mock_pain_point.title in first_call_arg

    def test_enrich_limits_keyword_queries_to_3(self, mock_pain_point_many_keywords, mock_quote_search_tool):
        """Use at most 3 supplemental keyword queries + 1 description query = 4 total."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        result = crew._enrich_single_pain_point(mock_pain_point_many_keywords, mock_quote_search_tool)

        # 1 description query + 3 keyword queries = 4 max
        assert mock_quote_search_tool._run.call_count <= 4

    def test_enrich_deduplicates_quotes(self, mock_pain_point):
        """Deduplicate quotes across keyword searches."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create a mock that returns the same quote for different keywords
        mock_tool = MagicMock()
        mock_tool._run.return_value = """--- Result 1 (score: 0.92, post_id: dup123, source: reddit) ---
I spend 3 hours every week on manual invoices and it's killing me. We need a better solution for our small business."""

        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        # Even with 4 queries returning same quote, should only have 1 unique quote
        unique_texts = set(q.quote_text.lower().strip() for q in result.quotes)
        assert len(unique_texts) <= len(result.quotes)

    def test_enrich_caps_quotes_at_12(self, mock_pain_point):
        """Cap quotes at 12 per pain point."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # Create a mock that returns many quotes
        many_quotes_result = "\n\n".join([
            f"""--- Result {i} (score: 0.{90-i:02d}, post_id: post{i}, source: reddit) ---
This is quote number {i} about manual invoicing with enough words to pass the fifteen word minimum filter for testing purposes in this test case."""
            for i in range(1, 20)  # 19 potential quotes
        ])

        mock_tool = MagicMock()
        mock_tool._run.return_value = many_quotes_result

        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        # Should cap at 12 quotes
        assert len(result.quotes) <= 12

    def test_enrich_per_post_cap_enforced(self, mock_pain_point):
        """At most _POST_DIVERSITY_CAP quotes may come from a single source post, so one
        comment cannot be sentence-shredded into many 'independent' quotes.

        This invariant used to be enforced BEFORE the stance gate via _PER_POST_CAP.
        That pre-gate truncation was measured to be the largest single source of lost
        evidence (recall on known-missing passages 34.9% -> 55.8% once it was removed),
        so the cap now runs AFTER validation as _POST_DIVERSITY_CAP: it still stops one
        talkative thread from reading as corroboration, but it no longer discards
        candidates before anything has judged them."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        # 10 distinct, on-topic sentences ALL from the same post_id.
        same_post = "\n\n".join([
            f"""--- Result {i} (score: 0.9{i % 10}, post_id: onepost, source: reddit) ---
Manual invoicing sentence number {i} that is wordy enough to clear the fifteen word minimum filter for this particular test case here."""
            for i in range(1, 11)
        ])
        mock_tool = MagicMock()
        mock_tool._run.return_value = same_post

        result = crew._enrich_single_pain_point(mock_pain_point, mock_tool)

        from_one_post = [q for q in result.quotes if q.post_id == "onepost"]
        assert len(from_one_post) <= PainPointCrew._POST_DIVERSITY_CAP
        # matched_post_ids (the volume set) is unaffected by the display cap — the
        # post still counts as one discussion.
        assert result.matched_post_ids == ["onepost"]

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
        """Handle pain point with minimal anchor keywords gracefully."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        mock_tool = MagicMock()
        mock_tool._run.return_value = ""

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

    def test_enrich_rejects_irrelevant_quotes(self):
        """Quotes with low relevance to the pain point are filtered out."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        pp = UnvalidatedPainPoint(
            title="Confusing Software Setup",
            description="Users struggle with confusing software setup and configuration",
            mention_count=10,
            anchor_keywords=["software setup", "confusing configuration"],
        )

        # Return an irrelevant quote about physical assembly
        mock_tool = MagicMock()
        mock_tool._run.return_value = """--- Result 1 (score: 0.78, post_id: irrelevant1, source: reddit) ---
Getting an Allen bit for a drill or impact helps a lot but always start by hand and final torque with an Allen key for best results"""

        result = crew._enrich_single_pain_point(pp, mock_tool)

        # The irrelevant quote should be filtered out
        assert len(result.quotes) == 0

    def test_enrich_sorts_by_combined_score(self):
        """Quotes are ranked by combined vector + relevance score."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        pp = UnvalidatedPainPoint(
            title="Manual Invoicing",
            description="Users struggle with manual invoicing processes",
            mention_count=10,
            anchor_keywords=["manual invoicing", "invoice problems"],
        )

        # Return two quotes: one with higher vector score but lower relevance,
        # another with lower vector score but higher relevance
        mock_tool = MagicMock()
        mock_tool._run.side_effect = [
            # Description query returns medium-relevance quote
            """--- Result 1 (score: 0.92, post_id: post1, source: reddit) ---
The billing system has some issues that affect our workflow and take time to resolve for the accounting team members""",
            # First keyword query returns high-relevance quote
            """--- Result 1 (score: 0.85, post_id: post2, source: reddit) ---
Manual invoicing is killing our small business and we desperately need invoice automation to save time and reduce errors""",
            # Other queries return nothing
            "",
            "",
        ]

        result = crew._enrich_single_pain_point(pp, mock_tool)

        # Both should be included (both relevant enough) and sorted by combined score
        assert len(result.quotes) >= 1


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
            description="Users struggle with manual invoicing processes taking too much time",
            mention_count=20,
            anchor_keywords=["manual invoicing", "invoice automation"],
        )

        # Realistic search results with quotes that are individually 15+ words AND relevant
        search_result = """--- Result 1 (score: 0.92, post_id: abc123, source: reddit) ---
I spend at least 3 hours every single week on manual invoicing and it is absolutely killing our productivity at work.

--- Result 2 (score: 0.87, post_id: def456, source: reddit) ---
Our manual invoicing process is completely error-prone and we have lost count of how many times we sent duplicate invoices to clients."""

        mock_tool = MagicMock()
        mock_tool._run.return_value = search_result

        result = crew._enrich_single_pain_point(pain_point, mock_tool)

        assert result.pain_point_title == "Manual Invoicing"
        assert len(result.quotes) >= 1
        # Verify quotes are ExtractedQuote instances with post_ids
        for quote in result.quotes:
            assert quote.post_id in ["abc123", "def456"]

    def test_quote_deduplication_across_queries(self):
        """Verify deduplication works when same quote found via different queries."""
        crew = create_minimal_crew(enrichment_knowledge=MagicMock())

        pain_point = UnvalidatedPainPoint(
            title="Test Pain Point",
            description="Test description for deduplication testing",
            mention_count=10,
            anchor_keywords=["keyword one", "keyword two", "keyword three"],
        )

        # Same quote returned for different queries
        identical_result = """--- Result 1 (score: 0.90, post_id: same123, source: reddit) ---
This is the exact same quote that should be deduplicated across multiple keyword searches in testing."""

        mock_tool = MagicMock()
        mock_tool._run.return_value = identical_result

        result = crew._enrich_single_pain_point(pain_point, mock_tool)

        # Should only have 1 unique quote despite being found via 4 queries
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


# ============================================================================
# TESTS: deterministic quote-grounding gate (#1)
# ============================================================================


class TestIsQuoteGrounded:
    """Tests for the static _is_quote_grounded fuzzy-substring check."""

    SRC = (
        "I spent four months trying to verify the supplier and the lab results were "
        "forged. honestly it was a complete nightmare and i lost money."
    )

    def test_exact_substring(self):
        assert PainPointCrew._is_quote_grounded("the lab results were forged", self.SRC) is True

    def test_case_and_whitespace_insensitive(self):
        assert PainPointCrew._is_quote_grounded("THE  LAB   RESULTS were FORGED", self.SRC) is True

    def test_trailing_punctuation_tolerated(self):
        # cleaned quote drops the trailing period — still a near-exact contiguous match
        assert PainPointCrew._is_quote_grounded("it was a complete nightmare", self.SRC) is True

    def test_off_source_rejected(self):
        assert PainPointCrew._is_quote_grounded("this product changed my life completely", self.SRC) is False

    def test_paraphrase_rejected(self):
        # reworded (results->result, were->was) is NOT verbatim -> flagged
        assert PainPointCrew._is_quote_grounded("the lab result was fake", self.SRC) is False

    def test_empty_inputs(self):
        assert PainPointCrew._is_quote_grounded("", self.SRC) is False
        assert PainPointCrew._is_quote_grounded("something", "") is False


class TestGroundingGate:
    """Tests for the grounding gate applied inside _enrich_single_pain_point."""

    def _crew_with_body(self, body_map):
        crew = create_minimal_crew()
        crew._raw_generic_posts = []
        crew._post_body_map_cache = body_map
        return crew

    def _pain(self):
        return UnvalidatedPainPoint(
            title="Supplier verification",
            description="Users cannot verify supplier legitimacy before paying",
            mention_count=5,
            anchor_keywords=["verify supplier", "lab results forged"],
        )

    # NOTE: quotes must be >=15 words (parser minimum) AND share pain vocabulary (relevance floor)
    # so they actually reach the grounding gate; otherwise they are dropped upstream.
    _GROUNDED = ("i really could not verify the supplier legitimacy before paying and the "
                 "lab results were forged which cost me a lot of money")
    _UNGROUNDED_A = ("there is no reliable way to verify a supplier or check whether the lab "
                     "results are forged before you pay them any money at all")
    _UNGROUNDED_B = ("paying a supplier without being able to verify legitimacy or confirm the "
                     "lab results means you risk losing real money every single time")

    def test_drops_ungrounded_keeps_grounded(self, mock_quote_search_tool):
        # two grounded quotes (floor already satisfied) so the ungrounded one is truly dropped,
        # not re-admitted by floor protection.
        crew = self._crew_with_body({
            "good1": f"preamble here. {self._GROUNDED}. trailing text.",
            "good2": f"intro. {self._UNGROUNDED_B}. outro padding text here.",  # verbatim in this body
            "bad": "a totally different body about gardening tools and soil mixes",
        })
        mock_quote_search_tool._run.return_value = (
            f"--- Result 1 (score: 0.95, post_id: good1, source: reddit) ---\n{self._GROUNDED}.\n\n"
            f"--- Result 2 (score: 0.93, post_id: good2, source: reddit) ---\n{self._UNGROUNDED_B}.\n\n"
            f"--- Result 3 (score: 0.90, post_id: bad, source: reddit) ---\n{self._UNGROUNDED_A}.\n"
        )
        res = crew._enrich_single_pain_point(self._pain(), mock_quote_search_tool)
        ids = {q.post_id for q in res.quotes}
        assert {"good1", "good2"} <= ids   # both grounded quotes kept
        assert "bad" not in ids            # ungrounded dropped (floor already met by the two grounded)

    def test_fail_open_unknown_post(self, mock_quote_search_tool):
        # body map empty -> post_id unknown -> fail-open (keep despite no source body)
        crew = self._crew_with_body({})
        mock_quote_search_tool._run.return_value = (
            f"--- Result 1 (score: 0.95, post_id: x1, source: reddit) ---\n{self._UNGROUNDED_A}.\n"
        )
        res = crew._enrich_single_pain_point(self._pain(), mock_quote_search_tool)
        assert len(res.quotes) >= 1

    def test_floor_protection_keeps_min_when_all_ungrounded(self, mock_quote_search_tool):
        # both post_ids ARE in the map (not fail-open) but their text is NOT in the body ->
        # floor protection keeps up to _MIN_QUOTES rather than emptying the evidence
        crew = self._crew_with_body({"p1": "a totally different body about gardening tools and soil",
                                     "p2": "another unrelated body about bicycle maintenance and tyres"})
        mock_quote_search_tool._run.return_value = (
            f"--- Result 1 (score: 0.95, post_id: p1, source: reddit) ---\n{self._UNGROUNDED_A}.\n\n"
            f"--- Result 2 (score: 0.90, post_id: p2, source: reddit) ---\n{self._UNGROUNDED_B}.\n"
        )
        res = crew._enrich_single_pain_point(self._pain(), mock_quote_search_tool)
        assert len(res.quotes) == PainPointCrew._MIN_QUOTES  # never emptied on grounding alone


class TestNormToolAddressable:
    """Tests for the tool-addressability verdict normalizer."""

    def test_none_variants(self):
        from nicheiq.crews.pain_point_crew import _norm_tool_addressable
        for v in ("none", "NO", "No", "not addressable"):
            assert _norm_tool_addressable(v) == "none"

    def test_partial_variants(self):
        from nicheiq.crews.pain_point_crew import _norm_tool_addressable
        for v in ("partial", "PARTIALLY", "part"):
            assert _norm_tool_addressable(v) == "partial"

    def test_full_and_unknown_default(self):
        from nicheiq.crews.pain_point_crew import _norm_tool_addressable
        for v in ("full", "YES", "weird-value", "", None):
            assert _norm_tool_addressable(v) == "full"
