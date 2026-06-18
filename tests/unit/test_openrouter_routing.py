"""Tests for OpenRouter provider routing in llm_service."""

import pytest
from langchain_openai import ChatOpenAI

from nicheiq.utils import llm_service
from nicheiq.utils.llm_service import (
    build_crew_llm,
    build_llm,
    is_openrouter_model,
    openrouter_headers,
    resolve_endpoint,
    validate_openrouter_tier_compatibility,
)


class TestIsOpenRouterModel:
    def test_detects_prefix(self):
        assert is_openrouter_model("openrouter/google/gemma-2-27b-it")
        assert is_openrouter_model("OpenRouter/google/gemma")  # case-insensitive

    def test_rejects_non_openrouter(self):
        assert not is_openrouter_model("gpt-4.1-mini")
        assert not is_openrouter_model("kimi-k2.5")
        assert not is_openrouter_model("google/gemma-2-27b-it")  # no prefix


class TestResolveEndpoint:
    def test_openrouter_strips_prefix_and_routes(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
        model, key, base = resolve_endpoint("openrouter/google/gemma-2-27b-it")
        assert model == "google/gemma-2-27b-it"
        assert key == "or-key"
        assert base == "https://openrouter.ai/api/v1"

    def test_openrouter_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", None)
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            resolve_endpoint("openrouter/google/gemma-2-27b-it")

    def test_openai_default_passthrough(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openai_api_key", "sk-oai")
        model, key, base = resolve_endpoint("gpt-4.1-mini")
        assert model == "gpt-4.1-mini"
        assert key == "sk-oai"
        assert base is None

    def test_explicit_base_url_overrides(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        _, _, base = resolve_endpoint("openrouter/x/y", base_url="https://custom/v1")
        assert base == "https://custom/v1"

    def test_kimi_still_routes_to_moonshot(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "moonshot_api_key", "moon-key")
        model, key, base = resolve_endpoint("kimi-k2.5")
        assert model == "kimi-k2.5"
        assert key == "moon-key"
        assert base == "https://api.moonshot.ai/v1"


class TestOpenRouterHeaders:
    def test_none_when_unset(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        assert openrouter_headers() is None

    def test_headers_when_set(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", "https://app")
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", "NicheIQ")
        assert openrouter_headers() == {"HTTP-Referer": "https://app", "X-Title": "NicheIQ"}


class TestBuildCrewLlm:
    def test_openai_non_reasoning_returns_chatopenai(self):
        """Invariant: OpenAI non-reasoning models still return ChatOpenAI (no regression)."""
        llm = build_crew_llm("gpt-4.1-mini", temperature=0.3)
        assert isinstance(llm, ChatOpenAI)

    def test_openrouter_returns_native_crew_llm(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        llm = build_crew_llm(
            "openrouter/google/gemma-2-27b-it",
            temperature=0.3,
            max_tokens=1000,
            frequency_penalty=0.5,
        )
        assert not isinstance(llm, ChatOpenAI)  # native CrewAI LLM, not ChatOpenAI
        assert getattr(llm, "provider", None) == "openai"
        assert getattr(llm, "base_url", None) == "https://openrouter.ai/api/v1"
        assert getattr(llm, "model", None) == "google/gemma-2-27b-it"  # prefix stripped


class TestBuildLlm:
    def test_openrouter_raises(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        with pytest.raises(ValueError, match="OpenRouter is not supported"):
            build_llm("openrouter/google/gemma-2-27b-it")


class TestTierGuard:
    def test_blocks_landing_page_llm(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "landing_page_llm", "openrouter/google/gemma-2-27b-it")
        monkeypatch.setattr(llm_service.settings, "landing_page_execution_llm", "gpt-5.1-codex-max")
        with pytest.raises(ValueError, match="landing-page tiers"):
            validate_openrouter_tier_compatibility()

    def test_blocks_landing_page_execution_llm(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "landing_page_llm", "gpt-5.2")
        monkeypatch.setattr(llm_service.settings, "landing_page_execution_llm", "openrouter/x/y")
        with pytest.raises(ValueError, match="landing-page tiers"):
            validate_openrouter_tier_compatibility()

    def test_warns_but_allows_risky_tier(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "landing_page_llm", "gpt-5.2")
        monkeypatch.setattr(llm_service.settings, "landing_page_execution_llm", "gpt-5.1-codex-max")
        monkeypatch.setattr(llm_service.settings, "content_analysis_llm", "openrouter/google/gemma-2-27b-it")
        # Should not raise (warn only)
        validate_openrouter_tier_compatibility()

    def test_default_config_passes(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "landing_page_llm", "gpt-5.2")
        monkeypatch.setattr(llm_service.settings, "landing_page_execution_llm", "gpt-5.1-codex-max")
        monkeypatch.setattr(llm_service.settings, "content_analysis_llm", "gpt-4.1-mini")
        monkeypatch.setattr(llm_service.settings, "function_calling_llm", "gpt-4o-mini")
        monkeypatch.setattr(llm_service.settings, "brainstorm_llm", "gpt-5.2")
        monkeypatch.setattr(llm_service.settings, "ideation_judge_llm", "gpt-5.4-mini")
        monkeypatch.setattr(llm_service.settings, "ideation_refine_llm", "gpt-5.2")
        validate_openrouter_tier_compatibility()


class TestActualCostCapture:
    """LLMService._extract_usage reads OpenRouter's actual cost; TokenUsage carries it."""

    def test_extract_usage_reads_cost(self):
        from nicheiq.utils.llm_service import LLMService
        meta = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0009}}
        usage = LLMService._extract_usage(meta, "openrouter/google/gemma-2-27b-it")
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5
        assert usage.cost == 0.0009
        assert usage.to_dict()["cost"] == 0.0009

    def test_extract_usage_no_cost_is_none(self):
        from nicheiq.utils.llm_service import LLMService
        meta = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        usage = LLMService._extract_usage(meta, "gpt-4o")
        assert usage.cost is None
        assert "cost" in usage.to_dict()
