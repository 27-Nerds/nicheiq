"""
Pydantic models for solution ideas (Stage 7).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SEORefinementMetadata(BaseModel):
    """Metadata about SEO refinement process for transparency."""

    model_config = ConfigDict(extra='forbid')

    baseline_volume_used: Optional[int] = Field(
        default=None, description="Baseline search volume used for calculations"
    )
    volume_multiplier: Optional[float] = Field(
        default=None, description="Multiplier applied based on actual vs baseline volume"
    )
    tier1_multiplier: Optional[float] = Field(
        default=None, description="Multiplier based on Tier 1 keyword count"
    )
    competition_modifier: Optional[float] = Field(
        default=None, description="Modifier based on average competition level"
    )
    base_cac: Optional[float] = Field(
        default=None, description="Base customer acquisition cost before adjustments"
    )
    difficulty_multiplier: Optional[float] = Field(
        default=None, description="Multiplier based on keyword difficulty"
    )
    volume_discount: Optional[float] = Field(
        default=None, description="Discount applied for high volume economies of scale"
    )
    estimated_year1_pages: Optional[int] = Field(
        default=None, description="Estimated number of pages in first year"
    )


class SolutionEvaluation(BaseModel):
    """Evaluation scores and analysis for a single solution."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the solution being evaluated")
    technical_feasibility_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Technical feasibility score (0.0-1.0 scale)"
    )
    market_fit_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Product-market fit score (0.0-1.0 scale)"
    )
    development_complexity: str = Field(
        ..., description="Development complexity: Low, Medium, or High"
    )
    estimated_development_time: str = Field(
        ..., description="Estimated time to MVP (e.g., '3-4 months', '6-8 months')"
    )
    differentiation_potential: float = Field(
        ..., ge=0.0, le=1.0,
        description="Differentiation potential score (0.0-1.0 scale)"
    )
    organic_acquisition_potential: float = Field(
        ..., ge=0.0, le=1.0,
        description="Organic acquisition potential score (0.0-1.0 scale) - effectiveness of SEO/content for customer acquisition"
    )
    strengths: List[str] = Field(..., description="Key advantages and positive factors")
    weaknesses: List[str] = Field(..., description="Concerns, risks, or challenges")
    key_risks: List[str] = Field(..., description="Critical factors that could cause failure")


class EvaluationResult(BaseModel):
    """Complete evaluation results for all solutions."""

    model_config = ConfigDict(extra='forbid')

    evaluations: List[SolutionEvaluation] = Field(
        ..., description="Evaluation for each solution"
    )
    ranking: List[str] = Field(
        ..., description="Solution names ranked by overall opportunity"
    )
    comparative_analysis: str = Field(
        ..., description="Side-by-side comparison and recommendation"
    )


class SolutionIdea(BaseModel):
    """Represents a micro-SaaS product concept."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the proposed product")
    description: str = Field(
        ...,
        description=(
            "Detailed description of HOW the solution works from the user's perspective. "
            "Should include the complete user journey: what users see when they arrive, "
            "what actions they take, what inputs they provide, what results they get, "
            "and how the solution delivers value. Must be specific and concrete enough "
            "that someone could visualize using the service (4-6 sentences minimum)."
        )
    )
    value_proposition: str = Field(
        ...,
        description=(
            "One-line value proposition clearly stating the core benefit. "
            "Should be a single compelling sentence that captures the unique value "
            "compared to alternatives. Not a tagline - a clear statement of what users get."
        )
    )
    pain_points_addressed: List[str] = Field(
        ..., description="List of pain points this solution addresses"
    )
    core_features: List[str] = Field(
        ..., description="Key features for minimum viable product"
    )
    target_personas: List[str] = Field(
        ..., description="Target user persona descriptions"
    )
    technical_approach: Optional[str] = Field(
        default=None, description="Technical architecture and implementation approach"
    )
    differentiation_factors: Optional[List[str]] = Field(
        default=None, description="Unique factors that differentiate from competitors"
    )
    requires_data_aggregation: bool = Field(
        default=False,
        description="Whether product requires external data aggregation",
    )
    data_sources: Optional[List[str]] = Field(
        default=None,
        description="Potential data sources if aggregation is required",
    )
    estimated_development_time: Optional[str] = Field(
        default=None, description="Estimated time to build MVP"
    )
    pricing_strategy: Optional[str] = Field(
        default=None, description="Detailed pricing model and monetization strategy"
    )
    market_fit_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Product-market fit evaluation score (0-1)"
    )
    technical_feasibility_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Technical feasibility assessment score (0-1)"
    )
    project_type: Optional[str] = Field(
        default=None,
        description="Project type category: saas, directory, aggregator, comparison-tool, marketplace"
    )

    # SEO & Organic Acquisition Fields
    programmatic_seo_opportunity: Optional[str] = Field(
        default=None,
        description=(
            "Assessment of programmatic SEO potential for this solution type. "
            "Examples: 'High - directory listings generate natural SEO pages', "
            "'Medium - comparison pages create indexable content', "
            "'Low - pure SaaS with minimal content generation'. "
            "Should reference specific content generation patterns and estimated page count potential."
        )
    )

    content_generation_model: Optional[str] = Field(
        default=None,
        description=(
            "Description of how this solution naturally generates SEO-friendly content. "
            "Examples: 'User submissions create unique tool pages', "
            "'Aggregated data creates comparison landing pages', "
            "'Manual content marketing via blog and guides'. "
            "Focus on WHAT content gets created, not HOW to build it technically."
        )
    )

    organic_discovery_queries: Optional[List[str]] = Field(
        default=None,
        description=(
            "5-10 example search queries where users would naturally discover this solution organically. "
            "Should reflect actual search intent patterns that the solution's content would rank for. "
            "Examples: 'best [tool type] for [use case]', '[problem] solutions', '[category] comparison'"
        )
    )

    estimated_cac_organic: Optional[str] = Field(
        default=None,
        description=(
            "Estimated customer acquisition cost via organic channels (SEO, content marketing). "
            "Format: '$X-Y per customer' with rationale. "
            "Consider: programmatic content generation reduces CAC dramatically vs paid channels. "
            "Examples: '$5-15 (programmatic SEO pages)', '$50-100 (traditional SEO + content)', "
            "'$200+ (limited content opportunities, relies on paid)'"
        )
    )

    estimated_cac_paid: Optional[str] = Field(
        default=None,
        description=(
            "Estimated customer acquisition cost via paid channels (ads, PPC) for comparison. "
            "Format: '$X-Y per customer' with rationale. "
            "Use for CAC comparison to highlight organic advantage. "
            "Examples: '$100-300 (competitive keywords)', '$50-150 (niche keywords)'"
        )
    )

    seo_scalability_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "SEO scalability assessment (0-1 scale). "
            "How easily can this solution scale organic traffic through content? "
            "0.8-1.0: High programmatic SEO potential (directories, aggregators) "
            "0.5-0.7: Moderate content generation (comparison tools, marketplaces) "
            "0.2-0.4: Limited content scaling (traditional SaaS) "
            "0.0-0.1: Minimal SEO leverage (tool-only products)"
        )
    )

    # Refined SEO Metrics (Stage 9.5 - Post-Keyword Discovery)
    seo_scalability_score_refined: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Refined SEO scalability score based on actual keyword data from Stage 9. "
            "Adjusts the architectural estimate using: "
            "(1) total keyword volume vs baseline, "
            "(2) Tier 1 quick win count, "
            "(3) average competition level. "
            "Compare to seo_scalability_score to see impact of market reality."
        )
    )

    estimated_cac_organic_refined: Optional[str] = Field(
        default=None,
        description=(
            "Refined organic CAC estimate based on actual keyword difficulty and volume. "
            "Format: '$X-Y per customer' with adjusted range. "
            "Factors in: (1) Tier 1 keyword competition levels, "
            "(2) total market volume for economies of scale. "
            "Compare to estimated_cac_organic to see refinement."
        )
    )

    programmatic_seo_opportunity_refined: Optional[str] = Field(
        default=None,
        description=(
            "Refined programmatic SEO assessment with quantitative page count estimates. "
            "Based on discovered keyword opportunities: Tier 1 landing pages, "
            "topic clusters, geographic/category variations. "
            "Includes both the calculated page potential and the original qualitative assessment."
        )
    )

    seo_refinement_metadata: Optional[SEORefinementMetadata] = Field(
        default=None,
        description=(
            "Metadata about the SEO refinement process for transparency. "
            "Includes: baseline_volume_used, volume_multiplier, tier1_multiplier, "
            "competition_modifier, base_cac, difficulty_multiplier, volume_discount, "
            "estimated_year1_pages. Useful for debugging and understanding score changes."
        )
    )


class IdeaGenerationResult(BaseModel):
    """Complete result of solution idea generation."""

    model_config = ConfigDict(extra='forbid')

    solution_ideas: List[SolutionIdea] = Field(..., description="Generated solution concepts")
    recommended_solution: Optional[str] = Field(
        default=None, description="Recommended solution name from the list"
    )
    market_insights: str = Field(
        ..., description="Market insights and opportunity assessment"
    )
