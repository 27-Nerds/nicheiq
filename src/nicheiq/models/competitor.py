"""
Pydantic models for competitive analysis (Stage 8).
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CompetitorType(str, Enum):
    """Type of competitor."""

    DIRECT = "direct"
    PARTIAL = "partial"
    INDIRECT = "indirect"

class MarketSaturation(str, Enum):
    """Level of market saturation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class Competitor(BaseModel):
    """Represents a competitive product or service."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description="Name of the competitor")
    url: Optional[str] = Field(default=None, description="Website URL")
    competitor_type: CompetitorType = Field(..., description="Type of competitor")
    description: str = Field(..., description="What this competitor offers")
    key_features: list[str] = Field(..., description="Main features they provide")
    pricing_model: Optional[str] = Field(
        default=None, description="Pricing model if available"
    )
    strengths: Optional[list[str]] = Field(default=None, description="Competitor strengths")
    weaknesses: Optional[list[str]] = Field(default=None, description="Competitor weaknesses")

class CompetitiveLandscape(BaseModel):
    """Complete competitive analysis for a solution idea."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    competitors: Optional[list[Competitor]] = Field(
        default=None, description="All competitors (direct, indirect, and partial solutions)"
    )
    market_gaps: list[str] = Field(
        ..., description="Specific unmet needs or underserved areas in the market"
    )
    differentiation_opportunities: list[str] = Field(
        ..., description="Specific ways this solution can differentiate from competitors"
    )
    competitive_intensity: str = Field(
        ..., description="Assessment of competitive intensity (Low/Medium/High) with justification"
    )
    recommended_positioning: str = Field(
        ..., description="Recommended market positioning and differentiation strategy"
    )
    pricing_insights: str = Field(
        ..., description="Market pricing analysis and recommended pricing approach"
    )

class CompetitiveAnalysisResult(BaseModel):
    """Complete result of competitive analysis for all solution ideas."""

    model_config = ConfigDict(extra='forbid')

    solution_landscapes: list[CompetitiveLandscape] = Field(
        ..., description="Competitive landscape for each solution idea"
    )
    top_opportunities: list[str] = Field(
        ..., description="3-5 highest-potential differentiation opportunities across all solutions"
    )
    strategic_recommendations: str = Field(
        ..., description="Executive summary with strategic insights and market positioning recommendations"
    )
