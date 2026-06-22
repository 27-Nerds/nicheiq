"""Tests for the max_tokens safety caps that prevent OpenRouter's 65536-default runaway.

Covers the single resolver, the three request builders (structured SDK path,
invoke_plain ChatOpenAI path, build_crew_llm), and the truncation retry.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from nicheiq.utils import llm_service
from nicheiq.utils.llm_service import (
    LLMService,
    MAX_TOKENS_LARGE,
    MAX_TOKENS_MEDIUM,
    MAX_TOKENS_SMALL,
    _resolve_max_tokens,
    build_crew_llm,
)


@pytest.fixture(autouse=True)
def _structured_tool_path(monkeypatch):
    """These tests assert the FORCED-TOOL structured path. Pin the transport to
    tool_choice and clear the provider allowlist so they don't inherit a
    json_schema/deepinfra .env (tests that need otherwise override after)."""
    monkeypatch.setattr(llm_service.settings, "openrouter_structured_mode", "tool_choice")
    monkeypatch.setattr(llm_service.settings, "openrouter_structured_providers", "")


class _M(BaseModel):
    name: str = Field(..., description="n")
    value: int = Field(..., description="v")


# --- _resolve_max_tokens (single source of truth) ---------------------------

class TestResolveMaxTokens:
    def test_none_falls_back_to_large(self):
        assert _resolve_max_tokens(None, reasoning_enabled=False) == MAX_TOKENS_LARGE

    def test_explicit_passes_through_when_not_reasoning(self):
        assert _resolve_max_tokens(MAX_TOKENS_SMALL, reasoning_enabled=False) == MAX_TOKENS_SMALL
        assert _resolve_max_tokens(32000, reasoning_enabled=False) == 32000

    def test_reasoning_floors_up_to_large(self):
        # A low cap on a reasoning-ON call would let hidden reasoning starve the
        # visible output budget -> floor it up.
        assert _resolve_max_tokens(MAX_TOKENS_SMALL, reasoning_enabled=True) == MAX_TOKENS_LARGE
        assert _resolve_max_tokens(MAX_TOKENS_MEDIUM, reasoning_enabled=True) == MAX_TOKENS_LARGE

    def test_reasoning_keeps_larger_explicit(self):
        assert _resolve_max_tokens(32000, reasoning_enabled=True) == 32000


# --- OpenRouter structured SDK path -----------------------------------------

class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def _resp(finish_reason, content):
    msg = SimpleNamespace(
        tool_calls=None, content=content, reasoning=None, reasoning_details=None
    )
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=None)
    return SimpleNamespace(choices=[choice], usage=usage)


_VALID = '{"name": "x", "value": 1}'
_BAD = "no json here"


def _run_openrouter(responses, *, max_tokens=None, reasoning_effort=None):
    fake = _FakeClient(responses)
    with patch("openai.OpenAI", return_value=fake):
        result = LLMService._invoke_structured_openrouter(
            prompt="p",
            output_model=_M,
            temperature=0.5,
            timeout=10,
            clean_model="deepseek/deepseek-v4-flash",
            api_key="k",
            base_url=None,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
        )
    return result, fake.chat.completions.calls


class TestStructuredOpenRouterCap:
    def test_always_sets_backstop_when_omitted(self):
        (parsed, _usage), calls = _run_openrouter([_resp("stop", _VALID)])
        assert parsed == _M(name="x", value=1)
        assert calls[0]["max_tokens"] == MAX_TOKENS_LARGE  # never unbounded

    def test_respects_explicit_value(self):
        _r, calls = _run_openrouter([_resp("stop", _VALID)], max_tokens=MAX_TOKENS_SMALL)
        assert calls[0]["max_tokens"] == MAX_TOKENS_SMALL

    def test_reasoning_floors_explicit_small_to_large(self):
        _r, calls = _run_openrouter(
            [_resp("stop", _VALID)], max_tokens=MAX_TOKENS_SMALL, reasoning_effort="high"
        )
        assert calls[0]["max_tokens"] == MAX_TOKENS_LARGE


class TestStructuredRetry:
    def test_sets_require_parameters_provider_routing(self):
        # provider.require_parameters merged into extra_body (alongside reasoning_body), so OpenRouter
        # only routes to tool-capable providers.
        _r, calls = _run_openrouter([_resp("stop", _VALID)])
        assert calls[0]["extra_body"]["provider"]["require_parameters"] is True
        assert "only" not in calls[0]["extra_body"]["provider"]  # no allowlist by default
        assert "reasoning" in calls[0]["extra_body"]  # merge, not overwrite

    def test_provider_allowlist_when_configured(self, monkeypatch):
        from nicheiq.utils import llm_service as llm
        monkeypatch.setattr(llm.settings, "openrouter_structured_providers", "deepinfra,baseten,parasail")
        _r, calls = _run_openrouter([_resp("stop", _VALID)])
        prov = calls[0]["extra_body"]["provider"]
        assert prov["only"] == ["deepinfra", "baseten", "parasail"]  # pinned to known-good providers
        # require_parameters MUST be absent when pinned: it filters on `reasoning` (always sent),
        # which a non-reasoning provider (deepinfra/qwen) lacks -> would 404 the pinned route.
        assert "require_parameters" not in prov

    def test_allowlist_skipped_for_first_party_model(self, monkeypatch):
        # A deepinfra-style allowlist must NOT pin a first-party (google) model — that provider
        # doesn't serve gemini and would 404. The global pin only applies to open-weight models.
        from nicheiq.utils import llm_service as llm
        monkeypatch.setattr(llm.settings, "openrouter_structured_providers", "deepinfra")
        fake = _FakeClient([_resp("stop", _VALID)])
        with patch("openai.OpenAI", return_value=fake):
            LLMService._invoke_structured_openrouter(
                prompt="p", output_model=_M, temperature=0.5, timeout=10,
                clean_model="google/gemini-2.5-flash-lite", api_key="k", base_url=None,
                reasoning_effort=None, max_tokens=None,
            )
        prov = fake.chat.completions.calls[0]["extra_body"]["provider"]
        assert prov["require_parameters"] is True
        assert "only" not in prov  # first-party => allowlist skipped

    def test_retries_on_none_choices_then_succeeds(self):
        # A provider 200 with choices=None must be a retryable no-output, not a bare TypeError.
        bad = SimpleNamespace(choices=None, usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0, cost=None))
        (parsed, _usage), calls = _run_openrouter([bad, _resp("stop", _VALID)])
        assert parsed == _M(name="x", value=1)
        assert len(calls) == 2  # retried once on the no-choices response

    def test_raises_clean_error_on_persistent_none_choices(self):
        bad = SimpleNamespace(choices=None, usage=None)
        fake = _FakeClient([bad, bad])
        with patch("openai.OpenAI", return_value=fake):
            with pytest.raises(ValueError, match="no choices"):
                LLMService._invoke_structured_openrouter(
                    prompt="p", output_model=_M, temperature=0.5, timeout=10,
                    clean_model="minimax/x", api_key="k", base_url=None,
                    reasoning_effort=None, max_tokens=None,
                )
        assert len(fake.chat.completions.calls) == 2  # bounded to one retry, then a clean raise

    def test_retries_once_on_length_then_succeeds(self):
        (parsed, _usage), calls = _run_openrouter(
            [_resp("length", _BAD), _resp("stop", _VALID)]
        )
        assert parsed == _M(name="x", value=1)
        assert len(calls) == 2  # one retry fired

    def test_relaxes_to_auto_on_unparseable_then_succeeds(self):
        # forced tool_choice yielded nothing parseable (qwen/OpenRouter case) -> retry with
        # tool_choice='auto', second response carries the JSON in content -> success.
        (parsed, _usage), calls = _run_openrouter(
            [_resp("tool_calls", _BAD), _resp("tool_calls", _VALID)]
        )
        assert parsed == _M(name="x", value=1)
        assert len(calls) == 2
        assert calls[0]["tool_choice"] != "auto"   # first call uses forced tool_choice
        assert calls[1]["tool_choice"] == "auto"   # retry relaxed to auto

    def test_raises_after_two_failures(self):
        fake = _FakeClient([_resp("tool_calls", _BAD), _resp("tool_calls", _BAD)])
        with patch("openai.OpenAI", return_value=fake):
            with pytest.raises(ValueError, match="not found in any"):
                LLMService._invoke_structured_openrouter(
                    prompt="p", output_model=_M, temperature=0.5, timeout=10,
                    clean_model="deepseek/x", api_key="k", base_url=None,
                    reasoning_effort=None, max_tokens=None,
                )
        assert len(fake.chat.completions.calls) == 2  # bounded to one relax retry

    def test_reasoning_on_does_not_relax_retry(self):
        # reasoning ON is already tool_choice='auto' — nothing to relax; a clean-finish None fails fast.
        fake = _FakeClient([_resp("stop", _BAD)])
        with patch("openai.OpenAI", return_value=fake):
            with pytest.raises(ValueError):
                LLMService._invoke_structured_openrouter(
                    prompt="p", output_model=_M, temperature=0.5, timeout=10,
                    clean_model="deepseek/x", api_key="k", base_url=None,
                    reasoning_effort="high", max_tokens=None,
                )
        assert len(fake.chat.completions.calls) == 1  # no relax retry on the reasoning-ON path


# --- invoke_plain inline ChatOpenAI path ------------------------------------

class TestInvokePlainCap:
    def test_openrouter_plain_sets_backstop(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        with patch("nicheiq.utils.llm_service.ChatOpenAI") as mock_chat:
            mock_chat.return_value.invoke.return_value = SimpleNamespace(
                content="hi", response_metadata={"token_usage": {"prompt_tokens": 1, "completion_tokens": 1}}
            )
            LLMService.invoke_plain("p", model_name="openrouter/deepseek/deepseek-v4-flash")
        assert mock_chat.call_args.kwargs["max_tokens"] == MAX_TOKENS_LARGE

    def test_openrouter_plain_respects_explicit(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)
        with patch("nicheiq.utils.llm_service.ChatOpenAI") as mock_chat:
            mock_chat.return_value.invoke.return_value = SimpleNamespace(
                content="hi", response_metadata={"token_usage": {}}
            )
            LLMService.invoke_plain(
                "p", model_name="openrouter/deepseek/deepseek-v4-flash", max_tokens=MAX_TOKENS_SMALL
            )
        assert mock_chat.call_args.kwargs["max_tokens"] == MAX_TOKENS_SMALL


# --- build_crew_llm (CrewAI agents) -----------------------------------------

class TestBuildCrewLlmCap:
    @pytest.fixture(autouse=True)
    def _or_keys(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
        monkeypatch.setattr(llm_service.settings, "openrouter_site_url", None)
        monkeypatch.setattr(llm_service.settings, "openrouter_app_name", None)

    def test_injects_backstop_when_absent(self):
        llm = build_crew_llm("openrouter/deepseek/deepseek-v4-flash", temperature=0.3)
        assert getattr(llm, "max_tokens", None) == MAX_TOKENS_LARGE

    def test_respects_explicit_value(self):
        llm = build_crew_llm("openrouter/x/y", max_tokens=MAX_TOKENS_MEDIUM)
        assert getattr(llm, "max_tokens", None) == MAX_TOKENS_MEDIUM

    def test_reasoning_floors_to_large(self):
        llm = build_crew_llm(
            "openrouter/deepseek/deepseek-v4-pro", reasoning_effort="high", max_tokens=MAX_TOKENS_SMALL
        )
        assert getattr(llm, "max_tokens", None) == MAX_TOKENS_LARGE
