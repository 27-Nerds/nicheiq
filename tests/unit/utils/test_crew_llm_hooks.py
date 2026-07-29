"""Tests for the Gemini trailing-assistant-turn hook."""

from types import SimpleNamespace

import pytest

from nicheiq.utils.crew_llm_hooks import (
    ensure_user_turn_last,
    is_google_model,
)


def _ctx(messages, model):
    """Stand-in for LLMCallHookContext — the hook only reads .messages and .llm."""
    return SimpleNamespace(messages=messages, llm=SimpleNamespace(model=model))


GEMINI = "google/gemini-3.5-flash-lite"


@pytest.mark.parametrize("model", [
    "google/gemini-3.5-flash-lite",   # OpenRouter id (openrouter/ prefix already stripped)
    "google/gemini-3.1-flash-lite",
    "gemini/gemini-2.5-flash",        # CrewAI native provider id
    "vertex_ai/gemini-2.5-pro",
])
def test_detects_google_models(model):
    assert is_google_model(model)


@pytest.mark.parametrize("model", [
    "openai/gpt-5.2",
    "x-ai/grok-4.3",
    "deepseek/deepseek-v4-flash",
    "inception/mercury-2-20260304",
    "",
])
def test_ignores_non_google_models(model):
    assert not is_google_model(model)


def test_appends_user_turn_when_google_request_ends_on_assistant():
    """The ReAct shape: CrewAI appends the tool Observation as an assistant turn, then
    re-invokes. Gemini 400s on that, so the hook must close it with a user turn."""
    messages = [
        {"role": "system", "content": "You are a researcher."},
        {"role": "user", "content": "Find data sources."},
        {"role": "assistant", "content": "Thought: ...\nObservation: <tool result>"},
    ]
    ensure_user_turn_last(_ctx(messages, GEMINI))

    assert len(messages) == 4
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"]


def test_noop_when_request_already_ends_on_user():
    messages = [
        {"role": "system", "content": "You are a researcher."},
        {"role": "user", "content": "Find data sources."},
    ]
    ensure_user_turn_last(_ctx(messages, GEMINI))

    assert len(messages) == 2


def test_noop_for_non_google_model():
    """Every other provider accepts a trailing assistant turn — their lists must go
    through byte-identical."""
    messages = [
        {"role": "user", "content": "Find data sources."},
        {"role": "assistant", "content": "Observation: <tool result>"},
    ]
    before = [dict(m) for m in messages]
    ensure_user_turn_last(_ctx(messages, "openai/gpt-5.2"))

    assert messages == before


def test_noop_on_empty_messages():
    messages = []
    ensure_user_turn_last(_ctx(messages, GEMINI))

    assert messages == []


def test_second_invocation_does_not_double_append():
    """Both hook paths can fire for one call if from_agent is None; the second pass sees a
    user turn last and must do nothing."""
    messages = [{"role": "assistant", "content": "Observation: <tool result>"}]
    ensure_user_turn_last(_ctx(messages, GEMINI))
    ensure_user_turn_last(_ctx(messages, GEMINI))

    assert len(messages) == 2


def test_mutates_in_place():
    """CrewAI requires in-place mutation — replacing the list breaks the executor."""
    messages = [{"role": "assistant", "content": "Observation: <tool result>"}]
    same_list = messages
    ensure_user_turn_last(_ctx(messages, GEMINI))

    assert messages is same_list
