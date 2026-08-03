import { describe, expect, it } from "vitest";
import { render } from "@testing-library/svelte";
import SolutionHero from "$lib/components/sections/SolutionHero.svelte";

/**
 * A rebuilt idea has no acquisition-cost figure on purpose: the earlier estimate priced the
 * product the rebuild replaced, and re-estimating needs payability and competitive research
 * the rebuild does not redo. Hiding the tile made a deliberate gap look like an oversight.
 */
const base = {
  solution_name: "HouseNutIndex",
  description: "Benchmarks house-nut ranges for independent rooms.",
} as Record<string, unknown>;

// Minimal dashboard: the hero reads the snapshot for its identity block only.
const dashboard = {
  recommended_solution_snapshot: { solution_name: "HouseNutIndex" },
  go_no_go_verdict: { verdict: "Conditional" },
} as Record<string, unknown>;

const renderHero = (solution: Record<string, unknown>) =>
  render(SolutionHero, {
    props: { solution, dashboard, selectionRationale: "" } as never,
  });

describe("SolutionHero acquisition cost", () => {
  it("explains the gap instead of hiding it when the idea was rebuilt", () => {
    const { getByText } = renderHero({ ...base, rebuild_origin: "parity_pivot" });
    expect(getByText("Not estimated")).toBeTruthy();
  });

  it("says nothing when there is no CAC and no rebuild to explain it", () => {
    const { queryByText } = renderHero(base);
    expect(queryByText("Not estimated")).toBeNull();
  });

  it("shows the real figure when one exists", () => {
    const { getByText, queryByText } = renderHero({
      ...base, rebuild_origin: "parity_pivot", estimated_cac_organic: "$15-45 per customer",
    });
    expect(getByText("$15-45 per customer")).toBeTruthy();
    expect(queryByText("Not estimated")).toBeNull();
  });
});
