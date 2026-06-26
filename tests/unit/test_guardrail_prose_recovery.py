"""
Tests for guardrail robustness to reasoning-model "Thought:" preambles.

DeepSeek-class models sometimes emit chain-of-thought as plain text BEFORE the
JSON (content = "Thought: ...{...}", reasoning_content empty), which broke the
guardrail json.loads at char 0. The parser now recovers the embedded JSON, and
the success payload normalizes prose-wrapped output to clean JSON so downstream
.pydantic materialization works.
"""

import json

from pydantic import BaseModel

from nicheiq.utils.validation.crew_guardrails import (
    _guardrail_success_payload,
    _parse_pydantic_from_task_output,
)


class _Tiny(BaseModel):
    concepts: list[str]
    removed: int


class _FakeTaskOutput:
    """Mimics a CrewAI TaskOutput where guardrails leave .pydantic = None."""

    def __init__(self, raw):
        self.raw = raw
        self.pydantic = None


PROSE_WRAPPED = (
    "Thought: I need to apply the filtering workflow to the pooled concepts.\n"
    "Let me identify the pain registry, then apply coverage lock and diversity.\n\n"
    "**Final Decision:** Keep 2, remove 1.\n"
    '{"concepts": ["ProtocolSkipAlert", "SolventResidueScanner"], "removed": 1}'
)


def test_parser_recovers_json_after_thought_preamble():
    result, err = _parse_pydantic_from_task_output(
        _FakeTaskOutput(PROSE_WRAPPED), _Tiny, "Diversity filtering"
    )
    assert err is None, err
    assert result is not None
    assert result.concepts == ["ProtocolSkipAlert", "SolventResidueScanner"]
    assert result.removed == 1


def test_parser_still_handles_clean_json():
    clean = '{"concepts": ["A"], "removed": 0}'
    result, err = _parse_pydantic_from_task_output(_FakeTaskOutput(clean), _Tiny, "x")
    assert err is None and result.concepts == ["A"]


def test_parser_reports_error_when_no_json_present():
    result, err = _parse_pydantic_from_task_output(
        _FakeTaskOutput("Thought: I cannot do this. No JSON here."), _Tiny, "x"
    )
    assert result is None and err is not None


def test_success_payload_normalizes_prose_to_clean_json():
    parsed = _Tiny(concepts=["A", "B"], removed=1)
    payload = _guardrail_success_payload(_FakeTaskOutput(PROSE_WRAPPED), parsed)
    # Must be clean JSON parseable from char 0 (no "Thought:" prefix).
    obj = json.loads(payload)
    assert obj["concepts"] == ["A", "B"] and obj["removed"] == 1


def test_success_payload_passes_clean_raw_through_unchanged():
    clean = '{"concepts": ["A"], "removed": 0}'
    parsed = _Tiny(concepts=["A"], removed=0)
    payload = _guardrail_success_payload(_FakeTaskOutput(clean), parsed)
    assert payload == clean  # no-op for well-behaved models
