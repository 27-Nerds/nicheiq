"""
Pydantic models for solution ideas (Stage 7).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SolutionIdea(BaseModel):
    """Represents a micro-SaaS product concept."""

    solution_name: str = Field(..., description="Name of the proposed product")
    description: str = Field(..., description="Detailed description of the solution")
    value_proposition: str = Field(
        ..., description="Unique value compared to alternatives"
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
    differentiation_factors: List[str] = Field(
        default_factory=list, description="Unique factors that differentiate from competitors"
    )
    requires_data_aggregation: bool = Field(
        default=False,
        description="Whether product requires external data aggregation",
    )
    data_sources: List[str] = Field(
        default_factory=list,
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

    class Config:
        json_schema_extra = {
            "example": {
                "solution_name": "NicheHire",
                "description": "Specialized freelancer marketplace for niche technical skills",
                "value_proposition": "Focus on verification and matching for niche skills",
                "pain_points_addressed": ["Difficulty finding specialized freelancers"],
                "core_features": [
                    "Skill-based search",
                    "Portfolio verification",
                    "Direct messaging",
                ],
                "target_personas": ["Startup founders", "Technical leads hiring for specialized roles"],
                "technical_approach": "React/Node.js stack with AI-powered matching algorithm",
                "differentiation_factors": [
                    "Verified portfolio system",
                    "Niche-specific matching algorithm",
                    "Quality over quantity focus"
                ],
                "requires_data_aggregation": False,
                "data_sources": [],
                "estimated_development_time": "6-8 weeks",
                "pricing_strategy": "15-20% commission on successful hires, with subscription tier for high-volume hirers",
                "market_fit_score": 0.85,
                "technical_feasibility_score": 0.9,
            }
        }


class IdeaGenerationResult(BaseModel):
    """Complete result of solution idea generation."""

    solution_ideas: List[SolutionIdea] = Field(..., description="Generated solution concepts")
    recommended_solution: Optional[str] = Field(
        default=None, description="Recommended solution name from the list"
    )
    market_insights: str = Field(
        ..., description="Market insights and opportunity assessment"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "solution_ideas": [],
                "recommended_solution": "NicheHire",
                "market_insights": "Market analysis reveals strong demand for specialized freelancer matching with estimated TAM of $500M...",
            }
        }
