"""Tests for the landing-model preflight check (F-034).

validate_model_available() guards the eventual retirement of pinned model ids
(gpt-5.3-codex today; its predecessor gpt-5.1-codex-max was retired and broke
landing jobs mid-generation). The check is fail-OPEN: only an explicit
404/model_not_found raises; every other error proceeds.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root, for `worker` package

import openai as openai_module

from nicheiq.utils.llm_service import validate_model_available


class _FakeAPIError(Exception):
    """Stands in for openai.APIStatusError (duck-typed: status_code + body)."""

    def __init__(self, status_code=None, body=None):
        super().__init__("fake api error")
        self.status_code = status_code
        self.body = body


class _FakeClient:
    """Mocks the INVOCATION probe surface (responses.create for codex ids,
    chat.completions.create otherwise) — a metadata retrieve is not sufficient
    because retired ids can stay listed while invocation 404s."""

    def __init__(self, exc=None):
        self._exc = exc
        self.retrieved = []
        self.responses = SimpleNamespace(create=self._probe)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._probe_chat))

    def _probe(self, model, **_kwargs):
        self.retrieved.append(model)
        if self._exc is not None:
            raise self._exc
        return {"id": model}

    def _probe_chat(self, model, **_kwargs):
        return self._probe(model)


def _patch_client(monkeypatch, exc=None):
    client = _FakeClient(exc=exc)
    monkeypatch.setattr(openai_module, "OpenAI", lambda **_kwargs: client)
    return client


class TestValidateModelAvailable:
    def test_available_model_returns_true(self, monkeypatch):
        client = _patch_client(monkeypatch)
        assert validate_model_available("gpt-5.3-codex") is True
        assert client.retrieved == ["gpt-5.3-codex"]

    def test_404_raises_with_actionable_message(self, monkeypatch):
        _patch_client(monkeypatch, exc=_FakeAPIError(status_code=404))
        with pytest.raises(ValueError) as excinfo:
            validate_model_available("gpt-5.1-codex-max")
        msg = str(excinfo.value)
        assert "gpt-5.1-codex-max" in msg
        assert "retired" in msg
        assert "LANDING_PAGE_EXECUTION_LLM" in msg
        assert "LANDING_PREFLIGHT_MODEL_CHECK" in msg

    def test_model_not_found_body_code_raises(self, monkeypatch):
        _patch_client(
            monkeypatch,
            exc=_FakeAPIError(status_code=400, body={"error": {"code": "model_not_found"}}),
        )
        with pytest.raises(ValueError, match="model_not_found"):
            validate_model_available("gpt-old-retired")

    def test_other_api_errors_fail_open(self, monkeypatch):
        _patch_client(monkeypatch, exc=_FakeAPIError(status_code=500))
        assert validate_model_available("gpt-5.3-codex") is True

    def test_network_error_fails_open(self, monkeypatch):
        _patch_client(monkeypatch, exc=ConnectionError("dns down"))
        assert validate_model_available("gpt-5.3-codex") is True

    def test_openrouter_and_kimi_ids_skip_check(self, monkeypatch):
        client = _patch_client(monkeypatch, exc=_FakeAPIError(status_code=404))
        assert validate_model_available("openrouter/x-ai/grok-4.3") is True
        assert validate_model_available("kimi-k2.5") is True
        assert client.retrieved == []  # never reached the API


class TestLandingPreflightGate:
    """The worker-side gate honours settings.landing_preflight_model_check."""

    def test_flag_off_skips_check(self, monkeypatch):
        from worker import tasks as worker_tasks
        from nicheiq.utils import llm_service

        monkeypatch.setattr(
            worker_tasks.settings, "landing_preflight_model_check", False
        )

        def _boom(_model_id):
            raise AssertionError("preflight must be skipped when the flag is off")

        monkeypatch.setattr(llm_service, "validate_model_available", _boom)
        worker_tasks._preflight_landing_models()  # must not raise

    def test_flag_on_checks_both_landing_tiers(self, monkeypatch):
        from worker import tasks as worker_tasks
        from nicheiq.utils import llm_service

        monkeypatch.setattr(worker_tasks.settings, "landing_preflight_model_check", True)
        monkeypatch.setattr(worker_tasks.settings, "landing_page_llm", "gpt-5.6-terra")
        monkeypatch.setattr(
            worker_tasks.settings, "landing_page_execution_llm", "gpt-5.3-codex"
        )
        checked = []
        monkeypatch.setattr(
            llm_service,
            "validate_model_available",
            lambda model_id: checked.append(model_id) or True,
        )
        worker_tasks._preflight_landing_models()
        assert checked == ["gpt-5.6-terra", "gpt-5.3-codex"]

    def test_flag_on_propagates_retired_model_error(self, monkeypatch):
        from worker import tasks as worker_tasks

        monkeypatch.setattr(worker_tasks.settings, "landing_preflight_model_check", True)
        _patch_client(monkeypatch, exc=_FakeAPIError(status_code=404))
        with pytest.raises(ValueError, match="not available"):
            worker_tasks._preflight_landing_models()
