import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { DetailedPainPoint, PainPointAnalytics, SolutionDetails } from "$lib/types/report";
import PainAnalysis from "../PainAnalysis.svelte";

afterEach(cleanup);

const originalAnimate = Element.prototype.animate;

beforeAll(() => {
  Object.defineProperty(Element.prototype, "animate", {
    configurable: true,
    value: () => {
      const animation: Partial<Animation> & { onfinish: Animation["onfinish"] } = {
        cancel: () => undefined,
        currentTime: 0,
        effect: null,
        onfinish: null,
        playState: "finished",
      };
      Object.defineProperty(animation, "onfinish", {
        configurable: true,
        get: () => null,
        set: (callback: Animation["onfinish"]) => {
          if (callback) {
            queueMicrotask(() =>
              callback.call(animation as Animation, {
                currentTime: 0,
                timelineTime: 0,
              } as AnimationPlaybackEvent),
            );
          }
        },
      });
      return animation as Animation;
    },
  });
});

afterAll(() => {
  if (originalAnimate) {
    Object.defineProperty(Element.prototype, "animate", {
      configurable: true,
      value: originalAnimate,
    });
  } else {
    Reflect.deleteProperty(Element.prototype, "animate");
  }
});

function pain(
  title: string,
  severity_score: number,
  overrides: Partial<DetailedPainPoint> = {},
): DetailedPainPoint {
  return {
    title,
    description: `${title} description`,
    mention_count: 8,
    severity_score,
    commercial_intent: 0.6,
    opportunity_level: "high",
    representative_quotes: [],
    source_platforms: ["reddit"],
    categories: [],
    source_post_ids: [],
    ...overrides,
  };
}

const analytics: PainPointAnalytics = {
  total_pain_points: 2,
  high_severity_count: 2,
  quadrant_distribution: {
    high_severity_high_wtp: 2,
    high_severity_low_wtp: 0,
    low_severity_high_wtp: 0,
    low_severity_low_wtp: 0,
  },
};

const solution: SolutionDetails = {
  solution_name: "TruckStockOptimizer",
  description: "Optimize inventory for each service truck.",
  value_proposition: "Generic value proposition that is not a saved pain mapping.",
  core_features: ["Unrelated feature assigned by array position"],
  pain_points_addressed: ["Cannot balance truck stock against return-trip risk"],
};

describe("PainAnalysis selected-solution scope", () => {
  it("shows only explicitly linked pain in the journey and never invents a feature mapping", () => {
    const unrelatedPain = "Cannot maintain one appliance-specific record";
    const selectedPain = "Cannot balance truck stock against return-trip risk";
    const view = render(PainAnalysis, {
      props: {
        painPoints: [pain(unrelatedPain, 0.95), pain(selectedPain, 0.81)],
        analytics,
        solution,
        corePainPoint: {
          title: selectedPain,
          severity_score: 0.81,
          commercial_intent_score: 0.6,
          representative_quote: "I either carry too much or drive back for parts.",
          source_platform: "reddit",
        },
      },
    });

    expect(view.getByRole("tab", { name: "Selected Problem" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(view.getByText(selectedPain)).toBeInTheDocument();
    expect(view.queryByText(unrelatedPain)).not.toBeInTheDocument();
    expect(view.getByText("Mapping Unavailable")).toBeInTheDocument();
    expect(
      view.getByText("No direct problem-to-solution mapping was retained for this problem."),
    ).toBeInTheDocument();
    expect(view.queryByText("Unrelated feature assigned by array position")).not.toBeInTheDocument();
    expect(
      view.queryByText("Generic value proposition that is not a saved pain mapping."),
    ).not.toBeInTheDocument();
  });

  it("keeps unrelated pains in an explicitly niche-wide analysis", async () => {
    const unrelatedPain = "Cannot maintain one appliance-specific record";
    const selectedPain = "Cannot balance truck stock against return-trip risk";
    const view = render(PainAnalysis, {
      props: {
        painPoints: [pain(unrelatedPain, 0.95), pain(selectedPain, 0.81)],
        analytics,
        solution,
        corePainPoint: {
          title: selectedPain,
          severity_score: 0.81,
          commercial_intent_score: 0.6,
          representative_quote: "I either carry too much or drive back for parts.",
          source_platform: "reddit",
        },
      },
    });

    await fireEvent.click(view.getByRole("tab", { name: "Niche Analysis" }));

    await waitFor(() => {
      expect(view.getByRole("heading", { name: "All retained pain research" })).toBeInTheDocument();
    });
    expect(view.getByText(unrelatedPain)).toBeInTheDocument();
    expect(
      view.getByText(/not claims that TruckStockOptimizer addresses every problem shown here/i),
    ).toBeInTheDocument();
  });
});

/**
 * ProgressRing's `color="auto"` is a GOODNESS ramp (>=0.7 success/green,
 * >=0.4 warning, else error/red). Severity is a badness scale, so pointing
 * `auto` at it inverts the colour against the label: the most severe pain in
 * the run painted green and the mildest one red. Real captured runs are full
 * of severity >= 0.7 values, so this was the common case, not an edge one.
 */
describe("PainAnalysis severity ring colour direction", () => {
  function severityRingStroke(container: HTMLElement): string | null {
    const item = Array.from(container.querySelectorAll(".score-ring-item"))
      .find((node) => node.textContent?.includes("Severity"));
    return item?.querySelector("circle:not(.progress-ring-bg)")?.getAttribute("stroke") ?? null;
  }

  it("never paints a high-severity pain with the success colour", async () => {
    const view = render(PainAnalysis, {
      props: { painPoints: [pain("Severe billing failure", 0.95)], analytics, solution },
    });

    await fireEvent.click(view.getByRole("tab", { name: "Niche Analysis" }));
    await waitFor(() => expect(view.container.querySelector(".score-ring-item")).not.toBeNull());

    expect(severityRingStroke(view.container)).toBe("var(--color-error)");
  });

  it("uses the same severity colour whatever the score, so the ramp cannot invert", async () => {
    const view = render(PainAnalysis, {
      props: { painPoints: [pain("Mild annoyance", 0.2)], analytics, solution },
    });

    await fireEvent.click(view.getByRole("tab", { name: "Niche Analysis" }));
    await waitFor(() => expect(view.container.querySelector(".score-ring-item")).not.toBeNull());

    expect(severityRingStroke(view.container)).toBe("var(--color-error)");
  });
});
