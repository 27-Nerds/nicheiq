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
    key_features: list[str] = Field(
        ...,
        description="All significant features from the competitor's product/features pages - be comprehensive for comparison (typically 4-8 features)"
    )
    pricing_model: Optional[str] = Field(
        default=None, description="Pricing model if available"
    )
    strengths: Optional[list[str]] = Field(default=None, description="Competitor strengths")
    weaknesses: Optional[list[str]] = Field(default=None, description="Competitor weaknesses")
    # Catalog rebuild (Phase 5.4): market position relative to the niche.
    # Distinct from `competitor_type` (which describes feature overlap with our
    # solution) — `position` describes the competitor's standing in the market.
    # Optional for back-compat; legacy reports have None.
    #   leader     = dominant brand recognition or market share
    #   challenger = mid-market with focused traction, scaling
    #   niche      = vertical-specific or limited footprint
    position: Optional[str] = Field(
        default=None,
        description="Market position: leader | challenger | niche",
    )

class CompetitiveLandscape(BaseModel):
    """Complete competitive analysis for a solution idea."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    competitors: list[Competitor] = Field(
        default_factory=list,
        description="Competitors found (may be empty for emerging niches)"
    )
    market_gaps: list[str] = Field(
        ..., min_length=2, description="ALL unmet needs, underserved areas, user complaints, and missing features - comprehensive list"
    )
    differentiation_opportunities: list[str] = Field(
        ..., description="ALL ways this solution can differentiate from competitors - comprehensive list"
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
    # Stamped by the flow when the deterministic on-niche check fails twice
    # (utils/validation/competitor_relevance.py). Downgrade-only: the landscape is kept
    # verbatim, but every count/saturation/gap claim derived from it is unverified.
    # None on every healthy landscape and on all legacy reports.
    off_niche_caveat: Optional[str] = Field(
        default=None,
        description="Set when the returned competitors share no vocabulary with the niche",
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


def find_landscape_for_solution(
    competitive_analysis: CompetitiveAnalysisResult | None,
    solution_name: str | None,
) -> CompetitiveLandscape | None:
    """Find the competitive landscape for a specific solution by name.

    Case-insensitive, stripped matching. Falls back to first landscape
    if no exact match found. Returns None only if no landscapes exist.

    Args:
        competitive_analysis: Full competitive analysis result (may be None).
        solution_name: Name of the solution to look up (may be None).

    Returns:
        Matching CompetitiveLandscape, first landscape as fallback, or None.
    """
    if not competitive_analysis or not competitive_analysis.solution_landscapes:
        return None

    if solution_name:
        needle = solution_name.strip().lower()
        for landscape in competitive_analysis.solution_landscapes:
            if landscape.solution_name.strip().lower() == needle:
                return landscape

    # Fallback: return first landscape
    return competitive_analysis.solution_landscapes[0]
