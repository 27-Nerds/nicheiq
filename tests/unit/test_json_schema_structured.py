"""Tests for the json_schema (guided-decoding) structured-output path.

Covers the schema shaper (_shape_json_schema) that rewrites Pydantic json-schema
into an xgrammar-compilable shape, and the response_format json_schema branch in
_invoke_structured_openrouter (no tool calls; the JSON lands in content).
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from nicheiq.utils import llm_service
from nicheiq.utils.llm_service import LLMService, _shape_json_schema


# --- _shape_json_schema -----------------------------------------------------

class _Inner(BaseModel):
    label: str = Field(..., min_length=2, max_length=40)
    score: int = Field(..., ge=0, le=100)


class _Outer(BaseModel):
    name: str = Field(..., pattern=r"^[a-z]+$")
    inner: _Inner                       # -> $ref/$defs
    items: list[_Inner] = Field(..., min_length=1)
    note: str | None = None             # -> anyOf [str, null]


class TestShapeJsonSchema:
    def _walk_keys(self, node, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                acc.add(k)
                self._walk_keys(v, acc)
        elif isinstance(node, list):
            for n in node:
                self._walk_keys(n, acc)

    def test_inlines_refs_and_drops_defs(self):
        shaped = _shape_json_schema(_Outer.model_json_schema())
        keys = set()
        self._walk_keys(shaped, keys)
        assert "$ref" not in keys
        assert "$defs" not in keys
        assert "definitions" not in keys
        # the inner object's properties survived the inline
        assert shaped["properties"]["inner"]["properties"].keys() >= {"label", "score"}

    def test_strips_unsupported_validation_keywords(self):
        shaped = _shape_json_schema(_Outer.model_json_schema())
        keys = set()
        self._walk_keys(shaped, keys)
        for forbidden in ("minimum", "maximum", "minLength", "maxLength", "pattern", "minItems"):
            assert forbidden not in keys, f"{forbidden} should be stripped"
        # ...but exclusiveMinimum/exclusiveMaximum (ge/le -> minimum/maximum) also gone
        assert "exclusiveMinimum" not in keys and "exclusiveMaximum" not in keys

    def test_oneof_rewritten_to_anyof(self):
        schema = {
            "type": "object",
            "properties": {
                "choice": {"oneOf": [{"type": "string"}, {"type": "integer"}]}
            },
        }
        shaped = _shape_json_schema(schema)
        choice = shaped["properties"]["choice"]
        assert "oneOf" not in choice
        assert choice["anyOf"] == [{"type": "string"}, {"type": "integer"}]

    def test_recursion_guard_terminates(self):
        # self-referential $ref must not infinite-loop
        schema = {
            "$defs": {"Node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Node"}}}},
            "$ref": "#/$defs/Node",
        }
        shaped = _shape_json_schema(schema)  # returns, doesn't hang
        assert shaped["type"] == "object"

    def test_output_is_json_serializable(self):
        import json
        assert json.loads(json.dumps(_shape_json_schema(_Outer.model_json_schema())))


# --- json_schema request branch ---------------------------------------------

class _M(BaseModel):
    name: str = Field(..., description="n")
    value: int = Field(..., description="v")


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
    msg = SimpleNamespace(tool_calls=None, content=content, reasoning=None, reasoning_details=None)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, cost=None)
    return SimpleNamespace(choices=[choice], usage=usage)


_VALID = '{"name": "x", "value": 1}'
_BAD = "no json here"


def _run(responses, mode, monkeypatch, *, providers="", reasoning_effort=None, max_tokens=None,
         creative=False, clean_model="qwen/qwen3-235b-a22b-2507"):
    monkeypatch.setattr(llm_service.settings, "openrouter_structured_mode", mode)
    monkeypatch.setattr(llm_service.settings, "openrouter_structured_providers", providers)
    fake = _FakeClient(responses)
    with patch("openai.OpenAI", return_value=fake):
        result = LLMService._invoke_structured_openrouter(
            prompt="p", output_model=_M, temperature=0.5, timeout=10,
            clean_model=clean_model, api_key="k", base_url=None,
            reasoning_effort=reasoning_effort, max_tokens=max_tokens, creative=creative,
        )
    return result, fake.chat.completions.calls


class TestJsonSchemaBranch:
    def test_sends_response_format_not_tools(self, monkeypatch):
        (parsed, _u), calls = _run([_resp("stop", _VALID)], "json_schema", monkeypatch)
        assert parsed == _M(name="x", value=1)
        rf = calls[0]["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["name"] == "_M"
        assert "tools" not in calls[0]
        assert "tool_choice" not in calls[0]

    def test_schema_is_shaped(self, monkeypatch):
        _r, calls = _run([_resp("stop", _VALID)], "json_schema", monkeypatch)
        schema = calls[0]["response_format"]["json_schema"]["schema"]
        import json
        assert "$ref" not in json.dumps(schema)  # shaped/inlined

    def test_keeps_provider_routing_and_max_tokens(self, monkeypatch):
        # No allowlist -> require_parameters routes among capable providers.
        _r, calls = _run([_resp("stop", _VALID)], "json_schema", monkeypatch)
        assert calls[0]["extra_body"]["provider"]["require_parameters"] is True
        assert calls[0]["max_tokens"] == llm_service.MAX_TOKENS_LARGE

    def test_allowlist_pins_only_without_require_parameters(self, monkeypatch):
        # With a provider allowlist (the qwen@deepinfra case), pin via `only` and DROP
        # require_parameters — it filters on `reasoning` (which deepinfra/qwen lacks) and
        # would 404 the pinned route.
        _r, calls = _run([_resp("stop", _VALID)], "json_schema", monkeypatch, providers="deepinfra")
        prov = calls[0]["extra_body"]["provider"]
        assert prov["only"] == ["deepinfra"]
        assert "require_parameters" not in prov

    def test_json_schema_forces_reasoning_off(self, monkeypatch):
        # An effort passed by the tier (e.g. thread_validation's 'minimal') must NOT enable
        # reasoning on the guided-decoding path (it returns empty output on qwen@deepinfra).
        _r, calls = _run(
            [_resp("stop", _VALID)], "json_schema", monkeypatch, reasoning_effort="minimal"
        )
        assert calls[0]["extra_body"]["reasoning"] == {"enabled": False}

    def test_default_mode_still_uses_tools(self, monkeypatch):
        _r, calls = _run([_resp("stop", _VALID)], "tool_choice", monkeypatch)
        assert "tools" in calls[0]
        assert "response_format" not in calls[0]

    def test_no_relax_to_auto_on_json_schema(self, monkeypatch):
        # json_schema has no tool_choice to relax -> a clean-finish None fails fast (1 call).
        monkeypatch.setattr(llm_service.settings, "openrouter_structured_mode", "json_schema")
        fake = _FakeClient([_resp("stop", _BAD)])
        with patch("openai.OpenAI", return_value=fake):
            with pytest.raises(ValueError):
                LLMService._invoke_structured_openrouter(
                    prompt="p", output_model=_M, temperature=0.5, timeout=10,
                    clean_model="qwen/x", api_key="k", base_url=None,
                    reasoning_effort=None, max_tokens=None,
                )
        assert len(fake.chat.completions.calls) == 1

    def test_still_retries_once_on_length(self, monkeypatch):
        (parsed, _u), calls = _run(
            [_resp("length", _BAD), _resp("stop", _VALID)], "json_schema", monkeypatch
        )
        assert parsed == _M(name="x", value=1)
        assert len(calls) == 2

    def test_creative_opts_out_of_json_schema_and_pin(self, monkeypatch):
        # Creative (divergent/brainstorm) calls keep tool_choice transport, honor reasoning, and
        # skip the provider pin — even with json_schema mode + a deepinfra allowlist set globally.
        (parsed, _u), calls = _run(
            [_resp("stop", _VALID)], "json_schema", monkeypatch,
            providers="deepinfra", reasoning_effort="low", creative=True,
            clean_model="minimax/minimax-m3",
        )
        assert parsed == _M(name="x", value=1)
        assert "tools" in calls[0] and "response_format" not in calls[0]   # tool path, not json_schema
        assert "only" not in calls[0]["extra_body"]["provider"]            # pin skipped -> no 404
        assert calls[0]["extra_body"]["reasoning"] == {"effort": "low"}    # reasoning honored
