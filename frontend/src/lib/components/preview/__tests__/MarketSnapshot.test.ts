import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import MarketSnapshot from "../MarketSnapshot.svelte";

/**
 * `discussion_growth_pct` is (recent 6 months - previous 6) / previous 6 over RAW
 * captured post counts. The pipeline's only guard is a non-zero divisor, so a
 * baseline of a handful of posts prints a confident triple-digit headline.
 *
 * The two small-baseline shapes below are the exact monthly totals from captured
 * runs under output/ (discovery_data_58f7f62a… and discovery_data_4a66d5f5…); the
 * healthy one is the shape of the majority of that corpus.
 */
function months(counts: number[]): { month: string; count: number }[] {
  return counts.map((count, i) => ({
    month: `2026-${String((i % 12) + 1).padStart(2, "0")}`,
    count,
  }));
}

/** 7 discussions in the baseline half, 27 in the recent half. Renders "+286%". */
const TINY_BASELINE = months([1, 1, 2, 1, 1, 1, 3, 4, 5, 5, 6, 4]);
/** 6 in the baseline half, 11 in the recent half. Renders "+83%". */
const TINIEST_BASELINE = months([1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 1]);
/** 24 in the baseline half, 40 in the recent half. Renders "+67%". */
const HEALTHY_BASELINE = months([4, 4, 4, 4, 4, 4, 6, 6, 7, 7, 7, 7]);

const baseProps = {
  discussionsAnalyzed: 120,
  communityCount: 8,
  totalEngagement: 3400,
};

describe("MarketSnapshot growth headline", () => {
  afterEach(cleanup);

  it("suppresses the percentage when the baseline half is too small to divide by", () => {
    const view = render(MarketSnapshot, {
      props: { ...baseProps, trend: TINY_BASELINE, growthPct: 286 },
    });

    expect(view.queryByText(/286%/)).toBeNull();
    expect(view.getByText("27 vs 7")).toBeInTheDocument();
    expect(view.getByText("discussions captured")).toBeInTheDocument();
    expect(
      view.getByText(/Too few captured discussions to state a percentage/),
    ).toBeInTheDocument();
  });

  it("suppresses a double-digit percentage over the same too-small baseline", () => {
    const view = render(MarketSnapshot, {
      props: { ...baseProps, trend: TINIEST_BASELINE, growthPct: 83 },
    });

    expect(view.queryByText(/83%/)).toBeNull();
    expect(view.getByText("11 vs 6")).toBeInTheDocument();
  });

  it("keeps the percentage once the baseline is large enough, and names its counts", () => {
    const view = render(MarketSnapshot, {
      props: { ...baseProps, trend: HEALTHY_BASELINE, growthPct: 67 },
    });

    expect(view.getByText(/↑ 67%/)).toBeInTheDocument();
    expect(view.getByText("discussion volume")).toBeInTheDocument();
    // The denominator travels with the rate at the first level of the card.
    expect(
      view.getByText(/40 vs 24 discussions, recent 6 months vs previous 6/),
    ).toBeInTheDocument();
  });

  it("renders no growth block at all when the pipeline reported no growth figure", () => {
    const view = render(MarketSnapshot, {
      props: { ...baseProps, trend: HEALTHY_BASELINE, growthPct: null },
    });

    expect(view.queryByText("discussion volume")).toBeNull();
    expect(view.queryByText("discussions captured")).toBeNull();
  });
});
