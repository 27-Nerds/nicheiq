"""CR-1 deterministic traffic/funnel economics and schema compatibility."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from nicheiq.crews.traffic_monetization_crew import TrafficMonetizationCrew
from nicheiq.models.competitor import VerifiedPricingProvenance
from nicheiq.models.research_state import FinalReport, ResearchState, TrafficMonetizationResult
from nicheiq.models.solution_idea import CommercialRouteContract


def _solution(capture: str | None, payer: str | None, **overrides):
    route = CommercialRouteContract(
        access_model="free",
        value_capture_mode=capture,
        payer=payer,
        source_user_payment_required=False,
    )
    values = {
        "solution_name": "CoffeeRoute",
        "idea_id": "idea-coffee",
        "idea_revision": 3,
        "description": "A wholesale coffee-roaster lead calculator.",
        "commercial_route": route,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _verified_unit(
    route: str,
    billing_basis: str,
    *,
    source_name: str = "Coffee Roaster Leads",
    source_url: str = "https://example.com/pricing",
    retrieved_quote: str = "$20-40 per qualified lead",
    value_low: int | None = 20,
    value_high: int | None = 40,
    commission_pct_low: float | None = None,
    commission_pct_high: float | None = None,
):
    competitor = SimpleNamespace(name=source_name, url=source_url)
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
    )])
    provenance = VerifiedPricingProvenance(
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        route=route,
        source_name=source_name,
        source_url=source_url,
        retrieved_quote=retrieved_quote,
        retrieved_at=datetime(2026, 8, 12, tzinfo=UTC),
        verification_marker="exact_quote_in_fetched_public_content",
        value_low=value_low,
        value_high=value_high,
        billing_basis=billing_basis,
        commission_pct_low=commission_pct_low,
        commission_pct_high=commission_pct_high,
    )
    return TrafficMonetizationCrew._attributed_unit_value_evidence(
        analysis,
        "CoffeeRoute",
        route,
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
        verified_pricing_evidence=[provenance],
    )


def _result(**overrides) -> TrafficMonetizationResult:
    values = {
        "solution_name": "CoffeeRoute",
        "monetization_model": "Ad-Supported",
        "estimated_monthly_pageviews": "1,000 - 5,000",
        "traffic_source_breakdown": [
            {"source": "organic_search", "percentage": "90%"},
            {"source": "direct", "percentage": "10%"},
        ],
        "estimated_cpm_rate": "$3-5 CPM",
        "estimated_monthly_ad_revenue": "$3 - $25",
        "recommended_ad_networks": ["Google AdSense"],
        "affiliate_commission_rate": "unknown",
        "estimated_affiliate_ctr": "unknown",
        "estimated_monthly_affiliate_revenue": "$0 - $0",
        "recommended_affiliate_programs": [],
        "lead_gen_price_per_lead": "$20-40",
        "estimated_monthly_revenue_range": "$3 - $25",
        "estimated_annual_revenue_range": "$36 - $300",
        "break_even_traffic_threshold": "unknown",
        "monetization_rationale": "Ads alone are economically thin for this narrow B2B audience.",
        "scaling_strategy": "Validate qualified buyer actions before adding traffic channels.",
        "monetization_confidence": "Low",
        "saas_alternative_viable": True,
        "saas_vs_traffic_recommendation": "Use the free tool only as a qualified acquisition path.",
    }
    values.update(overrides)
    return TrafficMonetizationResult(**values)


def test_free_tool_funnel_model_and_viability_fields_are_typed():
    result = _result(
        monetization_model="Free-Tool-Funnel",
        viability_verdict="conditional",
        funnel_target="paid monitoring",
        qualified_actions="5-20 qualified evaluations/month",
        conversion_assumptions=["0.5%-1.0% of visitors complete a qualified evaluation"],
        estimated_funnel_value="$100 - $800/month",
    )

    assert result.monetization_model == "Free-Tool-Funnel"
    assert result.viability_verdict == "conditional"
    assert result.funnel_target == "paid monitoring"


def test_legacy_traffic_result_loads_with_unknown_new_fields():
    legacy = _result().model_dump(mode="json")
    for key in (
        "viability_verdict", "funnel_target", "qualified_actions",
        "conversion_assumptions", "estimated_funnel_value", "economics_evaluated",
    ):
        legacy.pop(key, None)

    restored = TrafficMonetizationResult.model_validate(json.loads(json.dumps(legacy)))

    assert restored.viability_verdict is None
    assert restored.economics_evaluated is False
    assert restored.funnel_target is None
    assert restored.estimated_funnel_value is None


def test_typed_traffic_result_roundtrip_preserves_all_route_economics_fields():
    original = _result(
        monetization_model="Free-Tool-Funnel",
        viability_verdict="conditional",
        economics_evaluated=True,
        funnel_target="paid monitoring",
        qualified_actions="5 - 20 qualified evaluations/month",
        conversion_assumptions=[
            "0.5%-1.0% of candidate-relevant visits complete an evaluation",
        ],
        estimated_funnel_value="$100 - $800/month",
        unit_value_evidence={
            "route": "lead_generation",
            "candidate_idea_id": "idea-coffee",
            "candidate_idea_revision": 3,
            "source_name": "Roaster Leads",
            "source_url": "https://example.com/pricing",
            "evidence_text": "$20-40 per qualified lead",
            "retrieved_quote": "$20-40 per qualified lead",
            "retrieved_at": "2026-08-12T00:00:00Z",
            "verification_marker": "exact_quote_in_fetched_public_content",
            "value_low": 20,
            "value_high": 40,
            "billing_basis": "per_lead",
        },
    )

    restored = TrafficMonetizationResult.model_validate_json(
        original.model_dump_json()
    )

    assert restored.model_dump(mode="json") == original.model_dump(mode="json")

    checkpoint = ResearchState(traffic_monetization_results=[original])
    restored_checkpoint = ResearchState.model_validate_json(checkpoint.model_dump_json())
    assert restored_checkpoint.traffic_monetization_results == [original]

    report = FinalReport(
        niche="coffee roasters",
        executive_summary="A measured route.",
        selected_solution_name="CoffeeRoute",
        selection_rationale="Candidate-owned evidence.",
        pain_points_summary="Pain summary.",
        recommended_solutions=["CoffeeRoute"],
        solutions_summary="Solution summary.",
        competitive_summary="Competition summary.",
        market_validation="Market validation.",
        data_sourcing_recommendations="Data recommendations.",
        next_steps=["Validate the qualified action."],
        traffic_monetization=original,
    )
    restored_report = FinalReport.model_validate_json(report.model_dump_json())
    assert restored_report.traffic_monetization == original


def test_unmeasured_route_does_not_guess_viability_from_llm_strings_or_programs():
    result = _result(
        monetization_model="Affiliate",
        recommended_affiliate_programs=["A plausible-looking program"],
        viability_verdict=None,
        estimated_monthly_revenue_range="$50,000/month",
        estimated_annual_revenue_range="$600,000/year",
    )

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode=None,
        payer=None,
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
    )

    assert result.viability_verdict is None
    assert result.economics_evaluated is True
    assert result.estimated_monthly_revenue_range is None
    assert result.estimated_annual_revenue_range is None
    assert result.estimated_monthly_ad_revenue is None


def test_small_ads_with_credible_b2b_lead_route_are_not_called_ad_success():
    result = _result()
    evidence = _verified_unit("lead_generation", "per_lead")
    assert evidence is not None

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="lead_generation",
        payer="downstream_customer",
        projected_pageviews=(1_000, 5_000),
        deterministic_ad_revenue=(3, 25),
        unit_value_evidence=evidence,
        solution=_solution("lead_generation", "downstream_customer"),
    )

    assert result.monetization_model == "Lead-Gen"
    assert result.viability_verdict == "conditional"
    assert result.qualified_actions is not None
    assert result.estimated_funnel_value is not None
    assert result.recommended_ad_networks == []


def test_small_ads_without_a_downstream_payer_are_nonviable():
    result = _result()

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="advertising",
        payer="end_user",
        projected_pageviews=(1_000, 5_000),
        deterministic_ad_revenue=(3, 25),
        solution=_solution("advertising", "end_user"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.recommended_ad_networks == []
    assert result.estimated_monthly_ad_revenue == "$3 - $25/month"
    assert "Deterministic route economics: nonviable" in result.monetization_rationale


def test_high_ad_economics_cannot_succeed_without_an_advertiser_payer():
    result = _result()

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="advertising",
        payer="end_user",
        projected_pageviews=(100_000, 200_000),
        deterministic_ad_revenue=(500, 2_000),
        solution=_solution("advertising", "end_user"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.estimated_monthly_revenue_range is None


def test_incomplete_commercial_lane_never_upgrades_high_ad_economics():
    result = _result()
    incomplete = _solution("advertising", "advertiser")
    incomplete.commercial_route.source_user_payment_required = None

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="advertising",
        payer="advertiser",
        projected_pageviews=(100_000, 200_000),
        deterministic_ad_revenue=(500, 2_000),
        solution=incomplete,
    )

    assert result.economics_evaluated is True
    assert result.viability_verdict != "viable"
    assert result.estimated_monthly_revenue_range is None


def test_affiliate_cannot_be_viable_without_a_real_program():
    result = _result(
        monetization_model="Affiliate",
        recommended_affiliate_programs=["Plausible but unverified program"],
    )

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="affiliate",
        payer="vendor",
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        solution=_solution("affiliate", "vendor"),
    )

    assert result.viability_verdict == "nonviable"
    assert "no real candidate-specific affiliate program" in result.monetization_rationale


def test_money_range_parses_a_single_currency_symbol_range():
    assert TrafficMonetizationCrew._money_range("$20-40 per qualified lead") == (20, 40)


def test_nonviable_neutralizes_every_optimistic_llm_economic_field():
    result = _result(
        estimated_monthly_revenue_range="$50,000/month",
        estimated_annual_revenue_range="$600,000/year",
        estimated_monthly_affiliate_revenue="$45,000/month",
        affiliate_commission_rate="40%",
        estimated_affiliate_ctr="25%",
        recommended_affiliate_programs=["Imaginary Program"],
        sponsored_listing_price="$5,000/month",
        premium_placement_price="$10,000/month",
        lead_gen_price_per_lead="$500/lead",
        funnel_target="enterprise contract",
        qualified_actions="1,000/month",
        conversion_assumptions=["50% conversion"],
        estimated_funnel_value="$500,000/month",
        break_even_traffic_threshold="100 visits",
        scaling_strategy="Scale immediately.",
        monetization_confidence="High",
        year3_monthly_revenue="$1,000,000/month",
        full_potential_monthly_revenue="$2,000,000/month",
        revenue_growth_note="Guaranteed compounding.",
        revenue_milestones=[{
            "traffic": "1,000",
            "ad_revenue": "$50,000",
            "unlock": "Everything",
            "total_potential": "$2,000,000",
        }],
    )

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="advertising",
        payer="advertiser",
        projected_pageviews=(1_000, 5_000),
        deterministic_ad_revenue=(3, 25),
        solution=_solution("advertising", "advertiser"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.estimated_monthly_ad_revenue == "$3 - $25/month"
    for field in (
        "estimated_monthly_revenue_range", "estimated_annual_revenue_range",
        "estimated_monthly_affiliate_revenue", "affiliate_commission_rate",
        "estimated_affiliate_ctr", "sponsored_listing_price", "premium_placement_price",
        "lead_gen_price_per_lead", "funnel_target", "qualified_actions",
        "conversion_assumptions", "estimated_funnel_value", "break_even_traffic_threshold",
        "scaling_strategy", "year3_monthly_revenue", "full_potential_monthly_revenue",
        "revenue_growth_note", "revenue_milestones",
    ):
        assert getattr(result, field) in (None, [])
    assert result.recommended_affiliate_programs == []
    assert result.monetization_confidence == "Low"


def test_advertising_totals_are_code_owned_and_clear_other_routes():
    result = _result(
        estimated_monthly_revenue_range="$50,000/month",
        estimated_annual_revenue_range="$600,000/year",
        estimated_monthly_affiliate_revenue="$45,000/month",
        recommended_affiliate_programs=["Wrong route"],
        sponsored_listing_price="$5,000/month",
        monetization_confidence="High",
    )

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="advertising",
        payer="advertiser",
        projected_pageviews=(100_000, 200_000),
        deterministic_ad_revenue=(500, 2_000),
        solution=_solution("advertising", "advertiser"),
    )

    assert result.viability_verdict == "viable"
    assert result.estimated_monthly_revenue_range == "$500 - $2,000/month"
    assert result.estimated_annual_revenue_range == "$6,000 - $24,000/year"
    assert result.estimated_monthly_affiliate_revenue is None
    assert result.recommended_affiliate_programs == []
    assert result.sponsored_listing_price is None


def test_paid_upgrade_without_an_explicit_payer_is_nonviable_even_with_price_evidence():
    result = _result(monetization_model="Free-Tool-Funnel")

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="paid_upgrade_funnel",
        payer=None,
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        unit_value_evidence={
            "route": "paid_upgrade_funnel",
            "source_name": "Comparable Upgrade",
            "source_url": "https://example.com/pricing",
            "evidence_text": "$29-49 per paid account per month",
            "value_low": 29,
            "value_high": 49,
            "billing_basis": "per_paid_upgrade_month",
        },
        solution=_solution("paid_upgrade_funnel", None),
    )

    assert result.viability_verdict == "nonviable"
    assert result.estimated_monthly_revenue_range is None


@pytest.mark.parametrize(
    ("capture", "payer", "route", "basis"),
    [
        ("lead_generation", "end_user", "lead_generation", "per_lead"),
        ("affiliate", "end_user", "affiliate", "affiliate_program"),
    ],
)
def test_verified_evidence_cannot_override_an_incompatible_payer(
    capture, payer, route, basis,
):
    result = _result()
    evidence = _verified_unit(
        route,
        basis,
        commission_pct_low=5 if route == "affiliate" else None,
        commission_pct_high=10 if route == "affiliate" else None,
    )
    assert evidence is not None

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode=capture,
        payer=payer,
        projected_pageviews=(100_000, 200_000),
        deterministic_ad_revenue=(500, 2_000),
        unit_value_evidence=evidence,
        solution=_solution(capture, payer),
    )

    assert result.viability_verdict == "nonviable"
    assert result.estimated_funnel_value is None


def test_llm_authored_lead_price_is_not_unit_value_evidence():
    result = _result(lead_gen_price_per_lead="$20-40 per lead")

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="lead_generation",
        payer="downstream_customer",
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        unit_value_evidence=None,
        solution=_solution("lead_generation", "downstream_customer"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.lead_gen_price_per_lead is None
    assert result.estimated_funnel_value is None


def test_unverified_structured_price_cannot_upgrade_a_compatible_route():
    result = _result()

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="lead_generation",
        payer="downstream_customer",
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        unit_value_evidence={
            "route": "lead_generation",
            "source_name": "Roaster Leads",
            "source_url": "https://example.com/pricing",
            "evidence_text": "$20-40 per qualified lead",
            "value_low": 20,
            "value_high": 40,
            "billing_basis": "per_lead",
        },
        solution=_solution("lead_generation", "downstream_customer"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.estimated_funnel_value is None


def test_monthly_sponsorship_price_is_not_multiplied_by_qualified_actions():
    result = _result()
    evidence = _verified_unit(
        "sponsorship",
        "per_sponsored_listing_month",
        source_name="Coffee Roaster Directory",
        source_url="https://example.com/sponsor",
        retrieved_quote="$100-200 per sponsored listing per month",
        value_low=100,
        value_high=200,
    )
    assert evidence is not None

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="sponsorship",
        payer="listed_business",
        projected_pageviews=(100_000, 200_000),
        deterministic_ad_revenue=(500, 2_000),
        unit_value_evidence=evidence,
        solution=_solution("sponsorship", "listed_business"),
    )

    assert result.viability_verdict == "conditional"
    assert result.estimated_monthly_revenue_range == "$100 - $200/month"
    assert result.estimated_funnel_value == "$100 - $200/month"


def test_exact_landscape_model_authored_competitor_price_is_not_verified():
    competitor = SimpleNamespace(
        name="Roaster Leads",
        url="https://example.com/lead-pricing",
        pricing_model="$20-40 per qualified lead",
        description="Qualified wholesale coffee-roaster lead generation.",
    )
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
    )])

    evidence = TrafficMonetizationCrew._attributed_unit_value_evidence(
        analysis,
        "CoffeeRoute",
        "lead_generation",
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    )

    assert evidence is None


def test_arbitrary_competitor_privacy_url_is_not_verified_unit_value_evidence():
    competitor = SimpleNamespace(
        name="Roaster Leads",
        url="https://example.com/privacy",
        pricing_model="$20-40 per qualified lead",
        description="Qualified wholesale coffee-roaster lead generation.",
    )
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
    )])

    evidence = TrafficMonetizationCrew._attributed_unit_value_evidence(
        analysis,
        "CoffeeRoute",
        "lead_generation",
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    )

    assert evidence is None


@pytest.mark.parametrize(
    "source_url",
    [
        "https://localhost/pricing",
        "https://127.0.0.1/pricing",
        "https://192.168.1.7/pricing",
        "http://example.com/pricing",
        "https://user:password@example.com/pricing",
    ],
)
def test_verifier_provenance_rejects_non_public_or_credentialed_urls(source_url):
    with pytest.raises(ValueError, match="exact public HTTPS URL"):
        VerifiedPricingProvenance(
            candidate_idea_id="idea-coffee",
            candidate_idea_revision=3,
            route="lead_generation",
            source_name="Coffee Roaster Leads",
            source_url=source_url,
            retrieved_quote="$20-40 per qualified coffee-roaster lead",
            retrieved_at=datetime(2026, 8, 12, tzinfo=UTC),
            verification_marker="exact_quote_in_fetched_public_content",
            value_low=20,
            value_high=40,
            billing_basis="per_lead",
        )


def test_duplicate_or_stale_landscapes_cannot_supply_candidate_unit_value():
    coffee = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[SimpleNamespace(
            name="Roaster Leads",
            url="https://example.com/coffee-leads",
            pricing_model="$20-40 per qualified lead",
            description="Wholesale coffee roaster lead generation.",
        )],
    )
    stale_vet = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[SimpleNamespace(
            name="Vet Buyer Network",
            url="https://example.com/vet-leads",
            pricing_model="$80-120 per qualified lead",
            description="Veterinary clinic acquisition leads.",
        )],
    )

    evidence = TrafficMonetizationCrew._attributed_unit_value_evidence(
        SimpleNamespace(solution_landscapes=[stale_vet, coffee]),
        "CoffeeRoute",
        "lead_generation",
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    )

    assert evidence is None


def test_mismatched_revision_and_legacy_identityless_landscape_are_not_unit_evidence():
    competitor = SimpleNamespace(
        name="Roaster Leads",
        url="https://example.com/lead-pricing",
        pricing_model="$20-40 per qualified lead",
        description="Qualified wholesale coffee-roaster lead generation.",
    )
    landscapes = [
        SimpleNamespace(
            solution_name="CoffeeRoute",
            candidate_idea_id="idea-coffee",
            candidate_idea_revision=2,
            off_niche_caveat=None,
            competitors=[competitor],
        ),
        SimpleNamespace(
            solution_name="LegacyCoffeeRoute",
            candidate_idea_id=None,
            candidate_idea_revision=None,
            off_niche_caveat=None,
            competitors=[competitor],
        ),
    ]

    assert TrafficMonetizationCrew._attributed_unit_value_evidence(
        SimpleNamespace(solution_landscapes=landscapes),
        "CoffeeRoute",
        "lead_generation",
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    ) is None


def test_off_niche_landscape_caveat_blocks_identity_matched_price():
    landscape = SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat="Returned veterinary competitors for a coffee niche.",
        competitors=[SimpleNamespace(
            name="Roaster Leads",
            url="https://example.com/lead-pricing",
            pricing_model="$20-40 per qualified lead",
            description="Qualified wholesale coffee-roaster lead generation.",
        )],
    )

    assert TrafficMonetizationCrew._attributed_unit_value_evidence(
        SimpleNamespace(solution_landscapes=[landscape]),
        "CoffeeRoute",
        "lead_generation",
        "Wholesale coffee-roaster leads",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    ) is None


def test_affiliate_uses_only_attributed_exact_candidate_program_and_clears_other_routes():
    result = _result(
        monetization_model="Hybrid-Traffic",
        recommended_affiliate_programs=["LLM suggestion"],
        sponsored_listing_price="$999/month",
        estimated_monthly_revenue_range="$50,000/month",
    )
    evidence = _verified_unit(
        "affiliate",
        "affiliate_program",
        source_name="Coffee Roaster Supply Referral Program",
        source_url="https://example.com/affiliate",
        retrieved_quote="Exact-niche affiliate program pays 5-10% commission",
        value_low=None,
        value_high=None,
        commission_pct_low=5,
        commission_pct_high=10,
    )
    assert evidence is not None

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="affiliate",
        payer="vendor",
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        unit_value_evidence=evidence,
        solution=_solution("affiliate", "vendor"),
    )

    assert result.viability_verdict == "conditional"
    assert result.recommended_affiliate_programs == ["Coffee Roaster Supply Referral Program"]
    assert result.affiliate_commission_rate == "5-10%"
    assert result.estimated_monthly_revenue_range is None
    assert result.sponsored_listing_price is None
    assert result.monetization_confidence == "Low"


def test_generic_affiliate_program_is_not_exact_niche_evidence():
    competitor = SimpleNamespace(
        name="Generic Marketplace",
        url="https://example.com/affiliate",
        pricing_model="Affiliate program pays 5-10% commission",
        description="A broad consumer marketplace referral program.",
    )
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
    )])

    evidence = TrafficMonetizationCrew._attributed_unit_value_evidence(
        analysis,
        "CoffeeRoute",
        "affiliate",
        "Wholesale coffee-roaster lead calculator",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
    )

    assert evidence is None


def test_broad_one_token_affiliate_marketplace_is_not_exact_niche_evidence():
    competitor = SimpleNamespace(
        name="Coffee Marketplace",
        url="https://example.com/affiliate",
        pricing_model="Affiliate program pays 5-10% commission",
        description="A broad marketplace referral program for consumer purchases.",
    )
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
    )])

    provenance = VerifiedPricingProvenance(
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        route="affiliate",
        source_name="Coffee Marketplace",
        source_url="https://example.com/affiliate",
        retrieved_quote="Coffee affiliate program pays 5-10% commission",
        retrieved_at=datetime(2026, 8, 12, tzinfo=UTC),
        verification_marker="exact_quote_in_fetched_public_content",
        billing_basis="affiliate_program",
        commission_pct_low=5,
        commission_pct_high=10,
    )
    evidence = TrafficMonetizationCrew._attributed_unit_value_evidence(
        analysis,
        "CoffeeRoute",
        "affiliate",
        "Wholesale coffee-roaster lead calculator",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        niche_description="independent wholesale coffee roasters",
        verified_pricing_evidence=[provenance],
    )

    assert evidence is None


def test_wrong_billing_basis_does_not_count_as_structured_route_price():
    result = _result()

    TrafficMonetizationCrew._apply_deterministic_viability(
        result,
        value_capture_mode="lead_generation",
        payer="downstream_customer",
        projected_pageviews=(10_000, 20_000),
        deterministic_ad_revenue=(30, 100),
        unit_value_evidence={
            "route": "lead_generation",
            "source_name": "Roaster Listing",
            "source_url": "https://example.com/listing",
            "evidence_text": "$20-40 per listing per month",
            "value_low": 20,
            "value_high": 40,
            "billing_basis": "per_sponsored_listing_month",
        },
        solution=_solution("lead_generation", "downstream_customer"),
    )

    assert result.viability_verdict == "nonviable"
    assert result.lead_gen_price_per_lead is None


def test_keyword_demand_three_states_use_only_idea_relevant_rows():
    relevant = SimpleNamespace(
        solution_name="CoffeeRoute",
        niche_relevant_volume=900,
        validated_keywords=[{
            "keyword": "coffee roaster wholesale lead calculator",
            "search_volume": 900,
            "idea_intent_grade": 2,
        }],
    )
    contaminated = SimpleNamespace(
        solution_name="CoffeeRoute",
        niche_relevant_volume=0,
        total_volume=250_000,
        validated_keywords=[{
            "keyword": "coffee",
            "search_volume": 250_000,
            "idea_intent_grade": 0,
        }],
    )
    unmeasured = SimpleNamespace(
        solution_name="CoffeeRoute",
        niche_relevant_volume=None,
        validated_keywords=None,
        total_volume=250_000,
    )

    assert TrafficMonetizationCrew._qualified_keyword_volume([relevant], "CoffeeRoute") == 900
    assert TrafficMonetizationCrew._qualified_keyword_volume([contaminated], "CoffeeRoute") == 0
    assert TrafficMonetizationCrew._qualified_keyword_volume([unmeasured], "CoffeeRoute") is None


def test_keyword_prompt_excludes_irrelevant_big_volume_and_keeps_relevant_volume():
    validation = SimpleNamespace(
        solution_name="CoffeeRoute",
        niche_relevant_volume=900,
        validated_keywords=[
            {"keyword": "coffee", "search_volume": 250_000, "idea_intent_grade": 0},
            {
                "keyword": "coffee roaster wholesale lead calculator",
                "search_volume": 900,
                "idea_intent_grade": 2,
            },
        ],
    )

    formatted = TrafficMonetizationCrew()._format_keyword_data(
        [validation], "CoffeeRoute")

    assert "900 searches/month" in formatted
    assert "250,000" not in formatted
    assert "coffee roaster wholesale lead calculator" in formatted


def test_nested_route_is_canonical_and_missing_route_does_not_guess_from_prose():
    conflicting = SimpleNamespace(
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "lead buyer",
        },
        value_capture_mode="direct_user_payment",
    )
    missing = SimpleNamespace(
        commercial_route=None,
        pricing_strategy="affiliate with ads and sponsors",
    )

    assert TrafficMonetizationCrew._commercial_route_value(
        conflicting, "value_capture_mode") == "lead_generation"
    assert TrafficMonetizationCrew._commercial_route_value(
        missing, "value_capture_mode") is None


def test_analyze_uses_verified_pricing_provenance_not_llm_authored_price(monkeypatch):
    crew = TrafficMonetizationCrew()
    llm_result = _result(
        monetization_model="Lead-Gen",
        lead_gen_price_per_lead="$999 per lead",
        estimated_monthly_revenue_range="$50,000/month",
        monetization_confidence="High",
    )
    fake_crew = SimpleNamespace(
        kickoff=lambda **_kwargs: SimpleNamespace(pydantic=llm_result),
    )
    monkeypatch.setattr(crew, "crew", lambda: fake_crew)

    solution = SimpleNamespace(
        solution_name="CoffeeRoute",
        idea_id="idea-coffee",
        idea_revision=3,
        project_type="directory",
        description="A wholesale coffee-roaster lead calculator.",
        commercial_route={
            "access_model": "free",
            "value_capture_mode": "lead_generation",
            "payer": "downstream_customer",
            "source_user_payment_required": False,
        },
    )
    keyword_result = SimpleNamespace(
        solution_name="CoffeeRoute",
        niche_relevant_volume=100_000,
        validated_keywords=[{
            "keyword": "coffee roaster wholesale lead calculator",
            "search_volume": 100_000,
            "idea_intent_grade": 2,
        }],
    )
    competitor = SimpleNamespace(
        name="Coffee Roaster Leads",
        url="https://example.com/lead-pricing",
        pricing_model="$20-40 per qualified lead",
        description="Qualified wholesale coffee-roaster lead generation.",
        competitor_type="direct",
    )
    analysis = SimpleNamespace(solution_landscapes=[SimpleNamespace(
        solution_name="CoffeeRoute",
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        off_niche_caveat=None,
        competitors=[competitor],
        pricing_insights="Published per-lead pricing.",
        market_gaps=[],
    )])
    provenance = VerifiedPricingProvenance(
        candidate_idea_id="idea-coffee",
        candidate_idea_revision=3,
        route="lead_generation",
        source_name="Coffee Roaster Leads",
        source_url="https://example.com/lead-pricing",
        retrieved_quote="$20-40 per qualified lead for wholesale coffee roasters",
        retrieved_at=datetime(2026, 8, 12, tzinfo=UTC),
        verification_marker="exact_quote_in_fetched_public_content",
        value_low=20,
        value_high=40,
        billing_basis="per_lead",
    )

    result = crew.analyze(
        solution,
        [keyword_result],
        analysis,
        "wholesale coffee roasters",
        verified_pricing_evidence=[provenance],
    )

    assert result is not None
    assert result.economics_evaluated is True
    assert result.unit_value_evidence is not None
    assert result.unit_value_evidence.source_url == "https://example.com/lead-pricing"
    assert result.lead_gen_price_per_lead == "$20 - $40/lead"
    assert result.viability_verdict == "conditional"
    assert result.monetization_confidence == "Medium"
    assert "$999" not in (result.estimated_monthly_revenue_range or "")
