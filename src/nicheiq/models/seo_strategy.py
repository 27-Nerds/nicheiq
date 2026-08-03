"""
Pydantic models for SEO strategy (Stage 10 enhancement).

These models capture structured keyword data and narrative strategy sections
that combine into the comprehensive SEO section of the final report.
"""

from enum import Enum
from typing import Any, Optional

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
    Conceptual keyword from Phase 6a hybrid seed generation (before DataForSEO enrichment).

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
                f"Review Phase 6a prompt if many keywords exceed 5 words."
            )
        return v

class ConceptualTopicCluster(BaseModel):
    """Topic cluster for organizing keywords strategically (Phase 6a output)."""

    model_config = ConfigDict(extra='ignore')

    name: str = Field(..., description="Cluster name (e.g., 'International Shipping', 'Customs')")
    description: str = Field(..., description="Brief description of this topic area")
    strategic_importance: int = Field(
        ..., ge=1, le=5, description="Importance for SEO strategy (1=critical, 5=nice-to-have)"
    )

class ExpandedKeywordList(BaseModel):
    """
    Result of Phase 6a hybrid seed keyword generation.
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

    # SEO Difficulty (from DataForSEO Labs bulk_keyword_difficulty API)
    # This is the REAL SEO difficulty (backlink strength of top 10), NOT Google Ads competition
    keyword_difficulty: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "SEO difficulty score (0-100, lower=easier to rank). "
            "Based on backlink strength of top 10 results. "
            "Timeline: <25=1-3mo, 25-40=3-6mo, 40-60=6-9mo, 60-75=9-15mo, >75=12-18+mo"
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
        ..., min_length=2, description="Example target keywords this page type addresses"
    )
    primary_intent: str = Field(
        ..., description="Primary search intent: 'commercial', 'informational', 'navigational', 'transactional'"
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



class SeoKillQuestion(BaseModel):
    """Deterministic SEO-thesis stress test for a distribution_seo idea (no LLM).

    Answers the angle's kill-question — "is there a real indexable-page ceiling, are the pages
    winnable on a new domain, and is the page universe thin enough to risk a scaled-content penalty?"
    Computed from the already-validated keyword set (search_volume + keyword_difficulty) plus a small
    SERP sample. Surfaces the report's biggest distribution_seo blind spot: ideas that score great on
    keyword volume but have no real page universe / would face a Google penalty.
    """
    model_config = ConfigDict(extra='ignore')

    indexable_page_ceiling: int = Field(
        ..., description="Distinct non-zero-volume search intents — the realistic programmatic page universe")
    head_count: int = Field(0, description="Intents with monthly volume >= 1000")
    mid_count: int = Field(0, description="Intents with monthly volume 100-999")
    tail_count: int = Field(0, description="Intents with monthly volume 1-99")
    median_keyword_difficulty: Optional[float] = Field(
        None, description="Median KD (0-100) across the page universe")
    winnable_pages: int = Field(
        0, description="Pages with KD below the new-domain-rankable threshold (realistically winnable)")
    kd_sample_size: int = Field(
        0, description=("Page-universe intents that carried a keyword_difficulty value — the KD-coverage "
                        "denominator. DataForSEO omits KD for many (often easy) long-tail intents, so when "
                        "this is small relative to the ceiling, winnable_pages/median_keyword_difficulty are "
                        "unreliable and the verdict floor abstains."))
    forum_soft_serp_share: Optional[float] = Field(
        None, description=("UPSIDE-ONLY signal: fraction of sampled SERPs whose top results are UGC/forum "
                           "domains (= extra ranking room). Presence is a bonus; 0.0 is NEUTRAL (the default "
                           "for professional/legal niches), NOT 'unwinnable'. Does not feed the verdict."))
    institutional_serp_share: Optional[float] = Field(
        None, description=("CAUTION-ONLY signal: fraction of sampled SERPs DOMINATED (>=3 of top 5) by "
                           "institutional domains (.gov/.edu/.mil/Wikipedia) — a ranking headwind that "
                           "keyword-difficulty understates. High share flags 'verify winnability'; it is "
                           "NOT a kill and does NOT feed the verdict or the winnable count."))
    serp_sampled: int = Field(0, description="Number of representative queries sampled in the SERP")
    penalty_risk_flag: bool = Field(
        False, description="High page count + thin (tail-heavy) universe -> scaled-content-abuse penalty risk")
    # On-idea slice (Q-049 batch-1, display + telemetry only — never feeds the verdict):
    # the page universe restricted to idea-intent keywords (grade >= keyword_relevance_min_grade).
    on_idea_page_ceiling: Optional[int] = Field(
        default=None, ge=0,
        description=(
            "Distinct non-zero-volume intents whose idea_intent_grade >= keyword_relevance_min_grade "
            "— the ON-IDEA slice of indexable_page_ceiling. None when the intent grader covered "
            "<80% of the keyword set (coverage guard)."
        ),
    )
    on_idea_winnable: Optional[int] = Field(
        default=None, ge=0,
        description=(
            "On-idea pages (grade >= min_grade) with KD below the new-domain-rankable threshold. "
            "None under the coverage guard."
        ),
    )
    verdict: str = Field("", description="One-line human read of whether the SEO thesis holds")
    rationale: str = Field("", description="The evidence behind the verdict")


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
    total_keywords_analyzed: int = Field(
        ..., description="Total number of keywords with measurable search volume (after expansion)"
    )
    total_monthly_volume: int = Field(
        ..., description="Total monthly search volume across all keywords"
    )
    # Three-band idea-intent volume honesty (Q-049 batch-1). Computed in code from the
    # idea_intent_grade stamps on the enriched keyword set, ONLY when graded coverage >= 80%;
    # otherwise all three stay None and consumers keep exactly today's behavior.
    offtopic_volume_share: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Share of total_monthly_volume carried by grade-0 (OFFTOPIC) keywords. None when "
            "the intent grader did not cover >=80% of the keyword set."
        ),
    )
    category_volume_share: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "Share of total_monthly_volume carried by grade-1 (category-reach) plus ungraded "
            "keywords (ungraded rows are RETAINED fail-open and counted as category reach per "
            "the grader's caller contract). None under the coverage guard."
        ),
    )
    idea_intent_monthly_volume: Optional[int] = Field(
        default=None, ge=0,
        description=(
            "Monthly search volume carried by idea-intent keywords (grade >= "
            "keyword_relevance_min_grade). None under the coverage guard. total_monthly_volume "
            "is deliberately UNCHANGED — this is the honest subset, not a replacement."
        ),
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
        ..., description="Quick wins strategy narrative for Tier 1 (1-2 paragraphs, markdown)"
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

    # key_metrics_to_track removed - generic boilerplate
    # risk_mitigation removed - generic boilerplate

    # ========================================
    # BUDGET ALLOCATION
    # ========================================
    budget_allocation: Optional[str] = Field(
        default=None,
        description="Budget recommendations with options (markdown, Option A/B/C)"
    )

    # SEO kill-question: deterministic thesis stress-test, attached only for distribution_seo ideas.
    seo_kill_question: Optional["SeoKillQuestion"] = Field(
        default=None,
        description="Deterministic SEO-thesis stress test (page ceiling, winnable pages, penalty risk) "
                    "for a distribution_seo idea. None for other angles or when disabled."
    )

    # conclusion_bottom_line removed - generic boilerplate
    # next_steps_checklist removed - generic boilerplate

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
        default_factory=list,
        description="Premium keyword selections. Empty if no keywords meet Tier 0 threshold (opp_score > 200)."
    )
    tier_0_strategy: str = Field(
        default="No Tier 0 premium keywords identified - all keywords have opportunity scores below 200.",
        description="Strategy narrative for Tier 0 premium keywords (1 paragraph max)"
    )


class Tier1LightResult(BaseModel):
    """
    Lightweight Task 1a-ii output - Python hydrates stats from CSV.

    LLM outputs only keyword selections + strategies, not stats.
    """

    model_config = ConfigDict(extra='ignore')

    tier_1_keywords: list[LightweightKeywordSelection] = Field(
        default_factory=list,
        description="Quick win keyword selections. Empty if no keywords meet Tier 1 threshold (opp_score 100-200)."
    )
    tier_1_quick_win_strategy: str = Field(
        default="No Tier 1 quick win keywords identified - all keywords have opportunity scores outside 100-200 range.",
        description="Strategy narrative for Tier 1 quick wins (1 paragraph max)"
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

    @model_validator(mode='before')
    @classmethod
    def filter_invalid_category_groups(cls, data: Any) -> Any:
        """Filter out category groups with empty/missing keywords before validation."""
        if isinstance(data, dict):
            groups = data.get('tier_4_category_groups')
            if groups is not None and isinstance(groups, list):
                filtered = [
                    g for g in groups
                    if isinstance(g, dict) and g.get('keywords') and len(g['keywords']) > 0
                ]
                data['tier_4_category_groups'] = filtered if filtered else None
        return data


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
    Lightweight page type for LLM output.

    LLM outputs only strategic content (page type definitions, schema types).
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
        ..., min_length=2, description="Example target keywords"
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

    @model_validator(mode='before')
    @classmethod
    def filter_invalid_page_types(cls, data: Any) -> Any:
        """Filter out page types with fewer than 2 example_keywords before validation."""
        if isinstance(data, dict):
            page_types = data.get('keyword_based_page_types')
            if page_types is not None and isinstance(page_types, list):
                filtered = [
                    pt for pt in page_types
                    if isinstance(pt, dict)
                    and isinstance(pt.get('example_keywords'), list)
                    and len(pt['example_keywords']) >= 2
                ]
                data['keyword_based_page_types'] = filtered if filtered else None
        return data


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

    # ========================================
    # DIFFICULTY METRICS (Python-calculated from keyword_difficulty field)
    # ========================================
    # These aggregate metrics enable data-driven timeline estimates in Task 3

    avg_difficulty_tier0: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Average keyword_difficulty for Tier 0 keywords"
    )
    avg_difficulty_tier1: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Average keyword_difficulty for Tier 1 keywords"
    )
    avg_difficulty_tier2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Average keyword_difficulty for Tier 2 keywords"
    )
    difficulty_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Weighted average difficulty across all tiers (Tier weights: T0=0.4, T1=0.4, T2=0.2)"
    )
    timeline_multiplier: Optional[float] = Field(
        default=None,
        ge=0.5,
        le=2.0,
        description=(
            "Timeline adjustment based on difficulty_score. "
            "<0.75=accelerated (low difficulty), 0.75-1.25=standard, >1.25=extended (high difficulty)"
        )
    )
    tier1_ranking_time: Optional[str] = Field(
        default=None,
        description="Estimated time to rank for Tier 1 keywords (e.g., '3-6 months')"
    )
    tier2_ranking_time: Optional[str] = Field(
        default=None,
        description="Estimated time to rank for Tier 2 keywords (e.g., '6-9 months')"
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
    # keyword_driven_site_architecture removed - never rendered, overlaps with keyword_based_page_types
    keyword_based_page_types: Optional[list[KeywordBasedPageType]] = Field(
        default=None,
        min_length=2,
        description="Page types derived from keyword analysis (4-8 page types, minimum 2)"
    )

    @model_validator(mode='before')
    @classmethod
    def filter_invalid_page_types(cls, data: Any) -> Any:
        """Filter out page types with fewer than 2 example_keywords before validation."""
        if isinstance(data, dict):
            page_types = data.get('keyword_based_page_types')
            if page_types is not None and isinstance(page_types, list):
                filtered = [
                    pt for pt in page_types
                    if isinstance(pt, dict)
                    and isinstance(pt.get('example_keywords'), list)
                    and len(pt['example_keywords']) >= 2
                ]
                # Field has min_length=2, so set None if fewer than 2 valid items remain
                data['keyword_based_page_types'] = filtered if len(filtered) >= 2 else None
        return data

class ImplementationPlanResult(BaseModel):
    """
    Intermediate result from Task 3: Implementation Planning.

    The seo_specialist agent creates phased implementation roadmap with
    budget allocation.
    """

    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from LLM (e.g., additionalProperties)

    # Implementation
    implementation_roadmap: str = Field(
        ..., description="Phased implementation plan (markdown, 3-4 phases with timelines and targets)"
    )
    # key_metrics_to_track removed - generic boilerplate
    # expected_timeline removed - duplicates implementation_roadmap
    # next_steps_checklist removed - generic boilerplate

    # Optional planning elements
    # risk_mitigation removed - generic boilerplate
    budget_allocation: Optional[str] = Field(
        default=None, description="Budget recommendations with options (markdown, Option A/B/C)"
    )

# FinalSynthesis class deleted - only had conclusion_bottom_line (generic boilerplate)


# SyncFinalOutputs, ImplementationGuide, and all Light models (UniversalSEOElementsLight,
# PageTypeImplementationLight, SchemaSelectionLight, SchemaMarkupStrategyLight,
# ImplementationGuideLight) removed - Task 5/6 deleted from crew, technical SEO
# is now handled via Task 2's technical_seo_recommendations markdown field
