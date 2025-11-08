"""
Pydantic models for SEO strategy (Stage 10 enhancement).

These models capture structured keyword data and narrative strategy sections
that combine into the comprehensive SEO section of the final report.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_keyword(keyword: str, field_name: str = "keyword") -> bool:
    """
    Validate keyword meets API constraints and quality standards.

    Requirements:
    - Maximum 80 characters (DataForSEO API limit)
    - Maximum 10 words
    - No placeholder syntax: [brackets], {braces}, <angles>

    Returns:
        True if valid, False if invalid (logs warning)
    """
    # Check for placeholder syntax
    if any(char in keyword for char in ['[', ']', '{', '}', '<', '>']):
        logger.warning(
            f"Skipping {field_name} with placeholder syntax: '{keyword}'. "
            "Use concrete terms instead."
        )
        return False

    # Check character limit
    if len(keyword) > 80:
        logger.warning(
            f"Skipping {field_name} exceeding 80 chars ({len(keyword)}): '{keyword[:50]}...'"
        )
        return False

    # Check word count
    word_count = len(keyword.split())
    if word_count > 10:
        logger.warning(
            f"Skipping {field_name} exceeding 10 words ({word_count}): '{keyword[:50]}...'"
        )
        return False

    return True


class ContentType(str, Enum):
    """Type of content piece for keyword targeting."""

    LANDING_PAGE = "landing_page"
    BLOG_POST = "blog_post"
    GUIDE = "guide"
    TUTORIAL = "tutorial"
    CASE_STUDY = "case_study"
    COMPARISON = "comparison"
    FAQ = "faq"
    DOCUMENTATION = "documentation"


class MonthlySearchData(BaseModel):
    """Single month's search volume data from DataForSEO."""

    model_config = ConfigDict(extra='forbid')

    year: int = Field(..., description="Year of the search data")
    month: int = Field(..., description="Month number (1-12)")
    search_volume: int = Field(..., description="Search volume for this month")


class TieredKeyword(BaseModel):
    """
    Individual keyword with targeting strategy for report tables.

    Matches the table format from translation services example:
    | Keyword | Search Volume | Competition | Opportunity Score | Strategy |
    """

    model_config = ConfigDict(extra='forbid')

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO (single value)")
    monthly_searches: Optional[List[MonthlySearchData]] = Field(
        default=None,
        description="Historical 12-month search volume data from DataForSEO (array of {year, month, search_volume} objects). For reference only - do not sum or use for primary volume metric."
    )
    competition: str = Field(
        ..., description="Competition level (e.g., 'LOW (30)', 'MEDIUM (53)', 'VERY LOW (5)')"
    )
    opportunity_score: Optional[int] = Field(
        default=None, description="Calculated opportunity score (volume/competition or similar metric)"
    )
    strategy: str = Field(
        ..., description="Brief targeting strategy (1-2 sentences)"
    )
    intent: Optional[str] = Field(
        default=None, description="Search intent (e.g., 'High conversion intent', 'Informational')"
    )

    @field_validator('keyword')
    @classmethod
    def validate_keyword_constraints(cls, v: str) -> str:
        """Validate keyword and log warning if constraints not met (validation happens elsewhere)."""
        return v.strip()


class GeographicKeywordEntry(BaseModel):
    """Individual geographic keyword entry."""

    model_config = ConfigDict(extra='forbid')

    city: str = Field(..., description="City or location name")
    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO")
    notes: Optional[str] = Field(default=None, description="Optional notes about this keyword")

    @field_validator('keyword')
    @classmethod
    def validate_keyword_constraints(cls, v: str) -> str:
        """Strip whitespace (validation happens elsewhere to allow filtering)."""
        return v.strip()


class CategoryKeywordEntry(BaseModel):
    """Individual category keyword entry."""

    model_config = ConfigDict(extra='forbid')

    keyword_name: str = Field(..., description="Keyword name (document type, service name, etc.)")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO")
    competition: Optional[str] = Field(default=None, description="Competition level")
    cpc: Optional[str] = Field(default=None, description="Cost per click estimate")

    @field_validator('keyword_name')
    @classmethod
    def validate_keyword_constraints(cls, v: str) -> str:
        """Strip whitespace (validation happens elsewhere to allow filtering)."""
        return v.strip()


class GeographicKeywordGroup(BaseModel):
    """
    Geographic market keyword group.

    Example: Spanish-Speaking Markets, UK Markets, etc.
    """

    model_config = ConfigDict(extra='forbid')

    region_name: str = Field(..., description="Region/country name (e.g., 'Spanish-Speaking Markets')")
    total_volume: int = Field(..., description="Combined monthly search volume")
    competition_level: str = Field(..., description="Overall competition assessment")
    keywords: List[GeographicKeywordEntry] = Field(
        ..., description="List of geographic keyword entries"
    )
    strategy_notes: str = Field(
        ..., description="Strategic notes for this geographic market (1-3 sentences)"
    )


class CategoryKeywordGroup(BaseModel):
    """
    Category-based keyword group (document types, service categories, etc.).

    Example: Education Documents, Immigration Documents, etc.
    """

    model_config = ConfigDict(extra='forbid')

    category_name: str = Field(..., description="Category name (e.g., 'Education Documents')")
    total_volume: int = Field(..., description="Combined monthly search volume")
    keywords: List[CategoryKeywordEntry] = Field(
        ..., description="List of category keyword entries"
    )
    strategy_recommendation: str = Field(
        ..., description="Strategic recommendation for this category (2-4 sentences)"
    )


class TopicCluster(BaseModel):
    """Content pillar with grouped keywords."""

    model_config = ConfigDict(extra='forbid')

    cluster_name: str = Field(..., description="Name of the content cluster/pillar")
    primary_keyword: str = Field(..., description="Main keyword for this cluster")
    supporting_keywords: List[str] = Field(
        ..., description="Related keywords (5-15)"
    )
    total_monthly_volume: int = Field(
        ..., description="Combined search volume for all keywords in cluster"
    )
    content_recommendation: str = Field(
        ..., description="What to create for this cluster (2-4 sentences)"
    )
    estimated_traffic_potential: str = Field(
        ..., description="Monthly traffic estimate (e.g., '500-1000 visits')"
    )
    priority: int = Field(
        ..., ge=1, le=5, description="Priority level (1=highest, 5=lowest)"
    )

    @field_validator('primary_keyword')
    @classmethod
    def validate_primary_keyword(cls, v: str) -> str:
        """Strip whitespace (validation happens elsewhere to allow filtering)."""
        return v.strip()

    @field_validator('supporting_keywords')
    @classmethod
    def validate_supporting_keywords(cls, v: List[str]) -> List[str]:
        """Strip whitespace and filter out invalid keywords."""
        validated = []
        for keyword in v:
            keyword = keyword.strip()
            if validate_keyword(keyword, "supporting_keyword"):
                validated.append(keyword)
        return validated


class KeywordBasedPageType(BaseModel):
    """Page type definition derived from keyword clusters and search intent."""

    model_config = ConfigDict(extra='forbid')

    page_type_name: str = Field(
        ..., description="Name of page type based on keyword intent (e.g., 'Problem Solution Pages', 'Geographic Landing Pages')"
    )
    url_pattern: str = Field(
        ..., description="URL pattern optimized for target keywords (e.g., '/tools/{problem-keyword}/', '/city/{city-name}/')"
    )
    target_keyword_cluster: str = Field(
        ..., description="Which keyword tier/cluster this page type targets (e.g., 'Tier 1 quick wins', 'Geographic group: Spanish markets')"
    )
    example_keywords: List[str] = Field(
        ..., min_items=2, max_items=5, description="2-5 example target keywords this page type addresses"
    )
    primary_intent: str = Field(
        ..., description="Primary search intent: 'commercial', 'informational', 'navigational', 'transactional'"
    )
    estimated_page_count: int = Field(
        ..., description="Number of pages needed based on keyword volume (e.g., 12 cities = 12 pages)"
    )
    priority: str = Field(
        ..., description="Launch priority based on keyword opportunity: 'P0' (Tier 1 keywords), 'P1' (Tier 2), 'P2' (Tier 3-4)"
    )
    required_schema: Optional[List[str]] = Field(
        default=None, description="Schema.org types for this page type based on content and intent"
    )
    seo_optimization_notes: str = Field(
        ..., description="SEO-specific guidance: title patterns, header structure, internal linking strategy for these pages"
    )


class SectionKeywordMapping(BaseModel):
    """Mapping of a site section to its keyword cluster."""

    model_config = ConfigDict(extra='forbid')

    section_path: str = Field(..., description="URL path of the section (e.g., '/tools/', '/compare/')")
    keyword_cluster: str = Field(..., description="Keyword cluster description (e.g., 'Tier 1 problem-solving keywords')")


class KeywordDrivenSiteArchitecture(BaseModel):
    """Site structure organized by keyword clusters and search intent patterns."""

    model_config = ConfigDict(extra='forbid')

    url_hierarchy_diagram: Optional[str] = Field(
        default=None, description="ASCII/markdown hierarchy showing how keyword clusters map to site sections"
    )
    section_keyword_mapping: Optional[List[SectionKeywordMapping]] = Field(
        default=None, description="Mapping of top-level sections to keyword clusters (e.g., {'/tools/': 'Tier 1 problem-solving keywords', '/compare/': 'Competitor alternative keywords'})"
    )
    total_pages_from_keywords: Optional[int] = Field(
        default=None, description="Total page count derived from keyword opportunities (geographic variations × category variations × core pages)"
    )
    keyword_coverage_explanation: Optional[str] = Field(
        default=None, description="Explanation of how site structure ensures all high-priority keywords have dedicated landing pages (2-3 sentences)"
    )


class SEOStrategyReport(BaseModel):
    """
    Comprehensive SEO strategy report matching translation services example.

    This model captures both structured data (keywords, volumes, tiers) and
    narrative markdown sections for the final report's SEO section.
    """

    model_config = ConfigDict(extra='forbid')

    # ========================================
    # METADATA
    # ========================================
    seed_keywords_generated: Optional[List[str]] = Field(
        default=None,
        description="Seed keywords generated in STEP 1 before expansion (120-150 intent-based keywords)"
    )
    total_keywords_analyzed: int = Field(
        ..., description="Total number of keywords with measurable search volume (after expansion)"
    )
    total_monthly_volume: int = Field(
        ..., description="Total monthly search volume across all keywords"
    )

    # ========================================
    # KEY FINDINGS (Executive Summary Bullets)
    # ========================================
    key_findings: List[str] = Field(
        ..., description="3-5 bullet points highlighting key SEO findings"
    )

    # ========================================
    # TIER 1: IMMEDIATE IMPLEMENTATION
    # ========================================
    tier_1_keywords: List[TieredKeyword] = Field(
        ..., description="High volume + low competition keywords (3-5 keywords)"
    )
    tier_1_quick_win_strategy: str = Field(
        ...,
        description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
    )

    # ========================================
    # TIER 2: HIGH VALUE KEYWORDS
    # ========================================
    tier_2_keywords: Optional[List[TieredKeyword]] = Field(
        default=None,
        description="High value keywords with medium competition (3-5 keywords)"
    )
    tier_2_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 2 keywords (1-2 paragraphs, markdown)"
    )

    # ========================================
    # TIER 3: GEOGRAPHIC/NICHE OPPORTUNITIES
    # ========================================
    tier_3_geographic_groups: Optional[List[GeographicKeywordGroup]] = Field(
        default=None,
        description="Geographic keyword opportunities grouped by region"
    )

    # ========================================
    # TIER 4: SPECIALIZED/CATEGORY OPPORTUNITIES
    # ========================================
    tier_4_category_groups: Optional[List[CategoryKeywordGroup]] = Field(
        default=None,
        description="Category-based keyword groups (document types, service categories)"
    )

    # ========================================
    # CONTENT STRATEGY
    # ========================================
    content_strategy: str = Field(
        ...,
        description="Comprehensive content strategy with numbered sections (markdown, 4-6 paragraphs)"
    )
    topic_clusters: Optional[List[TopicCluster]] = Field(
        default=None,
        description="Content pillars/clusters (3-5 clusters)"
    )

    # ========================================
    # TECHNICAL SEO
    # ========================================
    technical_seo_recommendations: str = Field(
        ...,
        description="Technical SEO recommendations with URL structure, schema markup, code examples (markdown, 3-5 sections)"
    )

    # NEW: Keyword-Driven Site Architecture
    keyword_driven_site_architecture: Optional[KeywordDrivenSiteArchitecture] = Field(
        default=None,
        description="Site structure organized around keyword clusters and search intent patterns"
    )
    keyword_based_page_types: Optional[List[KeywordBasedPageType]] = Field(
        default=None,
        description="Page types derived from keyword analysis (4-8 page types covering different keyword clusters)"
    )

    # ========================================
    # COMPETITIVE POSITIONING
    # ========================================
    competitive_positioning: str = Field(
        ...,
        description="Keyword gaps to exploit, unique positioning angles (markdown, 2-4 sections with examples)"
    )

    # ========================================
    # IMPLEMENTATION ROADMAP
    # ========================================
    implementation_roadmap: str = Field(
        ...,
        description="Phased implementation plan (markdown, 3-4 phases with timelines and specific targets)"
    )

    # ========================================
    # METRICS & TRACKING
    # ========================================
    key_metrics_to_track: List[str] = Field(
        ..., description="4-6 critical KPIs (SEO Performance + Business Metrics)"
    )

    # ========================================
    # RISK MITIGATION
    # ========================================
    risk_mitigation: Optional[str] = Field(
        default=None,
        description="Potential challenges and mitigation strategies (markdown, 2-4 challenges)"
    )

    # ========================================
    # BUDGET ALLOCATION
    # ========================================
    budget_allocation: Optional[str] = Field(
        default=None,
        description="Budget recommendations with options (markdown, Option A/B/C)"
    )

    # ========================================
    # LONG-TERM STRATEGY
    # ========================================
    long_term_strategy: str = Field(
        ...,
        description="Year 1/2/3 strategic milestones (markdown, 3 sections)"
    )

    # ========================================
    # CONCLUSION
    # ========================================
    conclusion_bottom_line: str = Field(
        ...,
        description="Bottom line summary (1 paragraph)"
    )
    competitive_advantages: List[str] = Field(
        ..., description="2-4 key competitive advantages from SEO analysis"
    )
    critical_success_factors: List[str] = Field(
        ..., description="3-4 critical success factors"
    )
    expected_timeline: str = Field(
        ..., description="Timeline expectations (3, 6, 12, 18 months milestones)"
    )

    # ========================================
    # NEXT STEPS
    # ========================================
    next_steps_checklist: List[str] = Field(
        ..., description="Actionable checklist (5-8 items with ✅/⬜ checkboxes)"
    )
