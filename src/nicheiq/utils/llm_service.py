"""LLM invocation utilities for report generation."""

from typing import Type, TypeVar

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel

from ..config.settings import settings

T = TypeVar('T', bound=BaseModel)


def is_reasoning_model(model: str) -> bool:
    """
    Check if a model is a reasoning model that doesn't support sampling parameters.

    Reasoning models (GPT-5 series, o1/o3 series) don't support:
    - temperature, top_p, presence_penalty, frequency_penalty
    - max_tokens (use max_completion_tokens instead)

    See: https://community.openai.com/t/temperature-in-gpt-5-models/1337133
    """
    model_lower = model.lower()
    # GPT-5 series (gpt-5, gpt-5-mini, gpt-5.1, gpt-5.2, etc.)
    if model_lower.startswith("gpt-5"):
        return True
    # o1/o3/o4 reasoning models
    if model_lower.startswith(("o1", "o3", "o4")):
        return True
    return False


def build_llm_kwargs(
    model: str,
    temperature: float | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
    **extra_kwargs
) -> dict:
    """
    Build kwargs dict for ChatOpenAI, excluding unsupported params for reasoning models.

    Use this helper when instantiating ChatOpenAI directly in crews to ensure
    compatibility with GPT-5 and reasoning models.

    Args:
        model: Model name
        temperature: Temperature setting (ignored for reasoning models)
        api_key: OpenAI API key (defaults to settings)
        timeout: Timeout in seconds
        **extra_kwargs: Additional kwargs (frequency_penalty, presence_penalty, etc.)

    Returns:
        Dict of kwargs safe to pass to ChatOpenAI
    """
    kwargs = {"model": model}

    if api_key:
        kwargs["api_key"] = api_key
    else:
        kwargs["api_key"] = settings.openai_api_key

    if timeout:
        kwargs["timeout"] = timeout

    # For reasoning models, exclude sampling parameters
    if not is_reasoning_model(model):
        if temperature is not None:
            kwargs["temperature"] = temperature
        # Also handle other sampling params that may be passed
        for param in ["top_p", "frequency_penalty", "presence_penalty"]:
            if param in extra_kwargs:
                kwargs[param] = extra_kwargs.pop(param)

    # Add remaining kwargs
    kwargs.update(extra_kwargs)

    return kwargs


class TokenUsage:
    """Token usage data from LLM invocation."""

    __slots__ = ('prompt_tokens', 'completion_tokens', 'model')

    def __init__(self, prompt_tokens: int, completion_tokens: int, model: str):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model = model

    def to_dict(self) -> dict:
        """Convert to dictionary for cost tracking."""
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'model': self.model
        }


class LLMService:
    """
    Centralized LLM invocation service for both structured and plain text output.

    Handles all ChatOpenAI boilerplate and provides consistent
    error handling across all LLM calls in the codebase.

    Returns both the result and token usage for cost tracking.

    This eliminates 11+ duplicated LLM invocation patterns across the application.
    """

    @staticmethod
    def _extract_usage(response_metadata: dict, model: str) -> TokenUsage:
        """Extract token usage from LangChain response metadata."""
        usage = response_metadata.get('token_usage', {})
        return TokenUsage(
            prompt_tokens=usage.get('prompt_tokens', 0),
            completion_tokens=usage.get('completion_tokens', 0),
            model=model
        )

    @staticmethod
    def invoke_structured(
        prompt: str,
        output_model: Type[T],
        temperature: float = 0.6,
        timeout: int = 120,
        model_name: str | None = None
    ) -> tuple[T, TokenUsage]:
        """
        Invoke LLM with structured Pydantic output.

        Args:
            prompt: The prompt to send to LLM
            output_model: Pydantic model class for structured output
            temperature: Temperature setting (0.0-1.0), default 0.6
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional

        Returns:
            Tuple of (result, TokenUsage) where result is output_model instance

        Raises:
            Exception: If LLM invocation fails
        """
        model = model_name or settings.openai_model_name
        try:
            # Build kwargs - exclude temperature for reasoning models (GPT-5, o1/o3/o4)
            llm_kwargs = {
                "model": model,
                "api_key": settings.openai_api_key,
                "timeout": timeout,
            }
            if not is_reasoning_model(model):
                llm_kwargs["temperature"] = temperature

            llm = ChatOpenAI(**llm_kwargs)
            structured_llm = llm.with_structured_output(
                output_model,
                method="json_schema",  # Explicit constrained decoding for guaranteed schema adherence
                include_raw=True
            )

            raw_result = structured_llm.invoke(prompt)
            parsed = raw_result['parsed']
            raw_response = raw_result['raw']

            usage = LLMService._extract_usage(
                raw_response.response_metadata if hasattr(raw_response, 'response_metadata') else {},
                model
            )

            logger.debug(
                f"LLM invocation successful for {output_model.__name__} "
                f"({usage.prompt_tokens} in / {usage.completion_tokens} out)"
            )
            return parsed, usage

        except Exception as e:
            logger.error(f"LLM invocation failed for {output_model.__name__}: {e}")
            raise

    @staticmethod
    def invoke_plain(
        prompt: str,
        temperature: float = 0.7,
        timeout: int = 120,
        model_name: str | None = None
    ) -> tuple[str, TokenUsage]:
        """
        Invoke LLM with plain text output.

        Args:
            prompt: The prompt to send to LLM
            temperature: Temperature setting (0.0-1.0), default 0.7
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional

        Returns:
            Tuple of (content, TokenUsage) where content is the string response

        Raises:
            Exception: If LLM invocation fails
        """
        model = model_name or settings.openai_model_name
        try:
            # Build kwargs - exclude temperature for reasoning models (GPT-5, o1/o3/o4)
            llm_kwargs = {
                "model": model,
                "api_key": settings.openai_api_key,
                "timeout": timeout,
            }
            if not is_reasoning_model(model):
                llm_kwargs["temperature"] = temperature

            llm = ChatOpenAI(**llm_kwargs)

            result = llm.invoke(prompt)
            usage = LLMService._extract_usage(
                result.response_metadata if hasattr(result, 'response_metadata') else {},
                model
            )

            logger.debug(
                f"LLM plain invocation successful ({model}) "
                f"({usage.prompt_tokens} in / {usage.completion_tokens} out)"
            )
            return result.content, usage

        except Exception as e:
            logger.error(f"LLM plain invocation failed: {e}")
            raise
