"""
SEOStrategyCrew - Stage 9: Integrated Keyword Research + SEO Strategy
Multi-agent crew that performs keyword expansion and develops comprehensive SEO strategy.
"""

import re
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.competitor import CompetitiveAnalysisResult
from ..models.pain_point import PainPointAnalysisResult
from ..models.seo_strategy import (
    CategoryKeywordEntry,
    CategoryKeywordGroup,
    CategoryLightGroup,
    CategoryLightResult,
    CategoryTierResult,
    ContentStrategyResult,
    ContentStrategyResultLight,
    ExpandedKeywordList,
    GeographicKeywordEntry,
    GeographicKeywordGroup,
    GeographicLightGroup,
    GeographicLightResult,
    GeographicTierResult,
    HighPriorityTierResult,
    ImplementationPlanResult,
    KeywordAnalysisResult,
    KeywordBasedPageType,
    KeywordBasedPageTypeLight,
    # KeywordDrivenSiteArchitecture removed - never rendered
    KeywordSummaryResult,
    LightweightKeywordSelection,
    PremiumTierResult,
    # SectionKeywordMapping removed - never rendered
    SEOStrategyReport,
    StrategicLightResult,
    Tier0LightResult,
    Tier1LightResult,
    TieredKeyword,
    TopicCluster,
    TopicClusterLight,
)
# Removed: ImplementationGuide, ImplementationGuideLight, PageTypeImplementation,
# PageTypeImplementationLight, SchemaMarkupStrategy, SyncFinalOutputs,
# UniversalSEOElements, UniversalSEOElementsLight (Task 5/6 deleted)
from ..tools.dataforseo_tool import DataForSEOExpandTool, DataForSEOSearchVolumeTool
from ..utils.generation import KeywordSeedGenerator
from ..utils.validation import (
    validate_category_tier_output,
    validate_content_strategy_output,
    validate_geographic_tier_output,
    validate_implementation_plan_output,
    validate_keyword_summary,
    validate_strategic_tier_output,
)
# Removed: validate_implementation_guide_light_output (Task 5 deleted)

if TYPE_CHECKING:
    from ..models.competitor import CompetitiveLandscape
    from ..models.research_state import AudienceMappingResult, NicheContext
    from ..models.solution_idea import SolutionIdea


# ========================================
# HYDRATION UTILITIES FOR LIGHTWEIGHT OUTPUT PATTERN
# ========================================
# These functions hydrate lightweight LLM output with stats from CSV lookup.


def _build_keyword_lookup(enriched_keywords: list[dict]) -> dict[str, dict]:
    """
    Build keyword -> stats lookup from enriched CSV data.

    Args:
        enriched_keywords: List of keyword dicts from CSV parsing

    Returns:
        Dict mapping lowercase keyword to full stats dict
    """
    # Defensive: skip entries missing 'keyword' key to avoid KeyError
    return {
        kw['keyword'].lower().strip(): kw
        for kw in enriched_keywords
        if 'keyword' in kw and kw['keyword']
    }


def _hydrate_tiered_keyword(
    light: LightweightKeywordSelection,
    lookup: dict[str, dict],
    tier: int
) -> TieredKeyword | None:
    """
    Hydrate lightweight keyword selection with stats from CSV lookup.

    Args:
        light: Lightweight keyword selection from LLM
        lookup: Keyword -> stats lookup dict
        tier: Tier assignment (0, 1, 2)

    Returns:
        Full TieredKeyword with stats hydrated from CSV, or None when the
        keyword has NO CSV entry at all (LLM hallucination) — such keywords
        are DROPPED rather than shipped with fabricated default stats
        (volume=0, "MEDIUM (50)") that pollute tier tables and avg_competition.
        Keywords present in the CSV with individual fields missing keep
        per-field defaults: they are real, just partially measured.
    """
    kw_key = light.keyword.lower().strip()
    stats = lookup.get(kw_key)

    if stats is None:
        logger.warning(
            f"⚠️ HYDRATION: Keyword '{light.keyword}' not found in CSV lookup "
            f"(Tier {tier}) - dropping (likely LLM hallucination; fabricated "
            f"default stats would pollute tier tables)."
        )
        return None

    # Extract stats with warnings for missing values
    search_volume = stats.get('search_volume')
    if search_volume is None:
        logger.warning(f"⚠️ HYDRATION: Missing search_volume for '{light.keyword}', defaulting to 0")
        search_volume = 0

    competition_index = stats.get('competition_index')
    if competition_index is None:
        logger.debug(f"Missing competition_index for '{light.keyword}', defaulting to 50")
        competition_index = 50

    competition_level = stats.get('competition_level')
    if competition_level is None:
        competition_level = 'MEDIUM'

    opp_score = stats.get('opportunity_score')
    if opp_score is None:
        opp_score = search_volume / max(competition_index, 1) if competition_index else None
        logger.debug(f"Calculated opportunity_score for '{light.keyword}': {opp_score}")

    # Extract keyword_difficulty (SEO difficulty, NOT Google Ads competition)
    keyword_difficulty = stats.get('keyword_difficulty')  # May be None if not in top 1000

    tier_rationale = (
        f"Volume: {search_volume}, Comp: {competition_index}, Opp: {opp_score:.1f}"
        if opp_score else f"Volume: {search_volume}, Comp: {competition_index}"
    )
    # Add difficulty to rationale if available
    if keyword_difficulty is not None:
        tier_rationale += f", Diff: {keyword_difficulty:.0f}"

    return TieredKeyword(
        keyword=light.keyword,
        search_volume=search_volume,
        competition=f"{competition_level} ({competition_index})",
        opportunity_score=opp_score,
        strategy=light.strategy,
        intent=light.intent,
        tier=tier,
        tier_rationale=tier_rationale,
        keyword_difficulty=keyword_difficulty,
    )


def _hydrate_geographic_group(
    light_group: GeographicLightGroup,
    lookup: dict[str, dict]
) -> GeographicKeywordGroup:
    """
    Hydrate geographic group with stats from CSV lookup.

    Args:
        light_group: Lightweight geographic group from LLM
        lookup: Keyword -> stats lookup dict

    Returns:
        Full GeographicKeywordGroup with stats hydrated from CSV
    """
    keywords = []
    total_volume = 0
    missing_count = 0

    for entry in light_group.keywords:
        kw_key = entry.keyword.lower().strip()
        stats = lookup.get(kw_key)

        if stats is None:
            logger.warning(
                f"⚠️ HYDRATION: Geographic keyword '{entry.keyword}' not found in CSV lookup "
                f"(region: {light_group.region_name}). Using defaults."
            )
            missing_count += 1
            stats = {}

        vol = stats.get('search_volume')
        if vol is None:
            logger.debug(f"Missing search_volume for geographic keyword '{entry.keyword}', defaulting to 0")
            vol = 0

        total_volume += vol
        keywords.append(GeographicKeywordEntry(
            city=entry.city,
            keyword=entry.keyword,
            search_volume=vol,
            notes=entry.notes,
        ))

    if missing_count > 0:
        logger.warning(
            f"⚠️ HYDRATION SUMMARY: {missing_count}/{len(light_group.keywords)} keywords "
            f"missing from CSV in geographic group '{light_group.region_name}'"
        )

    return GeographicKeywordGroup(
        region_name=light_group.region_name,
        total_volume=total_volume,
        competition_level=light_group.competition_level,
        keywords=keywords,
        strategy_notes=light_group.strategy_notes,
    )


def _hydrate_category_group(
    light_group: CategoryLightGroup,
    lookup: dict[str, dict]
) -> CategoryKeywordGroup:
    """
    Hydrate category group with stats from CSV lookup.

    Args:
        light_group: Lightweight category group from LLM
        lookup: Keyword -> stats lookup dict

    Returns:
        Full CategoryKeywordGroup with stats hydrated from CSV
    """
    keywords = []
    total_volume = 0
    missing_count = 0

    for entry in light_group.keywords:
        kw_key = entry.keyword_name.lower().strip()
        stats = lookup.get(kw_key)

        if stats is None:
            logger.warning(
                f"⚠️ HYDRATION: Category keyword '{entry.keyword_name}' not found in CSV lookup "
                f"(category: {light_group.category_name}). Using defaults."
            )
            missing_count += 1
            stats = {}

        vol = stats.get('search_volume')
        if vol is None:
            vol = 0

        cpc = stats.get('cpc')
        if cpc is None:
            cpc = 0.0  # Silent default for CPC - less critical

        total_volume += vol
        keywords.append(CategoryKeywordEntry(
            keyword_name=entry.keyword_name,
            search_volume=vol,
            competition=stats.get('competition_level'),
            cpc=cpc,
        ))

    if missing_count > 0:
        logger.warning(
            f"⚠️ HYDRATION SUMMARY: {missing_count}/{len(light_group.keywords)} keywords "
            f"missing from CSV in category group '{light_group.category_name}'"
        )

    return CategoryKeywordGroup(
        category_name=light_group.category_name,
        total_volume=total_volume,
        keywords=keywords,
        strategy_recommendation=light_group.strategy_recommendation,
    )


def _hydrate_remaining_keywords(
    remaining: list[dict],
    tier: int,
    tier_strategy: str | None,
    lookup: dict[str, dict],
) -> list[TieredKeyword]:
    """
    Create TieredKeyword objects for keywords not sent to LLM.

    Uses tier-level strategy template from LLM output. This function
    hydrates remaining keywords (those exceeding LLM limit) with the
    tier strategy, ensuring no hallucination risk.

    Args:
        remaining: List of keyword dicts not sent to LLM
        tier: Tier number (1, 2, 3, 4)
        tier_strategy: Tier-level strategy narrative from LLM output
        lookup: Keyword -> stats lookup dict

    Returns:
        List of TieredKeyword objects with Python-hydrated strategies
    """
    tier_names = {
        0: "TIER_0_PREMIUM",
        1: "TIER_1_QUICK_WIN",
        2: "TIER_2_STRATEGIC",
        3: "TIER_3_GEOGRAPHIC",
        4: "TIER_4_CATEGORY",
    }

    # Truncate strategy to 150 chars for Python-assigned keywords
    strategy_prefix = "[Auto-tiered] "
    if tier_strategy:
        # Take first 150 chars of tier strategy, add ellipsis if truncated
        truncated_strategy = tier_strategy[:150].strip()
        if len(tier_strategy) > 150:
            truncated_strategy += "..."
        strategy_text = f"{strategy_prefix}{truncated_strategy}"
    else:
        strategy_text = f"{strategy_prefix}Applied tier-level strategy programmatically"

    results = []
    for kw in remaining:
        keyword_text = kw.get("keyword", "")
        kw_key = keyword_text.lower().strip()
        stats = lookup.get(kw_key, {})

        # Extract stats with defaults
        search_volume = stats.get("search_volume") or kw.get("search_volume") or 0
        competition_index = stats.get("competition_index") or kw.get("competition_index") or 50
        competition_level = stats.get("competition_level") or kw.get("competition_level") or "MEDIUM"
        opp_score = stats.get("opportunity_score") or kw.get("opportunity_score")

        # Calculate opp_score if not present
        if opp_score is None:
            opp_score = search_volume / max(competition_index, 1)

        tier_rationale = (
            f"Python-hydrated: Vol={search_volume}, Comp={competition_index}, "
            f"Opp={opp_score:.1f} (not sent to LLM)"
        )

        results.append(TieredKeyword(
            keyword=keyword_text,
            search_volume=search_volume,
            competition=f"{competition_level} ({competition_index})",
            opportunity_score=opp_score,
            tier=tier,
            strategy=strategy_text,
            intent=stats.get("search_intent", "informational"),
            tier_rationale=tier_rationale,
        ))

    return results


# ========================================
# TASK 2 HYDRATION UTILITIES
# ========================================
# Hydrate ContentStrategyResultLight with numeric data from CSV lookup.


def _hydrate_topic_cluster(
    light: TopicClusterLight,
    lookup: dict[str, dict]
) -> TopicCluster:
    """
    Hydrate lightweight topic cluster with real search volumes from CSV.

    Args:
        light: Lightweight topic cluster from LLM
        lookup: Keyword -> stats lookup dict

    Returns:
        Full TopicCluster with calculated volumes
    """
    # Sum volumes for primary + supporting keywords
    total_volume = 0
    missing_keywords = []

    # Check primary keyword
    primary_key = light.primary_keyword.lower().strip()
    primary_stats = lookup.get(primary_key)
    if primary_stats:
        total_volume += primary_stats.get('search_volume', 0) or 0
    else:
        missing_keywords.append(light.primary_keyword)

    # Check supporting keywords
    for kw in light.supporting_keywords:
        kw_key = kw.lower().strip()
        stats = lookup.get(kw_key)
        if stats:
            total_volume += stats.get('search_volume', 0) or 0
        else:
            missing_keywords.append(kw)

    if missing_keywords:
        logger.warning(
            f"⚠️ HYDRATION: Topic cluster '{light.cluster_name}' has {len(missing_keywords)} "
            f"keywords not found in CSV: {missing_keywords[:5]}{'...' if len(missing_keywords) > 5 else ''}"
        )

    # Calculate traffic potential (10-30% of volume is typical for ranking pages)
    traffic_low = int(total_volume * 0.10)
    traffic_high = int(total_volume * 0.30)
    traffic_potential = f"{traffic_low:,}-{traffic_high:,} visits/month"

    return TopicCluster(
        cluster_name=light.cluster_name,
        primary_keyword=light.primary_keyword,
        supporting_keywords=light.supporting_keywords,
        total_monthly_volume=total_volume,  # Python-calculated
        content_recommendation=light.content_recommendation,
        estimated_traffic_potential=traffic_potential,  # Python-calculated
        priority=light.priority,
    )


def _hydrate_page_type(
    light: KeywordBasedPageTypeLight,
    lookup: dict[str, dict],
) -> KeywordBasedPageType:
    """
    Hydrate lightweight page type to full model.

    Args:
        light: Lightweight page type from LLM
        lookup: Keyword -> stats lookup dict

    Returns:
        Full KeywordBasedPageType
    """
    return KeywordBasedPageType(
        page_type_name=light.page_type_name,
        url_pattern=light.url_pattern,
        target_keyword_cluster=light.target_keyword_cluster,
        example_keywords=light.example_keywords,
        primary_intent=light.primary_intent,
        priority=light.priority,
        required_schema=light.required_schema,
        seo_optimization_notes=light.seo_optimization_notes,
    )


def _hydrate_content_strategy(
    light: ContentStrategyResultLight,
    lookup: dict[str, dict],
) -> ContentStrategyResult:
    """
    Hydrate lightweight Task 2 output with numeric data from CSV.

    Args:
        light: Lightweight content strategy from LLM
        lookup: Keyword -> stats lookup dict

    Returns:
        Full ContentStrategyResult with calculated volumes
    """
    # Hydrate topic clusters
    hydrated_clusters = None
    if light.topic_clusters:
        hydrated_clusters = [
            _hydrate_topic_cluster(cluster, lookup)
            for cluster in light.topic_clusters
        ]
        logger.info(
            f"✅ Hydrated {len(hydrated_clusters)} topic clusters with search volumes"
        )

    # Hydrate page types
    hydrated_page_types = None
    if light.keyword_based_page_types:
        hydrated_page_types = [
            _hydrate_page_type(pt, lookup)
            for pt in light.keyword_based_page_types
        ]
        logger.info(
            f"✅ Hydrated {len(hydrated_page_types)} page types"
        )

    # keyword_driven_site_architecture removed - never rendered, overlaps with keyword_based_page_types

    return ContentStrategyResult(
        content_strategy=light.content_strategy,
        topic_clusters=hydrated_clusters,
        technical_seo_recommendations=light.technical_seo_recommendations,
        # keyword_driven_site_architecture removed
        keyword_based_page_types=hydrated_page_types,
    )


# Task 5 hydration functions removed - technical SEO now in Task 2's technical_seo_recommendations


@CrewBase
class SEOStrategyCrew:
    """
    Specialized crew for integrated keyword research and SEO strategy development.
    Performs keyword expansion using DataForSEO and creates actionable SEO implementation plan.

    Architecture:
    - 3 agents working in pipeline
    - Keyword Strategist expands seed keywords and creates tiered opportunity structure
    - Content Strategist develops content and cluster plan
    - SEO Specialist creates technical roadmap and implementation plan
    """

    agents_config = "config/seo_strategy_agents.yaml"
    tasks_config = "config/seo_strategy_tasks.yaml"

    # ========================================
    # KEYWORD LIMITS PER TIER (sent to LLM)
    # ========================================
    # Limits the number of keywords sent to LLM to optimize token usage.
    # Python hydrates remaining keywords using tier-level strategy.
    # Selection: Sort by opportunity_score descending (highest value first)

    TIER_0_LLM_LIMIT: int | None = None  # No limit - send all premium (rare and critical)
    TIER_1_LLM_LIMIT: int = 25           # Quick wins need strategic analysis
    TIER_2_LLM_LIMIT: int = 30           # Strategic tier benefits from context
    TIER_3_LLM_LIMIT: int = 40           # Geographic needs regional diversity
    TIER_4_LLM_LIMIT: int = 50           # Category tier is programmatic-focused

    def __init__(
        self,
        niche: str,
        selected_solution: "SolutionIdea",
        selection_rationale: str,
        competitive_analysis: CompetitiveAnalysisResult,
        pain_points: PainPointAnalysisResult | None = None,
        niche_context: "NicheContext | None" = None,
        allowed_project_types: list[str] | None = None,
        audience_mapping: "AudienceMappingResult | None" = None,
        covered_keywords: list[str] | None = None,
        job_id: str | None = None,
    ):
        """
        Initialize SEOStrategyCrew with SELECTED solution focus.

        The keyword_strategist agent will:
        1. Generate seed keywords specifically for the selected solution
        2. Expand seeds using DataForSEO tool
        3. Analyze and create tiered strategy focused on this solution

        Args:
            niche: The niche/market area being researched
            selected_solution: THE SINGLE SOLUTION to focus SEO strategy on (from Stage 5)
            selection_rationale: Why this solution was selected over alternatives
            competitive_analysis: Competitive landscape from Stage 8
            pain_points: Optional pain point analysis from Stage 6
            niche_context: Optional niche context with market_segments and industry_boundaries
            allowed_project_types: Optional project type constraints from user
            audience_mapping: Optional audience intelligence from Stage 6.5 (common_vocabulary for keywords)
            covered_keywords: Optional list of keyword strings already covered by anchor enrichment
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization
        self.niche = niche
        self.selected_solution = selected_solution
        self.selection_rationale = selection_rationale
        self.competitive_analysis = competitive_analysis
        self.pain_points = pain_points
        self.niche_context = niche_context
        self.allowed_project_types = allowed_project_types
        self.audience_mapping = audience_mapping
        self.covered_keywords = covered_keywords
        self.job_id = job_id

        # Initialize DataForSEO tools for keyword expansion and search volume
        self.dataforseo_expand_tool = DataForSEOExpandTool()
        self.dataforseo_volume_tool = DataForSEOSearchVolumeTool()

        # Initialize knowledge sources for keyword research
        self.knowledge_sources = []

        # Add pain point knowledge source if available (for user language)
        if pain_points and pain_points.pain_points:
            pain_point_content = self._prepare_pain_point_keywords_content()

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.pain_point_knowledge = StringKnowledgeSource(
                content=pain_point_content,
                chunk_size=1000,  # Smaller chunks for focused keyword extraction
                chunk_overlap=150,  # Moderate overlap
            )
            self.knowledge_sources.append(self.pain_point_knowledge)
            logger.info(
                f"Pain point keyword knowledge source created ({len(pain_point_content)} chars) "
                f"for user language extraction"
            )

        # Add competitive intelligence if available (for alternative keywords)
        competitive_landscape = self._find_solution_landscape()
        if competitive_landscape and competitive_landscape.competitors:
            comp_content = self._prepare_competitive_keywords_content(competitive_landscape)

            from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

            self.competitive_knowledge = StringKnowledgeSource(
                content=comp_content,
                chunk_size=800,  # Tight chunks for specific competitor data
                chunk_overlap=100,
            )
            self.knowledge_sources.append(self.competitive_knowledge)
            logger.info(
                f"Competitive keyword knowledge source created ({len(comp_content)} chars) "
                f"with {len(competitive_landscape.competitors)} competitors"
            )

        logger.info(
            f"SEOStrategyCrew initialized for selected solution: {selected_solution.solution_name}"
            f"{' with ' + str(len(self.knowledge_sources)) + ' knowledge source(s)' if self.knowledge_sources else ''}"
        )

    def _find_solution_landscape(self) -> "CompetitiveLandscape | None":
        """
        Find competitive landscape for the selected solution.

        Returns:
            CompetitiveLandscape for selected solution, or None if not found
        """
        for landscape in self.competitive_analysis.solution_landscapes:
            if landscape.solution_name == self.selected_solution.solution_name:
                return landscape
        return None

    def _prepare_pain_point_keywords_content(self) -> str:
        """
        Format pain points for keyword research with focus on user language.

        Extracts actual user phrasing from pain point quotes to identify
        natural search language patterns for keyword generation.

        Returns:
            Formatted string with pain point user language for keyword mining
        """
        formatted = []

        for pp in self.pain_points.pain_points:
            # Extract user language patterns for keywords
            formatted.append(
                f"""[PAIN POINT LANGUAGE FOR KEYWORDS]
[PROBLEM: {pp.title}]

**User Problem Description:**
{pp.description}

**Actual User Phrasing (All Quotes for Keyword Mining):**
{chr(10).join(f'- {quote}' for quote in pp.representative_quotes)}

**Keyword Signals:**
- Severity: {pp.severity_score:.2f} ({"high" if pp.severity_score >= 0.7 else "medium" if pp.severity_score >= 0.4 else "low"})
- User intent: {pp.commercial_intent:.2f} WTP indicates {"commercial intent" if pp.commercial_intent >= 0.6 else "informational intent"}
- Categories: {', '.join(pp.categories if pp.categories else ['N/A'])}
- Platforms: {', '.join(pp.source_platforms if pp.source_platforms else ['N/A'])}
"""
            )

        return "\n\n---\n\n".join(formatted)

    def _prepare_competitive_keywords_content(self, landscape: "CompetitiveLandscape") -> str:
        """
        Format competitive data for alternative keyword generation.

        Args:
            landscape: Competitive landscape for selected solution

        Returns:
            Formatted string with competitor data for keyword alternatives
        """
        formatted = [
            f"""[COMPETITIVE KEYWORDS FOR: {landscape.solution_name}]

**Direct Competitors ({len(landscape.competitors)}):**
{chr(10).join(f'- {c.name}: {c.description}' for c in landscape.competitors)}

**Market Gaps (Alternative Positioning Keywords):**
{chr(10).join(f'- {gap}' for gap in landscape.market_gaps)}

**Differentiation Opportunities (Unique Keyword Angles):**
{chr(10).join(f'- {opp}' for opp in landscape.differentiation_opportunities)}

**Recommended Positioning:**
{landscape.recommended_positioning}
"""
        ]

        return "\n".join(formatted)

    @agent
    def keyword_strategist(self) -> Agent:
        """
        Agent responsible for analyzing pre-enriched keywords from CSV input and creating tiered opportunity structure.

        NOTE: Receives complete keyword data via CSV input (enriched in Phase 6b with DataForSEO).
        Agent analyzes existing data to identify quick wins (Tier 1) vs long-term plays (Tier 4).
        Does NOT call external APIs - all keyword data is pre-validated and provided in task context.

        Uses zero temperature for data-driven keyword analysis (no creativity needed).
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["keyword_strategist"],
            tools=[],  # No tools needed - analyzes CSV data provided in task context
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Low temperature to avoid repetition loops
            ),
            verbose=True,
        )

    # ========================================
    # SPLIT KEYWORD ANALYSIS AGENTS (Tasks 1a-1d)
    # ========================================

    @agent
    def premium_tier_analyst(self) -> Agent:
        """
        Agent for Task 1a (Sequential): Premium Tier Analysis (Tiers 0, 1, 2).

        Legacy agent for backward compatibility with sequential execution.
        Identifies and analyzes high-opportunity keywords with opp_score >= 50.
        Focuses on quick-win and high-value opportunities for immediate SEO implementation.

        Uses zero temperature for data-driven keyword analysis.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["premium_tier_analyst"],
            tools=[],  # No tools needed - analyzes CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Low temperature to avoid repetition loops
            ),
            verbose=True,
        )

    # ========================================
    # PARALLEL KEYWORD ANALYSIS AGENTS (Tasks 1a-1e)
    # ========================================

    @agent
    def high_priority_analyst(self) -> Agent:
        """
        Agent for Task 1a (Parallel): High Priority Keywords (Tier 0 + Tier 1).

        Analyzes pre-filtered keywords with opp_score > 100 for immediate SEO wins.
        Receives only high-priority keywords - no filtering needed.

        Uses zero temperature for data-driven keyword analysis.

        NOTE: This agent is kept for backward compatibility. For new implementations,
        use tier_0_analyst and tier_1_analyst for better token management.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["high_priority_analyst"],
            tools=[],  # No tools needed - analyzes pre-filtered CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Low temperature to avoid repetition loops
            ),
            verbose=True,
        )

    @agent
    def tier_0_analyst(self) -> Agent:
        """
        Agent for Task 1a-i (Parallel): Tier 0 Premium Keywords.

        Analyzes PRE-FILTERED keywords with opp_score > 200 (exceptional opportunities).
        Receives only Tier 0 keywords - no filtering needed.

        Uses zero temperature for data-driven keyword analysis.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["tier_0_analyst"],
            tools=[],  # No tools needed - analyzes pre-filtered CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Low temperature to avoid repetition loops
            ),
            verbose=True,
        )

    @agent
    def tier_1_analyst(self) -> Agent:
        """
        Agent for Task 1a-ii (Parallel): Tier 1 Quick Win Keywords.

        Analyzes PRE-FILTERED keywords with opp_score 100-200 (quick wins).
        Receives only Tier 1 keywords - no filtering needed.

        Uses zero temperature for data-driven keyword analysis.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["tier_1_analyst"],
            tools=[],  # No tools needed - analyzes pre-filtered CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Low temperature to avoid repetition loops
            ),
            verbose=True,
        )

    @agent
    def strategic_tier_analyst(self) -> Agent:
        """
        Agent for Task 1b (Parallel): Strategic Keywords (Tier 2).

        Analyzes pre-filtered keywords with opp_score 50-100 for medium-term growth.
        Receives only strategic-tier keywords - no filtering needed.

        Uses low temperature for data-driven keyword analysis.
        Uses frequency_penalty to prevent infinite repetition loops in JSON output.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["strategic_tier_analyst"],
            tools=[],  # No tools needed - analyzes pre-filtered CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Slight randomness to prevent repetition loops
                frequency_penalty=0.5,  # Discourage repeating the same tokens
                presence_penalty=0.3,  # Discourage repeating topics
            ),
            verbose=True,
        )

    @agent
    def geographic_tier_analyst(self) -> Agent:
        """
        Agent for Task 1b: Geographic Tier Analysis (Tier 3).

        Groups location-based keywords by region for geographic SEO strategy.
        Only includes keywords with explicit location mentions in the keyword text.

        Uses low temperature for precise geographic segmentation.
        Uses frequency_penalty to prevent infinite repetition loops in JSON output.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["geographic_tier_analyst"],
            tools=[],  # No tools needed - analyzes CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Slight randomness to prevent repetition loops
                frequency_penalty=0.5,  # Discourage repeating the same tokens
                presence_penalty=0.3,  # Discourage repeating topics
            ),
            verbose=True,
        )

    @agent
    def category_tier_analyst(self) -> Agent:
        """
        Agent for Task 1c: Category Tier Analysis (Tier 4).

        Organizes remaining keywords into thematic category groups for programmatic SEO.
        Creates 8-15 category groups to maximize keyword coverage.

        Uses low temperature for systematic categorization.
        Uses frequency_penalty to prevent infinite repetition loops in JSON output.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["category_tier_analyst"],
            tools=[],  # No tools needed - analyzes CSV data
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.1,  # Slight randomness to prevent repetition loops
                frequency_penalty=0.5,  # Discourage repeating the same tokens
                presence_penalty=0.3,  # Discourage repeating topics
            ),
            verbose=True,
        )

    @agent
    def keyword_summary_analyst(self) -> Agent:
        """
        Agent for Task 1d: Summary & Synthesis.

        Synthesizes findings from Tasks 1a-1c into key findings, competitive
        positioning insights, and aggregate metrics.

        Uses low temperature for strategic synthesis with data grounding.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["keyword_summary_analyst"],
            tools=[],  # No tools needed - synthesizes from context
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.2,  # Slightly higher for strategic synthesis
            ),
            verbose=True,
        )

    @agent
    def content_strategist(self) -> Agent:
        """
        Agent responsible for content strategy and topic clustering.
        Creates content recommendations aligned with keyword opportunities.

        Uses moderate temperature (0.5) for balanced creative strategy with structure.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["content_strategist"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.5,  # Moderate temperature (ignored for reasoning models)
            ),
            verbose=True,
        )

    @agent
    def seo_specialist(self) -> Agent:
        """
        Agent responsible for technical SEO and implementation roadmap.
        Provides URL structure, schema markup, and phased implementation plan.

        Uses moderate temperature (0.4) to balance technical precision with creative customization.
        Slightly higher than 0.3 to encourage solution-specific examples while maintaining accuracy.
        Uses max_tokens=20000 to prevent truncation of large SEO strategy outputs.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["seo_specialist"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate temperature (ignored for reasoning models)
                timeout=180,
                # max_completion_tokens=20000,  # Disabled: CrewAI doesn't forward this properly for reasoning models
            ),
            verbose=True,
        )

    @task
    def expand_keywords_conceptually_task(self) -> Task:
        """
        Task: Phase 6a - Hybrid seed keyword generation (70% broad seeds + 30% targeted keywords).

        Output: ExpandedKeywordList with 40-50 total keywords organized by 5-8 topic clusters.
        """
        return Task(
            config=self.tasks_config["expand_keywords_conceptually"],
            agent=self.content_strategist(),  # Use content strategist for strategic thinking
            output_pydantic=ExpandedKeywordList,
        )

    # ========================================
    # SPLIT KEYWORD ANALYSIS TASKS (Tasks 1a-1d)
    # ========================================
    # These 4 tasks replace the single analyze_keywords_and_tier_task
    # Each produces smaller, more manageable JSON output

    @task
    def analyze_premium_tiers_task(self) -> Task:
        """
        Task 1a: Premium Tier Analysis (Tiers 0, 1, 2).

        Analyzes keywords with high opportunity scores (>= 50) and creates
        strategic targeting recommendations for quick-win and high-value opportunities.

        Output: PremiumTierResult with tier 0-2 keywords and strategies.
        """
        return Task(
            config=self.tasks_config["analyze_premium_tiers"],
            agent=self.premium_tier_analyst(),
            output_pydantic=PremiumTierResult,
        )

    @task
    def analyze_geographic_tier_task(self) -> Task:
        """
        Task 1b: Geographic Tier Analysis (Tier 3).

        Groups keywords containing explicit location mentions by region
        for geographic SEO strategy.

        Depends on: analyze_premium_tiers_task (context for knowing which keywords are premium)
        Output: GeographicTierResult with tier 3 geographic groups.
        """
        return Task(
            config=self.tasks_config["analyze_geographic_tier"],
            agent=self.geographic_tier_analyst(),
            context=[self.analyze_premium_tiers_task()],  # Knows which keywords are already in premium tiers
            output_pydantic=GeographicTierResult,
        )

    @task
    def analyze_category_tier_task(self) -> Task:
        """
        Task 1c: Category Tier Analysis (Tier 4).

        Organizes remaining keywords (after premium + geographic selection)
        into thematic category groups for programmatic SEO.

        Depends on: analyze_premium_tiers_task, analyze_geographic_tier_task
        Output: CategoryTierResult with tier 4 category groups.
        """
        return Task(
            config=self.tasks_config["analyze_category_tier"],
            agent=self.category_tier_analyst(),
            context=[
                self.analyze_premium_tiers_task(),  # Knows which keywords are premium
                self.analyze_geographic_tier_task(),  # Knows which keywords are geographic
            ],
            output_pydantic=CategoryTierResult,
        )

    @task
    def synthesize_keyword_summary_task(self) -> Task:
        """
        Task 1d (Sequential): Summary & Synthesis.

        Synthesizes findings from Tasks 1a-1c into key findings, competitive
        positioning insights, and aggregate metrics.

        Depends on: All previous keyword tasks (1a, 1b, 1c)
        Output: KeywordSummaryResult with totals, findings, and positioning.
        """
        return SafeTask(
            config=self.tasks_config["synthesize_keyword_summary"],
            agent=self.keyword_summary_analyst(),
            context=[
                self.analyze_premium_tiers_task(),  # Task 1a
                self.analyze_geographic_tier_task(),  # Task 1b
                self.analyze_category_tier_task(),  # Task 1c
            ],
            output_pydantic=KeywordSummaryResult,
            guardrail=validate_keyword_summary,
            guardrail_max_retries=2,
        )

    # ========================================
    # PARALLEL KEYWORD ANALYSIS TASKS (Tasks 1a-1e)
    # ========================================
    # These tasks use async_execution=True for parallel processing
    # Task 1e synthesizes results from Tasks 1a-1d

    @task
    def analyze_high_priority_tiers_task(self) -> Task:
        """
        Task 1a (Parallel): High Priority Keywords (Tier 0 + Tier 1).

        Analyzes PRE-FILTERED keywords with opp_score > 100.
        Runs in parallel with Tasks 1b, 1c, 1d.

        Output: HighPriorityTierResult with tier 0-1 keywords and strategies.

        NOTE: This task is kept for backward compatibility. For new implementations,
        use analyze_tier_0_premium_task and analyze_tier_1_quick_wins_task.
        """
        return Task(
            config=self.tasks_config["analyze_high_priority_tiers"],
            agent=self.high_priority_analyst(),
            output_pydantic=HighPriorityTierResult,
            async_execution=True,  # Runs in parallel
        )

    @task
    def analyze_tier_0_premium_task(self) -> Task:
        """
        Task 1a-i (Parallel): Tier 0 Premium Keywords.

        Analyzes PRE-FILTERED keywords with opp_score > 200.
        Runs in parallel with Tasks 1a-ii, 1b, 1c, 1d.

        Output: Tier0LightResult with lightweight keyword selections.
        Python hydrates full TieredKeyword objects with stats from CSV.
        """
        return Task(
            config=self.tasks_config["analyze_tier_0_premium"],
            agent=self.tier_0_analyst(),
            output_pydantic=Tier0LightResult,  # Lightweight output - Python hydrates stats
            async_execution=True,  # Runs in parallel
        )

    @task
    def analyze_tier_1_quick_wins_task(self) -> Task:
        """
        Task 1a-ii (Parallel): Tier 1 Quick Win Keywords.

        Analyzes PRE-FILTERED keywords with opp_score 100-200.
        Runs in parallel with Tasks 1a-i, 1b, 1c, 1d.

        Output: Tier1LightResult with lightweight keyword selections.
        Python hydrates full TieredKeyword objects with stats from CSV.
        """
        return Task(
            config=self.tasks_config["analyze_tier_1_quick_wins"],
            agent=self.tier_1_analyst(),
            output_pydantic=Tier1LightResult,  # Lightweight output - Python hydrates stats
            async_execution=True,  # Runs in parallel
        )

    @task
    def analyze_strategic_tier_task(self) -> Task:
        """
        Task 1b (Parallel): Strategic Keywords (Tier 2).

        Analyzes PRE-FILTERED keywords with opp_score 50-100.
        Runs in parallel with Tasks 1a, 1c, 1d.

        Output: StrategicLightResult with lightweight keyword selections.
        Python hydrates full TieredKeyword objects with stats from CSV.

        Guardrail: Validates JSON completeness and detects repetition loops.
        """
        return SafeTask(
            config=self.tasks_config["analyze_strategic_tier"],
            agent=self.strategic_tier_analyst(),
            output_pydantic=StrategicLightResult,  # Lightweight output - Python hydrates stats
            async_execution=True,  # Runs in parallel
            guardrail=validate_strategic_tier_output,
            guardrail_max_retries=2,  # Retry up to 2 times on validation failure
        )

    @task
    def analyze_geographic_tier_parallel_task(self) -> Task:
        """
        Task 1c (Parallel): Geographic Keywords (Tier 3).

        Analyzes PRE-FILTERED keywords with explicit location mentions.
        Runs in parallel with Tasks 1a, 1b, 1d.

        Output: GeographicLightResult with lightweight geographic groups.
        Python hydrates full GeographicKeywordGroup objects with stats from CSV.

        Guardrail: Validates JSON completeness and detects repetition loops.
        """
        return SafeTask(
            config=self.tasks_config["analyze_geographic_tier_parallel"],
            agent=self.geographic_tier_analyst(),
            output_pydantic=GeographicLightResult,  # Lightweight output - Python hydrates stats
            async_execution=True,  # Runs in parallel
            guardrail=validate_geographic_tier_output,
            guardrail_max_retries=2,  # Retry up to 2 times on validation failure
        )

    @task
    def analyze_category_tier_parallel_task(self) -> Task:
        """
        Task 1d (Parallel): Category Keywords (Tier 4).

        Analyzes PRE-FILTERED remaining keywords for programmatic SEO.
        Runs in parallel with Tasks 1a, 1b, 1c.

        Output: CategoryLightResult with lightweight category groups.
        Python hydrates full CategoryKeywordGroup objects with stats from CSV.

        Guardrail: Validates JSON completeness and detects repetition loops.
        This task is most susceptible to repetition issues due to large dataset size.
        """
        return SafeTask(
            config=self.tasks_config["analyze_category_tier_parallel"],
            agent=self.category_tier_analyst(),
            output_pydantic=CategoryLightResult,  # Lightweight output - Python hydrates stats
            async_execution=True,  # Runs in parallel
            guardrail=validate_category_tier_output,
            guardrail_max_retries=2,  # Retry up to 2 times on validation failure
        )

    @task
    def synthesize_keyword_summary_parallel_task(self) -> Task:
        """
        Task 1e (Parallel): Summary & Synthesis.

        Synthesizes findings from Tasks 1a-i, 1a-ii, 1b, 1c, 1d into key findings,
        competitive positioning insights, and aggregate metrics.

        Waits for: All parallel tasks via context
        Output: KeywordSummaryResult with totals, findings, and positioning.
        """
        return SafeTask(
            config=self.tasks_config["synthesize_keyword_summary_parallel"],
            agent=self.keyword_summary_analyst(),
            context=[
                self.analyze_tier_0_premium_task(),        # Task 1a-i (async)
                self.analyze_tier_1_quick_wins_task(),     # Task 1a-ii (async)
                self.analyze_strategic_tier_task(),       # Task 1b (async)
                self.analyze_geographic_tier_parallel_task(),  # Task 1c (async)
                self.analyze_category_tier_parallel_task(),    # Task 1d (async)
            ],
            output_pydantic=KeywordSummaryResult,
            guardrail=validate_keyword_summary,
            guardrail_max_retries=2,
            # async_execution=False (default) - waits for all async tasks
        )

    # ========================================
    # MULTI-TASK SEO STRATEGY (8-TASK FLOW)
    # ========================================
    # Tasks 1a-1d (split keyword analysis) + Tasks 2-5 (strategy development)

    @task
    def analyze_keywords_and_tier_task(self) -> Task:
        """
        Task 1: Keyword Analysis & Tiering.

        Analyzes pre-enriched keywords and creates tiered opportunity structure.

        Output: KeywordAnalysisResult with tier structure, competitive positioning, key findings.
        """
        return Task(
            config=self.tasks_config["analyze_keywords_and_tier"],
            agent=self.keyword_strategist(),
            output_pydantic=KeywordAnalysisResult,
        )

    @task
    def develop_content_technical_strategy_task(self) -> Task:
        """
        Task 2: Content & Technical Strategy (Lightweight Output Pattern).

        NOTE: This @task method is used by the LEGACY SEQUENTIAL flow only.
        The parallel flow constructs Task 2 inline in _create_strategy_parallel()
        to wire context to synthesize_keyword_summary_parallel_task instead.

        Develops content strategy, topic clusters, and technical SEO recommendations
        based on keyword analysis from Tasks 1a-1d (via synthesize_keyword_summary_task).

        Uses Lightweight Output Pattern:
        - LLM outputs strategic/creative content only (ContentStrategyResultLight)
        - Python hydrates numeric fields (volumes, page counts) from CSV data

        Depends on: synthesize_keyword_summary_task (legacy sequential summary)
        Output: ContentStrategyResultLight - Python will hydrate to ContentStrategyResult
        """
        return SafeTask(
            config=self.tasks_config["develop_content_technical_strategy"],
            agent=self.content_strategist(),
            context=[self.synthesize_keyword_summary_task()],  # Depends on Task 1d (summary of 1a-1c)
            output_pydantic=ContentStrategyResultLight,  # Lightweight - Python hydrates numeric fields
            guardrail=validate_content_strategy_output,
            guardrail_max_retries=2,
        )

    @task
    def create_implementation_plan_task(self) -> Task:
        """
        Task 3: Implementation Planning.

        NOTE: This @task method is used by the LEGACY SEQUENTIAL flow only.
        The parallel flow constructs Task 3 inline in _create_strategy_parallel()
        to wire context to the parallel summary task and inline Task 2.

        Creates phased implementation roadmap with metrics, timeline, budget, and risks
        based on keyword analysis and content strategy.

        Depends on: synthesize_keyword_summary_task (legacy), develop_content_technical_strategy_task
        Output: ImplementationPlanResult with roadmap, metrics, timeline.
        """
        return SafeTask(
            config=self.tasks_config["create_implementation_plan"],
            agent=self.seo_specialist(),
            context=[
                self.synthesize_keyword_summary_task(),  # Task 1d (keyword summary)
                self.develop_content_technical_strategy_task(),  # Task 2
            ],
            output_pydantic=ImplementationPlanResult,
            guardrail=validate_implementation_plan_output,
            guardrail_max_retries=2,
        )

    # synthesize_final_seo_strategy_task (Task 4) removed - only produced conclusion_bottom_line (generic boilerplate)
    # create_implementation_guide_task (Task 5) and sync_final_outputs_task (Task 6) removed
    # Technical SEO is now part of Task 2's technical_seo_recommendations markdown field

    @crew
    def crew(self) -> Crew:
        """
        Assemble the SEOStrategyCrew with all agents, tasks, and optional knowledge sources.

        If knowledge sources are available (pain points and/or competitive data),
        they are attached at crew level for keyword research and content strategy.

        Returns:
            Configured Crew instance with optional knowledge sources
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {"model_name": "text-embedding-3-small"},  # Cost-effective embeddings
        }

        crew_config = {
            "agents": self.agents,
            "tasks": self.tasks,
            "verbose": True,
            "process_type": "sequential",
            "embedder": embedder_config,
        }

        # Create Knowledge with niche-specific collection name for isolation
        self._crew_knowledge = None
        if self.knowledge_sources:
            collection_name = sanitize_collection_name(self.niche, "seo", self.job_id)
            logger.info(f"Creating SEO knowledge with collection: {collection_name}")
            knowledge = create_knowledge(
                sources=self.knowledge_sources,
                embedder_config=embedder_config,
                collection_name=collection_name,
            )
            if knowledge:
                crew_config["knowledge"] = knowledge
                self._crew_knowledge = knowledge

        return Crew(**crew_config)

    def expand_keywords_phase_1(self) -> ExpandedKeywordList:
        """
        Execute Phase 6a: Hybrid Seed Keyword Generation using KeywordSeedGenerator.

        Generates a strategic mix using 70-30 approach:
        - 70% Broad Seeds (28-35 keywords, 1-2 words): For DataForSEO expansion into thousands of variations
        - 30% Targeted Keywords (12-15 keywords, 3-5 words): Strategic high-value queries for direct validation

        Returns 40-50 total keywords organized by 5-8 topic clusters.

        Returns:
            ExpandedKeywordList with hybrid seed keywords for Phase 6b bulk validation and expansion
        """
        logger.info(
            f"Starting Phase 6a: Context-aware seed keyword generation for: {self.selected_solution.solution_name}"
        )

        try:
            # Initialize KeywordSeedGenerator
            generator = KeywordSeedGenerator()

            # Extract audience vocabulary for keyword grounding (from Stage 6.5)
            audience_vocab = (
                self.audience_mapping.common_vocabulary
                if self.audience_mapping else None
            )
            if audience_vocab:
                logger.info(f"Passing {len(audience_vocab)} audience vocabulary terms to seed generator")

            # Generate seeds with full context
            result = generator.generate_seeds(
                solution=self.selected_solution,
                niche_context=self.niche_context,
                pain_points=self.pain_points,
                competitive_analysis=self.competitive_analysis,
                audience_vocabulary=audience_vocab,
                num_broad_seeds=30,
                num_targeted_seeds=15,
                covered_keywords=self.covered_keywords,
            )

            if not result:
                logger.error(
                    "KeywordSeedGenerator returned None - falling back to minimal keywords"
                )
                # Fallback: return minimal keyword list
                from ..models.seo_strategy import ConceptualKeyword, ConceptualTopicCluster

                fallback_keywords = [
                    ConceptualKeyword(
                        keyword=self.selected_solution.solution_name.lower(),
                        cluster="Core Product",
                        priority=1,
                        rationale="Fallback keyword - generator failed",
                    )
                ]
                fallback_clusters = [
                    ConceptualTopicCluster(
                        name="Core Product",
                        description="Primary solution keywords",
                        strategic_importance=1,
                    )
                ]
                result = ExpandedKeywordList(
                    keywords=fallback_keywords,
                    topic_clusters=fallback_clusters,
                    expansion_rationale="Fallback mode - generator failed",
                )

            logger.info(
                f"Phase 6a complete: {len(result.keywords)} seed keywords generated, "
                f"{len(result.topic_clusters)} topic clusters identified"
            )
            return result

        except Exception as e:
            logger.error(f"Phase 6a keyword generation failed: {e}", exc_info=True)
            raise

    def _extract_page_types_from_task2(self, task2_output) -> str:
        """
        Extract keyword_based_page_types from Task 2 content strategy output.

        Args:
            task2_output: TaskOutput object from Task 2 (ContentStrategyResult)

        Returns:
            Formatted string with page types for content strategy reference
        """
        try:
            if hasattr(task2_output, "pydantic"):
                content_strategy = task2_output.pydantic
                if (
                    hasattr(content_strategy, "keyword_based_page_types")
                    and content_strategy.keyword_based_page_types
                ):
                    page_types = content_strategy.keyword_based_page_types
                    formatted = "\n".join([f"- {pt}" for pt in page_types])
                    logger.debug(f"Extracted {len(page_types)} page types from Task 2")
                    return formatted

            logger.warning("No keyword_based_page_types found in Task 2 output")
            return "No page types found in Task 2 output - generate based on project_type standards"

        except Exception as e:
            logger.warning(f"Failed to extract page types from Task 2: {e}")
            return "Unable to extract page types from Task 2 - generate based on project_type standards"

    def _calculate_trend_metrics(self, monthly_searches: list[dict]) -> dict:
        """
        Calculate trend metrics from 12-month historical search data.

        Analyzes monthly_searches data from DataForSEO to determine:
        - trend_direction: rising/stable/declining based on recent vs older volumes
        - trend_score: -1.0 to 1.0 representing percentage change (capped)
        - seasonality_index: 0.0 to 1.0 (coefficient of variation)
        - is_evergreen: True if low seasonality and not declining

        Args:
            monthly_searches: List of dicts with year, month, search_volume

        Returns:
            Dict with trend_direction, trend_score, seasonality_index, is_evergreen
        """
        if not monthly_searches or len(monthly_searches) < 2:
            return {
                "trend_direction": "unknown",
                "trend_score": 0.0,
                "seasonality_index": 0.0,
                "is_evergreen": False
            }

        # Sort by date (newest first)
        sorted_data = sorted(
            monthly_searches,
            key=lambda x: (x.get("year", 0), x.get("month", 0)),
            reverse=True
        )

        volumes = [m.get("search_volume", 0) for m in sorted_data]

        # Trend direction: Compare recent 3 months vs older 3 months
        recent_avg = sum(volumes[:3]) / 3 if len(volumes) >= 3 else sum(volumes) / len(volumes)
        older_avg = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else sum(volumes) / len(volumes)

        if older_avg > 0:
            trend_pct = ((recent_avg - older_avg) / older_avg) * 100
        else:
            trend_pct = 0

        # Trend direction thresholds
        if trend_pct > 15:
            trend_direction = "rising"
        elif trend_pct < -15:
            trend_direction = "declining"
        else:
            trend_direction = "stable"

        # Trend score: -1.0 to 1.0 (capped)
        trend_score = max(-1.0, min(1.0, trend_pct / 100))

        # Seasonality: coefficient of variation (std/mean)
        mean_vol = sum(volumes) / len(volumes) if volumes else 0
        if mean_vol > 0:
            variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
            std_dev = variance ** 0.5
            seasonality_index = min(1.0, std_dev / mean_vol)
        else:
            seasonality_index = 0.0

        # Evergreen: Low seasonality + stable/rising trend
        is_evergreen = seasonality_index < 0.3 and trend_direction != "declining"

        return {
            "trend_direction": trend_direction,
            "trend_score": round(trend_score, 2),
            "seasonality_index": round(seasonality_index, 2),
            "is_evergreen": is_evergreen
        }

    def _calculate_difficulty_metrics_from_partitions(self, partitions: dict) -> dict:
        """
        Calculate aggregate difficulty metrics from partitioned keyword data.

        Called BEFORE crew kickoff with raw enriched_keywords partitions.
        Metrics are passed as inputs to Task 3 for data-driven timeline estimates.

        Timeline derivation from difficulty:
        - <25: "1-3 months" (easy)
        - 25-40: "3-6 months"
        - 40-60: "6-9 months"
        - 60-75: "9-15 months"
        - >75: "12-18+ months" (hard)

        Args:
            partitions: Dict from _partition_keywords_for_parallel() containing
                        tier_0_remaining, tier_1_remaining, strategic_remaining lists

        Returns:
            Dict with difficulty metrics for injection into Task 3
        """
        def calc_avg_difficulty_from_dicts(keywords: list[dict]) -> float | None:
            """Calculate average keyword_difficulty from list of keyword dicts."""
            if not keywords:
                return None
            difficulties = [
                kw.get('keyword_difficulty')
                for kw in keywords
                if kw.get('keyword_difficulty') is not None
            ]
            if not difficulties:
                return None
            return sum(difficulties) / len(difficulties)

        def difficulty_to_ranking_time(difficulty: float | None) -> str:
            """Convert difficulty score to human-readable ranking time."""
            if difficulty is None:
                return "Unknown (no difficulty data)"
            if difficulty < 25:
                return "1-3 months"
            elif difficulty < 40:
                return "3-6 months"
            elif difficulty < 60:
                return "6-9 months"
            elif difficulty < 75:
                return "9-15 months"
            else:
                return "12-18+ months"

        def difficulty_to_multiplier(difficulty: float | None) -> float:
            """Convert difficulty to timeline multiplier (0.5-2.0)."""
            if difficulty is None:
                return 1.0  # Default to standard timeline
            # Linear interpolation: difficulty 0 -> 0.5, difficulty 50 -> 1.0, difficulty 100 -> 2.0
            return 0.5 + (difficulty / 100) * 1.5

        # Get keyword lists from partitions (includes both LLM and remaining keywords)
        # Note: partitions has tier_X_remaining lists, but we need ALL keywords per tier
        # The full tier list is tier_X_llm + tier_X_remaining (but we only store remaining)
        # For simplicity, we recalculate from the all keywords passed to partition
        # Actually, looking at _partition_keywords_for_parallel, tier_X_remaining is available

        # Calculate per-tier averages using remaining keywords (since LLM keywords are a subset)
        # This gives us difficulty for ALL keywords in each tier, not just LLM-selected ones
        tier_0_kws = partitions.get('tier_0_remaining', [])
        tier_1_kws = partitions.get('tier_1_remaining', [])
        tier_2_kws = partitions.get('strategic_remaining', [])

        # Also need to include the LLM keywords - build from CSV if available
        # Actually, the CSV already contains all keywords - let's extract difficulty from there
        # For now, use a simpler approach: calculate from full enriched_keywords passed separately

        avg_t0 = calc_avg_difficulty_from_dicts(tier_0_kws)
        avg_t1 = calc_avg_difficulty_from_dicts(tier_1_kws)
        avg_t2 = calc_avg_difficulty_from_dicts(tier_2_kws)

        # If remaining lists are empty but there were keywords sent to LLM, log warning
        if not tier_1_kws and partitions.get('tier_1_count', 0) > 0:
            logger.debug(
                f"Tier 1 difficulty calculated from remaining only - "
                f"{partitions.get('tier_1_count', 0)} keywords were sent to LLM"
            )

        # Calculate weighted difficulty score
        # Weights: T0=0.4, T1=0.4, T2=0.2 (premium/quick-win tiers matter most)
        weighted_scores = []
        weights = []
        if avg_t0 is not None:
            weighted_scores.append(avg_t0 * 0.4)
            weights.append(0.4)
        if avg_t1 is not None:
            weighted_scores.append(avg_t1 * 0.4)
            weights.append(0.4)
        if avg_t2 is not None:
            weighted_scores.append(avg_t2 * 0.2)
            weights.append(0.2)

        if weighted_scores and sum(weights) > 0:
            difficulty_score = sum(weighted_scores) / sum(weights)
        else:
            difficulty_score = None

        # Calculate timeline multiplier
        timeline_multiplier = difficulty_to_multiplier(difficulty_score)

        # Generate human-readable ranking times
        tier1_ranking_time = difficulty_to_ranking_time(avg_t1)
        tier2_ranking_time = difficulty_to_ranking_time(avg_t2)

        metrics = {
            "avg_difficulty_tier0": round(avg_t0, 1) if avg_t0 is not None else None,
            "avg_difficulty_tier1": round(avg_t1, 1) if avg_t1 is not None else None,
            "avg_difficulty_tier2": round(avg_t2, 1) if avg_t2 is not None else None,
            "difficulty_score": round(difficulty_score, 1) if difficulty_score is not None else None,
            "timeline_multiplier": round(timeline_multiplier, 2),
            "tier1_ranking_time": tier1_ranking_time,
            "tier2_ranking_time": tier2_ranking_time,
        }

        logger.info(
            f"Difficulty metrics calculated: T0={metrics['avg_difficulty_tier0']}, "
            f"T1={metrics['avg_difficulty_tier1']}, T2={metrics['avg_difficulty_tier2']}, "
            f"Score={metrics['difficulty_score']}, Multiplier={metrics['timeline_multiplier']}"
        )

        return metrics

    def _calculate_difficulty_metrics_from_enriched(self, enriched_keywords: list[dict]) -> dict:
        """
        Calculate aggregate difficulty metrics from enriched_keywords list.

        Alternative to _calculate_difficulty_metrics_from_partitions that uses
        the full enriched_keywords list directly, calculating tier membership
        from opportunity_score.

        Args:
            enriched_keywords: List of keyword dicts with search_volume,
                             competition_index, and keyword_difficulty fields

        Returns:
            Dict with difficulty metrics for injection into Task 3
        """
        def calc_avg_difficulty(keywords: list[dict]) -> float | None:
            """Calculate average keyword_difficulty from list of keyword dicts."""
            if not keywords:
                return None
            difficulties = [
                kw.get('keyword_difficulty')
                for kw in keywords
                if kw.get('keyword_difficulty') is not None
            ]
            if not difficulties:
                return None
            return sum(difficulties) / len(difficulties)

        def difficulty_to_ranking_time(difficulty: float | None) -> str:
            """Convert difficulty score to human-readable ranking time."""
            if difficulty is None:
                return "Unknown (no difficulty data)"
            if difficulty < 25:
                return "1-3 months"
            elif difficulty < 40:
                return "3-6 months"
            elif difficulty < 60:
                return "6-9 months"
            elif difficulty < 75:
                return "9-15 months"
            else:
                return "12-18+ months"

        def difficulty_to_multiplier(difficulty: float | None) -> float:
            """Convert difficulty to timeline multiplier (0.5-2.0)."""
            if difficulty is None:
                return 1.0  # Default to standard timeline
            return 0.5 + (difficulty / 100) * 1.5

        # Partition keywords by opportunity score (same logic as _partition_keywords_for_parallel)
        tier_0_kws = []  # opp_score > 200
        tier_1_kws = []  # opp_score 100-200
        tier_2_kws = []  # opp_score 50-100

        for kw in enriched_keywords:
            sv = kw.get("search_volume", 0) or 0
            ci = kw.get("competition_index", 1) or 1
            opp_score = sv / max(ci, 1)

            if opp_score > 200:
                tier_0_kws.append(kw)
            elif opp_score > 100:
                tier_1_kws.append(kw)
            elif opp_score >= 50:
                tier_2_kws.append(kw)

        # Calculate per-tier averages
        avg_t0 = calc_avg_difficulty(tier_0_kws)
        avg_t1 = calc_avg_difficulty(tier_1_kws)
        avg_t2 = calc_avg_difficulty(tier_2_kws)

        # Log keyword counts with difficulty data
        t0_with_diff = sum(1 for k in tier_0_kws if k.get('keyword_difficulty') is not None)
        t1_with_diff = sum(1 for k in tier_1_kws if k.get('keyword_difficulty') is not None)
        t2_with_diff = sum(1 for k in tier_2_kws if k.get('keyword_difficulty') is not None)
        logger.debug(
            f"Keywords with difficulty data: T0={t0_with_diff}/{len(tier_0_kws)}, "
            f"T1={t1_with_diff}/{len(tier_1_kws)}, T2={t2_with_diff}/{len(tier_2_kws)}"
        )

        # Calculate weighted difficulty score
        weighted_scores = []
        weights = []
        if avg_t0 is not None:
            weighted_scores.append(avg_t0 * 0.4)
            weights.append(0.4)
        if avg_t1 is not None:
            weighted_scores.append(avg_t1 * 0.4)
            weights.append(0.4)
        if avg_t2 is not None:
            weighted_scores.append(avg_t2 * 0.2)
            weights.append(0.2)

        if weighted_scores and sum(weights) > 0:
            difficulty_score = sum(weighted_scores) / sum(weights)
        else:
            difficulty_score = None

        # Calculate timeline multiplier
        timeline_multiplier = difficulty_to_multiplier(difficulty_score)

        # Generate human-readable ranking times
        tier1_ranking_time = difficulty_to_ranking_time(avg_t1)
        tier2_ranking_time = difficulty_to_ranking_time(avg_t2)

        metrics = {
            "avg_difficulty_tier0": round(avg_t0, 1) if avg_t0 is not None else None,
            "avg_difficulty_tier1": round(avg_t1, 1) if avg_t1 is not None else None,
            "avg_difficulty_tier2": round(avg_t2, 1) if avg_t2 is not None else None,
            "difficulty_score": round(difficulty_score, 1) if difficulty_score is not None else None,
            "timeline_multiplier": round(timeline_multiplier, 2),
            "tier1_ranking_time": tier1_ranking_time,
            "tier2_ranking_time": tier2_ranking_time,
        }

        logger.info(
            f"Difficulty metrics from enriched: T0={metrics['avg_difficulty_tier0']}, "
            f"T1={metrics['avg_difficulty_tier1']}, T2={metrics['avg_difficulty_tier2']}, "
            f"Score={metrics['difficulty_score']}, Multiplier={metrics['timeline_multiplier']}"
        )

        return metrics

    def _format_keywords_as_csv(self, enriched_keywords: list) -> str:
        """
        Format keywords as CSV for direct context injection.

        CSV is 2x more token-efficient than JSON for tabular data and provides
        complete keyword visibility to agents without requiring RAG queries.

        Includes trend analysis from monthly_searches data:
        - trend_direction: rising/stable/declining
        - trend_score: -1.0 to 1.0
        - seasonality_index: 0.0 to 1.0
        - is_evergreen: True/False

        Also includes keyword_difficulty (SEO difficulty score 0-100) for
        accurate timeline estimates.

        Returns:
            CSV string with header and keyword data (12 columns)
        """
        # CSV header with trend columns and keyword_difficulty
        lines = [
            "keyword,search_volume,competition_index,competition_level,cpc,opportunity_score,tier,keyword_difficulty,trend_direction,trend_score,seasonality,is_evergreen"
        ]

        for k in enriched_keywords:
            keyword_text = k.get("keyword", "")
            search_volume = k.get("search_volume", 0)
            competition_index = k.get("competition_index", 0)
            cpc = float(k.get("cpc") or 0)
            keyword_difficulty = k.get("keyword_difficulty")

            # Calculate opportunity score
            opp_score = search_volume / max(competition_index, 1)

            # Format competition label
            if competition_index < 30:
                comp_label = "LOW" if competition_index >= 15 else "VERY_LOW"
            elif competition_index < 60:
                comp_label = "MEDIUM"
            elif competition_index < 80:
                comp_label = "HIGH"
            else:
                comp_label = "VERY_HIGH"

            # Assign tier based on opportunity score
            if opp_score > 200:
                tier = "TIER_0_PREMIUM"
            elif opp_score > 100:
                tier = "TIER_1_QUICK_WIN"
            elif opp_score > 50:
                tier = "TIER_2_STRATEGIC"
            elif opp_score > 20:
                tier = "TIER_3_MEDIUM"
            else:
                tier = "TIER_4_LONG_TAIL"

            # Calculate trend metrics from monthly_searches
            monthly_searches = k.get("monthly_searches", [])
            trend_metrics = self._calculate_trend_metrics(monthly_searches)

            # Format keyword_difficulty (empty string if None)
            kd_str = f"{keyword_difficulty:.1f}" if keyword_difficulty is not None else ""

            # Add CSV row (escape commas in keyword text if present)
            keyword_escaped = keyword_text.replace(",", " ")
            lines.append(
                f"{keyword_escaped},{search_volume},{competition_index},"
                f"{comp_label},{cpc:.2f},{opp_score:.1f},{tier},{kd_str},"
                f"{trend_metrics['trend_direction']},{trend_metrics['trend_score']},"
                f"{trend_metrics['seasonality_index']},{trend_metrics['is_evergreen']}"
            )

        return "\n".join(lines)

    def _limit_keywords_for_llm(
        self,
        keywords: list[dict],
        limit: int | None,
        sort_by: str = "opportunity_score",
    ) -> tuple[list[dict], list[dict]]:
        """
        Split keywords into LLM subset and remainder for Python hydration.

        This optimization reduces token usage by sending only the top N keywords
        to the LLM for strategic analysis. Remaining keywords are hydrated by
        Python using the tier-level strategy (no hallucination risk).

        Args:
            keywords: Full list of keyword dicts from CSV
            limit: Max keywords to send to LLM (None = no limit, send all)
            sort_by: Field to sort by (descending). Default "opportunity_score"

        Returns:
            Tuple of (llm_keywords, remaining_keywords)
            - llm_keywords: Top N keywords sent to LLM for analysis
            - remaining_keywords: Rest of keywords to hydrate via Python
        """
        if limit is None or len(keywords) <= limit:
            return keywords, []

        # Calculate opportunity_score if not present
        def get_opp_score(kw: dict) -> float:
            if sort_by in kw and kw[sort_by] is not None:
                return float(kw[sort_by])
            # Calculate from volume/competition
            sv = kw.get("search_volume", 0) or 0
            ci = kw.get("competition_index", 1) or 1
            return sv / max(ci, 1)

        # Sort by opportunity_score descending (highest value first)
        sorted_kws = sorted(
            keywords,
            key=get_opp_score,
            reverse=True
        )

        return sorted_kws[:limit], sorted_kws[limit:]

    def _has_location_mention(self, keyword_text: str) -> bool:
        """
        Check if keyword contains explicit location mention.

        Uses regex patterns to detect:
        - Country names (usa, uk, spain, etc.)
        - Major city names (new york, london, tokyo, etc.)

        Args:
            keyword_text: The keyword string to check

        Returns:
            True if keyword contains explicit location mention
        """
        keyword_lower = keyword_text.lower()

        # Common country names (expanded list)
        countries = r'\b(usa|us|uk|canada|australia|germany|france|spain|italy|japan|china|india|brazil|mexico|netherlands|sweden|norway|switzerland|portugal|ireland|singapore|dubai|uae|thailand|vietnam|philippines|indonesia|malaysia|korea|taiwan|argentina|chile|colombia|peru|poland|czech|austria|belgium|denmark|finland|greece|hungary|israel|new zealand|russia|saudi|south africa|turkey|egypt|nigeria|kenya|morocco|pakistan|bangladesh|sri lanka|myanmar|cambodia|laos)\b'

        # Major cities (expanded list)
        cities = r'\b(new york|nyc|los angeles|la|london|paris|berlin|tokyo|sydney|melbourne|toronto|vancouver|dubai|singapore|hong kong|amsterdam|barcelona|madrid|rome|milan|munich|zurich|stockholm|oslo|copenhagen|dublin|lisbon|bangkok|seoul|taipei|shanghai|beijing|mumbai|delhi|bangalore|chennai|hyderabad|kolkata|pune|jakarta|manila|ho chi minh|hanoi|kuala lumpur|cairo|lagos|johannesburg|cape town|nairobi|casablanca|istanbul|moscow|st petersburg|warsaw|prague|vienna|brussels|budapest|athens|tel aviv|riyadh|doha|abu dhabi|sao paulo|rio de janeiro|buenos aires|santiago|bogota|lima|mexico city)\b'

        return bool(
            re.search(countries, keyword_lower) or
            re.search(cities, keyword_lower)
        )

    def _partition_keywords_for_parallel(self, enriched_keywords: list) -> dict:
        """
        Pre-filter keywords into 5 non-overlapping partitions for parallel processing.

        Applies LLM limits (TIER_X_LLM_LIMIT) to optimize token usage:
        - Sends top N keywords (by opportunity_score) to LLM for analysis
        - Returns remaining keywords for Python hydration

        DIFFICULTY GATING (Phase 6):
        Keywords with high SEO difficulty are demoted from premium tiers to ensure
        "quick win" labels actually represent achievable ranking opportunities.
        - Tier 0: opp_score > 200 AND difficulty < tier_0_max_difficulty (default 50)
        - Tier 1: opp_score 100-200 AND difficulty < tier_1_max_difficulty (default 60)
        - Tier 2: Includes demoted T0/T1 keywords with high difficulty

        Partitions:
        - tier_0: opp_score > 200 (Tier 0 Premium) - no limit
        - tier_1: opp_score 100-200 (Tier 1 Quick Wins) - top 25
        - strategic: opp_score 50-100 (Tier 2) - top 30
        - geographic: location mentions, opp < 50 (Tier 3) - top 40
        - category: remaining (Tier 4) - top 50

        Args:
            enriched_keywords: List of keyword dicts from DataForSEO

        Returns:
            dict with CSV strings, counts, totals, and remaining keywords for each partition
        """
        tier_0_keywords = []          # opp_score > 200 → Task 1a-i
        tier_1_keywords = []          # opp_score 100-200 → Task 1a-ii
        strategic_keywords = []       # opp_score 50-100 → Task 1b (T2)
        geographic_keywords = []      # location mentions, opp < 50 → Task 1c (T3)
        category_keywords = []        # remaining → Task 1d (T4)

        # Track demotions for logging
        demoted_from_t0 = 0
        demoted_from_t1 = 0

        # Get difficulty thresholds from settings
        t0_max_diff = settings.tier_0_max_difficulty
        t1_max_diff = settings.tier_1_max_difficulty

        for kw in enriched_keywords:
            keyword_text = kw.get("keyword", "").lower()
            sv = kw.get("search_volume", 0) or 0
            ci = kw.get("competition_index", 1) or 1
            opp_score = sv / max(ci, 1)
            difficulty = kw.get("keyword_difficulty")  # May be None

            # Partition with difficulty gating
            # Tier 0: High opportunity AND achievable difficulty
            if opp_score > 200:
                if difficulty is None or difficulty < t0_max_diff:
                    tier_0_keywords.append(kw)
                else:
                    # Demote to Tier 2 (high opp but hard to rank)
                    strategic_keywords.append(kw)
                    demoted_from_t0 += 1
            # Tier 1: Good opportunity AND reasonable difficulty
            elif opp_score > 100:
                if difficulty is None or difficulty < t1_max_diff:
                    tier_1_keywords.append(kw)
                else:
                    # Demote to Tier 2 (medium opp but hard to rank)
                    strategic_keywords.append(kw)
                    demoted_from_t1 += 1
            # Tier 2: Strategic (opp 50-100, no difficulty gate)
            elif opp_score >= 50:
                strategic_keywords.append(kw)
            # Tier 3: Geographic (has location mention, opp < 50)
            elif self._has_location_mention(keyword_text):
                geographic_keywords.append(kw)
            # Tier 4: Category (everything else)
            else:
                category_keywords.append(kw)

        # Log tier demotions for visibility
        if demoted_from_t0 > 0:
            logger.info(
                f"[Tier Gating] Demoted {demoted_from_t0} keywords from T0→T2 "
                f"(difficulty >= {t0_max_diff})"
            )
        if demoted_from_t1 > 0:
            logger.info(
                f"[Tier Gating] Demoted {demoted_from_t1} keywords from T1→T2 "
                f"(difficulty >= {t1_max_diff})"
            )

        # Apply LLM limits to each tier
        tier_0_llm, tier_0_remaining = self._limit_keywords_for_llm(
            tier_0_keywords, self.TIER_0_LLM_LIMIT
        )
        tier_1_llm, tier_1_remaining = self._limit_keywords_for_llm(
            tier_1_keywords, self.TIER_1_LLM_LIMIT
        )
        tier_2_llm, tier_2_remaining = self._limit_keywords_for_llm(
            strategic_keywords, self.TIER_2_LLM_LIMIT
        )
        tier_3_llm, tier_3_remaining = self._limit_keywords_for_llm(
            geographic_keywords, self.TIER_3_LLM_LIMIT
        )
        tier_4_llm, tier_4_remaining = self._limit_keywords_for_llm(
            category_keywords, self.TIER_4_LLM_LIMIT
        )

        # Log partitioning with limit details and demotion info
        demotion_note = ""
        if demoted_from_t0 or demoted_from_t1:
            demotion_note = f"\n  [Difficulty Gating] {demoted_from_t0} demoted T0→T2, {demoted_from_t1} demoted T1→T2"

        logger.info(
            f"Keyword partitioning (with LLM limits):\n"
            f"  Tier 0: {len(tier_0_llm)} sent to LLM / {len(tier_0_keywords)} total (limit={self.TIER_0_LLM_LIMIT or 'None'})\n"
            f"  Tier 1: {len(tier_1_llm)} sent to LLM / {len(tier_1_keywords)} total (limit={self.TIER_1_LLM_LIMIT})\n"
            f"  Tier 2: {len(tier_2_llm)} sent to LLM / {len(strategic_keywords)} total (limit={self.TIER_2_LLM_LIMIT})\n"
            f"  Tier 3: {len(tier_3_llm)} sent to LLM / {len(geographic_keywords)} total (limit={self.TIER_3_LLM_LIMIT})\n"
            f"  Tier 4: {len(tier_4_llm)} sent to LLM / {len(category_keywords)} total (limit={self.TIER_4_LLM_LIMIT})"
            f"{demotion_note}"
        )

        return {
            # Task 1a-i: Tier 0 Premium (no limit)
            "tier_0_csv": self._format_keywords_as_csv(tier_0_llm),
            "tier_0_count": len(tier_0_llm),
            "tier_0_total": len(tier_0_keywords),
            "tier_0_remaining": tier_0_remaining,

            # Task 1a-ii: Tier 1 Quick Wins (limited)
            "tier_1_csv": self._format_keywords_as_csv(tier_1_llm),
            "tier_1_count": len(tier_1_llm),
            "tier_1_total": len(tier_1_keywords),
            "tier_1_remaining": tier_1_remaining,

            # Legacy: high_priority (for backward compatibility - uses limited sets)
            "high_priority_csv": self._format_keywords_as_csv(tier_0_llm + tier_1_llm),
            "high_priority_count": len(tier_0_llm) + len(tier_1_llm),

            # Task 1b: Strategic / Tier 2 (limited)
            "strategic_csv": self._format_keywords_as_csv(tier_2_llm),
            "strategic_count": len(tier_2_llm),
            "strategic_total": len(strategic_keywords),
            "strategic_remaining": tier_2_remaining,

            # Task 1c: Geographic / Tier 3 (limited)
            "geographic_csv": self._format_keywords_as_csv(tier_3_llm),
            "geographic_count": len(tier_3_llm),
            "geographic_total": len(geographic_keywords),
            "geographic_remaining": tier_3_remaining,

            # Task 1d: Category / Tier 4 (limited)
            "category_csv": self._format_keywords_as_csv(tier_4_llm),
            "category_count": len(tier_4_llm),
            "category_total": len(category_keywords),
            "category_remaining": tier_4_remaining,

            # Difficulty gating metadata
            "demoted_from_t0": demoted_from_t0,
            "demoted_from_t1": demoted_from_t1,
        }

    def _calculate_category_limits(self, keyword_count: int) -> tuple[int, int]:
        """
        Calculate min/max category groups based on available keywords.

        Ensures LLM never creates more categories than keywords, preventing
        hallucinated content when input data is insufficient.

        Args:
            keyword_count: Number of keywords available for categorization

        Returns:
            Tuple of (min_categories, max_categories)
        """
        if keyword_count == 0:
            return (0, 0)
        elif keyword_count <= 3:
            return (1, min(keyword_count, 2))
        elif keyword_count <= 10:
            return (2, min(keyword_count, 5))
        elif keyword_count <= 30:
            return (4, min(keyword_count, 10))
        else:
            return (8, 15)

    def create_strategy_multitask(
        self,
        enriched_keywords: list,
        expanded_keywords: ExpandedKeywordList | None = None,
        parallel: bool = True,
    ) -> SEOStrategyReport:
        """
        Execute 11-Task SEO Strategy Flow with Parallel Keyword Analysis.

        Creates comprehensive SEO strategy using parallel keyword analysis:
        - Task 1a-i: Tier 0 Premium Keywords (opp_score > 200) - async
        - Task 1a-ii: Tier 1 Quick Win Keywords (opp_score 100-200) - async
        - Task 1b: Strategic Keywords (Tier 2) - async
        - Task 1c: Geographic Keywords (Tier 3) - async
        - Task 1d: Category Keywords (Tier 4) - async
        - Task 1e: Summary & Synthesis - sync (waits for 1a-i/ii, 1b-1d)
        - Task 2: Content & Technical Strategy (now includes comprehensive technical SEO)
        - Task 3: Implementation Planning
        - Task 4: Final Synthesis

        Benefits of parallel architecture:
        - ~5x faster keyword analysis (Tasks 1a-i/ii, 1b, 1c, 1d run concurrently)
        - Each agent sees only pre-filtered keywords (reduced tokens)
        - Zero keyword overlap (Python pre-filters into 5 partitions)
        - Native CrewAI async pattern (no ThreadPoolExecutor needed)
        - Split Tier 0/1 ensures no token exhaustion for large keyword sets

        Args:
            enriched_keywords: List of dicts from DataForSEO with volumes/competition
            expanded_keywords: Optional ExpandedKeywordList from Phase 6a
            parallel: Use parallel execution for keyword analysis (default True)

        Returns:
            Complete SEOStrategyReport with implementation details (29 fields total)
        """
        if parallel:
            return self._create_strategy_parallel(enriched_keywords, expanded_keywords)
        else:
            return self._create_strategy_sequential(enriched_keywords, expanded_keywords)

    @staticmethod
    def _deduplicate_across_tiers(
        keyword_analysis: KeywordAnalysisResult,
    ) -> KeywordAnalysisResult:
        """
        Remove keywords that appear in multiple tiers, keeping the highest-priority copy.

        Priority order: T0 > T1 > T2 > T3 > T4 > Untiered.
        Lower tier number = higher priority.

        Returns a **new** KeywordAnalysisResult (immutable pattern).
        """
        seen: set[str] = set()
        stats: dict[str, int] = {}

        def _dedup_tiered(
            keywords: list[TieredKeyword] | None, tier_name: str
        ) -> list[TieredKeyword] | None:
            if not keywords:
                stats[tier_name] = 0
                return keywords
            kept = []
            removed = 0
            for kw in keywords:
                key = kw.keyword.lower().strip()
                if key not in seen:
                    seen.add(key)
                    kept.append(kw)
                else:
                    removed += 1
            stats[tier_name] = removed
            return kept if kept else None

        def _dedup_geographic_groups(
            groups: list[GeographicKeywordGroup] | None, tier_name: str
        ) -> list[GeographicKeywordGroup] | None:
            if not groups:
                stats[tier_name] = 0
                return groups
            removed = 0
            new_groups = []
            for group in groups:
                # Deduplicate within the group first, then against seen
                internal_seen: set[str] = set()
                kept_entries = []
                for entry in group.keywords:
                    key = entry.keyword.lower().strip()
                    if key in internal_seen:
                        removed += 1
                        continue
                    internal_seen.add(key)
                    if key not in seen:
                        seen.add(key)
                        kept_entries.append(entry)
                    else:
                        removed += 1
                if kept_entries:
                    new_groups.append(
                        GeographicKeywordGroup(
                            region_name=group.region_name,
                            total_volume=sum(e.search_volume or 0 for e in kept_entries),
                            competition_level=group.competition_level,
                            keywords=kept_entries,
                            strategy_notes=group.strategy_notes,
                        )
                    )
            stats[tier_name] = removed
            return new_groups if new_groups else None

        def _dedup_category_groups(
            groups: list[CategoryKeywordGroup] | None, tier_name: str
        ) -> list[CategoryKeywordGroup] | None:
            if not groups:
                stats[tier_name] = 0
                return groups
            removed = 0
            new_groups = []
            for group in groups:
                # Deduplicate within the group first, then against seen
                internal_seen: set[str] = set()
                kept_entries = []
                for entry in group.keywords:
                    key = entry.keyword_name.lower().strip()
                    if key in internal_seen:
                        removed += 1
                        continue
                    internal_seen.add(key)
                    if key not in seen:
                        seen.add(key)
                        kept_entries.append(entry)
                    else:
                        removed += 1
                if kept_entries:
                    new_groups.append(
                        CategoryKeywordGroup(
                            category_name=group.category_name,
                            total_volume=sum(e.search_volume or 0 for e in kept_entries),
                            keywords=kept_entries,
                            strategy_recommendation=group.strategy_recommendation,
                        )
                    )
            stats[tier_name] = removed
            return new_groups if new_groups else None

        # Walk tiers in priority order
        new_t0 = _dedup_tiered(keyword_analysis.tier_0_keywords, "T0")
        new_t1 = _dedup_tiered(keyword_analysis.tier_1_keywords, "T1")
        new_t2 = _dedup_tiered(keyword_analysis.tier_2_keywords, "T2")
        new_t3 = _dedup_geographic_groups(keyword_analysis.tier_3_geographic_groups, "T3")
        new_t4 = _dedup_category_groups(keyword_analysis.tier_4_category_groups, "T4")
        new_untiered = _dedup_tiered(keyword_analysis.untiered_keywords, "Untiered")

        total_removed = sum(stats.values())
        if total_removed > 0:
            breakdown = ", ".join(f"{k}: {v}" for k, v in stats.items() if v > 0)
            logger.warning(
                f"⚠️ Cross-tier dedup: removed {total_removed} duplicates ({breakdown})"
            )
        else:
            logger.info("✅ Cross-tier dedup: no duplicates found")

        # Ensure tier_1 is never None (required field with min_length=1)
        if new_t1 is None:
            new_t1 = keyword_analysis.tier_1_keywords

        return KeywordAnalysisResult(
            tier_0_keywords=new_t0,
            tier_0_strategy=keyword_analysis.tier_0_strategy,
            tier_1_keywords=new_t1,
            tier_1_quick_win_strategy=keyword_analysis.tier_1_quick_win_strategy,
            tier_2_keywords=new_t2,
            tier_2_strategy=keyword_analysis.tier_2_strategy,
            tier_3_geographic_groups=new_t3,
            tier_4_category_groups=new_t4,
            untiered_keywords=new_untiered,
            total_keywords_analyzed=keyword_analysis.total_keywords_analyzed,
            total_monthly_volume=keyword_analysis.total_monthly_volume,
            key_findings=keyword_analysis.key_findings,
            competitive_positioning=keyword_analysis.competitive_positioning,
        )

    def _create_strategy_sequential(
        self, enriched_keywords: list, expanded_keywords: ExpandedKeywordList | None = None
    ) -> SEOStrategyReport:
        """
        Execute 7-Task SEO Strategy Flow with Sequential Keyword Analysis (legacy).

        This is the original sequential implementation kept for backward compatibility.
        Task 5/6 removed - technical SEO is now in Task 2's technical_seo_recommendations.
        """
        logger.info(
            f"Starting 7-Task SEO Strategy Flow (SEQUENTIAL) for: {self.selected_solution.solution_name}"
        )
        logger.info(
            f"Processing {len(enriched_keywords)} enriched keywords"
            + (
                f" with {len(expanded_keywords.keywords)} seed keywords"
                if expanded_keywords
                else ""
            )
        )

        try:
            # Format keywords as CSV for direct context injection
            keywords_csv = self._format_keywords_as_csv(enriched_keywords)
            csv_line_count = keywords_csv.count("\n") + 1
            csv_token_estimate = len(keywords_csv) // 4  # Rough estimate: 4 chars per token
            logger.info(
                f"Created keyword CSV: {csv_line_count} lines, ~{csv_token_estimate:,} tokens"
            )

            # Format topic clusters summary (with None handling)
            if expanded_keywords and expanded_keywords.topic_clusters:
                topic_clusters_summary = "\n".join(
                    [
                        f"- **{c.name}** (Priority {c.strategic_importance}/5): {c.description}"
                        for c in expanded_keywords.topic_clusters
                    ]
                )
            else:
                topic_clusters_summary = "No topic clusters identified"

            # Create 7-task crew with split keyword analysis agents (sequential)
            strategy_crew = Crew(
                agents=[
                    # Tasks 1a-1d: Split keyword analysis agents
                    self.premium_tier_analyst(),      # Task 1a
                    self.geographic_tier_analyst(),   # Task 1b
                    self.category_tier_analyst(),     # Task 1c
                    self.keyword_summary_analyst(),   # Task 1d
                    # Tasks 2-3: Strategy development agents
                    self.content_strategist(),        # Task 2
                    self.seo_specialist(),            # Task 3
                ],
                tasks=[
                    # Split keyword analysis (Tasks 1a-1d)
                    self.analyze_premium_tiers_task(),        # Task 1a
                    self.analyze_geographic_tier_task(),      # Task 1b (context: 1a)
                    self.analyze_category_tier_task(),        # Task 1c (context: 1a, 1b)
                    self.synthesize_keyword_summary_task(),   # Task 1d (context: 1a, 1b, 1c)
                    # Strategy development (Tasks 2-3)
                    self.develop_content_technical_strategy_task(),  # Task 2 (context: 1d, includes tech SEO)
                    self.create_implementation_plan_task(),          # Task 3 (final task)
                ],
                verbose=True,
                process_type="sequential",
            )
            self._last_crew = strategy_crew  # Store for usage_metrics access

            # Format solution architecture for task context
            core_features_formatted = (
                "\n".join([f"- {feat}" for feat in self.selected_solution.core_features])
                if self.selected_solution.core_features
                else "Not specified"
            )
            technical_approach_formatted = (
                self.selected_solution.technical_approach or "Not specified"
            )

            # Format competitor names for keyword contextualization
            competitive_landscape = self._find_solution_landscape()
            if competitive_landscape and competitive_landscape.competitors:
                competitor_names_formatted = "\n".join(
                    [f"- {c.name}" for c in competitive_landscape.competitors]
                )
            else:
                competitor_names_formatted = "No direct competitors identified"

            # Format pain point metrics for keyword contextualization
            from ..utils.pain_point_formatters import format_pain_points_for_agents

            if self.pain_points and self.pain_points.pain_points:
                pain_points_formatted = format_pain_points_for_agents(
                    pain_points=self.pain_points.pain_points,
                    format_type="metrics_only",
                    sort_by="severity",
                    limit=10,
                )
            else:
                pain_points_formatted = "No pain points available"

            # Format additional solution context
            value_proposition = self.selected_solution.value_proposition or "Not specified"
            target_personas_formatted = (
                "\n".join([f"- {persona}" for persona in self.selected_solution.target_personas])
                if self.selected_solution.target_personas
                else "Not specified"
            )
            pricing_strategy = self.selected_solution.pricing_strategy or "Not specified"

            # Calculate dynamic category limits based on estimated category keyword count
            # In sequential flow, ~60-70% of keywords typically end up in Tier 4 after filtering
            estimated_category_count = int(len(enriched_keywords) * 0.65)
            cat_min, cat_max = self._calculate_category_limits(estimated_category_count)
            logger.info(
                f"Dynamic category limits (sequential): min={cat_min}, max={cat_max} "
                f"(estimated from {len(enriched_keywords)} total keywords)"
            )

            logger.info("Executing 8-Task SEO Strategy Flow (split keyword analysis)...")
            logger.info(f"All {len(enriched_keywords)} keywords visible in context")
            crew_output = strategy_crew.kickoff(
                inputs={
                    "niche": self.niche,
                    "selected_solution_name": self.selected_solution.solution_name,
                    "selected_solution_description": self.selected_solution.description,
                    "value_proposition": value_proposition,
                    "target_personas": target_personas_formatted,
                    "pricing_strategy": pricing_strategy,
                    "core_features": core_features_formatted,
                    "technical_approach": technical_approach_formatted,
                    "competitor_names": competitor_names_formatted,
                    "top_pain_points": pain_points_formatted,
                    "enriched_keywords_count": len(enriched_keywords),
                    "enriched_keywords_csv": keywords_csv,
                    "topic_clusters_summary": topic_clusters_summary,
                    "allowed_project_types": ', '.join(self.allowed_project_types) if self.allowed_project_types else "All types allowed",
                    # Dynamic category limits (calculated by Python, not LLM)
                    "min_category_groups": cat_min,
                    "max_category_groups": cat_max,
                }
            )

            # Extract all task outputs (Tasks 1a-1d + Tasks 2-5 = 8 total)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, "tasks_output") else []
            if len(task_outputs) < 8:
                raise ValueError(
                    f"Expected 8 task outputs, got {len(task_outputs)}. "
                    "Pipeline may have failed mid-execution."
                )

            # ========================================
            # Extract and validate Tasks 1a-1d (Split Keyword Analysis)
            # ========================================

            task_1a_output = task_outputs[0].pydantic  # PremiumTierResult
            if task_1a_output is None:
                raise ValueError(
                    "Task 1a (Premium Tier Analysis) returned None pydantic output. "
                    "Check PremiumTierResult schema and agent prompt."
                )

            task_1b_output = task_outputs[1].pydantic  # GeographicTierResult
            if task_1b_output is None:
                raise ValueError(
                    "Task 1b (Geographic Tier Analysis) returned None pydantic output. "
                    "Check GeographicTierResult schema and agent prompt."
                )

            task_1c_output = task_outputs[2].pydantic  # CategoryTierResult
            if task_1c_output is None:
                raise ValueError(
                    "Task 1c (Category Tier Analysis) returned None pydantic output. "
                    "Check CategoryTierResult schema and agent prompt."
                )

            task_1d_output = task_outputs[3].pydantic  # KeywordSummaryResult
            if task_1d_output is None:
                raise ValueError(
                    "Task 1d (Summary & Synthesis) returned None pydantic output. "
                    "Check KeywordSummaryResult schema and agent prompt."
                )

            # ========================================
            # Merge Tasks 1a-1d into KeywordAnalysisResult
            # ========================================

            # Deduplicate tier keywords from Task 1a
            for tier_attr in ['tier_0_keywords', 'tier_1_keywords', 'tier_2_keywords']:
                tier_list = getattr(task_1a_output, tier_attr, None)
                if tier_list:
                    seen = set()
                    deduped = []
                    for kw in tier_list:
                        kw_key = kw.keyword.lower().strip()
                        if kw_key not in seen:
                            deduped.append(kw)
                            seen.add(kw_key)
                    if len(deduped) < len(tier_list):
                        logger.warning(f"⚠️ Removed {len(tier_list) - len(deduped)} duplicate keywords from {tier_attr}")
                        setattr(task_1a_output, tier_attr, deduped)

            # Create merged KeywordAnalysisResult from Tasks 1a-1d
            keyword_analysis = KeywordAnalysisResult(
                # From Task 1a (Premium Tiers)
                tier_0_keywords=task_1a_output.tier_0_keywords,
                tier_0_strategy=task_1a_output.tier_0_strategy,
                tier_1_keywords=task_1a_output.tier_1_keywords,
                tier_1_quick_win_strategy=task_1a_output.tier_1_quick_win_strategy,
                tier_2_keywords=task_1a_output.tier_2_keywords,
                tier_2_strategy=task_1a_output.tier_2_strategy,
                # From Task 1b (Geographic)
                tier_3_geographic_groups=task_1b_output.tier_3_geographic_groups,
                # From Task 1c (Category)
                tier_4_category_groups=task_1c_output.tier_4_category_groups,
                # Calculated from enriched_keywords (Python, not LLM)
                total_keywords_analyzed=len(enriched_keywords),
                total_monthly_volume=sum(kw.get("search_volume", 0) or 0 for kw in enriched_keywords),
                key_findings=task_1d_output.key_findings,
                competitive_positioning=task_1d_output.competitive_positioning,
            )

            # ═══ Cross-tier deduplication ═══
            keyword_analysis = self._deduplicate_across_tiers(keyword_analysis)

            # ═══ GUARDRAIL: Log tier keyword selection for visibility ═══
            tier0_in_csv = sum(
                1 for kw in enriched_keywords
                if (kw.get("search_volume", 0) or 0) / max(kw.get("competition_index", 1) or 1, 1) > 200
            )
            tier0_selected = len(keyword_analysis.tier_0_keywords or [])

            if tier0_in_csv > 0:
                if tier0_selected < tier0_in_csv:
                    logger.warning(
                        f"⚠️ TIER 0 LOSS: Only {tier0_selected}/{tier0_in_csv} premium keywords selected "
                        f"(opp_score >200 - should ALL be selected)"
                    )
                else:
                    logger.info(f"✅ Tier 0 keywords: {tier0_selected}/{tier0_in_csv} selected")
            elif tier0_selected > 0:
                logger.info(f"✅ Tier 0 keywords: {tier0_selected} (agent identified premium opportunities)")

            # Log Tier 4 category count
            tier_4_groups = keyword_analysis.tier_4_category_groups or []
            tier_4_cat_count = len(tier_4_groups)
            tier_4_kw_count = sum(len(g.keywords) for g in tier_4_groups) if tier_4_groups else 0

            if tier_4_cat_count < 6:
                logger.warning(
                    f"⚠️ TIER 4 UNDER-CREATION: Only {tier_4_cat_count} categories "
                    f"(expected 6-15). {tier_4_kw_count} keywords in Tier 4."
                )
            else:
                logger.info(f"✅ Tier 4 categories: {tier_4_cat_count} with {tier_4_kw_count} keywords")

            # Log total utilization
            total_tiered = (
                len(keyword_analysis.tier_0_keywords or []) +
                len(keyword_analysis.tier_1_keywords or []) +
                len(keyword_analysis.tier_2_keywords or []) +
                sum(len(g.keywords) for g in (keyword_analysis.tier_3_geographic_groups or [])) +
                tier_4_kw_count
            )
            analyzed = keyword_analysis.total_keywords_analyzed or 1
            utilization = total_tiered / analyzed

            if utilization < 0.5:
                logger.error(
                    f"⚠️ CRITICAL KEYWORD LOSS: Only {utilization:.1%} of keywords tiered "
                    f"({total_tiered}/{analyzed}). Keyword analysis filtering was too aggressive."
                )
            elif utilization < 0.7:
                logger.warning(
                    f"⚠️ Keyword utilization below target: {utilization:.1%} "
                    f"({total_tiered}/{analyzed})"
                )
            else:
                logger.info(f"✅ Keyword utilization: {utilization:.1%} ({total_tiered}/{analyzed})")

            logger.info(
                f"✅ Tasks 1a-1d merged into KeywordAnalysisResult:\n"
                f"  - Task 1a (Premium): T0={len(task_1a_output.tier_0_keywords or [])}, "
                f"T1={len(task_1a_output.tier_1_keywords or [])}, T2={len(task_1a_output.tier_2_keywords or [])}\n"
                f"  - Task 1b (Geographic): {task_1b_output.geographic_keywords_count} keywords in {len(task_1b_output.tier_3_geographic_groups or [])} groups\n"
                f"  - Task 1c (Category): {task_1c_output.category_keywords_count} keywords in {tier_4_cat_count} groups\n"
                f"  - Task 1d (Summary): {task_1d_output.total_keywords_analyzed} keywords, {task_1d_output.total_monthly_volume} monthly volume"
            )

            # ========================================
            # Extract and validate Tasks 2-5 (Strategy Development)
            # ========================================

            task_2_light = task_outputs[4].pydantic  # ContentStrategyResultLight
            if task_2_light is None:
                raise ValueError(
                    "Task 2 (Content Strategy) returned None pydantic output. "
                    "Check ContentStrategyResultLight schema and agent prompt."
                )

            # ========================================
            # HYDRATION: Task 2 - Build lookup and hydrate lightweight output
            # ========================================

            # Build keyword lookup from enriched keywords (for volume calculation)
            lookup = _build_keyword_lookup(enriched_keywords)
            logger.info(f"✅ Built keyword lookup with {len(lookup)} entries for Task 2 hydration")

            # Hydrate Task 2 lightweight output to full ContentStrategyResult
            task_2_output = _hydrate_content_strategy(task_2_light, lookup)
            logger.info(
                f"✅ Task 2 hydrated: {len(task_2_output.topic_clusters or [])} topic clusters, "
                f"{len(task_2_output.keyword_based_page_types or [])} page types"
            )

            task_3_output = task_outputs[5].pydantic  # ImplementationPlanResult
            if task_3_output is None:
                raise ValueError(
                    "Task 3 (Implementation Plan) returned None pydantic output. "
                    "Check ImplementationPlanResult schema and agent prompt."
                )

            # Task 4 (Final Synthesis) removed - only produced conclusion_bottom_line (generic boilerplate)
            # Task 5 (Implementation Guide) removed - technical SEO is now in Task 2

            # ========================================
            # Python merge: Combine all task outputs into SEOStrategyReport
            # ========================================

            result = SEOStrategyReport(
                # Merged keyword analysis (Tasks 1a-1d) - extra fields ignored via extra='ignore'
                **keyword_analysis.model_dump(),
                # Task 2 fields (includes technical_seo_recommendations)
                **task_2_output.model_dump(),
                # Task 3 fields (implementation_roadmap, budget_allocation)
                **task_3_output.model_dump(),
            )

            logger.info(
                f"[OK] 6-Task SEO Strategy Flow complete (Tasks 1a-1d + 2-3 merged via Python):\n"
                f"  - Tier 1 keywords: {len(result.tier_1_keywords) if result.tier_1_keywords else 0}\n"
                f"  - Topic clusters: {len(result.topic_clusters) if result.topic_clusters else 0}\n"
                f"  - Total monthly volume: {result.total_monthly_volume if result.total_monthly_volume is not None else 0}\n"
                f"  - Technical SEO: {'✓' if result.technical_seo_recommendations else '✗'}\n"
                f"  - Implementation roadmap: {'✓' if result.implementation_roadmap else '✗'}"
            )
            return result

        except Exception as e:
            logger.error(f"7-Task SEO Strategy Flow failed: {e}")
            raise

    def _create_strategy_parallel(
        self, enriched_keywords: list, expanded_keywords: ExpandedKeywordList | None = None
    ) -> SEOStrategyReport:
        """
        Execute 9-Task SEO Strategy Flow with Parallel Keyword Analysis.

        Tasks 1a-i, 1a-ii, 1b, 1c, 1d run in parallel using CrewAI's async_execution=True pattern.
        Task 1e waits for all 5 async tasks via context dependency.
        Tasks 2-3 run sequentially. Task 4/5/6 removed.

        Benefits:
        - ~5x faster keyword analysis (Tasks 1a-i, 1a-ii, 1b, 1c, 1d run concurrently)
        - Each agent sees only pre-filtered keywords (reduced tokens)
        - Zero keyword overlap (Python pre-filters into 5 partitions)
        - Tier 0 and Tier 1 have separate token budgets (fixes null issue)
        """
        logger.info(
            f"Starting 9-Task SEO Strategy Flow (PARALLEL) for: {self.selected_solution.solution_name}"
        )
        logger.info(
            f"Processing {len(enriched_keywords)} enriched keywords"
            + (
                f" with {len(expanded_keywords.keywords)} seed keywords"
                if expanded_keywords
                else ""
            )
        )

        try:
            # Calculate aggregate metrics in Python (not LLM) - saves ~6,000 tokens
            total_monthly_volume = sum(kw.get("search_volume", 0) or 0 for kw in enriched_keywords)
            total_keywords_analyzed = len(enriched_keywords)
            logger.info(
                f"Pre-calculated aggregates: {total_keywords_analyzed} keywords, "
                f"{total_monthly_volume:,} total monthly volume"
            )

            # Partition keywords into 4 non-overlapping groups for parallel processing
            partitions = self._partition_keywords_for_parallel(enriched_keywords)
            logger.info(
                f"Partitioned keywords: High Priority={partitions['high_priority_count']}, "
                f"Strategic={partitions['strategic_count']}, Geographic={partitions['geographic_count']}, "
                f"Category={partitions['category_count']}"
            )

            # Format topic clusters summary (with None handling)
            if expanded_keywords and expanded_keywords.topic_clusters:
                topic_clusters_summary = "\n".join(
                    [
                        f"- **{c.name}** (Priority {c.strategic_importance}/5): {c.description}"
                        for c in expanded_keywords.topic_clusters
                    ]
                )
            else:
                topic_clusters_summary = "No topic clusters identified"

            # Create 9-task crew with parallel keyword analysis
            # Tasks 1a-i, 1a-ii, 1b, 1c, 1d run concurrently (async_execution=True)
            # Task 1e waits for all via context dependency
            # Task 3 is final task (Task 4/5/6 removed)
            #
            # IMPORTANT: Store task references to access task.output directly after crew completes
            # (crew_output.tasks_output has bugs with async tasks - may not include all outputs)
            task_1a_i = self.analyze_tier_0_premium_task()           # Task 1a-i (async)
            task_1a_ii = self.analyze_tier_1_quick_wins_task()       # Task 1a-ii (async)
            task_1b = self.analyze_strategic_tier_task()             # Task 1b (async)
            task_1c = self.analyze_geographic_tier_parallel_task()   # Task 1c (async)
            task_1d = self.analyze_category_tier_parallel_task()     # Task 1d (async)
            task_1e = self.synthesize_keyword_summary_parallel_task()  # Task 1e (sync)

            # Task 2 and Task 3 are constructed inline (not via @task methods) to ensure
            # they reference task_1e (the parallel summary task) in their context.
            # The @task-decorated methods cache Task objects with context pointing to
            # synthesize_keyword_summary_task() (the legacy sequential task), which is NOT
            # in this crew's task list. Using inline Task() ensures correct context wiring.
            task_2 = SafeTask(
                config=self.tasks_config["develop_content_technical_strategy"],
                agent=self.content_strategist(),
                context=[task_1e],  # Parallel flow: depends on parallel summary task
                output_pydantic=ContentStrategyResultLight,
                guardrail=validate_content_strategy_output,
                guardrail_max_retries=2,
            )
            task_3 = SafeTask(
                config=self.tasks_config["create_implementation_plan"],
                agent=self.seo_specialist(),
                context=[task_1e, task_2],  # Parallel flow: depends on parallel summary + task 2
                output_pydantic=ImplementationPlanResult,
                guardrail=validate_implementation_plan_output,
                guardrail_max_retries=2,
            )

            strategy_crew = Crew(
                agents=[
                    # Tasks 1a-i, 1a-ii, 1b, 1c, 1d, 1e: Parallel keyword analysis agents
                    self.tier_0_analyst(),             # Task 1a-i (async)
                    self.tier_1_analyst(),             # Task 1a-ii (async)
                    self.strategic_tier_analyst(),     # Task 1b (async)
                    self.geographic_tier_analyst(),    # Task 1c (async)
                    self.category_tier_analyst(),      # Task 1d (async)
                    self.keyword_summary_analyst(),    # Task 1e (sync)
                    # Tasks 2-3: Strategy development agents
                    self.content_strategist(),         # Task 2
                    self.seo_specialist(),             # Task 3
                ],
                tasks=[
                    task_1a_i, task_1a_ii, task_1b, task_1c, task_1d, task_1e,
                    task_2, task_3,
                ],
                verbose=True,
                process_type="sequential",  # CrewAI handles async within sequential
            )
            self._last_crew = strategy_crew

            # Format solution architecture for task context
            core_features_formatted = (
                "\n".join([f"- {feat}" for feat in self.selected_solution.core_features])
                if self.selected_solution.core_features
                else "Not specified"
            )
            technical_approach_formatted = (
                self.selected_solution.technical_approach or "Not specified"
            )

            # Format competitor names for keyword contextualization
            competitive_landscape = self._find_solution_landscape()
            if competitive_landscape and competitive_landscape.competitors:
                competitor_names_formatted = "\n".join(
                    [f"- {c.name}" for c in competitive_landscape.competitors]
                )
            else:
                competitor_names_formatted = "No direct competitors identified"

            # Format pain point metrics for keyword contextualization
            from ..utils.pain_point_formatters import format_pain_points_for_agents

            if self.pain_points and self.pain_points.pain_points:
                pain_points_formatted = format_pain_points_for_agents(
                    pain_points=self.pain_points.pain_points,
                    format_type="metrics_only",
                    sort_by="severity",
                    limit=10,
                )
            else:
                pain_points_formatted = "No pain points available"

            # Format additional solution context
            value_proposition = self.selected_solution.value_proposition or "Not specified"
            target_personas_formatted = (
                "\n".join([f"- {persona}" for persona in self.selected_solution.target_personas])
                if self.selected_solution.target_personas
                else "Not specified"
            )
            pricing_strategy = self.selected_solution.pricing_strategy or "Not specified"

            # Calculate dynamic category limits based on keyword count
            cat_min, cat_max = self._calculate_category_limits(partitions["category_count"])
            logger.info(
                f"Dynamic category limits: min={cat_min}, max={cat_max} "
                f"(based on {partitions['category_count']} category keywords)"
            )

            # Calculate difficulty metrics for data-driven timeline estimates in Task 3
            difficulty_metrics = self._calculate_difficulty_metrics_from_enriched(enriched_keywords)

            logger.info("Executing 9-Task SEO Strategy Flow (parallel keyword analysis)...")
            logger.info(
                f"Tasks 1a-i/ii, 1b, 1c, 1d will run in PARALLEL: "
                f"T0={partitions['tier_0_count']}, T1={partitions['tier_1_count']}, "
                f"Strategic={partitions['strategic_count']}, Geographic={partitions['geographic_count']}, "
                f"Category={partitions['category_count']} = {len(enriched_keywords)} keywords"
            )

            crew_output = strategy_crew.kickoff(
                inputs={
                    "niche": self.niche,
                    "selected_solution_name": self.selected_solution.solution_name,
                    "selected_solution_description": self.selected_solution.description,
                    "value_proposition": value_proposition,
                    "target_personas": target_personas_formatted,
                    "pricing_strategy": pricing_strategy,
                    "core_features": core_features_formatted,
                    "technical_approach": technical_approach_formatted,
                    "competitor_names": competitor_names_formatted,
                    "top_pain_points": pain_points_formatted,
                    # Pre-calculated aggregates for Task 1e (saves ~6,000 tokens vs full CSV)
                    "enriched_keywords_count": total_keywords_analyzed,
                    "total_keywords_analyzed": total_keywords_analyzed,
                    "total_monthly_volume": total_monthly_volume,
                    # Split Tier 0 and Tier 1 CSVs (new parallel tasks)
                    "tier_0_keywords_csv": partitions["tier_0_csv"],
                    "tier_0_keywords_count": partitions["tier_0_count"],
                    "tier_0_total": partitions["tier_0_total"],  # For sampling context
                    "tier_1_keywords_csv": partitions["tier_1_csv"],
                    "tier_1_keywords_count": partitions["tier_1_count"],
                    "tier_1_total": partitions["tier_1_total"],  # For sampling context
                    # Legacy: high_priority (backward compatibility)
                    "high_priority_keywords_csv": partitions["high_priority_csv"],
                    "high_priority_keywords_count": partitions["high_priority_count"],
                    # Other partitioned CSVs for parallel tasks
                    "strategic_keywords_csv": partitions["strategic_csv"],
                    "strategic_keywords_count": partitions["strategic_count"],
                    "strategic_total": partitions["strategic_total"],  # For sampling context
                    "geographic_keywords_csv": partitions["geographic_csv"],
                    "geographic_keywords_count": partitions["geographic_count"],
                    "geographic_total": partitions["geographic_total"],  # For sampling context
                    "category_keywords_csv": partitions["category_csv"],
                    "category_keywords_count": partitions["category_count"],
                    "category_total": partitions["category_total"],  # For sampling context
                    # Dynamic category limits (calculated by Python, not LLM)
                    "min_category_groups": cat_min,
                    "max_category_groups": cat_max,
                    # Other context
                    "topic_clusters_summary": topic_clusters_summary,
                    "allowed_project_types": ', '.join(self.allowed_project_types) if self.allowed_project_types else "All types allowed",
                    # Difficulty metrics for Task 3 data-driven timeline estimates
                    "avg_difficulty_tier0": difficulty_metrics["avg_difficulty_tier0"],
                    "avg_difficulty_tier1": difficulty_metrics["avg_difficulty_tier1"],
                    "avg_difficulty_tier2": difficulty_metrics["avg_difficulty_tier2"],
                    "difficulty_score": difficulty_metrics["difficulty_score"],
                    "timeline_multiplier": difficulty_metrics["timeline_multiplier"],
                    "tier1_ranking_time": difficulty_metrics["tier1_ranking_time"],
                    "tier2_ranking_time": difficulty_metrics["tier2_ranking_time"],
                }
            )

            # ========================================
            # Extract task outputs using task.output (workaround for CrewAI async bug)
            # ========================================
            # NOTE: crew_output.tasks_output has bugs with async tasks - may not include all outputs
            # Instead, access task.output directly from the task objects we stored earlier
            # See: https://community.crewai.com/t/improper-taskoutput-when-using-async-execution-true-in-tasks/3340

            def _get_task_output(task, task_name: str, expected_type: str):
                """Extract pydantic output from task, with validation."""
                if not hasattr(task, 'output') or task.output is None:
                    raise ValueError(
                        f"{task_name} has no output. Task may not have executed. "
                        f"Expected {expected_type}."
                    )
                output = task.output
                # CrewAI 1.8.1+: When guardrails exist, pydantic may be None - parse from raw
                if output.pydantic is None and output.raw:
                    logger.debug(f"{task_name}: pydantic is None, will parse from raw")
                return output

            # Extract outputs from stored task references
            logger.info("[DEBUG] Extracting outputs from task.output (bypassing tasks_output bug)")

            task_1a_i_raw = _get_task_output(task_1a_i, "Task 1a-i (Tier 0 Premium)", "Tier0LightResult")
            task_1a_ii_raw = _get_task_output(task_1a_ii, "Task 1a-ii (Tier 1 Quick Win)", "Tier1LightResult")
            task_1b_raw = _get_task_output(task_1b, "Task 1b (Strategic Tier)", "StrategicLightResult")
            task_1c_raw = _get_task_output(task_1c, "Task 1c (Geographic Tier)", "GeographicLightResult")
            task_1d_raw = _get_task_output(task_1d, "Task 1d (Category Tier)", "CategoryLightResult")
            task_1e_raw = _get_task_output(task_1e, "Task 1e (Keyword Summary)", "KeywordSummaryResult")

            # Parse pydantic from raw if needed (guardrail compatibility)
            from ..utils.parsing.json_extractor import clean_llm_response

            def _parse_output(task_output, model_class, task_name: str, allow_fallback: bool = False):
                """Parse pydantic output, falling back to raw JSON if needed.

                Args:
                    task_output: CrewAI task output
                    model_class: Pydantic model class to validate against
                    task_name: Name for logging
                    allow_fallback: If True, return default model on failure (for Tier0/Tier1)
                """
                if task_output.pydantic is not None:
                    return task_output.pydantic
                # Parse from raw
                if not task_output.raw:
                    if allow_fallback:
                        logger.warning(f"⚠️ {task_name} has no output - using empty fallback")
                        return model_class()
                    raise ValueError(f"{task_name} has no pydantic or raw output")
                try:
                    cleaned = clean_llm_response(task_output.raw)
                    return model_class.model_validate_json(cleaned)
                except Exception as e:
                    if allow_fallback:
                        logger.warning(f"⚠️ {task_name} failed to parse: {e} - using empty fallback")
                        return model_class()
                    raise ValueError(f"{task_name} failed to parse: {e}")

            task_1a_i_output = _parse_output(task_1a_i_raw, Tier0LightResult, "Task 1a-i", allow_fallback=True)
            task_1a_ii_output = _parse_output(task_1a_ii_raw, Tier1LightResult, "Task 1a-ii", allow_fallback=True)
            task_1b_output = _parse_output(task_1b_raw, StrategicLightResult, "Task 1b")
            task_1c_output = _parse_output(task_1c_raw, GeographicLightResult, "Task 1c")
            task_1d_output = _parse_output(task_1d_raw, CategoryLightResult, "Task 1d")
            task_1e_output = _parse_output(task_1e_raw, KeywordSummaryResult, "Task 1e")

            logger.info("✅ All keyword analysis task outputs extracted successfully")

            # ========================================
            # HYDRATION: Build lookup and hydrate lightweight outputs
            # ========================================

            # Build keyword -> stats lookup from enriched keywords
            lookup = _build_keyword_lookup(enriched_keywords)
            logger.info(f"✅ Built keyword lookup with {len(lookup)} entries for hydration")

            # Hydrate Tier 0 (Task 1a-i) - lightweight -> full TieredKeyword
            tier_0_light = task_1a_i_output.tier_0_keywords or []
            tier_0_keywords = []
            seen_t0 = set()
            dropped_t0 = 0
            for light in tier_0_light:
                kw_key = light.keyword.lower().strip()
                if kw_key not in seen_t0:
                    hydrated = _hydrate_tiered_keyword(light, lookup, tier=0)
                    if hydrated is not None:
                        tier_0_keywords.append(hydrated)
                    else:
                        dropped_t0 += 1
                    seen_t0.add(kw_key)
            if dropped_t0:
                logger.warning(f"⚠️ Data quality: dropped {dropped_t0} Tier-0 keyword(s) with no CSV entry (LLM hallucination)")
            if len(tier_0_keywords) + dropped_t0 < len(tier_0_light):
                logger.warning(f"⚠️ Removed {len(tier_0_light) - len(tier_0_keywords) - dropped_t0} duplicate keywords from tier_0_keywords")
            if not tier_0_keywords and not partitions.get("tier_0_remaining"):
                logger.warning("⚠️ No Tier 0 premium keywords found - niche may lack high-opportunity keywords (opp_score > 200)")

            # Hydrate remaining Tier 0 keywords (Python hydration - no LLM limit exceeded for Tier 0)
            tier_0_remaining = partitions.get("tier_0_remaining", [])
            if tier_0_remaining:
                tier_0_hydrated_remaining = _hydrate_remaining_keywords(
                    remaining=tier_0_remaining,
                    tier=0,
                    tier_strategy=task_1a_i_output.tier_0_strategy,
                    lookup=lookup,
                )
                tier_0_keywords.extend(tier_0_hydrated_remaining)
                logger.info(f"✅ Tier 0: {len(tier_0_light)} analyzed by LLM, {len(tier_0_hydrated_remaining)} hydrated by Python ({len(tier_0_keywords)} total)")

            # Hydrate Tier 1 (Task 1a-ii) - lightweight -> full TieredKeyword
            tier_1_light = task_1a_ii_output.tier_1_keywords or []
            tier_1_keywords = []
            seen_t1 = set()
            dropped_t1 = 0
            for light in tier_1_light:
                kw_key = light.keyword.lower().strip()
                if kw_key not in seen_t1:
                    hydrated = _hydrate_tiered_keyword(light, lookup, tier=1)
                    if hydrated is not None:
                        tier_1_keywords.append(hydrated)
                    else:
                        dropped_t1 += 1
                    seen_t1.add(kw_key)
            if dropped_t1:
                logger.warning(f"⚠️ Data quality: dropped {dropped_t1} Tier-1 keyword(s) with no CSV entry (LLM hallucination)")
            if len(tier_1_keywords) + dropped_t1 < len(tier_1_light):
                logger.warning(f"⚠️ Removed {len(tier_1_light) - len(tier_1_keywords) - dropped_t1} duplicate keywords from tier_1_keywords")
            if not tier_1_keywords and not partitions.get("tier_1_remaining"):
                logger.warning("⚠️ No Tier 1 quick-win keywords found - niche may lack mid-opportunity keywords (opp_score 100-200)")

            # Hydrate remaining Tier 1 keywords (Python hydration)
            tier_1_remaining = partitions.get("tier_1_remaining", [])
            if tier_1_remaining:
                tier_1_hydrated_remaining = _hydrate_remaining_keywords(
                    remaining=tier_1_remaining,
                    tier=1,
                    tier_strategy=task_1a_ii_output.tier_1_quick_win_strategy,
                    lookup=lookup,
                )
                tier_1_keywords.extend(tier_1_hydrated_remaining)
                logger.info(f"✅ Tier 1: {len(tier_1_light)} analyzed by LLM, {len(tier_1_hydrated_remaining)} hydrated by Python ({len(tier_1_keywords)} total)")

            # Hydrate Tier 2 (Task 1b) - lightweight -> full TieredKeyword
            tier_2_light = task_1b_output.tier_2_keywords or []
            tier_2_keywords = []
            seen_t2 = set()
            dropped_t2 = 0
            for light in tier_2_light:
                kw_key = light.keyword.lower().strip()
                if kw_key not in seen_t2:
                    hydrated = _hydrate_tiered_keyword(light, lookup, tier=2)
                    if hydrated is not None:
                        tier_2_keywords.append(hydrated)
                    else:
                        dropped_t2 += 1
                    seen_t2.add(kw_key)
            if dropped_t2:
                logger.warning(f"⚠️ Data quality: dropped {dropped_t2} Tier-2 keyword(s) with no CSV entry (LLM hallucination)")
            if tier_2_keywords and len(tier_2_keywords) + dropped_t2 < len(tier_2_light):
                logger.warning(f"⚠️ Removed {len(tier_2_light) - len(tier_2_keywords) - dropped_t2} duplicate keywords from tier_2_keywords")

            # Hydrate remaining Tier 2 keywords (Python hydration)
            tier_2_remaining = partitions.get("strategic_remaining", [])
            if tier_2_remaining:
                tier_2_hydrated_remaining = _hydrate_remaining_keywords(
                    remaining=tier_2_remaining,
                    tier=2,
                    tier_strategy=task_1b_output.tier_2_strategy,
                    lookup=lookup,
                )
                tier_2_keywords.extend(tier_2_hydrated_remaining)
                logger.info(f"✅ Tier 2: {len(tier_2_light)} analyzed by LLM, {len(tier_2_hydrated_remaining)} hydrated by Python ({len(tier_2_keywords)} total)")

            # Hydrate Geographic (Task 1c) - lightweight -> full GeographicKeywordGroup
            tier_3_light_groups = task_1c_output.tier_3_geographic_groups or []
            tier_3_groups = [
                _hydrate_geographic_group(g, lookup)
                for g in tier_3_light_groups
            ] if tier_3_light_groups else None

            # Hydrate remaining Tier 3 (Geographic) keywords (Python hydration)
            # Note: Geographic keywords are grouped, so remaining ones go into a "Python-Hydrated" group
            tier_3_remaining = partitions.get("geographic_remaining", [])
            if tier_3_remaining:
                # Create TieredKeywords for remaining geographic keywords
                tier_3_hydrated_remaining = _hydrate_remaining_keywords(
                    remaining=tier_3_remaining,
                    tier=3,
                    tier_strategy=task_1c_output.geographic_strategy_notes,
                    lookup=lookup,
                )
                # Create a catch-all geographic group for remaining keywords
                if tier_3_hydrated_remaining:
                    from ..models.seo_strategy import GeographicKeywordGroup, GeographicKeywordEntry
                    remaining_entries = [
                        GeographicKeywordEntry(
                            keyword=kw.keyword,
                            city="[Auto-detected]",
                            search_volume=kw.search_volume,
                            notes=kw.tier_rationale,
                        )
                        for kw in tier_3_hydrated_remaining
                    ]
                    remaining_group = GeographicKeywordGroup(
                        region_name="Python-Hydrated Geographic",
                        total_volume=sum(kw.search_volume or 0 for kw in tier_3_hydrated_remaining),
                        keywords=remaining_entries,
                        strategy_notes="[Auto-tiered] " + (task_1c_output.geographic_strategy_notes or "Applied tier-level strategy programmatically")[:150],
                        competition_level="MEDIUM",
                    )
                    if tier_3_groups is None:
                        tier_3_groups = []
                    tier_3_groups.append(remaining_group)
                    logger.info(f"✅ Tier 3 (Geographic): {sum(len(g.keywords) for g in tier_3_light_groups)} analyzed by LLM, {len(tier_3_hydrated_remaining)} hydrated by Python")

            # Hydrate Category (Task 1d) - lightweight -> full CategoryKeywordGroup
            tier_4_light_groups = task_1d_output.tier_4_category_groups or []
            tier_4_groups = [
                _hydrate_category_group(g, lookup)
                for g in tier_4_light_groups
            ] if tier_4_light_groups else None

            # Hydrate remaining Tier 4 (Category) keywords (Python hydration)
            # Note: Category keywords are grouped, so remaining ones go into a "Python-Hydrated" group
            tier_4_remaining = partitions.get("category_remaining", [])
            if tier_4_remaining:
                # Create TieredKeywords for remaining category keywords
                tier_4_hydrated_remaining = _hydrate_remaining_keywords(
                    remaining=tier_4_remaining,
                    tier=4,
                    tier_strategy=task_1d_output.category_strategy_notes,
                    lookup=lookup,
                )
                # Create a catch-all category group for remaining keywords
                if tier_4_hydrated_remaining:
                    from ..models.seo_strategy import CategoryKeywordGroup, CategoryKeywordEntry
                    remaining_entries = [
                        CategoryKeywordEntry(
                            keyword_name=kw.keyword,
                            search_volume=kw.search_volume,
                            competition=kw.competition,
                            cpc=None,
                        )
                        for kw in tier_4_hydrated_remaining
                    ]
                    remaining_group = CategoryKeywordGroup(
                        category_name="Python-Hydrated Category",
                        total_volume=sum(kw.search_volume or 0 for kw in tier_4_hydrated_remaining),
                        keywords=remaining_entries,
                        strategy_recommendation="[Auto-tiered] " + (task_1d_output.category_strategy_notes or "Applied tier-level strategy programmatically")[:150],
                    )
                    if tier_4_groups is None:
                        tier_4_groups = []
                    tier_4_groups.append(remaining_group)
                    logger.info(f"✅ Tier 4 (Category): {sum(len(g.keywords) for g in tier_4_light_groups)} analyzed by LLM, {len(tier_4_hydrated_remaining)} hydrated by Python")

            logger.info(
                f"✅ Hydration complete: T0={len(tier_0_keywords)}, T1={len(tier_1_keywords)}, "
                f"T2={len(tier_2_keywords)}, T3 groups={len(tier_3_groups) if tier_3_groups else 0}, "
                f"T4 groups={len(tier_4_groups) if tier_4_groups else 0}"
            )

            # ========================================
            # RECOVERY: Force-add untiered keywords from CSV
            # ========================================

            # Build set of all selected keywords (across all tiers)
            selected_keywords = set()

            # Tier 0
            for kw in tier_0_keywords:
                selected_keywords.add(kw.keyword.lower().strip())

            # Tier 1
            for kw in tier_1_keywords:
                selected_keywords.add(kw.keyword.lower().strip())

            # Tier 2
            for kw in (tier_2_keywords or []):
                selected_keywords.add(kw.keyword.lower().strip())

            # Tier 3 (geographic groups)
            for group in (tier_3_groups or []):
                for entry in group.keywords:
                    selected_keywords.add(entry.keyword.lower().strip())

            # Tier 4 (category groups)
            for group in (tier_4_groups or []):
                for entry in group.keywords:
                    selected_keywords.add(entry.keyword_name.lower().strip())

            # Find untiered keywords (in CSV but not selected)
            untiered_keywords = []
            for kw_dict in enriched_keywords:
                kw_key = kw_dict['keyword'].lower().strip()
                if kw_key not in selected_keywords:
                    # Create TieredKeyword with tier=5 (untiered)
                    search_volume = kw_dict.get('search_volume', 0) or 0
                    competition_index = kw_dict.get('competition_index', 50) or 50
                    competition_level = kw_dict.get('competition_level', 'MEDIUM') or 'MEDIUM'
                    opp_score = kw_dict.get('opportunity_score')

                    untiered_keywords.append(TieredKeyword(
                        keyword=kw_dict['keyword'],
                        search_volume=search_volume,
                        competition=f"{competition_level} ({competition_index})",
                        opportunity_score=opp_score,
                        strategy="Auto-recovered: Not selected by LLM analysis",
                        intent=None,
                        tier=5,  # New tier for untiered keywords
                        tier_rationale="Force-added from CSV (not selected by LLM)"
                    ))

            if untiered_keywords:
                logger.info(
                    f"✅ RECOVERY: Force-added {len(untiered_keywords)} untiered keywords "
                    f"(CSV keywords not selected by LLM)"
                )

            # Create merged KeywordAnalysisResult from hydrated data
            keyword_analysis = KeywordAnalysisResult(
                # From Task 1a-i (Tier 0 Premium) - hydrated
                tier_0_keywords=tier_0_keywords if tier_0_keywords else None,
                tier_0_strategy=task_1a_i_output.tier_0_strategy,
                # From Task 1a-ii (Tier 1 Quick Wins) - hydrated
                tier_1_keywords=tier_1_keywords,
                tier_1_quick_win_strategy=task_1a_ii_output.tier_1_quick_win_strategy,
                # From Task 1b (Strategic: T2) - hydrated
                tier_2_keywords=tier_2_keywords if tier_2_keywords else None,
                tier_2_strategy=task_1b_output.tier_2_strategy,
                # From Task 1c (Geographic: T3) - hydrated
                tier_3_geographic_groups=tier_3_groups,
                # From Task 1d (Category: T4) - hydrated
                tier_4_category_groups=tier_4_groups,
                # Force-added untiered keywords (from recovery)
                untiered_keywords=untiered_keywords if untiered_keywords else None,
                # From Task 1e (Summary) - use Python-calculated values for accuracy
                total_keywords_analyzed=total_keywords_analyzed,  # Python-calculated
                total_monthly_volume=total_monthly_volume,        # Python-calculated
                key_findings=task_1e_output.key_findings,
                competitive_positioning=task_1e_output.competitive_positioning,
            )

            # ═══ Cross-tier deduplication ═══
            keyword_analysis = self._deduplicate_across_tiers(keyword_analysis)

            # ═══ GUARDRAIL: Log tier keyword selection for visibility ═══
            tier0_selected = len(keyword_analysis.tier_0_keywords or [])
            tier1_selected = len(keyword_analysis.tier_1_keywords or [])
            tier2_selected = len(keyword_analysis.tier_2_keywords or [])
            untiered_count = len(keyword_analysis.untiered_keywords or [])

            # Calculate geographic and category counts from hydrated groups
            tier_3_hydrated_groups = keyword_analysis.tier_3_geographic_groups or []
            tier_3_group_count = len(tier_3_hydrated_groups)
            tier_3_kw_count = sum(len(g.keywords) for g in tier_3_hydrated_groups)

            tier_4_hydrated_groups = keyword_analysis.tier_4_category_groups or []
            tier_4_cat_count = len(tier_4_hydrated_groups)
            tier_4_kw_count = sum(len(g.keywords) for g in tier_4_hydrated_groups)

            logger.info(
                f"✅ Parallel Tasks 1a-i/ii, 1b-1e merged into KeywordAnalysisResult (hydrated):\n"
                f"  - Task 1a-i (Tier 0 Premium): {tier0_selected} keywords\n"
                f"  - Task 1a-ii (Tier 1 Quick Wins): {tier1_selected} keywords\n"
                f"  - Task 1b (Strategic): T2={tier2_selected}\n"
                f"  - Task 1c (Geographic): {tier_3_kw_count} keywords in {tier_3_group_count} groups\n"
                f"  - Task 1d (Category): {tier_4_kw_count} keywords in {tier_4_cat_count} groups\n"
                f"  - Untiered (recovered): {untiered_count} keywords\n"
                f"  - Task 1e (Summary): {total_keywords_analyzed} keywords, "
                f"{total_monthly_volume} monthly volume"
            )

            # Log Tier 4 category count (already calculated above)

            if tier_4_cat_count < 6:
                logger.warning(
                    f"⚠️ TIER 4 UNDER-CREATION: Only {tier_4_cat_count} categories "
                    f"(expected 6-15). {tier_4_kw_count} keywords in Tier 4."
                )
            else:
                logger.info(f"✅ Tier 4 categories: {tier_4_cat_count} with {tier_4_kw_count} keywords")

            # Log utilization BEFORE recovery (for transparency)
            llm_selected = (
                tier0_selected + tier1_selected + tier2_selected +
                tier_3_kw_count + tier_4_kw_count
            )
            analyzed = keyword_analysis.total_keywords_analyzed or 1
            pre_recovery_utilization = llm_selected / analyzed

            if pre_recovery_utilization < 0.7:
                logger.warning(
                    f"⚠️ LLM keyword selection: {pre_recovery_utilization:.1%} "
                    f"({llm_selected}/{analyzed}) - {untiered_count} keywords recovered"
                )
            else:
                logger.info(
                    f"✅ LLM keyword selection: {pre_recovery_utilization:.1%} "
                    f"({llm_selected}/{analyzed})"
                )

            # Log utilization AFTER recovery (should be 100%)
            total_with_recovery = llm_selected + untiered_count
            post_recovery_utilization = total_with_recovery / analyzed

            logger.info(
                f"✅ Keyword utilization after recovery: {post_recovery_utilization:.1%} "
                f"({total_with_recovery}/{analyzed} keywords)"
            )

            # ========================================
            # Extract and validate Tasks 2-5 (Strategy Development)
            # ========================================
            # Using task.output directly (workaround for CrewAI async bug)

            task_2_raw = _get_task_output(task_2, "Task 2 (Content Strategy)", "ContentStrategyResultLight")
            task_2_light = _parse_output(task_2_raw, ContentStrategyResultLight, "Task 2")
            logger.info("✅ Task 2 output extracted")

            # ========================================
            # HYDRATION: Task 2 - Hydrate lightweight output with CSV data
            # ========================================

            # Note: lookup was already built earlier in parallel flow (line ~2303)
            # Hydrate Task 2 lightweight output to full ContentStrategyResult
            task_2_output = _hydrate_content_strategy(task_2_light, lookup)
            logger.info(
                f"✅ Task 2 hydrated: {len(task_2_output.topic_clusters or [])} topic clusters, "
                f"{len(task_2_output.keyword_based_page_types or [])} page types"
            )

            task_3_raw = _get_task_output(task_3, "Task 3 (Implementation Plan)", "ImplementationPlanResult")
            task_3_output = _parse_output(task_3_raw, ImplementationPlanResult, "Task 3")
            logger.info("✅ Task 3 output extracted")

            # Task 4 (Final Synthesis) removed - only produced conclusion_bottom_line (generic boilerplate)
            # Task 5 (Implementation Guide) removed - technical SEO is now in Task 2

            # ========================================
            # Python merge: Combine all task outputs into SEOStrategyReport
            # ========================================

            result = SEOStrategyReport(
                # Merged keyword analysis (Tasks 1a-1e) - extra fields ignored via extra='ignore'
                **keyword_analysis.model_dump(),
                # Task 2 fields (includes technical_seo_recommendations)
                **task_2_output.model_dump(),
                # Task 3 fields (implementation_roadmap, budget_allocation)
                **task_3_output.model_dump(),
            )

            logger.info(
                f"[OK] 8-Task SEO Strategy Flow complete (PARALLEL: Tasks 1a-i/ii, 1b-1e + 2-3):\n"
                f"  - Tier 0 keywords: {tier0_selected}\n"
                f"  - Tier 1 keywords: {tier1_selected}\n"
                f"  - Tier 2 keywords: {tier2_selected}\n"
                f"  - Untiered keywords (recovered): {untiered_count}\n"
                f"  - Topic clusters: {len(result.topic_clusters) if result.topic_clusters else 0}\n"
                f"  - Total monthly volume: {result.total_monthly_volume if result.total_monthly_volume is not None else 0}\n"
                f"  - Technical SEO: {'✓' if result.technical_seo_recommendations else '✗'}\n"
                f"  - Implementation roadmap: {'✓' if result.implementation_roadmap else '✗'}"
            )
            return result

        except Exception as e:
            logger.error(f"9-Task SEO Strategy Flow (PARALLEL) failed: {e}")
            raise

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            CrewAI UsageMetrics object or None if no execution yet
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
