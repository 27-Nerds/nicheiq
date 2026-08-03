"""Tests for the LTV:CAC grounding validator.

Regression suite for the 2026-08 Sev-1 (job 8ef396eb): the report published
"7.2:1 to 18:1 (LTV $324 - $810 ÷ CAC $45)" directly above a CAC table reading
Organic N/A / Paid N/A, and a rationale claiming the ratio "exceeds the mandatory
2:1 threshold". The $45 came from the market-fit benchmark band, not from the idea.
"""

import json
from pathlib import Path

import pytest

from nicheiq.validators.unit_economics import (
    NOT_COMPUTABLE,
    apply_ltv_cac_grounding,
    declares_not_computable,
    has_numeric_ratio,
    validate_ltv_cac_grounding,
)

# The stored record the defect was found in. Kept as the oracle: a synthetic fixture
# can be shaped to pass, this one cannot.
LIVE_REPORT = Path(__file__).resolve().parents[3] / (
    "output/jobs/8ef396eb-c63d-4641-889e-1db6dfc9dfde/report.json"
)


def _check(ratio, organic=None, paid=None, name="TestIdea"):
    return validate_ltv_cac_grounding(
        solution_name=name,
        ltv_to_cac_ratio=ratio,
        estimated_cac_organic=organic,
        estimated_cac_paid=paid,
    )


class TestAbsentCac:
    """No CAC published -> no ratio may be published."""

    @pytest.mark.parametrize(
        "organic,paid",
        [
            ("N/A", None),          # the live 8ef396eb shape
            (None, None),
            ("", ""),
            ("n/a", "N/A"),
            ("Not established", "unknown"),
            ("Requires technical analysis", None),  # prose with no dollar figure
        ],
    )
    def test_numeric_ratio_is_cleared(self, organic, paid):
        result = _check("7.2:1 to 18:1 (LTV $324 - $810 ÷ CAC $45)", organic, paid)
        assert result.status == "cleared_ungrounded"
        assert result.ratio == NOT_COMPUTABLE
        assert "$45" not in result.ratio
        assert result.changed

    def test_ratio_without_a_cited_cac_is_also_cleared(self):
        """The defect is the missing input, not the missing citation."""
        result = _check("12:1", "N/A", None)
        assert result.status == "cleared_ungrounded"
        assert result.ratio == NOT_COMPUTABLE

    def test_degradation_is_recorded_and_names_the_solution(self):
        result = _check("12:1", "N/A", None, name="HouseNutIndex")
        assert result.degradation
        assert "HouseNutIndex" in result.degradation
        assert "estimated_cac_organic" in result.degradation

    def test_rationale_note_disowns_the_threshold_claim(self):
        """Clearing the number while the prose still argues it is a new contradiction."""
        result = _check("12:1", "N/A", None)
        assert result.rationale_note
        assert "threshold" in result.rationale_note

    def test_already_not_computable_is_untouched(self):
        result = _check(NOT_COMPUTABLE, "N/A", None)
        assert result.status == "not_applicable"
        assert result.ratio == NOT_COMPUTABLE
        assert not result.changed

    def test_ad_model_na_string_is_untouched(self):
        """Ad/affiliate models legitimately state N/A prose here."""
        result = _check("N/A - SEO-driven traffic acquisition", None, None)
        assert result.status == "not_applicable"
        assert not result.changed

    def test_percentage_in_na_prose_is_not_read_as_a_ratio(self):
        """parse_ratio's bare-number fallback would read this as 100:1."""
        result = _check("N/A - 100% organic traffic model", None, None)
        assert result.status == "not_applicable"


class TestMismatchedCac:
    """CAC published, but the ratio divides by a different one."""

    def test_cited_cac_outside_published_bands_is_flagged(self):
        result = _check(
            "15:1 (LTV $675 ÷ CAC $45)",
            organic="$120-200 per customer (niche SEO pages)",
            paid="$300-500 per customer",
        )
        assert result.status == "flagged_mismatch"
        assert result.changed
        assert "unverified" in result.ratio
        # The published numeral survives verbatim — flagged, not rewritten.
        assert result.ratio.startswith("15:1 (LTV $675 ÷ CAC $45)")
        assert "$120-$200" in result.ratio or "$120" in result.ratio
        assert result.degradation and "does not match" in result.degradation

    def test_matching_cac_passes(self):
        result = _check(
            "15:1 (LTV $675 ÷ CAC $45)",
            organic="$30-50 per customer (high-intent guides)",
            paid="$150-300 per customer",
        )
        assert result.status == "ok"
        assert not result.changed
        assert result.ratio == "15:1 (LTV $675 ÷ CAC $45)"

    def test_cac_matching_the_paid_band_passes(self):
        result = _check(
            "3:1 (LTV $600 ÷ CAC $200)",
            organic="$30-50 per customer",
            paid="$150-300 per customer",
        )
        assert result.status == "ok"

    def test_rounding_at_a_band_edge_is_not_flagged(self):
        """$52 against a $15-50 band is rounding, not fabrication."""
        result = _check("13:1 (LTV $676 ÷ CAC $52)", organic="$15-50 per customer")
        assert result.status == "ok"

    def test_cited_cac_range_overlapping_the_band_passes(self):
        result = _check(
            "9:1 to 18:1 (LTV $324 - $810 ÷ CAC $35-45)",
            organic="$40-90 per customer",
        )
        assert result.status == "ok"

    def test_prose_numbers_in_the_cac_field_are_not_read_as_money(self):
        """'30+ pages' must not become a $30 CAC band."""
        result = _check(
            "15:1 (LTV $675 ÷ CAC $45)",
            organic="$120-200 per customer (programmatic content via 30+ pages)",
        )
        assert result.status == "flagged_mismatch"

    def test_ratio_with_no_cited_cac_is_left_alone_when_cac_exists(self):
        """Nothing to contradict; the validator does not invent a violation."""
        result = _check("8:1", organic="$30-50 per customer")
        assert result.status == "ok"
        assert not result.changed


class TestFailingRatioIsPreserved:
    """A failing ratio is a finding. The validator is downgrade-only."""

    @pytest.mark.parametrize("ratio", ["1.4:1 (LTV $63 ÷ CAC $45)", "0.8:1", "1.9x"])
    def test_below_floor_ratio_is_never_coerced_upward(self, ratio):
        result = _check(ratio, organic="$40-50 per customer")
        assert result.status == "ok"
        assert result.ratio == ratio
        assert not result.changed
        assert result.degradation is None

    def test_below_floor_and_mismatched_is_flagged_but_not_raised(self):
        result = _check(
            "1.4:1 (LTV $63 ÷ CAC $45)", organic="$300-500 per customer"
        )
        assert result.status == "flagged_mismatch"
        assert result.ratio.startswith("1.4:1 (LTV $63 ÷ CAC $45)")
        # Downgrade-only: no larger ratio appears anywhere in the output.
        assert "2:1" not in result.ratio

    def test_below_floor_with_absent_cac_is_cleared_not_raised(self):
        result = _check("1.4:1 (LTV $63 ÷ CAC $45)", "N/A", None)
        assert result.ratio == NOT_COMPUTABLE


class TestHelpers:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("3:1", True),
            ("7.2:1 to 18:1 (LTV $324 ÷ CAC $45)", True),
            ("18x", True),
            ("N/A - 100% organic traffic model", False),
            ("Not computable", False),
            ("healthy", False),
            (None, False),
        ],
    )
    def test_has_numeric_ratio(self, text, expected):
        assert has_numeric_ratio(text) is expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("N/A - SEO-driven traffic acquisition", True),
            (NOT_COMPUTABLE, True),
            ("Cannot be computed without a CAC", True),
            ("healthy", False),
            ("3:1", False),
        ],
    )
    def test_declares_not_computable(self, text, expected):
        assert declares_not_computable(text) is expected


@pytest.mark.skipif(
    not LIVE_REPORT.exists(), reason="stored 8ef396eb report not present in this checkout"
)
class TestAgainstStoredLiveReport:
    """The oracle: run the validator over the exact record the Sev-1 was found in."""

    @pytest.fixture(scope="class")
    def report(self):
        return json.loads(LIVE_REPORT.read_text())

    def test_the_stored_record_still_exhibits_the_defect(self, report):
        """Guards the test itself: if this record ever stops being the bad case,
        every assertion below is vacuous and must be re-pointed."""
        details = report["selected_solution_details"]
        assert report["pricing_strategy"]["ltv_to_cac_ratio"] == (
            "7.2:1 to 18:1 (LTV $324 - $810 ÷ CAC $45)"
        )
        assert details["estimated_cac_organic"] == "N/A"
        assert details["estimated_cac_paid"] is None
        assert "| Organic (SEO) | N/A |" in report["estimated_cac_breakdown"]
        # The threshold claim lives in wtp_validation, not pricing_rationale.
        assert "mandatory 2:1 threshold" in report["pricing_strategy"]["wtp_validation"]
        assert "$45 CAC assumption" in report["pricing_strategy"]["wtp_validation"]

    def test_validator_clears_the_live_ratio(self, report):
        details = report["selected_solution_details"]
        result = validate_ltv_cac_grounding(
            solution_name=report["selected_solution_name"],
            ltv_to_cac_ratio=report["pricing_strategy"]["ltv_to_cac_ratio"],
            estimated_cac_organic=details["estimated_cac_organic"],
            estimated_cac_paid=details["estimated_cac_paid"],
        )
        assert result.status == "cleared_ungrounded"
        assert result.ratio == NOT_COMPUTABLE
        # The invented $45 and the threshold claim are both gone from the ratio.
        assert "45" not in result.ratio
        assert "7.2" not in result.ratio
        assert result.degradation and report["selected_solution_name"] in result.degradation
        assert result.rationale_note

    def test_report_side_application_rebuilds_the_live_pricing_block(self, report):
        """End-to-end over the stored record: the exact objects the report assembles,
        through the exact helper report_generator calls."""
        from nicheiq.models.research_state import PricingStrategyResult
        from nicheiq.models.solution_idea import SolutionIdea

        original = PricingStrategyResult(**report["pricing_strategy"])
        solution = SolutionIdea(**report["selected_solution_details"])

        fixed, result = apply_ltv_cac_grounding(
            original, solution, report["selected_solution_name"]
        )

        assert result.status == "cleared_ungrounded"
        assert fixed.ltv_to_cac_ratio == NOT_COMPUTABLE
        # The threshold claim is disowned where it actually lives.
        assert "mandatory 2:1 threshold" in fixed.wtp_validation
        assert "unsupported" in fixed.wtp_validation
        assert "cleared to 'not computable'" in fixed.wtp_validation
        # The crew's own object is untouched — the report downgrades its rendering only.
        assert original.ltv_to_cac_ratio == "7.2:1 to 18:1 (LTV $324 - $810 ÷ CAC $45)"
        assert "unsupported" not in original.wtp_validation
        # No CAC in the ratio at all now, matching the N/A CAC table above it.
        assert "$45" not in fixed.ltv_to_cac_ratio

    def test_rerunning_on_an_already_downgraded_block_is_a_no_op(self, report):
        """Idempotence: report assembly can run more than once per job."""
        from nicheiq.models.research_state import PricingStrategyResult
        from nicheiq.models.solution_idea import SolutionIdea

        solution = SolutionIdea(**report["selected_solution_details"])
        once, _ = apply_ltv_cac_grounding(
            PricingStrategyResult(**report["pricing_strategy"]),
            solution,
            report["selected_solution_name"],
        )
        twice, result = apply_ltv_cac_grounding(
            once, solution, report["selected_solution_name"]
        )
        assert not result.changed
        assert twice.ltv_to_cac_ratio == once.ltv_to_cac_ratio
        assert twice.wtp_validation == once.wtp_validation

    def test_degradation_surfaces_verbatim_in_quality_caveats(self, report):
        """The ledger is only useful if the reader sees it. Proves the last hop:
        state.pipeline_degradations -> data_quality_summary.quality_caveats."""
        from unittest.mock import MagicMock

        from nicheiq.models.research_state import PricingStrategyResult
        from nicheiq.models.solution_idea import SolutionIdea
        from nicheiq.report.report_generator import ReportGenerator

        _, result = apply_ltv_cac_grounding(
            PricingStrategyResult(**report["pricing_strategy"]),
            SolutionIdea(**report["selected_solution_details"]),
            report["selected_solution_name"],
        )
        assert result.degradation

        state = MagicMock()
        state.seeded_from_catalog = False
        state.social_content_quality_tier = "EXCELLENT"
        state.pain_point_quality_tier = "GOLD"
        state.pain_point_confidence_score = 0.97
        state.seo_strategy_report = None
        state.fallback_stages = []
        state.filtering_stats = {}
        state.niche_drift_telemetry = {}
        state.idea_coverage_caveats = []
        state.pipeline_degradations = [result.degradation]

        gen = ReportGenerator(state)
        gen.accessor = MagicMock()
        gen.accessor.get_volume_filter_ratio.return_value = None
        summary = gen._generate_data_quality_summary()

        assert result.degradation in summary.quality_caveats

    def test_alternatives_with_real_cac_are_not_disturbed(self, report):
        """Ideas that DID publish a CAC must pass untouched — the validator must not
        blanket-clear every ratio in the report."""
        checked = 0
        for entry in report["data_quality_summary"]["examined_ruled_out"]:
            idea = entry["idea"]
            if not idea.get("estimated_cac_organic"):
                continue
            result = validate_ltv_cac_grounding(
                solution_name=idea.get("solution_name", "?"),
                ltv_to_cac_ratio="4:1",  # no cited CAC to contradict
                estimated_cac_organic=idea["estimated_cac_organic"],
                estimated_cac_paid=idea.get("estimated_cac_paid"),
            )
            assert result.status == "ok", idea.get("solution_name")
            checked += 1
        assert checked >= 3, "expected several ruled-out ideas with published CAC"
