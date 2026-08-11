import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReviewPage from "./+page.svelte";
import { rankedIdeasHref } from "$lib/selection/rankedIdeas";

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
  conclusions?: Array<Record<string, unknown>>;
  ownerEvidence?: Array<Record<string, unknown>>;
  founderFitResults?: Array<Record<string, unknown>>;
  founderFitStale?: boolean;
  solutionVotes?: Record<string, number>;
  solutionVotesById?: Record<string, number>;
  voteRationales?: Array<Record<string, unknown>>;
  collaboratorSignalsStatus?: "loaded" | "absent" | "unavailable";
  decisionTools?: boolean;
  status?: string;
  selectionRationale?: string | null;
  sampleReportAvailable?: boolean;
} = {}) {
  const ideas = options.ideas ?? [idea];
  return {
    job: {
      id: "job-1",
      status: options.status ?? "AWAITING_SELECTION",
      selectionRationale: options.selectionRationale ?? null,
    },
    // The risk-check summary inside /review is a decision tool; /review itself is not.
    decisionTools: options.decisionTools ?? true,
    sampleReportAvailable: options.sampleReportAvailable ?? true,
    workspace: {
      ideas,
      scopeSource: "url",
      canonicalQuery: "?idea=idea-a%3A3",
    },
    solutions: ideas,
    decisionState: {
      shortlist: {
        version: 7,
        fingerprint: "opaque-shortlist-fingerprint",
        items: options.saved === false
          ? []
          : ideas.map((entry) => ({
            ideaId: entry.idea_id,
            ideaRevision: entry.idea_revision ?? 1,
            title: entry.solution_name,
          })),
      },
      challenges: options.challenges ?? [],
      ownerEvidence: options.ownerEvidence ?? [],
      assumptions: options.assumptions ?? [],
      conclusions: options.conclusions ?? [],
      founderFit: options.founderFitResults
        ? {
            inputFingerprint: "founder-fit-fingerprint",
            results: options.founderFitResults.map((result) => ({
              idea: {
                ideaId: result.ideaId,
                ideaRevision: result.ideaRevision,
                title: result.ideaTitle,
              },
              verdict: result.verdict,
            })),
          }
        : null,
      staleCounts: { challenges: 0 },
      deepResearch: { eligible: true },
    },
    founderFit: options.founderFitResults
      ? {
          stale: options.founderFitStale ?? false,
          analysis: { results: options.founderFitResults },
        }
      : null,
    solutionVotes: options.solutionVotes ?? {},
    solutionVotesById: options.solutionVotesById ?? {},
    voteRationales: options.voteRationales ?? [],
    collaboratorSignalsStatus: options.collaboratorSignalsStatus ?? "loaded",
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
    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research" }));

    await waitFor(() => expect(mocks.selectSolution).toHaveBeenCalledWith("job-1", {
      clientRequestId: expect.any(String),
      expectedDraftVersion: 7,
      expectedSelectionFingerprint: "opaque-shortlist-fingerprint",
      expectedCost: 100,
      rationale: "Strongest buyer evidence.",
    }));
    expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1");
  });

  it("does not start when the linked scope differs from the saved shortlist", () => {
    const view = render(ReviewPage, { props: { data: data({ saved: false }) } });

    expect(view.getByText("This linked scope does not match your saved shortlist yet.")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
    expect(mocks.selectSolution).not.toHaveBeenCalled();
  });

  it("keeps balance-after-charge in the canonical record when the balance is insufficient", () => {
    const view = render(ReviewPage, { props: { data: data({ balance: 94 }) } });

    expect(view.getByLabelText("Credit summary"))
      .toHaveTextContent("FLAT PRICE 100 CREDITS · COVERS 1-3 IDEAS · BALANCE AFTER -6");
    expect(view.getByLabelText("Credit summary")).not.toHaveTextContent("SHORT");
    expect(view.queryByRole("link", { name: /top up/i })).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: /top up/i })).not.toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
    expect(view.container.textContent?.match(/\bcredits?\b/gi)).toHaveLength(2);
    expect(view.container.textContent?.match(/\b(?:price|charge|cost)\b/gi)).toHaveLength(1);
  });

  it("routes a losing concurrent-start tab to authoritative progress", async () => {
    const ApiError = (await import("$lib/api")).ApiError;
    mocks.selectSolution.mockRejectedValue(new ApiError(
      "Deep Research was started by another request",
      409,
      { code: "DEEP_RESEARCH_START_CONFLICT" },
    ));
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research" }));

    await waitFor(() => expect(mocks.invalidateAll).toHaveBeenCalled());
    expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1", { invalidateAll: true });
  });

  it("keeps a changed scope or price inline and requires a fresh confirmation", async () => {
    const ApiError = (await import("$lib/api")).ApiError;
    mocks.selectSolution
      .mockRejectedValueOnce(new ApiError(
        "Confirmation changed",
        409,
        { code: "DEEP_RESEARCH_SCOPE_CHANGED" },
      ))
      .mockResolvedValueOnce({});
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research" }));
    expect(await view.findByRole("heading", { name: "Review the updated confirmation" }))
      .toHaveFocus();
    expect(view.getByText(/Nothing was charged or started/)).toBeInTheDocument();
    expect(mocks.goto).not.toHaveBeenCalled();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();

    await fireEvent.click(view.getByRole("button", { name: "Use this updated scope and price" }));
    await fireEvent.click(view.getByRole("button", { name: "Confirm updated scope" }));
    await waitFor(() => expect(mocks.selectSolution).toHaveBeenCalledTimes(2));
    const [firstRequest, secondRequest] = mocks.selectSolution.mock.calls.map((call) => call[1]);
    expect(secondRequest.clientRequestId).not.toBe(firstRequest.clientRequestId);
    expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1");
  });

  it("does not disguise invalid credit data as a zero balance", () => {
    const invalid = data() as unknown as {
      creditBalance: number;
      stageCosts: { deep_research: number };
    };
    invalid.creditBalance = Number.NaN;
    const view = render(ReviewPage, { props: { data: invalid as never } });

    expect(view.getByText("Credit information is invalid or unavailable. Reload before starting so you can confirm the exact charge.")).toBeInTheDocument();
    expect(view.getByText("UNAVAILABLE")).toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
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
    expect(view.getAllByText("UNAVAILABLE")).toHaveLength(2);
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

  it("uses singular grammar for one open question", () => {
    const ideaRef = { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" };
    const view = render(ReviewPage, {
      props: {
        data: data({
          assumptions: [{ id: "a1", idea: ideaRef, ownerState: "OPEN" }],
        }),
      },
    });

    const question = view.getByRole("link", { name: "1 open question to resolve" });
    expect(question.closest("p"))
      .toHaveTextContent("1 open question to resolve is tracked but not yet answered.");
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
    expect(view.getByText(/clear recommendation, and decision-changing conditions/)).toBeInTheDocument();
    const sample = view.getByRole("link", { name: /See a sample report/ });
    expect(sample).toHaveAttribute("href", "/sample-report");
    // /sample-report is in the (public) route group: following it in-tab would
    // drop the user out of the app shell mid-commit.
    expect(sample).toHaveAttribute("target", "_blank");
    expect(view.getByText(/Starting Deep Research locks this exact shortlist/)).toBeInTheDocument();
    expect(view.getByText(/any active discovery share closes once the run is successfully queued/)).toBeInTheDocument();
    expect(view.getByText("Run protection: if the run fails or finds too little data, credits return automatically.")).toBeInTheDocument();
    expect(view.getByLabelText("Credit summary"))
      .toHaveTextContent("FLAT PRICE 100 CREDITS · COVERS 1-3 IDEAS · BALANCE AFTER 631");
    expect(view.container.textContent?.match(/\bcredits?\b/gi)).toHaveLength(2);
    expect(view.container.textContent?.match(/\b(?:price|charge|cost)\b/gi)).toHaveLength(1);
  });

  it("does not offer a dead sample link when no verified sample is published", () => {
    const view = render(ReviewPage, {
      props: { data: data({ sampleReportAvailable: false }) },
    });

    expect(view.queryByRole("link", { name: /See a sample report/ })).not.toBeInTheDocument();
    expect(view.getByText("Sample report temporarily unavailable.")).toBeInTheDocument();
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

  it("renders the provenance-safe saved decision receipt for each idea", () => {
    const ideaRef = { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" };
    const view = render(ReviewPage, {
      props: {
        data: data({
          ideas: [{ ...idea, red_team_verdict: "weakened" }],
          founderFitResults: [{
            ideaId: "idea-a",
            ideaRevision: 3,
            ideaTitle: "Signal desk",
            verdict: "needs_reshape",
            summary: "The full scope exceeds the saved time budget.",
            blockingConflict: null,
            decisionChangingUnknown: "Whether a narrow weekly brief retains enough value.",
          }],
          assumptions: [
            { id: "medium", idea: ideaRef, ownerState: "OPEN", impact: "MEDIUM", statement: "Whether buyers prefer email." },
            { id: "decisive", idea: ideaRef, ownerState: "OPEN", impact: "DECISIVE", statement: "Whether teams will pay before integrations exist." },
          ],
          conclusions: [
            { id: "latest", experimentId: "experiment-2", idea: ideaRef, outcome: "PASS" },
            { id: "older", experimentId: "experiment-1", idea: ideaRef, outcome: "FAIL" },
          ],
          solutionVotesById: { "idea-a": 2 },
          voteRationales: [{
            solutionId: "idea-a",
            solutionName: "Signal desk",
            comment: "Clearest fit for our weekly review.",
          }],
        }),
      },
    });

    const receipt = view.getByLabelText("Decision receipt for Signal desk");
    expect(receipt).not.toHaveTextContent("Research verdict");
    expect(receipt).toHaveTextContent("Founder fit Needs reshape: The full scope exceeds the saved time budget.");
    expect(receipt).toHaveTextContent("Open question Whether teams will pay before integrations exist.");
    expect(receipt).not.toHaveTextContent("Whether buyers prefer email.");
    expect(receipt).toHaveTextContent("Latest test Passed");
    expect(receipt).not.toHaveTextContent("Failed");
    expect(receipt).toHaveTextContent("Collaborator signal 2 collaborator votes. Latest note: “Clearest fit for our weekly review.”");
  });

  it("does not render an unprovenanced generator-owned research verdict", () => {
    const view = render(ReviewPage, {
      props: { data: data({ ideas: [{ ...idea, red_team_verdict: "killed" }] }) },
    });

    expect(view.queryByText("Research verdict")).not.toBeInTheDocument();
    expect(view.queryByText("Premise unproven")).not.toBeInTheDocument();
  });

  it("renders collaborator evidence when feedback loaded with votes", () => {
    const view = render(ReviewPage, {
      props: {
        data: data({
          collaboratorSignalsStatus: "loaded",
          solutionVotesById: { "idea-a": 1 },
        }),
      },
    });

    expect(view.getByLabelText("Decision receipt for Signal desk"))
      .toHaveTextContent("Collaborator signal 1 collaborator vote");
    expect(view.queryByRole("status")).not.toBeInTheDocument();
  });

  it("omits collaborator evidence without an outage warning when feedback loaded with no votes", () => {
    const view = render(ReviewPage, {
      props: { data: data({ collaboratorSignalsStatus: "loaded" }) },
    });

    expect(view.queryByLabelText("Decision receipt for Signal desk")).not.toBeInTheDocument();
    expect(view.queryByText("Collaborator signal")).not.toBeInTheDocument();
    expect(view.queryByRole("status")).not.toBeInTheDocument();
  });

  it("omits per-idea collaborator placeholders and shows one page warning when feedback fails", () => {
    const view = render(ReviewPage, {
      props: {
        data: data({
          collaboratorSignalsStatus: "unavailable",
          solutionVotesById: { "idea-a": 4, "idea-b": 2 },
          voteRationales: [{
            solutionId: "idea-a",
            solutionName: "Signal desk",
            comment: "This stale payload must not render during an outage.",
          }],
          ideas: [
            idea,
            {
              idea_id: "idea-b",
              idea_revision: 1,
              solution_name: "Signal brief",
              short_description: "Turns the same signals into a weekly brief.",
            },
          ],
        }),
      },
    });

    expect(view.queryByText("Collaborator signal")).not.toBeInTheDocument();
    expect(view.queryByText("Could not be loaded")).not.toBeInTheDocument();
    expect(view.queryByLabelText(/Decision receipt for/)).not.toBeInTheDocument();
    expect(view.getAllByRole("status")).toHaveLength(1);
    expect(view.getByRole("status")).toHaveTextContent(
      "Collaborator feedback is temporarily unavailable. Saved votes or notes may be missing from this page.",
    );
  });

  it("omits the entire decision receipt when an idea has no saved facts", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.queryByLabelText("Decision receipt for Signal desk")).not.toBeInTheDocument();
    expect(view.queryByText("Research verdict")).not.toBeInTheDocument();
    expect(view.queryByText("Founder fit")).not.toBeInTheDocument();
    expect(view.queryByText("Open question")).not.toBeInTheDocument();
    expect(view.queryByText("Latest test")).not.toBeInTheDocument();
    expect(view.queryByText("Collaborator signal")).not.toBeInTheDocument();
  });

  it("names the collection with the canonical shortlist vocabulary", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.getByRole("heading", { name: "Review your shortlist" })).toBeInTheDocument();
    expect(view.getByRole("link", { name: "Choose ideas" }))
      .toHaveAttribute("href", rankedIdeasHref("job-1"));
    expect(view.queryByText("Edit selection")).toBeNull();
  });

  it("routes every shortlist-editing action to the job hub that owns the shortlist", () => {
    const secondIdea = {
      idea_id: "idea-b",
      idea_revision: 1,
      solution_name: "Signal brief",
      short_description: "Turns the same signals into a weekly brief.",
    };
    const pageData = data({ ideas: [idea, secondIdea] }) as unknown as {
      workspace: { scopeSource: string };
      overlapGroups: Array<{ idea_names: string[]; shared_product: string }>;
    };
    pageData.workspace.scopeSource = "preview";
    pageData.overlapGroups = [{
      idea_names: ["Signal desk", "Signal brief"],
      shared_product: "market-signal briefing",
    }];

    const view = render(ReviewPage, { props: { data: pageData as never } });

    for (const link of view.getAllByRole("link", { name: "Choose ideas" })) {
      expect(link).toHaveAttribute("href", rankedIdeasHref("job-1"));
    }
    expect(view.getByRole("link", { name: "Change your shortlist" }))
      .toHaveAttribute("href", rankedIdeasHref("job-1"));
  });

  it("states one shortlist record line at the gate", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.getByText("1 SHORTLISTED · 0 CHECKS")).toBeInTheDocument();
  });

  it("acknowledges owner-saved evidence at the gate", () => {
    const view = render(ReviewPage, {
      props: {
        data: data({
          ownerEvidence: [
            { id: "oe-1", idea: { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" } },
            { id: "oe-2", idea: { ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" } },
            // Belongs to an idea that is not on this shortlist — must not be counted.
            { id: "oe-3", idea: { ideaId: "idea-z", ideaRevision: 1, title: "Other" } },
          ],
        }),
      },
    });

    expect(view.getByText("1 SHORTLISTED · 0 CHECKS · 2 EVIDENCE ADDED")).toBeInTheDocument();
    expect(view.getByRole("link", { name: "2 pieces of your own evidence" }))
      .toHaveAttribute("href", "/jobs/job-1/selection/risks?idea=idea-a%3A3");
  });

  it("keeps the record line clean when no owner evidence was saved", () => {
    const view = render(ReviewPage, { props: { data: data() } });

    expect(view.queryByText(/EVIDENCE ADDED/)).toBeNull();
  });

  it("opens a shortlisted idea for read-only inspection without leaving the gate", async () => {
    const view = render(ReviewPage, { props: { data: data() } });

    await fireEvent.click(view.getByRole("button", { name: /Signal desk/ }));

    await waitFor(() => expect(view.getAllByRole("dialog").length).toBeGreaterThan(0));
    // Inspection only: the shortlist is edited in Compare, so no select control.
    expect(view.queryByRole("button", { name: /Add to shortlist|Select this idea/ })).toBeNull();
  });

  it("keeps idea details inspectable but all commit inputs locked after selection ends", async () => {
    const view = render(ReviewPage, {
      props: {
        data: data({
          status: "COMPLETED",
          selectionRationale: "Strongest buyer evidence and the clearest repeat workflow.",
        }),
      },
    });

    expect(view.getByText(/View-only record of the exact shortlist/)).toBeInTheDocument();
    expect(view.getByText("Saved scope")).toBeInTheDocument();
    expect(view.queryByRole("link", { name: "Choose ideas" })).not.toBeInTheDocument();
    expect(view.getByRole("link", { name: "Open evidence record" })).toHaveAttribute(
      "href",
      "/jobs/job-1/selection/risks?idea=idea-a%3A3",
    );
    expect(view.getByRole("heading", { name: "Why these ideas?" })).toBeInTheDocument();
    expect(view.getByText("Strongest buyer evidence and the clearest repeat workflow.")).toBeInTheDocument();
    expect(view.queryByLabelText(/Why these ideas\?/)).not.toBeInTheDocument();
    expect(view.getByRole("button", { name: "Start Deep Research" })).toBeDisabled();
    await fireEvent.click(view.getByRole("button", { name: /Signal desk/ }));
    await waitFor(() => expect(view.getAllByRole("dialog").length).toBeGreaterThan(0));
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

    await fireEvent.click(view.getByRole("button", { name: "Start Deep Research" }));
    await waitFor(() => expect(mocks.selectSolution).toHaveBeenCalledWith("job-1", expect.objectContaining({
      rationale: "Updated reasoning.",
    })));
    await waitFor(() => expect(sessionStorage.getItem(RATIONALE_KEY)).toBeNull());
  });

  it("describes a blocked start button via the sr-only status node", () => {
    const view = render(ReviewPage, { props: { data: data({ saved: false }) } });

    const button = view.getByRole("button", { name: "Start Deep Research" });
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
