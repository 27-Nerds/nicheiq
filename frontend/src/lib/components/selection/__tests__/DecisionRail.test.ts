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
      staleItems: [],
    },
    tasks: [],
    recommendation: {
      target: "compare",
      title: "Compare trade-offs",
      description: "See the meaningful differences.",
      actionLabel: "Compare trade-offs",
      ideas: [],
    },
    deepResearch: { eligible: true, optionalWorkRequired: false, blockers: [] },
    ...overrides,
  };
}

function callbacks() {
  return {
    onRetrySave: vi.fn(),
    onReloadSave: vi.fn(),
    onRemoveShortlistItem: vi.fn(),
    onStartDeepResearch: vi.fn(),
  };
}

afterEach(cleanup);

describe("DecisionRail", () => {
  it("renders a compact exact-revision shortlist and total cost", () => {
    const view = render(DecisionRail, {
      props: { journey: journey(), deepResearchCost: 100, ...callbacks() },
    });

    expect(view.getByRole("complementary", { name: "Ideas for Deep Research" })).toBeInTheDocument();
    expect(view.getByLabelText("2 of 3 ideas selected")).toBeInTheDocument();
    expect(view.getByText("Signal desk").closest("li")).toHaveAttribute("data-idea-id", "idea-a");
    expect(view.getByText("Signal desk").closest("li")).toHaveAttribute("data-idea-revision", "2");
    expect(view.getByText("Evidence map").closest("li")).toHaveAttribute("data-idea-revision", "4");
    expect(view.getByText("100 credits total")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Review and start" })).toBeEnabled();
  });

  it("removes an exact revision and opens the routed review through explicit callbacks", async () => {
    const handlers = callbacks();
    const view = render(DecisionRail, { props: { journey: journey(), ...handlers } });

    await fireEvent.click(view.getByRole("button", { name: "Remove Signal desk from shortlist" }));
    expect(handlers.onRemoveShortlistItem).toHaveBeenCalledWith("idea-a", 2);

    await fireEvent.click(view.getByRole("button", { name: "Review and start" }));
    expect(handlers.onStartDeepResearch).toHaveBeenCalledOnce();
  });

  it("keeps the disabled reason available when no idea is selected", () => {
    const view = render(DecisionRail, {
      props: {
        journey: journey({
          shortlist: { version: 0, maxItems: 3, items: [], staleItems: [] },
          deepResearch: { eligible: false, optionalWorkRequired: false, blockers: ["NO_CURRENT_SHORTLIST"] },
        }),
        ...callbacks(),
      },
    });

    expect(view.getByText("Select 1–3 ideas to continue.")).toBeInTheDocument();
    expect(view.getByText("Select at least one idea to review the research scope.")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Review and start" })).toBeDisabled();
  });

  it("warns about same-product shortlist entries without blocking the start", () => {
    const view = render(DecisionRail, {
      props: {
        journey: journey(),
        overlapWarnings: [{
          ideaNames: ["Signal desk", "Evidence map"],
          sharedProduct: "vague-note to exact-edit translator",
        }],
        ...callbacks(),
      },
    });

    expect(view.getByRole("status")).toHaveTextContent(
      "Signal desk and Evidence map are variants of the same product (vague-note to exact-edit translator).",
    );
    // Advisory only — spending two slots on one product is the user's call to make.
    expect(view.getByRole("button", { name: "Review and start" })).toBeEnabled();
  });

  it("stays quiet when no two shortlisted ideas share a product", () => {
    const view = render(DecisionRail, {
      props: { journey: journey(), overlapWarnings: [], ...callbacks() },
    });

    expect(view.queryByRole("status")).not.toBeInTheDocument();
  });

  it("offers the correct recovery action when saving the shortlist fails", async () => {
    const handlers = callbacks();
    const view = render(DecisionRail, {
      props: {
        journey: journey(),
        saveState: "error",
        saveError: "This shortlist changed elsewhere.",
        saveConflict: true,
        ...handlers,
      },
    });

    expect(view.getByRole("alert")).toHaveTextContent("This shortlist changed elsewhere.");
    await fireEvent.click(view.getByRole("button", { name: "Reload" }));
    expect(handlers.onReloadSave).toHaveBeenCalledOnce();
    expect(handlers.onRetrySave).not.toHaveBeenCalled();
  });

  it("renders unavailable revisions as placeholders and blocks review", () => {
    const view = render(DecisionRail, {
      props: {
        journey: journey({
          shortlist: {
            version: 6,
            maxItems: 3,
            items: [{ ideaId: "idea-a", ideaRevision: 2, title: "Signal desk" }],
            staleItems: [{ ideaId: "idea-old", ideaRevision: 5, title: "Archived angle" }],
          },
        }),
        ...callbacks(),
      },
    });

    expect(view.getByText(/Archived angle · revision 5/)).toBeInTheDocument();
    expect(view.getByText("Needs replacement")).toBeInTheDocument();
    expect(view.getByText(/Replace unavailable candidate revisions/)).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Review and start" })).toBeDisabled();
  });
});
