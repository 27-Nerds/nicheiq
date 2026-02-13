"""
Executive Summary Models for NicheIQ Report

Provides top-level dashboard for quick decision-making with go/no-go verdict,
core pain point, and key opportunity metrics.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SolutionSnapshot(BaseModel):
    """Quick snapshot of the recommended solution."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(
        description="Solution name"
    )
    tagline: str = Field(
        description="One-sentence value proposition (10-15 words)"
    )
    core_value_prop: str = Field(
        description="Core value proposition explaining what problem it solves and for whom (2-3 sentences)"
    )
    project_type: str = Field(
        description="Solution type (e.g., 'directory', 'aggregator', 'marketplace', 'tool')"
    )

class GoNoGoVerdict(BaseModel):
    """Strategic recommendation on whether to pursue this opportunity."""

    model_config = ConfigDict(extra='forbid')

    verdict: Literal["Go", "No-Go", "Conditional"] = Field(
        description="Overall recommendation: Go (pursue), No-Go (avoid), or Conditional (pursue with caution)"
    )
    rationale: str = Field(
        description="2-3 sentence explanation of the verdict based on market fit, competition, and SEO opportunity"
    )
    risk_level: Literal["Low", "Medium", "High"] = Field(
        description="Overall risk assessment"
    )
    primary_concern: Optional[str] = Field(
        default=None,
        description="Main concern or blocker if verdict is No-Go or Conditional"
    )
    trend_context: Optional[str] = Field(
        default=None,
        description="Trend-based adjustment explanation, if any. None = no adjustment applied."
    )
    market_viability_context: Optional[str] = Field(
        default=None,
        description="Market viability adjustment explanation, if any. None = no adjustment applied."
    )

class CorePainPoint(BaseModel):
    """The single most important pain point driving this opportunity."""

    model_config = ConfigDict(extra='forbid')

    title: str = Field(
        description="Pain point title"
    )
    severity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Severity score (0-1 scale)"
    )
    willingness_to_pay_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Willingness to pay score (0-1 scale)"
    )
    representative_quote: str = Field(
        description="Actual user quote illustrating this pain point"
    )
    source_platform: str = Field(
        description="Where the quote came from (e.g., 'Reddit r/subreddit', 'Twitter')"
    )

class KeyMetrics(BaseModel):
    """Top-line metrics for opportunity assessment."""

    model_config = ConfigDict(extra='forbid')

    total_keyword_search_volume: int = Field(
        description="Total monthly search volume from SEO strategy analysis. Falls back to keyword validation volume for legacy data."
    )
    tier0_keyword_count: int = Field(
        description="Number of Tier 0 (Foundation) keywords"
    )
    tier1_keyword_count: int = Field(
        description="Number of Tier 1 (Quick Win) keywords"
    )
    tier2_keyword_count: int = Field(
        description="Number of Tier 2 (Strategic Growth) keywords"
    )
    tier3_keyword_count: int = Field(
        default=0,
        description="Number of Tier 3 (Long Term) keywords"
    )
    tier4_keyword_count: int = Field(
        default=0,
        description="Number of Tier 4 (Low Priority) keywords"
    )
    total_keyword_count: int = Field(
        description="Total number of enriched keywords analyzed"
    )
    high_severity_pain_points: int = Field(
        description="Number of pain points with severity >= 0.7 (single-criterion severity threshold)"
    )
    primary_competitor_count: int = Field(
        description="Number of direct competitors identified"
    )
    avg_pain_point_severity: float = Field(
        ge=0.0,
        le=1.0,
        description="Average severity score across all pain points"
    )
    avg_willingness_to_pay: float = Field(
        ge=0.0,
        le=1.0,
        description="Average willingness-to-pay score across all pain points"
    )
    social_evidence_threads: int = Field(
        description="Number of Reddit/Twitter threads analyzed"
    )
    market_fit_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Market fit score from selection criteria (0-1 scale). None = N/A"
    )
    competitive_advantage_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Competitive advantage score from selection criteria (0-1 scale). None = N/A"
    )
    technical_feasibility_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Technical feasibility score from selection criteria (0-1 scale). None = N/A"
    )
    seo_potential_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="SEO growth potential score from selection criteria (0-1 scale). None = N/A"
    )

class ExecutiveDashboard(BaseModel):
    """
    Top-level executive summary for quick decision-making.

    Positioned first in the report to provide immediate clarity on:
    - What solution to build
    - Whether to pursue it (Go/No-Go)
    - What problem it solves
    - Key opportunity metrics
    """

    model_config = ConfigDict(extra='forbid')

    recommended_solution_snapshot: SolutionSnapshot = Field(
        description="Quick overview of the recommended SaaS solution"
    )

    go_no_go_verdict: GoNoGoVerdict = Field(
        description="Strategic recommendation on pursuing this opportunity"
    )

    core_pain_point: CorePainPoint = Field(
        description="The #1 pain point driving this opportunity"
    )

    key_metrics: KeyMetrics = Field(
        description="Top-line metrics for opportunity assessment"
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Average of market fit, competitive advantage, technical feasibility, and SEO scores (0-1)"
    )

    research_depth_label: str = Field(
        default="Standard Research",
        description="Human-readable research depth: 'Premium Research', 'Standard Research', or 'Basic Research'"
    )
    # niche_description removed - use root report.niche instead

# Model for LLM-generated strategic narrative (hybrid approach)
class ExecutiveNarrative(BaseModel):
    """
    LLM-generated strategic narrative components.

    This is generated separately using minimal LLM synthesis,
    while metrics are computed via Python.
    """

    model_config = ConfigDict(extra='forbid')

    tagline: str = Field(
        description="One-sentence value proposition for the solution (10-15 words)"
    )

    core_value_prop: str = Field(
        description="Core value proposition (2-3 sentences)"
    )

    verdict_rationale: str = Field(
        description="2-3 sentence rationale for the Go/No-Go verdict"
    )
