"""
Tests for configuration management.
"""

import pytest
from nicheiq.config.settings import Settings


def test_settings_default_values():
    """Test that settings have reasonable default values."""
    # This will fail without .env, but tests default values logic
    assert Settings.model_fields["openai_model_name"].default == "gpt-4.1-mini"
    assert Settings.model_fields["log_level"].default == "INFO"
    assert Settings.model_fields["max_retries"].default == 3
    assert Settings.model_fields["timeout_seconds"].default == 60


def test_settings_field_types():
    """Test that settings fields have correct types."""
    assert Settings.model_fields["openai_model_name"].annotation == str
    assert Settings.model_fields["max_retries"].annotation == int
    assert Settings.model_fields["keyword_max_competition"].annotation == float


def test_search_configuration_defaults():
    """Test search configuration defaults."""
    assert Settings.model_fields["min_reddit_upvotes"].default == 10
    assert Settings.model_fields["min_reddit_comments"].default == 5
    assert Settings.model_fields["min_twitter_likes"].default == 10
    assert Settings.model_fields["min_twitter_replies"].default == 5


def test_keyword_configuration_defaults():
    """Test keyword research defaults."""
    assert Settings.model_fields["keyword_min_search_volume"].default == 50
    assert Settings.model_fields["keyword_max_competition"].default == 0.7
    assert Settings.model_fields["target_location"].default is None  # Global data if not specified
    assert Settings.model_fields["target_language"].default is None  # Default language if not specified
