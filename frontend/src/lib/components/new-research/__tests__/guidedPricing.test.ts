import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import ProcessTimeline from "../ProcessTimeline.svelte";
import StickyCtaBar from "../StickyCtaBar.svelte";

const stageCosts = {
  discovery: 5,
  deep_research: 15,
  landing_page: 5,
  regenerate_ideas: 2,
  seed_idea: 2,
  guided: { s1: 1, s2_4: 3, s5: 1, total: 5 },
};

afterEach(cleanup);

describe("guided research pricing", () => {
  it("shows each approval-priced Discovery segment instead of the flat Discovery price", () => {
    const view = render(ProcessTimeline, {
      props: { stageCosts, guided: true },
    });

    expect(view.getByText("1 credit now")).toBeInTheDocument();
    expect(view.getByText("3 credits after approval")).toBeInTheDocument();
    expect(view.getByText("15 credits later")).toBeInTheDocument();
    expect(view.queryByText("5 credits · ~15 min")).toBeNull();
  });

  it("describes the first guided purchase as a niche checkpoint", () => {
    const view = render(StickyCtaBar, {
      props: {
        visible: true,
        niche: "Freelance bookkeepers",
        creditCost: 1,
        loading: false,
        disabled: false,
        hasCredits: true,
        stageCost: 1,
        stageName: "guided research",
        ctaLabel: "Start guided research",
      },
    });

    expect(view.getByText("1 credit · niche checkpoint first")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start guided research" })).toBeInTheDocument();
    expect(view.queryByText(/first ideas ~15 min/)).toBeNull();
  });
});
