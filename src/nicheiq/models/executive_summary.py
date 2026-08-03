"""
Executive Summary Models for NicheIQ Report

Provides top-level dashboard for quick decision-making with go/no-go verdict,
core pain point, and key opportunity metrics.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

class SolutionSnapshot(BaseModel):
    """Quick snapshot of the recommended solution.

    Every field here is DESCRIPTIVE. Each is Optional because each is sourced from an
    upstream field that is itself optional (or reconstructed by an LLM path that may drop
    it — e.g. UnifiedSolutionCrew._generate_pivot_revision rebuilds an idea from a narrow
    schema that carries no project_type). A required-but-nullable field here would let a
    missing label raise inside dashboard assembly and delete the Go/No-Go verdict with it,
    which is exactly the Sev-1 this shape prevents.

    None means "the pipeline never recorded this", and the defined rendering is OMISSION —
    the report UI already guards each of these (e.g. SolutionHero's
    ``{#if snapshot.project_type}`` badge). Never substitute a placeholder label: an absent
    project type is not a project type.
    """

    model_config = ConfigDict(extra='forbid')

    name: Optional[str] = Field(
        default=None,
        description="Solution name. None = not recorded."
    )
    tagline: Optional[str] = Field(
        default=None,
        description="One-sentence value proposition (10-15 words). None = not recorded."
    )
    core_value_prop: Optional[str] = Field(
        default=None,
        description="Core value proposition explaining what problem it solves and for whom "
                    "(2-3 sentences). None = not recorded."
    )
    project_type: Optional[str] = Field(
        default=None,
        description="Solution type (e.g., 'directory', 'aggregator', 'marketplace', 'tool'). "
                    "None = the pipeline never recorded a type for this idea."
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
    payability_context: Optional[str] = Field(
        default=None,
        description="Buyer-payability floor explanation (Phase 5), if any. "
                    "None = no adjustment applied."
    )
    red_team_context: Optional[str] = Field(
        default=None,
        description="Red-team floor explanation (Phase 5.5) — adversarial "
                    "'weakened'/'killed' finding on the selected idea, if any. "
                    "None = no adjustment applied."
    )


class VerdictExplanation(BaseModel):
    """LLM explanation of an ALREADY-DECIDED Go/No-Go verdict (never decides it)."""

    model_config = ConfigDict(extra='forbid')

    explanation: str = Field(
        description=("2-3 sentences explaining WHY this idea landed at its verdict, in plain qualitative "
                     "terms (e.g. 'good market fit, weak SEO') — NEVER numeric scores.")
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
    commercial_intent_score: float = Field(
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
    avg_commercial_intent: float = Field(
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
    solo_dev_feasibility: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Solo developer feasibility score (0-1 scale). None = N/A"
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

    # go_no_go_verdict is the ONLY required section: it is what the buyer paid for and what
    # the report exists to state. The three supporting sections are Optional so that a
    # failure to build any one of them degrades that section alone instead of discarding
    # the verdict. Anything listed in `unavailable_sections` is None here by construction.
    go_no_go_verdict: GoNoGoVerdict = Field(
        description="Strategic recommendation on pursuing this opportunity"
    )

    recommended_solution_snapshot: Optional[SolutionSnapshot] = Field(
        default=None,
        description="Quick overview of the recommended SaaS solution. None = could not be built."
    )

    core_pain_point: Optional[CorePainPoint] = Field(
        default=None,
        description="The #1 pain point driving this opportunity. None = could not be built."
    )

    key_metrics: Optional[KeyMetrics] = Field(
        default=None,
        description="Top-line metrics for opportunity assessment. None = could not be built."
    )

    unavailable_sections: list[str] = Field(
        default_factory=list,
        description="Names of dashboard sections that could not be produced for this run. "
                    "Empty = complete dashboard. Non-empty means the verdict is still valid "
                    "but the listed supporting detail is missing and must be shown as such."
    )

    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Average of market fit, competitive advantage, technical feasibility, and SEO scores (0-1). None if scores unavailable."
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
