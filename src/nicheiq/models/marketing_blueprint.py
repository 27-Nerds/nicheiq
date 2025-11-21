"""
Marketing Blueprint Models for NicheIQ Report

Provides actionable Go-to-Market strategy with ICP, marketing channels,
messaging, and content angles for immediate execution.
"""

from pydantic import BaseModel, ConfigDict, Field


class IdealCustomerProfile(BaseModel):
    """Detailed persona of the ideal customer."""

    model_config = ConfigDict(extra='forbid')

    persona_name: str = Field(
        description="Persona name (e.g., 'Startup Founder Sarah', 'Digital Nomad Dan')"
    )
    demographics: str = Field(
        description="Age range, location, occupation (1-2 sentences)"
    )
    psychographics: str = Field(
        description="Values, motivations, behaviors (2-3 sentences)"
    )
    pain_points: list[str] = Field(
        description="Top 3-5 pain points this persona experiences"
    )
    goals: list[str] = Field(
        description="Top 3-5 goals this persona is trying to achieve"
    )
    buying_triggers: str = Field(
        description="What causes them to search for a solution (1-2 sentences)"
    )
    decision_criteria: str = Field(
        description="What they evaluate when choosing a solution (1-2 sentences)"
    )

class MarketingChannel(BaseModel):
    """A specific marketing channel with strategy and rationale."""

    model_config = ConfigDict(extra='forbid')

    channel_name: str = Field(
        description="Channel name (e.g., 'Reddit r/digitalnomad', 'Twitter #buildinpublic', 'SEO Blog')"
    )
    channel_type: str = Field(
        description="Type: Social, SEO, Paid, Community, Content, Email, etc."
    )
    target_audience_size: str | None = Field(
        default=None,
        description="Estimated audience size (e.g., '50K subreddit members', '2M monthly searches')"
    )
    rationale: str = Field(
        description="Why this channel is recommended (2-3 sentences with evidence from research)"
    )
    strategy: str = Field(
        description="How to approach this channel (2-3 tactical sentences)"
    )
    priority: str = Field(
        description="Priority: High, Medium, Low"
    )

class ContentAngle(BaseModel):
    """A specific content idea addressing pain points."""

    model_config = ConfigDict(extra='forbid')

    title: str = Field(
        description="Content title/headline (optimized for engagement)"
    )
    content_type: str = Field(
        description="Type: Blog Post, Reddit Thread, Twitter Thread, YouTube Video, Guide, etc."
    )
    pain_point_addressed: str = Field(
        description="Which pain point this content addresses"
    )
    hook: str = Field(
        description="Opening hook to grab attention (1-2 sentences)"
    )
    key_points: list[str] = Field(
        description="3-5 key points or sections to cover"
    )
    target_channel: str = Field(
        description="Where to publish this content"
    )

class First30DaysPlaybook(BaseModel):
    """Concrete action items for the first 30 days."""

    model_config = ConfigDict(extra='forbid')

    week_1_actions: list[str] = Field(
        description="3-5 specific actions for week 1"
    )
    week_2_actions: list[str] = Field(
        description="3-5 specific actions for week 2"
    )
    week_3_actions: list[str] = Field(
        description="3-5 specific actions for week 3"
    )
    week_4_actions: list[str] = Field(
        description="3-5 specific actions for week 4"
    )
    success_metrics: list[str] = Field(
        description="3-5 metrics to track during first 30 days"
    )

class GTMBlueprint(BaseModel):
    """
    Comprehensive Go-to-Market blueprint for immediate execution.

    Transforms research insights into actionable marketing strategy with
    customer personas, channel strategy, messaging, and content plan.
    """

    model_config = ConfigDict(extra='forbid')

    ideal_customer_profile: IdealCustomerProfile = Field(
        description="Detailed ICP derived from user segments and pain point analysis"
    )

    core_marketing_message: str = Field(
        description="One-liner value proposition for marketing materials (10-15 words, emotionally resonant)"
    )

    message_framework: str = Field(
        description="Before-After-Bridge framework: problem state, desired state, solution bridge (3 sentences)"
    )

    recommended_channels: list[MarketingChannel] = Field(
        description="Top 2-3 marketing channels with strategy and rationale"
    )

    example_content_angles: list[ContentAngle] = Field(
        description="3-5 ready-to-execute content ideas addressing pain points"
    )

    first_30_days_playbook: First30DaysPlaybook = Field(
        description="Week-by-week action plan for first month"
    )

    budget_estimate: str | None = Field(
        default=None,
        description="Estimated monthly marketing budget for first 3 months (optional)"
    )

# Model for LLM-generated marketing components (hybrid approach)
class MarketingNarrative(BaseModel):
    """
    LLM-generated marketing narrative components.

    Generated using minimal LLM synthesis while data extraction is Python-based.
    """

    model_config = ConfigDict(extra='forbid')

    core_marketing_message: str = Field(
        description="One-liner value proposition (10-15 words)"
    )

    message_framework: str = Field(
        description="Before-After-Bridge framework (3 sentences)"
    )

    content_angles: list[ContentAngle] = Field(
        description="3-5 content ideas with hooks and key points"
    )
