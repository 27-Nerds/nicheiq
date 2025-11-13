"""
Pydantic models for keyword research data (Stage 9).
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MonthlySearchVolume(BaseModel):
    """Monthly search volume entry."""

    model_config = ConfigDict(extra='forbid')

    month: str = Field(..., description="Month identifier (e.g., '2025-01')")
    volume: int = Field(..., description="Search volume for this month")


class KeywordIntent(str, Enum):
    """Type of search intent."""

    COMMERCIAL = "commercial"
    INFORMATIONAL = "informational"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"


class OpportunityLevel(str, Enum):
    """Keyword opportunity classification."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Keyword(BaseModel):
    """Represents a single keyword with its metrics."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "keyword": "freelancer marketplace for rust developers",
                "search_volume": 320,
                "competition": 0.45,
                "competition_index": 32.0,
                "cpc": 2.50,
                "keyword_difficulty": 42.0,
                "search_intent": "commercial",
                "opportunity_level": "high",
                "trend": "rising",
                "monthly_searches": {"2025-01": 280, "2025-02": 310, "2025-03": 320},
            }
        }
    )

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Monthly search volume")
    competition: float = Field(..., ge=0.0, le=1.0, description="Competition level (0-1)")
    competition_index: float = Field(
        default=0.0, description="Competition index score (defaults to 0 if unavailable)"
    )
    cpc: float = Field(default=0.0, description="Cost per click in USD (defaults to 0 if unavailable)")
    keyword_difficulty: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Keyword difficulty score (0-100)"
    )
    search_intent: Optional[KeywordIntent] = Field(
        default=None, description="Classified search intent"
    )
    opportunity_level: OpportunityLevel = Field(
        ..., description="Opportunity classification"
    )
    trend: Optional[str] = Field(
        default=None, description="Trend direction (rising, stable, declining)"
    )
    monthly_searches: List[MonthlySearchVolume] = Field(
        default_factory=list, description="Historical monthly search volumes (defaults to empty list if unavailable)"
    )

    @field_validator('competition_index', 'cpc', mode='before')
    @classmethod
    def coerce_numeric_none_to_zero(cls, v):
        """Coerce None to 0 for numeric fields (DataForSEO may return null)."""
        if v is None or v == "null":
            return 0.0
        return v

    @field_validator('monthly_searches', mode='before')
    @classmethod
    def coerce_monthly_searches_none_to_empty_list(cls, v):
        """Coerce None to [] for monthly_searches (DataForSEO may return null)."""
        if v is None or v == "null":
            return []
        return v


class GeographicBreakdown(BaseModel):
    """Search volume breakdown by geography."""

    model_config = ConfigDict(extra='forbid')

    country: str = Field(..., description="Country name")
    country_code: str = Field(..., description="ISO country code")
    search_volume: int = Field(..., description="Search volume in this country")
    percentage: float = Field(..., description="Percentage of total search volume")


class KeywordCluster(BaseModel):
    """Group of related keywords."""

    model_config = ConfigDict(extra='forbid')

    cluster_name: str = Field(..., description="Name/theme of this keyword cluster")
    keywords: List[Keyword] = Field(..., description="Keywords in this cluster")
    total_search_volume: int = Field(
        ..., description="Combined search volume for cluster"
    )
    avg_competition: float = Field(..., description="Average competition across cluster")
    opportunity_assessment: str = Field(
        ..., description="Assessment of opportunity for this cluster"
    )


class KeywordResearchReport(BaseModel):
    """Complete keyword research report for a solution idea."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "solution_idea": "NicheHire",
                "total_keywords_analyzed": 45,
                "high_opportunity_keywords": [],
                "medium_opportunity_keywords": [],
                "low_opportunity_keywords": [],
                "keyword_clusters": [],
                "geographic_breakdown": [],
                "long_tail_opportunities": [],
                "seasonal_patterns": "Stable search volume throughout the year",
                "total_addressable_searches": 12500,
                "demand_validation": "Strong validated demand with 12.5k monthly searches",
            }
        }
    )

    solution_idea: str = Field(..., description="Name of the solution idea")
    total_keywords_analyzed: int = Field(..., description="Total keywords analyzed")
    high_opportunity_keywords: List[Keyword] = Field(
        ..., description="Keywords with high opportunity"
    )
    medium_opportunity_keywords: List[Keyword] = Field(
        ..., description="Keywords with medium opportunity"
    )
    low_opportunity_keywords: List[Keyword] = Field(
        ..., description="Keywords with low opportunity"
    )
    keyword_clusters: List[KeywordCluster] = Field(
        default_factory=list, description="Grouped keyword themes"
    )
    geographic_breakdown: List[GeographicBreakdown] = Field(
        default_factory=list, description="Search volume by country"
    )
    long_tail_opportunities: List[Keyword] = Field(
        default_factory=list, description="Long-tail keyword opportunities"
    )
    seasonal_patterns: Optional[str] = Field(
        default=None, description="Analysis of seasonal search patterns"
    )
    total_addressable_searches: int = Field(
        ..., description="Total monthly searches across all keywords"
    )
    demand_validation: str = Field(
        ..., description="Overall assessment of search demand"
    )


class KeywordValidationResult(BaseModel):
    """Complete keyword validation for all solution ideas."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "niche": "SaaS development tools",
                "reports": [],
                "overall_market_size": 45000,
                "market_assessment": "Significant market with 45k monthly searches...",
            }
        }
    )

    niche: str = Field(..., description="The niche being analyzed")
    reports: List[KeywordResearchReport] = Field(
        ..., description="Keyword reports for each solution idea"
    )
    overall_market_size: int = Field(
        ..., description="Total monthly searches across all ideas"
    )
    market_assessment: str = Field(
        ..., description="Overall market size assessment"
    )
