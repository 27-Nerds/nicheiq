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
import { getChatHistory } from "$lib/api";
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
    const { findByRole } = render(PageComponent, {
      props: { data: baseData(baseJob()) as never },
    });

    await findByRole("button", { name: /Resume from checkpoint/i });
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
    const { queryByText, findByRole } = render(PageComponent, {
      props: { data: baseData(baseJob({ solutionIdeas: [] })) as never },
    });

    await findByRole("button", { name: /Resume from checkpoint/i });
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

      const retryButton = await view.findByRole("button", {
        name: "Retry Deep Research · 15 credits",
      });
      await fireEvent.click(retryButton);

      await view.findByRole("button", { name: "Retrying Deep Research..." });
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

      await fireEvent.click(await view.findByRole("button", {
        name: "Retry Deep Research · 15 credits",
      }));

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

  it("keeps the run-overview shell when the run died before discovery wrote anything", async () => {
    // Nothing to read means nothing to put in a workbench — the status-first layout is
    // still the right one here, right-rail status panel included.
    const { findByText, queryByText } = render(PageComponent, {
      props: { data: baseData(baseJob({ solutionIdeas: [] })) as never },
    });

    await findByText("Refunded");
    expect(queryByText("Recover run")).toBeNull();
  });

  it("frames a cancellation as the user's own decision, with no resume affordance", async () => {
    const job = baseJob({ status: "CANCELLED", creditRefunded: true } as never);
    const { findByText, findByRole, queryByRole } = render(PageComponent, {
      props: { data: baseData(job) as never },
    });

    await findByText("This research was cancelled");
    await findByText("Credits refunded");
    await findByRole("link", { name: /Start new research/i });
    expect(queryByRole("button", { name: /Resume from checkpoint/i })).toBeNull();
  });
});
