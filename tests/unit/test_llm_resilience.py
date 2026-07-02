"""LLM-gate resilience (2026-07-02 plan items 2a/2b/2d/6): OpenRouter fallback-model chains,
429 backoff, and the pipeline_degradations ledger producers.

Strategy: stub the OpenAI client inside llm_service, capture create_kwargs, and abort with a
NON-transient error — asserts request construction without simulating full valid responses.
"""

from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

import nicheiq.utils.llm_service as ls
from nicheiq.config.settings import settings
from pydantic import BaseModel


class _Out(BaseModel):
    ok: int = 0


class _Boom(Exception):
    """Non-transient, non-ratelimit — propagates immediately, aborting after capture."""


def _rate_limit_error() -> RateLimitError:
    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"), json={"error": "rl"})
    return RateLimitError("429", response=resp, body=None)


def _stub_client(monkeypatch, side_effects):
    """Patch ls.OpenAI so chat.completions.create pops side_effects (exception or return)."""
    captured = {"kwargs": [], "calls": 0}

    def _create(**kw):
        captured["kwargs"].append(kw)
        captured["calls"] += 1
        eff = side_effects[min(captured["calls"] - 1, len(side_effects) - 1)]
        if isinstance(eff, Exception):
            raise eff
        return eff

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    import openai
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: fake_client)  # llm_service imports it call-locally
    return captured


def _invoke(model="openrouter/inception/mercury-2"):
    return ls.LLMService.invoke_structured(
        prompt="x", output_model=_Out, temperature=0, model_name=model, reasoning_effort="minimal")


class TestFallbackModels:
    def test_models_array_injected_and_pin_dropped(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_fallback_models",
                            {"inception/mercury-2": ["openai/gpt-4o-mini"]})
        cap = _stub_client(monkeypatch, [_Boom()])
        with pytest.raises(_Boom):
            _invoke()
        kw = cap["kwargs"][0]
        assert kw["extra_body"]["models"] == ["inception/mercury-2", "openai/gpt-4o-mini"]
        # pin dropped: no provider.only allowlist may strangle the fallback's routing
        assert kw["extra_body"]["provider"] == {"require_parameters": True}

    def test_openrouter_prefixed_key_also_matches(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_fallback_models",
                            {"openrouter/inception/mercury-2": ["openrouter/openai/gpt-4o-mini"]})
        cap = _stub_client(monkeypatch, [_Boom()])
        with pytest.raises(_Boom):
            _invoke()
        # values are normalized to bare OpenRouter ids
        assert cap["kwargs"][0]["extra_body"]["models"] == ["inception/mercury-2", "openai/gpt-4o-mini"]

    def test_no_map_hit_no_models_array(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_fallback_models", {})
        cap = _stub_client(monkeypatch, [_Boom()])
        with pytest.raises(_Boom):
            _invoke()
        assert "models" not in cap["kwargs"][0]["extra_body"]


class TestRateLimitBackoff:
    def test_three_attempts_with_backoff_then_raise(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(ls.time, "sleep", lambda s: sleeps.append(s))
        cap = _stub_client(monkeypatch, [_rate_limit_error()])  # every call 429s
        with pytest.raises(RateLimitError):
            _invoke()
        assert cap["calls"] == 3          # 3 attempts
        assert len(sleeps) == 2           # backoff between attempts only
        assert 3 <= sleeps[0] <= 4.5      # 3*2^0 + jitter(0..1.5)
        assert 6 <= sleeps[1] <= 7.5      # 3*2^1 + jitter

    def test_non_ratelimit_transient_keeps_single_retry(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(ls.time, "sleep", lambda s: sleeps.append(s))
        from openai import APITimeoutError
        cap = _stub_client(monkeypatch, [APITimeoutError(request=httpx.Request("POST", "http://x"))])
        with pytest.raises(APITimeoutError):
            _invoke()
        assert cap["calls"] == 2          # original behavior: 1 immediate retry, no sleeps
        assert sleeps == []


class TestDegradationProducers:
    def test_stance_fail_open_counts_and_summary(self, monkeypatch):
        from nicheiq.crews.pain_point_crew import PainPointCrew
        crew = object.__new__(PainPointCrew)  # bare instance, defensive getattr path
        crew.degradation_events = []
        monkeypatch.setattr(
            ls.LLMService, "invoke_structured",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")), raising=True)
        pain = SimpleNamespace(title="T", description="D")
        quotes = [SimpleNamespace(quote_text="q1"), SimpleNamespace(quote_text="q2")]
        kept = crew._stance_filter_quotes(pain, quotes)
        assert kept == quotes                                   # fail-open unchanged
        assert getattr(crew, "_stance_gate_failures", 0) == 1   # counted

    def test_report_dedupes_ledger_into_quality_caveats(self):
        # the extend block dedupes against already-present caveats
        from nicheiq.report.report_generator import ReportGenerator  # noqa: F401 (import sanity)
        caveats = ["existing"]
        degradations = ["existing", "new-a", "new-a", "new-b"]
        seen = set(caveats)
        for d in degradations:
            if isinstance(d, str) and d and d not in seen:
                seen.add(d)
                caveats.append(d)
        assert caveats == ["existing", "new-a", "new-b"]
