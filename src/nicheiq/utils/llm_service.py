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


def is_openrouter_model(model: str) -> bool:
    """Check if a model should be routed through OpenRouter.

    Convention: an 'openrouter/' prefix marks the tier as OpenRouter. The bare
    OpenRouter model id (e.g. 'google/gemma-2-27b-it') is what gets sent to the
    OpenAI-compatible endpoint after the prefix is stripped.
    """
    return model.lower().startswith("openrouter/")


def resolve_endpoint(
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> tuple[str, str, str | None]:
    """Route a model string to (clean_model, api_key, base_url) by provider prefix.

    An explicit ``base_url`` always overrides the provider default (preserves the
    prior ``build_llm_kwargs`` contract). Centralizes provider routing so every
    entry point (ChatOpenAI kwargs, invoke_structured/plain) stays consistent.
    """
    if is_openrouter_model(model):
        key = api_key or settings.openrouter_api_key
        if not key:
            raise ValueError(
                "OPENROUTER_API_KEY required for 'openrouter/*' models. "
                "Get one at https://openrouter.ai/keys"
            )
        return model[len("openrouter/"):], key, base_url or settings.openrouter_base_url
    if is_kimi_model(model):
        key = api_key or settings.moonshot_api_key
        if not key:
            raise ValueError(
                "MOONSHOT_API_KEY required when using Kimi models. "
                "Get one at https://platform.moonshot.ai"
            )
        return model, key, base_url or "https://api.moonshot.ai/v1"
    return model, api_key or settings.openai_api_key, base_url


def openrouter_headers() -> dict | None:
    """Optional OpenRouter attribution headers; None if neither is configured."""
    headers = {}
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name
    return headers or None


def validate_openrouter_tier_compatibility() -> None:
    """Fail fast on tier settings that cannot run on OpenRouter.

    RAISES for the landing-page tiers (plain-Task creative steps hard-fail on bad
    JSON, and landing_page_execution_llm needs the OpenAI Responses API which
    OpenRouter doesn't serve). WARNS for other UNSAFE tiers (large context, tool
    calling, reasoning_effort no-op) — those degrade rather than guarantee failure.

    Call this once per pipeline run (ResearchFlow.__init__) and at landing-page
    entrypoints. Kept here (not in settings.py) to avoid a circular import.
    """
    blocked = {
        "LANDING_PAGE_LLM": settings.landing_page_llm,
        "LANDING_PAGE_EXECUTION_LLM": settings.landing_page_execution_llm,
    }
    offenders = [name for name, value in blocked.items() if is_openrouter_model(value)]
    if offenders:
        raise ValueError(
            "OpenRouter is not supported for landing-page tiers "
            f"({', '.join(offenders)}): these run plain-Task creative steps that "
            "hard-fail on non-conforming JSON, and execution requires the OpenAI "
            "Responses API. Use an OpenAI model for these tiers."
        )

    risky = {
        "CONTENT_ANALYSIS_LLM": settings.content_analysis_llm,   # needs very large context
        "FUNCTION_CALLING_LLM": settings.function_calling_llm,   # needs reliable tool calls
        "BRAINSTORM_LLM": settings.brainstorm_llm,               # reasoning_effort is a no-op on OR
        "IDEATION_JUDGE_LLM": settings.ideation_judge_llm,
        "IDEATION_REFINE_LLM": settings.ideation_refine_llm,
    }
    for name, value in risky.items():
        if is_openrouter_model(value):
            logger.warning(
                f"{name} is set to an OpenRouter model ('{value}') — this tier is "
                "UNSAFE for weak models (large context / tool calling / reasoning_effort). "
                "Quality may degrade or output may be incomplete."
            )


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
    # Route provider by model prefix (openrouter/* and kimi auto-detected; explicit
    # base_url overrides). For OpenRouter the prefix is stripped to the bare model id.
    is_openrouter = is_openrouter_model(model)
    model, resolved_key, resolved_base_url = resolve_endpoint(model, api_key, base_url)

    kwargs = {"model": model, "api_key": resolved_key}
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url

    # OpenRouter attribution/ranking headers (only when configured)
    if is_openrouter:
        headers = openrouter_headers()
        if headers:
            kwargs["default_headers"] = headers

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
    if is_openrouter_model(model):
        # build_llm()'s only callers are the landing-page execution (Codex) agents,
        # which are blocked from OpenRouter at startup (see main.validate_environment).
        # Fail loudly here too rather than silently mishandle the Responses-API path.
        raise ValueError(
            f"OpenRouter is not supported for build_llm() callers "
            f"(landing-page execution / Codex tier): got '{model}'. "
            "Use an OpenAI Codex model for landing_page_execution_llm."
        )
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

    For OpenRouter models ('openrouter/*') returns a crewai.llm.LLM with an
    explicit provider='openai' + base_url so CrewAI preserves the OpenRouter
    endpoint (ChatOpenAI's base_url is dropped by CrewAI's create_llm()).
    """
    if is_openrouter_model(model):
        from crewai.llm import LLM as CrewAILLM

        clean_model, resolved_key, resolved_base_url = resolve_endpoint(model, api_key)
        # Explicit provider='openai' is REQUIRED: without it CrewAI infers a provider
        # from the slash in the model id and falls back to litellm (not installed).
        or_kwargs: dict[str, Any] = {
            "model": clean_model,
            "provider": "openai",
            "base_url": resolved_base_url,
            "api_key": resolved_key,
        }
        if temperature is not None:
            or_kwargs["temperature"] = temperature
        # Forward the sampling kwargs the non-reasoning ChatOpenAI path also supports,
        # so a migrated agent behaves the same on OpenRouter as it would on OpenAI.
        for param in ("max_tokens", "top_p", "frequency_penalty", "presence_penalty", "timeout"):
            if param in extra_kwargs:
                or_kwargs[param] = extra_kwargs[param]
        # reasoning_effort is intentionally NOT forwarded: non-reasoning OpenRouter
        # models (e.g. gemma) reject unknown params, and reasoning-capable OpenRouter
        # tiers are classified UNSAFE/blocked.
        headers = openrouter_headers()
        if headers:
            or_kwargs["default_headers"] = headers
        return CrewAILLM(**or_kwargs)

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

    __slots__ = ('prompt_tokens', 'completion_tokens', 'model', 'cost')

    def __init__(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        cost: float | None = None,
    ):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model = model
        # Actual provider-reported cost (USD), when available (OpenRouter returns it;
        # OpenAI does not -> None means "estimate from the price table downstream").
        self.cost = cost

    def to_dict(self) -> dict:
        """Convert to dictionary for cost tracking."""
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'model': self.model,
            'cost': self.cost,
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
        """Extract token usage from LangChain response metadata.

        OpenRouter returns an actual ``cost`` (USD-equivalent) inside the usage
        object, which langchain passes through unfiltered into
        ``response_metadata['token_usage']``. OpenAI omits it (-> None -> estimate).
        """
        usage = response_metadata.get('token_usage', {})
        return TokenUsage(
            prompt_tokens=usage.get('prompt_tokens', 0),
            completion_tokens=usage.get('completion_tokens', 0),
            model=model,
            cost=usage.get('cost'),
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
        is_openrouter = is_openrouter_model(model)
        # Route provider by prefix (openrouter/kimi/openai). LangChain-direct calls
        # honor base_url, so OpenRouter works here without CrewAI.
        clean_model, resolved_key, resolved_base_url = resolve_endpoint(model)
        try:
            # Build kwargs - exclude temperature for reasoning models (GPT-5, o1/o3/o4)
            llm_kwargs = {
                "model": clean_model,
                "api_key": resolved_key,
                "timeout": timeout,
            }
            if resolved_base_url:
                llm_kwargs["base_url"] = resolved_base_url
            if is_openrouter:
                headers = openrouter_headers()
                if headers:
                    llm_kwargs["default_headers"] = headers
            if is_reasoning_model(clean_model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
            else:
                llm_kwargs["temperature"] = temperature

            llm = ChatOpenAI(**llm_kwargs)
            structured_llm = llm.with_structured_output(
                output_model,
                # OpenAI: strict json_schema constrained decoding. OpenRouter models
                # often don't support strict json_schema, so use function_calling
                # (broadly supported but still model-dependent).
                method="function_calling" if is_openrouter else "json_schema",
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
                    f"(model={clean_model}); likely truncated before visible output."
                )

            usage = LLMService._extract_usage(
                raw_response.response_metadata if hasattr(raw_response, 'response_metadata') else {},
                clean_model
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
        is_openrouter = is_openrouter_model(model)
        clean_model, resolved_key, resolved_base_url = resolve_endpoint(model)
        try:
            # Build kwargs - exclude temperature for reasoning models (GPT-5, o1/o3/o4)
            llm_kwargs = {
                "model": clean_model,
                "api_key": resolved_key,
                "timeout": timeout,
            }
            if resolved_base_url:
                llm_kwargs["base_url"] = resolved_base_url
            if is_openrouter:
                headers = openrouter_headers()
                if headers:
                    llm_kwargs["default_headers"] = headers
            if is_reasoning_model(clean_model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
            else:
                llm_kwargs["temperature"] = temperature

            llm = ChatOpenAI(**llm_kwargs)

            result = llm.invoke(prompt)
            usage = LLMService._extract_usage(
                result.response_metadata if hasattr(result, 'response_metadata') else {},
                clean_model
            )

            logger.debug(
                f"LLM plain invocation successful ({clean_model}) "
                f"({usage.prompt_tokens} in / {usage.completion_tokens} out)"
            )
            return result.content, usage

        except Exception as e:
            logger.error(f"LLM plain invocation failed: {e}")
            raise
