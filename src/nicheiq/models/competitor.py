"""
Pydantic models for competitive analysis (Stage 8).
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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

    name: str = Field(..., description="Name of the competitor")
    url: Optional[str] = Field(default=None, description="Website URL")
    competitor_type: CompetitorType = Field(..., description="Type of competitor")
    description: str = Field(..., description="What this competitor offers")
    key_features: List[str] = Field(..., description="Main features they provide")
    pricing_model: Optional[str] = Field(
        default=None, description="Pricing model if available"
    )
    strengths: List[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Competitor weaknesses")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Upwork",
                "url": "https://upwork.com",
                "competitor_type": "partial",
                "description": "General freelancer marketplace with all skill categories",
                "key_features": [
                    "Large freelancer pool",
                    "Escrow payment",
                    "Time tracking",
                ],
                "pricing_model": "20% commission on first $500",
                "strengths": ["Established brand", "Large user base"],
                "weaknesses": ["Not specialized", "High competition for freelancers"],
            }
        }


class CompetitiveLandscape(BaseModel):
    """Complete competitive analysis for a solution idea."""

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    competitors: List[Competitor] = Field(
        default_factory=list, description="All competitors (direct, indirect, and partial solutions)"
    )
    market_gaps: List[str] = Field(
        ..., description="Specific unmet needs or underserved areas in the market"
    )
    differentiation_opportunities: List[str] = Field(
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

    class Config:
        json_schema_extra = {
            "example": {
                "solution_name": "NicheHire",
                "competitors": [],
                "market_gaps": ["No specialized verification", "Poor niche matching algorithms"],
                "differentiation_opportunities": [
                    "Focus on quality verification over quantity",
                    "Specialize in deep niche matching"
                ],
                "competitive_intensity": "Medium - Several generic platforms exist but no niche-focused competitors",
                "recommended_positioning": "Position as the premium, specialized alternative to generic freelance platforms",
                "pricing_insights": "Market supports 15-20% commission vs. competitors' 10-15%, given specialized value",
            }
        }


class CompetitiveAnalysisResult(BaseModel):
    """Complete result of competitive analysis for all solution ideas."""

    solution_landscapes: List[CompetitiveLandscape] = Field(
        ..., description="Competitive landscape for each solution idea"
    )
    top_opportunities: List[str] = Field(
        ..., description="3-5 highest-potential differentiation opportunities across all solutions"
    )
    strategic_recommendations: str = Field(
        ..., description="Executive summary with strategic insights and market positioning recommendations"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "solution_landscapes": [],
                "top_opportunities": [
                    "Underserved niche market for X",
                    "Pricing gap in premium segment",
                    "Integration opportunity with Y"
                ],
                "strategic_recommendations": "Market analysis reveals strong opportunities in specialized segments...",
            }
        }
