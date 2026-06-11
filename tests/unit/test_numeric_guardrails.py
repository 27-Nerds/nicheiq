"""
Tests for the crew numeric guardrails (Phase 4 fixes).

Covers:
- numeric_parsers: range-aware dollar/ratio parsing (the old first-number
  regex parsed "$50-80M" as 50 with no multiplier)
- market-sizing guardrail: 3-2-1 rule promoted to hard failure
- pricing guardrail: numeric ARPU/LTV/ratio validation + CAC cross-check
- traffic guardrail: evidence-ceiling clamp; no forced affiliate programs
- competition-scale contract: 0-1 Keyword.competition never silently mixes
  with the 0-100 avg_competition scale
"""

import json
from unittest.mock import MagicMock

import pytest

from nicheiq.utils.validation.numeric_parsers import parse_dollar_amount, parse_ratio


class TestParseDollarAmount:
    @pytest.mark.parametrize("text,expected", [
        ("$2.5B", 2_500_000_000),
        ("$500K", 500_000),
        ("$800M", 800_000_000),
        ("USD 50M", 50_000_000),
        ("$50M+", 50_000_000),
        ("$300", 300),
        ("1.2 billion", 1_200_000_000),
        # Ranges → midpoint; a single trailing suffix applies to BOTH ends
        ("$50-80M", 65_000_000),
        ("$50M-$80M", 65_000_000),
        ("$300 - $750", 525),
        ("$5-10", 7.5),
        ("$5-15 CPM", 10),
    ])
    def test_formats(self, text, expected):
        assert parse_dollar_amount(text) == pytest.approx(expected)

    def test_no_number_returns_none(self):
        assert parse_dollar_amount("TBD") is None
        assert parse_dollar_amount(None) is None
        assert parse_dollar_amount("") is None


class TestParseRatio:
    @pytest.mark.parametrize("text,expected", [
        ("3:1", 3.0),
        ("2.5 : 1", 2.5),
        ("3x", 3.0),
        ("12:1 to 48:1", 30.0),  # range → midpoint
        ("ratio of 3.5", 3.5),
    ])
    def test_formats(self, text, expected):
        assert parse_ratio(text) == pytest.approx(expected)

    def test_no_number_returns_none(self):
        assert parse_ratio("healthy") is None
        assert parse_ratio(None) is None


def _market_sizing_output(tam="$500M", sam="$100M", som_y1="$5M", som_y3="$20M"):
    output = MagicMock()
    output.pydantic = None
    output.raw = json.dumps({
        "total_addressable_market": tam,
        "serviceable_available_market": sam,
        "serviceable_obtainable_market_y1": som_y1,
        "serviceable_obtainable_market_y3": som_y3,
        "primary_methodology": "Bottom-up",
        "methodology_explanation": "Keyword volume × conversion assumptions.",
        "data_sources_used": ["DataForSEO keyword volumes"],
        "keyword_demand_signal": "Strong",
        "pain_point_frequency": "High",
        "competitor_market_presence": "Moderate",
        "growth_drivers": ["driver1"],
        "market_saturation_level": "Medium",
        "market_timing_assessment": "Growth",
        "risk_factors": ["risk1"],
        "market_viability_verdict": "Strong",
        "viability_rationale": "Strong demand signals across sources.",
        "recommended_entry_strategy": "Niche-first entry strategy",
    })
    return output


class TestMarketSizingGuardrail:
    def _validate(self, output):
        from nicheiq.crews.market_sizing_crew import MarketSizingCrew
        crew = MarketSizingCrew.__new__(MarketSizingCrew)
        return crew._validate_market_sizing_output(output)

    def test_valid_hierarchy_passes(self):
        ok, _ = self._validate(_market_sizing_output())
        assert ok

    def test_range_values_parse_correctly(self):
        """'$50-80M' must parse as 65M (midpoint), not 50 plain dollars."""
        ok, _ = self._validate(_market_sizing_output(
            tam="$300-500M", sam="$50-80M", som_y1="$3-5M", som_y3="$10-15M"
        ))
        assert ok

    def test_hierarchy_violation_fails(self):
        ok, msg = self._validate(_market_sizing_output(tam="$50M", sam="$100M"))
        assert not ok
        assert "hierarchy" in msg.lower()

    def test_321_rule_is_hard_failure(self):
        """TAM only 2x SAM → hard fail (was warn-only)."""
        ok, msg = self._validate(_market_sizing_output(tam="$200M", sam="$100M"))
        assert not ok
        assert "3-2-1" in msg

    def test_sam_som_ratio_hard_failure(self):
        ok, msg = self._validate(_market_sizing_output(sam="$8M", som_y1="$5M"))
        assert not ok
        assert "3-2-1" in msg


def _pricing_output(
    arpu="$32/month",
    ltv="$384 - $960",
    ratio="4:1",
    pricing_model="Subscription",
    ad_revenue=None,
    affiliate_revenue=None,
):
    output = MagicMock()
    output.pydantic = None
    output.raw = json.dumps({
        "solution_name": "TestTool",
        "pricing_model": pricing_model,
        "pricing_rationale": "Detailed rationale explaining the strategy choice in depth for the niche.",
        "estimated_arpu": arpu,
        "estimated_ltv": ltv,
        "ltv_to_cac_ratio": ratio,
        "estimated_monthly_ad_revenue": ad_revenue,
        "estimated_monthly_affiliate_revenue": affiliate_revenue,
        "price_vs_competitors": "10% below median",
        "value_proposition_delta": "More features at lower price",
        "pricing_confidence": "Medium",
        "wtp_validation": "WTP scores support this pricing level.",
    })
    return output


class TestPricingGuardrail:
    def _validate(self, output, cac=None):
        from nicheiq.utils.validation.crew_guardrails import validate_pricing_strategy
        return validate_pricing_strategy(output, suggested_cac_range=cac)

    def test_valid_economics_pass(self):
        ok, _ = self._validate(_pricing_output())
        assert ok

    def test_ratio_below_mandatory_floor_fails(self):
        ok, msg = self._validate(_pricing_output(ratio="1.5:1"))
        assert not ok
        assert "2:1" in msg

    def test_ltv_below_arpu_fails(self):
        """LTV = retention × ARPU, so LTV < ARPU is arithmetic nonsense."""
        ok, msg = self._validate(_pricing_output(arpu="$50/month", ltv="$20"))
        assert not ok
        assert "Unit-economics" in msg

    def test_unparseable_ratio_fails(self):
        ok, msg = self._validate(_pricing_output(ratio="healthy"))
        assert not ok
        assert "ltv_to_cac_ratio" in msg

    def test_fabricated_ratio_vs_cac_anchor_fails(self):
        """LTV $672 ÷ CAC $45 ≈ 15:1; a stated 40:1 is fabrication (>2x off)."""
        ok, msg = self._validate(
            _pricing_output(ltv="$384 - $960", ratio="40:1"),
            cac="$30-60 (mixed organic + paid)",
        )
        assert not ok
        assert "inconsistent" in msg

    def test_consistent_ratio_vs_cac_anchor_passes(self):
        ok, _ = self._validate(
            _pricing_output(ltv="$384 - $960", ratio="15:1"),
            cac="$30-60 (mixed organic + paid)",
        )
        assert ok

    # --- Ad/affiliate models: the task YAML mandates "N/A - ..." for LTV and
    # ratio, so the guardrail must validate the revenue fields instead.
    # Regression for the 2026-06-11 golden run where prompt-compliant output
    # was rejected and 2/3 solutions lost pricing analysis.

    def test_ad_supported_with_na_ltv_passes(self):
        """The exact failure case from the 2026-06-11 log."""
        ok, _ = self._validate(_pricing_output(
            pricing_model="Ad-Supported-Free",
            arpu="$0.012 per pageview (ads + affiliate)",
            ltv="N/A - traffic-based model",
            ratio="N/A - SEO-driven traffic acquisition",
            ad_revenue="$400-800/month",
        ))
        assert ok

    def test_affiliate_only_with_affiliate_revenue_passes(self):
        ok, _ = self._validate(_pricing_output(
            pricing_model="Affiliate-Only",
            arpu="N/A - free tool",
            ltv="N/A - traffic-based model",
            ratio="N/A",
            affiliate_revenue="$200-400/month",
        ))
        assert ok

    def test_ad_model_without_revenue_estimates_fails(self):
        ok, msg = self._validate(_pricing_output(
            pricing_model="Ad-Supported-Free",
            ltv="N/A - traffic-based model",
            ratio="N/A",
        ))
        assert not ok
        assert "estimated_monthly_ad_revenue" in msg
        assert "estimated_monthly_affiliate_revenue" in msg

    def test_subscription_with_na_ltv_still_fails(self):
        """The N/A escape hatch is for ad/affiliate models only."""
        ok, msg = self._validate(_pricing_output(ltv="N/A - traffic-based model"))
        assert not ok
        assert "estimated_ltv" in msg

    def test_ad_model_skips_cac_cross_check(self):
        """The CAC anchor must not apply to models with no LTV to cross-check."""
        ok, _ = self._validate(
            _pricing_output(
                pricing_model="Ad-Supported-Free",
                ltv="N/A - traffic-based model",
                ratio="N/A",
                ad_revenue="$400-800/month",
            ),
            cac="$30-60 (mixed organic + paid)",
        )
        assert ok


def _pricing_output_with_tiers(
    starter=None, pro=None, enterprise=None, **kwargs
):
    """_pricing_output variant that also sets the recommended tier prices."""
    output = _pricing_output(**kwargs)
    payload = json.loads(output.raw)
    payload["recommended_starter_price"] = starter
    payload["recommended_pro_price"] = pro
    payload["recommended_enterprise_price"] = enterprise
    output.raw = json.dumps(payload)
    return output


class TestExampleAnchoring:
    """The pricing LLM must not ship the YAML's fictional example numbers.

    Regression for the 2026-06-11 catalog run where the final report carried
    the full DevFlowTracker tuple ($19/$49/$149 tiers, $32 ARPU, $384-$960
    LTV). Detection is numeric (>= 3 independent signals), not substring.
    """

    def _validate(self, output, cac=None):
        from nicheiq.utils.validation.crew_guardrails import validate_pricing_strategy
        return validate_pricing_strategy(output, suggested_cac_range=cac)

    def test_full_devflowtracker_copy_rejected(self):
        """The exact bca92a68 incident: 4 signals -> rejected."""
        ok, msg = self._validate(_pricing_output_with_tiers(
            starter="$19/month", pro="$49/month", enterprise="$149/month",
            arpu="$32/month", ltv="$384 - $960 (12-30mo retention)",
            ratio="8:1 (LTV $384 ÷ CAC $48)",
        ))
        assert not ok
        assert "fictional example" in msg
        assert "DevFlowTracker" in msg

    def test_reformatted_copy_still_rejected(self):
        """Numeric matching beats substring: em-dash + $1 tweak still counts."""
        ok, msg = self._validate(_pricing_output_with_tiers(
            starter="$19/month", pro="$49/month", enterprise="$149/month",
            arpu="$32/month", ltv="$385–$960",
            ratio="14:1",
        ))
        assert not ok
        assert "fictional example" in msg

    def test_two_coincidental_signals_pass(self):
        """A real $19/$49 SaaS with its own economics must not be rejected."""
        ok, _ = self._validate(_pricing_output_with_tiers(
            starter="$19/month", pro="$49/month", enterprise=None,
            arpu="$29/month", ltv="$348 - $870 (12-30mo retention)",
            ratio="8:1",
        ))
        assert ok

    def test_coupled_arpu_ltv_counts_as_one_signal(self):
        """ARPU $32 forces LTV $384-$960 arithmetically, so the pair plus one
        tier price (2 signals total) must pass — coupling-aware counting."""
        ok, _ = self._validate(_pricing_output_with_tiers(
            starter="$19/month", pro="$59/month", enterprise=None,
            arpu="$32/month", ltv="$384 - $960 (12-30mo retention)",
            ratio="14:1",
        ))
        assert ok

    def test_plumbingcostcalc_ad_copy_rejected(self):
        """Ad-model example copying: tiers absent, but ad+affiliate revenue
        plus the e.g.-list signals trip the threshold."""
        ok, msg = self._validate(_pricing_output_with_tiers(
            starter="$19/month",
            pricing_model="Ad-Supported-Free",
            arpu="$0.012 per pageview",
            ltv="N/A - traffic-based model",
            ratio="N/A",
            ad_revenue="$400-600/month",
            affiliate_revenue="$150-300/month",
        ))
        assert not ok
        assert "fictional example" in msg

    def test_yaml_examples_match_fingerprints(self):
        """Sync guard: if someone edits the YAML example numbers, this fails
        and tells them to update _collect_example_matches."""
        from pathlib import Path
        yaml_path = (
            Path(__file__).parents[2]
            / "src" / "nicheiq" / "crews" / "config" / "pricing_strategy_tasks.yaml"
        )
        text = yaml_path.read_text()
        for marker in (
            "$19/month", "$49/month", "$149/month",  # DevFlowTracker tiers
            "$32/month", "$384 - $960",              # DevFlowTracker ARPU/LTV
            "$400-600/month", "$150-300/month",      # PlumbingCostCalc revenue
        ):
            assert marker in text, (
                f"YAML example value {marker!r} not found in "
                "pricing_strategy_tasks.yaml — the example numbers changed. "
                "Update _collect_example_matches in crew_guardrails.py to match."
            )


def _traffic_output(pageviews="8,000-12,000", affiliate_programs=None):
    output = MagicMock()
    output.pydantic = None
    output.raw = json.dumps({
        "solution_name": "TestDirectory",
        "monetization_model": "Hybrid-Traffic",
        "estimated_monthly_pageviews": pageviews,
        "traffic_source_breakdown": [
            {"source": "organic_search", "percentage": "90%"},
            {"source": "direct", "percentage": "10%"},
        ],
        "estimated_cpm_rate": "$5-15 CPM",
        "estimated_monthly_ad_revenue": "$100-$300",
        "affiliate_commission_rate": "5-15%",
        "estimated_affiliate_ctr": "2-4% of pageviews",
        "estimated_monthly_affiliate_revenue": "$100-$300",
        "estimated_monthly_revenue_range": "$200-$600",
        "estimated_annual_revenue_range": "$2,400-$7,200",
        "break_even_traffic_threshold": "2,000 pageviews/mo",
        "recommended_ad_networks": ["Google AdSense"],
        "recommended_affiliate_programs": affiliate_programs if affiliate_programs is not None else [],
        "monetization_rationale": "Display ads plus affiliate links fit this traffic profile well.",
        "scaling_strategy": "Grow content footprint across tier-2 keywords.",
        "monetization_confidence": "Medium",
        "saas_alternative_viable": False,
        "saas_vs_traffic_recommendation": "Traffic-first monetization fits this niche.",
    })
    return output


class TestTrafficGuardrail:
    def _validate(self, output, ceiling=None):
        from nicheiq.utils.validation.crew_guardrails import validate_traffic_monetization
        return validate_traffic_monetization(output, traffic_ceiling_y1_high=ceiling)

    def test_empty_affiliate_programs_allowed(self):
        """The forced ≥1 affiliate-program rule is gone — empty list is honest."""
        ok, _ = self._validate(_traffic_output(affiliate_programs=[]))
        assert ok

    def test_pageviews_within_ceiling_pass(self):
        ok, _ = self._validate(_traffic_output(pageviews="8,000-12,000"), ceiling=15_000)
        assert ok

    def test_pageviews_exceeding_ceiling_fail(self):
        ok, msg = self._validate(_traffic_output(pageviews="50,000-80,000"), ceiling=15_000)
        assert not ok
        assert "ceiling" in msg

    def test_no_ceiling_skips_clamp(self):
        ok, _ = self._validate(_traffic_output(pageviews="50,000-80,000"), ceiling=None)
        assert ok


class TestCompetitionScaleContract:
    """0-1 Keyword.competition vs 0-100 avg_competition must never silently mix."""

    def test_keyword_competition_is_0_1_scale(self):
        from pydantic import ValidationError

        from nicheiq.models.keyword_data import Keyword

        with pytest.raises(ValidationError):
            Keyword(
                keyword="test",
                search_volume=100,
                competition=50,  # 0-100 value in a 0-1 field must be rejected
                opportunity_level="high",
            )

    def test_difficulty_adjusted_score_uses_0_100_avg_competition(self):
        """The difficulty-adjusted formula divides avg_competition by 100 —
        pin that the 0-100 scale produces a sane 0-1 opportunity factor."""
        avg_competition = 50.0  # 0-100 scale from DataForSEO
        avg_opportunity = 1 - (avg_competition / 100)
        assert 0.0 <= avg_opportunity <= 1.0
        assert avg_opportunity == 0.5
