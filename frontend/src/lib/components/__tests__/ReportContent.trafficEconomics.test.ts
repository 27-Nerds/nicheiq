import { cleanup, render } from "@testing-library/svelte";
import { page } from "$app/state";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Report, TrafficMonetization } from "$lib/types/report";
import ReportContent from "../ReportContent.svelte";

const originalUrl = page.url;

beforeEach(() => {
  page.url = new URL("http://localhost/report?view=evidence&topic=market&detail=full") as typeof page.url;
});

afterEach(() => {
  cleanup();
  page.url = originalUrl;
});

function traffic(viability_verdict?: TrafficMonetization["viability_verdict"]): TrafficMonetization {
  return {
    solution_name: "CoffeeRoute",
    monetization_model: "Ad-Supported",
    estimated_monthly_pageviews: "1,000 - 5,000",
    traffic_source_breakdown: [],
    estimated_monthly_ad_revenue: "$3 - $25/month",
    recommended_ad_networks: [],
    estimated_monthly_affiliate_revenue: "$45,000/month",
    recommended_affiliate_programs: [],
    estimated_monthly_revenue_range: "$50,000/month",
    estimated_annual_revenue_range: "$600,000/year",
    funnel_target: "paid monitoring",
    qualified_actions: "5 - 20 qualified evaluations/month",
    conversion_assumptions: ["0.5%-1.0% candidate-relevant conversion"],
    estimated_funnel_value: "$100 - $800/month",
    monetization_rationale: "Ads do not clear the viability threshold.",
    scaling_strategy: "Scale immediately.",
    saas_alternative_viable: false,
    saas_vs_traffic_recommendation: "Do not scale.",
    viability_verdict,
  };
}

function report(traffic_monetization: TrafficMonetization): Report {
  return {
    niche: "coffee roasters",
    executive_summary: "A route test.",
    selected_solution_name: "CoffeeRoute",
    selection_rationale: "Candidate evidence.",
    competitor_profiles: [],
    generated_at: "2026-08-12T00:00:00Z",
    traffic_monetization,
  };
}

describe("ReportContent traffic economics", () => {
  it("suppresses contradictory totals for a typed nonviable fallback record", () => {
    const view = render(ReportContent, { props: { report: report(traffic("nonviable")) } });

    expect(view.getByText("nonviable")).toBeInTheDocument();
    expect(view.queryByText("$50,000/month")).not.toBeInTheDocument();
    expect(view.queryByText("$600,000/year")).not.toBeInTheDocument();
    expect(view.queryByText("$100 - $800/month")).not.toBeInTheDocument();
    expect(view.queryByText("5 - 20 qualified evaluations/month")).not.toBeInTheDocument();
    expect(view.queryByText("0.5%-1.0% candidate-relevant conversion")).not.toBeInTheDocument();
    expect(view.getByText("Traffic route rejected")).toBeInTheDocument();
    expect(view.queryByText("How this model could earn revenue")).not.toBeInTheDocument();
  });

  it("preserves the revenue total for a verdict-absent legacy fallback record", () => {
    const view = render(ReportContent, { props: { report: report(traffic(undefined)) } });

    expect(view.getByText("$50K/month")).toBeInTheDocument();
    expect(view.getByText("Estimated funnel value")).toBeInTheDocument();
    expect(view.getByText("0.5%-1.0% candidate-relevant conversion")).toBeInTheDocument();
  });

  it("links accepted unit-value attribution in the traffic-only fallback", () => {
    const candidateTraffic = traffic("conditional");
    candidateTraffic.unit_value_evidence = {
      route: "lead_generation",
      source_name: "Roaster Leads",
      source_url: "https://example.com/lead-pricing",
      evidence_text: "$20-40 per qualified wholesale coffee-roaster lead",
      value_low: 20,
      value_high: 40,
      billing_basis: "per_lead",
      retrieved_quote: "$20-40 per qualified wholesale coffee-roaster lead",
      verification_marker: "exact_quote_in_fetched_public_content",
    };
    const view = render(ReportContent, { props: { report: report(candidateTraffic) } });

    expect(view.getByRole("link", { name: "Roaster Leads" }))
      .toHaveAttribute("href", "https://example.com/lead-pricing");
    expect(view.getByText("$20-40 per qualified wholesale coffee-roaster lead"))
      .toBeInTheDocument();
    expect(view.getByText("$20 - $40 · Per lead")).toBeInTheDocument();
  });
});
