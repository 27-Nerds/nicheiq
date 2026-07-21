import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import DecisionRail from "../DecisionRail.svelte";
import type { SelectionJourney } from "$lib/selection/decisionJourney";

function journey(overrides: Partial<SelectionJourney> = {}): SelectionJourney {
  return {
    shortlist: {
      version: 5,
      maxItems: 3,
      items: [
        { ideaId: "idea-a", ideaRevision: 2, title: "Signal desk" },
        { ideaId: "idea-b", ideaRevision: 4, title: "Evidence map" },
      ],
    },
    tasks: [
      {
        key: "constraints",
        title: "Your build constraints",
        description: "Time, budget, team, and advantages are saved.",
        status: "complete",
        statusLabel: "Complete",
      },
      {
        key: "compare",
        title: "Compare finalists",
        description: "See the meaningful differences.",
        status: "recommended",
        statusLabel: "Recommended",
      },
      {
        key: "risks",
        title: "Check the evidence",
        description: "Review evidence and open questions.",
        status: "available",
        statusLabel: "Ready",
      },
      {
        key: "tests",
        title: "Plan a test",
        description: "Start from a tracked assumption.",
        status: "optional",
        statusLabel: "Optional",
      },
      {
        key: "alternatives",
        title: "Explore variants",
        description: "Create variants or generate more ideas.",
        status: "optional",
        statusLabel: "Optional",
      },
    ],
    recommendation: {
      target: "compare",
      title: "Compare fit for you",
      description: "See how each finalist fits your saved constraints.",
      actionLabel: "Compare finalists",
      ideas: [
        { ideaId: "idea-a", ideaRevision: 2, title: "Signal desk" },
        { ideaId: "idea-b", ideaRevision: 4, title: "Evidence map" },
      ],
    },
    deepResearch: { eligible: true, optionalWorkRequired: false, blockers: [] },
    ...overrides,
  };
}

function callbacks() {
  return {
    onOpenCandidates: vi.fn(),
    onRunRecommendation: vi.fn(),
    onRetrySave: vi.fn(),
    onReloadSave: vi.fn(),
    onEditConstraints: vi.fn(),
    onAddResearchLead: vi.fn(),
    onRemoveShortlistItem: vi.fn(),
    onOpenCompare: vi.fn(),
    onOpenRisks: vi.fn(),
    onOpenTests: vi.fn(),
    onOpenAlternatives: vi.fn(),
    onStartDeepResearch: vi.fn(),
  };
}

afterEach(cleanup);

describe("DecisionRail", () => {
  it("renders exact shortlist revisions, novice task states, and Deep Research cost", () => {
    const view = render(DecisionRail, {
      props: {
        journey: journey(),
        deepResearchCost: 100,
        ...callbacks(),
      },
    });

    expect(view.getByRole("complementary", { name: "Your decision" })).toBeInTheDocument();
    expect(view.getByLabelText("2 of 3 shortlisted")).toBeInTheDocument();
    expect(view.getByText("Signal desk").closest("li")).toHaveAttribute("data-idea-id", "idea-a");
    expect(view.getByText("Signal desk").closest("li")).toHaveAttribute("data-idea-revision", "2");
    expect(view.getByText("Evidence map").closest("li")).toHaveAttribute("data-idea-revision", "4");
    expect(view.getByText("Revision 2")).toBeInTheDocument();
    expect(view.getByText("100 credits")).toBeInTheDocument();
    expect(view.getAllByText("Recommended")).toHaveLength(1);
    expect(view.getByRole("button", { name: "Remove Signal desk from shortlist" })).toBeInTheDocument();
  });

  it("routes the recommendation, tasks, shortlist edit, and commit through explicit callbacks", async () => {
    const handlers = callbacks();
    const view = render(DecisionRail, {
      props: {
        journey: journey(),
        ...handlers,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Compare finalists" }));
    expect(handlers.onRunRecommendation).toHaveBeenCalledOnce();

    await fireEvent.click(view.getByRole("button", { name: "Remove Signal desk from shortlist" }));
    expect(handlers.onRemoveShortlistItem).toHaveBeenCalledWith("idea-a", 2);

    await fireEvent.click(view.getByRole("button", { name: /Your build constraints/ }));
    expect(handlers.onEditConstraints).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: /Check the evidence/ }));
    expect(handlers.onOpenRisks).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: /Plan a test/ }));
    expect(handlers.onOpenTests).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: /Explore variants/ }));
    expect(handlers.onOpenAlternatives).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: "Edit" }));
    expect(handlers.onOpenCandidates).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research" }));
    expect(handlers.onStartDeepResearch).toHaveBeenCalledOnce();
  });

  it("requires a shortlist slot before the research recommendation can be added", () => {
    const fullJourney = journey({
      shortlist: {
        version: 6,
        maxItems: 3,
        items: [
          ...journey().shortlist.items,
          { ideaId: "idea-c", ideaRevision: 1, title: "Demand monitor" },
        ],
      },
    });
    const view = render(DecisionRail, {
      props: {
        journey: {
          ...fullJourney,
          recommendation: {
            target: "shortlist",
            title: "Review the strongest candidate",
            description: "Open the idea, check the evidence, and add it if it holds up.",
            actionLabel: "Review Market signal desk",
            ideas: [{ ideaId: "idea-d", ideaRevision: 1, title: "Market signal desk" }],
          },
        },
        researchLeadTitle: "Market signal desk",
        ...callbacks(),
      },
    });

    expect(view.getByRole("button", {
      name: "Shortlist is full; remove an idea before adding Market signal desk",
    })).toBeDisabled();
  });

  it("merges a shortlist recommendation into one next-step panel", async () => {
    const handlers = callbacks();
    const shortlistJourney = journey({
      shortlist: { version: 0, maxItems: 3, items: [] },
      recommendation: {
        target: "shortlist",
        title: "Review the strongest candidate",
        description: "Open the idea, check the evidence, and add it if it holds up.",
        actionLabel: "Review Market signal desk",
        ideas: [{ ideaId: "idea-c", ideaRevision: 1, title: "Market signal desk" }],
      },
    });
    const view = render(DecisionRail, {
      props: {
        journey: shortlistJourney,
        researchLeadTitle: "Market signal desk",
        ...handlers,
      },
    });

    expect(view.getAllByText("Market signal desk")).toHaveLength(1);
    await fireEvent.click(view.getByRole("button", { name: "Review Market signal desk" }));
    expect(handlers.onRunRecommendation).toHaveBeenCalledOnce();
    await fireEvent.click(view.getByRole("button", { name: "Add Market signal desk to shortlist" }));
    expect(handlers.onAddResearchLead).toHaveBeenCalledOnce();
  });

  it("disables unavailable steps and Deep Research without hiding why", () => {
    const noSelection = journey({
      shortlist: { version: 0, maxItems: 3, items: [] },
      tasks: journey().tasks.map((task) =>
        task.key === "compare" || task.key === "risks" || task.key === "tests"
          ? { ...task, status: "not_ready", statusLabel: "Choose ideas first" }
          : task,
      ),
      recommendation: {
        target: "shortlist",
        title: "Review the strongest candidate",
        description: "Choose an idea before doing decision work.",
        actionLabel: "Review candidates",
        ideas: [],
      },
      deepResearch: {
        eligible: false,
        optionalWorkRequired: false,
        blockers: ["NO_CURRENT_SHORTLIST"],
      },
    });
    const view = render(DecisionRail, { props: { journey: noSelection, ...callbacks() } });

    expect(view.getByText("Choose an idea to continue")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
    expect(view.getByRole("button", { name: /Compare finalists/ })).toBeDisabled();
    // Only the two primary tools (Compare, Check the evidence) surface the lock
    // hint; Plan-a-test is demoted to the quiet secondary row.
    expect(view.getAllByText("Choose ideas first")).toHaveLength(2);
  });
});
