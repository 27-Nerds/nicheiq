"""LLM invocation utilities for report generation."""

from typing import Any, Type, TypeVar

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


def is_codex_model(model: str) -> bool:
    """
    Check if a model requires the Responses API (Codex models).

    Codex models (gpt-5.1-codex-max, etc.) only support the Responses API,
    not the Chat Completions endpoint. LangChain's ChatOpenAI supports this
    via the use_responses_api=True parameter.

    See: https://python.langchain.com/docs/integrations/chat/openai/
    """
    model_lower = model.lower()
    return "codex" in model_lower


def is_kimi_model(model: str) -> bool:
    """Check if a model is a Kimi/Moonshot model requiring the Moonshot API."""
    return model.lower().startswith("kimi")


def build_llm_kwargs(
    model: str,
    temperature: float | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int | None = None,
    reasoning_effort: str | None = None,
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
        base_url: Base URL for the API (auto-detected for Kimi models)
        timeout: Timeout in seconds
        reasoning_effort: Reasoning effort for GPT-5/o1/o3 models ('none', 'minimal', 'low', 'medium', 'high', 'xhigh')
        **extra_kwargs: Additional kwargs (frequency_penalty, presence_penalty, etc.)

    Returns:
        Dict of kwargs safe to pass to ChatOpenAI
    """
    kwargs = {"model": model}

    if api_key:
        kwargs["api_key"] = api_key
    elif is_kimi_model(model):
        if not settings.moonshot_api_key:
            raise ValueError(
                "MOONSHOT_API_KEY required when using Kimi models. "
                "Get one at https://platform.moonshot.ai"
            )
        kwargs["api_key"] = settings.moonshot_api_key
        kwargs["base_url"] = "https://api.moonshot.ai/v1"
    else:
        kwargs["api_key"] = settings.openai_api_key

    # Explicit base_url overrides auto-detected one
    if base_url:
        kwargs["base_url"] = base_url

    if timeout:
        kwargs["timeout"] = timeout

    # Note: For Codex models, use build_llm() instead of ChatOpenAI directly
    # The use_responses_api flag on ChatOpenAI is ignored by CrewAI's internal handling

    # For reasoning models, exclude sampling parameters but allow reasoning_effort
    if is_reasoning_model(model):
        if reasoning_effort:
            # Pass reasoning_effort directly (LangChain supports it as explicit parameter)
            kwargs["reasoning_effort"] = reasoning_effort
    else:
        if temperature is not None:
            kwargs["temperature"] = temperature
        # Also handle other sampling params that may be passed
        for param in ["top_p", "frequency_penalty", "presence_penalty"]:
            if param in extra_kwargs:
                kwargs[param] = extra_kwargs.pop(param)

    # Handle max_tokens/max_completion_tokens
    # For reasoning models: CrewAI/LiteLLM doesn't forward max_completion_tokens properly,
    # so we exclude it entirely to avoid truncation issues. Use non-reasoning models for
    # tasks requiring large outputs.
    # For non-reasoning models: Convert max_tokens to max_completion_tokens (OpenAI API change)
    if "max_tokens" in extra_kwargs:
        if is_reasoning_model(model):
            # Remove max_tokens for reasoning models - CrewAI can't handle it
            extra_kwargs.pop("max_tokens")
            logger.warning(
                f"max_tokens ignored for reasoning model '{model}'. "
                f"Use a non-reasoning model (gpt-4o) for tasks requiring large outputs."
            )
        else:
            extra_kwargs["max_completion_tokens"] = extra_kwargs.pop("max_tokens")

    # Also check if max_completion_tokens was passed directly
    if "max_completion_tokens" in extra_kwargs and is_reasoning_model(model):
        extra_kwargs.pop("max_completion_tokens")
        logger.warning(
            f"max_completion_tokens ignored for reasoning model '{model}'. "
            f"CrewAI doesn't forward this parameter properly."
        )

    # Add remaining kwargs
    kwargs.update(extra_kwargs)

    return kwargs


def build_llm(
    model: str,
    reasoning_effort: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_output_tokens: int = 16384,
    **extra_kwargs: Any,
) -> Any:
    """
    Build the appropriate LLM instance based on model type.

    For Kimi models, returns ChatOpenAI pointed at Moonshot's API.
    For Codex models (gpt-5.1-codex-max, etc.), returns CodexLLM which uses
    the Responses API. For all other models, returns ChatOpenAI.

    Args:
        model: Model name
        reasoning_effort: Reasoning effort for GPT-5/o1/o3 models
        api_key: OpenAI API key (defaults to settings)
        base_url: Base URL for the API (auto-detected for Kimi models)
        max_output_tokens: Max output tokens for Codex models
        **extra_kwargs: Additional kwargs passed to the LLM

    Returns:
        LLM instance (CodexLLM or ChatOpenAI)
    """
    if is_kimi_model(model):
        # Use CrewAI's native LLM class directly so CrewAI preserves base_url.
        # ChatOpenAI stores it as openai_api_base, which CrewAI's create_llm()
        # can't read (it looks for base_url), causing requests to hit api.openai.com.
        from crewai.llm import LLM as CrewAILLM

        resolved_api_key = api_key
        resolved_base_url = base_url or "https://api.moonshot.ai/v1"
        if not resolved_api_key:
            if not settings.moonshot_api_key:
                raise ValueError(
                    "MOONSHOT_API_KEY required when using Kimi models. "
                    "Get one at https://platform.moonshot.ai"
                )
            resolved_api_key = settings.moonshot_api_key

        thinking = settings.kimi_thinking
        kimi_kwargs: dict[str, Any] = {
            "model": model,
            "provider": "openai",
            "base_url": resolved_base_url,
            "api_key": resolved_api_key,
        }
        if thinking:
            # Thinking mode: deeper reasoning, temperature must be 1.0
            kimi_kwargs["temperature"] = 1.0
        else:
            # Instant mode: faster, cheaper, deterministic code output
            kimi_kwargs["temperature"] = 0.6
            kimi_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if max_output_tokens:
            kimi_kwargs["max_tokens"] = max_output_tokens

        return CrewAILLM(**kimi_kwargs)
    elif is_codex_model(model):
        # Use custom CodexLLM for Codex models (Responses API)
        from .codex_llm import CodexLLM
        return CodexLLM(
            model=model,
            api_key=api_key or settings.openai_api_key,
            reasoning_effort=reasoning_effort or "medium",
            max_output_tokens=max_output_tokens,
        )
    else:
        # Use ChatOpenAI for standard models
        llm_kwargs = build_llm_kwargs(
            model=model,
            api_key=api_key,
            reasoning_effort=reasoning_effort,
            **extra_kwargs,
        )
        return ChatOpenAI(**llm_kwargs)


def build_crew_llm(
    model: str,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    api_key: str | None = None,
    **extra_kwargs: Any,
) -> Any:
    """
    Build an LLM instance for CrewAI Agents.

    For reasoning models (GPT-5/o1/o3/o4) returns a crewai.llm.LLM directly:
    CrewAI's create_llm() extracts only basic params (model/temperature/
    max_tokens) from a ChatOpenAI instance and silently DROPS reasoning_effort
    — which left the ideation pipeline with zero working creativity/depth
    knobs (temperature is unsupported on reasoning models AND the substitute
    never reached the API). The CrewAI LLM forwards reasoning_effort straight
    to litellm (verified: llm.py _prepare_completion_params).

    For non-reasoning models, returns ChatOpenAI via build_llm_kwargs
    (unchanged behavior — temperature et al. survive CrewAI conversion).
    """
    if is_reasoning_model(model):
        from crewai.llm import LLM as CrewAILLM

        if temperature is not None and not reasoning_effort:
            logger.warning(
                f"'{model}' is a reasoning model: temperature={temperature} is unsupported "
                "and no reasoning_effort substitute is configured — the call runs at model "
                "defaults with no diversity/depth tuning. Set a reasoning_effort."
            )
        crew_llm_kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key or settings.openai_api_key,
        }
        if reasoning_effort:
            crew_llm_kwargs["reasoning_effort"] = reasoning_effort
            logger.debug(f"build_crew_llm: {model} with reasoning_effort={reasoning_effort} (via CrewAI LLM)")
        return CrewAILLM(**crew_llm_kwargs)

    llm_kwargs = build_llm_kwargs(
        model=model,
        temperature=temperature,
        api_key=api_key,
        **extra_kwargs,
    )
    return ChatOpenAI(**llm_kwargs)


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
        model_name: str | None = None,
        reasoning_effort: str | None = None
    ) -> tuple[T, TokenUsage]:
        """
        Invoke LLM with structured Pydantic output.

        Args:
            prompt: The prompt to send to LLM
            output_model: Pydantic model class for structured output
            temperature: Temperature setting (0.0-1.0), default 0.6
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional
            reasoning_effort: Reasoning effort for GPT-5/o-series models
                ('none', 'minimal', 'low', 'medium', 'high', 'xhigh'). Ignored
                for non-reasoning models. Use 'minimal' for fast, low-cost
                structured calls so hidden reasoning tokens don't blow up cost.

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
            if is_reasoning_model(model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
            else:
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

            # Reasoning models can exhaust the output budget on hidden reasoning
            # before emitting any visible content, leaving parsed=None. Surface
            # this as a clear error (the caller's retry/except path handles it)
            # instead of returning None downstream.
            if parsed is None:
                raise ValueError(
                    f"Structured output for {output_model.__name__} was empty "
                    f"(model={model}); likely truncated before visible output."
                )

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
        model_name: str | None = None,
        reasoning_effort: str | None = None
    ) -> tuple[str, TokenUsage]:
        """
        Invoke LLM with plain text output.

        Args:
            prompt: The prompt to send to LLM
            temperature: Temperature setting (0.0-1.0), default 0.7
            timeout: Timeout in seconds, default 120
            model_name: Override default model, optional
            reasoning_effort: Reasoning effort for GPT-5/o-series models
                ('none', 'minimal', 'low', 'medium', 'high', 'xhigh'). Ignored
                for non-reasoning models.

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
            if is_reasoning_model(model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
            else:
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
