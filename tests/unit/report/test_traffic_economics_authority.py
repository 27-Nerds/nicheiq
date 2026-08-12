"""Stage-14 traffic projection authority regressions."""

from nicheiq.models.research_state import TrafficMonetizationResult
from nicheiq.report.report_generator import ReportGenerator


def _traffic(**overrides) -> TrafficMonetizationResult:
    values = {
        "solution_name": "CoffeeRoute",
        "monetization_model": "Free-Tool-Funnel",
        "estimated_monthly_pageviews": "900 - 1,200",
        "traffic_source_breakdown": [
            {"source": "organic_search", "percentage": "100%"},
        ],
        "estimated_cpm_rate": "$3-5 CPM",
        "estimated_monthly_ad_revenue": "$3 - $6/month",
        "recommended_ad_networks": [],
        "affiliate_commission_rate": "unknown",
        "estimated_affiliate_ctr": "unknown",
        "estimated_monthly_affiliate_revenue": "$0 - $0",
        "recommended_affiliate_programs": [],
        "lead_gen_price_per_lead": "$20-40",
        "estimated_monthly_revenue_range": "$100 - $800/month",
        "estimated_annual_revenue_range": "$1,200 - $9,600/year",
        "break_even_traffic_threshold": "unknown",
        "monetization_rationale": "Qualified downstream actions, not raw pageviews, carry value.",
        "scaling_strategy": "Validate candidate-relevant evaluations.",
        "monetization_confidence": "Medium",
        "viability_verdict": "conditional",
        "funnel_target": "paid monitoring",
        "qualified_actions": "5 - 20 qualified evaluations/month",
        "conversion_assumptions": [
            "0.5%-1.0% of candidate-relevant visits complete an evaluation",
        ],
        "estimated_funnel_value": "$100 - $800/month",
        "saas_alternative_viable": True,
        "saas_vs_traffic_recommendation": "Use the free surface as a measured funnel.",
    }
    values.update(overrides)
    return TrafficMonetizationResult(**values)


def test_typed_stage8_economics_are_not_overwritten_by_large_raw_seo_tiers():
    safe = _traffic()
    contaminated_raw_tier_projection = {
        "estimated_monthly_pageviews": "900,000-1,800,000",
        "estimated_monthly_ad_revenue": "$2,700-$9,000",
        "estimated_monthly_affiliate_revenue": "$50,000-$150,000",
        "estimated_monthly_revenue_range": "$52,700-$159,000",
        "year3_monthly_pageviews": "2,000,000-4,000,000",
        "year3_monthly_revenue": "$100,000-$500,000/mo",
        "traffic_methodology": "Projection from all raw SEO tiers",
    }

    merged = ReportGenerator._merge_legacy_traffic_projection(
        safe, contaminated_raw_tier_projection
    )

    assert merged.estimated_monthly_pageviews == "900 - 1,200"
    assert merged.estimated_monthly_revenue_range == "$100 - $800/month"
    assert merged.viability_verdict == "conditional"
    assert merged.estimated_funnel_value == "$100 - $800/month"
    assert merged.year3_monthly_pageviews is None
    assert merged.traffic_methodology is None


def test_legacy_record_still_accepts_the_existing_report_projection_fallback():
    legacy = _traffic(
        monetization_model="Ad-Supported",
        viability_verdict=None,
        funnel_target=None,
        qualified_actions=None,
        conversion_assumptions=None,
        estimated_funnel_value=None,
    )

    merged = ReportGenerator._merge_legacy_traffic_projection(
        legacy,
        {"estimated_monthly_pageviews": "4,000-8,000"},
    )

    assert merged.estimated_monthly_pageviews == "4,000-8,000"
    assert merged.viability_verdict is None


def test_evaluated_unknown_record_rejects_raw_seo_fallback():
    unknown = _traffic(
        economics_evaluated=True,
        viability_verdict=None,
        estimated_monthly_revenue_range=None,
        estimated_annual_revenue_range=None,
        estimated_monthly_ad_revenue=None,
        funnel_target=None,
        qualified_actions=None,
        conversion_assumptions=None,
        estimated_funnel_value=None,
    )

    merged = ReportGenerator._merge_legacy_traffic_projection(
        unknown,
        {
            "estimated_monthly_revenue_range": "$50,000/month",
            "estimated_annual_revenue_range": "$600,000/year",
            "estimated_monthly_ad_revenue": "$10,000/month",
        },
    )

    assert merged is unknown
    assert merged.estimated_monthly_revenue_range is None
    assert merged.estimated_annual_revenue_range is None
    assert merged.estimated_monthly_ad_revenue is None
