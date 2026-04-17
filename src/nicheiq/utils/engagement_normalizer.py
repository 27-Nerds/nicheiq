"""Per-source engagement normalization to 0-1 scale.

Borrowed from last30days skill's signals.py pattern. Provides comparable
engagement scores across Reddit, Hacker News, YouTube, and other platforms.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicheiq.models.social_content import SocialPost


def _log1p_safe(value: int | float | None) -> float:
    """Safe log1p that handles None, negative, and non-numeric values."""
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric <= 0:
        return 0.0
    return math.log1p(numeric)


# Per-platform engagement weight tables.
# Each tuple: (raw_engagement_key, weight)
# When raw_engagement keys aren't available, fall back to .score and .num_responses.
_PLATFORM_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "reddit": [("upvotes", 0.40), ("num_comments", 0.40), ("upvote_ratio", 0.20)],
    "hackernews": [("points", 0.50), ("num_comments", 0.50)],
    "youtube": [("views", 0.30), ("likes", 0.40), ("comments", 0.30)],
}

# Empirical max values for normalization (log1p scale).
# These produce scores in roughly 0-1 range for typical content.
_LOG_CEILING = math.log1p(100_000)  # ~11.5


def normalize_engagement(post: SocialPost) -> float:
    """Compute a 0-1 normalized engagement score using platform-specific weights.

    Falls back to generic scoring (score + num_responses) for unknown platforms.
    """
    weights = _PLATFORM_WEIGHTS.get(post.platform)

    if weights:
        raw_score = 0.0
        for key, weight in weights:
            # Try raw_engagement dict first, then model fields
            if key in post.raw_engagement:
                val = post.raw_engagement[key]
                # upvote_ratio is already 0-1, don't log it
                if key == "upvote_ratio":
                    raw_score += float(val or 0) * weight
                else:
                    raw_score += _log1p_safe(val) * weight
            elif key == "num_comments":
                raw_score += _log1p_safe(post.num_responses) * weight
            elif key in ("points", "upvotes"):
                raw_score += _log1p_safe(post.score) * weight
    else:
        # Unknown platform: generic fallback
        raw_score = (
            _log1p_safe(post.score) * 0.5
            + _log1p_safe(post.num_responses) * 0.5
        )

    # Normalize to 0-1 range
    return min(1.0, max(0.0, raw_score / _LOG_CEILING))
