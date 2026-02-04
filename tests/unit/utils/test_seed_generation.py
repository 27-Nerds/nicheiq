"""
Unit tests for SeedGenerator.calculate_validation_from_expansion().

Tests the pure-computation method that derives validation metrics
from already-expanded keywords without making any API calls.
"""

import pytest
from unittest.mock import MagicMock, patch

from nicheiq.utils.seed_generation import SeedGenerator


def _make_generator() -> SeedGenerator:
    """Create a SeedGenerator with a mocked state (no real ResearchState needed)."""
    state = MagicMock()
    state.niche_context = None
    state.pain_point_analysis = None
    return SeedGenerator(state=state)


def _kw(keyword: str, volume: int, competition: int = 30) -> dict:
    """Shorthand factory for a keyword dict matching DataForSEO shape."""
    return {"keyword": keyword, "search_volume": volume, "competition_index": competition}


class TestCalculateValidationFromExpansion:
    """Tests for calculate_validation_from_expansion()."""

    # ── 1. Empty input ─────────────────────────────────────────────

    def test_empty_keywords_returns_fallback(self):
        """Empty expanded_keywords should return the fallback dict."""
        gen = _make_generator()
        result = gen.calculate_validation_from_expansion(
            expanded_keywords=[],
            solution_name="TestSolution",
            original_seed_count=5,
        )

        assert result["validated_count"] == 0
        assert result["total_volume"] == 0
        assert result["keyword_demand_score"] == 0.0
        assert result["demand_signal"] == "weak"
        assert result["top_keywords"] == []
        assert result["top_geographic_keywords"] == []
        assert result["solution_name"] == "TestSolution"
        assert result["validation_signals"]["has_search_demand"] is False

    # ── 2. Basic metrics ───────────────────────────────────────────

    def test_basic_metrics(self):
        """Verify validated_count, total_volume, avg_competition, demand_signal."""
        gen = _make_generator()
        keywords = [
            _kw("remote work tools", 500, 40),
            _kw("best remote software", 200, 50),
            _kw("team collaboration app", 100, 60),
        ]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="RemoteHub",
            original_seed_count=5,
        )

        assert result["validated_count"] == 3
        assert result["total_volume"] == 800
        assert result["avg_competition"] == pytest.approx(50.0)
        # total_volume 800 < 2000 → weak
        assert result["demand_signal"] == "weak"

    # ── 3. keyword_demand_score capped at 1.0 ─────────────────────

    def test_volume_score_capped_at_one(self):
        """keyword_demand_score must never exceed 1.0 (guards le=1.0 constraint)."""
        gen = _make_generator()
        # 10 valid keywords but only 3 original seeds → ratio 10/3 > 1
        keywords = [_kw(f"keyword {i}", 200, 30) for i in range(10)]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="OverflowTest",
            original_seed_count=3,
        )

        assert result["keyword_demand_score"] <= 1.0

    # ── 4. Output structure matches validate_seeds_with_dataforseo ─

    def test_output_structure_matches_validate_seeds(self):
        """Returned dict must have the same keys as the fallback/empty result."""
        gen = _make_generator()
        expected_keys = {
            "solution_name",
            "validated_count",
            "total_volume",
            "avg_competition",
            "keyword_demand_score",
            "top_keywords",
            "top_geographic_keywords",
            "demand_signal",
            "validation_signals",
        }

        # Non-empty path
        keywords = [_kw("test keyword phrase", 300, 40)]
        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="StructTest",
            original_seed_count=5,
        )
        assert set(result.keys()) == expected_keys

        # Empty path
        empty_result = gen.calculate_validation_from_expansion(
            expanded_keywords=[],
            solution_name="StructTest",
            original_seed_count=5,
        )
        assert set(empty_result.keys()) == expected_keys

        # validation_signals sub-keys should match too
        expected_signal_keys = {
            "has_search_demand",
            "keyword_diversity",
            "high_volume_presence",
            "average_volume_per_keyword",
        }
        assert set(result["validation_signals"].keys()) == expected_signal_keys
        assert set(empty_result["validation_signals"].keys()) == expected_signal_keys

    # ── 5. Filters low-volume keywords ─────────────────────────────

    @patch("nicheiq.utils.seed_generation.settings")
    def test_filters_low_volume_keywords(self, mock_settings):
        """Keywords below keyword_min_search_volume should not count."""
        mock_settings.keyword_min_search_volume = 50

        gen = _make_generator()
        keywords = [
            _kw("high volume phrase", 500, 30),
            _kw("medium volume term", 100, 40),
            _kw("low volume junk", 10, 20),     # below 50
            _kw("zero volume trash", 0, 10),     # below 50
        ]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="FilterTest",
            original_seed_count=10,
        )

        # Only the first two should survive the min-volume filter
        assert result["validated_count"] == 2
        assert result["total_volume"] == 600

    # ── 6. Demand signal thresholds ────────────────────────────────

    @pytest.mark.parametrize(
        "volumes,expected_signal",
        [
            # total > 5000 → strong
            ([2000, 2000, 1500], "strong"),
            # total > 2000 but ≤ 5000 → moderate
            ([1000, 800, 500], "moderate"),
            # total ≤ 2000 → weak
            ([500, 300, 100], "weak"),
        ],
        ids=["strong", "moderate", "weak"],
    )
    def test_demand_signal_thresholds(self, volumes, expected_signal):
        """Demand signal should reflect total_volume thresholds."""
        gen = _make_generator()
        keywords = [_kw(f"keyword phrase {i}", v, 30) for i, v in enumerate(volumes)]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="DemandTest",
            original_seed_count=10,
        )

        assert result["demand_signal"] == expected_signal

    # ── 7. Geographic keywords detected ────────────────────────────

    def test_geo_keywords_detected(self):
        """Keywords containing geo terms should appear in top_geographic_keywords."""
        gen = _make_generator()
        keywords = [
            _kw("remote jobs spain", 500, 30),
            _kw("uk freelance platforms", 400, 40),
            _kw("best project tools", 300, 20),   # no geo
            _kw("canada work permits", 200, 50),
        ]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="GeoTest",
            original_seed_count=10,
        )

        geo = result["top_geographic_keywords"]
        assert len(geo) >= 2
        # Should contain the geo-bearing keywords (sorted by volume desc, capped at 3)
        assert any("spain" in kw.lower() for kw in geo)
        assert any("uk" in kw.lower() for kw in geo)

    # ── 8. Top keywords sorted descending & capped at 5 ───────────

    def test_top_keywords_sorted_by_volume(self):
        """top_keywords should be sorted by volume descending and limited to 5."""
        gen = _make_generator()
        keywords = [_kw(f"keyword phrase {i}", v, 30) for i, v in enumerate(
            [100, 900, 300, 700, 500, 200, 800, 400]
        )]

        result = gen.calculate_validation_from_expansion(
            expanded_keywords=keywords,
            solution_name="SortTest",
            original_seed_count=10,
        )

        top = result["top_keywords"]
        assert len(top) <= 5
        volumes = [kw["volume"] for kw in top]
        assert volumes == sorted(volumes, reverse=True)
        # Highest expected is 900
        assert top[0]["volume"] == 900
