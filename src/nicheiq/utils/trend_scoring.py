"""
Trend scoring calculations for market momentum analysis.

Computes deterministic market signals from keyword trend data, social
discussion timestamps, and competitive landscape. Used by TrendLongevityCrew
(Stage 9.5) but independent of CrewAI.

Architecture: Score-First Design
  rising_volume_pct → momentum_score → trend_direction
                                          │
  kw_count_signal ─────────────────→ trend_confidence
  disc_signal ─────────────────────→ (agreement check)

See docs/TREND_SCORING_METHODOLOGY.md for full methodology documentation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..models.competitor import CompetitiveAnalysisResult
    from ..models.keyword_data import CrewKeywordValidationResult
    from ..models.social_content import SocialContentCollection


# ── Thresholds (documented in docs/TREND_SCORING_METHODOLOGY.md) ──────

# Minimum classified keywords to trust computed signals
MIN_KNOWN_KEYWORDS = 5

# momentum_score band boundaries (rvp → score)
# Inspired by financial momentum quintile scoring (S&P, MSCI)
MOMENTUM_BANDS: list[tuple[float, float, float]] = [
    # (rvp_floor, score_floor, score_ceiling)
    (55, 0.80, 0.95),   # Strong growth
    (40, 0.60, 0.80),   # Moderate growth
    (25, 0.40, 0.60),   # Neutral/Stable
    (15, 0.25, 0.40),   # Leaning negative
    (0,  0.10, 0.25),   # Declining
]
SCORE_FLOOR = 0.10   # Winsorization floor (analogous to MSCI z-score cap)
SCORE_CEILING = 0.95  # Winsorization ceiling

# trend_direction thresholds (derived from Pydantic validator constraints)
GROWING_THRESHOLD = 0.60   # Pydantic requires: Growing → score >= 0.6
DECLINING_THRESHOLD = 0.40  # Pydantic requires: Declining → score <= 0.4

# keyword_volume_trend thresholds (rvp-based)
KW_TREND_INCREASING_THRESHOLD = 45  # Majority of volume in rising keywords
KW_TREND_DECREASING_THRESHOLD = 25  # Most volume in stable/declining keywords

# seasonal_pattern thresholds (% of keywords with CV > 0.3)
SEASONAL_STRONG_THRESHOLD = 0.50
SEASONAL_MILD_THRESHOLD = 0.30

# longevity verdict thresholds
DECLINING_RATIO_RISKY = 0.60
EVERGREEN_PCT_SUSTAINABLE = 0.50

# Discussion recency buckets (days)
RECENT_DAYS = 180
MODERATE_DAYS = 365


def compute_momentum_score(rvp: float, known: int) -> float:
    """Compute momentum score from rising_volume_pct.

    Uses piecewise linear interpolation across 5 bands, analogous to
    financial momentum quintile scoring. The score is winsorized to
    [0.10, 0.95] to prevent extreme outlier distortion (cf. MSCI
    methodology which winsorizes z-scores at ±3).

    Args:
        rvp: Rising volume percentage (0-100). Percentage of total keyword
            search volume that is in keywords classified as "rising."
        known: Number of keywords with known trend classification.
            If < MIN_KNOWN_KEYWORDS, returns conservative default.

    Returns:
        Momentum score in [0.10, 0.95]. Higher = more market growth.
        0.50 is the conservative default for insufficient data.
    """
    if known < MIN_KNOWN_KEYWORDS:
        return 0.50

    for i, (band_floor, score_floor, score_ceiling) in enumerate(MOMENTUM_BANDS):
        if rvp >= band_floor:
            # Compute band width (distance to next higher band's floor)
            if i == 0:
                band_width = 45  # Top band: 55-100
            else:
                band_width = MOMENTUM_BANDS[i - 1][0] - band_floor

            t = min((rvp - band_floor) / band_width, 1.0)  # 0-1 interpolation factor
            score = round(score_floor + t * (score_ceiling - score_floor), 2)
            return max(SCORE_FLOOR, min(score, SCORE_CEILING))

    return SCORE_FLOOR  # Shouldn't reach here, but safe default


def compute_trend_direction(momentum_score: float) -> str:
    """Derive trend direction from momentum score.

    By deriving direction FROM the score (not independently), the
    Pydantic validator constraint is satisfied by construction:
      Growing requires score >= 0.6
      Declining requires score <= 0.4

    Args:
        momentum_score: Score from compute_momentum_score()

    Returns:
        "Growing", "Stable", or "Declining"
    """
    if momentum_score >= GROWING_THRESHOLD:
        return "Growing"
    elif momentum_score <= DECLINING_THRESHOLD:
        return "Declining"
    return "Stable"


def compute_keyword_volume_trend(rvp: float, has_data: bool) -> str:
    """Classify keyword volume trend from rising_volume_pct.

    Uses volume-weighted rvp instead of keyword counts. A market where
    80% of search volume is in rising keywords is "Increasing" even if
    only 5 of 50 keywords are classified rising.

    Args:
        rvp: Rising volume percentage (0-100)
        has_data: Whether enriched keyword data is available

    Returns:
        "Increasing", "Stable", or "Decreasing"
    """
    if not has_data:
        return "Stable"
    if rvp >= KW_TREND_INCREASING_THRESHOLD:
        return "Increasing"
    elif rvp <= KW_TREND_DECREASING_THRESHOLD:
        return "Decreasing"
    return "Stable"


def compute_discussion_signals(
    social_content: SocialContentCollection | None,
) -> tuple[str, str]:
    """Compute discussion recency and frequency trend from post timestamps.

    Note: This measures RECENCY of posts, not true frequency. Used as a
    secondary confidence signal, not a primary direction indicator.

    Args:
        social_content: Social media discussions from Stage 5

    Returns:
        Tuple of (discussion_recency, discussion_frequency_trend)
        recency: "Recent", "Moderate", or "Dated"
        frequency: "Increasing", "Stable", or "Decreasing"
    """
    now = datetime.now(timezone.utc)
    buckets: dict[str, int] = {"recent": 0, "moderate": 0, "dated": 0}

    posts: list = []
    if social_content:
        posts.extend(social_content.reddit_posts or [])
        for thread in (social_content.twitter_threads or []):
            if hasattr(thread, 'original_tweet') and thread.original_tweet:
                posts.append(thread.original_tweet)

    for post in posts:
        created = getattr(post, 'created_utc', None) or getattr(post, 'created_at', None)
        if not created:
            continue
        days = (now - created).days
        if days < RECENT_DAYS:
            buckets["recent"] += 1
        elif days < MODERATE_DAYS:
            buckets["moderate"] += 1
        else:
            buckets["dated"] += 1

    total_posts = sum(buckets.values())
    if total_posts == 0:
        return "Dated", "Decreasing"

    majority = max(buckets, key=buckets.get)  # type: ignore[arg-type]
    recency_map = {"recent": "Recent", "moderate": "Moderate", "dated": "Dated"}
    freq_map = {"recent": "Increasing", "moderate": "Stable", "dated": "Decreasing"}
    return recency_map[majority], freq_map[majority]


def compute_trend_confidence(
    trend_direction: str,
    enriched_keywords_trends: dict | None,
    discussion_frequency_trend: str,
) -> str:
    """Compute confidence from secondary signal agreement with primary direction.

    Secondary signals (keyword count breadth + discussion recency) act as
    confirmation indicators, analogous to market breadth confirming price
    momentum in financial analysis.

    Args:
        trend_direction: Primary direction from compute_trend_direction()
        enriched_keywords_trends: Aggregated keyword trend data
        discussion_frequency_trend: From compute_discussion_signals()

    Returns:
        "High", "Medium", or "Low"
    """
    if not enriched_keywords_trends:
        return "Low"

    dist = enriched_keywords_trends.get("trend_distribution", {})
    known = dist.get("rising", 0) + dist.get("stable", 0) + dist.get("declining", 0)

    if known < MIN_KNOWN_KEYWORDS:
        return "Low"

    # Secondary signal 1: keyword count breadth
    rising_count = dist.get("rising", 0)
    declining_count = dist.get("declining", 0)
    if rising_count > declining_count:
        kw_count_signal = "Growing"
    elif declining_count > rising_count:
        kw_count_signal = "Declining"
    else:
        kw_count_signal = "Stable"

    # Secondary signal 2: discussion recency
    disc_signal_map = {"Increasing": "Growing", "Stable": "Stable", "Decreasing": "Declining"}
    disc_signal = disc_signal_map.get(discussion_frequency_trend, "Stable")

    # Count agreements with primary direction
    agreements = sum(1 for s in [kw_count_signal, disc_signal] if s == trend_direction)
    if agreements == 2:
        return "High"
    elif agreements == 1:
        return "Medium"
    return "Low"


def compute_seasonal_pattern(enriched_keywords_trends: dict | None) -> str:
    """Classify seasonal pattern from keyword seasonality data.

    Thresholds raised from 40%/20% to 50%/30% to compensate for upstream
    CV > 0.3 noise (moderate volume variation triggers seasonal flag).

    Args:
        enriched_keywords_trends: Aggregated keyword trend data

    Returns:
        "Strong Seasonal", "Mild Seasonal", "Year-Round", or "Unknown"
    """
    if not enriched_keywords_trends:
        return "Unknown"

    total_kw = enriched_keywords_trends.get("total_keywords_analyzed", 0)
    seasonal_count = enriched_keywords_trends.get("seasonal_count", 0)
    pct = seasonal_count / total_kw if total_kw > 0 else 0

    if pct > SEASONAL_STRONG_THRESHOLD:
        return "Strong Seasonal"
    elif pct > SEASONAL_MILD_THRESHOLD:
        return "Mild Seasonal"
    return "Year-Round"


def compute_longevity_suggestion(enriched_keywords_trends: dict | None) -> str:
    """Suggest longevity verdict from keyword data.

    Never suggests "Fad" — that requires temporal judgment (adoption speed,
    spike patterns) that only the LLM can assess from raw discussion data.
    See L.E.K. Consulting's fad-vs-trend framework.

    Args:
        enriched_keywords_trends: Aggregated keyword trend data

    Returns:
        "Sustainable", "Risky", or "Undetermined"
    """
    if not enriched_keywords_trends:
        return "Undetermined"

    dist = enriched_keywords_trends.get("trend_distribution", {})
    known = dist.get("rising", 0) + dist.get("stable", 0) + dist.get("declining", 0)

    if known == 0:
        return "Undetermined"

    total_kw = enriched_keywords_trends.get("total_keywords_analyzed", 0)
    evergreen_pct = (
        enriched_keywords_trends.get("evergreen_count", 0) / total_kw
        if total_kw else 0
    )
    market_momentum = enriched_keywords_trends.get("market_momentum", "Stable")
    declining_ratio = dist.get("declining", 0) / known

    if declining_ratio > DECLINING_RATIO_RISKY:
        return "Risky"
    elif evergreen_pct > EVERGREEN_PCT_SUSTAINABLE and market_momentum != "Declining":
        return "Sustainable"
    return "Undetermined"


def compute_timing(
    trend_direction: str,
    longevity_verdict: str,
    momentum_score: float,
) -> str:
    """Compute timing recommendation from merged signals.

    Args:
        trend_direction: From compute_trend_direction()
        longevity_verdict: LLM-generated verdict
        momentum_score: From compute_momentum_score()

    Returns:
        "Enter Now", "Monitor & Wait", or "Missed Window"
    """
    if longevity_verdict == "Risky":
        return "Monitor & Wait"
    if longevity_verdict == "Fad":
        return "Missed Window"
    if trend_direction == "Growing" and momentum_score >= 0.7:
        return "Enter Now"
    if trend_direction == "Declining" and momentum_score < 0.4:
        return "Missed Window"
    return "Monitor & Wait"


def compute_data_sources(
    keyword_validation: CrewKeywordValidationResult | None,
    social_content: SocialContentCollection | None,
    competitive_analysis: CompetitiveAnalysisResult | None,
    enriched_keywords_trends: dict | None,
) -> list[str]:
    """List data sources used in the analysis."""
    sources: list[str] = []
    if keyword_validation:
        sources.append("Keyword validation (Stage 8.5)")
    if social_content and (social_content.reddit_posts or social_content.twitter_threads):
        sources.append("Social discussions (Stage 5)")
    if competitive_analysis:
        sources.append("Competitive analysis (Stage 7)")
    if enriched_keywords_trends:
        sources.append("Enriched keyword trends (Stage 9)")
    return sources


def compute_deterministic_signals(
    keyword_validation: CrewKeywordValidationResult | None,
    social_content: SocialContentCollection | None,
    competitive_analysis: CompetitiveAnalysisResult | None,
    enriched_keywords_trends: dict | None,
) -> dict:
    """Compute all deterministic trend signals from available data.

    Orchestrates all individual computation functions. Always returns
    a complete dict (never None). Missing data → conservative defaults.

    This is the main entry point called by TrendLongevityCrew.analyze().

    Args:
        keyword_validation: Keyword data from Stage 8.5
        social_content: Social discussions from Stage 5
        competitive_analysis: Competitive landscape from Stage 7
        enriched_keywords_trends: Aggregated trends from Stage 9.5c

    Returns:
        Dict with keys: keyword_volume_trend, momentum_score,
        trend_direction, trend_confidence, seasonal_pattern,
        discussion_recency, discussion_frequency_trend,
        suggested_longevity_verdict, analysis_timeframe,
        data_sources_analyzed
    """
    # Extract upstream data
    dist = {}
    known = 0
    rvp = 0.0
    if enriched_keywords_trends:
        dist = enriched_keywords_trends.get("trend_distribution", {})
        known = dist.get("rising", 0) + dist.get("stable", 0) + dist.get("declining", 0)
        rvp = enriched_keywords_trends.get("rising_volume_pct", 0)

    has_data = enriched_keywords_trends is not None

    # Compute each signal
    kw_trend = compute_keyword_volume_trend(rvp, has_data)
    score = compute_momentum_score(rvp, known)
    direction = compute_trend_direction(score)
    discussion_recency, discussion_freq = compute_discussion_signals(social_content)
    confidence = compute_trend_confidence(direction, enriched_keywords_trends, discussion_freq)
    seasonal = compute_seasonal_pattern(enriched_keywords_trends)
    verdict = compute_longevity_suggestion(enriched_keywords_trends)
    timeframe = "12 months" if enriched_keywords_trends else "Limited"
    sources = compute_data_sources(
        keyword_validation, social_content, competitive_analysis, enriched_keywords_trends
    )

    return {
        "keyword_volume_trend": kw_trend,
        "momentum_score": score,
        "trend_direction": direction,
        "trend_confidence": confidence,
        "seasonal_pattern": seasonal,
        "discussion_recency": discussion_recency,
        "discussion_frequency_trend": discussion_freq,
        "suggested_longevity_verdict": verdict,
        "analysis_timeframe": timeframe,
        "data_sources_analyzed": sources,
    }
