"""
Pydantic models for solution ideas (Stage 7).
"""


from typing import Optional

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

class SolutionSEORefinement(BaseModel):
    """
    SEO score refinements from Stage 9.5 using actual keyword data.

    Contains ONLY the refined/new fields added after keyword research.
    Used in unified enrichment pattern where each stage outputs only its additions,
    then report generator merges all enrichments into complete SolutionIdea.
    """
    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of solution being refined")

    seo_scalability_score_refined: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Refined SEO scalability score using actual keyword volume data from Stage 9"
    )

    estimated_cac_organic_refined: Optional[str] = Field(
        default=None,
        description="Refined organic CAC range based on keyword difficulty and volume (e.g., '$12-25')"
    )

    programmatic_seo_opportunity_refined: Optional[str] = Field(
        default=None,
        description="Quantified programmatic SEO opportunity with page count estimates"
    )

    estimated_indexable_pages: Optional[int] = Field(
        default=None,
        description="Estimated number of indexable pages based on keyword research and content model"
    )

    seo_refinement_metadata: Optional[SEORefinementMetadata] = Field(
        default=None,
        description="Detailed calculation metadata showing how refined scores were derived"
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
    strengths: list[str] = Field(..., description="Key advantages and positive factors")
    weaknesses: list[str] = Field(..., description="Concerns, risks, or challenges")
    key_risks: list[str] = Field(..., description="Critical factors that could cause failure")

class EvaluationResult(BaseModel):
    """Complete evaluation results for all solutions."""

    model_config = ConfigDict(extra='forbid')

    evaluations: list[SolutionEvaluation] = Field(
        ..., description="Evaluation for each solution"
    )
    ranking: list[str] = Field(
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
    pain_points_addressed: list[str] = Field(
        ..., description="List of pain points this solution addresses"
    )
    core_features: list[str] = Field(
        ..., description="Key features for minimum viable product"
    )
    target_personas: list[str] = Field(
        ..., description="Target user persona descriptions"
    )
    technical_approach: Optional[str] = Field(
        default=None, description="Technical architecture and implementation approach"
    )
    differentiation_factors: Optional[list[str]] = Field(
        default=None, description="Unique factors that differentiate from competitors"
    )
    requires_data_aggregation: bool = Field(
        default=False,
        description="Whether product requires external data aggregation",
    )
    data_sources: Optional[list[str]] = Field(
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

    organic_discovery_queries: Optional[list[str]] = Field(
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

    estimated_indexable_pages: Optional[int] = Field(
        default=None,
        description=(
            "Estimated total potential indexable pages for SEO. "
            "Represents the full scope of programmatic content generation potential. "
            "Used for CAC calculations and growth projections. "
            "Populated during Stage 9.5 SEO refinement based on keyword research."
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

    # Keyword Validation & Refinement (Stage 8.8 and 8.85)
    keyword_geographic_priorities: Optional[list[str]] = Field(
        default=None,
        description=(
            "Geographic priorities identified from keyword validation data (Stage 8.8). "
            "List of 3-8 countries/regions with highest keyword opportunity based on search volume and competition. "
            "Examples: 'Portugal (450 keywords, avg vol 1.2k)', 'Spain (320 keywords, avg vol 890)', "
            "'Germany (280 keywords, high competition)'. "
            "Used for geographic expansion planning and localized content strategy."
        )
    )

    keyword_feature_priorities: Optional[list[str]] = Field(
        default=None,
        description=(
            "Feature or category priorities identified from keyword themes in Stage 8.8 validation. "
            "List of 3-8 feature areas or product categories with strong keyword support. "
            "Examples: 'Health insurance (580 keywords, Tier 1: 45)', 'Tax planning (320 keywords, Tier 1: 28)', "
            "'Banking services (210 keywords, high competition)'. "
            "Informs MVP scope and product roadmap decisions based on organic discovery potential."
        )
    )

    keyword_strategic_insights: Optional[str] = Field(
        default=None,
        description=(
            "Strategic insights derived from keyword validation data in Stage 8.8. "
            "2-3 sentence analysis covering: unexpected keyword opportunities discovered, "
            "competitive gaps revealed by low-competition/high-volume keywords, "
            "or geographic/categorical patterns that suggest pivot opportunities. "
            "Examples: 'Discovered untapped demand in Eastern Europe with 30% lower competition', "
            "'Tax residency keywords show 3x higher volume than anticipated, suggesting product expansion'."
        )
    )

    category_pivot_suggestion: Optional[str] = Field(
        default=None,
        description=(
            "Category or positioning pivot suggestion based on keyword validation findings from Stage 8.8. "
            "Single sentence recommendation if keyword data reveals stronger opportunity in adjacent category. "
            "Format: 'Consider pivoting from [original positioning] to [suggested positioning] based on [data insight]'. "
            "Examples: 'Consider pivoting from general expat directory to tax-focused platform based on 2.5x higher keyword volume in tax residency vertical', "
            "'null' if current positioning aligns with keyword data. Set to None if no pivot recommended."
        )
    )

class IdeaGenerationResult(BaseModel):
    """Complete result of solution idea generation."""

    model_config = ConfigDict(extra='forbid')

    solution_ideas: list[SolutionIdea] = Field(..., description="Generated solution concepts")
    recommended_solution: Optional[str] = Field(
        default=None, description="Recommended solution name from the list"
    )
    market_insights: str = Field(
        ..., description="Market insights and opportunity assessment"
    )

class SolutionEnhancement(BaseModel):
    """Enhancement data for a single solution from competitive analysis."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Solution name (must match Task 1)")
    new_core_features: list[str] = Field(
        default_factory=list,
        description="NEW features to add from competitive analysis (not all features)"
    )
    new_differentiation_factors: list[str] = Field(
        default_factory=list,
        description="NEW differentiation factors from competitive gaps (not all factors)"
    )
    value_proposition_update: Optional[str] = Field(
        default=None,
        description="Updated value proposition (only if competitive analysis suggests refinement)"
    )
    pricing_strategy_update: Optional[str] = Field(
        default=None,
        description="Refined pricing strategy (only if competitive analysis suggests changes)"
    )
    market_fit_score_adjustment: Optional[float] = Field(
        default=None,
        ge=-0.1,
        le=0.1,
        description="Market fit score adjustment based on competitive insights (max ±0.1)"
    )

class CompetitiveEnhancements(BaseModel):
    """
    Task 3 output: Competitive enhancements for solutions (ONLY new/changed data).

    Contains competitive insights to enhance solutions from Task 1.
    These enhancements will be merged with Task 1 solutions via Python.
    """

    model_config = ConfigDict(extra='forbid')

    solution_enhancements: list[SolutionEnhancement] = Field(
        ...,
        description="Enhancements for each solution based on competitive analysis"
    )
    overall_competitive_insights: str = Field(
        ...,
        description="Cross-solution competitive insights and market positioning (2-3 paragraphs)"
    )
