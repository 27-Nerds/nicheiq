"""
Unit tests for LLMService - centralized LLM invocation service.

Tests both invoke_structured() and invoke_plain() methods with mocking
to avoid real LLM API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import BaseModel, Field

from nicheiq.models.seo_strategy import (
    ConceptualKeyword,
    ConceptualTopicCluster,
    ExpandedKeywordList,
)
from nicheiq.utils import llm_service
from nicheiq.utils.llm_service import LLMService, TokenUsage


# Test Models
class TestModel(BaseModel):
    """Simple Pydantic model for testing structured output."""
    name: str = Field(..., description="Test name")
    value: int = Field(..., description="Test value")


def _make_raw_response(response_metadata: dict | None = None) -> Mock:
    """Create mock raw response with response_metadata."""
    mock = Mock()
    mock.response_metadata = response_metadata or {
        'token_usage': {'prompt_tokens': 100, 'completion_tokens': 50}
    }
    return mock


def _make_structured_response(parsed_result, response_metadata: dict | None = None) -> dict:
    """Create mock response for with_structured_output(include_raw=True)."""
    return {
        'parsed': parsed_result,
        'raw': _make_raw_response(response_metadata)
    }


def _expanded_keyword_result() -> ExpandedKeywordList:
    return ExpandedKeywordList(
        keywords=[ConceptualKeyword(keyword="inventory", cluster="Core", priority=1)],
        topic_clusters=[
            ConceptualTopicCluster(
                name="Core", description="Core inventory terms", strategic_importance=1
            )
        ],
        expansion_rationale="Cover the primary workflow.",
    )


class TestInvokeStructured:
    """Test LLMService.invoke_structured() method (the ChatOpenAI / OpenAI path)."""

    @pytest.fixture(autouse=True)
    def _default_openai_model(self, monkeypatch):
        # These tests assert the ChatOpenAI-path contract. Pin a non-OpenRouter
        # default model so the ambient .env (which may set an openrouter/* default)
        # doesn't reroute them through the separate OpenRouter SDK path. Tests that
        # @patch settings themselves override this for their own body.
        monkeypatch.setattr(llm_service.settings, "openai_model_name", "gpt-4o", raising=False)

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_successful_invocation(self, mock_logger, mock_chat_openai):
        """Verify successful structured output with Pydantic model."""
        # Setup mock - now returns dict with 'parsed' and 'raw' due to include_raw=True
        expected_result = TestModel(name="test", value=42)
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(expected_result)
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test - now returns tuple (result, usage)
        result, usage = LLMService.invoke_structured(
            prompt="Test prompt",
            output_model=TestModel
        )

        # Assert
        assert isinstance(result, TestModel)
        assert result.name == "test"
        assert result.value == 42
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        mock_logger.debug.assert_called_once()
        assert "TestModel" in str(mock_logger.debug.call_args)

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_default_temperature_is_0_6(self, mock_chat_openai):
        """Verify default temperature=0.6 for structured calls."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test
        LLMService.invoke_structured("Test", TestModel)

        # Assert - check ChatOpenAI was called with temp=0.6
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['temperature'] == 0.6

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_default_timeout_is_120(self, mock_chat_openai):
        """Verify default timeout=120 seconds."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test
        LLMService.invoke_structured("Test", TestModel)

        # Assert - check ChatOpenAI was called with timeout=120
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['timeout'] == 120

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_custom_temperature_override(self, mock_chat_openai):
        """Test custom temperature parameter."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test with custom temperature
        LLMService.invoke_structured("Test", TestModel, temperature=0.9)

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['temperature'] == 0.9

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_custom_timeout_override(self, mock_chat_openai):
        """Test custom timeout parameter."""
        # Setup mock
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test with custom timeout
        LLMService.invoke_structured("Test", TestModel, timeout=300)

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['timeout'] == 300

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.settings')
    def test_custom_model_override(self, mock_settings, mock_chat_openai):
        """Test custom model_name parameter."""
        # Setup
        mock_settings.openai_model_name = "gpt-4o"
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test with custom model
        LLMService.invoke_structured("Test", TestModel, model_name="gpt-4o-mini")

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['model'] == "gpt-4o-mini"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_reasoning_effort_forwarded_for_gpt5(self, mock_chat_openai):
        """reasoning_effort is forwarded (and temperature omitted) for GPT-5 models."""
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        LLMService.invoke_structured(
            "Test", TestModel, temperature=0, model_name="gpt-5-nano",
            reasoning_effort="minimal",
        )

        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['reasoning_effort'] == "minimal"
        assert 'temperature' not in call_kwargs  # reasoning models reject temperature

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_reasoning_effort_ignored_for_non_reasoning(self, mock_chat_openai):
        """reasoning_effort is dropped for non-reasoning models; temperature kept."""
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        LLMService.invoke_structured(
            "Test", TestModel, temperature=0, model_name="gpt-4.1-mini",
            reasoning_effort="minimal",
        )

        call_kwargs = mock_chat_openai.call_args[1]
        assert 'reasoning_effort' not in call_kwargs
        assert call_kwargs['temperature'] == 0

    @pytest.mark.parametrize("reasoning_effort", [None, "", "none"])
    def test_keyword_schema_forces_none_on_chat_completions(self, reasoning_effort):
        """Unset/none effort must not inherit GPT-5.6 reasoning with function tools."""
        structured = Mock()
        structured.invoke.return_value = _make_structured_response(_expanded_keyword_result())

        with patch('nicheiq.utils.llm_service.ChatOpenAI') as mock_chat_openai:
            mock_chat_openai.return_value.with_structured_output.return_value = structured
            LLMService.invoke_structured(
                "Test",
                ExpandedKeywordList,
                model_name="gpt-5.6-luna",
                reasoning_effort=reasoning_effort,
            )

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs['reasoning_effort'] == "none"
        assert 'use_responses_api' not in call_kwargs
        mock_chat_openai.return_value.with_structured_output.assert_called_once_with(
            ExpandedKeywordList, method="function_calling", include_raw=True
        )

    @pytest.mark.parametrize("reasoning_effort", ["minimal", "high"])
    def test_keyword_schema_uses_responses_for_requested_reasoning(self, reasoning_effort):
        """Function tools retain a real requested effort by switching transports."""
        structured = Mock()
        structured.invoke.return_value = _make_structured_response(_expanded_keyword_result())

        with patch('nicheiq.utils.llm_service.ChatOpenAI') as mock_chat_openai:
            mock_chat_openai.return_value.with_structured_output.return_value = structured
            LLMService.invoke_structured(
                "Test",
                ExpandedKeywordList,
                model_name="gpt-5.6-luna",
                reasoning_effort=reasoning_effort,
            )

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs['reasoning_effort'] == reasoning_effort
        assert call_kwargs['use_responses_api'] is True

    def test_keyword_responses_usage_metadata_reaches_cost_tracking(self):
        """Responses API token counts live on usage_metadata, not token_usage."""
        raw_response = Mock()
        raw_response.response_metadata = {}
        raw_response.usage_metadata = {"input_tokens": 123, "output_tokens": 45}
        structured = Mock()
        structured.invoke.return_value = {
            "parsed": _expanded_keyword_result(),
            "raw": raw_response,
        }

        with patch('nicheiq.utils.llm_service.ChatOpenAI') as mock_chat_openai:
            mock_chat_openai.return_value.with_structured_output.return_value = structured
            _, usage = LLMService.invoke_structured(
                "Test",
                ExpandedKeywordList,
                model_name="gpt-5.6-luna",
                reasoning_effort="minimal",
            )

        assert usage.prompt_tokens == 123
        assert usage.completion_tokens == 45

    @pytest.mark.parametrize(
        ("reasoning_effort", "uses_responses"),
        [(None, False), ("", False), ("none", False), ("minimal", True)],
    )
    def test_json_schema_fallback_applies_function_tool_transport_invariant(
        self, reasoning_effort, uses_responses
    ):
        """A runtime json_schema rejection must apply the same function-tool rule."""
        primary_structured = Mock()
        primary_structured.invoke.side_effect = ValueError(
            "Invalid schema for response_format: additionalProperties"
        )
        primary = Mock()
        primary.with_structured_output.return_value = primary_structured

        fallback_structured = Mock()
        fallback_structured.invoke.return_value = _make_structured_response(
            TestModel(name="test", value=1)
        )
        fallback = Mock()
        fallback.with_structured_output.return_value = fallback_structured

        with patch(
            'nicheiq.utils.llm_service.ChatOpenAI', side_effect=[primary, fallback]
        ) as mock_chat_openai:
            LLMService.invoke_structured(
                "Test",
                TestModel,
                model_name="gpt-5.6-luna",
                reasoning_effort=reasoning_effort,
            )

        fallback_kwargs = mock_chat_openai.call_args_list[1].kwargs
        if uses_responses:
            assert fallback_kwargs['reasoning_effort'] == reasoning_effort
            assert fallback_kwargs['use_responses_api'] is True
        else:
            assert fallback_kwargs['reasoning_effort'] == "none"
            assert 'use_responses_api' not in fallback_kwargs
        primary.with_structured_output.assert_called_once_with(
            TestModel, method="json_schema", include_raw=True
        )
        fallback.with_structured_output.assert_called_once_with(
            TestModel, method="function_calling", include_raw=True
        )

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.settings')
    def test_uses_settings_model_by_default(self, mock_settings, mock_chat_openai):
        """Verify settings.openai_model_name is used when model_name=None."""
        # Setup
        mock_settings.openai_model_name = "gpt-4o"
        mock_settings.openai_api_key = "test-key"
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test without model_name parameter
        LLMService.invoke_structured("Test", TestModel)

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['model'] == "gpt-4o"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.settings')
    def test_uses_settings_api_key(self, mock_settings, mock_chat_openai):
        """Verify settings.openai_api_key is used."""
        # Setup
        mock_settings.openai_model_name = "gpt-4o"
        mock_settings.openai_api_key = "sk-test-key-12345"
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test
        LLMService.invoke_structured("Test", TestModel)

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['api_key'] == "sk-test-key-12345"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_logs_success_with_model_name(self, mock_logger, mock_chat_openai):
        """Verify logger.debug called with model name."""
        # Setup
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(TestModel(name="test", value=1))
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test
        LLMService.invoke_structured("Test", TestModel)

        # Assert
        mock_logger.debug.assert_called_once()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "TestModel" in debug_message
        assert "successful" in debug_message

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_logs_error_and_raises_on_failure(self, mock_logger, mock_chat_openai):
        """Verify logger.error called and exception raised on failure."""
        # Setup mock to raise exception
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API error")
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test and assert exception is raised
        with pytest.raises(Exception, match="API error"):
            LLMService.invoke_structured("Test", TestModel)

        # Assert error was logged
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "TestModel" in error_message
        assert "failed" in error_message

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_returns_token_usage(self, mock_chat_openai):
        """Verify TokenUsage is returned with token counts."""
        # Setup mock with specific token counts
        mock_llm = Mock()
        mock_llm.invoke.return_value = _make_structured_response(
            TestModel(name="test", value=1),
            {'token_usage': {'prompt_tokens': 250, 'completion_tokens': 75}}
        )
        mock_chat_openai.return_value.with_structured_output.return_value = mock_llm

        # Test
        result, usage = LLMService.invoke_structured("Test", TestModel)

        # Assert
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 250
        assert usage.completion_tokens == 75
        usage_dict = usage.to_dict()
        assert usage_dict['prompt_tokens'] == 250
        assert usage_dict['completion_tokens'] == 75


class TestLostStructuredOutputDiagnostic:
    """The 'structured output lost' error must describe what was ACTUALLY sent instead of
    recommending a setting the call already applied. Live 2026-08-03: this path told the
    operator to set `*_REASONING_EFFORT=none` for gpt-5.6-luna while
    IDEATION_REFINE_REASONING_EFFORT=none was already in .env — and the OpenRouter
    'reasoning channel' cause it named cannot occur here (OpenRouter returns earlier)."""

    class _OptModel(BaseModel):
        name: str
        note: str | None = None   # anyOf => function_calling transport, as BaseSolutionIdea

    @pytest.fixture(autouse=True)
    def _pin_model(self, monkeypatch):
        monkeypatch.setattr(llm_service.settings, "openai_model_name", "gpt-4o", raising=False)

    def _fail(self, *, finish_reason="tool_calls", parsing_error=None,
              tool_calls=(), invalid_tool_calls=()) -> str:
        raw = Mock()
        raw.response_metadata = {"finish_reason": finish_reason}
        raw.content = ""
        raw.tool_calls = list(tool_calls)
        raw.invalid_tool_calls = list(invalid_tool_calls)
        structured = Mock()
        structured.invoke.return_value = {
            "parsed": None, "raw": raw, "parsing_error": parsing_error,
        }
        llm = Mock()
        llm.with_structured_output.return_value = structured
        with patch('nicheiq.utils.llm_service.ChatOpenAI', return_value=llm):
            with pytest.raises(ValueError) as excinfo:
                LLMService.invoke_structured(
                    "Test", self._OptModel,
                    model_name="gpt-5.6-luna", reasoning_effort="none",
                )
        return str(excinfo.value)

    def test_parse_failure_reports_the_real_cause(self):
        msg = self._fail(parsing_error=ValueError("note: Input should be a valid string"))
        assert "could not be parsed" in msg
        assert "note: Input should be a valid string" in msg   # the failing field
        assert "reasoning settings are not the lever" in msg

    def test_empty_response_states_what_was_tried(self):
        msg = self._fail()
        assert "was empty" in msg
        assert "transport=function_calling" in msg
        assert "reasoning_effort='none'" in msg   # already applied — not a fix to suggest

    def test_never_recommends_an_already_applied_effort_setting(self):
        for msg in (self._fail(), self._fail(parsing_error=RuntimeError("bad args")),
                    self._fail(invalid_tool_calls=[{"name": "x", "args": "{"}])):
            assert "REASONING_EFFORT" not in msg
            assert "reasoning' channel" not in msg


class TestInvokePlain:
    """Test LLMService.invoke_plain() method."""

    @pytest.fixture(autouse=True)
    def _default_openai_model(self, monkeypatch):
        # Plain-call assertions must not depend on the ambient .env model, which may
        # be a reasoning model and therefore intentionally omit temperature.
        monkeypatch.setattr(llm_service.settings, "openai_model_name", "gpt-4o", raising=False)

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_successful_invocation(self, mock_logger, mock_chat_openai):
        """Verify successful plain text invocation."""
        # Setup mock with response_metadata for token usage
        mock_result = Mock()
        mock_result.content = "test response"
        mock_result.response_metadata = {
            'token_usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test - now returns tuple (content, usage)
        content, usage = LLMService.invoke_plain("Test prompt")

        # Assert
        assert content == "test response"
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        mock_logger.debug.assert_called_once()

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_returns_string_from_content(self, mock_chat_openai):
        """Verify result.content is extracted and returned as string."""
        # Setup mock
        mock_result = Mock()
        mock_result.content = "extracted content"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        content, usage = LLMService.invoke_plain("Test")

        # Assert
        assert isinstance(content, str)
        assert content == "extracted content"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_default_temperature_is_0_7(self, mock_chat_openai):
        """Verify default temperature=0.7 for plain calls."""
        # Setup mock
        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        LLMService.invoke_plain("Test")

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['temperature'] == 0.7

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_default_timeout_is_120(self, mock_chat_openai):
        """Verify default timeout=120 seconds."""
        # Setup mock
        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        LLMService.invoke_plain("Test")

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['timeout'] == 120

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_custom_parameters(self, mock_chat_openai):
        """Test custom temperature, timeout, model_name."""
        # Setup mock
        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test with custom parameters
        LLMService.invoke_plain(
            "Test",
            temperature=0.3,
            timeout=60,
            model_name="gpt-4"
        )

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['temperature'] == 0.3
        assert call_kwargs['timeout'] == 60
        assert call_kwargs['model'] == "gpt-4"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.settings')
    def test_uses_settings_by_default(self, mock_settings, mock_chat_openai):
        """Verify settings values used by default."""
        # Setup
        mock_settings.openai_model_name = "gpt-4o"
        mock_settings.openai_api_key = "test-key"
        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        LLMService.invoke_plain("Test")

        # Assert
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['model'] == "gpt-4o"
        assert call_kwargs['api_key'] == "test-key"

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_logs_success_with_model_name(self, mock_logger, mock_chat_openai):
        """Verify logger.debug called with model name."""
        # Setup
        mock_settings_patch = patch('nicheiq.utils.llm_service.settings')
        mock_settings = mock_settings_patch.start()
        mock_settings.openai_model_name = "gpt-4o"

        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        LLMService.invoke_plain("Test")

        # Assert
        mock_logger.debug.assert_called_once()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "successful" in debug_message
        assert "gpt-4o" in debug_message

        mock_settings_patch.stop()

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    @patch('nicheiq.utils.llm_service.logger')
    def test_handles_errors_gracefully(self, mock_logger, mock_chat_openai):
        """Verify error handling and logging."""
        # Setup mock to raise exception
        mock_chat_openai.return_value.invoke.side_effect = Exception("Connection error")

        # Test and assert exception is raised
        with pytest.raises(Exception, match="Connection error"):
            LLMService.invoke_plain("Test")

        # Assert error was logged
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "failed" in error_message

    @patch('nicheiq.utils.llm_service.ChatOpenAI')
    def test_returns_token_usage(self, mock_chat_openai):
        """Verify TokenUsage is returned with token counts."""
        # Setup mock with specific token counts
        mock_result = Mock()
        mock_result.content = "test"
        mock_result.response_metadata = {
            'token_usage': {'prompt_tokens': 300, 'completion_tokens': 100}
        }
        mock_chat_openai.return_value.invoke.return_value = mock_result

        # Test
        content, usage = LLMService.invoke_plain("Test")

        # Assert
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 300
        assert usage.completion_tokens == 100
        usage_dict = usage.to_dict()
        assert usage_dict['prompt_tokens'] == 300
        assert usage_dict['completion_tokens'] == 100
