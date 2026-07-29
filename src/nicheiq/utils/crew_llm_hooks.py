"""Google/Gemini message-shape hook for CrewAI agent loops.

Gemini rejects any request whose LAST message is an assistant ("model") turn:

    400 INVALID_ARGUMENT — "Requests ending with a model turn are not supported."

CrewAI's ReAct executor produces exactly that shape. `CrewAgentExecutor._append_message()`
defaults to ``role="assistant"``, so the agent's own Thought/Action AND the tool
Observation are appended as an assistant turn, then the loop re-invokes the LLM with that
list (crew_agent_executor.py `_invoke_loop`). The forced-final-answer nudge in
`handle_max_iterations_exceeded` (agent_utils.py) does the same and calls `llm.call()`
directly. Both are fine on OpenAI/Anthropic and 400 on every Google endpoint — live-hit by
the two tool-using agents (`data_source_researcher`, `competitive_researcher`), which run
on `openai_model_name`.

There is no upstream fix (checked crewai 1.8.1 and main on 2026-07-28; PR #3407 patched a
different path — the system-only chat opening — and was closed unmerged), so we close it
with CrewAI's supported `before_llm_call` hook, documented to mutate ``context.messages``
in place. The hook fires on BOTH failing paths: the executor path via
`agent_utils.invoke_before_llm_call_hooks`, and the direct `llm.call()` path via
`BaseLLM._invoke_before_llm_call_hooks` (which runs when ``from_agent`` is None and mutates
the list actually sent).

Only Google-family models are touched; every other provider accepts a trailing assistant
turn and its message list passes through untouched.
"""

from typing import Any

from loguru import logger

# Minimal continuation turn. Carries no instruction of its own so it can't fight either
# the ReAct format prompt or the force-final-answer nudge it may follow.
_CONTINUE_TURN = "Continue."

_registered = False


def _model_id(llm: Any) -> str:
    """Model id off a hook context's ``llm``, which is typed ``BaseLLM | str | Any | None``."""
    if isinstance(llm, str):
        return llm
    return getattr(llm, "model", "") or ""


def is_google_model(model: str) -> bool:
    """True for Google-family ids in any of the forms this project produces: OpenRouter
    ids are vendor-prefixed (``google/gemini-3.5-flash-lite`` — the ``openrouter/`` prefix
    is stripped by `resolve_endpoint` before the id reaches the LLM), CrewAI's native
    provider uses ``gemini/…``."""
    m = model.lower()
    return m.startswith(("google/", "gemini/", "vertex_ai/")) or "gemini" in m


def ensure_user_turn_last(context: Any) -> None:
    """Append a minimal user turn when a Google model is about to receive a request
    ending on an assistant turn. No-op for every other provider, and for lists that
    already end on a user/tool turn."""
    messages = context.messages
    if not messages or messages[-1].get("role") != "assistant":
        return
    if not is_google_model(_model_id(context.llm)):
        return
    messages.append({"role": "user", "content": _CONTINUE_TURN})


def register_google_turn_hook() -> None:
    """Register the hook globally, once. CrewAI copies the global hook list into each
    executor at construction time, so this must run before any crew kicks off —
    `build_crew_llm` calls it, which every crew agent goes through."""
    global _registered
    if _registered:
        return
    from crewai.hooks import register_before_llm_call_hook

    register_before_llm_call_hook(ensure_user_turn_last)
    _registered = True
    logger.debug(
        "[llm] registered Gemini trailing-assistant-turn hook "
        "(Google models reject requests ending on a model turn)"
    )
