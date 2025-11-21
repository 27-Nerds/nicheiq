"""
Pydantic models for solution refinement based on keyword insights (Stage 8.85).
"""

from pydantic import BaseModel, ConfigDict, Field


class FeaturePriority(BaseModel):
    """Recommended priority for a specific feature based on keyword demand."""

    model_config = ConfigDict(extra='forbid')

    feature_name: str = Field(..., description="Name of the feature")
    priority: int = Field(..., ge=1, le=10, description="Priority rank (1 = highest priority)")
    keyword_support: int = Field(
        ..., ge=0, description="Number of keywords that validate demand for this feature"
    )
    rationale: str = Field(
        ..., description="Explanation of why this priority was assigned based on keyword insights"
    )

class SolutionRefinement(BaseModel):
    """Strategic refinement recommendations based on keyword validation insights."""

    model_config = ConfigDict(extra='forbid')

    geographic_priorities: list[str] = Field(
        ...,
        description=(
            "Ranked list of geographic markets to prioritize based on keyword volume and demand. "
            "Examples: ['Spain', 'Portugal', 'France'], ['United States', 'Canada', 'United Kingdom']. "
            "Order reflects keyword volume and market opportunity."
        )
    )

    category_pivot_recommendation: str | None = Field(
        default=None,
        description=(
            "Suggested category/vertical pivot if keyword analysis reveals better positioning opportunity. "
            "Examples: 'Focus on remote workers instead of digital nomads', "
            "'Pivot to B2B SaaS positioning from B2C', "
            "'Expand from freelancers to broader gig economy professionals'. "
            "Only populated if keywords strongly suggest a positioning shift."
        )
    )

    feature_priorities: list[FeaturePriority] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Top 5-10 features ranked by keyword support and demand signals. "
            "Helps prioritize MVP development based on what users are actively searching for."
        )
    )

    content_strategy_preview: str = Field(
        ...,
        description=(
            "Early content strategy recommendations based on top keyword themes and clusters. "
            "Should be 2-3 paragraphs outlining which content types to prioritize, "
            "what topics resonate most with search demand, and how to structure the content roadmap. "
            "Examples: pillar pages, comparison content, geographic landing pages, how-to guides."
        )
    )

    strategic_insights: list[str] = Field(
        ...,
        min_length=3,
        max_length=8,
        description=(
            "3-8 key actionable insights from keyword analysis. "
            "Should highlight non-obvious opportunities, potential risks, or strategic advantages. "
            "Examples: 'Strong demand in tier-2 cities overlooked by competitors', "
            "'Seasonal spike in Q1 suggests tax-season positioning', "
            "'Long-tail keywords indicate educational content gap'."
        )
    )
