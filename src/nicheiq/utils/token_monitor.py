"""
Token monitoring utilities for tracking LLM input costs.

Provides visibility into token usage without enforcing hard limits.
Supports configurable soft caps and cost estimation.
"""

import logging

from ..config.settings import settings

logger = logging.getLogger(__name__)

class ContentTokenMonitor:
    """
    Token counting and cost monitoring for LLM inputs.

    Provides visibility into token usage without enforcing hard limits.
    Supports configurable soft caps and cost estimation.

    Used for: Monitoring large content inputs (Reddit/Twitter posts) to prevent
    unexpected costs and track context window usage.
    """

    # Cost per 1M input tokens (USD) - Standard tier pricing
    MODEL_COSTS = {
        # GPT-5 series
        "gpt-5.1": 1.25,
        "gpt-5": 1.25,
        "gpt-5-mini": 0.25,
        "gpt-5-nano": 0.05,
        # GPT-4.1 series
        "gpt-4.1": 2.00,
        "gpt-4.1-mini": 0.40,
        "gpt-4.1-nano": 0.10,
        # GPT-4o series
        "gpt-4o": 2.50,
        "gpt-4o-mini": 0.15,
        # o-series reasoning
        "o3": 2.00,
        "o4-mini": 1.10,
        "o3-mini": 1.10,
        "o1-mini": 1.10,
        # Legacy
        "gpt-4-turbo": 10.00,
        "gpt-4": 30.00,
        "gpt-3.5-turbo": 0.50,
    }

    def __init__(self):
        """Initialize token monitor."""
        try:
            import tiktoken
            self.tiktoken = tiktoken
            self.encoding_cache = {}
        except ImportError:
            logger.warning(
                "tiktoken not installed - token counting disabled. "
                "Install with: pip install tiktoken"
            )
            self.tiktoken = None
            self.encoding_cache = {}

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        """
        Count tokens in text for specified model.

        Args:
            text: Input text to count tokens
            model: OpenAI model name (default: gpt-4o)

        Returns:
            Token count, or 0 if tiktoken not available
        """
        if not self.tiktoken or not text:
            return 0

        try:
            # Get or create encoding for model
            if model not in self.encoding_cache:
                self.encoding_cache[model] = self.tiktoken.encoding_for_model(model)

            encoding = self.encoding_cache[model]
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed for model {model}: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

    def estimate_cost(self, tokens: int, model: str = "gpt-4o") -> float:
        """
        Estimate API cost for token count.

        Args:
            tokens: Number of input tokens
            model: OpenAI model name

        Returns:
            Estimated cost in USD
        """
        cost_per_million = self.MODEL_COSTS.get(model, 2.50)  # Default to gpt-4o
        return (tokens / 1_000_000) * cost_per_million

    def log_content_stats(
        self,
        content: str,
        label: str,
        model: str = "gpt-4o",
        context_limit: int = 1_000_000
    ) -> int:
        """
        Log token count and cost estimate for content.

        Args:
            content: Content to analyze
            label: Descriptive label for logging (e.g., "Task 1 Reddit content")
            model: Model name for token counting
            context_limit: Model's context window size (default: 1M for extended models)

        Returns:
            Token count
        """
        if not settings.token_monitoring_enabled:
            return 0

        token_count = self.count_tokens(content, model)
        cost_estimate = self.estimate_cost(token_count, model)
        percentage = (token_count / context_limit) * 100 if context_limit > 0 else 0

        logger.info(
            f"{label}: {token_count:,} tokens (~${cost_estimate:.2f}), "
            f"{percentage:.1f}% of {context_limit:,} context window"
        )

        return token_count

    def check_soft_cap(
        self,
        tokens: int,
        label: str,
        model: str = "gpt-4o"
    ) -> bool:
        """
        Check if token count exceeds soft cap and log warnings.

        Args:
            tokens: Token count to check
            label: Descriptive label for logging
            model: Model name for cost estimation

        Returns:
            True if over soft cap (when enabled), False otherwise
        """
        # Check warning threshold (always enabled)
        if tokens > settings.token_warning_threshold:
            cost = self.estimate_cost(tokens, model)
            logger.warning(
                f"{label}: Large content detected ({tokens:,} tokens, ~${cost:.2f}). "
                f"Exceeds warning threshold of {settings.token_warning_threshold:,} tokens."
            )

        # Check soft cap (if enabled)
        if settings.token_soft_cap_enabled and tokens > settings.token_soft_cap:
            cost = self.estimate_cost(tokens, model)
            logger.critical(
                f"{label}: Content exceeds soft cap! "
                f"({tokens:,} tokens > {settings.token_soft_cap:,} limit, ~${cost:.2f}). "
                f"Consider reducing collection size or increasing soft cap in settings."
            )
            return True

        return False
