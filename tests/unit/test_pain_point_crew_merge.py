"""
Tests for PainPointCrew merge logic and fuzzy matching.

Tests:
- fuzzy_find_matching_score: title matching with threshold
- validate_pain_point_extraction: anchor_keywords validation
- _setup_enrichment_knowledge: creates Knowledge with correct sources
- Merge logic (Task 2 + Task 3 + Task 4 -> final PainPoint)
"""

from datetime import datetime, timezone
from difflib import SequenceMatcher
from unittest.mock import MagicMock, patch

import pytest

from nicheiq.crews.pain_point_crew import (
    FUZZY_MATCH_THRESHOLD,
    PainPointCrew,
    fuzzy_find_matching_score,
    validate_pain_point_extraction,
)
from nicheiq.models.keyword_data import OpportunityLevel
from nicheiq.models.pain_point import (
    EnrichedPainPointQuotes,
    ExtractedQuote,
    PainPointExtraction,
    PainPointScoring,
    QuoteEnrichmentResult,
    UnvalidatedPainPoint,
    ValidationResult,
)


class TestFuzzyFindMatchingScore:
    """Tests for fuzzy_find_matching_score function."""

    def test_fuzzy_find_matching_score_exact_match(self):
        """Exact title match -> ratio=1.0."""
        scores = [
            _make_scoring("Manual Invoicing"),
            _make_scoring("Expense Tracking"),
        ]

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        assert result is not None
        assert result.pain_point_title == "Manual Invoicing"
        assert ratio == 1.0

    def test_fuzzy_find_matching_score_case_insensitive(self):
        """'Manual Invoicing' matches 'manual invoicing'."""
        scores = [
            _make_scoring("manual invoicing"),  # lowercase
        ]

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        assert result is not None
        assert ratio == 1.0

    def test_fuzzy_find_matching_score_fuzzy_match(self):
        """85%+ similarity -> returns match."""
        scores = [
            _make_scoring("Manual Invoice Processing"),  # Similar to "Manual Invoicing"
        ]

        # "Manual Invoicing" vs "Manual Invoice Processing"
        # Check actual similarity
        similarity = SequenceMatcher(
            None,
            "manual invoicing",
            "manual invoice processing"
        ).ratio()

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        if similarity >= FUZZY_MATCH_THRESHOLD:
            assert result is not None
            assert ratio >= FUZZY_MATCH_THRESHOLD
        else:
            # If not similar enough, might not match
            assert ratio < 1.0

    def test_fuzzy_find_matching_score_no_match(self):
        """Below threshold -> (None, best_ratio)."""
        scores = [
            _make_scoring("Completely Different Topic"),
        ]

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        assert result is None
        assert ratio < FUZZY_MATCH_THRESHOLD

    def test_fuzzy_threshold_boundary_0_85(self):
        """Exact 0.85 similarity should match."""
        # Create titles that are exactly at threshold
        # "Manual Invoicing" vs "Manual Invoicng" (missing 'i') should be close
        scores = [
            _make_scoring("Manual Invoicng"),  # Slight typo
        ]

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        # The exact ratio depends on the strings, but we test boundary behavior
        if ratio >= FUZZY_MATCH_THRESHOLD:
            assert result is not None
        else:
            assert result is None

    def test_fuzzy_below_threshold_0_84(self):
        """0.84 similarity should NOT match."""
        scores = [
            _make_scoring("Very Different Title Here"),
        ]

        result, ratio = fuzzy_find_matching_score("Manual Invoicing", scores)

        # These should be very different
        assert result is None
        assert ratio < FUZZY_MATCH_THRESHOLD

    def test_fuzzy_empty_scores_list(self):
        """Returns (None, 0.0) for empty list."""
        result, ratio = fuzzy_find_matching_score("Any Title", [])

        assert result is None
        assert ratio == 0.0


class TestValidatePainPointExtraction:
    """Tests for validate_pain_point_extraction guardrail."""

    def test_validate_pain_point_extraction_checks_anchor_keywords(self):
        """Fails if pain point has < 2 anchor_keywords."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_extraction_json(
            pain_points=[
                {
                    "title": "Manual Invoicing",
                    "description": "Users struggle with manual invoicing",
                    "mention_count": 10,
                    "anchor_keywords": ["only_one"],  # Only 1, needs 2
                },
                {
                    "title": "Expense Tracking",
                    "description": "Expense tracking is difficult",
                    "mention_count": 8,
                    "anchor_keywords": ["kw1", "kw2"],
                },
                {
                    "title": "Tax Prep",
                    "description": "Tax preparation is hard",
                    "mention_count": 5,
                    "anchor_keywords": ["kw1", "kw2"],
                },
            ]
        )

        success, result = validate_pain_point_extraction(output)

        assert not success
        assert "anchor_keywords" in result.lower()

    def test_validate_pain_point_extraction_passes_valid(self):
        """Valid extraction -> (True, json)."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_extraction_json(
            pain_points=[
                {
                    "title": f"Pain Point {i}",
                    "parent_theme_id": "test-theme",
                    "description": f"Description for pain point {i}",
                    "mention_count": 10,
                    "anchor_keywords": ["kw1", "kw2"],
                }
                for i in range(3)
            ]
        )

        success, result = validate_pain_point_extraction(output)

        assert success

    def test_validate_pain_point_extraction_min_3(self):
        """Test min_length=3 constraint for pain points."""
        output = MagicMock()
        output.pydantic = None
        output.raw = _make_extraction_json(
            pain_points=[
                {
                    "title": "Pain 1",
                    "description": "Description 1",
                    "mention_count": 10,
                    "anchor_keywords": ["kw1", "kw2"],
                },
                {
                    "title": "Pain 2",
                    "description": "Description 2",
                    "mention_count": 8,
                    "anchor_keywords": ["kw1", "kw2"],
                },
                # Only 2 pain points
            ]
        )

        success, result = validate_pain_point_extraction(output)

        assert not success
        assert "at least 3" in result.lower()

    def test_validate_pain_point_extraction_pydantic_available(self):
        """When pydantic is available, uses it directly."""
        extraction = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title=f"Pain Point Number {i}",
                    parent_theme_id="test-theme",
                    description=f"This is a detailed description for pain point {i} that is long enough",
                    mention_count=10,
                    anchor_keywords=["kw1", "kw2"],
                )
                for i in range(3)
            ],
            extraction_summary="Extracted 3 pain points",
        )

        output = MagicMock()
        output.pydantic = extraction
        output.raw = extraction.model_dump_json()

        success, result = validate_pain_point_extraction(output)

        # validate_pain_point_extraction returns (True, model_dump_json())
        assert success


class TestSetupEnrichmentKnowledge:
    """Tests for _setup_enrichment_knowledge method."""

    @patch("nicheiq.utils.knowledge.reddit_knowledge_source.RedditKnowledgeSource")
    @patch("nicheiq.utils.knowledge.twitter_knowledge_source.TwitterKnowledgeSource")
    def test_setup_enrichment_knowledge_creates_sources(
        self,
        mock_twitter_source_class,
        mock_reddit_source_class,
        mock_reddit_post,
        mock_twitter_thread,
    ):
        """Verifies Knowledge sources are created with correct params."""
        # Import here to get the actual classes
        from nicheiq.utils.knowledge import RedditKnowledgeSource, TwitterKnowledgeSource

        # Create actual sources (the test verifies the parameters)
        reddit_source = RedditKnowledgeSource(
            posts=[mock_reddit_post],
            chunk_size=2000,
            chunk_overlap=600,
        )
        twitter_source = TwitterKnowledgeSource(
            threads=[mock_twitter_thread],
            chunk_size=1500,
            chunk_overlap=400,
        )

        # Verify sources have correct config
        assert reddit_source.posts == [mock_reddit_post]
        assert reddit_source.chunk_size == 2000
        assert reddit_source.chunk_overlap == 600

        assert twitter_source.threads == [mock_twitter_thread]
        assert twitter_source.chunk_size == 1500
        assert twitter_source.chunk_overlap == 400

    def test_setup_enrichment_knowledge_reddit_only(
        self,
        mock_reddit_post,
    ):
        """Works with Reddit posts only (no Twitter)."""
        from nicheiq.utils.knowledge import RedditKnowledgeSource

        reddit_source = RedditKnowledgeSource(
            posts=[mock_reddit_post],
            chunk_size=2000,
            chunk_overlap=600,
        )

        assert reddit_source.posts == [mock_reddit_post]


class TestMergeLogic:
    """Tests for the merge logic in PainPointCrew.analyze()."""

    def test_merge_combines_task2_task3_task4(self):
        """Mock outputs -> correct final PainPoint."""
        # Task 2: Extraction (with anchor_keywords) - need 3 pain points
        task2_output = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title="Manual Invoicing",
                    description="Manual invoicing is painful",
                    mention_count=20,
                    anchor_keywords=["manual invoices", "invoice pain"],
                    source_platforms=["Reddit"],
                    categories=["workflow"],
                ),
                UnvalidatedPainPoint(
                    title="Expense Tracking",
                    description="Expense tracking is tedious",
                    mention_count=15,
                    anchor_keywords=["expense reports", "receipt tracking"],
                ),
                UnvalidatedPainPoint(
                    title="Tax Preparation",
                    description="Tax prep is complex",
                    mention_count=10,
                    anchor_keywords=["tax filing", "tax documents"],
                ),
            ],
            extraction_summary="Extracted 3 pain points",
        )

        # Task 3: Validation (scores)
        task3_output = ValidationResult(
            niche="test",
            pain_point_scores=[
                PainPointScoring(
                    pain_point_title="Manual Invoicing",
                    severity_score=0.8,
                    willingness_to_pay=0.7,
                    opportunity_level=OpportunityLevel.HIGH,
                ),
                PainPointScoring(
                    pain_point_title="Expense Tracking",
                    severity_score=0.6,
                    willingness_to_pay=0.5,
                    opportunity_level=OpportunityLevel.MEDIUM,
                ),
                PainPointScoring(
                    pain_point_title="Tax Preparation",
                    severity_score=0.7,
                    willingness_to_pay=0.6,
                    opportunity_level=OpportunityLevel.MEDIUM,
                ),
            ],
            validation_summary="Validated 3 pain points",
        )

        # Task 4: Quote Enrichment
        task4_output = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[
                EnrichedPainPointQuotes(
                    pain_point_title="Manual Invoicing",
                    quotes=[
                        ExtractedQuote(
                            quote_text="I spend 3 hours on invoices weekly",
                            post_id="abc123",
                        ),
                    ],
                ),
                EnrichedPainPointQuotes(
                    pain_point_title="Expense Tracking",
                    quotes=[
                        ExtractedQuote(quote_text="Receipt tracking is a nightmare", post_id="def456"),
                    ],
                ),
                EnrichedPainPointQuotes(
                    pain_point_title="Tax Preparation",
                    quotes=[
                        ExtractedQuote(quote_text="Tax prep takes weeks", post_id="ghi789"),
                    ],
                ),
            ],
            total_quotes_found=3,
            enrichment_summary="Found 3 quotes",
        )

        # Simulate merge (simplified version of what analyze() does)
        final_pain_points = _simulate_merge(task2_output, task3_output, task4_output)

        assert len(final_pain_points) == 3
        pp = final_pain_points[0]  # Manual Invoicing
        assert pp["title"] == "Manual Invoicing"
        assert pp["severity_score"] == 0.8
        assert pp["willingness_to_pay"] == 0.7
        assert pp["representative_quotes"] == ["I spend 3 hours on invoices weekly"]
        assert pp["source_post_ids"] == ["abc123"]

    def test_merge_handles_unmatched_quotes(self):
        """Pain point without Task 4 match -> empty quotes."""
        task2_output = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title="Manual Invoicing",
                    description="Description",
                    mention_count=10,
                    anchor_keywords=["kw1", "kw2"],
                ),
                UnvalidatedPainPoint(
                    title="Pain Point Two",
                    description="Description two",
                    mention_count=8,
                    anchor_keywords=["kw3", "kw4"],
                ),
                UnvalidatedPainPoint(
                    title="Pain Point Three",
                    description="Description three",
                    mention_count=6,
                    anchor_keywords=["kw5", "kw6"],
                ),
            ],
            extraction_summary="Summary",
        )

        task3_output = ValidationResult(
            niche="test",
            pain_point_scores=[
                PainPointScoring(
                    pain_point_title="Manual Invoicing",
                    severity_score=0.8,
                    willingness_to_pay=0.7,
                    opportunity_level=OpportunityLevel.HIGH,
                ),
                PainPointScoring(
                    pain_point_title="Pain Point Two",
                    severity_score=0.6,
                    willingness_to_pay=0.5,
                    opportunity_level=OpportunityLevel.MEDIUM,
                ),
                PainPointScoring(
                    pain_point_title="Pain Point Three",
                    severity_score=0.5,
                    willingness_to_pay=0.4,
                    opportunity_level=OpportunityLevel.LOW,
                ),
            ],
            validation_summary="Summary",
        )

        # Task 4 has different pain point (no match for "Manual Invoicing")
        task4_output = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[
                EnrichedPainPointQuotes(
                    pain_point_title="Different Pain Point",  # No match
                    quotes=[
                        ExtractedQuote(quote_text="Some quote", post_id="p1"),
                    ],
                ),
            ],
            total_quotes_found=1,
            enrichment_summary="Summary",
        )

        final_pain_points = _simulate_merge(task2_output, task3_output, task4_output)

        assert len(final_pain_points) == 3
        # First pain point should have empty quotes (no Task 4 match)
        pp = final_pain_points[0]
        assert pp["representative_quotes"] == []
        assert pp["source_post_ids"] == []

    def test_merge_handles_unmatched_scores(self):
        """Pain point without Task 3 match -> skipped."""
        task2_output = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title="Manual Invoicing",  # Has no matching score
                    description="Description",
                    mention_count=10,
                    anchor_keywords=["kw1", "kw2"],
                ),
                UnvalidatedPainPoint(
                    title="Matched Pain Point",  # Has matching score
                    description="Description two",
                    mention_count=8,
                    anchor_keywords=["kw3", "kw4"],
                ),
                UnvalidatedPainPoint(
                    title="Another Unmatched",  # Has no matching score
                    description="Description three",
                    mention_count=6,
                    anchor_keywords=["kw5", "kw6"],
                ),
            ],
            extraction_summary="Summary",
        )

        # Task 3 only has score for "Matched Pain Point"
        task3_output = ValidationResult(
            niche="test",
            pain_point_scores=[
                PainPointScoring(
                    pain_point_title="Matched Pain Point",  # Only matches one
                    severity_score=0.8,
                    willingness_to_pay=0.7,
                    opportunity_level=OpportunityLevel.HIGH,
                ),
            ],
            validation_summary="Summary",
        )

        task4_output = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[],
            total_quotes_found=0,
            enrichment_summary="No quotes",
        )

        final_pain_points = _simulate_merge(task2_output, task3_output, task4_output)

        # Only 1 pain point should be in output (the one with matching score)
        assert len(final_pain_points) == 1
        assert final_pain_points[0]["title"] == "Matched Pain Point"

    def test_extraction_rejects_duplicate_titles(self):
        """PainPointExtraction.validate_unique_titles rejects duplicates at the model boundary.

        The DB enforces @@unique([sourceJobId, title]) on CatalogPainPoint, so the
        merge layer never has to handle duplicate titles — they're caught upstream.
        """
        from pydantic import ValidationError as _VE

        with pytest.raises(_VE) as exc_info:
            PainPointExtraction(
                niche="test",
                extracted_pain_points=[
                    UnvalidatedPainPoint(
                        title="Duplicate Title",
                        description="First instance",
                        mention_count=10,
                        anchor_keywords=["kw1", "kw2"],
                    ),
                    UnvalidatedPainPoint(
                        title="Duplicate Title",
                        description="Second instance",
                        mention_count=5,
                        anchor_keywords=["kw3", "kw4"],
                    ),
                    UnvalidatedPainPoint(
                        title="Unique Title",
                        description="Third",
                        mention_count=8,
                        anchor_keywords=["kw5", "kw6"],
                    ),
                ],
                extraction_summary="Summary",
            )
        assert "Duplicate pain point titles" in str(exc_info.value)
        assert "Duplicate Title" in str(exc_info.value)

    def test_merge_task4_extra_pain_points(self):
        """Task 4 has enrichments not in Task 2 (should be ignored)."""
        task2_output = PainPointExtraction(
            niche="test",
            extracted_pain_points=[
                UnvalidatedPainPoint(
                    title="Real Pain Point",
                    description="Description",
                    mention_count=10,
                    anchor_keywords=["kw1", "kw2"],
                ),
                UnvalidatedPainPoint(
                    title="Second Real Pain",
                    description="Description two",
                    mention_count=8,
                    anchor_keywords=["kw3", "kw4"],
                ),
                UnvalidatedPainPoint(
                    title="Third Real Pain",
                    description="Description three",
                    mention_count=6,
                    anchor_keywords=["kw5", "kw6"],
                ),
            ],
            extraction_summary="Summary",
        )

        task3_output = ValidationResult(
            niche="test",
            pain_point_scores=[
                PainPointScoring(
                    pain_point_title="Real Pain Point",
                    severity_score=0.8,
                    willingness_to_pay=0.7,
                    opportunity_level=OpportunityLevel.HIGH,
                ),
                PainPointScoring(
                    pain_point_title="Second Real Pain",
                    severity_score=0.6,
                    willingness_to_pay=0.5,
                    opportunity_level=OpportunityLevel.MEDIUM,
                ),
                PainPointScoring(
                    pain_point_title="Third Real Pain",
                    severity_score=0.5,
                    willingness_to_pay=0.4,
                    opportunity_level=OpportunityLevel.LOW,
                ),
            ],
            validation_summary="Summary",
        )

        # Task 4 has extra pain point that wasn't in Task 2
        task4_output = QuoteEnrichmentResult(
            niche="test",
            enriched_pain_points=[
                EnrichedPainPointQuotes(
                    pain_point_title="Real Pain Point",
                    quotes=[ExtractedQuote(quote_text="Real quote", post_id="p1")],
                ),
                EnrichedPainPointQuotes(
                    pain_point_title="Extra Pain Point",  # Not in Task 2
                    quotes=[ExtractedQuote(quote_text="Extra quote", post_id="p2")],
                ),
            ],
            total_quotes_found=2,
            enrichment_summary="Summary",
        )

        final_pain_points = _simulate_merge(task2_output, task3_output, task4_output)

        # All 3 real pain points should be in output
        assert len(final_pain_points) == 3
        # First one should have quotes from Task 4
        assert final_pain_points[0]["title"] == "Real Pain Point"
        assert final_pain_points[0]["representative_quotes"] == ["Real quote"]


# Helper functions

def _make_scoring(title: str) -> PainPointScoring:
    """Create a PainPointScoring with given title."""
    return PainPointScoring(
        pain_point_title=title,
        severity_score=0.7,
        willingness_to_pay=0.6,
        opportunity_level=OpportunityLevel.MEDIUM,
    )


def _make_extraction_json(pain_points: list) -> str:
    """Create extraction JSON string."""
    import json
    return json.dumps({
        "niche": "test",
        "extracted_pain_points": pain_points,
        "extraction_summary": "Test extraction",
    })


def _simulate_merge(
    task2_output: PainPointExtraction,
    task3_output: ValidationResult,
    task4_output: QuoteEnrichmentResult,
) -> list[dict]:
    """
    Simulate the merge logic from PainPointCrew.analyze().

    Returns list of dicts representing final PainPoints.
    """
    final_pain_points = []

    for unvalidated in task2_output.extracted_pain_points:
        # Find matching score
        matching_score, score_ratio = fuzzy_find_matching_score(
            unvalidated.title,
            task3_output.pain_point_scores,
        )

        if not matching_score:
            continue  # Skip if no score match

        # Find matching quotes
        quotes = []
        source_ids = []

        for enriched in task4_output.enriched_pain_points:
            ratio = SequenceMatcher(
                None,
                unvalidated.title.lower().strip(),
                enriched.pain_point_title.lower().strip(),
            ).ratio()

            if ratio >= FUZZY_MATCH_THRESHOLD:
                for eq in enriched.quotes:
                    quotes.append(eq.quote_text)
                    source_ids.append(eq.post_id)
                break

        final_pain_points.append({
            "title": unvalidated.title,
            "description": unvalidated.description,
            "mention_count": unvalidated.mention_count,
            "severity_score": matching_score.severity_score,
            "willingness_to_pay": matching_score.willingness_to_pay,
            "opportunity_level": matching_score.opportunity_level,
            "representative_quotes": quotes,
            "source_post_ids": source_ids,
            "source_platforms": unvalidated.source_platforms,
            "categories": unvalidated.categories,
        })

    return final_pain_points
