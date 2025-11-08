"""
Pydantic models for pain point analysis (Stage 6).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .keyword_data import OpportunityLevel


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
