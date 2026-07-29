import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { Report } from "$lib/types/report";
import UnifiedHero from "../UnifiedHero.svelte";

afterEach(cleanup);

describe("UnifiedHero heading hierarchy", () => {
  const props = {
    report: {} as Report,
    nicheName: "independent bike repair shops",
    nicheDescription: "Research for independent operators.",
    funnelStats: {
      scanned: 0,
      relevant: 0,
      analyzed: 0,
      problems: 0,
    },
    previewMode: true,
    heroZoneOnly: true,
  };

  it("keeps the shared preview heading subordinate by default", () => {
    const view = render(UnifiedHero, {
      props,
    });

    expect(
      view.getByRole("heading", {
        level: 2,
        name: "Independent Bike Repair Shops",
      }),
    ).toBeInTheDocument();
    expect(view.container.querySelector("h1")).toBeNull();
  });

  it("uses the report niche as the single page-level heading when requested", () => {
    const view = render(UnifiedHero, {
      props: {
        ...props,
        headingLevel: 1,
      },
    });

    expect(
      view.getByRole("heading", {
        level: 1,
        name: "Independent Bike Repair Shops",
      }),
    ).toBeInTheDocument();
    expect(view.container.querySelectorAll("h1")).toHaveLength(1);
  });
});

describe("UnifiedHero metric truthfulness", () => {
  const baseProps = {
    nicheName: "independent bike repair shops",
    nicheDescription: "Research for independent operators.",
    funnelStats: {
      scanned: 0,
      relevant: 0,
      analyzed: 0,
      problems: 0,
    },
  };

  function makeReport({
    confidenceScore,
    marketFitScore,
    saturationScore,
  }: {
    confidenceScore: number | null;
    marketFitScore: number | null;
    saturationScore: number | null;
  }): Report {
    return {
      executive_dashboard: {
        confidence_score: confidenceScore,
        research_depth_label: "Standard Research",
        key_metrics: {
          market_fit_score: marketFitScore,
        },
      },
      // These aliases are intentionally populated. An explicit null in the
      // current dashboard must not silently become this legacy value.
      market_analytics: {
        overall_opportunity_score: 0.5,
        selection_confidence: 0.5,
      },
      competitive_analytics: {
        market_saturation_score: saturationScore,
      },
    } as unknown as Report;
  }

  it("keeps explicit missing metrics distinct from observed zero", () => {
    const view = render(UnifiedHero, {
      props: {
        ...baseProps,
        report: makeReport({
          confidenceScore: null,
          marketFitScore: null,
          saturationScore: null,
        }),
      },
    });

    expect(
      view.container.querySelector(".verdict-percentage"),
    ).toHaveTextContent("N/A");
    expect(view.getByText("NOT AVAILABLE")).toBeInTheDocument();
    expect(
      view.getByLabelText("Market Fit: not available"),
    ).toBeInTheDocument();

    const saturationLabel = view.getByText("Saturation");
    expect(saturationLabel.previousElementSibling).toHaveTextContent("Unknown");

    const signalLabels = Array.from(
      view.container.querySelectorAll(".signal-label"),
    ).map((element) => element.textContent);
    expect(signalLabels).not.toContain("Opportunity");
  });

  it("renders an observed zero as zero rather than unavailable", () => {
    const view = render(UnifiedHero, {
      props: {
        ...baseProps,
        report: makeReport({
          confidenceScore: 0,
          marketFitScore: 0,
          saturationScore: 0,
        }),
      },
    });

    expect(
      view.container.querySelector(".verdict-percentage"),
    ).toHaveTextContent("0%");
    expect(view.getByLabelText("Market Fit: 0%")).toBeInTheDocument();
    expect(
      view.queryByLabelText("Market Fit: not available"),
    ).not.toBeInTheDocument();

    const saturationLabel = view.getByText("Saturation");
    expect(saturationLabel.previousElementSibling).toHaveTextContent("Low");
  });

  it("explains the summary and research-depth measures without false verdict claims", () => {
    const view = render(UnifiedHero, {
      props: {
        ...baseProps,
        report: makeReport({
          confidenceScore: 0.72,
          marketFitScore: 0.7,
          saturationScore: 0.4,
        }),
      },
    });

    expect(
      view.getByText(/Missing dimensions are left out, not treated as zero/),
    ).toBeInTheDocument();
    expect(
      view.getByText(/The recommendation is evaluated separately/),
    ).toBeInTheDocument();
    expect(view.queryByText(/Directly determines/)).not.toBeInTheDocument();
    expect(view.queryByText(/all thresholds met/)).not.toBeInTheDocument();

    expect(
      view.getByText(/The tier uses distinct source posts/),
    ).toBeInTheDocument();
    expect(
      view.getByText(/It does not measure how attractive the opportunity is/),
    ).toBeInTheDocument();
  });
});
