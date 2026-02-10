"""
Solution preview models for the interactive job flow.

These models represent the solution data shown to users during
the selection phase, including validation data from pricing/keyword stages.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SolutionValidationData(BaseModel):
    """Validation data for a single solution (from pricing + keyword stages)."""

    model_config = ConfigDict(extra="allow")

    keyword_demand_score: Optional[float] = Field(
        default=None, description="Keyword demand score from validation"
    )
    demand_signal: Optional[str] = Field(
        default=None, description="Demand signal assessment (e.g., 'Strong', 'Moderate')"
    )
    total_volume: Optional[int] = Field(
        default=None, description="Total keyword search volume"
    )
    validated_count: Optional[int] = Field(
        default=None, description="Number of keywords validated"
    )
    avg_keyword_difficulty: Optional[float] = Field(
        default=None, description="Average keyword difficulty"
    )
    rankability_factor: Optional[float] = Field(
        default=None, description="Rankability factor from difficulty analysis"
    )
    top_keywords: Optional[list[dict]] = Field(
        default=None, description="Top validated keywords with volume/difficulty"
    )
    top_geographic_keywords: Optional[list[dict]] = Field(
        default=None, description="Top geographic keyword opportunities"
    )
    pricing_validation: Optional[dict] = Field(
        default=None, description="Pricing validation results"
    )


class SolutionPreview(BaseModel):
    """
    A solution idea as presented to users during the selection phase.

    Contains the display fields from BaseSolutionIdea plus optional
    validation data that arrives incrementally during the validation phase.
    """

    model_config = ConfigDict(extra="allow")

    # Core identity fields
    solution_name: str = Field(..., alias="name", description="Solution name")
    description: str = Field(..., description="Solution description")
    value_proposition: str = Field(..., description="Value proposition")

    # Analysis fields
    pain_points_addressed: list[str] = Field(default_factory=list)
    core_features: list[str] = Field(default_factory=list)
    target_personas: list[str] = Field(default_factory=list)
    project_type: Optional[str] = None
    differentiation_factors: Optional[list[str]] = None

    # Scores
    market_fit_score: Optional[float] = None
    technical_feasibility_score: Optional[float] = None
    seo_scalability_score: Optional[float] = None
    novelty_score: Optional[float] = None

    # SEO fields
    programmatic_seo_opportunity: Optional[str] = None
    estimated_cac_organic: Optional[str] = None
    organic_discovery_queries: Optional[list[str]] = None

    # Validation state
    validated: bool = Field(default=False, description="Whether validation has completed")
    validation: Optional[SolutionValidationData] = Field(
        default=None, description="Validation data (null until validated)"
    )

    # Composite score (may be adjusted after validation)
    adjusted_composite_score: Optional[float] = Field(
        default=None, description="Score adjusted after validation data"
    )


class SolutionPreviewList(BaseModel):
    """Collection of solution previews for the selection phase."""

    model_config = ConfigDict(extra="allow")

    solutions: list[SolutionPreview] = Field(default_factory=list)
    generation_round: int = Field(default=1, description="1 = initial, 2 = regenerated")
    can_regenerate: bool = Field(default=True)
    pain_points_summary: Optional[str] = Field(
        default=None, description="Brief summary of pain points driving these solutions"
    )
    niche_context: Optional[str] = Field(
        default=None, description="Context about the niche"
    )
