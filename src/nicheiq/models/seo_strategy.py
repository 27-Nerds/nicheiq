"""
Pydantic models for SEO strategy (Stage 10 enhancement).

These models capture structured keyword data and narrative strategy sections
that combine into the comprehensive SEO section of the final report.
"""

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

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

    keyword: str = Field(..., description="The keyword phrase")
    search_volume: int = Field(..., description="Average monthly search volume from DataForSEO (single value)")
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

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

    category_name: str = Field(..., description="Category name (e.g., 'Education Documents')")
    total_volume: int = Field(..., description="Combined monthly search volume")
    keywords: list[CategoryKeywordEntry] = Field(
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

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

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

class PageTypeImplementation(BaseModel):
    """SEO implementation template for specific page type."""

    model_config = ConfigDict(extra='forbid')

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
    h2_structure: str = Field(
        ...,
        description="Recommended H2 sections (3-6 suggestions, markdown list)"
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

class SchemaExample(BaseModel):
    """Individual schema markup code example."""

    model_config = ConfigDict(extra='forbid')

    schema_type: str = Field(
        ...,
        description="Schema.org type (e.g., 'Organization', 'Service', 'FAQ', 'Article', 'BreadcrumbList')"
    )
    json_ld_code: str = Field(
        ...,
        description="JSON-LD code snippet for this schema type"
    )

class SchemaMarkupStrategy(BaseModel):
    """Schema markup implementation guide with code examples."""

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

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

class KeywordAnalysisResult(BaseModel):
    """
    Intermediate result from Task 1: Keyword Analysis & Tiering.

    The keyword_strategist agent analyzes enriched keywords and creates
    tiered opportunity structure with competitive positioning.
    """

    model_config = ConfigDict(extra='forbid')

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
        ..., description="High volume + low competition keywords (3-5 keywords)"
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

    # Metadata and findings
    total_keywords_analyzed: int = Field(..., description="Total number of keywords analyzed")
    total_monthly_volume: int = Field(..., description="Total monthly search volume across all keywords")
    key_findings: list[str] = Field(..., description="3-5 bullet points highlighting key SEO findings")
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

        total_tiered = tier_0_count + tier_1_count + tier_2_count + tier_3_count + tier_4_count

        # Tiered logging levels for visibility (no pipeline failure)
        if self.total_keywords_analyzed > 50:
            keyword_utilization = total_tiered / self.total_keywords_analyzed
            tier_breakdown = (
                f"[T0: {tier_0_count}, T1: {tier_1_count}, T2: {tier_2_count}, "
                f"T3: {tier_3_count}, T4: {tier_4_count}]"
            )

            if keyword_utilization < 0.5:
                logger.error(
                    f"⚠️ CRITICAL KEYWORD LOSS: Only {keyword_utilization:.1%} utilization "
                    f"({total_tiered}/{self.total_keywords_analyzed} keywords tiered). "
                    f"Task 1 filtering was too aggressive - expand Tier 4 categories. {tier_breakdown}"
                )
            elif keyword_utilization < 0.7:
                logger.warning(
                    f"⚠️ Keyword utilization low: {total_tiered}/{self.total_keywords_analyzed} "
                    f"({keyword_utilization:.1%}). Consider expanding Tier 4 categories. {tier_breakdown}"
                )
            else:
                logger.info(
                    f"✅ Keyword utilization: {keyword_utilization:.1%} "
                    f"({total_tiered}/{self.total_keywords_analyzed} keywords tiered). {tier_breakdown}"
                )

        return self

class ContentStrategyResult(BaseModel):
    """
    Intermediate result from Task 2: Content & Technical Strategy.

    The content_strategist agent develops content strategy, topic clusters,
    and technical SEO recommendations based on keyword analysis.
    """

    model_config = ConfigDict(extra='forbid')

    # Content strategy
    content_strategy: str = Field(
        ..., description="Comprehensive content strategy with numbered sections (markdown, 4-6 paragraphs)"
    )
    topic_clusters: Optional[list[TopicCluster]] = Field(
        default=None, description="Content pillars/clusters (3-5 clusters)"
    )

    # Technical SEO
    technical_seo_recommendations: str = Field(
        ..., description="Technical SEO recommendations with URL structure, schema markup, code examples (markdown, 3-5 sections)"
    )
    keyword_driven_site_architecture: Optional[KeywordDrivenSiteArchitecture] = Field(
        default=None, description="Site structure organized around keyword clusters and search intent patterns"
    )
    keyword_based_page_types: Optional[list[KeywordBasedPageType]] = Field(
        default=None, description="Page types derived from keyword analysis (4-8 page types)"
    )

class ImplementationPlanResult(BaseModel):
    """
    Intermediate result from Task 3: Implementation Planning.

    The seo_specialist agent creates phased implementation roadmap with
    metrics, timeline, budget, and risk mitigation strategies.
    """

    model_config = ConfigDict(extra='forbid')

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

    model_config = ConfigDict(extra='forbid')

    long_term_strategy: str = Field(
        ..., description="Year 1/2/3 strategic milestones (markdown, 3 sections)"
    )
    conclusion_bottom_line: str = Field(
        ..., description="Bottom line summary (1 paragraph)"
    )
    competitive_advantages: list[str] = Field(
        ..., description="2-4 key competitive advantages from SEO analysis"
    )
    critical_success_factors: list[str] = Field(
        ..., description="3-4 critical success factors"
    )

class ImplementationGuide(BaseModel):
    """
    Task 5 output: SEO Implementation Guide (3 new fields only).

    Contains technical implementation details that extend SEOStrategyReport.
    These fields will be merged with Task 4 output via Python.
    """

    model_config = ConfigDict(extra='forbid')

    universal_seo_elements: UniversalSEOElements = Field(
        ..., description="Universal SEO elements for every page (title, meta, canonical, OG, robots)"
    )
    page_type_implementations: list[PageTypeImplementation] = Field(
        ..., description="SEO templates for 4-6 key page types"
    )
    schema_markup_strategy: SchemaMarkupStrategy = Field(
        ..., description="Schema markup strategy with JSON-LD examples and testing"
    )
