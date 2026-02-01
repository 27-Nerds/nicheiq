"""Unit tests for PricingStrategyResult.format_summary()."""

import pytest

from nicheiq.models.research_state import PricingStrategyResult


def _make_pricing(**overrides) -> PricingStrategyResult:
    """Create a PricingStrategyResult with sensible defaults, applying overrides."""
    defaults = dict(
        solution_name="TestSolution",
        pricing_model="Freemium",
        pricing_rationale="Good fit for the market",
        estimated_arpu="$25/month",
        estimated_ltv="$300 - $750",
        ltv_to_cac_ratio="8:1",
        price_vs_competitors="10% below median",
        value_proposition_delta="15% more features at 20% lower price",
        pricing_confidence="Medium",
        wtp_validation="Pain scores support this pricing",
    )
    defaults.update(overrides)
    return PricingStrategyResult(**defaults)


class TestFormatSummary:
    """Tests for PricingStrategyResult.format_summary()."""

    def test_freemium_starter_and_pro(self):
        pricing = _make_pricing(
            pricing_model="Freemium",
            recommended_starter_price="$19/mo",
            recommended_pro_price="$49/mo",
        )
        result = pricing.format_summary()
        assert result == "Freemium: $19/mo starter, $49/mo pro"

    def test_subscription_all_tiers(self):
        pricing = _make_pricing(
            pricing_model="Subscription",
            recommended_starter_price="$29/mo",
            recommended_pro_price="$79/mo",
            recommended_enterprise_price="$199/mo",
        )
        result = pricing.format_summary()
        assert result == "Subscription: $29/mo starter, $79/mo pro, $199/mo enterprise"

    def test_ad_supported_free_no_subscription_prices(self):
        pricing = _make_pricing(
            pricing_model="Ad-Supported-Free",
            recommended_starter_price=None,
            recommended_pro_price=None,
            recommended_enterprise_price=None,
            estimated_monthly_ad_revenue="$400-800",
        )
        result = pricing.format_summary()
        assert result == "Ad-Supported-Free: est. $400-800/mo ad revenue"

    def test_affiliate_only(self):
        pricing = _make_pricing(
            pricing_model="Affiliate-Only",
            recommended_starter_price=None,
            recommended_pro_price=None,
            recommended_enterprise_price=None,
            estimated_monthly_affiliate_revenue="$200-400",
        )
        result = pricing.format_summary()
        assert result == "Affiliate-Only: est. $200-400/mo affiliate revenue"

    def test_ad_and_affiliate_combined(self):
        pricing = _make_pricing(
            pricing_model="Ad-Supported-Free",
            recommended_starter_price=None,
            recommended_pro_price=None,
            recommended_enterprise_price=None,
            estimated_monthly_ad_revenue="$300-600",
            estimated_monthly_affiliate_revenue="$100-200",
        )
        result = pricing.format_summary()
        assert result == "Ad-Supported-Free: est. $300-600/mo ad revenue, est. $100-200/mo affiliate revenue"

    def test_hybrid_only_starter(self):
        pricing = _make_pricing(
            pricing_model="Hybrid",
            recommended_starter_price="$15/mo",
            recommended_pro_price=None,
            recommended_enterprise_price=None,
        )
        result = pricing.format_summary()
        assert result == "Hybrid: $15/mo starter"

    def test_all_optional_prices_none(self):
        pricing = _make_pricing(
            pricing_model="Usage-Based",
            recommended_starter_price=None,
            recommended_pro_price=None,
            recommended_enterprise_price=None,
            estimated_monthly_ad_revenue=None,
            estimated_monthly_affiliate_revenue=None,
        )
        result = pricing.format_summary()
        assert result == "Usage-Based"
