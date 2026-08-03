import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { MarketSizing, Report } from "$lib/types/report";
import ReportEvidenceSummary from "../ReportEvidenceSummary.svelte";

afterEach(cleanup);

const marketSizing: MarketSizing = {
  total_addressable_market: "$1.03-$2.06M",
  serviceable_available_market: "$0.000227-$0.000454M",
  serviceable_obtainable_market_y1: "$0.000001-$0.000009M",
  serviceable_obtainable_market_y3: "$0.000011-$0.000045M",
  primary_methodology: "Keyword-anchored bottom-up",
  methodology_explanation: "Derived from search demand.",
  data_sources_used: ["DataForSEO"],
  risk_factors: [
    "Search demand sits below the 5,000-search stop-condition threshold",
    "TAM is far below the $50M Income Potential threshold",
  ],
};

function report(): Report {
  return {
    niche: "Kubernetes model serving",
    executive_summary: "A generated summary.",
    selected_solution_name: "Cold Start Atlas",
    selection_rationale: "The recommendation held after validation.",
    competitor_profiles: [],
    generated_at: "2026-07-25T12:00:00.000Z",
    market_sizing: marketSizing,
    pricing_strategy: {
      pricing_model: "Freemium",
      pricing_rationale: "Pains show an average WTP score of 0.43 overall.",
      recommended_starter_price: "$19/mo",
    } as Report["pricing_strategy"],
  };
}

describe("ReportEvidenceSummary market panel", () => {
  it("renders sub-dollar $M figures at a readable unit", () => {
    const view = render(ReportEvidenceSummary, { props: { report: report(), topic: "market" } });

    expect(view.getByText("$227-$454")).toBeInTheDocument();
    expect(view.getByText("$1-$9")).toBeInTheDocument();
    expect(view.getByText("$1.03M-$2.06M")).toBeInTheDocument();
    expect(view.queryByText(/0\.000227/)).not.toBeInTheDocument();
  });

  it("leaves the entry price untouched", () => {
    const view = render(ReportEvidenceSummary, { props: { report: report(), topic: "market" } });

    expect(view.getByText("$19/mo")).toBeInTheDocument();
  });

  it("strips internal gate names and stale metric names from backend prose", () => {
    const view = render(ReportEvidenceSummary, { props: { report: report(), topic: "market" } });

    expect(
      view.getByText("Search demand sits below our 5,000-search minimum-demand bar"),
    ).toBeInTheDocument();
    expect(
      view.getByText("TAM is far below the $50M scale bar we use for venture-scale opportunities"),
    ).toBeInTheDocument();
    expect(
      view.getByText("Pains show an average commercial-intent score of 43/100 overall."),
    ).toBeInTheDocument();
    expect(view.queryByText(/stop-condition|Income Potential|WTP/)).not.toBeInTheDocument();
  });
});
