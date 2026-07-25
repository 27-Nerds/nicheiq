import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReviewPage from "./+page.svelte";

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  invalidateAll: vi.fn(),
  selectSolution: vi.fn(),
}));

vi.mock("$app/navigation", () => ({
  goto: mocks.goto,
  invalidateAll: mocks.invalidateAll,
}));
vi.mock("$lib/api", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    details?: unknown;
    constructor(message: string, status: number, details?: unknown) {
      super(message);
      this.status = status;
      this.details = details;
    }
  },
  selectSolution: mocks.selectSolution,
}));

const idea = {
  idea_id: "idea-a",
  idea_revision: 3,
  solution_name: "Signal desk",
  short_description: "Turns recurring market signals into a focused briefing.",
};

const RATIONALE_KEY = "nicheiq:research-rationale:job-1";

function data(options: {
  saved?: boolean;
  balance?: number;
  balanceUnavailable?: boolean;
  costsUnavailable?: boolean;
  ideas?: Array<Record<string, unknown>>;
  challenges?: Array<Record<string, unknown>>;
  assumptions?: Array<Record<string, unknown>>;
  decisionTools?: boolean;
} = {}) {
  const ideas = options.ideas ?? [idea];
  return {
    job: { id: "job-1", status: "AWAITING_SELECTION" },
    // The risk-check summary inside /review is a decision tool; /review itself is not.
    decisionTools: options.decisionTools ?? true,
    workspace: {
      ideas,
      scopeSource: "url",
      canonicalQuery: "?idea=idea-a%3A3",
    },
    decisionState: {
      shortlist: {
        items: options.saved === false
          ? []
          : ideas.map((entry) => ({
            ideaId: entry.idea_id,
            ideaRevision: entry.idea_revision ?? 1,
            title: entry.solution_name,
          })),
      },
      challenges: options.challenges ?? [],
      assumptions: options.assumptions ?? [],
      staleCounts: { challenges: 0 },
      deepResearch: { eligible: true },
    },
    creditBalance: options.balance ?? 731,
    stageCosts: { deep_research: 100 },
    billingLoadState: {
      balanceUnavailable: options.balanceUnavailable ?? false,
      costsUnavailable: options.costsUnavailable ?? false,
    },
  } as never;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe("selection review page", () => {
  it("starts Deep Research only for the exact saved revisions", async () => {
    mocks.selectSolution.mockResolvedValue({});
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.input(view.getByLabelText(/Why these ideas\?/), {
      target: { value: "Strongest buyer evidence." },
    });
    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research · 100 credits" }));

    await waitFor(() => expect(mocks.selectSolution).toHaveBeenCalledWith("job-1", {
      solutionNames: ["Signal desk"],
      solutionIds: ["idea-a"],
      rationale: "Strongest buyer evidence.",
    }));
    expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1");
  });

  it("does not start when the linked scope differs from the saved shortlist", () => {
    const view = render(ReviewPage, { props: { data: data({ saved: false }) } });

    expect(view.getByText("This linked scope does not match your saved shortlist yet.")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research · 100 credits" })).toBeDisabled();
    expect(mocks.selectSolution).not.toHaveBeenCalled();
  });

  it("states the exact credit shortfall and keeps the commit disabled", () => {
    const view = render(ReviewPage, { props: { data: data({ balance: 60 }) } });

    expect(view.getByText("You need 40 more credits before you can start.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Add credits" })).toHaveAttribute("href", "/billing");
    expect(view.getByRole("button", { name: "Start Deep Research · 100 credits" })).toBeDisabled();
  });

  it("routes a losing concurrent-start tab to authoritative progress", async () => {
    const ApiError = (await import("$lib/api")).ApiError;
    mocks.selectSolution.mockRejectedValue(new ApiError(
      "Deep Research was started by another request",
      409,
      { code: "DEEP_RESEARCH_START_CONFLICT" },
    ));
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research · 100 credits" }));

    await waitFor(() => expect(mocks.invalidateAll).toHaveBeenCalled());
    expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1", { invalidateAll: true });
  });

  it("does not disguise invalid credit data as a zero balance", () => {
    const invalid = data() as unknown as {
      creditBalance: number;
      stageCosts: { deep_research: number };
    };
    invalid.creditBalance = Number.NaN;
    const view = render(ReviewPage, { props: { data: invalid as never } });

    expect(view.getByText("Credit information is invalid or unavailable. Reload before starting so you can confirm the exact charge.")).toBeInTheDocument();
    expect(view.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(view.getByRole("button", { name: "Start Deep Research · 100 credits" })).toBeDisabled();
  });

  it("does not trust fallback billing values after an API failure", () => {
    const view = render(ReviewPage, {
      props: {
        data: data({ balanceUnavailable: true, costsUnavailable: true }),
      },
    });

    expect(view.getByText(
      "Your credit balance and the current Deep Research price could not be loaded. Reload before starting so you can confirm the exact charge.",
    )).toBeInTheDocument();
    expect(view.getAllByText("Unavailable")).toHaveLength(4);
    expect(view.getByRole("button", { name: "Reload credit information" })).toBeEnabled();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
  });

  it("surfaces proof-work at the gate: open questions link and weakened-check warning", () => {
    const ideaRef = { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" };
    const outOfScopeRef = { ideaId: "idea-z", ideaRevision: 1, title: "Other" };
    const view = render(ReviewPage, {
      props: {
        data: data({
          challenges: [
            { id: "c1", idea: ideaRef, lens: "demand", overall: "withstands", gapQuestionIds: [] },
            { id: "c2", idea: ideaRef, lens: "competition", overall: "weakened", gapQuestionIds: [] },
          ],
          assumptions: [
            { id: "a1", idea: ideaRef, ownerState: "OPEN" },
            { id: "a2", idea: ideaRef, ownerState: "OPEN" },
            { id: "a3", idea: ideaRef, ownerState: "RETIRED" },
            { id: "a4", idea: outOfScopeRef, ownerState: "OPEN" },
          ],
        }),
      },
    });

    expect(view.getByText(/2 current evidence checks are saved/)).toBeInTheDocument();
    const openLink = view.getByRole("link", { name: "2 open questions to resolve" });
    expect(openLink).toHaveAttribute("href", "/jobs/job-1/selection/risks?idea=idea-a%3A3");
    expect(view.getByText(/1 check found claims weakened or contradicted/)).toBeInTheDocument();
  });

  it("stays quiet when no proof-work exists in scope", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.queryByRole("link", { name: /questions to resolve/ })).not.toBeInTheDocument();
    expect(view.queryByText(/weakened or contradicted/)).not.toBeInTheDocument();
  });

  it("shows the paywall value block: ETA, deliverables, sample link, flat price, lock and refund lines", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.getByText(/Typically ready within the hour/)).toBeInTheDocument();
    expect(view.getByText("What you get")).toBeInTheDocument();
    expect(view.getByText(/Demand & pain evidence/)).toBeInTheDocument();
    expect(view.getByText(/go \/ no-go verdict/)).toBeInTheDocument();
    const sample = view.getByRole("link", { name: /See a sample report/ });
    expect(sample).toHaveAttribute("href", "/sample-report");
    // /sample-report is in the (public) route group: following it in-tab would
    // drop the user out of the app shell mid-commit.
    expect(sample).toHaveAttribute("target", "_blank");
    expect(view.getByText("One price for up to 3 ideas — the same 100 credits for 1, 2, or 3.")).toBeInTheDocument();
    expect(view.getByText("Starting locks this shortlist — ideas can’t be changed during the run.")).toBeInTheDocument();
    expect(view.getByText("If the run fails or finds too little data, credits are returned automatically.")).toBeInTheDocument();
  });

  it("recaps each idea with its Research score and marks bundle-tier ideas", () => {
    const view = render(ReviewPage, {
      props: {
        data: data({
          ideas: [
            { ...idea, adjusted_composite_score: 0.72 },
            {
              idea_id: "idea-b",
              idea_revision: 1,
              solution_name: "Bundle desk",
              short_description: "A multi-pain bundle.",
              adjusted_composite_score: 0.61,
              idea_tier: "bundle",
              pain_points_addressed: ["p1", "p2", "p3", "p4"],
            },
          ],
        }),
      },
    });

    expect(view.getByRole("heading", { name: "2 selected · max 3" })).toBeInTheDocument();
    // Bare index, not a percentage: the Research score is a relative ranking
    // across this run, printed the same way by the ranked list and Compare.
    expect(view.getByText("Research score 72")).toBeInTheDocument();
    expect(view.getByText("Research score 61")).toBeInTheDocument();
    expect(view.getByText(/Bundle · 4 pain signals/)).toBeInTheDocument();
  });

  it("names the collection with the canonical shortlist vocabulary", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.getByRole("heading", { name: "Review your shortlist" })).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Choose ideas" }))
      .toHaveAttribute("href", "/jobs/job-1/selection/compare?idea=idea-a%3A3");
    expect(view.queryByText("Edit selection")).toBeNull();
  });

  it("states one shortlist record line at the gate", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.getByText("1 SHORTLISTED · 0 CHECKS")).toBeInTheDocument();
  });

  it("opens a shortlisted idea for read-only inspection without leaving the gate", async () => {
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.click(view.getByRole("button", { name: /Signal desk/ }));

    await waitFor(() => expect(view.getAllByRole("dialog").length).toBeGreaterThan(0));
    // Inspection only: the shortlist is edited in Compare, so no select control.
    expect(view.queryByRole("button", { name: /Add to shortlist|Select this idea/ })).toBeNull();
  });

  it("does not claim both that no check is saved and that checks were archived", () => {
    const staleData = data();
    (staleData as unknown as { decisionState: { staleCounts: { challenges: number } } })
      .decisionState.staleCounts.challenges = 2;
    const view = render(ReviewPage, { props: { data: staleData } });

    expect(view.getByText(/No current risk check: earlier checks were archived/)).toBeInTheDocument();
    expect(view.queryByText(/^No risk check saved\./)).toBeNull();
  });

  it("restores a persisted rationale, writes through on input, and clears it after a successful start", async () => {
    sessionStorage.setItem(RATIONALE_KEY, "Saved earlier.");
    mocks.selectSolution.mockResolvedValue({});
    const view = render(ReviewPage, { props: { data: data() } });

    const field = view.getByLabelText(/Why these ideas\?/) as HTMLTextAreaElement;
    expect(field.value).toBe("Saved earlier.");

    await fireEvent.input(field, { target: { value: "Updated reasoning." } });
    await waitFor(() => expect(sessionStorage.getItem(RATIONALE_KEY)).toBe("Updated reasoning."));

    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research · 100 credits" }));
    await waitFor(() => expect(mocks.selectSolution).toHaveBeenCalledWith("job-1", expect.objectContaining({
      rationale: "Updated reasoning.",
    })));
    await waitFor(() => expect(sessionStorage.getItem(RATIONALE_KEY)).toBeNull());
  });

  it("describes a blocked start button via the sr-only status node", () => {
    const view = render(ReviewPage, { props: { data: data({ saved: false }) } });

    const button = view.getByRole("button", { name: "Start Deep Research · 100 credits" });
    expect(button).toHaveAttribute("aria-describedby", "start-research-status");
    expect(document.getElementById("start-research-status")?.textContent)
      .toContain("Save this exact research scope before starting research.");
  });
});

describe("review page without the decision tools grant", () => {
  it("drops the risk-check summary but keeps the review flow", () => {
    const ideaRef = { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" };
    const view = render(ReviewPage, {
      props: {
        data: data({
          decisionTools: false,
          challenges: [
            { id: "c1", idea: ideaRef, lens: "demand", overall: "withstands", gapQuestionIds: [] },
            { id: "c2", idea: ideaRef, lens: "competition", overall: "weakened", gapQuestionIds: [] },
          ],
          assumptions: [{ id: "a1", idea: ideaRef, ownerState: "OPEN" }],
        }),
      },
    });

    expect(view.queryByText("Risk check")).toBeNull();
    expect(view.queryByText(/current evidence checks are saved/)).toBeNull();
    expect(view.queryByText(/questions to resolve/)).toBeNull();
    expect(view.queryByRole("link", { name: "Check the evidence" })).toBeNull();
  });
});
