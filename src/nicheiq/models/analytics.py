"""
Analytics Models for NicheIQ Report

Provides computed analytics and metrics for visual dashboards and charts.
All analytics are Python-computed from existing research data (no LLM).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MarketAnalytics(BaseModel):
    """Market opportunity scores and analytics."""

    model_config = ConfigDict(extra='forbid')

    overall_opportunity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted average of selection criteria (0-1 scale)"
    )
    market_size_category: str = Field(
        description="Market size: Large (10K+ volume), Medium (1K-10K), Small (<1K)"
    )
    selection_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in solution selection (avg of top 2 criteria)"
    )
    competitive_intensity: str = Field(
        description="Competition level: Low (<3 competitors), Medium (3-7), High (8+)"
    )
    recommendation: str = Field(
        description="Go/Conditional/No-Go based on scores"
    )

class SEOAnalytics(BaseModel):
    """SEO keyword distribution and opportunity metrics."""

    model_config = ConfigDict(extra='forbid')

    tier0_count: int = Field(
        default=0,
        description="Number of Tier 0 (Premium) keywords with exceptional opportunity scores (>200)"
    )
    tier1_count: int = Field(
        description="Number of Tier 1 (Quick Win) keywords"
    )
    tier2_count: int = Field(
        description="Number of Tier 2 (Strategic Growth) keywords"
    )
    tier3_count: int = Field(
        default=0,
        description="Number of Tier 3 keywords"
    )
    tier4_count: int = Field(
        default=0,
        description="Number of Tier 4 keywords"
    )
    total_keywords: int = Field(
        description="Total keyword count across all tiers"
    )
    total_search_volume: int = Field(
        description="Total monthly search volume"
    )
    avg_competition: Optional[float] = Field(
        default=None,
        description="Average competition level across keywords (0-100 scale)"
    )
    keyword_diversity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Diversity score (0-1): higher = more varied keyword types"
    )
    high_volume_keywords: int = Field(
        default=0,
        description="Keywords with >1000 monthly searches"
    )

class CompetitiveAnalytics(BaseModel):
    """Competitive density and market coverage analytics."""

    model_config = ConfigDict(extra='forbid')

    competitor_count: int = Field(
        description="Total unique competitors identified"
    )
    market_saturation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Market saturation (0-1): 0=blue ocean, 1=saturated"
    )
    differentiation_strength: str = Field(
        description="Differentiation potential: Strong, Moderate, Weak"
    )
    market_gaps_identified: int = Field(
        description="Number of market gaps identified"
    )
    avg_competitor_features: Optional[float] = Field(
        default=None,
        description="Average feature count across competitors"
    )

class PainPointAnalytics(BaseModel):
    """Pain point clustering and priority matrix data."""

    model_config = ConfigDict(extra='forbid')

    total_pain_points: int = Field(
        description="Total pain points identified"
    )
    high_priority_count: int = Field(
        description="Pain points with severity >= 0.7"
    )
    quadrant_distribution: dict[str, int] = Field(
        description="Distribution across priority quadrants"
    )
    avg_severity: float = Field(
        ge=0.0,
        le=1.0,
        description="Average severity score"
    )
    avg_willingness_to_pay: float = Field(
        ge=0.0,
        le=1.0,
        description="Average WTP score"
    )
    top_pain_point_title: str = Field(
        description="Title of highest priority pain point"
    )

class VisualizationManifest(BaseModel):
    """Paths and metadata for generated visualizations."""

    model_config = ConfigDict(extra='forbid')

    pain_point_matrix_path: Optional[str] = Field(
        default=None,
        description="Path to pain point severity vs WTP scatter plot"
    )
    competitive_landscape_path: Optional[str] = Field(
        default=None,
        description="Path to competitive positioning chart"
    )
    keyword_opportunity_path: Optional[str] = Field(
        default=None,
        description="Path to keyword tier distribution chart"
    )
    implementation_timeline_path: Optional[str] = Field(
        default=None,
        description="Path to implementation roadmap chart"
    )
    charts_format: str = Field(
        default="png",
        description="Chart format: png, svg, or json (Plotly)"
    )
    generated_at: Optional[str] = Field(
        default=None,
        description="Timestamp when charts were generated"
    )
