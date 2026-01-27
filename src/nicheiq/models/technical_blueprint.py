"""
Pydantic models for Technical Blueprint (Site Structure & User Flows).

Stage 10.5: LLM-generated personalized site architecture and user journey maps.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Site Structure Models
# =============================================================================


class SitePage(BaseModel):
    """Single page in site structure."""

    model_config = ConfigDict(extra="ignore")

    page_name: str = Field(..., description="Human-readable page name")
    url_pattern: str = Field(
        ..., description="URL pattern using [param] syntax (e.g., /compare/[product-a]-vs-[product-b])"
    )
    page_type: str = Field(
        ..., description="Page type: static | programmatic | dynamic"
    )
    purpose: str = Field(..., description="1-sentence purpose of this page")
    estimated_count: Optional[int] = Field(
        default=None, description="Estimated page count (for programmatic pages)"
    )
    priority: str = Field(
        default="P1", description="Priority: P0 (MVP must-have) | P1 (soon after) | P2 (later)"
    )


class SiteSection(BaseModel):
    """Section grouping pages by purpose."""

    model_config = ConfigDict(extra="ignore")

    section_name: str = Field(..., description="Section name (e.g., 'Core Content', 'User Tools')")
    description: str = Field(..., description="Brief description of section purpose")
    pages: list[SitePage] = Field(..., description="Pages within this section")


class SiteStructure(BaseModel):
    """Complete site architecture for the solution."""

    model_config = ConfigDict(extra="ignore")

    overview: str = Field(
        ..., description="1-2 sentence architecture philosophy for this site"
    )
    sections: list[SiteSection] = Field(
        ..., min_length=2, max_length=5, description="2-5 logical sections with pages"
    )
    total_static_pages: int = Field(
        ..., description="Count of hand-crafted static pages"
    )
    total_programmatic_pages: int = Field(
        ..., description="Count of auto-generated programmatic pages"
    )
    mvp_page_count: int = Field(
        ..., description="Pages needed for MVP launch (P0 pages only)"
    )
    tech_stack_recommendation: Optional[str] = Field(
        default=None,
        description="Suggested tech stack appropriate for this solution type",
    )


# =============================================================================
# User Flows Models
# =============================================================================


class UserFlowStep(BaseModel):
    """Single step in a user flow."""

    model_config = ConfigDict(extra="ignore")

    step_number: int = Field(..., description="Step sequence number (1-based)")
    action: str = Field(..., description="What the user does at this step")
    page: str = Field(..., description="Which page this step happens on")
    system_response: Optional[str] = Field(
        default=None, description="What the system shows or does in response"
    )


class UserFlow(BaseModel):
    """Complete user journey for a persona."""

    model_config = ConfigDict(extra="ignore")

    flow_name: str = Field(
        ..., description="Descriptive name (e.g., 'Organic Comparison Discovery')"
    )
    persona: str = Field(..., description="Target persona from solution's target_personas")
    goal: str = Field(..., description="What the user wants to accomplish")
    entry_point: str = Field(
        ..., description="How they arrive (Google search, direct URL, referral, etc.)"
    )
    steps: list[UserFlowStep] = Field(
        ..., min_length=3, max_length=7, description="3-7 sequential steps in the journey"
    )
    conversion_point: str = Field(
        ..., description="Where and how the user converts"
    )
    success_metric: str = Field(
        ..., description="Measurable KPI for this flow (e.g., 'signup rate', 'time to conversion')"
    )


class UserFlowsSection(BaseModel):
    """All user flows with cross-flow insight."""

    model_config = ConfigDict(extra="ignore")

    flows: list[UserFlow] = Field(
        ..., min_length=1, max_length=3, description="1-3 user journey flows"
    )
    key_insight: Optional[str] = Field(
        default=None, description="Cross-flow observation or strategic insight"
    )
