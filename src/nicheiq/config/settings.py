"""
Centralized configuration management for NicheIQ.
Uses pydantic-settings for type-safe environment variable loading.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _patch_tiktoken_models():
    """
    Patch tiktoken's MODEL_TO_ENCODING to support new OpenAI models.

    This runs at import time to ensure all libraries (CrewAI, LangChain)
    can tokenize new models like gpt-5.2, gpt-5.1, etc.
    """
    try:
        from tiktoken import model as tm

        # Models not yet in tiktoken 0.12.0 - all use o200k_base encoding
        new_models = {
            # GPT-5.2 series
            "gpt-5.2": "o200k_base",
            "gpt-5.2-chat-latest": "o200k_base",
            "gpt-5.2-pro": "o200k_base",
            # GPT-5.1 series
            "gpt-5.1": "o200k_base",
            "gpt-5.1-chat-latest": "o200k_base",
            "gpt-5.1-codex-max": "o200k_base",
            "gpt-5.1-codex": "o200k_base",
            "gpt-5.1-codex-mini": "o200k_base",
            # GPT-5 codex variants
            "gpt-5-codex": "o200k_base",
            "gpt-5-search-api": "o200k_base",
            "gpt-5-pro": "o200k_base",
            # o4 series
            "o4": "o200k_base",
            "o4-mini-deep-research": "o200k_base",
            # GPT-4.1 series (uses o200k_base like GPT-4o)
            "gpt-4.1": "o200k_base",
            "gpt-4.1-mini": "o200k_base",
            "gpt-4.1-nano": "o200k_base",
        }

        for model, encoding in new_models.items():
            if model not in tm.MODEL_TO_ENCODING:
                tm.MODEL_TO_ENCODING[model] = encoding

    except ImportError:
        pass  # tiktoken not installed


# Patch tiktoken at import time
_patch_tiktoken_models()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model_name: str = Field(default="gpt-4.1-mini", description="OpenAI model to use (safe non-reasoning default; prod overrides via env)")
    function_calling_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for function/tool calling (cheaper model recommended)"
    )
    content_analysis_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for content analysis (gpt-4.1-mini: needs 1M context for large Reddit content; gpt-4o is only 128K)"
    )
    thread_validation_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for thread relevance validation in Stage 5 (gpt-4o-mini or gpt-3.5-turbo for cost efficiency)"
    )
    brainstorm_llm: str = Field(
        default="gpt-5.2",
        description="Model to use for solution brainstorming/ideation (gpt-5.2 recommended for creative thinking)"
    )
    brainstorm_reasoning_effort: str | None = Field(
        default="high",
        description=(
            "Reasoning effort for GPT-5 series models: 'none', 'minimal', 'low', 'medium', "
            "'high', 'xhigh'. Default 'high' — this is the ONLY working creativity/depth "
            "knob for reasoning models (temperature is unsupported). Ignored by older models."
        )
    )
    keyword_validation_llm: str = Field(
        default="gpt-5-nano",
        description="Model to use for keyword relevance validation in Phase 6c (gpt-5-nano at minimal reasoning effort for cost efficiency)"
    )
    keyword_research_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for keyword research crew in keyword validation (gpt-4o-mini for cost efficiency, gpt-4o for better quality)"
    )
    pain_point_validation_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for pain point analysis/validation in Stage 6 (use non-reasoning model to allow max_tokens)"
    )
    competitor_extraction_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for extracting product/brand/tool names from social discussion sentences"
    )
    pain_solution_mapping_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for pain-to-solution mapping in Stage 10 report generation (gpt-4.1-mini: non-reasoning, good instruction-following)"
    )
    quote_enrichment_llm: str = Field(
        default="gpt-4.1-mini",
        description="Model for quote enrichment agent (Task 4) in Stage 6 - uses vector search to find quotes"
    )
    quote_enrichment_target_per_pain_point: int = Field(
        default=8,
        description="Target number of quotes per pain point in Task 4 enrichment"
    )
    landing_page_llm: str = Field(
        default="gpt-5.2",
        description="Model to use for landing page generation (gpt-5.2 recommended for high-quality creative output)"
    )
    # 3-tier reasoning effort for landing page agents
    landing_page_creative_reasoning_effort: str = Field(
        default="high",
        description="Reasoning effort for creative agents (Strategist, Creative Director, Visual Designer, Brand Designer, Copywriter). 'high' recommended."
    )
    landing_page_execution_reasoning_effort: str = Field(
        default="medium",
        description="Reasoning effort for code generation agents (HTML Developer, Animation Enhancer). 'medium' recommended."
    )
    landing_page_validation_reasoning_effort: str = Field(
        default="low",
        description="Reasoning effort for validation agents (QA Reviewer). 'low' recommended for structured validation tasks."
    )
    landing_page_execution_llm: str = Field(
        default="gpt-5.1-codex-max",
        description="Model for execution agents (HTML Developer, Animation Enhancer, QA Reviewer). Codex models recommended for reliable code generation."
    )

    # Moonshot AI (Kimi) Configuration
    moonshot_api_key: str | None = Field(
        default=None,
        description="Moonshot AI API key for Kimi models (get from platform.moonshot.ai)"
    )
    kimi_thinking: bool = Field(
        default=False,
        description="Enable Kimi thinking mode (deeper reasoning, temp=1.0). Default: False (instant mode, temp=0.6, faster and cheaper)."
    )

    # CrewAI+ (Enterprise) - Optional
    crewai_api_key: str | None = Field(default=None, description="CrewAI+ API key")

    # Serper.dev API
    serper_api_key: str = Field(..., description="Serper.dev API key for Google Search")

    # Reddit API (PRAW)
    reddit_client_id: str = Field(..., description="Reddit client ID")
    reddit_client_secret: str = Field(..., description="Reddit client secret")
    reddit_user_agent: str = Field(
        default="NicheIQ/0.1.0", description="Reddit user agent string"
    )

    # Twitter Configuration
    twitter_username: str | None = Field(default=None, description="Twitter username")
    twitter_password: str | None = Field(default=None, description="Twitter password")
    twitter_email: str | None = Field(default=None, description="Twitter email")
    twitter_cookies_cache: str = Field(
        default="data/twitter_cookies.json",
        description="Path to cache Twitter cookies (auto-created after first login)"
    )
    enable_twitter: bool = Field(
        default=True,
        description="Enable/disable Twitter/X data collection (set to False to skip Twitter entirely)"
    )
    enable_reddit: bool = Field(
        default=True,
        description="Enable/disable Reddit data collection (set to False to skip Reddit entirely)"
    )
    enable_hackernews: bool = Field(
        default=True,
        description="Enable/disable Hacker News data collection via Algolia API (free, no auth needed)"
    )
    enable_youtube: bool = Field(
        default=False,
        description="Enable/disable YouTube transcript collection (requires youtube-transcript-api)"
    )
    enable_seed_enrichment: bool = Field(
        default=True,
        description="Best-effort live-evidence enrichment (Hacker News) for catalog-seeded jobs; failures never block the job"
    )
    min_hn_points: int = Field(
        default=5, description="Minimum points for Hacker News stories"
    )
    min_hn_comments: int = Field(
        default=3, description="Minimum comments for Hacker News stories"
    )
    min_youtube_views: int = Field(
        default=0, description="Minimum views for YouTube videos (0 = accept all, Serper view parsing is ~40-60% reliable)"
    )
    youtube_api_key: str | None = Field(
        default=None,
        description="YouTube Data API v3 key (optional). Enables comment collection and accurate engagement metrics."
    )
    max_youtube_videos: int = Field(
        default=25,
        description="Maximum YouTube videos to collect per run (each costs 1 API quota unit for comments)."
    )
    max_youtube_comments_per_video: int = Field(
        default=20,
        description="Maximum top comments to fetch per YouTube video (by relevance)."
    )
    min_youtube_comment_likes: int = Field(
        default=5,
        description="Minimum likes for YouTube comments to be included (reduces noise)."
    )
    min_youtube_comment_length: int = Field(
        default=50,
        description="Minimum character length for YouTube comments to be included."
    )
    webshare_api_key: str | None = Field(
        default=None,
        description="Webshare API key. When set, YouTube transcript fetching routes "
                    "through direct-mode proxies fetched from /api/v2/proxy/list. "
                    "Get key from https://proxy2.webshare.io/userapi/keys."
    )
    webshare_proxy_country_codes: list[str] | None = Field(
        default=None,
        description="Optional ISO country code filter for the Webshare proxy pool "
                    "(e.g. 'US,GB' comma-separated, or JSON array). None = all countries."
    )

    # DataForSEO API
    dataforseo_login: str = Field(..., description="DataForSEO API login")
    dataforseo_password: str = Field(..., description="DataForSEO API password")

    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    timeout_seconds: int = Field(default=60, description="API request timeout in seconds (increased for large batches)")
    niche_description: str | None = Field(
        default=None, description="Niche/market area to research (optional, can be provided via CLI)"
    )

    # Search Configuration
    num_search_queries: int = Field(
        default=40, description="Number of search queries to generate for discovering pain points"
    )
    max_search_results: int = Field(
        default=20, description="Maximum search results per query"
    )
    min_reddit_upvotes: int = Field(
        default=10, description="Minimum upvotes for Reddit posts (higher threshold for quality)"
    )
    min_reddit_comments: int = Field(
        default=5, description="Minimum comments for Reddit posts (higher threshold for quality)"
    )
    reddit_comment_limit: int | None = Field(
        default=None,
        description="Max MoreComments to replace (None=all comments, 32=most comments, 0=top-level only)",
    )
    min_comment_length: int = Field(
        default=50,
        description="Minimum character length for Reddit comments (filters out short/low-value comments)"
    )
    min_comment_score: int = Field(
        default=2,
        description="Minimum score for Reddit comments (filters out low-quality/downvoted comments)"
    )
    max_reddit_content_tokens: int = Field(
        default=150_000,
        description="Maximum tokens for Reddit content in PainPointCrew (filters by engagement/recency)"
    )
    min_twitter_likes: int = Field(default=10, description="Minimum likes for Twitter posts (higher threshold for quality)")
    min_twitter_replies: int = Field(
        default=5, description="Minimum replies for Twitter posts (higher threshold for quality)"
    )

    # Keyword Research Configuration
    keyword_min_search_volume: int = Field(
        default=50, description="Minimum monthly search volume for keywords"
    )
    keyword_max_competition: float = Field(
        default=0.7, description="Maximum competition level (0-1)"
    )
    target_location: int | None = Field(
        default=None, description="Target location code (e.g., 2840 = United States). If None, API uses global data."
    )
    target_language: str | None = Field(
        default=None, description="Target language code (e.g., 'en'). If None, API uses default language."
    )
    keyword_relevance_threshold: float = Field(
        default=0.65,
        description="Minimum relevance score (0.0-1.0) for keyword validation in Phase 6c (never lowered)"
    )

    # SEO Refinement Settings (Stage 12)
    seo_refinement_enabled: bool = Field(
        default=True,
        description="Enable SEO score refinement based on keyword data from Stage 9"
    )
    seo_refinement_volume_baselines: dict = Field(
        default={
            'directory': 50_000,
            'aggregator': 50_000,
            'comparison-tool': 30_000,
            'marketplace': 30_000,
            'saas': 10_000
        },
        description="Baseline monthly volumes by project type for refinement calculations"
    )
    seo_refinement_max_volume_boost: float = Field(
        default=1.2,
        description="Maximum volume multiplier boost (default 1.2 = 20% boost)"
    )
    seo_refinement_max_tier1_boost: float = Field(
        default=0.20,
        description="Maximum Tier 1 keyword boost (default 0.20 = 20% boost)"
    )
    seo_refinement_volume_discount_floor: float = Field(
        default=0.7,
        description="Minimum volume discount for CAC calculations (default 0.7 = 30% max discount)"
    )
    seo_refinement_min_competition_modifier: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description="Minimum competition modifier floor. Even highly competitive keywords allow some SEO value through long-tail variants."
    )
    seo_refinement_keyword_evidence_enabled: bool = Field(
        default=True,
        description="Enable keyword-evidence floor: when real keyword data shows SEO opportunity, prevent a false-zero LLM baseline from killing the score"
    )
    seo_refinement_max_keyword_evidence: float = Field(
        default=0.35, ge=0.0, le=1.0,
        description="Maximum keyword evidence floor. Rescue mechanism cap, not a replacement for LLM assessment."
    )

    # Keyword Enrichment Settings (Stage 6 Iterative)
    keyword_enrichment_target_count: int = Field(
        default=150,
        description="Target number of keywords with meaningful search volume"
    )
    keyword_enrichment_min_volume: int = Field(
        default=500,
        description="Minimum monthly search volume for a keyword to count toward target"
    )
    keyword_enrichment_max_rounds: int = Field(
        default=5,
        description="Maximum enrichment iterations to prevent runaway costs"
    )
    keyword_enrichment_batch_size: int = Field(
        default=12,
        description="Number of seeds per DataForSEO API call (reduced for better quality)"
    )
    keyword_cluster_min_coverage: float = Field(
        default=0.7,
        description=(
            "Minimum percentage of topic clusters that must have keywords (0.0-1.0). "
            "Renamed from keyword_enrichment_min_coverage: that name was defined TWICE "
            "with different meanings, and Python silently kept the later 0.30 enrichment "
            "threshold — so this 0.7 cluster threshold never actually applied. Restoring "
            "it may add enrichment rounds (more DataForSEO calls)."
        )
    )

    # Parallel Validation Settings
    validation_parallel_enabled: bool = Field(
        default=True,
        description="Enable parallel batch processing for validation tasks (keyword and thread validation)"
    )
    keyword_validation_max_workers: int = Field(
        default=3,
        description="Maximum parallel workers for keyword validation (Phase 6c). Recommended: 3-5 for balance of speed and API limits"
    )
    keyword_validation_batch_size: int = Field(
        default=50,
        description="Number of keywords per API call within each parallel worker (Phase 6c). Recommended: 50-150"
    )
    thread_validation_max_workers: int = Field(
        default=4,
        description="Maximum parallel workers for thread validation (Stage 5). Recommended: 3-5 for balanced throughput"
    )

    # Token Monitoring Configuration (Soft Caps for Cost Control)
    token_monitoring_enabled: bool = Field(
        default=True,
        description="Enable token counting and cost monitoring for LLM inputs"
    )
    token_warning_threshold: int = Field(
        default=200_000,
        description="Log warning when content exceeds this token count (for cost visibility)"
    )
    token_soft_cap_enabled: bool = Field(
        default=False,
        description="Enable soft cap enforcement (logs critical warning but doesn't fail)"
    )
    token_soft_cap: int = Field(
        default=400_000,
        description="Soft cap token limit - if enabled, logs critical warning when exceeded"
    )
    cost_logging_enabled: bool = Field(
        default=True,
        description="Log estimated API costs for token usage"
    )

    # Cost Budget Configuration
    cost_budget_enabled: bool = Field(
        default=False,
        description="Enable cost budget tracking (logs warning when approaching limit)"
    )
    cost_budget_limit: float = Field(
        default=5.00,
        gt=0,
        description="Maximum API cost budget per run in USD (soft limit, logs warning when exceeded)"
    )

    # Reddit Post Cache (PostgreSQL-backed)
    reddit_post_cache_enabled: bool = Field(
        default=True,
        description="Enable PostgreSQL-backed Reddit thread cache to avoid re-fetching posts via PRAW"
    )
    reddit_post_cache_ttl_hours: int = Field(
        default=168,
        description="TTL in hours for cached Reddit threads (default 168 = 7 days)"
    )

    # Reddit Freshness Search Configuration
    reddit_freshness_search_enabled: bool = Field(
        default=True,
        description="Enable date-filtered Serper search pass for fresh Reddit posts"
    )
    reddit_freshness_tbs: str = Field(
        default="qdr:y",
        description="Google tbs (time-based search) param for freshness pass (qdr:d, qdr:m, qdr:y)"
    )
    reddit_freshness_query_fraction: float = Field(
        default=0.3,
        description="Fraction of queries to use for freshness Serper pass (0.0-1.0)"
    )

    # PRAW Native Search Configuration
    reddit_native_search_enabled: bool = Field(
        default=True,
        description="Enable PRAW native subreddit search for very recent posts"
    )
    reddit_native_search_time_filter: str = Field(
        default="month",
        description="PRAW time_filter for native search (hour, day, week, month, year, all)"
    )
    reddit_native_search_query_fraction: float = Field(
        default=0.25,
        description="Fraction of queries to use for PRAW native search (0.0-1.0)"
    )
    reddit_native_search_max_results: int = Field(
        default=10,
        description="Max results per query+subreddit combination in PRAW native search"
    )

    # Token Budget Freshness Reserve
    token_budget_freshness_reserve: float = Field(
        default=0.25,
        description="Fraction of token budget reserved for fresh posts (0 = disabled)"
    )
    token_budget_freshness_days: int = Field(
        default=180,
        description="Posts younger than this (days) are considered 'fresh' for token budget reserve"
    )

    # Solution Validation Configuration
    top_solutions_for_validation: int = Field(
        default=5,
        description=(
            "Number of top solutions to validate with pricing, keywords, and competitive "
            "analysis. Default 5 covers ALL refined solutions (3-5 generated) so novel "
            "ideas aren't structurally excluded from demand validation; batched keyword "
            "expansion keeps the API cost roughly flat vs the old top-3."
        )
    )

    # keyword validation: Keyword Validation Configuration
    keyword_validation_enabled: bool = Field(
        default=True,
        description="Enable keyword demand validation for top N solutions before final selection"
    )
    # NOTE: keyword_min_search_volume (used by validation too) is defined once
    # in the Keyword Research Configuration section above — it was previously
    # duplicated here with the same default, which Python silently collapsed.
    keyword_min_volume_threshold: int = Field(
        default=10,
        description="Minimum search volume threshold for relevance checking (lower than min_search_volume)"
    )
    keyword_pivot_max_attempts: int = Field(
        default=3,
        description=(
            "Maximum number of pivot attempts (different seed generation strategies) before "
            "accepting best result. Most successful validations land on attempts 1-2; "
            "3 keeps an adequate fallback at lower DataForSEO cost."
        )
    )
    keyword_quick_expansion_size: int = Field(
        default=50,
        description="Target number of keywords for quick expansion during relevance testing"
    )
    keyword_validation_top_pain_points: int = Field(
        default=5,
        description="Number of top pain points to include in keyword validation context"
    )
    keyword_validation_top_competitors: int = Field(
        default=10,
        description="Number of top competitors to include in keyword validation context"
    )
    keyword_validation_temperature: float = Field(
        default=0.7,
        description="LLM temperature for keyword research crew (0.7 recommended for creative tasks with constraints)"
    )

    # Phase 6c: Keyword Enrichment Quality Gates
    keyword_enrichment_min_coverage: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Minimum coverage rate for keyword enrichment (validated/total). Default 0.30 = warn if <30% pass validation"
    )
    keyword_enrichment_target_coverage: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Target coverage rate for keyword enrichment. Default 0.60 = celebrate if ≥60% pass validation"
    )
    keyword_tiering_min_coverage: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Minimum tiering coverage (tiered_keywords/enriched_keywords). Warn if below this threshold"
    )

    # Tier difficulty gates (keywords above these thresholds get demoted to lower tiers)
    # These gates ensure "quick win" tiers only contain actually achievable keywords
    tier_0_max_difficulty: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Max keyword_difficulty for Tier 0 Premium keywords. Keywords with higher difficulty demoted to Tier 2."
    )
    tier_1_max_difficulty: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Max keyword_difficulty for Tier 1 Quick Win keywords. Keywords with higher difficulty demoted to Tier 2."
    )
    tier_2_max_difficulty: int = Field(
        default=75,
        ge=0,
        le=100,
        description="Max keyword_difficulty for Tier 2 Strategic keywords. Very hard keywords still included but flagged."
    )

    @field_validator('reddit_comment_limit', 'target_location', mode='before')
    @classmethod
    def parse_empty_string_as_none(cls, v):
        """Convert empty string to None for optional int fields."""
        if v == '':
            return None
        return v

    @field_validator('webshare_proxy_country_codes', mode='before')
    @classmethod
    def parse_country_codes(cls, v):
        """Accept comma-separated env string or JSON array; emit list[str] or None."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            return [c.strip().upper() for c in v.split(',') if c.strip()]
        return v

    @field_validator('keyword_validation_top_pain_points', 'keyword_validation_top_competitors')
    @classmethod
    def validate_positive_count(cls, v):
        """Validate that count fields are at least 1."""
        if v < 1:
            raise ValueError("Must be at least 1")
        return v

    @field_validator('keyword_validation_temperature')
    @classmethod
    def validate_temperature_range(cls, v):
        """Validate that temperature is in valid range for LLMs."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @field_validator('keyword_enrichment_min_coverage', 'keyword_enrichment_target_coverage', 'keyword_tiering_min_coverage', 'keyword_cluster_min_coverage')
    @classmethod
    def validate_coverage_percentage(cls, v):
        """Validate coverage percentages are between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Coverage must be between 0.0 and 1.0")
        return v

    # Stage 10: Solution Refinement Configuration
    solution_refinement_enabled: bool = Field(
        default=True,
        description="Enable strategic refinement of selected solution based on keyword insights"
    )

    # Output Configuration
    output_dir: Path = Field(
        default=Path("./output"), description="Base output directory"
    )
    reports_dir: Path = Field(
        default=Path("./output/reports"), description="Reports output directory"
    )

    # Checkpoint Configuration
    checkpoint_enabled: bool = Field(
        default=True,
        description="Enable checkpoint/resume functionality to recover from failures"
    )
    checkpoint_dir: Path = Field(
        default=Path("./output/checkpoints"),
        description="Checkpoint storage directory"
    )
    checkpoint_max_age_days: int = Field(
        default=7,
        description="Maximum age of checkpoints before auto-cleanup (0 = disable cleanup)"
    )
    checkpoint_auto_cleanup: bool = Field(
        default=True,
        description="Automatically cleanup old checkpoints on startup"
    )

    # Report Generation Validation Thresholds
    # Market Validation Levels
    market_validation_strong_volume: int = Field(
        default=100_000,
        description="Minimum total search volume for STRONG market validation level"
    )
    market_validation_strong_pain_points: int = Field(
        default=10,
        description="Minimum pain point count for STRONG market validation level"
    )
    market_validation_moderate_volume: int = Field(
        default=30_000,
        description="Minimum total search volume for MODERATE market validation level"
    )
    market_validation_moderate_pain_points: int = Field(
        default=5,
        description="Minimum pain point count for MODERATE market validation level"
    )

    # Go/No-Go Verdict Thresholds
    verdict_go_avg_score: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        description="Minimum average score (all 4 scores) for Go verdict"
    )
    verdict_go_min_individual_score: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Minimum individual score (market_fit, tech_feasibility) for Go verdict"
    )
    verdict_conditional_avg_score: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum average score for Conditional verdict"
    )
    verdict_conditional_min_individual_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Minimum individual score for Conditional verdict"
    )

    # STRIVE market-sizing pre-check
    strive_talked_about_min_mentions: int = Field(
        default=30,
        ge=0,
        description=(
            "Minimum corpus-wide unique discussions for the STRIVE 'Talked About' "
            "criterion. total_mentions is evidence-grounded (unique post IDs "
            "matched by quote vector search) instead of summed LLM estimates. "
            "Recalibrated 2026-06-11 from the golden run: a GOLD-tier corpus "
            "(123 relevant discussions, 910 comments) produced 44 corpus-unique "
            "mentions, so the old default of 50 — tuned to inflated LLM sums — "
            "failed strong data."
        )
    )

    # Pain Point & Competitive Thresholds
    pain_point_high_priority_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum severity score for high-priority pain point classification"
    )
    competitive_intensity_low_threshold: int = Field(
        default=3,
        description="Maximum competitor count for 'Low' competitive intensity classification"
    )
    competitive_intensity_high_threshold: int = Field(
        default=8,
        description="Minimum competitor count for 'High' competitive intensity classification"
    )

    # Report Formatting Thresholds
    report_max_quote_length: int = Field(
        default=200,
        gt=0,
        description="Maximum character length for pain point quotes in evidence appendix (0 = unlimited)"
    )

    # Score Accessor Defaults
    score_accessor_default_fallback: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default score value when score data is missing (used by ScoreAccessor)"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create output directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_enabled:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
