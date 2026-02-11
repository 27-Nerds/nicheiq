"""
Solution Selection Model - Stage 5

Captures the selected solution and selection rationale after competitive analysis.
This model represents the strategic decision of which solution to focus on for
SEO strategy, keyword research, and implementation.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SelectionCriteriaScore(BaseModel):
    """Single selection criteria score entry."""

    model_config = ConfigDict(extra='forbid')

    criterion: str = Field(..., description="Criterion name (e.g., 'market_fit', 'technical_feasibility')")
    score: float = Field(..., ge=0.0, le=1.0, description="Score value (0-1 scale)")
    justification: Optional[str] = Field(default=None, description="Brief justification for the score")

class SolutionScores(BaseModel):
    """Complete selection scores for a single solution."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of the solution")
    market_fit_score: float = Field(..., ge=0.0, le=1.0, description="Market fit score (0-1)")
    technical_feasibility_score: float = Field(..., ge=0.0, le=1.0, description="Technical feasibility score (0-1)")
    competitive_advantage_score: float = Field(..., ge=0.0, le=1.0, description="Competitive advantage score (0-1)")
    seo_growth_potential_score: float = Field(..., ge=0.0, le=1.0, description="SEO growth potential score (0-1)")
    composite_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite score")
    rank: int = Field(..., description="Rank among all solutions (1 = best)")

    # keyword validation: Keyword Validation Fields
    keyword_demand_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Keyword demand score from keyword validation validation (0-1). "
            "Formula: (0.60 × volume_score) + (0.40 × opportunity_score). "
            "0.80-1.0: Exceptional, 0.65-0.79: Strong, 0.50-0.64: Moderate, <0.50: Weak"
        )
    )

    adjusted_composite_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Adjusted composite score after keyword validation. "
            "Formula: composite_score × keyword_demand_score. "
            "Used for final re-ranking in keyword validation."
        )
    )

class SolutionSelection(BaseModel):
    """
    Results of solution selection process (Stage 5).

    After analyzing all solution ideas through competitive research,
    this model identifies which single solution to focus on for
    keyword research, SEO strategy, and MVP development.
    """

    model_config = ConfigDict(extra='ignore')

    selected_solution_name: str = Field(
        ...,
        min_length=3,
        description="Name of the selected solution to focus on (minimum 3 chars)"
    )

    selection_rationale: str = Field(
        ...,
        min_length=100,
        description=(
            "2-3 paragraphs explaining WHY this solution was selected over alternatives. "
            "Should reference specific data points: market fit scores, competitive gaps, "
            "pain point alignment, and strategic advantages. (minimum 100 chars)"
        )
    )

    selection_criteria_scores: Optional[list[SelectionCriteriaScore]] = Field(
        default=None,
        description=(
            "Breakdown of selection criteria scores (0-1 scale) for the selected solution. "
            "Typical criteria: market_fit, technical_feasibility, competitive_advantage, "
            "organic_acquisition_potential"
        )
    )

    all_solution_scores: Optional[list[SolutionScores]] = Field(
        default=None,
        description=(
            "Complete scores for ALL solutions evaluated (selected + runner-ups). "
            "Includes market_fit, technical_feasibility, competitive_advantage, seo_growth_potential, "
            "composite score, and rank. Enables transparent comparison across all alternatives."
        )
    )

    runner_up_solutions: Optional[list[str]] = Field(
        default=None,
        description="Names of other viable solutions considered (in priority order)"
    )

    recommended_focus: str = Field(
        ...,
        description=(
            "Strategic focus recommendation for the selected solution. "
            "Examples: 'Geographic expansion starting with Spain', "
            "'Enterprise segment first, then SMB', 'Niche dominance in [specific vertical]'"
        )
    )
