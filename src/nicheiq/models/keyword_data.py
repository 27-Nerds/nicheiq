"""
Pydantic models for keyword research data (Stage 9).
"""

from enum import Enum
from typing import Literal, Optional

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
            }
        }
    )

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Monthly search volume")
    competition: float = Field(..., ge=0.0, le=1.0, description="Competition level (0-1)")
    competition_index: Optional[float] = Field(
        default=None, description="Competition index score (None = data unavailable from source)"
    )
    cpc: Optional[float] = Field(
        default=None, description="Cost per click in USD (None = data unavailable from source)"
    )
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
    # Note: monthly_searches is preserved in raw dict format during pipeline stages
    # (12-month historical data from DataForSEO), but not typed in this model yet

    # NEW: Competition scale metadata for data quality tracking
    competition_scale: Literal["0-1", "0-100"] = Field(
        default="0-1",
        description=(
            "Scale used for competition field. '0-1' is normalized, '0-100' is raw from DataForSEO. "
            "IMPORTANT: Always normalize to 0-1 before using in calculations."
        )
    )

    # NEW: Tier classification rationale for transparency
    tier: Optional[int] = Field(
        default=None,
        ge=0,
        le=4,
        description="Keyword tier (0=premium, 1=quick_win, 2=strategic, 3=geographic, 4=categorical)"
    )
    tier_rationale: Optional[str] = Field(
        default=None,
        description=(
            "Explanation of tier classification (e.g., 'High volume (4.2k) + Low difficulty (18) = quick win')"
        )
    )

    @field_validator('competition_index', 'cpc', mode='before')
    @classmethod
    def coerce_null_string_to_none(cls, v):
        """Convert 'null' string to None (DataForSEO may return literal 'null' string).

        Note: None is preserved as None to distinguish 'no data available' from '0'.
        """
        if v == "null":
            return None
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
    keywords: list[Keyword] = Field(..., description="Keywords in this cluster")
    total_search_volume: int = Field(
        ..., description="Combined search volume for cluster"
    )
    avg_competition: float = Field(
        ..., ge=0.0, le=1.0,
        description="Average competition level across cluster (0-1 scale, derived from Keyword.competition)"
    )
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
    high_opportunity_keywords: list[Keyword] = Field(
        ..., description="Keywords with high opportunity"
    )
    medium_opportunity_keywords: list[Keyword] = Field(
        ..., description="Keywords with medium opportunity"
    )
    low_opportunity_keywords: list[Keyword] = Field(
        ..., description="Keywords with low opportunity"
    )
    keyword_clusters: list[KeywordCluster] = Field(
        default_factory=list, description="Grouped keyword themes"
    )
    geographic_breakdown: list[GeographicBreakdown] = Field(
        default_factory=list, description="Search volume by country"
    )
    long_tail_opportunities: list[Keyword] = Field(
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
    reports: list[KeywordResearchReport] = Field(
        ..., description="Keyword reports for each solution idea"
    )
    overall_market_size: int = Field(
        ..., description="Total monthly searches across all ideas"
    )
    market_assessment: str = Field(
        ..., description="Overall market size assessment"
    )

# Stage 8.8 - Quick Keyword Validation Models

class KeywordSeedResult(BaseModel):
    """LLM-generated seed keywords for quick validation (Stage 8.8)."""

    model_config = ConfigDict(extra='forbid')

    seeds: list[str] = Field(
        ...,
        min_length=10,
        max_length=10,
        description="Exactly 10 keyword seeds covering diverse search intents and specificity levels"
    )

class KeywordValidationSummary(BaseModel):
    """Quick validation results for a single solution (Stage 8.8)."""

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "solution_name": "ExpatEase Directory",
                "validated_count": 18,
                "total_volume": 14250,
                "avg_competition": 42.5,
                "keyword_demand_score": 0.78,
                "top_keywords": [],
                "top_geographic_keywords": ["expat services spain", "relocation portugal"],
                "demand_signal": "strong",
                "validation_signals": {
                    "has_search_demand": True,
                    "keyword_diversity": True,
                    "high_volume_presence": True,
                    "average_volume_per_keyword": 791.7
                }
            }
        }
    )

    solution_name: str = Field(..., description="Name of the solution")
    validated_count: int = Field(
        ..., ge=0, le=20, description="Number of keywords validated (out of 20)"
    )
    total_volume: int = Field(..., ge=0, description="Total monthly search volume across validated keywords")
    avg_competition: float = Field(
        ..., ge=0.0, le=100.0,
        description="Average competition index across validated keywords (0-100 scale from DataForSEO)"
    )
    # NEW: Explicit documentation of competition scale
    competition_scale: Literal["0-100"] = Field(
        default="0-100",
        description="Scale of avg_competition field (always 0-100 from DataForSEO raw data)"
    )
    keyword_demand_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Hybrid demand score: (0.60 × volume_score) + (0.40 × opportunity_score). "
            "0.80-1.0: Exceptional, 0.65-0.79: Strong, 0.50-0.64: Moderate, 0.35-0.49: Weak, 0.0-0.34: Critical"
        )
    )
    top_keywords: list[dict] = Field(
        default_factory=list,
        description="Top 5 keywords by search volume with metrics (keyword, volume, competition)"
    )
    top_geographic_keywords: list[str] = Field(
        default_factory=list,
        description="Top 3 geographic keywords indicating regional demand"
    )
    demand_signal: str = Field(
        ...,
        description="Overall demand assessment: 'strong' (>5k volume), 'moderate' (2k-5k), 'weak' (<2k)"
    )
    validation_signals: dict = Field(
        ...,
        description=(
            "Binary validation signals: has_search_demand (>1k total), "
            "keyword_diversity (>=5 valid), high_volume_presence (any keyword >500), "
            "average_volume_per_keyword"
        )
    )

# Stage 8.8 - CrewAI Agent-Based Validation Models

class EnrichedKeyword(BaseModel):
    """Keyword with metrics from DataForSEO expansion."""

    model_config = ConfigDict(extra='forbid')

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., ge=0, description="Monthly search volume")
    competition: float = Field(..., ge=0.0, le=1.0, description="Competition level (0-1)")
    cpc: Optional[float] = Field(default=None, description="Cost per click in USD")
    tier: Optional[str] = Field(default=None, description="Keyword tier classification (quick_win, strategic_growth)")
    geography: Optional[str] = Field(default=None, description="Geographic modifier if present")

class KeywordAttemptResult(BaseModel):
    """Result from a single keyword research strategy attempt (e.g., hybrid, competitor)."""

    model_config = ConfigDict(extra='forbid')

    strategy_name: str = Field(..., description="Strategy used (hybrid, competitor, pain_point, category)")
    keywords: list[EnrichedKeyword] = Field(default_factory=list, description="Keywords found by this strategy")
    total_keywords: int = Field(..., ge=0, description="Number of keywords found")
    avg_relevance_score: float = Field(..., ge=0.0, le=1.0, description="Average semantic relevance score")
    quality_flag: str = Field(..., description="SUCCESS if relevance ≥ 0.6 AND keywords ≥ 20, else INSUFFICIENT")
    error_log: Optional[str] = Field(default=None, description="Error details if strategy failed")

class CrewKeywordValidationResult(BaseModel):
    """
    Final keyword validation result from KeywordValidationCrew.

    IMPORTANT: This model MUST maintain backward compatibility with Stage 8.85.
    Use model_dump() to convert to dict format expected by solution refinement logic.

    Note: No custom to_dict() needed - Pydantic's model_dump() handles serialization.
    """

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "solution_name": "ExpatEase Directory",
                "validated_count": 42,
                "total_volume": 18750,
                "avg_competition": 38.5,
                "keyword_demand_score": 0.78,
                "top_keywords": [
                    {"keyword": "expat health insurance", "volume": 3200, "competition": 0.42},
                    {"keyword": "relocation services portugal", "volume": 2100, "competition": 0.38},
                    {"keyword": "expat tax advisor spain", "volume": 1850, "competition": 0.35},
                    {"keyword": "international moving companies", "volume": 1650, "competition": 0.45},
                    {"keyword": "expat community barcelona", "volume": 1420, "competition": 0.32}
                ],
                "top_geographic_keywords": [
                    "expat services spain",
                    "relocation portugal",
                    "expat life barcelona"
                ],
                "demand_signal": "strong",
                "validation_signals": {
                    "has_search_demand": True,
                    "keyword_diversity": True,
                    "high_volume_presence": True,
                    "average_volume_per_keyword": 446.4
                },
                "attempts_made": 1,
                "best_relevance_score": 0.78,
                "accumulated_keywords_count": 42
            }
        }
    )

    solution_name: str = Field(..., description="Name of the solution")
    validated_count: int = Field(..., ge=0, description="Number of validated keywords")
    total_volume: int = Field(..., ge=0, description="Total monthly search volume")
    avg_competition: float = Field(..., ge=0.0, le=100.0, description="Average competition index")
    # NEW: Explicit documentation of competition scale
    competition_scale: Literal["0-100"] = Field(
        default="0-100",
        description="Scale of avg_competition field (always 0-100 from DataForSEO raw data)"
    )
    keyword_demand_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Keyword demand multiplier for solution scoring"
    )
    top_keywords: list[dict] = Field(
        default_factory=list,
        description="Top keywords with metrics (for Stage 8.85 compatibility)"
    )
    top_geographic_keywords: list[str] = Field(
        default_factory=list,
        description="Geographic keywords (for Stage 8.85 compatibility)"
    )
    demand_signal: str = Field(
        ...,
        description="Demand classification: strong | moderate | weak"
    )
    validation_signals: dict = Field(
        ...,
        description="Binary validation flags for Stage 8.85"
    )

    # New fields specific to crew-based approach
    attempts_made: int = Field(..., ge=1, le=4, description="Number of strategy attempts")
    best_relevance_score: float = Field(..., ge=0.0, le=1.0, description="Best relevance score achieved")
    accumulated_keywords_count: Optional[int] = Field(
        default=None,
        description="Total keywords accumulated across attempts"
    )
