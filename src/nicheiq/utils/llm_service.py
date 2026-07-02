"""LLM invocation utilities for report generation."""

import json
import random
import time
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


# Effort levels that ENABLE reasoning on OpenRouter (its unified reasoning.effort
# accepts low|medium|high; xhigh maps to high).
_OPENROUTER_EFFORT_ENABLE = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
}


def openrouter_reasoning_body(reasoning_effort: str | None) -> dict:
    """Build OpenRouter's unified ``reasoning`` request param (passed via extra_body).

    Policy: on OpenRouter, reasoning is **OFF by default** and only turned on when a
    tier explicitly asks for ``low``/``medium``/``high``/``xhigh``. Everything else
    (``none``/``minimal``/``off``/unset/unknown) returns an explicit DISABLE
    (``{"reasoning": {"enabled": False}}``).

    Why default-off:
      * Reasoning-capable models that think BY DEFAULT (Kimi K2.6, DeepSeek "think"
        mode, ...) otherwise burn the output budget on hidden reasoning and TRUNCATE
        structured/tool-call output — the failure we hit on the validation tiers.
      * OpenRouter normalizes ``reasoning`` per provider and SILENTLY IGNORES it for
        models that don't support reasoning, so the disable is safe on plain models
        (gemma, DeepSeek V4 Flash non-think, ...).

    This both **supports reasoning models** (set an effort to turn it on) and gives
    an explicit **ability to disable** reasoning. Always returns a dict to attach as
    ``extra_body`` on OpenRouter calls.
    """
    mapped = _OPENROUTER_EFFORT_ENABLE.get((reasoning_effort or "").lower())
    if mapped:
        return {"reasoning": {"effort": mapped}}
    return {"reasoning": {"enabled": False}}


# --- max_tokens safety caps -------------------------------------------------
# OpenRouter defaults max_tokens to 65536 when a request omits it, so any model
# can run away/loop to the 64K cap and truncate structured output. These bound
# every OpenRouter request. Capping does NOT reduce normal-case cost (you pay for
# tokens generated, not the cap) — it only bounds the worst case.
MAX_TOKENS_SMALL = 4096      # optional trim for guaranteed-small NON-reasoning calls
MAX_TOKENS_MEDIUM = 8192
MAX_TOKENS_LARGE = 16384
MAX_TOKENS_XL = 32768        # convergent refinement of up to ~12 full idea specs in one call
_DEFAULT_MAX_TOKENS = MAX_TOKENS_LARGE  # backstop — >= every current real output


def _resolve_max_tokens(max_tokens: int | None, *, reasoning_enabled: bool) -> int:
    """Single source of truth for the 'never unbounded' invariant.

    - ``None`` -> backstop (LARGE), so a caller that forgets to size still gets a
      safe, non-truncating cap (never OpenRouter's 65536 default).
    - reasoning-ON -> floor at LARGE: reasoning tokens count against ``max_tokens``,
      so a low cap makes the model burn its budget on hidden thinking and truncate
      the structured output. ``is_reasoning_model`` does NOT recognize the
      OpenRouter reasoning models in use (kimi/deepseek/glm), so this floor — keyed
      on whether reasoning is actually enabled for the call — is what protects them.
    """
    eff = max_tokens or _DEFAULT_MAX_TOKENS
    if reasoning_enabled:
        eff = max(eff, MAX_TOKENS_LARGE)
    return eff


# Vendors that serve their OWN models on a single OpenRouter provider. A third-party
# allowlist (e.g. deepinfra, meant for open-weight roulette) would 404 these, so the
# `only` pin is skipped for them — they don't need it (one vendor, no parser roulette).
_FIRST_PARTY_VENDOR_PREFIXES = ("google/", "openai/", "anthropic/", "x-ai/")


def _structured_provider_routing(clean_model: str = "", *, pin: bool = True) -> dict:
    """OpenRouter `provider` routing for the structured-output SDK path. Always
    require_parameters (route only to providers that honor the request params — tools/
    tool_choice OR response_format). Optionally restrict to an allowlist
    (settings.openrouter_structured_providers) to pin known-good providers for OPEN-WEIGHT
    models whose vLLM/SGLang parser/guided-decoder is provider-dependent. The allowlist is
    skipped for first-party models (google/openai/anthropic/x-ai): they live on ONE provider,
    so a third-party allowlist would route them to nothing (404). Load-balancing still
    happens within the allowlist for open-weight models.

    ``pin=False`` skips the allowlist entirely (creative calls): the divergent/brainstorm
    pool uses open-weight models (minimax/hy3) that the qwen allowlist provider (deepinfra)
    does NOT serve, so pinning them would 404. Those calls free-route among capable providers."""
    allow = settings.openrouter_structured_providers_list
    is_first_party = any(clean_model.startswith(p) for p in _FIRST_PARTY_VENDOR_PREFIXES)
    if pin and allow and not is_first_party:
        # Pin to the vetted providers — and do NOT also set require_parameters. require_parameters
        # filters on EVERY request param, including `reasoning` (we always send
        # reasoning:{enabled:false}); a non-reasoning provider like DeepInfra/qwen doesn't advertise
        # `reasoning`, so require_parameters would exclude it and `only` then leaves ZERO endpoints
        # -> 404 "no endpoints found that can handle the requested parameters" (observed live). The
        # allowlist IS the routing decision: these providers are verified to support response_format/
        # tools, and any param they don't support (reasoning) is silently ignored without it.
        return {"only": allow}
    # No allowlist (or first-party): require_parameters routes among ALL providers to one that
    # honors the structured params (tools/tool_choice OR response_format), excluding silent droppers.
    return {"require_parameters": True}


# --- json_schema (guided-decoding) structured path -------------------------
# JSON-Schema keywords vLLM's guided decoder (xgrammar — DeepInfra/Together/Fireworks)
# cannot compile; leaving them in forces a slower/erroring fallback. Strip them from
# the wire schema and let the Pydantic reader enforce them after parsing instead.
_GUIDED_UNSUPPORTED_KEYS = frozenset({
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "format",
    "minItems", "maxItems", "uniqueItems",
})


def _shape_json_schema(schema: dict) -> dict:
    """Rewrite a Pydantic json-schema into a guided-decoding-friendly shape.

    xgrammar (vLLM's default guided-json backend) can't compile ``$ref``/``$defs``,
    ``oneOf``, or numeric/string/array bounds, and degrades to a slower/erroring
    decoder on them. We:
      * inline every ``$ref`` and drop ``$defs`` (no references survive),
      * rewrite ``oneOf`` -> ``anyOf`` (xgrammar handles anyOf via EBNF alternation),
      * strip the unsupported validation keywords (the Pydantic reader still enforces
        them post-parse).
    Pure-data transform that builds fresh dicts/lists; the model class is untouched.
    """
    defs = {**schema.get("$defs", {}), **schema.get("definitions", {})}

    def resolve(node: Any, seen: frozenset) -> Any:
        if isinstance(node, list):
            return [resolve(n, seen) for n in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            key = ref.split("/")[-1]
            if key in seen:                       # recursion guard (models aren't recursive)
                return {}
            merged = dict(resolve(defs.get(key, {}), seen | {key}))
            for k, v in node.items():             # honor sibling keys alongside $ref
                if k != "$ref":
                    merged[k] = resolve(v, seen)
            return merged
        out: dict = {}
        for k, v in node.items():
            if k in ("$defs", "definitions") or k in _GUIDED_UNSUPPORTED_KEYS:
                continue
            out["anyOf" if k == "oneOf" else k] = resolve(v, seen)
        return out

    return resolve(schema, frozenset())


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
        "BRAINSTORM_LLM": settings.brainstorm_llm,               # needs a reasoning-capable model
        "IDEATION_JUDGE_LLM": settings.ideation_judge_llm,
        "IDEATION_REFINE_LLM": settings.ideation_refine_llm,
    }
    for name, value in risky.items():
        if is_openrouter_model(value):
            logger.warning(
                f"{name} is set to an OpenRouter model ('{value}') — verify it suits this "
                "tier (large context / tool calling / reasoning). The tier's *_reasoning_effort "
                "is forwarded to OpenRouter (ignored by non-reasoning models); quality may "
                "degrade if the model lacks the needed capability."
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

    # OpenRouter attribution/ranking headers (only when configured) + reasoning
    if is_openrouter:
        headers = openrouter_headers()
        if headers:
            kwargs["default_headers"] = headers
        reasoning_body = openrouter_reasoning_body(reasoning_effort)
        if reasoning_body:
            kwargs["extra_body"] = reasoning_body

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
        for param in ("top_p", "frequency_penalty", "presence_penalty", "timeout"):
            if param in extra_kwargs:
                or_kwargs[param] = extra_kwargs[param]
        # Forward reasoning via OpenRouter's unified `reasoning` param (extra_body).
        # Safe on any model (OpenRouter ignores it for non-reasoning models), so a
        # reasoning-capable OR model honors the tier's effort while plain workhorse
        # models are unaffected. extra_body reaches the completion call via CrewAI's
        # additional_params (same mechanism as the Kimi `extra_body` path).
        reasoning_body = openrouter_reasoning_body(reasoning_effort)
        if reasoning_body:
            or_kwargs["extra_body"] = reasoning_body
        # Always bound max_tokens so a CrewAI agent can't inherit OpenRouter's 65536
        # default and run away. Floored to LARGE when reasoning is on.
        reasoning_on = "effort" in reasoning_body.get("reasoning", {})
        or_kwargs["max_tokens"] = _resolve_max_tokens(
            extra_kwargs.get("max_tokens"), reasoning_enabled=reasoning_on
        )
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

    # Bound output for non-reasoning ChatOpenAI agents too (build_llm_kwargs converts
    # max_tokens -> max_completion_tokens). Harmless on OpenAI; keeps the invariant uniform.
    extra_kwargs.setdefault("max_tokens", _resolve_max_tokens(None, reasoning_enabled=False))
    llm_kwargs = build_llm_kwargs(
        model=model,
        temperature=temperature,
        api_key=api_key,
        **extra_kwargs,
    )
    return ChatOpenAI(**llm_kwargs)


def _recover_structured_output(raw_response: Any, output_model: Type["T"]) -> Any:
    """Best-effort recovery of a structured object from a response's TEXT content
    when native structured parsing (tool-call / json_schema) returned None.

    Handles models that answer in ``content`` instead of emitting a tool call, or
    that prefix reasoning before the JSON. Reuses the project's json_extractor
    (its ``clean_llm_response`` strips ``<think>…</think>`` and other paired tags).
    Returns a validated ``output_model`` instance, or None when there is nothing
    usable (genuinely empty/truncated content) — in which case the caller still
    raises/degrades exactly as before.
    """
    content = getattr(raw_response, "content", None)
    if isinstance(content, list):  # multimodal content blocks -> join text parts
        content = " ".join(
            (part.get("text", "") if isinstance(part, dict) else str(part))
            for part in content
        )
    if not isinstance(content, str) or not content.strip():
        return None
    from .parsing.json_extractor import extract_json_object_from_text

    obj = extract_json_object_from_text(content)
    if not isinstance(obj, dict):
        return None
    try:
        return output_model.model_validate(obj)
    except Exception:
        return None


def _structured_from_message(msg: Any, output_model: Type["T"]) -> Any:
    """Universal multi-channel extraction of a structured object from an OpenRouter
    chat-completion message.

    Tries, in priority order: tool-call arguments -> content -> reasoning (plaintext)
    -> reasoning_details[].text/.summary. Returns a validated ``output_model`` or None.

    Why every channel: with a forced tool_choice, several OpenRouter models put the
    tool payload in a NON-standard place — DeepSeek (reasoning ON) emits the JSON into
    the ``reasoning`` channel instead of ``tool_calls`` (proven live), and langchain's
    ChatOpenAI silently DROPS ``reasoning``. Reading the raw SDK message and scanning
    all channels makes structured output robust across DeepSeek / Kimi / GLM regardless
    of where the model stashes the call. Per OpenRouter docs ``reasoning`` /
    ``reasoning_details`` are returned by default when the model reasons.
    """
    from .parsing.json_extractor import extract_json_object_from_text

    candidates: list[str] = []
    for tc in (getattr(msg, "tool_calls", None) or []):
        fn = getattr(tc, "function", None)
        args = getattr(fn, "arguments", None) if fn else None
        if args:
            candidates.append(args)
    content = getattr(msg, "content", None)
    if isinstance(content, str) and content.strip():
        candidates.append(content)
    reasoning = getattr(msg, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        candidates.append(reasoning)
    for d in (getattr(msg, "reasoning_details", None) or []):
        if isinstance(d, dict):
            txt = d.get("text") or d.get("summary")
        else:
            txt = getattr(d, "text", None) or getattr(d, "summary", None)
        if isinstance(txt, str) and txt.strip():
            candidates.append(txt)

    for raw in candidates:
        try:
            obj = json.loads(raw)
        except Exception:
            obj = extract_json_object_from_text(raw)
        if isinstance(obj, dict):
            try:
                return output_model.model_validate(obj)
            except Exception:
                continue
    return None


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
    def _invoke_structured_openrouter(
        prompt: str,
        output_model: Type[T],
        temperature: float,
        timeout: int,
        clean_model: str,
        api_key: str,
        base_url: str | None,
        reasoning_effort: str | None,
        max_tokens: int | None = None,
        creative: bool = False,
        messages: list[dict] | None = None,
    ) -> tuple[T, TokenUsage]:
        """OpenRouter structured-output path via the direct OpenAI SDK (not langchain).

        langchain's ``with_structured_output`` forces tool_choice and then DROPS the
        provider ``reasoning`` field — but several OpenRouter models emit the tool-call
        JSON into that field under a forced tool choice (proven for DeepSeek with
        reasoning ON), so the payload is lost and surfaces as a false "empty output".
        Calling the SDK directly lets ``_structured_from_message`` read the payload from
        WHEREVER the model put it (tool_calls -> content -> reasoning ->
        reasoning_details). Universal across DeepSeek / Kimi / GLM (verified live).
        """
        from openai import OpenAI

        client_kwargs: dict = {"api_key": api_key, "timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
        headers = openrouter_headers()
        if headers:
            client_kwargs["default_headers"] = headers

        # Creative calls (divergent/brainstorm ideation) opt OUT of the structured-workhorse
        # overrides: they keep tool_choice transport (reasoning honored) and free provider
        # routing. Forcing them onto json_schema would strip reasoning, and the deepinfra pin
        # would 404 their non-deepinfra models (minimax/hy3). Extraction tiers keep both.
        use_json_schema = (not creative) and settings.openrouter_structured_mode == "json_schema"
        # Guided-decoding json_schema is for DETERMINISTIC structured extraction; an active
        # reasoning effort on this path breaks open-weight providers (qwen@deepinfra returns
        # empty `{...: []}` with ~9 output tokens, observed live) and adds no value for the
        # extraction/classification/mapping tiers that use it. A tier may still pass an effort
        # (e.g. thread_validation hardcodes 'minimal' for GPT-5-nano) — force it OFF here.
        effective_effort = None if use_json_schema else reasoning_effort
        reasoning_body = openrouter_reasoning_body(effective_effort)
        reasoning_on = "effort" in reasoning_body.get("reasoning", {})

        create_kwargs: dict = {
            "model": clean_model,
            # A caller-supplied multi-turn history (system/user/assistant) enables the
            # ideator↔reviewer mirrored-thread dialog; otherwise wrap the single prompt.
            "messages": messages if messages else [{"role": "user", "content": prompt}],
            # Merge reasoning + provider routing into extra_body (do NOT overwrite reasoning_body).
            # provider.require_parameters=True routes ONLY to providers that honor the request params
            # (tools/tool_choice OR response_format) — avoids silently dropping to a provider that
            # ignores them. An OPTIONAL provider.only allowlist (settings.openrouter_structured_providers)
            # further pins known-good providers (e.g. deepinfra for qwen guided-json) since a CLAIMED
            # capability can still hide a flaky vLLM/SGLang parser. Load-balancing stays within the allowlist.
            "extra_body": {**reasoning_body, "provider": _structured_provider_routing(clean_model, pin=not creative)},
            # Always bound max_tokens (a real wire param on OpenRouter) so the request
            # can never inherit OpenRouter's 65536 default and run away. Floored to LARGE
            # when reasoning is on (reasoning tokens count against this cap).
            "max_tokens": _resolve_max_tokens(max_tokens, reasoning_enabled=reasoning_on),
        }

        # Fallback-model chain (OpenRouter model-layer failover): when the primary model has a
        # configured fallback list, pass OpenRouter's top-level `models` array so a provider outage /
        # upstream 429 on the primary automatically retries the fallbacks IN ONE REQUEST (billed only
        # for the successful run). Essential for SINGLE-PROVIDER models (e.g. inception/mercury-2 —
        # provider-layer failover has nowhere to go; observed live 2026-07-02: one 15s 429 window
        # killed the stance gate for a whole run). The provider.only pin is keyed to the PRIMARY, so
        # it must be dropped (keep require_parameters) or it would strangle the fallback's routing.
        _fallbacks = (settings.llm_fallback_models or {}).get(clean_model) \
            or (settings.llm_fallback_models or {}).get(f"openrouter/{clean_model}")
        if _fallbacks:
            create_kwargs["extra_body"]["models"] = [clean_model] + [
                m.removeprefix("openrouter/") for m in _fallbacks
            ]
            create_kwargs["extra_body"]["provider"] = {"require_parameters": True}

        if use_json_schema:
            # response_format json_schema => guided/constrained decoding, NO tool calls.
            # The grammar masks logits to schema-valid tokens, so this sidesteps BOTH the
            # open-weight tool-parser failure (qwen finish_reason=tool_calls/empty-args) and
            # the Gemini-3 thought_signature 400 — the JSON lands in `content`, which the
            # universal reader already parses. Schema is shaped for xgrammar (no $ref/oneOf/
            # bounds); strict=False because Pydantic schemas use optionals/unions that the
            # strict all-required+nullable contract would reject (guided decoding still constrains).
            create_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "schema": _shape_json_schema(output_model.model_json_schema()),
                    "strict": False,
                },
            }
        else:
            from langchain_core.utils.function_calling import convert_to_openai_tool

            tool = convert_to_openai_tool(output_model)
            tool_name = tool["function"]["name"]
            # tool_choice policy: a FORCED tool choice gives the strictest structured
            # compliance, BUT constrained decoding conflicts with a model's thinking mode
            # — DeepSeek (reasoning ON + forced) intermittently aborts after a few tokens
            # or leaks the call into 'reasoning' (proven live: 'required' is worst, 0/3).
            # So when reasoning is ENABLED, relax to tool_choice='auto' (reliable across
            # DeepSeek/Kimi/GLM); the universal reader still parses whichever channel the
            # payload lands in. When reasoning is OFF, keep the forced choice.
            create_kwargs["tools"] = [tool]
            create_kwargs["tool_choice"] = (
                "auto" if reasoning_on else {"type": "function", "function": {"name": tool_name}}
            )

        if not is_reasoning_model(clean_model):
            create_kwargs["temperature"] = temperature

        # Retry once on TRANSIENT failures. Slow/large reasoning responses (e.g. GLM)
        # are held open with keep-alive padding and occasionally arrive truncated ->
        # the SDK raises json.JSONDecodeError parsing the body; connection/timeout/5xx
        # are likewise transient. A single retry recovers these for every tier (proven
        # rare, <1/14). Non-transient errors (bad request, auth) propagate immediately.
        try:
            from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
            transient = (json.JSONDecodeError, APIConnectionError, APITimeoutError, InternalServerError)
            ratelimit_exc: tuple = (RateLimitError,)
        except Exception:
            transient = (json.JSONDecodeError,)
            ratelimit_exc = ()

        client = OpenAI(**client_kwargs)
        response = None
        parsed = None
        # Outer loop: up to 2 retries (3 attempts) on a clean-but-empty structured response.
        # The escalation branches are mutually exclusive via explicit parse_attempt + transport
        # guards (each ends in `continue`); the final `raise` fires when none match.
        #   json_schema empty -> attempt0 pinned -> attempt1 unpinned reselect -> attempt2 tool.
        #   plain forced-tool empty -> attempt0 relax to auto -> raise (unchanged, 2 calls).
        #   truncation (finish=length) -> retried ONCE (attempt0 only).
        # Inner loop: retry once on TRANSIENT failures (see below).
        for parse_attempt in range(3):
            response = None
            last_exc = None
            transient_tries = 0
            ratelimit_tries = 0
            while response is None:
                try:
                    response = client.chat.completions.create(**create_kwargs)
                except ratelimit_exc as e:
                    # Rate-limit branch: an INSTANT retry inside a 429 window is a guaranteed second
                    # failure (observed live: a whole parallel stance burst died in one 15s window).
                    # Jittered exponential backoff, up to 3 attempts, ≤~12s total sleep. Checked
                    # BEFORE `transient` (RateLimitError subclasses APIStatusError, not in that tuple).
                    last_exc = e
                    ratelimit_tries += 1
                    if ratelimit_tries >= 3:
                        break
                    delay = min(3 * (2 ** (ratelimit_tries - 1)), 8) + random.uniform(0, 1.5)
                    logger.warning(
                        f"OpenRouter rate-limited for {output_model.__name__} "
                        f"(model={clean_model}, attempt {ratelimit_tries}/3) — backing off {delay:.1f}s"
                    )
                    time.sleep(delay)
                except transient as e:
                    # Non-rate-limit transients keep the original single immediate retry.
                    last_exc = e
                    transient_tries += 1
                    if transient_tries >= 2:
                        break
                    logger.warning(
                        f"OpenRouter transient error for {output_model.__name__} "
                        f"(model={clean_model}, attempt {transient_tries}/2): "
                        f"{type(e).__name__}: {str(e)[:120]}"
                    )
            if response is None:
                raise last_exc

            # Some providers (e.g. minimax:nitro) intermittently return a 200 with choices=None
            # or []. Treat that as a no-output rather than letting `choices[0]` raise a bare
            # "'NoneType' object is not subscriptable". finish=None routes it through the same
            # escalation ladder (so the json_schema -> tool fallback is reachable here too).
            choices = getattr(response, "choices", None) or []
            if not choices:
                finish = None
            else:
                msg = choices[0].message
                parsed = _structured_from_message(msg, output_model)
                if parsed is not None:
                    break
                finish = choices[0].finish_reason

            # --- escalation ladder (each branch mutates create_kwargs then `continue`s) ---
            if parse_attempt < 2:
                # (a) Truncation: a fresh call may re-route or complete within the cap. ONCE.
                if finish == "length" and parse_attempt == 0:
                    logger.warning(
                        f"OpenRouter structured output truncated (finish_reason=length) "
                        f"for {output_model.__name__} (model={clean_model}); retrying once."
                    )
                    continue
                # (b) json_schema empty on a clean finish, step 1: drop the provider `only` pin
                # so OpenRouter's require_parameters routing reselects a different json-capable
                # provider. Drop `reasoning` too — it's already disabled on this path, and
                # require_parameters filters on EVERY param (incl. reasoning), which would 404 a
                # non-reasoning provider like qwen@deepinfra.
                if use_json_schema and parse_attempt == 0:
                    logger.warning(
                        f"OpenRouter json_schema output not parseable for {output_model.__name__} "
                        f"(model={clean_model}, finish_reason={finish}); reselecting a json-capable "
                        f"provider (require_parameters) and retrying."
                    )
                    create_kwargs["extra_body"].pop("reasoning", None)
                    create_kwargs["extra_body"]["provider"] = _structured_provider_routing(
                        clean_model, pin=False)
                    continue
                # (c) json_schema empty, step 2: switch to the tool-call transport (a different
                # decoding path that sidesteps the guided-json parser entirely).
                if use_json_schema and parse_attempt == 1:
                    from langchain_core.utils.function_calling import convert_to_openai_tool
                    logger.warning(
                        f"OpenRouter json_schema reselect still empty for {output_model.__name__} "
                        f"(model={clean_model}, finish_reason={finish}); falling back to tool-call "
                        f"transport and retrying."
                    )
                    create_kwargs.pop("response_format", None)
                    create_kwargs["extra_body"].pop("reasoning", None)
                    create_kwargs["tools"] = [convert_to_openai_tool(output_model)]
                    create_kwargs["tool_choice"] = "auto"
                    create_kwargs["extra_body"]["provider"] = _structured_provider_routing(
                        clean_model, pin=False)
                    use_json_schema = False
                    continue
                # (d) Plain forced-tool path produced nothing parseable (qwen/OpenRouter: empty/
                # malformed args from a flaky provider parser). Relax to tool_choice='auto' so the
                # model can emit the JSON into `content`. Reasoning-OFF forced path only, ONCE.
                if not reasoning_on and not use_json_schema and parse_attempt == 0:
                    logger.warning(
                        f"OpenRouter structured output not parseable for {output_model.__name__} "
                        f"(model={clean_model}, finish_reason={finish}); retrying once with "
                        f"tool_choice='auto'."
                    )
                    create_kwargs["tool_choice"] = "auto"
                    continue

            if finish is None:
                raise ValueError(
                    f"OpenRouter returned no choices for {output_model.__name__} (model={clean_model}).")
            raise ValueError(
                f"Structured output for {output_model.__name__} not found in any "
                f"channel (model={clean_model}, finish_reason={finish}); checked "
                f"tool_calls/content/reasoning/reasoning_details."
            )

        usage_obj = response.usage
        cost = None
        if usage_obj is not None:
            cost = getattr(usage_obj, "cost", None)
            if cost is None:
                cost = (getattr(usage_obj, "model_extra", None) or {}).get("cost")
        usage = TokenUsage(
            prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
            model=clean_model,
            cost=cost,
        )
        logger.debug(
            f"OpenRouter structured OK for {output_model.__name__} "
            f"({usage.prompt_tokens} in / {usage.completion_tokens} out, cost={cost})"
        )
        return parsed, usage

    @staticmethod
    def invoke_structured(
        prompt: str = "",
        output_model: Type[T] = None,
        temperature: float = 0.6,
        timeout: int = 120,
        model_name: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        creative: bool = False,
        messages: list[dict] | None = None,
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
            max_tokens: Output cap. None -> safe backstop (never OpenRouter's 65536
                default); floored up when reasoning is enabled. Override upward only
                for genuinely large outputs.
            creative: True for divergent/brainstorm ideation — opts OUT of the OpenRouter
                structured-workhorse overrides (json_schema mode + provider allowlist pin),
                keeping tool_choice transport with reasoning honored and free provider
                routing. Needed because the brainstorm pool (minimax/hy3) isn't served by
                the qwen allowlist provider and would otherwise 404.

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
            # OpenRouter: use the direct OpenAI-SDK path (not langchain) so we can read
            # the structured payload from EVERY channel (tool_calls/content/reasoning).
            # langchain drops `reasoning`, where some models (DeepSeek under reasoning
            # ON + forced tool_choice) put the tool call -> false "empty output".
            if is_openrouter:
                return LLMService._invoke_structured_openrouter(
                    prompt=prompt,
                    output_model=output_model,
                    temperature=temperature,
                    timeout=timeout,
                    clean_model=clean_model,
                    api_key=resolved_key,
                    base_url=resolved_base_url,
                    reasoning_effort=reasoning_effort,
                    max_tokens=max_tokens,
                    creative=creative,
                    messages=messages,
                )
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
                reasoning_body = openrouter_reasoning_body(reasoning_effort)
                if reasoning_body:
                    llm_kwargs["extra_body"] = reasoning_body
            if is_reasoning_model(clean_model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
                # OpenAI reasoning models: max_tokens is dropped here by design (see
                # build_llm_kwargs) — they rely on their own server-side limits.
            else:
                llm_kwargs["temperature"] = temperature
                llm_kwargs["max_tokens"] = _resolve_max_tokens(max_tokens, reasoning_enabled=False)

            llm = ChatOpenAI(**llm_kwargs)
            structured_llm = llm.with_structured_output(
                output_model,
                # OpenAI: strict json_schema constrained decoding. OpenRouter models
                # often don't support strict json_schema, so use function_calling
                # (broadly supported but still model-dependent).
                method="function_calling" if is_openrouter else "json_schema",
                include_raw=True
            )

            raw_result = structured_llm.invoke(messages if messages else prompt)
            parsed = raw_result['parsed']
            raw_response = raw_result['raw']

            # Native structured parse can return None when a model answers in
            # `content` instead of a clean tool call, or prefixes reasoning. Try to
            # recover the JSON from the raw content before failing.
            if parsed is None:
                parsed = _recover_structured_output(raw_response, output_model)
                if parsed is not None:
                    logger.warning(
                        f"Recovered {output_model.__name__} via content fallback "
                        f"(model={clean_model}; native structured parse returned None)"
                    )

            # Genuinely empty/unparseable output. Distinguish the two real causes so
            # the error is actionable (the caller's retry/except path handles either):
            #   * finish_reason == 'tool_calls' but no tool_call/content reached us:
            #     the model emitted the call into a channel langchain drops (e.g.
            #     OpenRouter's 'reasoning' field). Proven for DeepSeek under reasoning
            #     ON + forced tool_choice. Fix = run that tier with reasoning OFF.
            #   * otherwise: truncated/empty before any visible output.
            if parsed is None:
                meta = raw_response.response_metadata if hasattr(raw_response, "response_metadata") else {}
                finish = (meta or {}).get("finish_reason")
                if finish == "tool_calls":
                    raise ValueError(
                        f"Structured output for {output_model.__name__} was lost "
                        f"(model={clean_model}, finish_reason=tool_calls but no tool "
                        f"call/content reached the client). This model likely emitted "
                        f"the tool call into a 'reasoning' channel under forced "
                        f"tool_choice — disable reasoning for this tier "
                        f"(set its *_REASONING_EFFORT=none)."
                    )
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
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
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
            max_tokens: Output cap. None -> safe backstop (never OpenRouter's 65536
                default); floored up when reasoning is enabled.

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
            reasoning_on = False
            if is_openrouter:
                headers = openrouter_headers()
                if headers:
                    llm_kwargs["default_headers"] = headers
                reasoning_body = openrouter_reasoning_body(reasoning_effort)
                reasoning_on = "effort" in reasoning_body.get("reasoning", {})
                if reasoning_body:
                    llm_kwargs["extra_body"] = reasoning_body
            if is_reasoning_model(clean_model):
                if reasoning_effort:
                    llm_kwargs["reasoning_effort"] = reasoning_effort
                # OpenAI reasoning models: max_tokens dropped by design (server-side limits).
            else:
                llm_kwargs["temperature"] = temperature
                # Bound output so an OpenRouter plain call can't inherit the 65536 default.
                llm_kwargs["max_tokens"] = _resolve_max_tokens(
                    max_tokens, reasoning_enabled=reasoning_on
                )

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
