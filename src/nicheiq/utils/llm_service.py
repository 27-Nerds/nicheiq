"""LLM invocation utilities for report generation."""

from typing import Type, TypeVar

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel

from ..config.settings import settings

T = TypeVar('T', bound=BaseModel)


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
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=settings.openai_api_key,
                timeout=timeout,
            )
            structured_llm = llm.with_structured_output(output_model, include_raw=True)

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
            llm = ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=settings.openai_api_key,
                timeout=timeout,
            )

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
