"""
Tests for keyword trend classification consistency.

Ensures _format_keyword_monthly_trends (crew) and _calculate_trend_metrics (flow)
produce consistent results regardless of input sort order, and that asymmetric
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
        ("moderate_rise_25pct", [100, 100, 100, 100, 100, 100, 100, 100, 100, 125, 125, 125]),
        ("moderate_decline_30pct", [200, 200, 200, 200, 200, 200, 200, 200, 200, 140, 140, 140]),
        ("borderline_rise_21pct", [100, 100, 100, 100, 100, 100, 100, 100, 100, 121, 121, 121]),
        ("borderline_decline_26pct", [200, 200, 200, 200, 200, 200, 200, 200, 200, 148, 148, 148]),
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

class TestAsymmetricThresholds:
    """Rising threshold (>20%) is lower than declining threshold (>25%).
    This means the 'stable' band is wider on the declining side."""

    def test_19pct_rise_is_stable(self, flow):
        """A 19% rise should be 'stable' (below the 20% rising threshold)."""
        # old avg = 100, recent avg = 119 → +19%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 119, 119, 119]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_21pct_rise_is_rising(self, flow):
        """A 21% rise should be 'rising' (above the 20% threshold)."""
        # old avg = 100, recent avg = 121 → +21%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 121, 121, 121]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "rising"

    def test_24pct_decline_is_stable(self, flow):
        """A 24% decline should still be 'stable' (inside the -25% threshold)."""
        # old avg = 200, recent avg = 152 → -24%
        volumes = [200, 200, 200, 200, 200, 200, 200, 200, 200, 152, 152, 152]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable"

    def test_26pct_decline_is_declining(self, flow):
        """A 26% decline should be 'declining' (beyond the -25% threshold)."""
        # old avg = 200, recent avg = 148 → -26%
        volumes = [200, 200, 200, 200, 200, 200, 200, 200, 200, 148, 148, 148]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "declining"

    def test_asymmetry_prevents_false_declining(self, flow):
        """A moderate drop (-20%) that would have been 'declining' under the old
        symmetric ±15% threshold is now 'stable'."""
        # old avg = 100, recent avg = 80 → -20%
        volumes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 80, 80, 80]
        result = flow._calculate_trend_metrics(_make_monthly(volumes))
        assert result["trend_direction"] == "stable", (
            "A -20% change should be stable under asymmetric thresholds"
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
