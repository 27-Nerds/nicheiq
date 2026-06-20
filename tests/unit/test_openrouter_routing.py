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


class TestOpenRouterReasoningPassthrough:
    """Reasoning is forwarded to OpenRouter via the unified `reasoning` extra_body."""

    def test_effort_mapping(self):
        from nicheiq.utils.llm_service import openrouter_reasoning_body
        assert openrouter_reasoning_body("high") == {"reasoning": {"effort": "high"}}
        assert openrouter_reasoning_body("medium") == {"reasoning": {"effort": "medium"}}
        assert openrouter_reasoning_body("low") == {"reasoning": {"effort": "low"}}
        assert openrouter_reasoning_body("xhigh") == {"reasoning": {"effort": "high"}}
        # default-OFF policy: "minimal"/"none"/unset => reasoning DISABLED on OpenRouter
        # (enabling it truncates structured output on reasons-by-default models).
        assert openrouter_reasoning_body("minimal") == {"reasoning": {"enabled": False}}
        assert openrouter_reasoning_body("none") == {"reasoning": {"enabled": False}}
        assert openrouter_reasoning_body(None) == {"reasoning": {"enabled": False}}
        assert openrouter_reasoning_body("") == {"reasoning": {"enabled": False}}

    def test_build_crew_llm_forwards_reasoning(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        llm = build_crew_llm("openrouter/deepseek/deepseek-v4-pro", reasoning_effort="high")
        # extra_body reaches the completion call via CrewAI additional_params
        assert getattr(llm, "additional_params", {}).get("extra_body") == {"reasoning": {"effort": "high"}}

    def test_build_crew_llm_no_effort_disables_reasoning(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        # No effort => reasoning explicitly disabled (default-off policy)
        llm = build_crew_llm("openrouter/minimax/minimax-m3", temperature=0.3, max_tokens=1000)
        assert getattr(llm, "additional_params", {}).get("extra_body") == {"reasoning": {"enabled": False}}

    def test_build_llm_kwargs_forwards_reasoning(self, monkeypatch):
        from nicheiq.utils.llm_service import build_llm_kwargs
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        kw = build_llm_kwargs("openrouter/deepseek/deepseek-v4-pro", reasoning_effort="medium")
        assert kw.get("extra_body") == {"reasoning": {"effort": "medium"}}


class _FakeRaw:
    def __init__(self, content):
        self.content = content


class TestStructuredRecovery:
    """invoke_structured recovers JSON from content when native parse returns None."""

    def _model(self):
        from pydantic import BaseModel
        class M(BaseModel):
            a: int
            b: str
        return M

    def test_recovers_plain_json(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        M = self._model()
        assert _recover_structured_output(_FakeRaw('{"a": 1, "b": "x"}'), M) == M(a=1, b="x")

    def test_recovers_fenced_json(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        M = self._model()
        assert _recover_structured_output(_FakeRaw('```json\n{"a": 1, "b": "x"}\n```'), M) == M(a=1, b="x")

    def test_recovers_after_reasoning_tag(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        M = self._model()
        c = "<think>let me reason about this carefully</think>\n{\"a\": 2, \"b\": \"y\"}"
        assert _recover_structured_output(_FakeRaw(c), M) == M(a=2, b="y")

    def test_recovers_json_amid_prose(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        M = self._model()
        c = 'Sure! Here is the result: {"a": 3, "b": "z"} — hope that helps.'
        assert _recover_structured_output(_FakeRaw(c), M) == M(a=3, b="z")

    def test_none_on_truncated(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        assert _recover_structured_output(_FakeRaw('{"a": 1, "b": "x'), self._model()) is None

    def test_none_on_empty(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        assert _recover_structured_output(_FakeRaw(''), self._model()) is None
        assert _recover_structured_output(_FakeRaw(None), self._model()) is None


from types import SimpleNamespace


def _msg(tool_args=None, content=None, reasoning=None, reasoning_details=None):
    """Build an OpenAI-SDK-shaped chat message stub for _structured_from_message."""
    tool_calls = None
    if tool_args is not None:
        tool_calls = [SimpleNamespace(function=SimpleNamespace(arguments=tool_args))]
    return SimpleNamespace(
        tool_calls=tool_calls, content=content,
        reasoning=reasoning, reasoning_details=reasoning_details,
    )


class TestStructuredFromMessage:
    """Universal multi-channel reader for OpenRouter structured output."""

    def _model(self):
        from pydantic import BaseModel
        class M(BaseModel):
            a: int
            b: str
        return M

    def test_reads_tool_call_arguments_first(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        msg = _msg(tool_args='{"a": 1, "b": "x"}', reasoning='{"a": 9, "b": "wrong"}')
        assert _structured_from_message(msg, M) == M(a=1, b="x")  # tool_call wins

    def test_falls_back_to_content(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        assert _structured_from_message(_msg(content='{"a": 2, "b": "y"}'), M) == M(a=2, b="y")

    def test_recovers_from_reasoning_channel(self):
        """The DeepSeek case: tool_calls/content empty, payload leaked into `reasoning`."""
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        msg = _msg(reasoning='{"a": 3, "b": "z"}')
        assert _structured_from_message(msg, M) == M(a=3, b="z")

    def test_recovers_from_reasoning_details_text(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        msg = _msg(reasoning_details=[{"type": "reasoning.text", "text": '{"a": 4, "b": "w"}'}])
        assert _structured_from_message(msg, M) == M(a=4, b="w")

    def test_extracts_json_embedded_in_reasoning_prose(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        msg = _msg(reasoning='Let me think... the answer is {"a": 5, "b": "p"} I believe.')
        assert _structured_from_message(msg, M) == M(a=5, b="p")

    def test_skips_invalid_channel_for_next_valid(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        # tool args truncated/garbage -> fall through to reasoning
        msg = _msg(tool_args='{"a": 1, "b":', reasoning='{"a": 7, "b": "ok"}')
        assert _structured_from_message(msg, M) == M(a=7, b="ok")

    def test_none_when_no_channel_has_valid_json(self):
        from nicheiq.utils.llm_service import _structured_from_message
        M = self._model()
        assert _structured_from_message(_msg(content="no json here", reasoning="still none"), M) is None
        assert _structured_from_message(_msg(), M) is None

    def test_none_on_validation_failure(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        # 'a' must be int; non-coercible string -> validation fails -> None
        assert _recover_structured_output(_FakeRaw('{"a": "not-a-number", "b": "x"}'), self._model()) is None

    def test_recovers_multimodal_list_content(self):
        from nicheiq.utils.llm_service import _recover_structured_output
        M = self._model()
        c = [{"type": "text", "text": '{"a": 4, "b": "q"}'}]
        assert _recover_structured_output(_FakeRaw(c), M) == M(a=4, b="q")
