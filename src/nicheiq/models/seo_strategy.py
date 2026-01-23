"""
Pydantic models for SEO strategy (Stage 10 enhancement).

These models capture structured keyword data and narrative strategy sections
that combine into the comprehensive SEO section of the final report.
"""

import json
from enum import Enum
from typing import Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

class ConceptualKeyword(BaseModel):
    """
    Conceptual keyword from Phase 9.5a hybrid seed generation (before DataForSEO enrichment).

    Keywords should follow the 70-30 hybrid approach:
    - 70% Broad Seeds: 1-2 words (max 3 words)
    - 30% Targeted Keywords: 3-5 words

    Includes strategic context and cluster assignment for intelligent enrichment.
    """

    model_config = ConfigDict(extra='ignore')

    keyword: str = Field(..., description="The keyword phrase")
    cluster: str = Field(..., description="Topic cluster this keyword belongs to")
    priority: int = Field(..., ge=1, le=5, description="Strategic priority (1=highest, 5=lowest)")
    rationale: Optional[str] = Field(
        default=None,
        description="Why this keyword is important strategically"
    )

    @field_validator('keyword')
    @classmethod
    def validate_keyword_length(cls, v: str) -> str:
        """Log warning if keyword exceeds recommended length (helps detect prompt issues)."""
        word_count = len(v.split())
        if word_count > 5:
            import logging
            logging.getLogger(__name__).warning(
                f"Keyword '{v}' has {word_count} words (recommended: 1-5 words). "
                f"Review Phase 9.5a prompt if many keywords exceed 5 words."
            )
        return v

class ConceptualTopicCluster(BaseModel):
    """Topic cluster for organizing keywords strategically (Phase 9.5a output)."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Cluster name (e.g., 'International Shipping', 'Customs')")
    description: str = Field(..., description="Brief description of this topic area")
    strategic_importance: int = Field(
        ..., ge=1, le=5, description="Importance for SEO strategy (1=critical, 5=nice-to-have)"
    )

class ExpandedKeywordList(BaseModel):
    """
    Result of Phase 9.5a hybrid seed keyword generation.
    Contains 40-50 strategically selected keywords using 70-30 mix:
    - 70% Broad Seeds (28-35 keywords, 1-2 words)
    - 30% Targeted Keywords (12-15 keywords, 3-5 words)
    """

    model_config = ConfigDict(extra='ignore')

    keywords: list[ConceptualKeyword] = Field(
        ..., description="Hybrid seed keywords (40-50 total): 70% broad seeds (1-2 words) + 30% targeted keywords (3-5 words)"
    )
    topic_clusters: list[ConceptualTopicCluster] = Field(
        ..., description="Topic clusters for organizing keywords"
    )
    expansion_rationale: str = Field(
        ..., description="Overall strategy behind keyword expansion"
    )

class TieredKeyword(BaseModel):
    """
    Individual keyword with targeting strategy for report tables.

    Matches the table format from translation services example:
    | Keyword | Search Volume | Competition | Opportunity Score | Strategy |
    """

    model_config = ConfigDict(extra='ignore')

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO (single value)")
    competition: str = Field(
        ..., description="Competition level (e.g., 'LOW (30)', 'MEDIUM (53)', 'VERY LOW (5)')"
    )
    opportunity_score: Optional[float] = Field(
        default=None, description="Calculated opportunity score (volume/competition or similar metric)"
    )
    strategy: str = Field(
        ..., description="Brief targeting strategy (1-2 sentences)"
    )
    intent: Optional[str] = Field(
        default=None, description="Search intent (e.g., 'High conversion intent', 'Informational')"
    )

    # NEW: Tier classification rationale for transparency
    tier: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="Keyword tier (0=premium, 1=quick_win, 2=strategic, 3=geographic, 4=categorical, 5=untiered)"
    )
    tier_rationale: Optional[str] = Field(
        default=None,
        description=(
            "Explanation of tier classification (e.g., 'High volume (4.2k) + Low competition (18) = quick win')"
        )
    )

    @field_validator('keyword')
    @classmethod
    def validate_keyword_constraints(cls, v: str) -> str:
        """Validate keyword and log warning if constraints not met (validation happens elsewhere)."""
        return v.strip()

class GeographicKeywordEntry(BaseModel):
    """Individual geographic keyword entry."""

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

    keyword_name: str = Field(..., description="Keyword name (document type, service name, etc.)")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO")
    competition: Optional[str] = Field(default=None, description="Competition level")
    cpc: float = Field(default=0.0, description="Cost per click estimate (defaults to 0 if unavailable)")

    @field_validator('keyword_name')
    @classmethod
    def validate_keyword_constraints(cls, v: str) -> str:
        """Strip whitespace (validation happens elsewhere to allow filtering)."""
        return v.strip()

    @field_validator('cpc', mode='before')
    @classmethod
    def coerce_cpc_none_to_zero(cls, v):
        """Coerce None to 0 for CPC field (DataForSEO may return null)."""
        if v is None or v == "null":
            return 0.0
        return v

class GeographicKeywordGroup(BaseModel):
    """
    Geographic market keyword group.

    Example: Spanish-Speaking Markets, UK Markets, etc.
    """

    model_config = ConfigDict(extra='ignore')

    region_name: str = Field(..., description="Region/country name (e.g., 'Spanish-Speaking Markets')")
    total_volume: int = Field(..., description="Combined monthly search volume")
    competition_level: str = Field(..., description="Overall competition assessment")
    keywords: list[GeographicKeywordEntry] = Field(
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

    model_config = ConfigDict(extra='ignore')

    category_name: str = Field(..., description="Category name (e.g., 'Education Documents')")
    total_volume: int = Field(..., description="Combined monthly search volume")
    keywords: list[CategoryKeywordEntry] = Field(
        ..., description="List of category keyword entries"
    )
    strategy_recommendation: str = Field(
        ..., description="Strategic recommendation for this category (2-4 sentences)"
    )

    @field_validator('keywords')
    @classmethod
    def keywords_not_empty(cls, v: list[CategoryKeywordEntry]) -> list[CategoryKeywordEntry]:
        """Ensure category has at least 1 keyword to prevent empty/hallucinated categories."""
        if v is not None and len(v) == 0:
            raise ValueError("Category must have at least 1 keyword - empty categories are not allowed")
        return v

class TopicCluster(BaseModel):
    """Content pillar with grouped keywords."""

    model_config = ConfigDict(extra='ignore')

    cluster_name: str = Field(..., description="Name of the content cluster/pillar")
    primary_keyword: str = Field(..., description="Main keyword for this cluster")
    supporting_keywords: list[str] = Field(
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
    def validate_supporting_keywords(cls, v: list[str]) -> list[str]:
        """Strip whitespace and filter out invalid keywords."""
        validated = []
        for keyword in v:
            keyword = keyword.strip()
            if validate_keyword(keyword, "supporting_keyword"):
                validated.append(keyword)
        return validated

class KeywordBasedPageType(BaseModel):
    """Page type definition derived from keyword clusters and search intent."""

    model_config = ConfigDict(extra='ignore')

    page_type_name: str = Field(
        ..., description="Name of page type based on keyword intent (e.g., 'Problem Solution Pages', 'Geographic Landing Pages')"
    )
    url_pattern: str = Field(
        ..., description="URL pattern optimized for target keywords (e.g., '/tools/[problem-keyword]/', '/city/[city-name]/')"
    )
    target_keyword_cluster: str = Field(
        ..., description="Which keyword tier/cluster this page type targets (e.g., 'Tier 1 quick wins', 'Geographic group: Spanish markets')"
    )
    example_keywords: list[str] = Field(
        ..., min_length=2, max_length=5, description="2-5 example target keywords this page type addresses"
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
    required_schema: Optional[list[str]] = Field(
        default=None, description="Schema.org types for this page type based on content and intent"
    )
    seo_optimization_notes: str = Field(
        ..., description="SEO-specific guidance: title patterns, header structure, internal linking strategy for these pages"
    )
    seo_optimization_notes_addendum: Optional[str] = Field(
        default=None, description="Additional SEO optimization notes if needed"
    )

class SectionKeywordMapping(BaseModel):
    """Mapping of a site section to its keyword cluster."""

    model_config = ConfigDict(extra='ignore')

    section_path: str = Field(..., description="URL path of the section (e.g., '/tools/', '/compare/')")
    keyword_cluster: str = Field(..., description="Keyword cluster description (e.g., 'Tier 1 problem-solving keywords')")

class KeywordDrivenSiteArchitecture(BaseModel):
    """Site structure organized by keyword clusters and search intent patterns."""

    model_config = ConfigDict(extra='ignore')

    url_hierarchy_diagram: Optional[str] = Field(
        default=None, description="ASCII/markdown hierarchy showing how keyword clusters map to site sections"
    )
    section_keyword_mapping: Optional[list[SectionKeywordMapping]] = Field(
        default=None, description="Mapping of top-level sections to keyword clusters (e.g., {'/tools/': 'Tier 1 problem-solving keywords', '/compare/': 'Competitor alternative keywords'})"
    )
    total_pages_from_keywords: Optional[int] = Field(
        default=None, description="Total page count derived from keyword opportunities (geographic variations × category variations × core pages)"
    )
    keyword_coverage_explanation: Optional[str] = Field(
        default=None, description="Explanation of how site structure ensures all high-priority keywords have dedicated landing pages (2-3 sentences)"
    )

class UniversalSEOElements(BaseModel):
    """Universal SEO elements that appear on every page."""

    model_config = ConfigDict(extra='ignore')

    title_tag_formula: str = Field(
        ...,
        description="Title tag format pattern (e.g., '[Primary Keyword] | [Secondary] | [Brand]')"
    )
    title_tag_guidelines: str = Field(
        ...,
        description="Character limits, keyword placement, CTR optimization tips (2-3 paragraphs, markdown)"
    )
    meta_description_guidelines: str = Field(
        ...,
        description="Length, CTA inclusion, keyword usage best practices (2-3 paragraphs, markdown)"
    )
    canonical_url_strategy: str = Field(
        ...,
        description="Self-referencing canonicals, filter/sort handling, duplicate content prevention (2 paragraphs, markdown)"
    )
    open_graph_tags: str = Field(
        ...,
        description="Required OG tags (og:title, og:description, og:image, og:url) with format examples (markdown)"
    )
    robots_meta_guidelines: str = Field(
        ...,
        description="When to use index/noindex, follow/nofollow with page type examples (2 paragraphs, markdown)"
    )
    robots_meta_guidelines_note: Optional[str] = Field(
        default=None, description="Additional notes on robots meta guidelines"
    )

class PageTypeImplementation(BaseModel):
    """SEO implementation template for specific page type."""

    model_config = ConfigDict(extra='ignore')

    page_type: str = Field(
        ...,
        description="Page type name (e.g., 'Homepage', 'Location Page', 'Profile Page', 'Content Page')"
    )
    url_pattern: str = Field(
        ...,
        description="URL structure pattern (e.g., '/translators/[city]', '/guides/[topic]')"
    )
    target_keywords: list[str] = Field(
        ...,
        description="3-5 primary and secondary keyword patterns for this page type"
    )
    title_tag_example: str = Field(
        ...,
        description="Example title tag applying the formula to this page type"
    )
    meta_description_example: str = Field(
        ...,
        description="Example meta description for this page type"
    )
    h1_structure: str = Field(
        ...,
        description="H1 format pattern (e.g., '[Service] in [Location] - [Value Prop]')"
    )
    h2_structure: list[str] = Field(
        ...,
        description="Recommended H2 section headings (3-6 headings)"
    )
    schema_types: list[str] = Field(
        ...,
        description="Required schema types (e.g., ['Organization', 'Service', 'Breadcrumb', 'FAQ'])"
    )
    internal_linking_strategy: str = Field(
        ...,
        description="How this page type should link to others (2-3 sentences)"
    )
    content_guidelines: str = Field(
        ...,
        description="Min/optimal word count, required sections, quality standards (2-3 sentences)"
    )
    priority: Optional[str] = Field(
        default=None, description="Implementation priority level (e.g., 'high', 'medium', 'low')"
    )

class SchemaExample(BaseModel):
    """Individual schema markup code example."""

    model_config = ConfigDict(extra='ignore')

    schema_type: str = Field(
        ...,
        description="Schema.org type (e.g., 'Organization', 'Service', 'FAQ', 'Article', 'BreadcrumbList')"
    )
    json_ld_code: str = Field(
        ...,
        description="JSON-LD code snippet for this schema type"
    )

    @field_validator("json_ld_code", mode="before")
    @classmethod
    def serialize_json_ld(cls, v):
        """Convert dict to JSON string if LLM returns object instead of string."""
        if isinstance(v, dict):
            return json.dumps(v, indent=2)
        return v

class SchemaMarkupStrategy(BaseModel):
    """Schema markup implementation guide with code examples."""

    model_config = ConfigDict(extra='ignore')

    why_schema_matters: str = Field(
        ...,
        description="Benefits: rich results, voice search, AI search, CTR boost (2-3 paragraphs, markdown)"
    )
    priority_schema_types: list[str] = Field(
        ...,
        description="Ordered list of 6-8 essential schema types (Organization, Service, Person, Review, FAQ, Article, BreadcrumbList, etc.)"
    )
    implementation_method: str = Field(
        ...,
        description="JSON-LD format, placement in <head>, why JSON-LD over Microdata (2 paragraphs, markdown)"
    )
    schema_examples: list[SchemaExample] = Field(
        ...,
        description="JSON-LD code snippets for each priority schema type (6-8 examples)"
    )
    testing_validation: str = Field(
        ...,
        description="Tools and process: Google Rich Results Test, Schema Validator, Search Console monitoring (2 paragraphs, markdown)"
    )

class SEOStrategyReport(BaseModel):
    """
    Comprehensive SEO strategy report matching translation services example.

    This model captures both structured data (keywords, volumes, tiers) and
    narrative markdown sections for the final report's SEO section.
    """

    model_config = ConfigDict(extra='ignore')

    # ========================================
    # METADATA
    # ========================================
    seed_keywords_generated: Optional[list[str]] = Field(
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
    key_findings: list[str] = Field(
        ..., description="3-5 bullet points highlighting key SEO findings"
    )

    # ========================================
    # TIER 0: PREMIUM OPPORTUNITIES
    # ========================================
    tier_0_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Premium keywords with exceptional opportunity scores (>200)"
    )
    tier_0_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 0 premium keywords (1-2 paragraphs, markdown)"
    )

    # ========================================
    # TIER 1: IMMEDIATE IMPLEMENTATION
    # ========================================
    tier_1_keywords: list[TieredKeyword] = Field(
        ..., description="High volume + low competition keywords (3-5 keywords)"
    )
    tier_1_quick_win_strategy: str = Field(
        ...,
        description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
    )

    # ========================================
    # TIER 2: HIGH VALUE KEYWORDS
    # ========================================
    tier_2_keywords: Optional[list[TieredKeyword]] = Field(
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
    tier_3_geographic_groups: Optional[list[GeographicKeywordGroup]] = Field(
        default=None,
        description="Geographic keyword opportunities grouped by region"
    )

    # ========================================
    # TIER 4: SPECIALIZED/CATEGORY OPPORTUNITIES
    # ========================================
    tier_4_category_groups: Optional[list[CategoryKeywordGroup]] = Field(
        default=None,
        description="Category-based keyword groups (document types, service categories)"
    )

    # ========================================
    # TIER 5: UNTIERED KEYWORDS (FORCE-ADDED)
    # ========================================
    untiered_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Keywords from CSV not selected by LLM - force-added for completeness"
    )

    # ========================================
    # CONTENT STRATEGY
    # ========================================
    content_strategy: str = Field(
        ...,
        description="Comprehensive content strategy with numbered sections (markdown, 4-6 paragraphs)"
    )
    topic_clusters: Optional[list[TopicCluster]] = Field(
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
    keyword_based_page_types: Optional[list[KeywordBasedPageType]] = Field(
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
    key_metrics_to_track: list[str] = Field(
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
    competitive_advantages: list[str] = Field(
        ..., description="2-4 key competitive advantages from SEO analysis"
    )
    critical_success_factors: list[str] = Field(
        ..., description="3-4 critical success factors"
    )
    expected_timeline: str = Field(
        ..., description="Timeline expectations (3, 6, 12, 18 months milestones)"
    )

    # ========================================
    # NEXT STEPS
    # ========================================
    next_steps_checklist: list[str] = Field(
        ..., description="Actionable checklist (5-8 items with ✅/⬜ checkboxes)"
    )

    # ========================================
    # IMPLEMENTATION GUIDE (TASK 5)
    # ========================================
    universal_seo_elements: Optional[UniversalSEOElements] = Field(
        default=None,
        description="Universal SEO elements for every page (title tags, meta descriptions, canonical, OG tags, robots)"
    )
    page_type_implementations: Optional[list[PageTypeImplementation]] = Field(
        default=None,
        description="SEO templates for 4-6 key page types (homepage, location pages, profile pages, content pages)"
    )
    schema_markup_strategy: Optional[SchemaMarkupStrategy] = Field(
        default=None,
        description="Schema markup implementation guide with JSON-LD code examples and testing guidance"
    )

    @field_validator('total_monthly_volume', mode='before')
    @classmethod
    def validate_total_monthly_volume(cls, v):
        """Coerce None to 0 when all keywords have null volumes."""
        if v is None or v == "null":
            return 0
        return v

# ========================================
# INTERMEDIATE MODELS FOR MULTI-TASK FLOW
# ========================================

# ----------------------------------------
# Stage 9 Split Task Models (Tasks 1a-1d)
# ----------------------------------------

class PremiumTierResult(BaseModel):
    """
    Task 1a: Premium Tier Analysis (Tiers 0, 1, 2).

    Analyzes keywords with high opportunity scores and creates strategic
    targeting recommendations for quick-win and high-value opportunities.

    Output size: ~30-50 keywords, ~50-80 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    # Tier 0: Premium opportunities (opp_score > 200)
    tier_0_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Premium keywords with exceptional opportunity scores (>200). Select ALL keywords meeting this threshold."
    )
    tier_0_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 0 premium keywords (1-2 paragraphs, markdown)"
    )

    # Tier 1: Quick wins (opp_score > 100)
    tier_1_keywords: list[TieredKeyword] = Field(
        ...,
        min_length=1,
        description="High volume + low competition keywords (3-5 keywords, minimum 1)"
    )
    tier_1_quick_win_strategy: str = Field(
        ..., description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
    )

    # Tier 2: Strategic keywords (opp_score 50-100)
    tier_2_keywords: Optional[list[TieredKeyword]] = Field(
        default=None, description="High value keywords with medium competition (3-5 keywords)"
    )
    tier_2_strategy: Optional[str] = Field(
        default=None, description="Strategy narrative for Tier 2 keywords (1-2 paragraphs, markdown)"
    )

    # Tracking for merge validation
    premium_keywords_count: int = Field(
        ..., description="Total count of T0 + T1 + T2 keywords"
    )
    filtered_keywords_count: int = Field(
        default=0, description="Count of keywords filtered as irrelevant in STEP 0"
    )


class HighPriorityTierResult(BaseModel):
    """
    Task 1a (Parallel): High Priority Keywords (Tier 0 + Tier 1).

    Analyzes pre-filtered keywords with opp_score > 100 for immediate SEO wins.
    This task runs in parallel with Tasks 1b, 1c, 1d.

    Output size: ~10-30 keywords, ~30-50 lines JSON

    NOTE: This model is kept for backward compatibility. For new implementations,
    use Tier0PremiumResult and Tier1QuickWinResult for better token management.
    """

    model_config = ConfigDict(extra='ignore')

    # Tier 0: Premium opportunities (opp_score > 200)
    tier_0_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Premium keywords with exceptional opportunity scores (>200). Select ALL keywords meeting this threshold."
    )
    tier_0_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 0 premium keywords (1-2 paragraphs, markdown)"
    )

    # Tier 1: Quick wins (opp_score 100-200)
    tier_1_keywords: list[TieredKeyword] = Field(
        ...,
        min_length=1,
        description="High volume + low competition keywords (opp_score 100-200, minimum 1)"
    )
    tier_1_quick_win_strategy: str = Field(
        ..., description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
    )

    # Tracking
    high_priority_count: int = Field(
        ..., description="Total count of T0 + T1 keywords"
    )


# ========================================
# LIGHTWEIGHT OUTPUT MODELS FOR PYTHON HYDRATION
# ========================================
# These models capture only LLM-generated content (keyword selections + strategies).
# Python hydrates full objects with stats from CSV lookup.


class LightweightKeywordSelection(BaseModel):
    """Minimal keyword selection - Python will hydrate with stats from CSV."""

    model_config = ConfigDict(extra='ignore')

    keyword: str = Field(..., description="The keyword phrase (must match CSV exactly)")
    strategy: str = Field(..., description="Brief targeting strategy (1-2 sentences)")
    intent: Optional[str] = Field(default=None, description="Search intent classification")


class Tier0LightResult(BaseModel):
    """
    Lightweight Task 1a-i output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + strategies, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_0_keywords: list[LightweightKeywordSelection] = Field(
        ...,
        min_length=1,
        description="Premium keyword selections. Include ALL keywords from CSV."
    )
    tier_0_strategy: str = Field(
        ..., description="Strategy narrative for Tier 0 premium keywords (1 paragraph max)"
    )


class Tier1LightResult(BaseModel):
    """
    Lightweight Task 1a-ii output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + strategies, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_1_keywords: list[LightweightKeywordSelection] = Field(
        ...,
        min_length=1,
        description="Quick win keyword selections. Include ALL keywords from CSV."
    )
    tier_1_quick_win_strategy: str = Field(
        ..., description="Strategy narrative for Tier 1 quick wins (1 paragraph max)"
    )


class StrategicLightResult(BaseModel):
    """
    Lightweight Task 1b output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + strategies, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_2_keywords: Optional[list[LightweightKeywordSelection]] = Field(
        default=None,
        description="Strategic keyword selections (or null if empty)"
    )
    tier_2_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 2 keywords (1-2 paragraphs, or null if empty)"
    )


class GeographicLightEntry(BaseModel):
    """Lightweight geographic entry - Python hydrates search_volume from CSV."""

    model_config = ConfigDict(extra='ignore')

    keyword: str = Field(..., description="The keyword phrase (must match CSV exactly)")
    city: str = Field(..., description="City/location extracted from keyword text")
    notes: Optional[str] = Field(default=None, description="Optional notes about this keyword")


class GeographicLightGroup(BaseModel):
    """Lightweight geographic group - Python calculates total_volume from CSV."""

    model_config = ConfigDict(extra='ignore')

    region_name: str = Field(..., description="Region name (e.g., 'Spanish-Speaking Markets')")
    keywords: list[GeographicLightEntry] = Field(
        ..., description="Geographic keyword entries"
    )
    strategy_notes: str = Field(
        ..., description="Strategic notes for this geographic market (1-3 sentences)"
    )
    competition_level: str = Field(
        ..., description="LLM assessment: 'LOW', 'MEDIUM', or 'HIGH'"
    )


class GeographicLightResult(BaseModel):
    """
    Lightweight Task 1c output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + groupings, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_3_geographic_groups: Optional[list[GeographicLightGroup]] = Field(
        default=None, description="Geographic keyword groups (or null if none)"
    )
    geographic_strategy_notes: Optional[str] = Field(
        default=None, description="Overall geographic strategy (1-2 paragraphs, or null)"
    )


class CategoryLightEntry(BaseModel):
    """Lightweight category entry - Python hydrates stats from CSV."""

    model_config = ConfigDict(extra='ignore')

    keyword_name: str = Field(..., description="Keyword phrase (must match CSV exactly)")


class CategoryLightGroup(BaseModel):
    """Lightweight category group - Python calculates total_volume from CSV."""

    model_config = ConfigDict(extra='ignore')

    category_name: str = Field(..., description="Category theme name")
    keywords: list[CategoryLightEntry] = Field(
        ..., min_length=1, description="Keywords in this category (at least 1)"
    )
    strategy_recommendation: str = Field(
        ..., description="Strategy recommendation for this category (2-4 sentences)"
    )


class CategoryLightResult(BaseModel):
    """
    Lightweight Task 1d output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + groupings, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_4_category_groups: Optional[list[CategoryLightGroup]] = Field(
        default=None, description="Category groups (or null if empty)"
    )
    category_strategy_notes: Optional[str] = Field(
        default=None, description="Overall category strategy (1-2 paragraphs, or null)"
    )


# ----------------------------------------
# Task 2: Lightweight Content Strategy Output
# ----------------------------------------
# LLM generates strategic/creative content only.
# Python hydrates numeric fields from keyword CSV data.


class TopicClusterLight(BaseModel):
    """
    Lightweight topic cluster - Python hydrates volumes.

    LLM outputs only strategic content (cluster groupings, recommendations).
    Python calculates total_monthly_volume and estimated_traffic_potential from CSV.
    """

    model_config = ConfigDict(extra='ignore')

    cluster_name: str = Field(..., description="Name of the content cluster/pillar")
    primary_keyword: str = Field(
        ..., description="Main keyword for this cluster (must match CSV keyword)"
    )
    supporting_keywords: list[str] = Field(
        ..., description="Related keywords (must match CSV keywords, 5-15 keywords)"
    )
    content_recommendation: str = Field(
        ..., description="What to create for this cluster (2-4 sentences)"
    )
    priority: int = Field(
        ..., ge=1, le=5, description="Priority level (1=highest, 5=lowest)"
    )


class KeywordBasedPageTypeLight(BaseModel):
    """
    Lightweight page type - Python hydrates page count.

    LLM outputs only strategic content (page type definitions, schema types).
    Python calculates estimated_page_count based on keyword tier/cluster data.
    """

    model_config = ConfigDict(extra='ignore')

    page_type_name: str = Field(
        ..., description="Name of page type based on keyword intent"
    )
    url_pattern: str = Field(
        ..., description="URL pattern optimized for target keywords"
    )
    target_keyword_cluster: str = Field(
        ..., description="Which keyword tier/cluster this page type targets"
    )
    example_keywords: list[str] = Field(
        ..., min_length=2, max_length=5, description="2-5 example target keywords"
    )
    primary_intent: str = Field(
        ..., description="Primary search intent: 'commercial', 'informational', 'navigational', 'transactional'"
    )
    priority: str = Field(
        ..., description="Launch priority: 'P0' (Tier 1), 'P1' (Tier 2), 'P2' (Tier 3-4)"
    )
    required_schema: Optional[list[str]] = Field(
        default=None, description="Schema.org types for this page type"
    )
    seo_optimization_notes: str = Field(
        ..., description="SEO-specific guidance for these pages"
    )


class ContentStrategyResultLight(BaseModel):
    """
    Lightweight Task 2 output - Python hydrates numeric fields.

    LLM outputs only strategic/creative content:
    - content_strategy narrative
    - Topic cluster groupings (which keywords belong together)
    - technical_seo_recommendations narrative
    - Page type definitions (URL patterns, schema types)

    Python hydrates from CSV:
    - total_monthly_volume (sum from keyword CSV)
    - estimated_traffic_potential (calculated from volume)
    - estimated_page_count (count keywords per tier)
    - total_pages_from_keywords (sum page type counts)
    """

    model_config = ConfigDict(extra='ignore')

    # Content strategy (LLM-generated)
    content_strategy: str = Field(
        ...,
        min_length=100,
        description="Comprehensive content strategy with numbered sections (markdown, 4-6 paragraphs)"
    )
    topic_clusters: Optional[list[TopicClusterLight]] = Field(
        default=None, description="Content pillars/clusters (3-5 clusters) - Python will add volumes"
    )

    # Technical SEO (LLM-generated)
    technical_seo_recommendations: str = Field(
        ...,
        min_length=50,
        description="Technical SEO recommendations (markdown, 3-5 sections)"
    )
    keyword_based_page_types: Optional[list[KeywordBasedPageTypeLight]] = Field(
        default=None,
        description="Page types (4-8 types) - Python will add page counts"
    )

    # Site architecture fields (LLM-generated, minimal numeric content)
    url_hierarchy_diagram: Optional[str] = Field(
        default=None, description="ASCII/markdown hierarchy showing keyword cluster mapping"
    )
    section_keyword_mapping: Optional[str] = Field(
        default=None, description="Mapping of sections to keyword clusters (markdown)"
    )
    keyword_coverage_explanation: Optional[str] = Field(
        default=None, description="How site structure ensures keyword coverage (2-3 sentences)"
    )


# ========================================
# ORIGINAL (FULL) OUTPUT MODELS - KEPT FOR BACKWARD COMPATIBILITY
# ========================================


class Tier0PremiumResult(BaseModel):
    """
    Task 1a-i (Parallel): Tier 0 Premium Keywords.

    Analyzes pre-filtered keywords with opp_score > 200 (exceptional opportunities).
    This task runs in parallel with Tasks 1a-ii, 1b, 1c, 1d.

    Output size: ~50-200 keywords, ~100-300 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    tier_0_keywords: list[TieredKeyword] = Field(
        ...,
        min_length=1,
        description="Premium keywords with opp_score >200. Include ALL keywords from CSV."
    )
    tier_0_strategy: str = Field(
        ..., description="Strategy narrative for Tier 0 premium keywords (1 paragraph max)"
    )
    tier_0_count: int = Field(..., description="Total count of Tier 0 keywords")


class Tier1QuickWinResult(BaseModel):
    """
    Task 1a-ii (Parallel): Tier 1 Quick Win Keywords.

    Analyzes pre-filtered keywords with opp_score 100-200 (quick wins).
    This task runs in parallel with Tasks 1a-i, 1b, 1c, 1d.

    Output size: ~10-50 keywords, ~30-80 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    tier_1_keywords: list[TieredKeyword] = Field(
        ...,
        min_length=1,
        description="Quick win keywords with opp_score 100-200. Include ALL keywords from CSV."
    )
    tier_1_quick_win_strategy: str = Field(
        ..., description="Strategy narrative for Tier 1 quick wins (1 paragraph max)"
    )
    tier_1_count: int = Field(..., description="Total count of Tier 1 keywords")


class StrategicTierResult(BaseModel):
    """
    Task 1b (Parallel): Strategic Keywords (Tier 2).

    Analyzes pre-filtered keywords with opp_score 50-100 for medium-term SEO growth.
    This task runs in parallel with Tasks 1a, 1c, 1d.

    Output size: ~10-30 keywords, ~20-40 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    # Tier 2: Strategic keywords (opp_score 50-100)
    tier_2_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Strategic keywords with medium competition (opp_score 50-100)"
    )
    tier_2_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 2 keywords (1-2 paragraphs, markdown)"
    )

    # Tracking
    strategic_count: int = Field(
        default=0, description="Total count of Tier 2 keywords"
    )


class GeographicTierResult(BaseModel):
    """
    Task 1b: Geographic Tier Analysis (Tier 3).

    Groups keywords containing explicit location mentions (city/country names)
    by region for geographic SEO strategy.

    Output size: ~20-50 keywords grouped, ~40-60 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    tier_3_geographic_groups: Optional[list[GeographicKeywordGroup]] = Field(
        default=None, description="Geographic keyword opportunities grouped by region"
    )
    geographic_strategy_notes: Optional[str] = Field(
        default=None, description="Strategic notes for geographic keyword targeting (1-2 paragraphs, markdown)"
    )
    geographic_keywords_count: int = Field(
        default=0, description="Total count of keywords in geographic groups"
    )


class CategoryTierResult(BaseModel):
    """
    Task 1c: Category Tier Analysis (Tier 4).

    Organizes remaining keywords (after premium + geographic selection) into
    thematic category groups for programmatic SEO.

    Output size: ~100-200 keywords grouped, ~100-150 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    tier_4_category_groups: Optional[list[CategoryKeywordGroup]] = Field(
        default=None, description="Category-based keyword groups (document types, service categories)"
    )
    category_strategy_notes: Optional[str] = Field(
        default=None, description="Strategic notes for category-based keyword targeting (1-2 paragraphs, markdown)"
    )
    category_keywords_count: int = Field(
        default=0, description="Total count of keywords in category groups"
    )


class KeywordSummaryResult(BaseModel):
    """
    Task 1e: Summary & Synthesis with sample keywords for downstream tasks.

    Synthesizes findings from Tasks 1a-1d into key findings and competitive
    positioning insights. Also extracts sample keywords from each tier for
    Task 2 (Content Strategy) to use in topic cluster creation.

    Aggregate metrics (total_keywords_analyzed, total_monthly_volume) are
    calculated by Python in the merge step.

    Output size: ~30-50 lines JSON
    """

    model_config = ConfigDict(extra='ignore')

    key_findings: list[str] = Field(
        ...,
        min_length=1,
        description="3-5 bullet points highlighting key SEO findings (minimum 1)"
    )
    competitive_positioning: str = Field(
        ..., description="Keyword gaps to exploit, unique positioning angles (markdown, 2-4 sections)"
    )

    # Sample keywords for downstream tasks (Task 2+)
    top_tier_0_keywords: Optional[list[str]] = Field(
        default=None,
        description="Top 3-5 Tier 0 premium keyword strings (from Task 1a-i context)"
    )
    top_tier_1_keywords: Optional[list[str]] = Field(
        default=None,
        description="Top 5-10 Tier 1 quick-win keyword strings (from Task 1a-ii context)"
    )
    top_tier_2_keywords: Optional[list[str]] = Field(
        default=None,
        description="Top 5-10 Tier 2 strategic keyword strings (from Task 1b context)"
    )
    sample_geographic_regions: Optional[list[str]] = Field(
        default=None,
        description="Key geographic region names from Tier 3 groups (from Task 1c context)"
    )
    sample_category_themes: Optional[list[str]] = Field(
        default=None,
        description="Key category theme names from Tier 4 groups (from Task 1d context)"
    )


# ----------------------------------------
# Combined Keyword Analysis Result
# ----------------------------------------

class KeywordAnalysisResult(BaseModel):
    """
    Intermediate result from Task 1: Keyword Analysis & Tiering.

    The keyword_strategist agent analyzes enriched keywords and creates
    tiered opportunity structure with competitive positioning.
    """

    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from LLM (e.g., additionalProperties)

    # Tier 0: Premium opportunities (opp_score > 200)
    tier_0_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Premium keywords with exceptional opportunity scores (>200). Select ALL keywords meeting this threshold."
    )
    tier_0_strategy: Optional[str] = Field(
        default=None,
        description="Strategy narrative for Tier 0 premium keywords (1-2 paragraphs, markdown)"
    )

    # Tier structure
    tier_1_keywords: list[TieredKeyword] = Field(
        ...,
        min_length=1,
        description="High volume + low competition keywords (3-5 keywords, minimum 1)"
    )
    tier_1_quick_win_strategy: str = Field(
        ..., description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
    )
    tier_2_keywords: Optional[list[TieredKeyword]] = Field(
        default=None, description="High value keywords with medium competition (3-5 keywords)"
    )
    tier_2_strategy: Optional[str] = Field(
        default=None, description="Strategy narrative for Tier 2 keywords (1-2 paragraphs, markdown)"
    )
    tier_3_geographic_groups: Optional[list[GeographicKeywordGroup]] = Field(
        default=None, description="Geographic keyword opportunities grouped by region"
    )
    tier_4_category_groups: Optional[list[CategoryKeywordGroup]] = Field(
        default=None, description="Category-based keyword groups (document types, service categories)"
    )

    # Untiered keywords (in CSV but not selected by LLM)
    untiered_keywords: Optional[list[TieredKeyword]] = Field(
        default=None,
        description="Keywords from CSV that were not tiered by LLM analysis. "
                    "Force-added to ensure 100% keyword utilization."
    )

    # Metadata and findings
    total_keywords_analyzed: int = Field(..., description="Total number of keywords analyzed")
    total_monthly_volume: int = Field(..., description="Total monthly search volume across all keywords")
    key_findings: list[str] = Field(
        ...,
        min_length=1,
        description="3-5 bullet points highlighting key SEO findings (minimum 1)"
    )
    competitive_positioning: str = Field(
        ..., description="Keyword gaps to exploit, unique positioning angles (markdown, 2-4 sections)"
    )

    @field_validator('total_monthly_volume', mode='before')
    @classmethod
    def validate_total_monthly_volume(cls, v):
        """Coerce None to 0 when all keywords have null volumes."""
        if v is None or v == "null":
            return 0
        return v

    @model_validator(mode='after')
    def validate_keyword_distribution(self) -> 'KeywordAnalysisResult':
        """
        Validate that keywords are reasonably distributed across tiers.

        Logs tiered warnings for visibility (no pipeline failure):
        - ERROR: <50% utilization (critical keyword loss)
        - WARNING: <70% utilization (below target)
        - INFO: >=70% utilization (success)

        NOTE: Untiered keywords (tier 5) are included in total but logged separately.
        With recovery enabled, utilization should always reach 100%.
        """
        tier_0_count = len(self.tier_0_keywords) if self.tier_0_keywords else 0
        tier_1_count = len(self.tier_1_keywords) if self.tier_1_keywords else 0
        tier_2_count = len(self.tier_2_keywords) if self.tier_2_keywords else 0

        tier_3_count = 0
        if self.tier_3_geographic_groups:
            for group in self.tier_3_geographic_groups:
                tier_3_count += len(group.keywords)

        tier_4_count = 0
        if self.tier_4_category_groups:
            for group in self.tier_4_category_groups:
                tier_4_count += len(group.keywords)

        untiered_count = len(self.untiered_keywords) if self.untiered_keywords else 0

        # LLM-selected keywords (Tiers 0-4)
        llm_selected = tier_0_count + tier_1_count + tier_2_count + tier_3_count + tier_4_count
        # Total including recovered untiered
        total_with_recovery = llm_selected + untiered_count

        # Tiered logging levels for visibility (no pipeline failure)
        if self.total_keywords_analyzed > 50:
            llm_utilization = llm_selected / self.total_keywords_analyzed
            final_utilization = total_with_recovery / self.total_keywords_analyzed
            tier_breakdown = (
                f"[T0: {tier_0_count}, T1: {tier_1_count}, T2: {tier_2_count}, "
                f"T3: {tier_3_count}, T4: {tier_4_count}, Untiered: {untiered_count}]"
            )

            if llm_utilization < 0.5:
                logger.error(
                    f"⚠️ CRITICAL LLM SELECTION GAP: Only {llm_utilization:.1%} selected by LLM "
                    f"({llm_selected}/{self.total_keywords_analyzed}). "
                    f"{untiered_count} keywords force-added via recovery. {tier_breakdown}"
                )
            elif llm_utilization < 0.7:
                logger.warning(
                    f"⚠️ LLM selection low: {llm_selected}/{self.total_keywords_analyzed} "
                    f"({llm_utilization:.1%}). {untiered_count} keywords recovered. {tier_breakdown}"
                )
            else:
                logger.info(
                    f"✅ LLM keyword selection: {llm_utilization:.1%} "
                    f"({llm_selected}/{self.total_keywords_analyzed}). {tier_breakdown}"
                )

            # Final utilization should be 100% with recovery
            if final_utilization >= 0.999:
                logger.info(
                    f"✅ Final keyword utilization: {final_utilization:.1%} "
                    f"({total_with_recovery}/{self.total_keywords_analyzed} keywords)"
                )

        return self

class ContentStrategyResult(BaseModel):
    """
    Intermediate result from Task 2: Content & Technical Strategy.

    The content_strategist agent develops content strategy, topic clusters,
    and technical SEO recommendations based on keyword analysis.
    """

    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from LLM (e.g., additionalProperties)

    # Content strategy
    content_strategy: str = Field(
        ...,
        min_length=100,
        description="Comprehensive content strategy with numbered sections (markdown, 4-6 paragraphs, minimum 100 chars)"
    )
    topic_clusters: Optional[list[TopicCluster]] = Field(
        default=None, description="Content pillars/clusters (3-5 clusters)"
    )

    # Technical SEO
    technical_seo_recommendations: str = Field(
        ...,
        min_length=50,
        description="Technical SEO recommendations with URL structure, schema markup, code examples (markdown, 3-5 sections, minimum 50 chars)"
    )
    keyword_driven_site_architecture: Optional[KeywordDrivenSiteArchitecture] = Field(
        default=None, description="Site structure organized around keyword clusters and search intent patterns"
    )
    keyword_based_page_types: Optional[list[KeywordBasedPageType]] = Field(
        default=None,
        min_length=2,
        description="Page types derived from keyword analysis (4-8 page types, minimum 2)"
    )

class ImplementationPlanResult(BaseModel):
    """
    Intermediate result from Task 3: Implementation Planning.

    The seo_specialist agent creates phased implementation roadmap with
    metrics, timeline, budget, and risk mitigation strategies.
    """

    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from LLM (e.g., additionalProperties)

    # Implementation
    implementation_roadmap: str = Field(
        ..., description="Phased implementation plan (markdown, 3-4 phases with timelines and targets)"
    )
    key_metrics_to_track: list[str] = Field(
        ..., description="4-6 critical KPIs (SEO Performance + Business Metrics)"
    )
    expected_timeline: str = Field(
        ..., description="Timeline expectations (3, 6, 12, 18 months milestones)"
    )
    next_steps_checklist: list[str] = Field(
        ..., description="Actionable checklist (5-8 items with ✅/⬜ checkboxes)"
    )

    # Optional planning elements
    risk_mitigation: Optional[str] = Field(
        default=None, description="Potential challenges and mitigation strategies (markdown, 2-4 challenges)"
    )
    budget_allocation: Optional[str] = Field(
        default=None, description="Budget recommendations with options (markdown, Option A/B/C)"
    )

class FinalSynthesis(BaseModel):
    """
    Task 4 output: Final SEO Strategy Synthesis (4 new fields only).

    Contains strategic synthesis and long-term vision that extends
    outputs from Tasks 1-3. These fields will be merged with Tasks 1-3 via Python.
    """

    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from LLM (e.g., additionalProperties)

    long_term_strategy: str = Field(
        ...,
        min_length=50,
        description="Year 1/2/3 strategic milestones (markdown, 3 sections, minimum 50 chars)"
    )
    conclusion_bottom_line: str = Field(
        ...,
        min_length=50,
        description="Bottom line summary (1 paragraph, minimum 50 chars)"
    )
    competitive_advantages: list[str] = Field(
        ...,
        min_length=2,
        description="2-4 key competitive advantages from SEO analysis (minimum 2)"
    )
    critical_success_factors: list[str] = Field(
        ...,
        min_length=3,
        description="3-4 critical success factors (minimum 3)"
    )

class ImplementationGuide(BaseModel):
    """
    Task 5 output: SEO Implementation Guide (3 new fields only).

    Contains technical implementation details that extend SEOStrategyReport.
    These fields will be merged with Task 4 output via Python.
    """

    model_config = ConfigDict(extra='ignore')

    universal_seo_elements: UniversalSEOElements = Field(
        ..., description="Universal SEO elements for every page (title, meta, canonical, OG, robots)"
    )
    page_type_implementations: list[PageTypeImplementation] = Field(
        ...,
        min_length=4,
        description="SEO templates for 4-6 key page types (minimum 4)"
    )
    schema_markup_strategy: SchemaMarkupStrategy = Field(
        ..., description="Schema markup strategy with JSON-LD examples and testing"
    )


# ========================================
# LIGHTWEIGHT TASK 5 OUTPUT MODELS FOR PYTHON HYDRATION
# ========================================
# These models capture only LLM-generated content (schema selections + strategic guidance).
# Python generates actual JSON-LD code using templates + solution context.


class SchemaSelectionLight(BaseModel):
    """
    Lightweight schema selection - Python generates actual JSON-LD.

    LLM selects which schemas to use and provides strategic rationale,
    but does NOT generate the actual JSON-LD code (which is 80% static).
    """

    model_config = ConfigDict(extra='ignore')

    schema_type: str = Field(
        ...,
        description="Schema.org type: Organization, Service, FAQPage, BreadcrumbList, Article, WebPage, Review, HowTo"
    )
    priority: int = Field(
        ..., ge=1, le=5, description="Implementation priority (1=critical, 5=nice-to-have)"
    )
    strategic_rationale: str = Field(
        ..., description="Why this schema matters for SEO (1-2 sentences)"
    )
    # For FAQPage - LLM suggests question topics (not full questions)
    suggested_questions: Optional[list[str]] = Field(
        default=None,
        description="For FAQPage: 3-5 question topics (not full questions, e.g., 'pricing', 'how it works')"
    )


class SchemaMarkupStrategyLight(BaseModel):
    """
    Lightweight schema strategy - Python generates JSON-LD code.

    LLM provides:
    - Strategic narrative (why schema matters)
    - Schema type selections with rationale
    - Implementation guidance

    Python hydrates with:
    - Actual JSON-LD code from templates
    """

    model_config = ConfigDict(extra='ignore')

    why_schema_matters: str = Field(
        ...,
        description="Benefits narrative (rich results, voice search, AI search, CTR) - 2-3 paragraphs, markdown"
    )
    selected_schemas: list[SchemaSelectionLight] = Field(
        ...,
        min_length=4,
        description="4-8 schema types to implement with strategic rationale"
    )
    implementation_method: str = Field(
        ...,
        description="JSON-LD format guidance, placement in <head>, why JSON-LD over Microdata - 2 paragraphs, markdown"
    )
    testing_validation: str = Field(
        ...,
        description="Testing tools and process (Google Rich Results Test, Schema Validator, Search Console) - 2 paragraphs, markdown"
    )


class ImplementationGuideLight(BaseModel):
    """
    Lightweight Task 5 output - schema_markup_strategy uses light model.

    LLM generates:
    - universal_seo_elements (same as before - pure strategic content)
    - page_type_implementations (same as before - pure strategic content)
    - schema_markup_strategy (LIGHT - schema selections + rationale only)

    Python hydrates:
    - schema_markup_strategy.schema_examples (JSON-LD code from templates)
    """

    model_config = ConfigDict(extra='ignore')

    universal_seo_elements: UniversalSEOElements = Field(
        ..., description="Universal SEO elements for every page (title, meta, canonical, OG, robots)"
    )
    page_type_implementations: list[PageTypeImplementation] = Field(
        ...,
        min_length=4,
        description="SEO templates for 4-6 key page types (minimum 4)"
    )
    schema_markup_strategy: SchemaMarkupStrategyLight = Field(
        ..., description="Schema strategy with type selections (Python generates JSON-LD code)"
    )
