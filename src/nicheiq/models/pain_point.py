"""
Pydantic models for pain point analysis (Stage 6).
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .keyword_data import OpportunityLevel


class EngagementMetric(BaseModel):
    """Engagement metric for a single post."""

    model_config = ConfigDict(extra='forbid')

    post_id: str = Field(..., description="Post ID")
    score: int = Field(..., description="Engagement score (upvotes, likes, etc.)")


class UnvalidatedPainPoint(BaseModel):
    """Pain point extracted by analyst without severity/WTP scores yet."""

    model_config = ConfigDict(extra='forbid')

    title: str = Field(..., description="Short title of the pain point")
    description: str = Field(..., description="Detailed description of the problem")
    mention_count: int = Field(..., description="Number of times this problem was mentioned")
    representative_quotes: List[str] = Field(
        ..., description="Real user quotes representing this pain point"
    )
    source_platforms: Optional[List[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[List[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )
    source_post_ids: List[str] = Field(
        default_factory=list,
        description="List of post IDs (Reddit/Twitter) where this pain point was found (for traceability)"
    )


class ThemeCategory(BaseModel):
    """Single theme category from content categorization."""

    model_config = ConfigDict(extra='forbid')

    category_name: str = Field(..., description="Theme category name")
    definition: str = Field(..., description="What this category represents")
    frequency: str = Field(..., description="High/Medium/Low based on mention count")
    mention_count: int = Field(..., description="Number of distinct discussions")
    primary_user_segments: List[str] = Field(
        ..., description="User types in this category"
    )
    representative_quotes: List[str] = Field(
        ..., description="3+ quotes from discussions"
    )


class UserSegment(BaseModel):
    """User segment identified in categorization."""

    model_config = ConfigDict(extra='forbid')

    segment_name: str = Field(..., description="User segment name")
    primary_concerns: List[str] = Field(
        ..., description="Main pain points/topics"
    )
    mention_frequency: str = Field(..., description="High/Medium/Low")


class ContentCategorizationReport(BaseModel):
    """Complete categorization report from Task 1."""

    model_config = ConfigDict(extra='forbid')

    executive_summary: str = Field(..., description="2-3 sentence overview")
    theme_categories: List[ThemeCategory] = Field(
        ..., description="5-10 theme categories identified"
    )
    user_segments: List[UserSegment] = Field(
        ..., description="User segment profiles"
    )
    discussion_quality_assessment: str = Field(
        ..., description="Quality assessment narrative"
    )
    overall_quality: str = Field(
        ..., description="High/Medium/Low with justification"
    )


class PainPointExtraction(BaseModel):
    """Output from pain_point_analyst before validation."""

    model_config = ConfigDict(extra='forbid')

    niche: str = Field(..., description="The niche being analyzed")
    extracted_pain_points: List[UnvalidatedPainPoint] = Field(
        ..., description="Pain points extracted from discussions (not yet scored)"
    )
    extraction_summary: str = Field(
        ..., description="Summary of extraction process and key findings"
    )


class PainPoint(BaseModel):
    """Represents a user pain point discovered from social discussions."""

    model_config = ConfigDict(extra='forbid')

    title: str = Field(..., description="Short title of the pain point")
    description: str = Field(..., description="Detailed description of the problem")
    mention_count: int = Field(..., description="Number of times this problem was mentioned")
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
    representative_quotes: List[str] = Field(
        ..., description="Real user quotes representing this pain point"
    )
    source_platforms: Optional[List[str]] = Field(
        default=None, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: Optional[List[str]] = Field(
        default=None, description="Categories this pain point belongs to"
    )
    source_post_ids: List[str] = Field(
        default_factory=list,
        description="List of post IDs (Reddit/Twitter) where this pain point was found (for traceability)"
    )
    source_engagement_metrics: List[EngagementMetric] = Field(
        default_factory=list,
        description="Engagement metrics for source posts (for traceability)"
    )


class PainPointAnalysisResult(BaseModel):
    """Complete result of pain point analysis."""

    model_config = ConfigDict(extra='forbid')

    niche: str = Field(..., description="The niche being analyzed")
    pain_points: List[PainPoint] = Field(..., description="List of discovered pain points")
    total_mentions: int = Field(
        ..., description="Total number of pain point mentions across all discussions"
    )
    top_categories: List[str] = Field(
        ..., description="Top categories of pain points identified"
    )
    analysis_summary: str = Field(..., description="Executive summary of pain point analysis")
    content_categorization: Optional[ContentCategorizationReport] = Field(
        default=None,
        description="Detailed content categorization from Task 1 (themes, segments, quality)"
    )
