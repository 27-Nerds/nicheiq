"""
Unit tests for Kimi/Moonshot model detection and routing in llm_service.

Tests is_kimi_model(), build_llm_kwargs() with Kimi models, and
build_llm() Kimi path (returns CrewAI LLM pointed at Moonshot API).
"""

import pytest
from unittest.mock import patch

from nicheiq.utils.llm_service import (
    is_kimi_model,
    build_llm_kwargs,
    build_llm,
)


class TestIsKimiModel:
    """Test is_kimi_model() detection function."""

    def test_detects_kimi_k2_5(self):
        assert is_kimi_model("kimi-k2.5") is True

    def test_detects_kimi_uppercase(self):
        assert is_kimi_model("Kimi-K2.5") is True

    def test_rejects_openai_models(self):
        assert is_kimi_model("gpt-4o") is False
        assert is_kimi_model("gpt-5.2") is False
        assert is_kimi_model("gpt-5.1-codex-max") is False

    def test_rejects_other_models(self):
        assert is_kimi_model("claude-3-opus") is False
        assert is_kimi_model("llama-3") is False


class TestBuildLlmKwargsKimi:
    """Test build_llm_kwargs() with Kimi models."""

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_uses_moonshot_api_key(self, mock_settings):
        mock_settings.moonshot_api_key = "test-moonshot-key"
        kwargs = build_llm_kwargs(model="kimi-k2.5")
        assert kwargs["api_key"] == "test-moonshot-key"

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_sets_moonshot_base_url(self, mock_settings):
        mock_settings.moonshot_api_key = "test-key"
        kwargs = build_llm_kwargs(model="kimi-k2.5")
        assert kwargs["base_url"] == "https://api.moonshot.ai/v1"

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_raises_without_api_key(self, mock_settings):
        mock_settings.moonshot_api_key = None
        with pytest.raises(ValueError, match="MOONSHOT_API_KEY"):
            build_llm_kwargs(model="kimi-k2.5")

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_includes_temperature(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        kwargs = build_llm_kwargs(model="kimi-k2.5", temperature=0.6)
        assert kwargs["temperature"] == 0.6

    @patch('nicheiq.utils.llm_service.settings')
    def test_explicit_base_url_overrides_auto(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        kwargs = build_llm_kwargs(
            model="kimi-k2.5",
            base_url="https://custom.example.com/v1",
        )
        assert kwargs["base_url"] == "https://custom.example.com/v1"

    @patch('nicheiq.utils.llm_service.settings')
    def test_explicit_api_key_overrides_auto(self, mock_settings):
        mock_settings.moonshot_api_key = "auto-key"
        kwargs = build_llm_kwargs(
            model="kimi-k2.5",
            api_key="explicit-key",
        )
        assert kwargs["api_key"] == "explicit-key"

    @patch('nicheiq.utils.llm_service.settings')
    def test_openai_model_still_uses_openai_key(self, mock_settings):
        mock_settings.openai_api_key = "openai-key"
        mock_settings.moonshot_api_key = "moonshot-key"
        kwargs = build_llm_kwargs(model="gpt-4o", temperature=0.5)
        assert kwargs["api_key"] == "openai-key"
        assert "base_url" not in kwargs


class TestBuildLlmKimi:
    """Test build_llm() returns CrewAI LLM for Kimi models."""

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_returns_crewai_llm(self, mock_settings):
        """Verify Kimi models produce a CrewAI-native LLM, not ChatOpenAI."""
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        from crewai.llms.base_llm import BaseLLM
        result = build_llm(model="kimi-k2.5")
        assert isinstance(result, BaseLLM)

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_has_moonshot_base_url(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5")
        assert result.base_url == "https://api.moonshot.ai/v1"

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_has_correct_model_name(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5")
        assert result.model == "kimi-k2.5"

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_does_not_use_codex(self, mock_settings):
        """Verify Kimi models bypass the Codex path."""
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        from crewai.llms.base_llm import BaseLLM
        result = build_llm(model="kimi-k2.5")
        # Should be a CrewAI LLM, not CodexLLM
        assert isinstance(result, BaseLLM)
        assert result.model == "kimi-k2.5"

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_passes_max_output_tokens(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5", max_output_tokens=30000)
        assert result.max_tokens == 30000

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_instant_mode_temperature(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5")
        assert result.temperature == 0.6

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_instant_mode_disables_thinking(self, mock_settings):
        """Verify instant mode disables thinking for deterministic code output."""
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5")
        assert result.additional_params.get("extra_body") == {
            "thinking": {"type": "disabled"}
        }

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_thinking_mode_temperature(self, mock_settings):
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = True
        result = build_llm(model="kimi-k2.5")
        assert result.temperature == 1.0

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_thinking_mode_no_extra_body(self, mock_settings):
        """Verify thinking mode does not disable thinking."""
        mock_settings.moonshot_api_key = "key"
        mock_settings.kimi_thinking = True
        result = build_llm(model="kimi-k2.5")
        assert "extra_body" not in result.additional_params

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_raises_without_api_key(self, mock_settings):
        mock_settings.moonshot_api_key = None
        with pytest.raises(ValueError, match="MOONSHOT_API_KEY"):
            build_llm(model="kimi-k2.5")

    @patch('nicheiq.utils.llm_service.settings')
    def test_kimi_model_explicit_api_key(self, mock_settings):
        mock_settings.moonshot_api_key = "auto-key"
        mock_settings.kimi_thinking = False
        result = build_llm(model="kimi-k2.5", api_key="explicit-key")
        assert result.api_key == "explicit-key"
