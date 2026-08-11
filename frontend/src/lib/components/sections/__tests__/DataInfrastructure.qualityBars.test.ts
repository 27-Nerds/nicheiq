import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import DataInfrastructure from "../DataInfrastructure.svelte";
import type { DataSourceResearchFull, EvaluatedDataSource } from "$lib/types/report";

/**
 * The Source Quality Analysis meters used to run every value through ONE lookup
 * that mapped "high" and "low" to the same 90, and then drew the Integration row
 * as `100 - that`. On real captured runs (integration_complexity is LOW 877x,
 * MEDIUM 555x, HIGH 451x across output/) that made the easiest integration and
 * the hardest one render an identical 10% bar, with MEDIUM drawing a FULLER
 * "good" bar than LOW. A prose coverage_score, which is what the pipeline
 * actually writes there, fell through to a flat 50% - a measurement-looking
 * meter for a value that was never measured.
 */
function source(
  provider: string,
  quality: EvaluatedDataSource["quality_metrics"],
): EvaluatedDataSource {
  return {
    provider,
    priority: "HIGH",
    priority_rationale: `${provider} rationale`,
    quality_metrics: quality,
  };
}

function report(sources: EvaluatedDataSource[]): DataSourceResearchFull {
  return {
    source_evaluation: {
      evaluated_sources: sources,
      recommended_stack: [],
      primary_risks: [],
    },
  } as unknown as DataSourceResearchFull;
}

/** Every quality row of the first evaluated card, as label -> bar fill (or null). */
function rows(container: HTMLElement): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  for (const row of container.querySelectorAll(".quality-row")) {
    const label = row.querySelector(".quality-label")?.textContent?.trim() ?? "";
    const bar = row.querySelector<HTMLElement>(".quality-bar");
    out[label] = bar ? (bar.style.getPropertyValue("--bar-fill") || null) : null;
  }
  return out;
}

describe("DataInfrastructure source quality meters", () => {
  afterEach(cleanup);

  it("does not draw the easiest and the hardest integration as the same bar", () => {
    const view = render(DataInfrastructure, {
      props: {
        data: report([
          source("Easy API", { integration_complexity: "LOW" }),
          source("Hard scrape", { integration_complexity: "HIGH" }),
        ]),
      },
    });

    const bars = Array.from(view.container.querySelectorAll(".quality-row"))
      .filter((row) => row.querySelector(".quality-label")?.textContent?.trim() === "Integration")
      .map((row) => row.querySelector<HTMLElement>(".quality-bar")?.style.getPropertyValue("--bar-fill"));

    expect(bars).toHaveLength(2);
    expect(bars[0]).not.toBe(bars[1]);
    // LOW complexity is the good end, so it must read fuller than HIGH.
    expect(parseInt(bars[0]!, 10)).toBeGreaterThan(parseInt(bars[1]!, 10));
  });

  it("orders LOW above MEDIUM above HIGH for integration effort", () => {
    const fills = ["LOW", "MEDIUM", "HIGH"].map((complexity) => {
      const view = render(DataInfrastructure, {
        props: {
          data: report([
            source("S", { integration_complexity: complexity as "LOW" | "MEDIUM" | "HIGH" }),
          ]),
        },
      });
      const fill = rows(view.container)["Integration"];
      cleanup();
      return parseInt(fill!, 10);
    });

    expect(fills[0]).toBeGreaterThan(fills[1]);
    expect(fills[1]).toBeGreaterThan(fills[2]);
  });

  it("reads a high cost as a low cost-viability bar, not a high one", () => {
    const view = render(DataInfrastructure, {
      props: { data: report([source("Pricey", { cost_viability: "HIGH" })]) },
    });

    expect(parseInt(rows(view.container)["Cost"]!, 10)).toBeLessThan(50);
  });

  it("omits the bar entirely when the value is prose rather than a band", () => {
    const view = render(DataInfrastructure, {
      props: {
        data: report([
          source("Prosey", {
            coverage_score: "Extensive EU and US product and ingredient label coverage",
            freshness: "daily",
          }),
        ]),
      },
    });

    const measured = rows(view.container);
    expect(measured["Coverage"]).toBeNull();
    // The stated value still shows; only the invented meter is gone.
    expect(view.getByText(/Extensive EU and US product/)).toBeInTheDocument();
    expect(measured["Freshness"]).toBe("90%");
  });

  // Verbatim from a captured run (output/**/discovery data, cosmetics niche).
  it("grades a coverage_score that does state a percentage", () => {
    const view = render(DataInfrastructure, {
      props: {
        data: report([
          source("Numeric", {
            coverage_score: "Extensive EU and US product and ingredient label coverage, ~85% market coverage",
          }),
        ]),
      },
    });

    expect(rows(view.container)["Coverage"]).toBe("85%");
  });

  /**
   * All three strings are verbatim from output/ (cosmetics + work-rights runs);
   * 388 of the 1,084 coverage_score values that reach the percent fallback state
   * a range like these. Reading the range's TOP drew a meter above anything the
   * source claimed — "~50-60%" rendered as a 60% bar. The low end is a number
   * the source did state and can only understate.
   */
  it.each([
    ["Moderate coverage of cosmetic ingredients with hazard ratings, ~60-70%", "60%"],
    ["Partial coverage (~50-60%) of cosmetic ingredients", "50%"],
    [
      "Approximately 70-90% coverage of public policy/operational guidance for work rights across national visa categories (some open datasets available)",
      "70%",
    ],
  ])("grades a stated range at its lower bound, not its upper: %s", (coverage_score, expected) => {
    const view = render(DataInfrastructure, {
      props: { data: report([source("Ranged", { coverage_score })]) },
    });

    expect(rows(view.container)["Coverage"]).toBe(expected);
  });

  /**
   * Verbatim from output/ (13 of 2,802 captured coverage_score values). These lead
   * with a band word AND state their own range, so trying MAGNITUDE_BANDS first sent
   * them to 90 - at or ABOVE the ceiling the source itself named. A range the source
   * committed to outranks the band word that precedes it.
   */
  it.each([
    ["High coverage for US breweries (estimate 70-85%); international coverage partial", "70%"],
    [
      "High for Stable Diffusion community models (~70-90% of popular SD variants), limited outside that ecosystem",
      "70%",
    ],
    [
      "High for registered legal entities across many jurisdictions; ~70-90% coverage of incorporated brands in major markets (lower for small sole-proprietors)",
      "70%",
    ],
  ])("prefers a stated range over the band word that opens the value: %s", (coverage_score, expected) => {
    const view = render(DataInfrastructure, {
      props: { data: report([source("Banded", { coverage_score })]) },
    });

    expect(rows(view.container)["Coverage"]).toBe(expected);
  });

  /**
   * The converse, and the reason only a RANGE outranks the band: a lone figure in
   * prose is often not a magnitude at all. Verbatim from output/ (5 occurrences) -
   * ">20% revenue/user" is a share of revenue, so grading the cost at 20 would draw
   * an expensive source as an 80% cost-viability bar.
   */
  it("does not let an incidental lone percentage override the band word", () => {
    const view = render(DataInfrastructure, {
      props: {
        data: report([
          source("Pricey", {
            cost_viability: "HIGH (commercial pricing, cost likely >20% revenue/user at scale)",
          }),
        ]),
      },
    });

    expect(rows(view.container)["Cost"]).toBe("10%");
  });

  /**
   * The range separator has to match case-insensitively. STATED_PERCENT runs on the
   * raw value while the bands run on a lower-cased copy, so an uppercase "TO" missed
   * group 1 and the match fell through to the range's UPPER bound - silently
   * restoring the exact overstatement this meter was fixed to remove.
   */
  it.each([
    ["50 TO 60%", "50%"],
    ["40 To 60%", "40%"],
  ])("reads an upper-cased range separator at the lower bound too: %s", (coverage_score, expected) => {
    const view = render(DataInfrastructure, {
      props: { data: report([source("Shouty", { coverage_score })]) },
    });

    expect(rows(view.container)["Coverage"]).toBe(expected);
  });

  // "Near real-time" (151 values) and "hourly" (37) are the freshest things the
  // pipeline writes and drew no bar at all.
  it.each([
    ["Near real-time", "95%"],
    ["near-real-time (seconds-to-minutes upon upload)", "95%"],
    ["hourly", "92%"],
  ])("grades maximally fresh values instead of omitting the bar: %s", (freshness, expected) => {
    const view = render(DataInfrastructure, {
      props: { data: report([source("Fresh", { freshness })]) },
    });

    expect(rows(view.container)["Freshness"]).toBe(expected);
  });

  // Design-rule 16: `.quality-row` is a fixed `80px 1fr 60px` grid, so an omitted
  // bar must still occupy the middle rail or the label and value columns slide.
  it("keeps the three-column rail when the bar is omitted", () => {
    const view = render(DataInfrastructure, {
      props: {
        data: report([
          source("Prosey", { coverage_score: "Broad but unquantified label coverage" }),
        ]),
      },
    });

    const coverageRow = Array.from(view.container.querySelectorAll(".quality-row")).find(
      (row) => row.querySelector(".quality-label")?.textContent?.trim() === "Coverage",
    )!;

    expect(coverageRow.querySelector(".quality-bar")).toBeNull();
    expect(coverageRow.querySelector(".quality-bar-wrap--empty")).not.toBeNull();
    expect(coverageRow.children).toHaveLength(3);
  });
});
