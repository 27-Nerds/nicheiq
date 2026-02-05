"""
Tests for keyword trend classification consistency.

Ensures _format_keyword_monthly_trends (crew) and _calculate_trend_metrics (flow)
produce consistent results regardless of input sort order, and that symmetric
thresholds and low-volume noise floors work correctly.

Regression tests for: declining-trend bias caused by unsorted monthly data
and misaligned thresholds between the two functions.
"""

import pytest


# ---------------------------------------------------------------------------
# Helper: build 12-month search data
# ---------------------------------------------------------------------------

def _make_monthly(volumes_oldest_first: list[int], start_year: int = 2024, start_month: int = 1) -> list[dict]:
    """Build monthly_searches dicts from a list of volumes (oldest-first).

    Returns dicts in oldest-first order (Jan→Dec) — the order DataForSEO
    typically returns. Tests must prove that classification is correct
    regardless of this ordering.
    """
    result = []
    y, m = start_year, start_month
    for vol in volumes_oldest_first:
        result.append({"year": y, "month": m, "search_volume": vol})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


# ---------------------------------------------------------------------------
# Fixtures: instantiate the objects under test
# ---------------------------------------------------------------------------

@pytest.fixture
def flow():
    """Provide _calculate_trend_metrics as a bound method without full ResearchFlow init.

    _calculate_trend_metrics is a pure function that only uses `self` for method
    dispatch.  We grab the unbound method and bind it to a dummy object so we
    don't need to instantiate the full ResearchFlow (which requires API keys,
    tools, etc.).
    """
    from nicheiq.flows.research_flow import ResearchFlow

    class _Stub:
        """Minimal stand-in that carries the method."""
        _calculate_trend_metrics = ResearchFlow._calculate_trend_metrics

    return _Stub()


@pytest.fixture
def crew():
    """Minimal TrendLongevityCrew (only _format_keyword_monthly_trends needed)."""
    from nicheiq.crews.trend_longevity_crew import TrendLongevityCrew
    return TrendLongevityCrew.__new__(TrendLongevityCrew)


# ===================================================================
# A. Sort-order invariance
# ===================================================================

class TestSortOrderInvariance:
    """Both functions must produce identical results whether input is
    oldest-first or newest-first."""

    # Clearly rising: old months ~100, recent months ~200
    RISING_OLDEST_FIRST = [100, 105, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
    # Clearly declining: old months ~200, recent months ~100
    DECLINING_OLDEST_FIRST = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 105, 100]
    # Stable: ~150 throughout
    STABLE_OLDEST_FIRST = [150, 148, 152, 149, 151, 150, 148, 152, 149, 151, 150, 148]

    @pytest.mark.parametrize("label,volumes", [
        ("rising", RISING_OLDEST_FIRST),
        ("declining", DECLINING_OLDEST_FIRST),
        ("stable", STABLE_OLDEST_FIRST),
    ])
    def test_calculate_trend_metrics_order_invariant(self, flow, label, volumes):
        """_calculate_trend_metrics must give the same result for both orderings."""
        oldest_first = _make_monthly(volumes)
        newest_first = list(reversed(oldest_first))

        result_of = flow._calculate_trend_metrics(oldest_first)
        result_nf = flow._calculate_trend_metrics(newest_first)

        assert result_of["trend_direction"] == result_nf["trend_direction"], (
            f"Sort-order mismatch for {label}: oldest-first={result_of['trend_direction']}, "
            f"newest-first={result_nf['trend_direction']}"
        )
        assert result_of["trend_score"] == result_nf["trend_score"]

    @pytest.mark.parametrize("label,volumes,expected_arrow", [
        ("rising", RISING_OLDEST_FIRST, "↑ Rising"),
        ("declining", DECLINING_OLDEST_FIRST, "↓ Declining"),
        ("stable", STABLE_OLDEST_FIRST, "→ Stable"),
    ])
    def test_format_keyword_monthly_trends_order_invariant(self, crew, label, volumes, expected_arrow):
        """_format_keyword_monthly_trends must give the same arrow for both orderings."""
        oldest_first = _make_monthly(volumes)
        newest_first = list(reversed(oldest_first))

        kw_of = [{"keyword": "test kw", "search_volume": 150, "monthly_searches": oldest_first}]
        kw_nf = [{"keyword": "test kw", "search_volume": 150, "monthly_searches": newest_first}]

        result_of = crew._format_keyword_monthly_trends(kw_of)
        result_nf = crew._format_keyword_monthly_trends(kw_nf)

        assert result_of == result_nf, (
            f"Sort-order mismatch for {label}: oldest-first output != newest-first output"
        )
        assert expected_arrow in result_of, (
            f"Expected '{expected_arrow}' in output for {label}, got: {result_of}"
        )


# ===================================================================
# B. Cross-function consistency
# ===================================================================

class TestCrossFunctionConsistency:
    """_format_keyword_monthly_trends and _calculate_trend_metrics must agree
    on direction for the same monthly data."""

    # Map _calculate_trend_metrics direction → expected arrow substring
    DIRECTION_TO_ARROW = {
        "rising": "Rising",
        "declining": "Declining",
        "stable": "Stable",
    }

    @pytest.mark.parametrize("desc,volumes", [
        ("strong_rise", [80, 85, 90, 100, 120, 140, 160, 180, 200, 220, 240, 260]),
        ("strong_decline", [260, 240, 220, 200, 180, 160, 140, 120, 100, 90, 85, 80]),
        ("flat", [500, 505, 498, 502, 500, 497, 503, 500, 498, 502, 500, 505]),
        ("moderate_rise_15pct", [100, 100, 100, 100, 100, 100, 100, 100, 100, 115, 115, 115]),
        ("moderate_decline_15pct", [200, 200, 200, 200, 200, 200, 200, 200, 200, 170, 170, 170]),
        ("borderline_rise_11pct", [100, 100, 100, 100, 100, 100, 100, 100, 100, 111, 111, 111]),
        ("borderline_decline_11pct", [200, 200, 200, 200, 200, 200, 200, 200, 200, 178, 178, 178]),
    ])
    def test_both_functions_agree_on_direction(self, flow, crew, desc, volumes):
        """The trend arrow in the formatted text must match the metric direction."""
        monthly = _make_monthly(volumes)

        metric_result = flow._calculate_trend_metrics(monthly)
        direction = metric_result["trend_direction"]

        # Skip 'unknown' — only happens with <2 data points
        if direction == "unknown":
            pytest.skip("unknown direction, not testable for agreement")

        formatted = crew._format_keyword_monthly_trends(
            [{"keyword": "test", "search_volume": 500, "monthly_searches": monthly}]
        )

        expected_arrow = self.DIRECTION_TO_ARROW[direction]
        assert expected_arrow in formatted, (
            f"[{desc}] _calculate_trend_metrics says '{direction}' but "
            f"_format_keyword_monthly_trends does not contain '{expected_arrow}'. "
            f"Output: {formatted}"
        )


# ===================================================================
# C. Asymmetric threshold behavior
# ===================================================================

class TestClassificationThresholds:
    """Symmetric ±10% thresholds for rising/declining classification.
    Normal keyword noise is ±5-15%, so ±10% prevents false classifications."""

    def test_9pct_rise_is_stable(self, flow):
        """A 9% rise should be 'stable' (below the 10% rising threshold)."""
        # old avg = 100, recent avg = 109 → +9%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 109, 109, 109]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_11pct_rise_is_rising(self, flow):
        """An 11% rise should be 'rising' (above the 10% threshold)."""
        # old avg = 100, recent avg = 111 → +11%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 111, 111, 111]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "rising"

    def test_9pct_decline_is_stable(self, flow):
        """A 9% decline should be 'stable' (inside the -10% threshold)."""
        # old avg = 200, recent avg = 182 → -9%
        volumes = [200, 200, 200, 200, 200, 200, 200, 200, 200, 182, 182, 182]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_11pct_decline_is_declining(self, flow):
        """An 11% decline should be 'declining' (beyond the -10% threshold)."""
        # old avg = 200, recent avg = 178 → -11%
        volumes = [200, 200, 200, 200, 200, 200, 200, 200, 200, 178, 178, 178]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "declining"

    def test_symmetry_prevents_false_declining(self, flow):
        """A -9% change should be 'stable' under symmetric ±10% thresholds."""
        # old avg = 100, recent avg = 91 → -9%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 91, 91, 91]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable", (
            "A -9% change should be stable under symmetric ±10% thresholds"
        )


# ===================================================================
# D. Low-volume noise floor
# ===================================================================

class TestLowVolumeNoiseFloor:
    """When both recent and older averages are below 50, the keyword should
    always be classified as 'stable' regardless of percentage change."""

    def test_low_volume_large_pct_change_is_stable(self, flow):
        """Tiny volumes (10→30) have +200% change but should be stable."""
        # old avg ~10, recent avg ~30 → +200%
        volumes = [10, 10, 10, 10, 10, 10, 10, 10, 10, 30, 30, 30]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_low_volume_decline_is_stable(self, flow):
        """Tiny volumes (40→10) have -75% change but should be stable."""
        # old avg ~40, recent avg ~10 → -75%
        volumes = [40, 40, 40, 40, 40, 40, 40, 40, 40, 10, 10, 10]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_noise_floor_not_applied_when_volumes_above_50(self, flow):
        """When volumes are >= 50, normal thresholds apply."""
        # old avg = 60, recent avg = 80 → +33% → rising
        volumes = [60, 60, 60, 60, 60, 60, 60, 60, 60, 80, 80, 80]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "rising"

    def test_low_volume_noise_floor_in_crew_format(self, crew):
        """Crew formatter should also apply noise floor for low-volume keywords."""
        volumes = [10, 10, 10, 10, 10, 10, 10, 10, 10, 30, 30, 30]
        monthly = _make_monthly(volumes)
        result = crew._format_keyword_monthly_trends(
            [{"keyword": "rare term", "search_volume": 20, "monthly_searches": monthly}]
        )
        assert "Stable" in result


# ===================================================================
# E. Edge cases
# ===================================================================

class TestEdgeCases:
    """Edge cases for trend classification."""

    def test_empty_monthly_searches(self, flow):
        result = flow._calculate_trend_metrics([])
        assert result["trend_direction"] == "unknown"

    def test_single_month(self, flow):
        result = flow._calculate_trend_metrics([{"year": 2024, "month": 1, "search_volume": 100}])
        assert result["trend_direction"] == "unknown"

    def test_two_months_minimal(self, flow):
        """With only 2 months, both [:3] and [-3:] slices return the full list,
        so recent_avg == older_avg → stable (not enough data to differentiate)."""
        data = _make_monthly([100, 200])
        result = flow._calculate_trend_metrics(data)
        assert result["trend_direction"] == "stable"

    def test_zero_older_avg(self, flow):
        """If older months have zero volume, trend_pct should be 0 (not divide-by-zero)."""
        volumes = [0, 0, 0, 0, 0, 0, 0, 0, 0, 100, 100, 100]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        # older_avg = 0, so trend_pct = 0, and recent_avg=100 > 50, but trend_pct=0 → stable
        assert result["trend_direction"] == "stable"

    def test_format_empty_keywords(self, crew):
        assert crew._format_keyword_monthly_trends(None) == ""
        assert crew._format_keyword_monthly_trends([]) == ""

    def test_format_keyword_without_monthly_data(self, crew):
        """Keywords with no monthly_searches should just show volume, no arrow."""
        result = crew._format_keyword_monthly_trends(
            [{"keyword": "no data", "search_volume": 100, "monthly_searches": []}]
        )
        assert "no data" in result
        assert "Rising" not in result
        assert "Declining" not in result

    def test_shuffled_input_order(self, flow, crew):
        """Randomly shuffled monthly data should still classify correctly."""
        import random
        # Clearly rising: old ~100, new ~300
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 300, 300, 300]
        monthly = _make_monthly(volumes)

        rng = random.Random(42)
        shuffled = monthly.copy()
        rng.shuffle(shuffled)

        result = flow._calculate_trend_metrics(shuffled)
        assert result["trend_direction"] == "rising"

        formatted = crew._format_keyword_monthly_trends(
            [{"keyword": "shuffled", "search_volume": 200, "monthly_searches": shuffled}]
        )
        assert "Rising" in formatted


# ===================================================================
# F. Deterministic signal computation (_compute_deterministic_signals)
# ===================================================================

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


def _make_enriched(
    rising=10, stable=5, declining=5, unknown=0,
    rising_volume_pct=50, total_keywords_analyzed=20,
    seasonal_count=2, evergreen_count=8,
    market_momentum="Stable",
):
    """Build a minimal enriched_keywords_trends dict."""
    return {
        "trend_distribution": {
            "rising": rising,
            "stable": stable,
            "declining": declining,
            "unknown": unknown,
        },
        "rising_volume_pct": rising_volume_pct,
        "total_keywords_analyzed": total_keywords_analyzed,
        "seasonal_count": seasonal_count,
        "evergreen_count": evergreen_count,
        "market_momentum": market_momentum,
    }


def _make_social_content(reddit_days_ago=None, twitter_days_ago=None,
                         reddit_scores=None, twitter_likes=None, twitter_retweets=None):
    """Build a minimal SocialContentCollection with posts at given ages.

    Args:
        reddit_days_ago: List of days-ago values for Reddit posts.
        twitter_days_ago: List of days-ago values for Twitter tweets.
        reddit_scores: Optional list of scores for Reddit posts (default: 10 each).
        twitter_likes: Optional list of likes for Twitter tweets (default: 10 each).
        twitter_retweets: Optional list of retweets for Twitter tweets (default: 5 each).
    """
    from nicheiq.models.social_content import (
        SocialContentCollection, RedditPost, TwitterThread, TwitterTweet,
    )
    now = datetime.now(timezone.utc)
    reddit_posts = []
    if reddit_days_ago:
        for i, days in enumerate(reddit_days_ago):
            score = reddit_scores[i] if reddit_scores else 10
            reddit_posts.append(RedditPost(
                post_id=f"r{i}",
                title=f"Post {i}",
                selftext="text",
                author="user",
                subreddit="test",
                score=score,
                num_comments=5,
                created_utc=now - timedelta(days=days),
                url=f"https://reddit.com/r/test/{i}",
            ))

    twitter_threads = []
    if twitter_days_ago:
        for i, days in enumerate(twitter_days_ago):
            likes = twitter_likes[i] if twitter_likes else 10
            retweets = twitter_retweets[i] if twitter_retweets else 5
            tweet = TwitterTweet(
                tweet_id=f"t{i}",
                author_username="tweeter",
                text="tweet",
                likes=likes,
                retweets=retweets,
                replies_count=2,
                created_at=now - timedelta(days=days),
                url=f"https://twitter.com/{i}",
            )
            twitter_threads.append(TwitterThread(
                thread_id=f"t{i}",
                original_tweet=tweet,
                replies=[],
                total_engagement=15,
            ))

    return SocialContentCollection(
        reddit_posts=reddit_posts,
        twitter_threads=twitter_threads,
    )


def _make_competitive(intensities=None, competitor_counts=None, gap_counts=None):
    """Build a minimal CompetitiveAnalysisResult."""
    from nicheiq.models.competitor import (
        CompetitiveAnalysisResult, CompetitiveLandscape, Competitor, CompetitorType,
    )
    landscapes = []
    if intensities:
        for i, intensity in enumerate(intensities):
            comps = [
                Competitor(
                    name=f"Comp{j}",
                    competitor_type=CompetitorType.DIRECT,
                    description="desc",
                    key_features=["f1"],
                )
                for j in range(competitor_counts[i] if competitor_counts else 3)
            ]
            landscapes.append(CompetitiveLandscape(
                solution_name=f"Sol{i}",
                competitors=comps,
                market_gaps=[f"gap{j}" for j in range(max(2, gap_counts[i] if gap_counts else 3))],
                differentiation_opportunities=["diff1"],
                competitive_intensity=intensity,
                recommended_positioning="pos",
                pricing_insights="pricing",
            ))
    elif competitor_counts:
        for i, count in enumerate(competitor_counts):
            comps = [
                Competitor(
                    name=f"Comp{j}",
                    competitor_type=CompetitorType.DIRECT,
                    description="desc",
                    key_features=["f1"],
                )
                for j in range(count)
            ]
            landscapes.append(CompetitiveLandscape(
                solution_name=f"Sol{i}",
                competitors=comps,
                market_gaps=[f"gap{j}" for j in range(max(2, gap_counts[i] if gap_counts else 3))],
                differentiation_opportunities=["diff1"],
                competitive_intensity="Medium",
                recommended_positioning="pos",
                pricing_insights="pricing",
            ))

    return CompetitiveAnalysisResult(
        solution_landscapes=landscapes,
        top_opportunities=["opp1"],
        strategic_recommendations="Strategic recommendations for market entry." * 3,
    )


from nicheiq.utils.trend_scoring import (
    compute_deterministic_signals,
    compute_momentum_score,
    compute_trend_direction,
    compute_keyword_volume_trend,
    compute_discussion_signals,
    compute_trend_confidence,
    compute_seasonal_pattern,
    compute_longevity_suggestion,
    compute_timing,
)


class TestKeywordVolumeTrend:
    """keyword_volume_trend uses rising_volume_pct (volume-weighted)."""

    def test_kw_trend_increasing(self):
        """rvp >= 45 -> Increasing."""
        enriched = _make_enriched(rising_volume_pct=50)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Increasing"

    def test_kw_trend_decreasing(self):
        """rvp <= 25 -> Decreasing."""
        enriched = _make_enriched(rising_volume_pct=20)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Decreasing"

    def test_kw_trend_stable_mid(self):
        """25 < rvp < 45 -> Stable."""
        enriched = _make_enriched(rising_volume_pct=35)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Stable"

    def test_kw_trend_no_enriched_data(self):
        result = compute_deterministic_signals(None, None, None, None)
        assert result["keyword_volume_trend"] == "Stable"


class TestMomentumScore:
    """momentum_score computed entirely from rising_volume_pct."""

    def test_momentum_high_rvp(self):
        """rvp=75 -> score in 0.80-0.95 range."""
        enriched = _make_enriched(rising_volume_pct=75)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.80 <= result["momentum_score"] <= 0.95

    def test_momentum_moderate_rvp(self):
        """rvp=60 -> score in 0.80-0.95 range (strong growth band)."""
        enriched = _make_enriched(rising_volume_pct=60)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.80 <= result["momentum_score"] <= 0.95

    def test_momentum_neutral_rvp(self):
        """rvp=45 -> score in 0.60-0.80 range (moderate growth band)."""
        enriched = _make_enriched(rising_volume_pct=45)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.60 <= result["momentum_score"] <= 0.80

    def test_momentum_low_rvp(self):
        """rvp=30 -> score in 0.40-0.60 range (neutral/stable band)."""
        enriched = _make_enriched(rising_volume_pct=30)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.40 <= result["momentum_score"] <= 0.60

    def test_momentum_declining_rvp(self):
        """rvp=10 -> score in 0.10-0.25 range (declining band)."""
        enriched = _make_enriched(rising_volume_pct=10)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.10 <= result["momentum_score"] <= 0.25

    def test_momentum_default_no_data(self):
        """No enriched data -> 0.50."""
        result = compute_deterministic_signals(None, None, None, None)
        assert result["momentum_score"] == 0.50

    def test_momentum_insufficient_keywords(self):
        """<5 known keywords -> 0.50 default."""
        enriched = _make_enriched(rising=1, stable=1, declining=1, unknown=17, rising_volume_pct=80)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["momentum_score"] == 0.50

    def test_direction_derived_from_score(self):
        """trend_direction is derived from momentum_score (no independent voting)."""
        # High rvp -> high score -> Growing
        enriched_high = _make_enriched(rising_volume_pct=75)
        result_high = compute_deterministic_signals(None, None, None, enriched_high)
        assert result_high["trend_direction"] == "Growing"
        assert result_high["momentum_score"] >= 0.60

        # Low rvp -> low score -> Declining
        enriched_low = _make_enriched(rising_volume_pct=10)
        result_low = compute_deterministic_signals(None, None, None, enriched_low)
        assert result_low["trend_direction"] == "Declining"
        assert result_low["momentum_score"] <= 0.40

        # Mid rvp -> mid score -> Stable
        enriched_mid = _make_enriched(rising_volume_pct=33)
        result_mid = compute_deterministic_signals(None, None, None, enriched_mid)
        assert result_mid["trend_direction"] == "Stable"
        assert 0.40 < result_mid["momentum_score"] < 0.60

    def test_no_reconciliation_clamping(self):
        """Score is never clamped — it reflects actual rvp regardless of
        secondary signal disagreement."""
        # High rvp with conflicting discussion signal (dated posts)
        social = _make_social_content(reddit_days_ago=[400, 500, 600])
        enriched = _make_enriched(rising_volume_pct=75)
        result = compute_deterministic_signals(None, social, None, enriched)
        # Score should still be in the 0.80-0.90 range, not clamped
        assert 0.80 <= result["momentum_score"] <= 0.90
        assert result["trend_direction"] == "Growing"
        # But confidence should be lower due to disagreement
        assert result["trend_confidence"] in ("Low", "Medium")


class TestDiscussionSignals:
    """discussion_recency and discussion_frequency_trend."""

    def test_discussion_recency_recent(self):
        """Majority <180 days → Recent."""
        social = _make_social_content(reddit_days_ago=[10, 30, 60, 90, 120])
        result = compute_deterministic_signals(None, social, None, None)
        assert result["discussion_recency"] == "Recent"
        assert result["discussion_frequency_trend"] == "Increasing"

    def test_discussion_recency_dated(self):
        """Majority >365 days → Dated."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600, 700])
        result = compute_deterministic_signals(None, social, None, None)
        assert result["discussion_recency"] == "Dated"
        assert result["discussion_frequency_trend"] == "Decreasing"

    def test_discussion_empty_posts(self):
        """No posts → Dated, Decreasing."""
        from nicheiq.models.social_content import SocialContentCollection
        empty = SocialContentCollection(reddit_posts=[], twitter_threads=[])
        result = compute_deterministic_signals(None, empty, None, None)
        assert result["discussion_recency"] == "Dated"
        assert result["discussion_frequency_trend"] == "Decreasing"

    def test_discussion_none_social(self):
        """None social_content → Dated, Decreasing."""
        result = compute_deterministic_signals(None, None, None, None)
        assert result["discussion_recency"] == "Dated"
        assert result["discussion_frequency_trend"] == "Decreasing"

    def test_discussion_includes_twitter(self):
        """Twitter threads should be counted too."""
        social = _make_social_content(twitter_days_ago=[10, 20, 30, 40, 50])
        result = compute_deterministic_signals(None, social, None, None)
        assert result["discussion_recency"] == "Recent"


class TestSeasonalPattern:
    """seasonal_pattern computation with raised thresholds."""

    def test_seasonal_strong(self):
        """>50% seasonal -> Strong Seasonal."""
        enriched = _make_enriched(seasonal_count=12, total_keywords_analyzed=20)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["seasonal_pattern"] == "Strong Seasonal"

    def test_seasonal_year_round(self):
        """<30% seasonal -> Year-Round."""
        enriched = _make_enriched(seasonal_count=4, total_keywords_analyzed=20)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["seasonal_pattern"] == "Year-Round"

    def test_seasonal_mild(self):
        """30-50% seasonal -> Mild Seasonal."""
        enriched = _make_enriched(seasonal_count=8, total_keywords_analyzed=20)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["seasonal_pattern"] == "Mild Seasonal"

    def test_seasonal_no_data(self):
        result = compute_deterministic_signals(None, None, None, None)
        assert result["seasonal_pattern"] == "Unknown"


class TestTrendConfidence:
    """trend_confidence from secondary signal agreement."""

    def test_confidence_high_all_agree(self):
        """Both secondary signals agree with direction -> High."""
        social = _make_social_content(reddit_days_ago=[10, 20, 30])  # Recent -> Growing
        # rising > declining in counts -> kw_count_signal = Growing
        # rvp=75 -> score ~0.82 -> direction = Growing
        enriched = _make_enriched(rising=15, stable=3, declining=2, rising_volume_pct=75)
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Growing"
        assert result["trend_confidence"] == "High"

    def test_confidence_medium_one_agrees(self):
        """One secondary signal agrees with direction -> Medium."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600])  # Dated -> Declining
        # But keyword counts rising > declining -> Growing (disagrees with Declining disc)
        # rvp=75 -> Growing direction
        enriched = _make_enriched(rising=15, stable=3, declining=2, rising_volume_pct=75)
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Growing"
        assert result["trend_confidence"] == "Medium"  # kw agrees, disc disagrees

    def test_confidence_low_none_agree(self):
        """Neither secondary signal agrees with direction -> Low."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600])  # Dated -> Declining
        # keyword counts: declining > rising -> Declining
        # But rvp=33 -> Stable direction (neither agrees with Stable)
        enriched = _make_enriched(rising=2, stable=3, declining=15, rising_volume_pct=33)
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Stable"
        assert result["trend_confidence"] == "Low"

    def test_confidence_low_insufficient_data(self):
        """<5 known keywords -> always Low."""
        enriched = _make_enriched(rising=1, stable=1, declining=1, unknown=17)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_confidence"] == "Low"


class TestLongevityVerdictSuggestion:
    """suggested_longevity_verdict computation (no more Fad)."""

    def test_verdict_sustainable(self):
        """>50% evergreen + not declining -> Sustainable."""
        enriched = _make_enriched(
            rising=10, stable=5, declining=5,
            evergreen_count=15, total_keywords_analyzed=20,
            market_momentum="Growing",
        )
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Sustainable"

    def test_verdict_risky_high_decline(self):
        """>60% declining -> Risky (never Fad)."""
        enriched = _make_enriched(rising=2, stable=2, declining=80)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Risky"

    def test_verdict_risky_moderate_decline(self):
        """>60% declining + low rising -> Risky."""
        enriched = _make_enriched(rising=10, stable=28, declining=62)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Risky"

    def test_verdict_undetermined(self):
        """Ambiguous data -> Undetermined."""
        enriched = _make_enriched(rising=30, stable=30, declining=30, evergreen_count=5)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Undetermined"

    def test_verdict_undetermined_no_data(self):
        result = compute_deterministic_signals(None, None, None, None)
        assert result["suggested_longevity_verdict"] == "Undetermined"

    def test_never_suggests_fad(self):
        """Python never suggests Fad — that requires temporal LLM judgment."""
        # Even with extreme decline, should be Risky not Fad
        enriched = _make_enriched(rising=0, stable=0, declining=100)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] != "Fad"


class TestTiming:
    """compute_timing standalone function."""

    def test_timing_enter_now(self):
        assert compute_timing("Growing", "Sustainable", 0.75) == "Enter Now"

    def test_timing_risky_override(self):
        """Risky verdict → always Monitor & Wait regardless of momentum."""
        assert compute_timing("Growing", "Risky", 0.80) == "Monitor & Wait"

    def test_timing_fad_override(self):
        """Fad verdict → always Missed Window."""
        assert compute_timing("Growing", "Fad", 0.80) == "Missed Window"

    def test_timing_missed_window(self):
        """Declining + low momentum → Missed Window."""
        assert compute_timing("Declining", "Sustainable", 0.30) == "Missed Window"

    def test_timing_monitor_moderate(self):
        """Growing but momentum < 0.7 → Monitor & Wait."""
        assert compute_timing("Growing", "Sustainable", 0.65) == "Monitor & Wait"


# ===================================================================
# G. Momentum score mathematical properties
# ===================================================================

class TestMomentumScoreMathProperties:
    """Verify mathematical properties of the momentum scoring function.

    Grounded in financial momentum scoring practice:
    - Monotonicity: higher rvp must always produce higher score (like ROC)
    - Continuity: no jumps at band boundaries (unlike discrete buckets)
    - Winsorization: extreme values are capped (like MSCI ±3 z-score)
    - Range: output is always in [0.10, 0.95] (bounded like normalized scores)
    """

    def test_monotonicity_across_full_range(self):
        """Higher rvp must always produce higher or equal momentum_score.
        This ensures the scoring function has no inversions."""
        prev_score = 0.0
        for rvp in range(0, 101, 5):
            enriched = _make_enriched(rising_volume_pct=rvp)
            result = compute_deterministic_signals(None, None, None, enriched)
            assert result["momentum_score"] >= prev_score, (
                f"Monotonicity violated: rvp={rvp} gave score={result['momentum_score']}, "
                f"but rvp={rvp-5} gave score={prev_score}"
            )
            prev_score = result["momentum_score"]

    def test_continuity_at_band_boundaries(self):
        """Score should not jump more than 0.05 at band boundaries.
        Boundary points: rvp=15, 25, 40, 55."""
        boundaries = [15, 25, 40, 55]
        for boundary in boundaries:
            enriched_below = _make_enriched(rising_volume_pct=boundary - 1)
            enriched_at = _make_enriched(rising_volume_pct=boundary)
            result_below = compute_deterministic_signals(None, None, None, enriched_below)
            result_at = compute_deterministic_signals(None, None, None, enriched_at)
            gap = abs(result_at["momentum_score"] - result_below["momentum_score"])
            assert gap <= 0.05, (
                f"Discontinuity at rvp={boundary}: "
                f"score({boundary-1})={result_below['momentum_score']}, "
                f"score({boundary})={result_at['momentum_score']}, gap={gap}"
            )

    def test_winsorization_floor(self):
        """Score never goes below 0.10 (analogous to MSCI z-score floor)."""
        enriched = _make_enriched(rising_volume_pct=0)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["momentum_score"] >= 0.10

    def test_winsorization_ceiling(self):
        """Score never exceeds 0.95 (analogous to MSCI z-score cap)."""
        enriched = _make_enriched(rising_volume_pct=100)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["momentum_score"] <= 0.95

    def test_score_range_always_valid(self):
        """Score is always in [0.10, 0.95] for any valid rvp input."""
        for rvp in range(0, 101):
            enriched = _make_enriched(rising_volume_pct=rvp)
            result = compute_deterministic_signals(None, None, None, enriched)
            assert 0.10 <= result["momentum_score"] <= 0.95, (
                f"Score out of range for rvp={rvp}: {result['momentum_score']}"
            )

    def test_neutral_point(self):
        """rvp=33 should produce ~0.50, the midpoint of the scoring range.
        This is the 'fair value' — neither bullish nor bearish signal."""
        enriched = _make_enriched(rising_volume_pct=33)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert 0.45 <= result["momentum_score"] <= 0.55, (
            f"Neutral point (rvp=33) should be ~0.50, got {result['momentum_score']}"
        )


# ===================================================================
# H. Boundary conditions
# ===================================================================

class TestBoundaryConditions:
    """Test exact boundary values for all threshold-based classifications."""

    # ── keyword_volume_trend boundaries ──
    def test_kw_trend_boundary_at_45(self):
        """rvp=45 is the boundary for Increasing."""
        enriched = _make_enriched(rising_volume_pct=45)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Increasing"

    def test_kw_trend_boundary_at_44(self):
        """rvp=44 should be Stable (just below Increasing threshold)."""
        enriched = _make_enriched(rising_volume_pct=44)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Stable"

    def test_kw_trend_boundary_at_25(self):
        """rvp=25 is the boundary for Decreasing."""
        enriched = _make_enriched(rising_volume_pct=25)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Decreasing"

    def test_kw_trend_boundary_at_26(self):
        """rvp=26 should be Stable (just above Decreasing threshold)."""
        enriched = _make_enriched(rising_volume_pct=26)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["keyword_volume_trend"] == "Stable"

    # ── trend_direction boundaries (derived from score) ──
    def test_direction_growing_boundary(self):
        """rvp=40 maps to score 0.60 -> Growing."""
        enriched = _make_enriched(rising_volume_pct=40)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Growing"
        assert result["momentum_score"] >= 0.60

    def test_direction_stable_upper(self):
        """rvp=39 maps to score ~0.59 -> Stable (just below Growing threshold of 0.60)."""
        enriched = _make_enriched(rising_volume_pct=39)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Stable"

    def test_direction_declining_boundary(self):
        """rvp=25 maps to score 0.40 -> Declining."""
        enriched = _make_enriched(rising_volume_pct=25)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Declining"
        assert result["momentum_score"] <= 0.40

    def test_direction_stable_lower(self):
        """rvp=26 maps to score ~0.41 -> Stable (just above Declining threshold)."""
        enriched = _make_enriched(rising_volume_pct=26)
        result = compute_deterministic_signals(None, None, None, enriched)
        # At rvp=26, score = 0.40 + (26-25)/15 * 0.20 = 0.41 -> Stable
        assert result["momentum_score"] > 0.40

    # ── seasonal boundaries ──
    def test_seasonal_boundary_at_50(self):
        """Exactly 50% seasonal -> Mild Seasonal (>50% needed for Strong)."""
        enriched = _make_enriched(seasonal_count=10, total_keywords_analyzed=20)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["seasonal_pattern"] == "Mild Seasonal"  # >50% needed, 50% is not >50%

    def test_seasonal_boundary_at_51(self):
        """51% seasonal -> Strong Seasonal."""
        enriched = _make_enriched(seasonal_count=51, total_keywords_analyzed=100)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["seasonal_pattern"] == "Strong Seasonal"

    # ── longevity verdict boundary ──
    def test_verdict_boundary_at_60(self):
        """Exactly 60% declining is not >60%, should be Undetermined."""
        enriched = _make_enriched(rising=20, stable=20, declining=60, evergreen_count=5)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Undetermined"

    def test_verdict_boundary_at_61(self):
        """61% declining -> Risky."""
        enriched = _make_enriched(rising=19, stable=20, declining=61, evergreen_count=5)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["suggested_longevity_verdict"] == "Risky"

    # ── known keywords threshold ──
    def test_known_exactly_5(self):
        """Exactly 5 known keywords should use real computation, not default."""
        enriched = _make_enriched(rising=3, stable=1, declining=1, unknown=15, rising_volume_pct=75)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["momentum_score"] != 0.50  # Should use real computation

    def test_known_exactly_4(self):
        """Exactly 4 known keywords should fall back to default 0.50."""
        enriched = _make_enriched(rising=2, stable=1, declining=1, unknown=16, rising_volume_pct=75)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["momentum_score"] == 0.50  # Insufficient data


# ===================================================================
# I. Score-direction consistency (Pydantic validator guarantee)
# ===================================================================

class TestScoreDirectionConsistency:
    """Verify that momentum_score and trend_direction are ALWAYS consistent.

    The Pydantic validator requires:
    - Growing -> score >= 0.6
    - Declining -> score <= 0.4

    Our score-first architecture guarantees this by construction.
    These tests verify the guarantee across many rvp values.
    """

    @pytest.mark.parametrize("rvp", list(range(0, 101, 3)))
    def test_score_direction_always_consistent(self, rvp):
        """For any rvp value, score and direction must satisfy Pydantic constraints."""
        enriched = _make_enriched(rising_volume_pct=rvp)
        result = compute_deterministic_signals(None, None, None, enriched)
        score = result["momentum_score"]
        direction = result["trend_direction"]

        if direction == "Growing":
            assert score >= 0.60, f"Growing but score={score} < 0.6 (rvp={rvp})"
        elif direction == "Declining":
            assert score <= 0.40, f"Declining but score={score} > 0.4 (rvp={rvp})"
        else:
            assert 0.40 < score < 0.60, f"Stable but score={score} outside (0.4, 0.6) (rvp={rvp})"


# ===================================================================
# J. Real-world scenarios
# ===================================================================

class TestRealWorldScenarios:
    """Test with realistic niche profiles to verify outputs make real-world sense.

    Each scenario is a plausible niche configuration. We verify that
    the computed signals match what a human analyst would expect.
    """

    def test_booming_saas_niche(self):
        """Growing SaaS niche: high rvp, recent discussions, many competitors.
        Example: 'AI writing tools' in early 2024."""
        social = _make_social_content(
            reddit_days_ago=[5, 15, 30, 45, 60, 90, 120],
            twitter_days_ago=[10, 20, 40],
        )
        enriched = _make_enriched(
            rising=45, stable=30, declining=10, unknown=15,
            rising_volume_pct=72,
            total_keywords_analyzed=100,
            seasonal_count=10,
            evergreen_count=55,
            market_momentum="Growing",
        )
        result = compute_deterministic_signals(None, social, None, enriched)

        assert result["trend_direction"] == "Growing"
        assert result["momentum_score"] >= 0.80
        assert result["keyword_volume_trend"] == "Increasing"
        assert result["discussion_recency"] == "Recent"
        assert result["trend_confidence"] == "High"  # Both secondaries agree
        assert result["seasonal_pattern"] == "Year-Round"
        assert result["suggested_longevity_verdict"] == "Sustainable"

    def test_dying_niche(self):
        """Declining niche: low rvp, old discussions, few competitors.
        Example: 'RSS reader software' in 2023."""
        social = _make_social_content(
            reddit_days_ago=[400, 500, 600, 700, 800],
        )
        enriched = _make_enriched(
            rising=3, stable=12, declining=70, unknown=15,
            rising_volume_pct=8,
            total_keywords_analyzed=100,
            seasonal_count=5,
            evergreen_count=10,
            market_momentum="Declining",
        )
        result = compute_deterministic_signals(None, social, None, enriched)

        assert result["trend_direction"] == "Declining"
        assert result["momentum_score"] <= 0.20
        assert result["keyword_volume_trend"] == "Decreasing"
        assert result["discussion_recency"] == "Dated"
        assert result["trend_confidence"] == "High"  # Both secondaries agree (Declining)
        assert result["suggested_longevity_verdict"] == "Risky"

    def test_stable_evergreen_niche(self):
        """Stable evergreen niche: balanced rvp, moderate discussions.
        Example: 'project management software' — always in demand."""
        social = _make_social_content(
            reddit_days_ago=[30, 90, 200, 300, 400],
        )
        enriched = _make_enriched(
            rising=20, stable=55, declining=15, unknown=10,
            rising_volume_pct=30,
            total_keywords_analyzed=100,
            seasonal_count=8,
            evergreen_count=65,
            market_momentum="Stable",
        )
        result = compute_deterministic_signals(None, social, None, enriched)

        assert result["trend_direction"] == "Stable"
        assert 0.43 <= result["momentum_score"] <= 0.53
        assert result["keyword_volume_trend"] == "Stable"
        assert result["seasonal_pattern"] == "Year-Round"
        assert result["suggested_longevity_verdict"] == "Sustainable"  # High evergreen

    def test_seasonal_niche(self):
        """Seasonal niche: moderate rvp, strong seasonality.
        Example: 'tax preparation software' — Q1 spike."""
        social = _make_social_content(
            reddit_days_ago=[60, 120, 250, 350],
        )
        enriched = _make_enriched(
            rising=15, stable=30, declining=10, unknown=5,
            rising_volume_pct=35,
            total_keywords_analyzed=60,
            seasonal_count=35,  # 58% seasonal
            evergreen_count=20,
            market_momentum="Stable",
        )
        result = compute_deterministic_signals(None, social, None, enriched)

        assert result["seasonal_pattern"] == "Strong Seasonal"
        assert result["trend_direction"] == "Stable"

    def test_emerging_niche_few_keywords(self):
        """Emerging niche with insufficient keyword data.
        Example: very new market with only 3 analyzed keywords."""
        enriched = _make_enriched(
            rising=2, stable=1, declining=0, unknown=7,
            rising_volume_pct=85,
            total_keywords_analyzed=10,
            seasonal_count=0,
            evergreen_count=3,
            market_momentum="Growing",
        )
        result = compute_deterministic_signals(None, None, None, enriched)

        # Only 3 known keywords — should use conservative defaults
        assert result["momentum_score"] == 0.50
        assert result["trend_direction"] == "Stable"
        assert result["trend_confidence"] == "Low"

    def test_conflicting_signals_niche(self):
        """Niche with conflicting signals: high volume momentum but old discussions.
        Example: niche growing in search but community has moved to newer alternatives."""
        social = _make_social_content(
            reddit_days_ago=[500, 600, 700],  # Very old discussions
        )
        enriched = _make_enriched(
            rising=35, stable=30, declining=20, unknown=15,
            rising_volume_pct=65,  # Strong volume momentum
            total_keywords_analyzed=100,
            seasonal_count=5,
            evergreen_count=50,
            market_momentum="Growing",
        )
        result = compute_deterministic_signals(None, social, None, enriched)

        # Volume says Growing, but discussions are dated
        assert result["trend_direction"] == "Growing"
        assert result["momentum_score"] >= 0.80
        # Confidence should reflect the disagreement
        assert result["trend_confidence"] in ("Low", "Medium")
        assert result["discussion_recency"] == "Dated"

    def test_no_data_at_all(self):
        """No input data at all — maximum conservatism."""
        result = compute_deterministic_signals(None, None, None, None)

        assert result["trend_direction"] == "Stable"
        assert result["momentum_score"] == 0.50
        assert result["trend_confidence"] == "Low"
        assert result["keyword_volume_trend"] == "Stable"
        assert result["discussion_recency"] == "Dated"
        assert result["discussion_frequency_trend"] == "Decreasing"
        assert result["seasonal_pattern"] == "Unknown"
        assert result["suggested_longevity_verdict"] == "Undetermined"

    def test_rvp_30_produces_stable(self):
        """rvp=30 should produce 'Stable' (was 'Declining' before recalibration — the core bug)."""
        enriched = _make_enriched(rising_volume_pct=30)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Stable"

    def test_rvp_35_produces_stable(self):
        """rvp=35 should produce 'Stable'."""
        enriched = _make_enriched(rising_volume_pct=35)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Stable"

    def test_normal_market_scenario(self):
        """Realistic RVP ~30% should produce 'Stable' with score ~0.47.
        This is the typical profile for a healthy, non-trending niche."""
        enriched = _make_enriched(rising_volume_pct=30)
        result = compute_deterministic_signals(None, None, None, enriched)
        assert result["trend_direction"] == "Stable"
        assert 0.43 <= result["momentum_score"] <= 0.53


# ===================================================================
# K. Breadth vs volume divergence
# ===================================================================

class TestBreadthVsVolumeDivergence:
    """Verify that breadth (keyword count) and volume (rvp) divergence
    correctly affects confidence without distorting the score.

    Grounded in financial market breadth analysis: a rally driven by
    a few large-caps (narrow breadth) is less reliable than one where
    many stocks participate (broad breadth).
    """

    def test_broad_rally_high_confidence(self):
        """Many keywords rising + high rvp = broad rally, High confidence."""
        social = _make_social_content(reddit_days_ago=[10, 30, 60])
        enriched = _make_enriched(
            rising=50, stable=30, declining=20,  # Breadth: rising > declining
            rising_volume_pct=70,  # Volume confirms
        )
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Growing"
        assert result["trend_confidence"] == "High"

    def test_narrow_rally_lower_confidence(self):
        """Few keywords rising but high rvp = narrow rally, lower confidence.
        A few high-volume keywords drive the growth — fragile."""
        social = _make_social_content(reddit_days_ago=[10, 30, 60])
        enriched = _make_enriched(
            rising=5, stable=30, declining=65,  # Breadth: declining > rising
            rising_volume_pct=70,  # Volume still strong (few big keywords)
        )
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Growing"  # Volume drives direction
        # But breadth says Declining, so confidence drops
        assert result["trend_confidence"] in ("Low", "Medium")

    def test_broad_decline_high_confidence(self):
        """Many keywords declining + low rvp = broad decline, High confidence."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600])
        enriched = _make_enriched(
            rising=5, stable=10, declining=85,  # Breadth: declining >> rising
            rising_volume_pct=8,  # Volume confirms decline
        )
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Declining"
        assert result["trend_confidence"] == "High"

    def test_volume_stable_but_breadth_declining(self):
        """rvp in stable range but many keywords declining.
        This could mean: a few large keywords carry the market while
        smaller keywords are dying off. Direction stays Stable (from volume)
        but confidence reflects the breadth disagreement."""
        social = _make_social_content(reddit_days_ago=[400, 500, 600])  # Dated -> Declining
        enriched = _make_enriched(
            rising=5, stable=15, declining=80,  # Breadth: strongly declining
            rising_volume_pct=33,  # Volume: stable range
        )
        result = compute_deterministic_signals(None, social, None, enriched)
        assert result["trend_direction"] == "Stable"
        # Breadth says Declining, disc says Declining -> neither agrees with Stable
        assert result["trend_confidence"] == "Low"


# ===================================================================
# L. Merge integration
# ===================================================================

class TestMergeIntegration:
    """Verify that deterministic + narrative merge into valid TrendLongevityResult."""

    def test_merge_produces_valid_result(self):
        from nicheiq.models.research_state import TrendLongevityResult, TrendNarrativeOutput

        enriched = _make_enriched(rising_volume_pct=60)
        deterministic = compute_deterministic_signals(None, None, None, enriched)

        narrative = TrendNarrativeOutput(
            market_maturity="Growth",
            longevity_verdict="Sustainable",
            longevity_rationale="Sustainable because strong keyword growth.",
            new_entrants_trend="Increasing",
            competitive_activity_level="Moderate",
            volume_growth_rate="+15% YoY",
            trend_duration="2+ years growth",
            peak_periods=None,
            community_growth_indicators=["Signal 1 - Stage 5", "Signal 2 - Stage 6", "Signal 3 - Stage 7"],
            trend_reversal_risks=["MEDIUM - Risk 1 - Stage 5", "LOW - Risk 2 - Stage 7", "LOW - Risk 3 - Stage 8.5"],
        )

        timing = compute_timing(
            deterministic["trend_direction"],
            narrative.longevity_verdict,
            deterministic["momentum_score"],
        )

        result = TrendLongevityResult(
            keyword_volume_trend=deterministic["keyword_volume_trend"],
            momentum_score=deterministic["momentum_score"],
            trend_direction=deterministic["trend_direction"],
            trend_confidence=deterministic["trend_confidence"],
            seasonal_pattern=deterministic["seasonal_pattern"],
            discussion_recency=deterministic["discussion_recency"],
            discussion_frequency_trend=deterministic["discussion_frequency_trend"],
            timing_recommendation=timing,
            analysis_timeframe=deterministic["analysis_timeframe"],
            data_sources_analyzed=deterministic["data_sources_analyzed"],
            market_maturity=narrative.market_maturity,
            longevity_verdict=narrative.longevity_verdict,
            longevity_rationale=narrative.longevity_rationale,
            new_entrants_trend=narrative.new_entrants_trend,
            competitive_activity_level=narrative.competitive_activity_level,
            volume_growth_rate=narrative.volume_growth_rate,
            trend_duration=narrative.trend_duration,
            peak_periods=narrative.peak_periods,
            community_growth_indicators=narrative.community_growth_indicators,
            trend_reversal_risks=narrative.trend_reversal_risks,
        )

        assert result.trend_direction in ("Growing", "Stable", "Declining")
        assert result.longevity_verdict == "Sustainable"

    def test_merge_passes_pydantic_validator(self):
        from nicheiq.models.research_state import TrendLongevityResult, TrendNarrativeOutput

        # Test all three directions via rvp
        for rvp, expected_dir in [(75, "Growing"), (33, "Stable"), (10, "Declining")]:
            enriched = _make_enriched(rising_volume_pct=rvp)
            deterministic = compute_deterministic_signals(None, None, None, enriched)
            assert deterministic["trend_direction"] == expected_dir

            narrative = TrendNarrativeOutput(
                market_maturity="Growth",
                longevity_verdict="Sustainable",
                longevity_rationale="Test rationale.",
                new_entrants_trend="Stable",
                competitive_activity_level="Moderate",
                community_growth_indicators=["s1", "s2", "s3"],
                trend_reversal_risks=["r1", "r2", "r3"],
            )

            timing = compute_timing(
                deterministic["trend_direction"],
                narrative.longevity_verdict,
                deterministic["momentum_score"],
            )

            # This will raise ValueError if validate_consistency fails
            result = TrendLongevityResult(
                keyword_volume_trend=deterministic["keyword_volume_trend"],
                momentum_score=deterministic["momentum_score"],
                trend_direction=deterministic["trend_direction"],
                trend_confidence=deterministic["trend_confidence"],
                seasonal_pattern=deterministic["seasonal_pattern"],
                discussion_recency=deterministic["discussion_recency"],
                discussion_frequency_trend=deterministic["discussion_frequency_trend"],
                timing_recommendation=timing,
                analysis_timeframe=deterministic["analysis_timeframe"],
                data_sources_analyzed=deterministic["data_sources_analyzed"],
                market_maturity=narrative.market_maturity,
                longevity_verdict=narrative.longevity_verdict,
                longevity_rationale=narrative.longevity_rationale,
                new_entrants_trend=narrative.new_entrants_trend,
                competitive_activity_level=narrative.competitive_activity_level,
                community_growth_indicators=narrative.community_growth_indicators,
                trend_reversal_risks=narrative.trend_reversal_risks,
            )

            if result.trend_direction == "Growing":
                assert result.momentum_score >= 0.6
            elif result.trend_direction == "Declining":
                assert result.momentum_score <= 0.4
