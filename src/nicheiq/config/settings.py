"""
Centralized configuration management for NicheIQ.
Uses pydantic-settings for type-safe environment variable loading.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
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

    # CrewAI+ (Enterprise) - Optional
    crewai_api_key: Optional[str] = Field(default=None, description="CrewAI+ API key")

    # Serper.dev API
    serper_api_key: str = Field(..., description="Serper.dev API key for Google Search")

    # Reddit API (PRAW)
    reddit_client_id: str = Field(..., description="Reddit client ID")
    reddit_client_secret: str = Field(..., description="Reddit client secret")
    reddit_user_agent: str = Field(
        default="NicheIQ/0.1.0", description="Reddit user agent string"
    )

    # Twitter Configuration
    twitter_username: Optional[str] = Field(default=None, description="Twitter username")
    twitter_password: Optional[str] = Field(default=None, description="Twitter password")
    twitter_email: Optional[str] = Field(default=None, description="Twitter email")
    twitter_cookies_cache: str = Field(
        default=".twitter_cookies.json",
        description="Path to cache Twitter cookies (auto-created after first login)"
    )

    # DataForSEO API
    dataforseo_login: str = Field(..., description="DataForSEO API login")
    dataforseo_password: str = Field(..., description="DataForSEO API password")

    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    timeout_seconds: int = Field(default=30, description="API request timeout in seconds")
    niche_description: Optional[str] = Field(
        default=None, description="Niche/market area to research (optional, can be provided via CLI)"
    )

    # Search Configuration
    max_search_results: int = Field(
        default=20, description="Maximum search results per query"
    )
    min_reddit_upvotes: int = Field(
        default=5, description="Minimum upvotes for Reddit posts"
    )
    min_reddit_comments: int = Field(
        default=3, description="Minimum comments for Reddit posts"
    )
    reddit_comment_limit: Optional[int] = Field(
        default=None,
        description="Max MoreComments to replace (None=all comments, 32=most comments, 0=top-level only)",
    )
    min_twitter_likes: int = Field(default=5, description="Minimum likes for Twitter posts")
    min_twitter_replies: int = Field(
        default=3, description="Minimum replies for Twitter posts"
    )

    # Keyword Research Configuration
    keyword_min_search_volume: int = Field(
        default=50, description="Minimum monthly search volume for keywords"
    )
    keyword_max_competition: float = Field(
        default=0.7, description="Maximum competition level (0-1)"
    )
    target_location: int = Field(
        default=2840, description="Target location code (2840 = United States)"
    )
    target_language: str = Field(default="en", description="Target language code")

    # Output Configuration
    output_dir: Path = Field(
        default=Path("./output"), description="Base output directory"
    )
    reports_dir: Path = Field(
        default=Path("./output/reports"), description="Reports output directory"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create output directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
