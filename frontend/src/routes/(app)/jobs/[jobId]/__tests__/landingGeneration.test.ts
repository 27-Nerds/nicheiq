import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, fireEvent } from "@testing-library/svelte";
import { page } from "$app/state";
import { invalidateAll } from "$app/navigation";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import type { Job } from "$lib/types/job";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
    shouldKeepSSEOpen: vi.fn(() => false),
    getReportSummary: vi.fn(() => Promise.resolve(null)),
    getDiscoveryShareStatus: vi.fn(() => Promise.resolve({ isShared: false, solutionVotes: {} })),
    getSolutions: vi.fn(() => Promise.resolve({ solutions: [] })),
    getDiscoveryData: vi.fn(() => Promise.resolve(null)),
    getPreviewReport: vi.fn(() => Promise.resolve(null)),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
  };
});

import PageComponent from "../+page.svelte";

function completedJob(): Job {
  return {
    id: "job-1",
    niche: "test niche",
    status: "COMPLETED",
    entryMode: "standard",
    solutionIdeas: [],
    selectedSolutions: [],
    assets: [{ type: "REPORT_JSON", url: "/jobs/job-1/report" }],
    stagesCompleted: 16,
    totalStages: 16,
  } as unknown as Job;
}

function pageData(job: Job) {
  return {
    job,
    solutions: [],
    reportSummary: null,
    discoveryData: null,
    solutionVotes: {},
    previewReport: null,
    userEmail: "test@example.com",
    catalogPainPoints: [],
    creditBalance: 100,
    stageCosts: {
      discovery: 5,
      deep_research: 15,
      landing_page: 5,
      regenerate_ideas: 2,
      seed_idea: 3,
    },
    billingLoadState: { balanceUnavailable: false, costsUnavailable: false },
  };
}

describe("+page.svelte — landing-page purchase", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    (page as any).params = { jobId: "job-1" };
    (page as any).data = {
      ...(page as any).data,
      creditBalance: 100,
      stageCosts: { landing_page: 5 },
    };
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("confirms the displayed cost and refreshes it when the server reports a price change", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        error: "Landing page price changed",
        code: "PRICE_CHANGED",
        expectedCost: 5,
        actualCost: 7,
      }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const view = render(PageComponent, {
      props: { data: pageData(completedJob()) as never },
    });

    await fireEvent.click(await view.findByRole("button", { name: /Generate.*5/ }));
    await view.findByText("5 credits — confirm?");
    await fireEvent.click(await view.findByRole("button", { name: "Generate" }));

    expect(fetchSpy).toHaveBeenCalledWith("/api/jobs/job-1/generate-landing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expectedCost: 5 }),
    });
    await view.findByText(
      "The landing page price changed. Review the updated cost and try again.",
    );
    expect(invalidateAll).toHaveBeenCalled();
  });

  it("disables landing-page generation when the current price is unavailable", async () => {
    const data = {
      ...pageData(completedJob()),
      billingLoadState: { balanceUnavailable: false, costsUnavailable: true },
    };
    const view = render(PageComponent, {
      props: { data: data as never },
    });

    await view.findByText("Current price unavailable. Refresh to try again.");
    expect(await view.findByRole("button", { name: "Generate unavailable" })).toBeDisabled();
  });

  it("disables a failed landing-page retry when the current price is unavailable", async () => {
    const job = {
      ...completedJob(),
      landingPageStatus: "FAILED",
    } as Job;
    const data = {
      ...pageData(job),
      billingLoadState: { balanceUnavailable: false, costsUnavailable: true },
    };
    const view = render(PageComponent, {
      props: { data: data as never },
    });

    await view.findByText("Current price unavailable. Refresh to try again.");
    expect(await view.findByRole("button", { name: "Retry unavailable" })).toBeDisabled();
  });
});
