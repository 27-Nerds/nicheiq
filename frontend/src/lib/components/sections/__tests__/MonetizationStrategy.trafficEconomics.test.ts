import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { PricingStrategy, TrafficMonetization } from "$lib/types/report";
import MonetizationStrategy from "../MonetizationStrategy.svelte";

afterEach(cleanup);

const pricingData: PricingStrategy = {
  solution_name: "CoffeeRoute",
  pricing_model: "Freemium",
  pricing_rationale: "The paid offer follows a qualified free evaluation.",
};

function traffic(overrides: Partial<TrafficMonetization> = {}): TrafficMonetization {
  return {
    solution_name: "CoffeeRoute",
    monetization_model: "Free-Tool-Funnel",
    estimated_monthly_pageviews: "900 - 1,200",
    traffic_source_breakdown: [{ source: "organic_search", percentage: "100%" }],
    estimated_monthly_ad_revenue: "$3 - $6/month",
    recommended_ad_networks: [],
    estimated_monthly_affiliate_revenue: "$0 - $0",
    recommended_affiliate_programs: [],
    estimated_monthly_revenue_range: "$100 - $800/month",
    estimated_annual_revenue_range: "$1,200 - $9,600/year",
    monetization_rationale: "Qualified actions carry the downstream value.",
    scaling_strategy: "Validate the funnel before scaling acquisition.",
    saas_alternative_viable: true,
    saas_vs_traffic_recommendation: "Use the free surface as a measured funnel.",
    viability_verdict: "conditional",
    funnel_target: "paid monitoring",
    qualified_actions: "5 - 20 qualified evaluations/month",
    conversion_assumptions: [
      "0.5%-1.0% of candidate-relevant visits complete an evaluation",
    ],
    estimated_funnel_value: "$100 - $800/month",
    ...overrides,
  };
}

describe("traffic route economics", () => {
  it("renders the typed viability and qualified funnel economics", () => {
    const view = render(MonetizationStrategy, {
      props: { pricingData, trafficData: traffic() },
    });

    expect(view.getByText("Conditional")).toBeInTheDocument();
    expect(view.getByText("paid monitoring")).toBeInTheDocument();
    expect(view.getByText("5 - 20 qualified evaluations/month")).toBeInTheDocument();
    expect(view.getByText("$100 - $800/month")).toBeInTheDocument();
    expect(
      view.getByText("0.5%-1.0% of candidate-relevant visits complete an evaluation"),
    ).toBeInTheDocument();
  });

  it("keeps legacy traffic records renderable when typed route fields are absent", () => {
    const view = render(MonetizationStrategy, {
      props: {
        pricingData,
        trafficData: traffic({
          viability_verdict: undefined,
          funnel_target: undefined,
          qualified_actions: undefined,
          conversion_assumptions: undefined,
          estimated_funnel_value: undefined,
        }),
      },
    });

    expect(view.getByText("Free-Tool-Funnel")).toBeInTheDocument();
    expect(view.queryByText("Route viability")).not.toBeInTheDocument();
  });

  it("suppresses contradictory totals and roadmaps for typed nonviable routes", () => {
    const contaminatedPricing: PricingStrategy = {
      ...pricingData,
      pricing_model: "Ad-Supported-Free",
      pricing_confidence: "High",
      estimated_monthly_ad_revenue: "$50,000/month",
      estimated_monthly_affiliate_revenue: "$45,000/month",
    };
    const view = render(MonetizationStrategy, {
      props: {
        pricingData: contaminatedPricing,
        trafficData: traffic({
          viability_verdict: "nonviable",
          monetization_confidence: "Low",
          estimated_monthly_revenue_range: "$50,000/month",
          estimated_annual_revenue_range: "$600,000/year",
          year3_monthly_revenue: "$1,000,000/month",
          full_potential_monthly_revenue: "$2,000,000/month",
          revenue_milestones: [{
            traffic: "1,000",
            ad_revenue: "$50,000",
            unlock: "Everything",
            total_potential: "$2,000,000",
          }],
        }),
      },
    });

    expect(view.getByText("Nonviable")).toBeInTheDocument();
    expect(view.queryByText("$50,000/month")).not.toBeInTheDocument();
    expect(view.queryByText("$1,000,000/month")).not.toBeInTheDocument();
    expect(view.queryByText("$2,000,000/month")).not.toBeInTheDocument();
    expect(view.queryByText("$100 - $800/month")).not.toBeInTheDocument();
    expect(view.queryByText("paid monitoring")).not.toBeInTheDocument();
    expect(
      view.queryByText("0.5%-1.0% of candidate-relevant visits complete an evaluation"),
    ).not.toBeInTheDocument();
    expect(view.queryByText("Revenue Potential at Scale")).not.toBeInTheDocument();
    expect(view.queryByText("High confidence")).not.toBeInTheDocument();
    expect(view.queryByText("$45,000/month")).not.toBeInTheDocument();
    expect(view.getByText("Low confidence")).toBeInTheDocument();
    expect(view.getByText("$3 - $6/month")).toBeInTheDocument();
  });

  it("suppresses SaaS-shaped pricing cards when the typed traffic route is nonviable", () => {
    const contaminatedPricing: PricingStrategy = {
      ...pricingData,
      pricing_model: "Freemium",
      recommended_starter_price: "$99/month",
      recommended_pro_price: "$499/month",
      pricing_confidence: "High",
      estimated_arpu: "$250/month",
      estimated_ltv: "$50,000",
      ltv_to_cac_ratio: "10:1",
    };
    const view = render(MonetizationStrategy, {
      props: {
        pricingData: contaminatedPricing,
        trafficData: traffic({ viability_verdict: "nonviable" }),
      },
    });

    expect(view.getByText("Traffic Route Rejected")).toBeInTheDocument();
    expect(view.getByText("Deterministic route assessment")).toBeInTheDocument();
    expect(view.queryByText("Pricing model and revenue projections")).not.toBeInTheDocument();
    expect(view.queryByText("$99/month")).not.toBeInTheDocument();
    expect(view.queryByText("$499/month")).not.toBeInTheDocument();
    expect(view.queryByText("$250/month")).not.toBeInTheDocument();
    expect(view.queryByText("$50,000")).not.toBeInTheDocument();
    expect(view.queryByText("High confidence")).not.toBeInTheDocument();
  });

  it("links the accepted candidate-specific unit-value source", () => {
    const view = render(MonetizationStrategy, {
      props: {
        pricingData,
        trafficData: traffic({
          unit_value_evidence: {
            route: "lead_generation",
            source_name: "Roaster Leads",
            source_url: "https://example.com/lead-pricing",
            evidence_text: "$20-40 per qualified wholesale coffee-roaster lead",
            value_low: 20,
            value_high: 40,
            billing_basis: "per_lead",
            retrieved_quote: "$20-40 per qualified wholesale coffee-roaster lead",
            verification_marker: "exact_quote_in_fetched_public_content",
          },
        }),
      },
    });

    expect(view.getByRole("link", { name: "Roaster Leads" }))
      .toHaveAttribute("href", "https://example.com/lead-pricing");
    expect(view.getByText("$20-40 per qualified wholesale coffee-roaster lead"))
      .toBeInTheDocument();
    expect(view.getByText("$20 - $40 · Per lead")).toBeInTheDocument();
  });

  it("never turns a non-http evidence URL into a link", () => {
    const view = render(MonetizationStrategy, {
      props: {
        pricingData,
        trafficData: traffic({
          unit_value_evidence: {
            route: "lead_generation",
            source_name: "Unsafe Source",
            source_url: "javascript:alert(1)",
            evidence_text: "$20 per lead",
            value_low: 20,
            value_high: 20,
            billing_basis: "per_lead",
          },
        }),
      },
    });

    expect(view.queryByRole("link", { name: "Unsafe Source" })).not.toBeInTheDocument();
    expect(view.getByText("Unsafe Source")).toBeInTheDocument();
  });
});
