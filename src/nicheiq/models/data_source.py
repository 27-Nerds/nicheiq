"""
Pydantic models for data source research (Stage 9.5).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    fallback_for: Optional[list[str]] = Field(
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

class DataQualityMetrics(BaseModel):
    """5D Data Quality Matrix scores for a data source."""

    model_config = ConfigDict(extra='forbid')

    coverage_score: str = Field(..., description="Coverage % or description (e.g., '80% market coverage')")
    freshness: str = Field(..., description="Update frequency: real-time, hourly, daily, weekly, monthly")
    integration_complexity: str = Field(..., description="LOW, MEDIUM, or HIGH")
    cost_viability: str = Field(..., description="Cost assessment: FREE, LOW, MEDIUM, HIGH")
    quality_assessment: str = Field(..., description="Accuracy/reliability notes")

class EvaluatedDataSource(BaseModel):
    """Data source with full evaluation from Task 2."""

    model_config = ConfigDict(extra='forbid')

    provider: str = Field(..., description="Provider name")
    url: Optional[str] = Field(default=None, description="API documentation URL")
    priority: str = Field(..., description="HIGH, MEDIUM, or LOW")
    priority_rationale: str = Field(
        ..., description="Why this priority (SEO keywords, pain points, competitive advantage)"
    )
    quality_metrics: DataQualityMetrics = Field(..., description="5D quality matrix scores")
    mvp_cost_estimate: Optional[str] = Field(
        default=None, description="Cost at 1k-10k users"
    )
    scale_cost_estimate: Optional[str] = Field(
        default=None, description="Cost at 100k+ users"
    )
    identified_risks: list[str] = Field(
        default_factory=list, description="2-4 specific risks"
    )
    mitigation_strategies: Optional[list[str]] = Field(
        default=None, description="How to mitigate risks"
    )

class SourceEvaluationReport(BaseModel):
    """Complete evaluation output from Task 2."""

    model_config = ConfigDict(extra='forbid')

    high_priority_sources: list[EvaluatedDataSource] = Field(
        ..., min_length=1, description="1-3 HIGH priority sources (minimum 1)"
    )
    medium_priority_sources: list[EvaluatedDataSource] = Field(
        ..., description="2-4 MEDIUM priority sources"
    )
    low_priority_sources: list[EvaluatedDataSource] = Field(
        ..., description="Remaining sources"
    )
    overall_data_quality_risk: str = Field(
        ..., description="Overall risk assessment narrative"
    )
    critical_blockers: list[str] = Field(
        default_factory=list, description="Risks that could block launch"
    )
    evaluation_summary: str = Field(
        ..., description="2-3 sentence summary of evaluation findings"
    )

    @field_validator('high_priority_sources')
    @classmethod
    def validate_sources(cls, v: list[EvaluatedDataSource]) -> list[EvaluatedDataSource]:
        """Validate that each high-priority source has required fields."""
        for source in v:
            if source.url and not source.url.startswith('http'):
                raise ValueError(f"Invalid URL for source '{source.provider}': {source.url}")
            if not source.quality_metrics:
                raise ValueError(f"Missing quality_metrics for source: {source.provider}")
        return v

class RoadmapPhase(BaseModel):
    """Structured phase in implementation roadmap."""

    model_config = ConfigDict(extra='forbid')

    phase_number: int = Field(..., description="1, 2, or 3")
    phase_name: str = Field(..., description="MVP, Growth, or Scale")
    timeline: str = Field(..., description="e.g., 'Months 1-3'")
    goal: str = Field(..., description="What this phase achieves")
    data_sources: list[str] = Field(..., description="Provider names for this phase")
    estimated_monthly_cost: str = Field(
        ..., description="Cost range (e.g., '$100-200')"
    )
    key_milestones: list[str] = Field(
        default_factory=list, description="Success criteria"
    )
    fallback_strategies: list[str] = Field(
        default_factory=list, description="What to do if sources fail"
    )

class DataImplementationPlan(BaseModel):
    """Task 3 output: Implementation planning data (ONLY new fields added by Task 3).

    This intermediate model contains ONLY the implementation planning fields.
    Python will merge this with SourceEvaluationReport to create DataSourceResearchResult.
    """

    model_config = ConfigDict(extra='forbid')

    implementation_phases: list[RoadmapPhase] = Field(
        ...,
        min_length=1,
        description="3-phase structured roadmap (MVP/Growth/Scale) with goals, milestones, costs, and fallbacks (minimum 1)"
    )
    data_partnerships_needed: Optional[list[DataPartnership]] = Field(
        default=None,
        description="Data partnerships or alternative collection methods required"
    )
    estimated_monthly_cost: str = Field(
        ...,
        description="Total estimated monthly data costs (e.g., '$250-500/month for 10k users')"
    )
    implementation_roadmap: str = Field(
        ...,
        min_length=50,
        description="Recommended phased approach for data integration (2-3 paragraphs, minimum 50 chars)"
    )
    competitive_data_insights: Optional[str] = Field(
        default=None,
        description="What data sources do competitors use? How does our access compare?"
    )
    seo_aligned_priorities: Optional[str] = Field(
        default=None,
        description="How data source priorities align with high-traffic SEO keywords"
    )

class DataSourceResearchResult(BaseModel):
    """Complete result of data source research for selected solution."""

    model_config = ConfigDict(extra='forbid')

    solution_name: str = Field(..., description="Name of solution this research is for")
    primary_data_sources: list[DataSource] = Field(
        ...,
        description="Primary data sources (HIGH priority, best coverage/access)"
    )
    fallback_sources: Optional[list[DataSource]] = Field(
        default=None,
        description="Backup data sources if primary options fail or are restricted"
    )
    source_evaluation: Optional[SourceEvaluationReport] = Field(
        default=None,
        description="Detailed evaluation from Task 2 (priorities, quality matrix, risks)"
    )
    implementation_phases: Optional[list[RoadmapPhase]] = Field(
        default=None,
        description="3-phase structured roadmap with goals, milestones, costs, and fallbacks"
    )
    data_partnerships_needed: Optional[list[DataPartnership]] = Field(
        default=None,
        description="Data partnerships or alternative collection methods required"
    )
    estimated_monthly_cost: Optional[str] = Field(
        default=None,
        description="Total estimated monthly data costs (e.g., '$250-500/month for 10k users')"
    )
    data_quality_risks: Optional[list[str]] = Field(
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
