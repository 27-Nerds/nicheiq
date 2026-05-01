"""
Pydantic models for pain point analysis (Stage 6).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .keyword_data import OpportunityLevel


class UnvalidatedPainPoint(BaseModel):
    """Pain point extracted by analyst without severity/WTP scores yet."""

    model_config = ConfigDict(extra='ignore')

    title: str = Field(..., description="Short title of the pain point")
    description: str = Field(..., description="Detailed description of the problem")
    short_summary: Optional[str] = Field(
        default=None,
        description=(
            "Punchy 1-2 sentence summary for card display. Focuses on the core user "
            "problem and its impact. Must be under 180 characters. "
            "Example: 'Manual invoicing wastes 3-5 hours weekly per user. "
            "Delays payments and introduces billing errors.'"
        ),
    )
    mention_count: int = Field(
        ...,
        description="Total UNIQUE discussions mentioning this problem"
    )
    anchor_keywords: list[str] = Field(
        ...,
        min_length=2,
        max_length=12,
        description="2-10 short anchor phrases (2-6 words each) capturing user language for this pain point. Task 4 uses the first 4 for vector search."
    )
    source_platforms: Optional[list[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[list[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )

class ThemeCategory(BaseModel):
    """Single theme category from content categorization."""

    model_config = ConfigDict(extra='ignore')

    category_name: str = Field(..., description="Theme category name")
    definition: str = Field(..., description="What this category represents")
    frequency: str = Field(..., description="High/Medium/Low based on mention count")
    mention_count: int = Field(
        ...,
        description="Number of distinct discussions mentioning this theme"
    )
    # Catalog rebuild (Phase 5.4): numeric severity score 0-100 for the public
    # catalog UI. Optional for backward compatibility — legacy reports produced
    # before this field existed have None and the catalog UI uses the
    # `frequency` string as a fallback (High=85, Medium=55, Low=25 mapping
    # in the frontend's scaleSeverity helper).
    severity_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Severity score 0-100 (NOT 0-1). Combines mention frequency with pain weight.",
    )
    primary_user_segments: list[str] = Field(
        ..., description="User types in this category"
    )
    anchor_keywords: list[str] = Field(
        ...,
        min_length=3,
        max_length=12,
        description="3-8 short anchor phrases (2-6 words each) that capture how users express this theme. Used by Task 4 for vector search."
    )

    @field_validator('anchor_keywords', mode='before')
    @classmethod
    def truncate_anchor_keywords(cls, v: object) -> object:
        if isinstance(v, list) and len(v) > 12:
            return v[:12]
        return v

class UserSegment(BaseModel):
    """User segment identified in categorization."""

    model_config = ConfigDict(extra='ignore')

    segment_name: str = Field(..., description="User segment name")
    primary_concerns: list[str] = Field(
        ..., description="Main pain points/topics"
    )
    mention_frequency: str = Field(..., description="High/Medium/Low")

class ContentCategorizationReport(BaseModel):
    """Complete categorization report from Task 1."""

    model_config = ConfigDict(extra='ignore')

    executive_summary: str = Field(..., description="2-3 sentence overview")
    theme_categories: list[ThemeCategory] = Field(
        ..., min_length=4, description="5-10 theme categories identified (minimum 4)"
    )
    user_segments: list[UserSegment] = Field(
        ..., min_length=3, description="User segment profiles (minimum 3)"
    )
    overall_quality: str = Field(
        ..., description="High/Medium/Low rating"
    )
    overall_quality_justification: Optional[str] = Field(
        default=None, description="Justification for the quality rating"
    )

    @field_validator('theme_categories')
    @classmethod
    def validate_themes_have_anchor_keywords(cls, v: list[ThemeCategory]) -> list[ThemeCategory]:
        """Ensure each theme has anchor keywords for vector search."""
        for theme in v:
            if not theme.anchor_keywords or len(theme.anchor_keywords) < 3:
                raise ValueError(f"Theme '{theme.category_name}' needs at least 3 anchor_keywords")
        return v

class PainPointExtraction(BaseModel):
    """Output from pain_point_analyst before validation."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    extracted_pain_points: list[UnvalidatedPainPoint] = Field(
        ..., min_length=3, description="Pain points extracted from discussions (minimum 3)"
    )
    extraction_summary: str = Field(
        ..., description="Summary of extraction process and key findings"
    )

class PainPointScoring(BaseModel):
    """Scoring data for a single pain point from validation task (Task 3 output).

    This intermediate model contains ONLY the new scoring fields added by the validator.
    Python will merge this with UnvalidatedPainPoint to create the final PainPoint.
    """

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(
        ..., description="Title reference key to match with UnvalidatedPainPoint"
    )
    severity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Severity score (0-1) based on emotional language"
    )
    willingness_to_pay: float = Field(
        ..., ge=0.0, le=1.0, description="Indicator of willingness to pay for solution (0-1)"
    )
    opportunity_level: OpportunityLevel = Field(
        ..., description="Overall opportunity level (high/medium/low)"
    )
    scoring_rationale: Optional[str] = Field(
        default=None, description="Brief explanation of why these scores were assigned"
    )

class ValidationResult(BaseModel):
    """Task 3 output: Validation scores for all pain points (ONLY new scoring data)."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    pain_point_scores: list[PainPointScoring] = Field(
        ..., min_length=1, description="Validation scores for each extracted pain point (at least 1)"
    )
    validation_summary: str = Field(
        ..., description="Summary of validation methodology and overall assessment"
    )


# ========================================
# TASK 4: QUOTE ENRICHMENT OUTPUT MODELS
# ========================================

class ExtractedQuote(BaseModel):
    """A single quote with its source attribution from vector search."""

    model_config = ConfigDict(extra='ignore')

    quote_text: str = Field(..., description="Verbatim quote text from search results")
    post_id: str = Field(..., description="Post ID from search result metadata")


class EnrichedPainPointQuotes(BaseModel):
    """Quotes found via vector search for one pain point."""

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(..., description="Exact title from Task 2 for matching")
    quotes: list[ExtractedQuote] = Field(
        default_factory=list,
        description="Quotes with post_id attribution from vector search metadata"
    )


class QuoteEnrichmentResult(BaseModel):
    """Task 4 output: quotes per pain point from vector search."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    enriched_pain_points: list[EnrichedPainPointQuotes] = Field(
        ..., description="Quotes for each pain point from Task 2"
    )
    total_quotes_found: int = Field(..., description="Total quotes across all pain points")
    enrichment_summary: str = Field(..., description="2-3 sentences on search results and coverage")


class SinglePainPointQuotesResult(BaseModel):
    """Result of quote search for a single pain point (parallel enrichment)."""

    model_config = ConfigDict(extra='ignore')

    pain_point_title: str = Field(..., description="Title of the pain point searched")
    anchor_keywords_searched: list[str] = Field(
        default_factory=list,
        description="Keywords used for search"
    )
    quotes: list[ExtractedQuote] = Field(
        default_factory=list,
        description="Quotes found (6-12 target)"
    )
    search_summary: str = Field(
        default="",
        description="Brief summary of search results"
    )


class PainPoint(BaseModel):
    """Represents a user pain point discovered from social discussions."""

    model_config = ConfigDict(extra='ignore')

    title: str = Field(..., description="Short title of the pain point")
    description: str = Field(..., description="Detailed description of the problem")
    short_summary: Optional[str] = Field(
        default=None,
        description=(
            "Punchy 1-2 sentence summary for card display. Focuses on the core user "
            "problem and its impact. Must be under 180 characters."
        ),
    )
    mention_count: int = Field(
        ...,
        description="Total UNIQUE discussions mentioning this problem - typically much larger than quote count"
    )
    severity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Severity score (0-1) based on emotional language"
    )
    willingness_to_pay: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Indicator of willingness to pay for solution (0-1)",
    )
    opportunity_level: OpportunityLevel = Field(
        ..., description="Overall opportunity level (high/medium/low)"
    )
    representative_quotes: list[str] = Field(
        ..., description="Real user quotes representing this pain point"
    )
    source_platforms: Optional[list[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[list[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )
    source_post_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Parallel array with representative_quotes: source_post_ids[i] is the "
            "post/thread ID where representative_quotes[i] was found. "
            "Empty string means source unknown. May contain duplicates."
        )
    )
    # Audience segment mapping (from Stage 6.5 audience mapping)
    affected_segments: Optional[list[str]] = Field(
        default=None,
        description=(
            "Audience segments from Stage 6.5 that experience this pain point "
            "(e.g., ['Solo Founders', 'Marketing Managers']). Populated when audience mapping available."
        )
    )

    # NEW: Solution approach mapping (from Stage 10 report generation)
    solution_approach: Optional[str] = Field(
        default=None,
        description="1-2 sentence explanation of how the selected solution addresses this pain point."
    )

class PainPointAnalysisResult(BaseModel):
    """Complete result of pain point analysis."""

    model_config = ConfigDict(extra='ignore')

    niche: str = Field(..., description="The niche being analyzed")
    pain_points: list[PainPoint] = Field(..., description="List of discovered pain points")
    total_mentions: int = Field(
        ..., description="Total number of pain point mentions across all discussions"
    )
    top_categories: list[str] = Field(
        ..., description="Top categories of pain points identified"
    )
    analysis_summary: str = Field(..., description="Executive summary of pain point analysis")
    content_categorization: Optional[ContentCategorizationReport] = Field(
        default=None,
        description="Detailed content categorization from Task 1 (themes, segments, quality)"
    )
