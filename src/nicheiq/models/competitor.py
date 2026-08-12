"""
Pydantic models for competitive analysis (Stage 8).
"""

from datetime import datetime
from enum import Enum
from ipaddress import ip_address
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CompetitorType(str, Enum):
    """Type of competitor."""

    DIRECT = "direct"
    PARTIAL = "partial"
    INDIRECT = "indirect"

class MarketSaturation(str, Enum):
    """Level of market saturation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class Competitor(BaseModel):
    """Represents a competitive product or service."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Name of the competitor")
    url: Optional[str] = Field(default=None, description="Website URL")
    competitor_type: CompetitorType = Field(..., description="Type of competitor")
    description: str = Field(..., description="What this competitor offers")
    key_features: list[str] = Field(
        ...,
        description="All significant features from the competitor's product/features pages - be comprehensive for comparison (typically 4-8 features)"
    )
    pricing_model: Optional[str] = Field(
        default=None, description="Pricing model if available"
    )
    strengths: Optional[list[str]] = Field(default=None, description="Competitor strengths")
    weaknesses: Optional[list[str]] = Field(default=None, description="Competitor weaknesses")
    # Catalog rebuild (Phase 5.4): market position relative to the niche.
    # Distinct from `competitor_type` (which describes feature overlap with our
    # solution) — `position` describes the competitor's standing in the market.
    # Optional for back-compat; legacy reports have None.
    #   leader     = dominant brand recognition or market share
    #   challenger = mid-market with focused traction, scaling
    #   niche      = vertical-specific or limited footprint
    position: Optional[str] = Field(
        default=None,
        description="Market position: leader | challenger | niche",
    )


class VerifiedPricingProvenance(BaseModel):
    """Code-owned output of a bounded exact-page pricing verifier.

    CompetitiveLandscape is LLM-authored, so its URL and pricing prose can never create
    this record. A verifier must fetch the exact safe public URL and confirm that
    ``retrieved_quote`` occurs in the retrieved content before constructing it.
    """

    model_config = ConfigDict(extra='forbid')

    candidate_idea_id: str = Field(..., min_length=1)
    candidate_idea_revision: int = Field(..., ge=1)
    route: Literal[
        "lead_generation", "sponsorship", "paid_upgrade_funnel", "affiliate"
    ]
    source_name: str = Field(..., min_length=1)
    source_url: str
    retrieved_quote: str = Field(..., min_length=1)
    retrieved_at: datetime
    verification_marker: Literal["exact_quote_in_fetched_public_content"]
    value_low: Optional[int] = Field(default=None, ge=0)
    value_high: Optional[int] = Field(default=None, ge=0)
    billing_basis: Literal[
        "per_lead", "per_sponsored_listing_month", "per_paid_upgrade_month",
        "affiliate_program",
    ]
    commission_pct_low: Optional[float] = Field(default=None, ge=0, le=100)
    commission_pct_high: Optional[float] = Field(default=None, ge=0, le=100)

    @field_validator("source_url")
    @classmethod
    def _require_public_https_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or host == "localhost"
            or host.endswith(".localhost")
        ):
            raise ValueError("source_url must be an exact public HTTPS URL")
        try:
            host_address = ip_address(host)
        except ValueError:
            host_address = None
        if host_address is not None and not host_address.is_global:
            raise ValueError("source_url must be an exact public HTTPS URL")
        return value.strip()

    @model_validator(mode="after")
    def _validate_range(self):
        if self.value_low is not None and self.value_high is not None:
            if self.value_high < self.value_low:
                raise ValueError("value_high must be greater than or equal to value_low")
        return self

class CompetitiveLandscape(BaseModel):
    """Complete competitive analysis for a solution idea."""

    model_config = ConfigDict(extra='ignore')

    solution_name: str = Field(..., description="Name of the solution being analyzed")
    candidate_idea_id: Optional[str] = Field(
        default=None,
        description="Code-owned durable identity of the exact candidate analyzed",
    )
    candidate_idea_revision: Optional[int] = Field(
        default=None,
        ge=1,
        description="Code-owned immutable revision of the exact candidate analyzed",
    )
    competitors: list[Competitor] = Field(
        default_factory=list,
        description="Competitors found (may be empty for emerging niches)"
    )
    market_gaps: list[str] = Field(
        ..., min_length=2, description="ALL unmet needs, underserved areas, user complaints, and missing features - comprehensive list"
    )
    differentiation_opportunities: list[str] = Field(
        ..., description="ALL ways this solution can differentiate from competitors - comprehensive list"
    )
    competitive_intensity: str = Field(
        ..., description="Assessment of competitive intensity (Low/Medium/High) with justification"
    )
    recommended_positioning: str = Field(
        ..., description="Recommended market positioning and differentiation strategy"
    )
    pricing_insights: str = Field(
        ..., description="Market pricing analysis and recommended pricing approach"
    )
    # Stamped by the flow when the deterministic on-niche check fails twice
    # (utils/validation/competitor_relevance.py). Downgrade-only: the landscape is kept
    # verbatim, but every count/saturation/gap claim derived from it is unverified.
    # None on every healthy landscape and on all legacy reports.
    off_niche_caveat: Optional[str] = Field(
        default=None,
        description="Set when the returned competitors share no vocabulary with the niche",
    )

class CompetitiveAnalysisResult(BaseModel):
    """Complete result of competitive analysis for all solution ideas."""

    model_config = ConfigDict(extra='ignore')

    solution_landscapes: list[CompetitiveLandscape] = Field(
        ..., min_length=1, description="Competitive landscape for each solution idea (at least 1)"
    )
    top_opportunities: list[str] = Field(
        ..., description="3-5 highest-potential differentiation opportunities across all solutions"
    )
    strategic_recommendations: str = Field(
        ..., min_length=50, description="Executive summary with strategic insights (minimum 50 chars)"
    )


def find_landscape_for_solution(
    competitive_analysis: CompetitiveAnalysisResult | None,
    solution_name: str | None,
) -> CompetitiveLandscape | None:
    """Find the competitive landscape for a specific solution by name.

    Case-insensitive, stripped matching. Falls back to first landscape
    if no exact match found. Returns None only if no landscapes exist.

    Args:
        competitive_analysis: Full competitive analysis result (may be None).
        solution_name: Name of the solution to look up (may be None).

    Returns:
        Matching CompetitiveLandscape, first landscape as fallback, or None.
    """
    if not competitive_analysis or not competitive_analysis.solution_landscapes:
        return None

    if solution_name:
        needle = solution_name.strip().lower()
        for landscape in competitive_analysis.solution_landscapes:
            if landscape.solution_name.strip().lower() == needle:
                return landscape

    # Fallback: return first landscape
    return competitive_analysis.solution_landscapes[0]
