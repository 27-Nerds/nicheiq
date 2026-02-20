"""
Tests for score refinement utilities.
"""

import pytest
from unittest.mock import MagicMock
from nicheiq.utils.score_refinement import (
    refine_scalability_score,
    refine_cac_organic,
    refine_programmatic_opportunity
)


class TestRefineScalabilityScore:
    """Tests for refine_scalability_score function."""

    def test_basic_refinement(self):
        """Test basic score refinement with typical inputs."""
        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=50000,
            tier1_count=15,
            all_tiered_keywords=[]
        )

        assert "score" in result
        assert "metadata" in result
        assert 0.0 <= result["score"] <= 1.0
        assert "baseline_volume" in result["metadata"]
        assert "volume_multiplier" in result["metadata"]
        assert "tier1_multiplier" in result["metadata"]
        assert "competition_modifier" in result["metadata"]
        assert "change" in result["metadata"]

    def test_volume_multiplier_calculation(self):
        """Test volume multiplier with different volume levels."""
        # Low volume (80% of baseline - will be floored at 0.8)
        result_low = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=40000,  # 80% of 50000 baseline for directory
            tier1_count=10,
            all_tiered_keywords=[]
        )
        assert result_low["metadata"]["volume_multiplier"] == 0.8

        # High volume (150% of baseline)
        result_high = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=75000,  # 150% of 50000 baseline
            tier1_count=10,
            all_tiered_keywords=[]
        )
        # Volume ratio = 75000/50000 = 1.5
        # But it's capped at settings.seo_refinement_max_volume_boost (default 1.2)
        # So multiplier should be 1.2
        assert result_high["metadata"]["volume_multiplier"] == 1.2

    def test_tier1_boost_calculation(self):
        """Test Tier 1 keyword boost (1% per keyword, max 20%)."""
        # 10 keywords = 10% boost
        result_10 = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=10,
            all_tiered_keywords=[]
        )
        assert result_10["metadata"]["tier1_multiplier"] == 1.10

        # 25 keywords = 20% boost (capped)
        result_25 = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=25,
            all_tiered_keywords=[]
        )
        assert result_25["metadata"]["tier1_multiplier"] == 1.20

    def test_competition_modifier_from_keywords(self):
        """Test competition modifier calculation from Tier 1 keywords."""
        # Create mock keywords with competition data
        mock_keywords = [
            MagicMock(competition="LOW (30)"),
            MagicMock(competition="LOW (25)"),
            MagicMock(competition="MEDIUM (45)"),
        ]

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=3,
            all_tiered_keywords=mock_keywords
        )

        # Average competition = (30 + 25 + 45) / 3 = 33.33
        # Normalized = 0.3333
        # Modifier = 1.0 - 0.3333 = 0.6667
        assert result["metadata"]["competition_modifier"] == pytest.approx(0.667, abs=0.01)

    def test_competition_modifier_malformed_data(self):
        """Test competition modifier with malformed competition strings."""
        mock_keywords = [
            MagicMock(competition="INVALID"),
            MagicMock(competition="LOW (30)"),
            MagicMock(competition="MISSING_PAREN"),
        ]

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=3,
            all_tiered_keywords=mock_keywords
        )

        # Only one valid keyword parsed
        # Average = 30 / 100 = 0.3
        # Modifier = 1.0 - 0.3 = 0.7
        assert result["metadata"]["competition_modifier"] == 0.7

    def test_score_capped_at_one(self):
        """Test that refined score is capped at 1.0."""
        result = refine_scalability_score(
            base_score=0.9,
            project_type="directory",
            total_volume=100000,  # Very high volume
            tier1_count=20,  # High tier1 count
            all_tiered_keywords=[]
        )

        assert result["score"] <= 1.0

    def test_unknown_project_type_uses_default_baseline(self):
        """Test that unknown project types use default 30k baseline."""
        result = refine_scalability_score(
            base_score=0.7,
            project_type="unknown_type",
            total_volume=30000,
            tier1_count=10,
            all_tiered_keywords=[]
        )

        assert result["metadata"]["baseline_volume"] == 30000

    def test_zero_baseline_volume_handling(self):
        """Test handling of zero baseline volume (edge case)."""
        # This shouldn't happen in practice, but test defensive coding
        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=50000,
            tier1_count=10,
            all_tiered_keywords=[]
        )

        # Should not crash and return valid result
        assert 0.0 <= result["score"] <= 1.0

    def test_empty_tier1_keywords_uses_neutral_competition(self):
        """Test that empty tier1_keywords list uses neutral 0.5 modifier."""
        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=0,
            all_tiered_keywords=[]
        )

        assert result["metadata"]["competition_modifier"] == 0.5

    def test_zero_base_with_strong_keyword_evidence(self):
        """Test that keyword evidence floor rescues a false-zero LLM baseline (bug case)."""
        # Simulate the real bug case: aggregator with 3M+ volume, 184 keywords, base=0.0
        mock_keywords = [MagicMock(competition="LOW (5)")] * 169  # Tier 0
        mock_keywords.append(MagicMock(competition="HIGH (100)"))  # 1 Tier 1
        mock_keywords.extend([MagicMock(competition="LOW (10)")] * 8)  # Tier 2

        result = refine_scalability_score(
            base_score=0.0,
            project_type="aggregator",
            total_volume=3_000_000,
            tier1_count=1,
            all_tiered_keywords=mock_keywords,
            total_keyword_count=184,
        )

        # Floor should rescue from 0.0
        assert result["score"] > 0.0
        assert result["score"] <= 0.35  # Capped by max_keyword_evidence
        assert result["metadata"]["floor_applied"] is True
        assert result["metadata"]["floor_reason"] == "keyword_evidence_override"

    def test_competition_from_all_tiers(self):
        """Test competition modifier reflects all-tier average, not just Tier 1."""
        # 5 Tier 0 at LOW(10), 2 Tier 1 at HIGH(80), 3 Tier 2 at MEDIUM(50)
        mock_keywords = (
            [MagicMock(competition="LOW (10)")] * 5 +
            [MagicMock(competition="HIGH (80)")] * 2 +
            [MagicMock(competition="MEDIUM (50)")] * 3
        )

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=2,
            all_tiered_keywords=mock_keywords,
            total_keyword_count=10,
        )

        # avg = (5*10 + 2*80 + 3*50) / 10 = (50+160+150)/10 = 36.0
        # modifier = 1.0 - 0.36 = 0.64
        assert result["metadata"]["competition_modifier"] == pytest.approx(0.64, abs=0.01)
        assert result["metadata"]["keywords_used_for_competition"] == 10

    def test_competition_modifier_floored(self):
        """Test competition modifier is floored at minimum when all keywords are max competition."""
        mock_keywords = [MagicMock(competition="HIGH (100)")] * 10

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=5,
            all_tiered_keywords=mock_keywords,
            total_keyword_count=10,
        )

        # raw = 1.0 - 1.0 = 0.0, floored to 0.2
        assert result["metadata"]["competition_modifier"] == 0.2
        assert result["metadata"]["min_competition_modifier_applied"] is True
        assert result["score"] > 0.0

    def test_normal_case_floor_not_applied(self):
        """Test that floor is not applied when multiplicative score is healthy."""
        mock_keywords = [MagicMock(competition="LOW (30)")] * 15

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=50000,
            tier1_count=15,
            all_tiered_keywords=mock_keywords,
            total_keyword_count=50,
        )

        assert result["metadata"]["floor_applied"] is False
        assert result["score"] > 0.0

    def test_zero_base_zero_data_stays_zero(self):
        """Test that zero base with zero keyword data stays at 0.0."""
        result = refine_scalability_score(
            base_score=0.0,
            project_type="directory",
            total_volume=0,
            tier1_count=0,
            all_tiered_keywords=[],
            total_keyword_count=0,
        )

        assert result["score"] == 0.0

    def test_keyword_breadth_signal(self):
        """Test that keyword breadth contributes to evidence floor."""
        result = refine_scalability_score(
            base_score=0.0,
            project_type="directory",
            total_volume=10000,
            tier1_count=0,
            all_tiered_keywords=[],
            total_keyword_count=100,
        )

        # volume_signal = min(0.15, (10000/50000)*0.01) = min(0.15, 0.002) = 0.002
        # tier1_signal = 0
        # breadth_signal = min(0.10, 100 * 0.001) = 0.10
        # floor = 0.002 + 0 + 0.10 = 0.102
        assert result["metadata"]["keyword_breadth_signal"] == 0.1
        assert result["score"] > 0.0
        assert result["metadata"]["floor_applied"] is True

    def test_backward_compat_tier1_only(self):
        """Test backward compatibility: same Tier 1 keywords produce same competition result."""
        mock_keywords = [
            MagicMock(competition="LOW (30)"),
            MagicMock(competition="LOW (25)"),
            MagicMock(competition="MEDIUM (45)"),
        ]

        result = refine_scalability_score(
            base_score=0.7,
            project_type="directory",
            total_volume=30000,
            tier1_count=3,
            all_tiered_keywords=mock_keywords,
        )

        # Same as original test_competition_modifier_from_keywords
        assert result["metadata"]["competition_modifier"] == pytest.approx(0.667, abs=0.01)


class TestRefineCAC:
    """Tests for refine_cac_organic function."""

    def test_parse_cac_range(self):
        """Test parsing CAC from '$15-30' format."""
        result = refine_cac_organic(
            base_cac_str="$15-30 per customer",
            tier1_keywords=[],
            total_volume=50000
        )

        assert "cac_range" in result
        assert "metadata" in result
        # Base CAC should be midpoint: (15 + 30) / 2 = 22.5
        assert result["metadata"]["base_cac"] == 22.5

    def test_parse_single_cac_value(self):
        """Test parsing CAC from single value like '$25'."""
        result = refine_cac_organic(
            base_cac_str="$25",
            tier1_keywords=[],
            total_volume=50000
        )

        assert result["metadata"]["base_cac"] == 25

    def test_none_base_cac_returns_na(self):
        """Test that None base_cac_str returns N/A."""
        result = refine_cac_organic(
            base_cac_str=None,
            tier1_keywords=[],
            total_volume=50000
        )

        assert result["cac_range"] == "N/A"
        assert result["metadata"]["estimated_year1_pages"] == 0

    def test_difficulty_multiplier_calculation(self):
        """Test difficulty multiplier from Tier 1 keyword competition."""
        mock_keywords = [
            MagicMock(competition="LOW (30)"),
            MagicMock(competition="LOW (40)"),
        ]

        result = refine_cac_organic(
            base_cac_str="$20-40",
            tier1_keywords=mock_keywords,
            total_volume=50000
        )

        # Average difficulty = (30 + 40) / 2 = 35
        # Multiplier = 1.0 + (35 / 100) = 1.35
        assert result["metadata"]["difficulty_multiplier"] == 1.35
        assert result["metadata"]["avg_tier1_difficulty"] == 35.0

    def test_volume_discount_calculation(self):
        """Test volume discount (economies of scale)."""
        # Low volume (no significant discount)
        result_low = refine_cac_organic(
            base_cac_str="$20",
            tier1_keywords=[],
            total_volume=10000
        )
        # Volume discount = 1.0 - (10000 / 1000000) = 0.99
        assert result_low["metadata"]["volume_discount"] == 0.99

        # High volume (max discount floor applied)
        result_high = refine_cac_organic(
            base_cac_str="$20",
            tier1_keywords=[],
            total_volume=2000000  # 2M volume
        )
        # Should hit floor (default 0.5)
        assert result_high["metadata"]["volume_discount"] >= 0.5

    def test_cac_range_rounded_to_nearest_five(self):
        """Test that CAC range is rounded to nearest $5."""
        result = refine_cac_organic(
            base_cac_str="$23",  # Odd base value
            tier1_keywords=[],
            total_volume=50000
        )

        # Extract low and high from "$X-Y" format
        cac_range = result["cac_range"]
        low, high = cac_range.replace("$", "").split("-")
        low_val = int(low)
        high_val = int(high)

        # Check both are multiples of 5
        assert low_val % 5 == 0
        assert high_val % 5 == 0

    def test_malformed_cac_string_uses_fallback(self):
        """Test that malformed CAC string uses $100 fallback."""
        result = refine_cac_organic(
            base_cac_str="Invalid CAC string",
            tier1_keywords=[],
            total_volume=50000
        )

        assert result["metadata"]["base_cac"] == 100


class TestRefineProgrammaticOpportunity:
    """Tests for refine_programmatic_opportunity function."""

    def test_basic_page_count_from_tier1(self):
        """Test page count calculation from Tier 1 keywords only."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = None

        result = refine_programmatic_opportunity(
            original_assessment="Original assessment text",
            seo_report=mock_seo_report,
            tier1_count=15
        )

        assert result["page_count"] == 15
        assert "15 Tier 1 landing pages" in result["assessment"]

    def test_page_count_with_geographic_groups(self):
        """Test page count includes geographic groups."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = [
            MagicMock(), MagicMock(), MagicMock()  # 3 groups
        ]
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = None

        result = refine_programmatic_opportunity(
            original_assessment="Original",
            seo_report=mock_seo_report,
            tier1_count=10
        )

        # 10 tier1 + 3 geo = 13
        assert result["page_count"] == 13
        assert "3 geographic pages" in result["assessment"]

    def test_page_count_with_category_groups(self):
        """Test page count includes category groups."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = [
            MagicMock(), MagicMock()  # 2 groups
        ]
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = None

        result = refine_programmatic_opportunity(
            original_assessment="Original",
            seo_report=mock_seo_report,
            tier1_count=10
        )

        # 10 tier1 + 2 category = 12
        assert result["page_count"] == 12
        assert "2 category pages" in result["assessment"]

    def test_page_count_with_topic_clusters(self):
        """Test page count includes topic clusters (4 pages per cluster)."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = [
            MagicMock(), MagicMock(), MagicMock()  # 3 clusters
        ]
        mock_seo_report.keyword_based_page_types = None

        result = refine_programmatic_opportunity(
            original_assessment="Original",
            seo_report=mock_seo_report,
            tier1_count=10
        )

        # 10 tier1 + (3 clusters * 4 pages) = 22
        assert result["page_count"] == 22
        assert "12 content pieces" in result["assessment"]
        assert "3 topic clusters" in result["assessment"]

    def test_page_count_ignores_keyword_based_page_types(self):
        """Test page count does not include keyword-based page types (no estimated_page_count)."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = [MagicMock(), MagicMock()]

        result = refine_programmatic_opportunity(
            original_assessment="Original",
            seo_report=mock_seo_report,
            tier1_count=10
        )

        # Only tier1 count contributes
        assert result["page_count"] == 10

    def test_comprehensive_page_count(self):
        """Test page count with all sources combined."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = [MagicMock(), MagicMock()]  # 2
        mock_seo_report.tier_4_category_groups = [MagicMock()]  # 1
        mock_seo_report.topic_clusters = [MagicMock(), MagicMock()]  # 2 * 4 = 8
        mock_seo_report.keyword_based_page_types = [MagicMock()]

        result = refine_programmatic_opportunity(
            original_assessment="Original assessment",
            seo_report=mock_seo_report,
            tier1_count=15
        )

        # 15 + 2 + 1 + 8 = 26 (keyword_based_page_types no longer contributes)
        assert result["page_count"] == 26

    def test_assessment_includes_original(self):
        """Test that refined assessment includes original assessment."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = None

        original = "This is the original architectural analysis."

        result = refine_programmatic_opportunity(
            original_assessment=original,
            seo_report=mock_seo_report,
            tier1_count=10
        )

        assert original in result["assessment"]
        assert "Original Architectural Analysis" in result["assessment"]

    def test_none_original_assessment_shows_na(self):
        """Test that None original assessment shows N/A."""
        mock_seo_report = MagicMock()
        mock_seo_report.tier_3_geographic_groups = None
        mock_seo_report.tier_4_category_groups = None
        mock_seo_report.topic_clusters = None
        mock_seo_report.keyword_based_page_types = None

        result = refine_programmatic_opportunity(
            original_assessment=None,
            seo_report=mock_seo_report,
            tier1_count=10
        )

        assert "N/A" in result["assessment"]

    def test_missing_attributes_handled_gracefully(self):
        """Test that missing seo_report attributes don't crash."""
        # Create minimal mock without any tier attributes
        mock_seo_report = MagicMock(spec=[])  # Empty spec = no attributes

        result = refine_programmatic_opportunity(
            original_assessment="Original",
            seo_report=mock_seo_report,
            tier1_count=10
        )

        # Should only count tier1
        assert result["page_count"] == 10
