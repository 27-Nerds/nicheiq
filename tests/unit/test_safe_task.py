"""Tests for SafeTask — proves CrewAI structured-output conversion is non-fatal.

Reproduces the prod crash class (uncaught pydantic ValidationError from
Task._export_output on malformed LLM JSON) and asserts SafeTask degrades it to
the guardrail retry/degrade path instead. Covers the documented matrix:
malformed first/after-retry, successful retry -> pydantic, sync + async loops,
single + multiple guardrails, guardrail returning str vs TaskOutput, and a
version-coupling guard against CrewAI upgrades.
"""

import asyncio

import pytest
from crewai.task import Task
from crewai.tasks.output_format import OutputFormat
from crewai.tasks.task_output import TaskOutput
from pydantic import BaseModel, ValidationError

from nicheiq.crews.safe_task import SafeTask


class Demo(BaseModel):
    value: int


VALID = '{"value": 5}'
SCHEMA_INVALID = '{"value": "not-an-int"}'  # parses as JSON, fails Demo validation


def _make_task(cls, **kw):
    base = dict(description="d", expected_output="e", output_pydantic=Demo)
    base.update(kw)
    return cls(**base)


def _task_output(raw):
    return TaskOutput(
        description="d",
        expected_output="e",
        raw=raw,
        agent="tester",
        output_format=OutputFormat.RAW,
    )


class _StubAgent:
    """Minimal agent that returns a fixed (or scripted) string for each call."""

    role = "tester"
    last_messages: list = []

    def __init__(self, outputs):
        # outputs: str (constant) or list[str] (per-attempt)
        self._outputs = outputs
        self._i = 0

    def _next(self):
        if isinstance(self._outputs, str):
            return self._outputs
        out = self._outputs[min(self._i, len(self._outputs) - 1)]
        self._i += 1
        return out

    def execute_task(self, task, context=None, tools=None):
        return self._next()

    async def aexecute_task(self, task, context=None, tools=None):
        return self._next()


# ── Direct _export_output behavior (the core fix) ──────────────────────────


def test_export_output_valid_json_returns_model():
    task = _make_task(SafeTask)
    pydantic_out, json_out = task._export_output(VALID)
    assert isinstance(pydantic_out, Demo)
    assert pydantic_out.value == 5


def test_export_output_schema_invalid_degrades_to_none():
    """THE fix: malformed/invalid JSON must NOT raise; returns (None, None)."""
    task = _make_task(SafeTask)
    assert task._export_output(SCHEMA_INVALID) == (None, None)


def test_export_output_truncated_json_degrades_to_none():
    task = _make_task(SafeTask)
    assert task._export_output('{"value": ') == (None, None)


def test_plain_task_raises_on_invalid_json():
    """Confirms the underlying bug exists, so SafeTask's divergence is meaningful."""
    task = _make_task(Task)
    with pytest.raises(ValidationError):
        task._export_output(SCHEMA_INVALID)


def test_export_output_without_output_pydantic_is_noop():
    task = SafeTask(description="d", expected_output="e")
    assert task._export_output(SCHEMA_INVALID) == (None, None)


# ── Version-coupling guard (fail loudly on CrewAI upgrades) ─────────────────


def test_export_output_method_still_exists_on_base_task():
    assert hasattr(Task, "_export_output"), (
        "CrewAI removed/renamed Task._export_output; SafeTask override is dead. "
        "Re-verify the guardrail conversion path for the new version."
    )


def test_safetask_overrides_export_output():
    assert SafeTask._export_output is not Task._export_output


def test_safetask_is_task_subclass_and_copy_preserves_type():
    task = _make_task(SafeTask)
    assert isinstance(task, Task)
    # Task.copy() reconstructs via self.__class__ (task.py:822-863)
    copied = task.copy(agents=[], task_mapping={})
    assert isinstance(copied, SafeTask)


# ── Sync guardrail loop: crash -> graceful degrade ─────────────────────────


def _run_guardrail(task, agent, guardrail):
    return task._invoke_guardrail_function(
        task_output=_task_output(SCHEMA_INVALID),
        agent=agent,
        tools=[],
        guardrail=guardrail,
    )


def test_sync_loop_safetask_degrades_to_guardrail_exhaustion():
    def always_fail(to):
        return (False, "nope")

    task = _make_task(SafeTask, guardrail=always_fail, guardrail_max_retries=1)
    agent = _StubAgent(SCHEMA_INVALID)  # regenerated output stays invalid
    with pytest.raises(Exception, match="guardrail validation"):
        _run_guardrail(task, agent, always_fail)


def test_sync_loop_plain_task_crashes_with_validationerror():
    def always_fail(to):
        return (False, "nope")

    task = _make_task(Task, guardrail=always_fail, guardrail_max_retries=1)
    agent = _StubAgent(SCHEMA_INVALID)
    with pytest.raises(ValidationError):
        _run_guardrail(task, agent, always_fail)


def test_sync_loop_successful_retry_populates_pydantic():
    calls = {"n": 0}

    def pass_on_retry(to):
        calls["n"] += 1
        return (True, to.raw) if calls["n"] >= 2 else (False, "retry")

    task = _make_task(SafeTask, guardrail=pass_on_retry, guardrail_max_retries=2)
    agent = _StubAgent(VALID)  # regeneration yields valid JSON
    out = _run_guardrail(task, agent, pass_on_retry)
    assert isinstance(out.pydantic, Demo)
    assert out.pydantic.value == 5


def test_sync_loop_guardrail_returning_taskoutput_is_passed_through():
    replacement = _task_output(VALID)

    def replace(to):
        return (True, replacement)

    task = _make_task(SafeTask, guardrail=replace, guardrail_max_retries=1)
    out = _run_guardrail(task, _StubAgent(VALID), replace)
    assert out is replacement


# ── Async guardrail loop: same _export_output, so same protection ──────────


def test_async_loop_safetask_degrades_to_guardrail_exhaustion():
    def always_fail(to):
        return (False, "nope")

    task = _make_task(SafeTask, guardrail=always_fail, guardrail_max_retries=1)
    agent = _StubAgent(SCHEMA_INVALID)

    async def run():
        return await task._ainvoke_guardrail_function(
            task_output=_task_output(SCHEMA_INVALID),
            agent=agent,
            tools=[],
            guardrail=always_fail,
        )

    with pytest.raises(Exception, match="guardrail validation"):
        asyncio.run(run())


# ── Multiple guardrails construct & still degrade ──────────────────────────


def test_multiple_guardrails_construction_and_export_still_safe():
    def g1(to):
        return (True, to.raw)

    def g2(to):
        return (True, to.raw)

    task = _make_task(SafeTask, guardrails=[g1, g2])
    # the override is guardrail-agnostic; conversion still degrades safely
    assert task._export_output(SCHEMA_INVALID) == (None, None)
