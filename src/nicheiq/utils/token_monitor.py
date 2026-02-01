"""
Token monitoring utilities for tracking LLM costs.

Provides visibility into token usage without enforcing hard limits.
Supports configurable soft caps, cost estimation, and per-run cost tracking.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

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

    # Cost per 1M tokens (USD) - Standard tier pricing
    # Structure: {"input": input_cost, "output": output_cost}
    MODEL_PRICING = {
        # GPT-5.2 series
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-5.2-chat-latest": {"input": 1.75, "output": 14.00},
        "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
        # GPT-5.1 series
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5.1-chat-latest": {"input": 1.25, "output": 10.00},
        "gpt-5.1-codex-max": {"input": 1.25, "output": 10.00},
        "gpt-5.1-codex": {"input": 1.25, "output": 10.00},
        "gpt-5.1-codex-mini": {"input": 0.25, "output": 2.00},
        # GPT-5 series
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5-chat-latest": {"input": 1.25, "output": 10.00},
        "gpt-5-codex": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
        "gpt-5-pro": {"input": 15.00, "output": 120.00},
        "gpt-5-search-api": {"input": 1.25, "output": 10.00},
        # GPT-4.1 series
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        # GPT-4o series
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-search-preview": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini-search-preview": {"input": 0.15, "output": 0.60},
        # Realtime models
        "gpt-realtime": {"input": 4.00, "output": 16.00},
        "gpt-realtime-mini": {"input": 0.60, "output": 2.40},
        "gpt-4o-realtime-preview": {"input": 5.00, "output": 20.00},
        "gpt-4o-mini-realtime-preview": {"input": 0.60, "output": 2.40},
        # Audio models
        "gpt-audio": {"input": 2.50, "output": 10.00},
        "gpt-audio-mini": {"input": 0.60, "output": 2.40},
        "gpt-4o-audio-preview": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini-audio-preview": {"input": 0.15, "output": 0.60},
        # o-series reasoning
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 1.10, "output": 4.40},
        "o1-pro": {"input": 150.00, "output": 600.00},
        "o3": {"input": 2.00, "output": 8.00},
        "o3-mini": {"input": 1.10, "output": 4.40},
        "o3-pro": {"input": 20.00, "output": 80.00},
        "o3-deep-research": {"input": 10.00, "output": 40.00},
        "o4-mini": {"input": 1.10, "output": 4.40},
        "o4-mini-deep-research": {"input": 2.00, "output": 8.00},
        # Codex
        "codex-mini-latest": {"input": 1.50, "output": 6.00},
        # Computer use
        "computer-use-preview": {"input": 3.00, "output": 12.00},
        # Image models (input only for generation)
        "gpt-image-1": {"input": 5.00, "output": 5.00},
        "gpt-image-1-mini": {"input": 2.00, "output": 2.00},
        # Legacy GPT-4 series
        "chatgpt-4o-latest": {"input": 5.00, "output": 15.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-2024-04-09": {"input": 10.00, "output": 30.00},
        "gpt-4-0125-preview": {"input": 10.00, "output": 30.00},
        "gpt-4-1106-preview": {"input": 10.00, "output": 30.00},
        "gpt-4-1106-vision-preview": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4-0613": {"input": 30.00, "output": 60.00},
        "gpt-4-0314": {"input": 30.00, "output": 60.00},
        "gpt-4-32k": {"input": 60.00, "output": 120.00},
        # Legacy GPT-3.5 series
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-1106": {"input": 1.00, "output": 2.00},
        "gpt-3.5-turbo-0613": {"input": 1.50, "output": 2.00},
        "gpt-3.5-0301": {"input": 1.50, "output": 2.00},
        "gpt-3.5-turbo-instruct": {"input": 1.50, "output": 2.00},
        "gpt-3.5-turbo-16k-0613": {"input": 3.00, "output": 4.00},
        # Base models
        "davinci-002": {"input": 2.00, "output": 2.00},
        "babbage-002": {"input": 0.40, "output": 0.40},
        # Embeddings (input only)
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
        "text-embedding-ada-002": {"input": 0.10, "output": 0.0},
    }

    # Backward compatibility: input-only cost lookup (for existing estimate_cost usage)
    MODEL_COSTS = {k: v["input"] for k, v in MODEL_PRICING.items()}

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

    def count_post_tokens(self, post: "RedditPost", model: str | None = None) -> int:
        """
        Count tokens for a Reddit post including comments.

        Args:
            post: RedditPost object with title, selftext, and comments
            model: OpenAI model name (default: from CONTENT_ANALYSIS_LLM setting)

        Returns:
            Token count for the entire post
        """
        if model is None:
            model = settings.content_analysis_llm or "gpt-4o"

        text_parts = [post.title, post.selftext]
        for comment in post.comments:
            text_parts.append(comment.body)
            for reply in comment.replies[:15]:  # Match actual reply limit
                text_parts.append(reply.body)
        return self.count_tokens(" ".join(text_parts), model)

    @staticmethod
    def engagement_recency_score(post: "RedditPost") -> float:
        """
        Calculate hybrid score: engagement weighted by recency.

        Recent high-engagement posts score higher than old high-engagement posts.
        Formula: score / days_old (minimum 1 day to avoid division by zero)

        Args:
            post: RedditPost object with score and created_utc

        Returns:
            Engagement/recency score (higher is better)
        """
        from datetime import datetime, timezone
        days_old = max((datetime.now(timezone.utc) - post.created_utc).days, 1)
        return post.score / days_old

    @staticmethod
    def pain_point_priority_score(post: "RedditPost") -> float:
        """
        Calculate priority score optimized for pain point extraction.

        Weights discussion richness and content depth over raw engagement,
        with gentle recency decay so old-but-rich discussions aren't buried.

        Formula:
            0.40 * discussion_richness + 0.25 * engagement +
            0.20 * content_depth + 0.15 * recency

        - discussion_richness: log2(1 + comments) * min(avg_comment_len / 200, 1.5)
        - engagement: log2(1 + upvotes)
        - content_depth: log2(1 + selftext_len) / log2(1 + 2000)
        - recency: 1 / log2(1 + days_old)  (365-day post retains ~12%)

        Args:
            post: RedditPost object with score, comments, selftext, created_utc

        Returns:
            Pain point priority score (higher is better)
        """
        from datetime import datetime, timezone
        from math import log2

        # Discussion richness (40%): comment count weighted by avg comment quality
        comment_count = len(post.comments) if post.comments else 0
        if comment_count > 0:
            total_comment_len = sum(len(c.body) for c in post.comments)
            avg_comment_len = total_comment_len / comment_count
        else:
            avg_comment_len = 0.0
        discussion_richness = log2(1 + comment_count) * min(avg_comment_len / 200, 1.5)

        # Engagement (25%): log-scaled upvotes
        engagement = log2(1 + max(post.score, 0))

        # Content depth (20%): selftext length relative to a "good" post (~2000 chars)
        selftext_len = len(post.selftext) if post.selftext else 0
        content_depth = log2(1 + selftext_len) / log2(1 + 2000)

        # Recency (15%): gentle decay using log
        days_old = max((datetime.now(timezone.utc) - post.created_utc).days, 1)
        recency = 1.0 / log2(1 + days_old)

        return (
            0.40 * discussion_richness
            + 0.25 * engagement
            + 0.20 * content_depth
            + 0.15 * recency
        )

    def filter_posts_to_token_budget(
        self,
        posts: list["RedditPost"],
        max_tokens: int,
        score_fn=None,
    ) -> list["RedditPost"]:
        """
        Sort posts by scoring function and keep what fits in token budget.

        Args:
            posts: List of RedditPost objects to filter
            max_tokens: Maximum total tokens to include
            score_fn: Callable that takes a RedditPost and returns a float score.
                       Defaults to engagement_recency_score.

        Returns:
            Filtered list of posts sorted by score
        """
        if not posts:
            return posts

        if score_fn is None:
            score_fn = self.engagement_recency_score

        # Sort by score (highest first)
        sorted_posts = sorted(
            posts,
            key=score_fn,
            reverse=True
        )

        selected_posts = []
        total_tokens = 0

        for post in sorted_posts:
            post_tokens = self.count_post_tokens(post)
            if total_tokens + post_tokens <= max_tokens:
                selected_posts.append(post)
                total_tokens += post_tokens
            else:
                logger.debug(
                    f"Dropping post {post.post_id} (score: {post.score}, "
                    f"~{post_tokens:,} tokens) - would exceed budget"
                )

        logger.info(
            f"Token budget filter: kept {len(selected_posts)}/{len(posts)} posts "
            f"(~{total_tokens:,} tokens, budget: {max_tokens:,})"
        )
        return selected_posts


@dataclass
class StageUsage:
    """
    Token usage and cost for a single stage/component.

    Used by CostTracker to record per-stage costs for aggregation.
    """

    stage: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CostTracker:
    """
    Aggregate cost tracker for a complete pipeline run.

    Collects token usage from:
    - CrewAI crews (via crew.usage_metrics)
    - Direct LLM calls (via LLMService token tracking)

    Usage:
        tracker = CostTracker()

        # After crew execution:
        tracker.record_crew_usage("Stage 6", crew.usage_metrics, "gpt-4o")

        # After LLM call:
        tracker.record_llm_usage("Niche Context", usage_dict)

        # At end of run:
        tracker.log_summary()
        summary = tracker.get_summary()
    """

    # Default pricing for unknown models (gpt-4o equivalent)
    DEFAULT_PRICING = {"input": 2.50, "output": 10.00}

    def __init__(self):
        """Initialize empty cost tracker."""
        self.stage_usages: list[StageUsage] = []

    def record_crew_usage(
        self,
        stage: str,
        usage_metrics: dict | None,
        model: str
    ) -> StageUsage:
        """
        Record usage from CrewAI crew.usage_metrics.

        Args:
            stage: Stage name (e.g., "Stage 6 - Pain Point Analysis")
            usage_metrics: UsageMetrics object or dict from crew.usage_metrics
            model: Model name for cost lookup

        Returns:
            StageUsage record
        """
        if usage_metrics is None:
            prompt_tokens = 0
            completion_tokens = 0
        elif hasattr(usage_metrics, 'prompt_tokens'):
            # UsageMetrics Pydantic model - access attributes directly
            prompt_tokens = usage_metrics.prompt_tokens or 0
            completion_tokens = usage_metrics.completion_tokens or 0
        else:
            # Dict fallback
            prompt_tokens = usage_metrics.get('prompt_tokens', 0)
            completion_tokens = usage_metrics.get('completion_tokens', 0)

        return self._record_usage(stage, model, prompt_tokens, completion_tokens)

    def record_llm_usage(
        self,
        stage: str,
        usage_dict: dict
    ) -> StageUsage:
        """
        Record usage from LLMService calls.

        Args:
            stage: Stage/component name (e.g., "Niche Context Generation")
            usage_dict: Dict with prompt_tokens, completion_tokens, model

        Returns:
            StageUsage record
        """
        prompt_tokens = usage_dict.get('prompt_tokens', 0)
        completion_tokens = usage_dict.get('completion_tokens', 0)
        model = usage_dict.get('model', 'gpt-4o')

        return self._record_usage(stage, model, prompt_tokens, completion_tokens)

    def _record_usage(
        self,
        stage: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> StageUsage:
        """
        Internal method to record usage and calculate costs.

        Args:
            stage: Stage name
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            StageUsage record
        """
        pricing = ContentTokenMonitor.MODEL_PRICING.get(model, self.DEFAULT_PRICING)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        usage = StageUsage(
            stage=stage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost
        )
        self.stage_usages.append(usage)

        # Log individual stage cost
        if settings.cost_logging_enabled:
            logger.debug(
                f"Cost [{stage}]: {prompt_tokens:,} in + {completion_tokens:,} out = "
                f"${usage.total_cost:.4f} ({model})"
            )

        return usage

    def get_summary(self) -> dict[str, Any]:
        """
        Get aggregated cost summary.

        Returns:
            Dictionary with total tokens, costs, and stage breakdown
        """
        total_prompt = sum(u.prompt_tokens for u in self.stage_usages)
        total_completion = sum(u.completion_tokens for u in self.stage_usages)
        total_input_cost = sum(u.input_cost for u in self.stage_usages)
        total_output_cost = sum(u.output_cost for u in self.stage_usages)

        return {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_input_cost": round(total_input_cost, 4),
            "total_output_cost": round(total_output_cost, 4),
            "total_cost": round(total_input_cost + total_output_cost, 4),
            "stage_breakdown": [u.to_dict() for u in self.stage_usages]
        }

    def log_summary(self) -> None:
        """
        Log formatted cost summary.

        Outputs a formatted summary of all costs to the logger.
        """
        summary = self.get_summary()

        logger.info("=" * 60)
        logger.info("COST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info(
            f"  - Input tokens:  {summary['total_prompt_tokens']:,} "
            f"(${summary['total_input_cost']:.4f})"
        )
        logger.info(
            f"  - Output tokens: {summary['total_completion_tokens']:,} "
            f"(${summary['total_output_cost']:.4f})"
        )
        logger.info(f"Total Cost: ${summary['total_cost']:.4f}")
        logger.info("-" * 60)
        logger.info("Per-Stage Breakdown:")

        for usage in self.stage_usages:
            logger.info(
                f"  {usage.stage}: ${usage.total_cost:.4f} "
                f"({usage.prompt_tokens:,} in / {usage.completion_tokens:,} out)"
            )

        logger.info("=" * 60)
