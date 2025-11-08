"""
Pydantic models for data source research (Stage 9.5).
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataSource(BaseModel):
    """Represents a single data source (API, database, provider)."""

    model_config = ConfigDict(extra='forbid')

    provider: str = Field(..., description="Provider name (e.g., 'Adzuna API', 'Indeed', 'RemoteOK')")
    url: Optional[str] = Field(default=None, description="URL to API documentation or provider website")
    access_model: str = Field(
        ...,
        description="Access model: 'free', 'freemium', 'paid', 'application-required', 'restricted', 'partner-only'"
    )
    cost_estimate: Optional[str] = Field(
        default=None,
        description="Cost estimate (e.g., 'Free tier: 1000 calls/month, Paid: $99/mo', '$0.01/request')"
    )
    coverage: Optional[str] = Field(
        default=None,
        description="Data coverage description (e.g., '20M+ jobs, updated daily', 'US & Canada only')"
    )
    update_frequency: Optional[str] = Field(
        default=None,
        description="How often data is refreshed (e.g., 'real-time', 'daily', 'weekly')"
    )
    integration_complexity: str = Field(
        ...,
        description="Integration difficulty: 'low', 'medium', 'high'"
    )
    priority: str = Field(
        ...,
        description="Priority level based on SEO/pain point analysis: 'HIGH', 'MEDIUM', 'LOW'"
    )
    priority_rationale: Optional[str] = Field(
        default=None,
        description="Why this priority (e.g., 'Supports job listings keyword with 12k searches/month')"
    )
    rate_limits: Optional[str] = Field(
        default=None,
        description="API rate limits if known (e.g., '100 requests/min', '10k requests/day')"
    )
    data_quality_notes: Optional[str] = Field(
        default=None,
        description="Notes on data quality, completeness, or reliability"
    )
    fallback_for: Optional[List[str]] = Field(
        default=None,
        description="List of other providers this serves as a fallback for"
    )


class DataPartnership(BaseModel):
    """Represents a potential data partnership or manual data collection need."""

    model_config = ConfigDict(extra='forbid')

    partner_type: str = Field(..., description="Type: 'direct-partnership', 'web-scraping', 'manual-curation', 'user-generated'")
    description: str = Field(..., description="What data would come from this partnership/method")
    effort_estimate: str = Field(..., description="Effort required: 'low', 'medium', 'high'")
    timeline: Optional[str] = Field(default=None, description="Time to establish (e.g., '1-2 months', '3-6 months')")
    notes: Optional[str] = Field(default=None, description="Additional context or considerations")


class DataSourceResearchResult(BaseModel):
    """Complete result of data source research for selected solution."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of solution this research is for")
    primary_data_sources: List[DataSource] = Field(
        ...,
        description="Primary data sources (HIGH priority, best coverage/access)"
    )
    fallback_sources: Optional[List[DataSource]] = Field(
        default=None,
        description="Backup data sources if primary options fail or are restricted"
    )
    data_partnerships_needed: Optional[List[DataPartnership]] = Field(
        default=None,
        description="Data partnerships or alternative collection methods required"
    )
    estimated_monthly_cost: Optional[str] = Field(
        default=None,
        description="Total estimated monthly data costs (e.g., '$250-500/month for 10k users')"
    )
    data_quality_risks: Optional[List[str]] = Field(
        default=None,
        description="Identified risks: data gaps, stale data, coverage limitations, reliability concerns"
    )
    implementation_roadmap: str = Field(
        ...,
        description="Recommended phased approach for data integration (2-3 paragraphs)"
    )
    competitive_data_insights: Optional[str] = Field(
        default=None,
        description="What data sources do competitors use? How does our access compare?"
    )
    seo_aligned_priorities: Optional[str] = Field(
        default=None,
        description="How data source priorities align with high-traffic SEO keywords"
    )
