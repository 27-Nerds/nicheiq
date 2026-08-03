"""
Custom LLM class for OpenAI Codex models using the Responses API.

Codex models (gpt-5.1-codex-max, etc.) only support the Responses API,
not the Chat Completions endpoint. This class extends CrewAI's BaseLLM
to directly call the Responses API, bypassing CrewAI's default
OpenAI provider which uses chat.completions.

Reference: https://platform.openai.com/docs/models/gpt-5.1-codex
"""

import os
from typing import Any

from crewai import BaseLLM
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel


# Context window sizes for Codex models
CODEX_CONTEXT_WINDOWS = {
    # gpt-5.3-codex verified live on the Responses API (2026-07); mirrors the
    # gpt-5.1-codex-max window. The landing preflight check guards its retirement.
    "gpt-5.3-codex": 200_000,
    "gpt-5.1-codex-max": 200_000,
    "gpt-5.1-codex": 128_000,
    "gpt-5.1-codex-mini": 128_000,
    "gpt-5-codex": 128_000,
}

DEFAULT_CODEX_CONTEXT_WINDOW = 128_000


class CodexLLM(BaseLLM):
    """
    Custom LLM implementation for OpenAI Codex models.

    Codex models require the Responses API instead of Chat Completions.
    This class handles the API differences and extracts text from the
    multi-part response structure.

    Args:
        model: Model name (e.g., "gpt-5.1-codex-max")
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        reasoning_effort: Reasoning effort level ("low", "medium", "high", "xhigh")
        max_output_tokens: Maximum output tokens (default 16384)

    Example:
        >>> from nicheiq.utils.codex_llm import CodexLLM
        >>> llm = CodexLLM(
        ...     model="gpt-5.1-codex-max",
        ...     reasoning_effort="medium",
        ... )
        >>> # Use with CrewAI Agent
        >>> agent = Agent(role="Coder", llm=llm, ...)
    """

    def __init__(
        self,
        model: str = "gpt-5.3-codex",
        api_key: str | None = None,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 16384,
        **kwargs: Any,
    ) -> None:
        """Initialize CodexLLM with Responses API client."""
        super().__init__(model=model, api_key=api_key, provider="openai", **kwargs)

        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens

        # Initialize OpenAI client
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key."
            )
        self._client = OpenAI(api_key=resolved_api_key)

        logger.debug(
            f"CodexLLM initialized: model={model}, "
            f"reasoning_effort={reasoning_effort}, "
            f"max_output_tokens={max_output_tokens}"
        )

    def call(
        self,
        messages: str | list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: type[BaseModel] | None = None,
    ) -> str | Any:
        """
        Call the Codex model via the Responses API.

        Args:
            messages: Input messages (string or list of message dicts)
            tools: Optional tool definitions (converted for Responses API)
            callbacks: Optional callback functions (not used)
            available_functions: Optional function mapping (not used)
            from_task: Source task (for context)
            from_agent: Source agent (for context)
            response_model: Optional Pydantic model for structured output

        Returns:
            Text response from the model
        """
        # Convert messages to Responses API format
        input_items = self._format_messages(messages)

        # Build request parameters
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "max_output_tokens": self.max_output_tokens,
        }

        # Add reasoning effort (Codex models support this)
        if self.reasoning_effort:
            request_kwargs["reasoning"] = {"effort": self.reasoning_effort}

        # Note: Responses API doesn't support stop sequences
        # self.stop is ignored for Codex models

        # Make the API call
        try:
            response = self._client.responses.create(**request_kwargs)
        except Exception as e:
            logger.error(f"CodexLLM API call failed: {e}")
            raise

        # Update token usage tracking
        if hasattr(response, "usage") and response.usage:
            self._token_usage["prompt_tokens"] += response.usage.input_tokens
            self._token_usage["completion_tokens"] += response.usage.output_tokens
            self._token_usage["total_tokens"] += response.usage.total_tokens
            self._token_usage["successful_requests"] += 1

        # Extract text from response
        text = self._extract_text(response)

        logger.debug(
            f"CodexLLM response: {len(text)} chars, "
            f"tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out"
        )

        return text

    def _format_messages(
        self, messages: str | list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Convert messages to Responses API format.

        The Responses API expects messages as:
        [{"role": "user", "content": "..."}]

        Args:
            messages: String or list of message dicts

        Returns:
            List of message dicts in Responses API format
        """
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]

        # Messages is already a list, ensure correct format
        formatted = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Handle content that might be a list (multimodal)
                if isinstance(content, list):
                    # Extract text parts only for now
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    content = "\n".join(text_parts)

                formatted.append({"role": role, "content": str(content)})
            else:
                # Fallback for unexpected types
                formatted.append({"role": "user", "content": str(msg)})

        return formatted

    def _extract_text(self, response: Any) -> str:
        """
        Extract text content from Responses API response.

        The response structure is:
        - response.output: list of items
        - Each item has .type ("reasoning" or "message")
        - Message items have .content list
        - Content items have .type and .text

        Args:
            response: Response object from Responses API

        Returns:
            Extracted text content
        """
        for item in response.output:
            if item.type == "message" and hasattr(item, "content"):
                for content in item.content:
                    if content.type == "output_text":
                        return content.text

        # Fallback: return empty string if no text found
        logger.warning("CodexLLM: No text content found in response")
        return ""

    def get_context_window_size(self) -> int:
        """
        Get the context window size for this Codex model.

        Returns:
            Context window size in tokens
        """
        return CODEX_CONTEXT_WINDOWS.get(
            self.model.lower(), DEFAULT_CODEX_CONTEXT_WINDOW
        )

    def supports_stop_words(self) -> bool:
        """
        Check if this model supports stop words.

        Returns:
            False (Responses API doesn't support stop sequences)
        """
        return False
