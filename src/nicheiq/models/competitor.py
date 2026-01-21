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

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    competitors: list[Competitor] = Field(
        default_factory=list, min_length=2, description="All competitors (minimum 2 required)"
    )
    market_gaps: list[str] = Field(
        ..., min_length=2, description="Specific unmet needs or underserved areas (minimum 2)"
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

    model_config = ConfigDict(extra='ignore')

    solution_landscapes: list[CompetitiveLandscape] = Field(
        ..., min_length=1, description="Competitive landscape for each solution idea (at least 1)"
    )
    top_opportunities: list[str] = Field(
        ..., description="3-5 highest-potential differentiation opportunities across all solutions"
    )
    strategic_recommendations: str = Field(
        ..., min_length=50, description="Executive summary with strategic insights (minimum 50 chars)"
    )
