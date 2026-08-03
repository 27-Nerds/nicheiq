"""
Pydantic models for solution refinement based on keyword insights (Stage 10).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FeaturePriority(BaseModel):
    """Recommended priority for a specific feature based on keyword demand."""

    model_config = ConfigDict(extra='ignore')

    feature_name: str = Field(..., description="Name of the feature")
    priority: float = Field(..., ge=1, le=10, description="Priority rank (1 = highest priority)")
    keyword_support: float = Field(
        ..., ge=0, description="Number of keywords that validate demand for this feature"
    )
    rationale: str = Field(
        ..., description="Explanation of why this priority was assigned based on keyword insights"
    )

class SolutionRefinement(BaseModel):
    """Strategic refinement recommendations based on keyword validation insights."""

    model_config = ConfigDict(extra='ignore')

    geographic_priorities: list[str] = Field(
        default_factory=list,
        description=(
            "Markets to prioritize, ranked, EACH traceable to a location term in the validated "
            "keywords. An EMPTY LIST is the correct answer when no validated keyword carries a "
            "location term — most niches have no geographic signal at all. Never rank markets "
            "from general knowledge or from what sounds plausible for the industry."
        )
    )
    # `min_length=1` and a worked example (['Spain', 'Portugal', 'France']) used to live here.
    # Together they guaranteed fabrication: the field was mandatory, most niches have no geo
    # signal, and the only concrete strings in scope were those countries — so runs shipped a
    # Spain-first go-to-market plan for US-only niches. Removing the example moved the model to
    # an honest sentinel ("Not geographically differentiated…"), which then rendered AS a ranked
    # market (live run 8f35ea6b). The real fix is permitting empty, which every consumer already
    # handles: the frontend guards on `.length > 0` and omits the section entirely.

    category_pivot_recommendation: Optional[str] = Field(
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
