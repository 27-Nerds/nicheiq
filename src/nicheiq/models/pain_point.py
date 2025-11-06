"""
Pydantic models for pain point analysis (Stage 6).
"""

from typing import List

from pydantic import BaseModel, Field

from .keyword_data import OpportunityLevel


class PainPoint(BaseModel):
    """Represents a user pain point discovered from social discussions."""

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
    source_platforms: List[str] = Field(
        default_factory=list, description="Platforms where this pain was found (Reddit, Twitter)"
    )
    categories: List[str] = Field(
        default_factory=list, description="Categories this pain point belongs to"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Difficulty finding specialized freelancers",
                "description": "Users struggle to find freelancers with niche technical skills",
                "mention_count": 15,
                "severity_score": 0.8,
                "willingness_to_pay": 0.9,
                "opportunity_level": "high",
                "representative_quotes": [
                    "I've been searching for weeks for a Rust developer",
                    "Why is it so hard to find good designers for SaaS landing pages?"
                ],
                "source_platforms": ["Reddit", "Twitter"],
                "categories": ["hiring", "freelancing"],
            }
        }


class PainPointAnalysisResult(BaseModel):
    """Complete result of pain point analysis."""

    niche: str = Field(..., description="The niche being analyzed")
    pain_points: List[PainPoint] = Field(..., description="List of discovered pain points")
    total_mentions: int = Field(
        ..., description="Total number of pain point mentions across all discussions"
    )
    top_categories: List[str] = Field(
        ..., description="Top categories of pain points identified"
    )
    analysis_summary: str = Field(..., description="Executive summary of pain point analysis")

    class Config:
        json_schema_extra = {
            "example": {
                "niche": "SaaS development tools",
                "pain_points": [],
                "total_mentions": 127,
                "top_categories": ["collaboration", "deployment", "monitoring"],
                "analysis_summary": "Analysis of 45 discussions revealed 5 major pain points with 127 total mentions...",
            }
        }
