"""
Pydantic models for research flow state management.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .competitor import CompetitiveAnalysisResult
from .keyword_data import KeywordValidationResult
from .pain_point import PainPointAnalysisResult
from .social_content import SocialContentCollection
from .solution_idea import IdeaGenerationResult


class NicheContext(BaseModel):
    """Initial niche understanding (Stage 1)."""

    niche_input: str = Field(..., description="User's niche input")
    niche_description: str = Field(..., description="LLM-generated niche description")
    market_segments: List[str] = Field(..., description="Key market segments")
    industry_boundaries: str = Field(..., description="Industry boundaries definition")


class SearchQuery(BaseModel):
    """A single search query."""

    query: str = Field(..., description="Search query text")
    query_type: str = Field(
        ..., description="Type: problem/alternative/frustration/solution"
    )
    platform: str = Field(..., description="Target platform: reddit/twitter")


class FinalReport(BaseModel):
    """Final comprehensive research report (Stage 10)."""

    niche: str = Field(..., description="Niche analyzed")
    executive_summary: str = Field(..., description="High-level executive summary")
    top_pain_points: List[str] = Field(..., description="Top identified pain points")
    recommended_solutions: List[str] = Field(
        ..., description="Recommended solution ideas to pursue"
    )
    market_validation: str = Field(..., description="Overall market validation conclusion")
    seo_implementation_guide: str = Field(
        ..., description="Detailed SEO implementation strategy"
    )
    data_sourcing_recommendations: str = Field(
        ..., description="Data sourcing strategy for aggregation projects"
    )
    next_steps: List[str] = Field(..., description="Recommended next steps")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )
    pdf_path: Optional[str] = Field(default=None, description="Path to generated PDF report")


class ResearchState(BaseModel):
    """Complete state for the research flow."""

    # Stage 1: Niche Analysis
    niche_context: Optional[NicheContext] = None

    # Stage 2: Query Generation
    search_queries: List[SearchQuery] = Field(default_factory=list)

    # Stage 4-5: Content Collection
    social_content: Optional[SocialContentCollection] = None

    # Stage 6: Pain Point Analysis
    pain_point_analysis: Optional[PainPointAnalysisResult] = None

    # Stage 7: Idea Generation
    idea_generation: Optional[IdeaGenerationResult] = None

    # Stage 8: Competitive Analysis
    competitive_analysis: Optional[CompetitiveAnalysisResult] = None

    # Stage 9: Keyword Validation
    keyword_validation: Optional[KeywordValidationResult] = None

    # Stage 10: Final Report
    final_report: Optional[FinalReport] = None

    # Metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    current_stage: int = Field(default=1, description="Current pipeline stage (1-10)")
    errors: List[str] = Field(default_factory=list, description="Errors encountered")

    class Config:
        json_schema_extra = {
            "example": {
                "niche_context": {},
                "search_queries": [],
                "search_results": {},
                "social_content": {},
                "pain_point_analysis": {},
                "idea_generation": {},
                "competitive_analysis": {},
                "keyword_validation": {},
                "final_report": {},
                "started_at": "2025-01-15T10:00:00",
                "completed_at": None,
                "current_stage": 1,
                "errors": [],
            }
        }
