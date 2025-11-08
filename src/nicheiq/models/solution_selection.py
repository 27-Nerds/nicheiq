"""
Solution Selection Model - Stage 8.5

Captures the selected solution and selection rationale after competitive analysis.
This model represents the strategic decision of which solution to focus on for
SEO strategy, keyword research, and implementation.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SelectionCriteriaScore(BaseModel):
    """Single selection criteria score entry."""

    model_config = ConfigDict(extra='forbid')

    criterion: str = Field(..., description="Criterion name (e.g., 'market_fit', 'technical_feasibility')")
    score: float = Field(..., description="Score value (0-1 scale)")


class SolutionSelection(BaseModel):
    """
    Results of solution selection process (Stage 8.5).

    After analyzing all solution ideas through competitive research,
    this model identifies which single solution to focus on for
    keyword research, SEO strategy, and MVP development.
    """

    model_config = ConfigDict(extra='forbid')

    selected_solution_name: str = Field(
        ...,
        description="Name of the selected solution to focus on"
    )

    selection_rationale: str = Field(
        ...,
        description=(
            "2-3 paragraphs explaining WHY this solution was selected over alternatives. "
            "Should reference specific data points: market fit scores, competitive gaps, "
            "pain point alignment, and strategic advantages."
        )
    )

    selection_criteria_scores: Optional[List[SelectionCriteriaScore]] = Field(
        default=None,
        description=(
            "Breakdown of selection criteria scores (0-1 scale). "
            "Typical criteria: market_fit, technical_feasibility, competitive_advantage, "
            "organic_acquisition_potential"
        )
    )

    runner_up_solutions: Optional[List[str]] = Field(
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
