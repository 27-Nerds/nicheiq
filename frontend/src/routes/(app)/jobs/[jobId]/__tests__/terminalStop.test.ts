/**
 * A run that stops after discovery still owns everything Phase 1 produced, and the owner paid
 * for it. The page used to gate that content on job.status alone, so FAILED matched neither
 * `isSelectionPhase` nor `isCompleted` and fell through every branch — the dossier lost its
 * header and rendered collapsed, and the failure itself was restated three times in
 * hand-rolled banners that duplicated JobHeroAside's right-rail panel verbatim.
 *
 * These cover the replacement: one design-system handoff card carrying the NEXT STEP only,
 * and dossier chrome keyed on whether a dossier EXISTS rather than on the job being live.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, fireEvent, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";
import { goto, invalidateAll } from "$app/navigation";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import {
  getChatHistory,
  getDiscoveryData,
  getPreviewReport,
  shouldKeepSSEOpen,
  subscribeToProgress,
} from "$lib/api";
import type { Job } from "$lib/types/job";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
    shouldKeepSSEOpen: vi.fn(() => false),
    getReportSummary: vi.fn(() => Promise.resolve(null)),
    getDiscoveryShareStatus: vi.fn(() => Promise.resolve({ isShared: false, solutionVotes: {} })),
    regenerateIdeas: vi.fn(),
    getSolutions: vi.fn(() => Promise.resolve({ solutions: [] })),
    getDiscoveryData: vi.fn(() => Promise.resolve(null)),
    getPreviewReport: vi.fn(() => Promise.resolve(null)),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
  };
});

import PageComponent from "../+page.svelte";

function baseJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    niche: "test niche",
    status: "FAILED",
    entryMode: "standard",
    solutionIdeas: [
      { solution_name: "Alpha Idea", description: "d", value_proposition: "v" } as never,
      { solution_name: "Beta Idea", description: "d", value_proposition: "v" } as never,
    ],
    selectedSolutions: [],
    assets: [],
    stagesCompleted: 8,
    totalStages: 16,
    ...overrides,
  } as unknown as Job;
}

const DISCOVERY = {
  subreddit_post_counts: { r_test: 4 },
  total_posts_analyzed: 42,
} as never;

function baseData(job: Job, discoveryData: unknown = null) {
  return {
    job,
    solutions: job.solutionIdeas ?? [],
    reportSummary: null,
    discoveryData,
    solutionVotes: {},
    previewReport: null,
    userEmail: "test@example.com",
    catalogPainPoints: [],
    creditBalance: 100,
    stageCosts: { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3 },
    billingLoadState: { balanceUnavailable: false, costsUnavailable: false },
  };
}

describe("+page.svelte — terminal-stop handoff", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    (page as any).params = { jobId: "job-1" };
    (page as any).data = {
      ...(page as any).data,
      stageCosts: { deep_research: 15 },
    };
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
  });

  afterEach(() => {
    cleanup();
  });

  it("offers resume and a fresh run as the only next steps on a failed job", async () => {
    const { findAllByRole, findByRole } = render(PageComponent, {
      props: { data: baseData(baseJob()) as never },
    });

    expect(await findAllByRole("button", { name: /Resume from checkpoint/i })).toHaveLength(2);
    await findByRole("link", { name: /Start new research/i });
  });

  it("discloses that a refunded stage may be re-charged before resume", async () => {
    const { findByText } = render(PageComponent, {
      props: { data: baseData(baseJob({ creditRefunded: true })) as never },
    });

    await findByText(
      "Resuming picks up from the last checkpoint and may re-charge the refunded stage at its original amount.",
    );
  });

  it("shows the exact re-charge before resuming a modern refunded dispatch", async () => {
    const { findAllByRole, findByText } = render(PageComponent, {
      props: {
        data: baseData(baseJob({
          creditRefunded: true,
          creditRefundedAmount: 99,
          errorDetails: {
            code: "PROVIDER_UNAVAILABLE",
            severity: "error",
            userMessage: "Research service temporarily unavailable",
            actionableGuidance: "Try again from the saved checkpoint.",
          },
        })) as never,
      },
    });

    await findByText(
      "Try again from the saved checkpoint. Resuming will charge the refunded 99 credits again when the retry is queued.",
    );
    const resumeActions = await findAllByRole("button", {
      name: "Resume from checkpoint · 99 credits",
    });
    expect(resumeActions).toHaveLength(2);
  });

  it("does not restate the aside's diagnosis — the failure headline appears exactly once", async () => {
    const job = baseJob({
      errorDetails: {
        userMessage: "Deep research could not start",
        actionableGuidance: "Resume to retry from the last checkpoint.",
      } as never,
    });
    const { findAllByText } = render(PageComponent, { props: { data: baseData(job) as never } });

    const headlines = await findAllByText("Deep research could not start");
    expect(headlines).toHaveLength(1);
  });

  it("tells the owner their completed discovery work survived the failure", async () => {
    const { findByText } = render(PageComponent, {
      props: { data: baseData(baseJob(), DISCOVERY) as never },
    });

    await findByText(/Your discovery work is intact\./);
    // Counted from the pool the run actually produced, not hardcoded.
    await findByText(/the 2 ideas it produced/);
  });

  it("keeps the retained-work note off a run that died before discovery produced anything", async () => {
    const { queryByText, findAllByRole } = render(PageComponent, {
      props: { data: baseData(baseJob({ solutionIdeas: [] })) as never },
    });

    expect(await findAllByRole("button", { name: /Resume from checkpoint/i })).toHaveLength(2);
    expect(queryByText(/Your discovery work is intact\./)).toBeNull();
  });

  it("gives a stopped run the dossier header, retitled since there is no shortlist to justify", async () => {
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob(), DISCOVERY) as never },
    });

    await findByText("What discovery found");
    expect(queryByText("Evidence behind the shortlist")).toBeNull();
  });

  it("gives a stopped run that completed discovery the workbench shell, not the run-overview one", async () => {
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob(), DISCOVERY) as never },
    });

    // Workbench nav: one recovery step + the discovery context, no phase checklist.
    await findByText("Recover run");
    await findByText("Discovery context");
    expect(queryByText("Phase 1 · Discovery")).toBeNull();
    // The legacy run-overview furniture is gone: no right-rail status panel restating
    // FAILED, and no progress stepper for a pipeline that is no longer moving.
    expect(queryByText("Refunded")).toBeNull();
  });

  it("runs the recovery transition before the stopped-run sidebar opens selection", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/jobs/job-1/resume") {
        return new Response(JSON.stringify({ status: "AWAITING_SELECTION" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const deepFailure = baseJob({
      jobMode: "interactive",
      selectedSolutionIds: ["idea-alpha"],
      selectedSolutions: ["Alpha Idea"],
    });
    const view = render(PageComponent, {
      props: { data: baseData(deepFailure, DISCOVERY) as never },
    });

    const recoveryButtons = await view.findAllByRole("button", { name: "Review selection" });
    expect(recoveryButtons).toHaveLength(2);
    expect(view.queryByRole("link", { name: "Review selection" })).toBeNull();

    await fireEvent.click(recoveryButtons[0]);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith("/api/jobs/job-1/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      expect(goto).toHaveBeenCalledWith("/jobs/job-1#opportunities", {
        replaceState: true,
        invalidateAll: true,
      });
    });
    fetchSpy.mockRestore();
  });

  it("retries a failed catalog idea directly instead of sending it through selection", async () => {
    let resolveResume!: (response: Response) => void;
    const resumeResponse = new Promise<Response>((resolve) => {
      resolveResume = resolve;
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/jobs/job-1/resume") return resumeResponse;
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    try {
      const catalogFailure = baseJob({
        entryMode: "deep_idea",
        jobMode: "interactive",
        solutionIdeas: [],
        selectedSolutionIds: ["catalog-idea"],
        selectedSolutions: ["Catalog Idea"],
        creditRefunded: true,
        stopReason: "INSUFFICIENT_DATA",
      } as never);
      const view = render(PageComponent, {
        props: { data: baseData(catalogFailure) as never },
      });

      await view.findByRole("heading", { name: "Retry Deep Research for this idea" });
      await view.findByText(
        "The retry uses the same catalog idea. Retrying Deep Research costs 15 credits; the charge happens when the retry is queued.",
      );
      expect(view.queryByText("Review your saved shortlist")).toBeNull();
      expect(view.queryByRole("button", { name: "Review selection" })).toBeNull();

      // The stopped-run sidebar mirrors the card's primary action, so the label
      // legitimately appears twice (rail + card).
      const retryButtons = await view.findAllByRole("button", {
        name: "Retry Deep Research · 15 credits",
      });
      expect(retryButtons).toHaveLength(2);
      await fireEvent.click(retryButtons[1]);

      const busyButtons = await view.findAllByRole("button", { name: "Retrying Deep Research..." });
      expect(busyButtons).toHaveLength(2);
      expect(view.queryByText("Opening...")).toBeNull();
      expect(fetchSpy).toHaveBeenCalledWith("/api/jobs/job-1/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expectedCost: 15 }),
      });

      resolveResume(new Response(JSON.stringify({ status: "queued", creditCharged: 15 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
      await waitFor(() => {
        expect(view.queryByRole("button", { name: "Retrying Deep Research..." })).toBeNull();
      });
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it("refreshes catalog pricing before another retry after PRICE_CHANGED", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        error: "Deep Research price changed",
        code: "PRICE_CHANGED",
        expectedCost: 15,
        actualCost: 18,
      }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    try {
      const catalogFailure = baseJob({
        entryMode: "deep_idea",
        solutionIdeas: [],
        selectedSolutionIds: ["catalog-idea"],
        selectedSolutions: ["Catalog Idea"],
      } as never);
      const view = render(PageComponent, {
        props: { data: baseData(catalogFailure) as never },
      });

      const retryButtons = await view.findAllByRole("button", {
        name: "Retry Deep Research · 15 credits",
      });
      expect(retryButtons).toHaveLength(2);
      await fireEvent.click(retryButtons[1]);

      await view.findByText(
        "The Deep Research price changed. Review the updated cost and try again.",
      );
      expect(invalidateAll).toHaveBeenCalled();
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it("disables both catalog retry actions when the current price is unavailable", async () => {
    const catalogFailure = baseJob({
      entryMode: "deep_idea",
      solutionIdeas: [],
      selectedSolutionIds: ["catalog-idea"],
      selectedSolutions: ["Catalog Idea"],
    } as never);
    const data = {
      ...baseData(catalogFailure, DISCOVERY),
      billingLoadState: { balanceUnavailable: false, costsUnavailable: true },
    };
    const view = render(PageComponent, {
      props: { data: data as never },
    });

    await view.findByText(
      "We couldn't load the current Deep Research price. Refresh this page before retrying; nothing will be charged.",
    );
    const retryButtons = await view.findAllByRole("button", {
      name: "Retry Deep Research · price unavailable",
    });
    expect(retryButtons).toHaveLength(2);
    for (const button of retryButtons) {
      expect(button).toBeDisabled();
    }
  });

  it("gives even a run that died before discovery wrote anything the workbench stop layout", async () => {
    // Every terminal stop is a "here is what happened, decide what to do" screen now;
    // the legacy run-overview shell (right-rail status panel) never renders for one.
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob({ solutionIdeas: [] })) as never },
    });

    await findByText("Recover run");
    expect(queryByText("Refunded")).toBeNull();
  });

  it("subtitles a no-artifact FAILED run without claiming discovery output survived", async () => {
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob({ solutionIdeas: [] })) as never },
    });

    await findByText("This run stopped before discovery finished.");
    expect(queryByText(/Everything it found is still here/)).toBeNull();
    expect(queryByText(/Your discovery work is intact/)).toBeNull();
  });

  it("subtitles a no-artifact CANCELLED run without claiming discovery output survived", async () => {
    const job = baseJob({ status: "CANCELLED", solutionIdeas: [] } as never);
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(job) as never },
    });

    await findByText("This run was cancelled before discovery produced anything to keep.");
    expect(queryByText(/Everything discovery found is still here/)).toBeNull();
  });

  it("hides the deep-research capped previews on a stopped run", async () => {
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob(), DISCOVERY) as never },
    });

    await findByText("Recover run");
    expect(queryByText("Unlocks with Deep Research")).toBeNull();
  });

  it("swaps to the stop layout and refetches the artifacts when a cancel arrives live over SSE", async () => {
    let sseCallback: ((data: unknown) => void) | undefined;
    vi.mocked(shouldKeepSSEOpen).mockReturnValue(true);
    vi.mocked(subscribeToProgress).mockImplementation(((_id: string, cb: (d: unknown) => void) => {
      sseCallback = cb;
      return () => {};
    }) as never);
    const running = baseJob({ status: "RUNNING" } as never);
    const view = render(PageComponent, {
      props: { data: baseData(running) as never },
    });

    expect(view.queryByText("This research was cancelled")).toBeNull();
    const callsBefore = vi.mocked(getDiscoveryData).mock.calls.length;

    const invalidationsBefore = vi.mocked(invalidateAll).mock.calls.length;
    sseCallback?.({ id: "job-1", status: "CANCELLED", creditRefunded: true });

    await view.findByText("This research was cancelled");
    await view.findAllByRole("link", { name: /Start new research/i });
    await waitFor(() => {
      // CANCELLED is on the refetch list: the artifacts are re-requested so the page
      // can prove (or settle the absence of) the discovery work before claiming either.
      expect(vi.mocked(getDiscoveryData).mock.calls.length).toBeGreaterThan(callsBefore);
      expect(vi.mocked(getPreviewReport)).toHaveBeenCalled();
      // The app header owns the credit balance through its layout data. Terminal
      // settlement must refresh that data so a refund is visible without a reload.
      expect(vi.mocked(invalidateAll).mock.calls.length).toBeGreaterThan(invalidationsBefore);
    });

    // vi.clearAllMocks() does not undo mockReturnValue/mockImplementation — restore
    // the factory behavior so later tests keep the closed-SSE default.
    vi.mocked(shouldKeepSSEOpen).mockReturnValue(false);
    vi.mocked(subscribeToProgress).mockImplementation((() => () => {}) as never);
  });

  it("frames a cancellation as the user's own decision, with no resume affordance", async () => {
    const job = baseJob({ status: "CANCELLED", creditRefunded: true } as never);
    const { findByText, findAllByRole, queryByRole } = render(PageComponent, {
      props: { data: baseData(job) as never },
    });

    await findByText("This research was cancelled");
    await findByText("Credits refunded");
    // Sidebar recovery row + card action carry the same label by design.
    const newRunLinks = await findAllByRole("link", { name: /Start new research/i });
    expect(newRunLinks).toHaveLength(2);
    expect(queryByRole("button", { name: /Resume from checkpoint/i })).toBeNull();
  });
});
