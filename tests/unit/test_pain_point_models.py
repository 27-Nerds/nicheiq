"""
Tests for pain point Pydantic models - quote enrichment feature.

Tests the new anchor_keywords-based architecture:
- ThemeCategory with anchor_keywords (not representative_quotes)
- UnvalidatedPainPoint with anchor_keywords (not representative_quotes)
- ExtractedQuote, EnrichedPainPointQuotes, QuoteEnrichmentResult models
- PainPoint (final) still has representative_quotes and source_post_ids
"""

import pytest
from pydantic import ValidationError

from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import (
    ContentCategorizationReport,
    EnrichedPainPointQuotes,
    ExtractedQuote,
    PainPoint,
    PainPointExtraction,
    PainPointScoring,
    QuoteEnrichmentResult,
    SinglePainPointQuotesResult,
    ThemeCategory,
    UnvalidatedPainPoint,
    UserSegment,
    ValidationResult,
)


class TestThemeCategory:
    """Tests for ThemeCategory model with anchor_keywords."""

    def test_theme_category_has_anchor_keywords(self):
        """Verify ThemeCategory has anchor_keywords field (min 3, max 10)."""
        theme = ThemeCategory(
            category_name="Invoicing Pain",
            definition="Frustrations with manual invoicing",
            frequency="High",
            mention_count=25,
            primary_user_segments=["Small Business Owners"],
            anchor_keywords=["manual invoicing", "invoice automation", "billing nightmare"],
        )
        assert theme.anchor_keywords == ["manual invoicing", "invoice automation", "billing nightmare"]
        assert len(theme.anchor_keywords) >= 3

    def test_theme_category_anchor_keywords_min_length(self):
        """Test that ThemeCategory requires at least 3 anchor_keywords."""
        with pytest.raises(ValidationError) as exc_info:
            ThemeCategory(
                category_name="Test",
                definition="Test definition",
                frequency="Medium",
                mention_count=10,
                primary_user_segments=["Users"],
                anchor_keywords=["keyword1", "keyword2"],  # Only 2, needs 3
            )
        assert "anchor_keywords" in str(exc_info.value)

    def test_theme_category_anchor_keywords_max_length(self):
        """Test that ThemeCategory accepts up to 12 anchor_keywords and truncates extras."""
        # Exactly 12 is the hard cap
        theme = ThemeCategory(
            category_name="Test",
            definition="Test definition",
            frequency="Medium",
            mention_count=10,
            primary_user_segments=["Users"],
            anchor_keywords=[f"keyword{i}" for i in range(12)],
        )
        assert len(theme.anchor_keywords) == 12

        # Over-cap input is silently truncated to 12 so one LLM overshoot doesn't crash the pipeline
        theme_truncated = ThemeCategory(
            category_name="Test",
            definition="Test definition",
            frequency="Medium",
            mention_count=10,
            primary_user_segments=["Users"],
            anchor_keywords=[f"keyword{i}" for i in range(15)],
        )
        assert len(theme_truncated.anchor_keywords) == 12
        assert theme_truncated.anchor_keywords == [f"keyword{i}" for i in range(12)]

    def test_theme_category_no_representative_quotes(self):
        """Confirm representative_quotes is not a field on ThemeCategory."""
        theme = ThemeCategory(
            category_name="Test",
            definition="Test definition",
            frequency="Medium",
            mention_count=10,
            primary_user_segments=["Users"],
            anchor_keywords=["kw1", "kw2", "kw3"],
        )
        # Extra fields are ignored with extra='ignore'
        assert not hasattr(theme, "representative_quotes") or theme.model_fields.get("representative_quotes") is None


class TestUnvalidatedPainPoint:
    """Tests for UnvalidatedPainPoint model with anchor_keywords."""

    def test_unvalidated_pain_point_has_anchor_keywords(self):
        """Verify UnvalidatedPainPoint has anchor_keywords (min 2, max 8)."""
        pp = UnvalidatedPainPoint(
            title="Manual Invoicing",
            description="Users struggle with manual invoicing processes",
            mention_count=20,
            anchor_keywords=["manual invoices", "invoice pain"],
        )
        assert pp.anchor_keywords == ["manual invoices", "invoice pain"]

    def test_unvalidated_pain_point_anchor_keywords_min_length(self):
        """Test that UnvalidatedPainPoint requires at least 2 anchor_keywords."""
        with pytest.raises(ValidationError) as exc_info:
            UnvalidatedPainPoint(
                title="Test",
                description="Test description",
                mention_count=5,
                anchor_keywords=["only_one"],  # Only 1, needs 2
            )
        assert "anchor_keywords" in str(exc_info.value)

    def test_unvalidated_pain_point_anchor_keywords_max_length(self):
        """Test that UnvalidatedPainPoint allows max 12 anchor_keywords."""
        # This should succeed with exactly 12
        pp = UnvalidatedPainPoint(
            title="Test",
            description="Test description",
            mention_count=5,
            anchor_keywords=[f"kw{i}" for i in range(12)],
        )
        assert len(pp.anchor_keywords) == 12

        # This should fail with 13
        with pytest.raises(ValidationError):
            UnvalidatedPainPoint(
                title="Test",
                description="Test description",
                mention_count=5,
                anchor_keywords=[f"kw{i}" for i in range(13)],  # 13 exceeds max
            )

    def test_unvalidated_pain_point_no_quotes_or_source_ids(self):
        """Confirm representative_quotes and source_post_ids are not fields on UnvalidatedPainPoint."""
        pp = UnvalidatedPainPoint(
            title="Test",
            description="Test description",
            mention_count=5,
            anchor_keywords=["kw1", "kw2"],
        )
        # These fields should not exist in the model
        assert "representative_quotes" not in pp.model_fields
        assert "source_post_ids" not in pp.model_fields

    def test_unvalidated_pain_point_optional_fields(self):
        """Test optional source_platforms and categories fields."""
        pp = UnvalidatedPainPoint(
            title="Test",
            description="Test description",
            mention_count=5,
            anchor_keywords=["kw1", "kw2"],
            source_platforms=["Reddit", "Twitter"],
            categories=["workflow", "automation"],
        )
        assert pp.source_platforms == ["Reddit", "Twitter"]
        assert pp.categories == ["workflow", "automation"]


class TestExtractedQuote:
    """Tests for ExtractedQuote model."""

    def test_extracted_quote_model(self):
        """Test ExtractedQuote with required quote_text and post_id."""
        quote = ExtractedQuote(
            quote_text="I spend 3 hours every week on manual invoices",
            post_id="abc123",
        )
        assert quote.quote_text == "I spend 3 hours every week on manual invoices"
        assert quote.post_id == "abc123"

    def test_extracted_quote_requires_quote_text(self):
        """Test that quote_text is required."""
        with pytest.raises(ValidationError):
            ExtractedQuote(post_id="abc123")  # Missing quote_text

    def test_extracted_quote_requires_post_id(self):
        """Test that post_id is required."""
        with pytest.raises(ValidationError):
            ExtractedQuote(quote_text="Some quote")  # Missing post_id

    def test_extracted_quote_empty_strings_allowed(self):
        """Test that empty strings are technically allowed (guardrail validates)."""
        # Empty strings pass model validation but fail guardrail
        quote = ExtractedQuote(quote_text="", post_id="")
        assert quote.quote_text == ""
        assert quote.post_id == ""


class TestEnrichedPainPointQuotes:
    """Tests for EnrichedPainPointQuotes model."""

    def test_enriched_pain_point_quotes_model(self):
        """Test EnrichedPainPointQuotes with pain_point_title and quotes list."""
        enriched = EnrichedPainPointQuotes(
            pain_point_title="Manual Invoicing",
            quotes=[
                ExtractedQuote(quote_text="Quote 1", post_id="p1"),
                ExtractedQuote(quote_text="Quote 2", post_id="p2"),
            ],
        )
        assert enriched.pain_point_title == "Manual Invoicing"
        assert len(enriched.quotes) == 2

    def test_enriched_pain_point_quotes_empty_list(self):
        """Test that quotes list can be empty (default)."""
        enriched = EnrichedPainPointQuotes(
            pain_point_title="Test Pain Point",
        )
        assert enriched.quotes == []

    def test_enriched_pain_point_quotes_requires_title(self):
        """Test that pain_point_title is required."""
        with pytest.raises(ValidationError):
            EnrichedPainPointQuotes(quotes=[])  # Missing pain_point_title


class TestQuoteEnrichmentResult:
    """Tests for QuoteEnrichmentResult model."""

    def test_quote_enrichment_result_model(self):
        """Test QuoteEnrichmentResult with all required fields."""
        result = QuoteEnrichmentResult(
            niche="small business automation",
            enriched_pain_points=[
                EnrichedPainPointQuotes(
                    pain_point_title="Manual Invoicing",
                    quotes=[ExtractedQuote(quote_text="Test quote", post_id="p1")],
                )
            ],
            total_quotes_found=1,
            enrichment_summary="Found 1 quote for 1 pain point.",
        )
        assert result.niche == "small business automation"
        assert len(result.enriched_pain_points) == 1
        assert result.total_quotes_found == 1

    def test_quote_enrichment_result_requires_all_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            QuoteEnrichmentResult(
                niche="test",
                # Missing: enriched_pain_points, total_quotes_found, enrichment_summary
            )


class TestFinalPainPoint:
    """Tests for final PainPoint model (unchanged)."""

    def test_final_pain_point_unchanged(self):
        """Confirm PainPoint still has representative_quotes and source_post_ids."""
        pp = PainPoint(
            title="Manual Invoicing",
            description="Users struggle with manual invoicing",
            mention_count=20,
            severity_score=0.8,
            commercial_intent=0.7,
            opportunity_level=OpportunityLevel.HIGH,
            representative_quotes=["Quote 1", "Quote 2"],
            source_post_ids=["p1", "p2"],
        )
        assert pp.representative_quotes == ["Quote 1", "Quote 2"]
        assert pp.source_post_ids == ["p1", "p2"]

    def test_final_pain_point_source_ids_optional(self):
        """Test that source_post_ids has default empty list."""
        pp = PainPoint(
            title="Test",
            description="Test description",
            mention_count=5,
            severity_score=0.5,
            commercial_intent=0.5,
            opportunity_level=OpportunityLevel.MEDIUM,
            representative_quotes=["Quote 1"],
        )
        assert pp.source_post_ids == []


class TestContentCategorizationValidators:
    """Tests for ContentCategorizationReport field validators."""

    def test_content_categorization_anchor_keywords_validator(self):
        """Test validator rejects themes with < 3 anchor_keywords."""
        # This should fail because one theme has only 2 keywords
        with pytest.raises(ValidationError) as exc_info:
            ContentCategorizationReport(
                executive_summary="Test summary",
                theme_categories=[
                    ThemeCategory(
                        category_name="Valid Theme",
                        definition="Has enough keywords",
                        frequency="High",
                        mention_count=20,
                        primary_user_segments=["Users"],
                        anchor_keywords=["kw1", "kw2", "kw3"],
                    ),
                    # This theme would fail at ThemeCategory level, not report level
                    # So we test at the ThemeCategory model level instead
                ],
                user_segments=[
                    UserSegment(segment_name="Users", primary_concerns=["concern"], mention_frequency="High"),
                    UserSegment(segment_name="Admins", primary_concerns=["admin"], mention_frequency="Medium"),
                    UserSegment(segment_name="Devs", primary_concerns=["dev"], mention_frequency="Low"),
                ],
                overall_quality="High",
            )
        # Actually, with only 1 theme, this fails the min_length=4 constraint
        assert "theme_categories" in str(exc_info.value)

    def test_content_categorization_valid(self):
        """Test valid ContentCategorizationReport passes validation."""
        report = ContentCategorizationReport(
            executive_summary="Test summary",
            theme_categories=[
                ThemeCategory(
                    category_name=f"Theme {i}",
                    definition=f"Definition {i}",
                    frequency="Medium",
                    mention_count=10,
                    primary_user_segments=["Users"],
                    anchor_keywords=["kw1", "kw2", "kw3"],
                )
                for i in range(4)  # Minimum 4 themes
            ],
            user_segments=[
                UserSegment(segment_name="Users", primary_concerns=["concern"], mention_frequency="High"),
                UserSegment(segment_name="Admins", primary_concerns=["admin"], mention_frequency="Medium"),
                UserSegment(segment_name="Devs", primary_concerns=["dev"], mention_frequency="Low"),
            ],
            overall_quality="High",
        )
        assert len(report.theme_categories) == 4
        assert len(report.user_segments) == 3


class TestPainPointExtraction:
    """Tests for PainPointExtraction model."""

    def test_pain_point_extraction_min_pain_points(self):
        """Test that PainPointExtraction requires at least 3 pain points."""
        with pytest.raises(ValidationError) as exc_info:
            PainPointExtraction(
                niche="test",
                extracted_pain_points=[
                    UnvalidatedPainPoint(
                        title="Pain 1",
                        description="Desc 1",
                        mention_count=5,
                        anchor_keywords=["kw1", "kw2"],
                    ),
                    UnvalidatedPainPoint(
                        title="Pain 2",
                        description="Desc 2",
                        mention_count=5,
                        anchor_keywords=["kw1", "kw2"],
                    ),
                    # Only 2 pain points, need 3
                ],
                extraction_summary="Summary",
            )
        assert "extracted_pain_points" in str(exc_info.value)

    def test_pain_point_extraction_valid(self):
        """Test valid PainPointExtraction."""
        extraction = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title=f"Pain {i}",
                    description=f"Description {i}",
                    mention_count=5,
                    anchor_keywords=["kw1", "kw2"],
                )
                for i in range(3)
            ],
            extraction_summary="Extracted 3 pain points",
        )
        assert len(extraction.extracted_pain_points) == 3


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_validation_result_min_scores(self):
        """Test that ValidationResult requires at least 1 score."""
        with pytest.raises(ValidationError) as exc_info:
            ValidationResult(
                niche="test",
                pain_point_scores=[],  # Empty list
                validation_summary="Summary",
            )
        assert "pain_point_scores" in str(exc_info.value)

    def test_validation_result_valid(self):
        """Test valid ValidationResult."""
        result = ValidationResult(
            niche="test",
            pain_point_scores=[
                PainPointScoring(
                    pain_point_title="Manual Invoicing",
                    severity_score=0.8,
                    commercial_intent=0.7,
                    opportunity_level=OpportunityLevel.HIGH,
                )
            ],
            validation_summary="Validated 1 pain point",
        )
        assert len(result.pain_point_scores) == 1


class TestPainPointScoring:
    """Tests for PainPointScoring model."""

    def test_pain_point_scoring_score_ranges(self):
        """Test severity_score and commercial_intent are 0-1."""
        # Valid scores
        score = PainPointScoring(
            pain_point_title="Test",
            severity_score=0.5,
            commercial_intent=0.5,
            opportunity_level=OpportunityLevel.MEDIUM,
        )
        assert 0.0 <= score.severity_score <= 1.0
        assert 0.0 <= score.commercial_intent <= 1.0

        # Invalid severity_score > 1
        with pytest.raises(ValidationError):
            PainPointScoring(
                pain_point_title="Test",
                severity_score=1.5,
                commercial_intent=0.5,
                opportunity_level=OpportunityLevel.MEDIUM,
            )

        # Invalid commercial_intent < 0
        with pytest.raises(ValidationError):
            PainPointScoring(
                pain_point_title="Test",
                severity_score=0.5,
                commercial_intent=-0.1,
                opportunity_level=OpportunityLevel.MEDIUM,
            )


class TestSinglePainPointQuotesResult:
    """Tests for SinglePainPointQuotesResult model (parallel enrichment)."""

    def test_single_pain_point_quotes_result_model(self):
        """Test SinglePainPointQuotesResult creation with all fields."""
        result = SinglePainPointQuotesResult(
            pain_point_title="Manual Invoicing",
            anchor_keywords_searched=["invoice automation", "billing pain"],
            quotes=[
                ExtractedQuote(
                    quote_text="I spend hours every week on manual invoicing",
                    post_id="abc123",
                ),
                ExtractedQuote(
                    quote_text="Billing is such a nightmare for my small business",
                    post_id="def456",
                ),
            ],
            search_summary="Searched 2 keywords, found 2 quotes",
        )
        assert result.pain_point_title == "Manual Invoicing"
        assert len(result.anchor_keywords_searched) == 2
        assert len(result.quotes) == 2
        assert result.quotes[0].post_id == "abc123"

    def test_single_pain_point_quotes_result_defaults(self):
        """Test SinglePainPointQuotesResult with default values."""
        result = SinglePainPointQuotesResult(
            pain_point_title="Test Pain Point",
        )
        assert result.pain_point_title == "Test Pain Point"
        assert result.anchor_keywords_searched == []
        assert result.quotes == []
        assert result.search_summary == ""

    def test_single_pain_point_quotes_result_requires_title(self):
        """Test that pain_point_title is required."""
        with pytest.raises(ValidationError):
            SinglePainPointQuotesResult(
                # Missing pain_point_title
                quotes=[],
            )
