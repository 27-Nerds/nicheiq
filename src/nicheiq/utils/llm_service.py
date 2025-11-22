"""LLM invocation utilities for report generation."""

from typing import Type, TypeVar

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel

from ..config.settings import settings

T = TypeVar('T', bound=BaseModel)


class LLMService:
    """
    Centralized LLM invocation service for both structured and plain text output.

    Handles all ChatOpenAI boilerplate and provides consistent
    error handling across all LLM calls in the codebase.

    This eliminates 11+ duplicated LLM invocation patterns across the application.
    """

    @staticmethod
    def invoke_structured(
        prompt: str,
        output_model: Type[T],
        temperature: float = 0.6,
        timeout: int = 120,
        model_name: str | None = None
    ) -> T:
        """
        Invoke LLM with structured Pydantic output.

        Args:
            prompt: The prompt to send to LLM
            output_model: Pydantic model class for structured output
            temperature: Temperature setting (0.0-1.0), default 0.6
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional

        Returns:
            Instance of output_model populated by LLM

        Raises:
            Exception: If LLM invocation fails
        """
        try:
            structured_llm = ChatOpenAI(
                model=model_name or settings.openai_model_name,
                temperature=temperature,
                api_key=settings.openai_api_key,
                timeout=timeout,
            ).with_structured_output(output_model)

            result = structured_llm.invoke(prompt)
            logger.debug(f"LLM invocation successful for {output_model.__name__}")
            return result

        except Exception as e:
            logger.error(f"LLM invocation failed for {output_model.__name__}: {e}")
            raise

    @staticmethod
    def invoke_plain(
        prompt: str,
        temperature: float = 0.7,
        timeout: int = 120,
        model_name: str | None = None
    ) -> str:
        """
        Invoke LLM with plain text output.

        Args:
            prompt: The prompt to send to LLM
            temperature: Temperature setting (0.0-1.0), default 0.7
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional

        Returns:
            Plain text string response from LLM

        Raises:
            Exception: If LLM invocation fails
        """
        try:
            llm = ChatOpenAI(
                model=model_name or settings.openai_model_name,
                temperature=temperature,
                api_key=settings.openai_api_key,
                timeout=timeout,
            )

            result = llm.invoke(prompt)
            logger.debug(f"LLM plain invocation successful (model: {model_name or settings.openai_model_name})")
            return result.content

        except Exception as e:
            logger.error(f"LLM plain invocation failed: {e}")
            raise
