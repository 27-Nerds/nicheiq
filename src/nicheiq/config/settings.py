"""
Centralized configuration management for NicheIQ.
Uses pydantic-settings for type-safe environment variable loading.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    openai_model_name: str = Field(default="gpt-4o", description="OpenAI model to use")
    function_calling_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for function/tool calling (cheaper model recommended)"
    )
    content_analysis_llm: str = Field(
        default="gpt-4o",
        description="Model to use for content analysis and categorization tasks (gpt-4o or gpt-4o-mini recommended)"
    )
    thread_validation_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for thread relevance validation in Stage 5 (gpt-4o-mini or gpt-3.5-turbo for cost efficiency)"
    )
    brainstorm_llm: str = Field(
        default="gpt-4o",
        description="Model to use for solution brainstorming/ideation (gpt-4o, o1-mini, or claude-3-5-sonnet for creative thinking)"
    )
    keyword_validation_llm: str = Field(
        default="gpt-4.1-nano",
        description="Model to use for keyword relevance validation in Stage 9.5c (gpt-4.1-nano recommended for cost efficiency)"
    )
    keyword_research_llm: str = Field(
        default="gpt-4o-mini",
        description="Model to use for keyword research crew in Stage 8.8 (gpt-4o-mini for cost efficiency, gpt-4o for better quality)"
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

    # DataForSEO API
    dataforseo_login: str = Field(..., description="DataForSEO API login")
    dataforseo_password: str = Field(..., description="DataForSEO API password")

    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    timeout_seconds: int = Field(default=30, description="API request timeout in seconds")
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
        description="Minimum relevance score (0.0-1.0) for keyword validation in Stage 9.5c (never lowered)"
    )

    # SEO Refinement Settings (Stage 9.5)
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

    # Keyword Enrichment Settings (Stage 9.5 Iterative)
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
    keyword_enrichment_min_coverage: float = Field(
        default=0.7,
        description="Minimum percentage of topic clusters that must have keywords (0.0-1.0)"
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

    # Stage 8.8: Keyword Validation Configuration
    keyword_validation_enabled: bool = Field(
        default=True,
        description="Enable keyword demand validation for top 3 solutions before final selection"
    )
    keyword_min_search_volume: int = Field(
        default=50,
        description="Minimum monthly search volume for a keyword to be considered 'validated'"
    )
    keyword_min_volume_threshold: int = Field(
        default=10,
        description="Minimum search volume threshold for relevance checking (lower than min_search_volume)"
    )
    keyword_pivot_max_attempts: int = Field(
        default=4,
        description="Maximum number of pivot attempts (different seed generation strategies) before accepting best result"
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

    # Stage 8.85: Solution Refinement Configuration
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create output directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_enabled:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
