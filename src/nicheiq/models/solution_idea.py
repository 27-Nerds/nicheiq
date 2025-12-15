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


class BaseSolutionIdea(BaseModel):
    """
    Solution idea as output by Stage 7 (UnifiedSolutionCrew).

    Contains ONLY the fields that Stage 7 should populate. Does NOT include:
    - Stage 8.85 keyword refinement fields (keyword_geographic_priorities, etc.)
    - Stage 9.5 SEO refinement fields (seo_scalability_score_refined, etc.)

    Those fields are added via Python merging in report_generator._merge_solution_enrichments()
    using separate output models (SolutionRefinement, SolutionSEORefinement).
    """

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

    # SEO & Organic Acquisition Fields (Stage 7 estimates - before keyword research)
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

    # Novelty & Solo-Dev Feasibility Fields (Stage 7)
    novelty_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Innovation/uniqueness score (0-1 scale). "
            "0.9-1.0: Novel mechanism, no direct competitors doing it this way. "
            "0.6-0.8: Unique combination of existing approaches. "
            "0.3-0.5: Better execution of known pattern. "
            "0.0-0.2: Minor variation on obvious/generic solution."
        )
    )

    novelty_justification: Optional[str] = Field(
        default=None,
        description=(
            "Explanation of why this solution is non-obvious. "
            "Format: 'This is surprising because most would try [obvious approach] "
            "but this does [unexpected thing] which works because [reason].' "
            "Required when novelty_score > 0.5 to validate the innovation claim."
        )
    )

    solo_dev_feasibility: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Feasibility for a solo developer to build and launch (0-1 scale). "
            "0.9-1.0: Static site + APIs, <2 months, no complex backend. "
            "0.7-0.8: Simple backend, 2-3 months, standard tech stack. "
            "0.4-0.6: Moderate complexity, 3-6 months, some specialized skills needed. "
            "0.0-0.3: Complex infrastructure, >6 months, or requires team/enterprise sales."
        )
    )


class SolutionIdea(BaseSolutionIdea):
    """
    Full solution idea with all enrichments from Stage 7, 8.85, and 9.5.

    Extends BaseSolutionIdea with fields populated by later pipeline stages:
    - Stage 8.85: Keyword refinement fields (from SolutionRefinement)
    - Stage 9.5: SEO refinement fields (from SolutionSEORefinement)

    Used in final reports after merging. NOT used as LLM output model in Stage 7.
    The report_generator._merge_solution_enrichments() creates SolutionIdea instances
    by combining BaseSolutionIdea with SolutionRefinement and SolutionSEORefinement.
    """

    # Stage 8.85: Keyword Validation & Refinement (from SolutionRefinement)
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

    # Stage 9.5: Refined SEO Metrics (from SolutionSEORefinement)
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
    """
    Complete result of solution idea generation (Stage 7).

    Uses BaseSolutionIdea (NOT SolutionIdea) to ensure LLM only outputs
    Stage 7 fields. Enrichment fields from Stage 8.85 and 9.5 are added
    later via Python merging in report_generator._merge_solution_enrichments().
    """

    model_config = ConfigDict(extra='forbid')

    solution_ideas: list[BaseSolutionIdea] = Field(..., description="Generated solution concepts")
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


class IdeationProcess(BaseModel):
    """
    Metadata about the ideation/filtering process for transparency.

    Captures the divergent-convergent ideation workflow to provide visibility into:
    - How many concepts were generated and filtered
    - Which concepts were removed and why
    - What ideation techniques were applied
    """

    model_config = ConfigDict(extra='forbid')

    total_concepts_generated: int = Field(
        ...,
        description="Total raw concepts from divergent exploration phase"
    )
    concepts_filtered: int = Field(
        ...,
        description="Number of concepts filtered out during diversity pass"
    )
    removed_concepts: list[str] = Field(
        default_factory=list,
        description="Names of concepts removed as duplicates or too similar"
    )
    removal_reasons: list[str] = Field(
        default_factory=list,
        description="Explanations for why each removed concept was filtered"
    )
    techniques_used: list[str] = Field(
        default_factory=list,
        description="Ideation techniques applied during exploration (e.g., niche_drilling, data_source_inversion)"
    )
    diversity_summary: Optional[str] = Field(
        default=None,
        description="Summary of diversity achieved: project types represented, data sources covered"
    )


# =============================================================================
# Divergent-Convergent Ideation Models (3-Task Architecture)
# =============================================================================

class RawConcept(BaseModel):
    """
    Lightweight concept from divergent exploration (Task 1).

    Minimal fields to capture wild ideas quickly without premature evaluation.
    Each concept should be generated using one of the forced ideation techniques.
    """

    model_config = ConfigDict(extra='forbid')

    concept_name: str = Field(
        ...,
        description="Short, descriptive name for the concept (e.g., 'PlumbingCostCalc', 'RemoteTaxAdvisors')"
    )
    one_liner: str = Field(
        ...,
        description=(
            "1-2 sentence description of what this solution does and why it's interesting. "
            "Focus on the unique angle, not generic 'helps users with X'. "
            "Example: 'Aggregates plumber pricing from 50 cities to generate [City] plumbing cost pages.'"
        )
    )
    ideation_technique: str = Field(
        ...,
        description=(
            "Which ideation technique generated this concept. One of: "
            "'niche_drilling' (specific sub-niche), "
            "'data_source_inversion' (unique data source), "
            "'cross_industry_template' (pattern from other industry), "
            "'atomic_feature' (single feature as product), "
            "'community_flip' (users create content for each other)"
        )
    )
    project_type: str = Field(
        ...,
        description="Project type: directory, aggregator, comparison-tool, marketplace, saas, or other"
    )
    target_keywords: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description=(
            "2-5 example SEO keywords this solution would target. "
            "Must be specific search queries users would type. "
            "Example: ['[city] plumbing cost', 'plumber prices near me', 'how much does plumber charge']"
        )
    )
    data_source_hint: Optional[str] = Field(
        default=None,
        description=(
            "Hint about the primary data source or mechanism. "
            "Examples: 'Reddit discussions', 'Government APIs', 'User submissions', 'Web scraping [sites]'"
        )
    )


class RawConceptList(BaseModel):
    """
    Output of divergent exploration task (Task 1).

    Contains 8-12 raw concepts generated using forced ideation techniques.
    No evaluation or scoring at this stage - quantity and variety over quality.
    """

    model_config = ConfigDict(extra='forbid')

    concepts: list[RawConcept] = Field(
        ...,
        min_length=6,
        max_length=15,
        description="8-12 raw concepts from divergent exploration (minimum 6, maximum 15)"
    )
    techniques_used: list[str] = Field(
        ...,
        description="List of ideation techniques applied during exploration"
    )
    pain_points_referenced: list[str] = Field(
        ...,
        description="Pain point titles that informed the concept generation"
    )


class FilteredConceptList(BaseModel):
    """
    Output of diversity filtering task (Task 2).

    Contains 5-7 unique concepts after removing duplicates and enforcing diversity.
    Includes transparency about what was removed and why.
    """

    model_config = ConfigDict(extra='forbid')

    concepts: list[RawConcept] = Field(
        ...,
        min_length=3,
        max_length=8,
        description="5-7 unique concepts after filtering (minimum 3, maximum 8)"
    )
    removed_concepts: list[str] = Field(
        ...,
        description="Names of concepts removed as duplicates or too similar"
    )
    removal_reasons: list[str] = Field(
        ...,
        description=(
            "Explanations for why each removed concept was filtered. "
            "Format: '[ConceptName]: [reason]' "
            "Example: 'VendorCompare: Too similar to VendorMatch (same data source + mechanism)'"
        )
    )
    diversity_summary: str = Field(
        ...,
        description=(
            "Summary of diversity achieved: project types represented, "
            "data sources variety, niche specificity distribution. "
            "Example: '3 directories, 2 aggregators, 1 comparison tool across 4 unique data sources'"
        )
    )
