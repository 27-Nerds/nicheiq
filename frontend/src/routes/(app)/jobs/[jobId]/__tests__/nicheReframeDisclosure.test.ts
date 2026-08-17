/**
 * The job page's Stage-1 reframe disclosure, driven through production wiring.
 *
 * Round 1 built the disclosure inside `UnifiedHero` and gated it on `report.niche_context`.
 * This page has the hero's ONLY production mount, and it passes `report={previewHeroReport}`
 * — an object the page synthesizes at :1212 from placeholder data, which never carries
 * `niche_context`. The gate therefore read `undefined` on every render that ever happened,
 * and the component test stayed green because it hand-built `{ niche, niche_context }`
 * itself. (That mount is also inside `<div aria-hidden="true" inert>` behind a blur, so
 * even a wired hero would have disclosed nothing to a reader.)
 *
 * So this file starts one level up, like `portfolioSummary.test.ts` beside it: it runs the
 * real `+page.server.ts` load against a realistic `/solutions` response carrying a captured
 * run's `niche_context`, renders the real page component, and asserts on rendered DOM —
 * including that the disclosure is not inside an aria-hidden/inert subtree.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";
import type { Job } from "$lib/types/job";

const mocks = vi.hoisted(() => ({
  fetchBackend: vi.fn(),
}));

vi.mock("$lib/backend", () => ({
  fetchBackend: mocks.fetchBackend,
}));

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
    shouldKeepSSEOpen: vi.fn(() => false),
    getReportSummary: vi.fn(() => Promise.resolve(null)),
    getDiscoveryShareStatus: vi.fn(() =>
      Promise.resolve({ isShared: false, solutionVotes: {} })),
    getSolutions: vi.fn(() => Promise.resolve({ solutionIdeas: [] })),
    getDiscoveryData: vi.fn(() => Promise.resolve(null)),
    getPreviewReport: vi.fn(() => Promise.resolve(null)),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
  };
});

import { load } from "../+page.server";
import PageComponent from "../+page.svelte";
import {
  ON_NICHE_RUN,
  REFRAMED_RUN,
  type CapturedRun,
  expectDiscloses,
  expectSilent,
} from "$lib/components/__tests__/fixtures/nicheReframeSurface";

const IDEAS = [
  {
    solution_name: "Alpha Idea",
    idea_id: "idea-alpha",
    idea_revision: 1,
    description: "Reconciles service records against the parts actually shipped",
    value_proposition: "Cuts the reconciliation pass from a day to an hour",
    market_fit_score: 0.72,
    technical_feasibility_score: 0.68,
    adjusted_composite_score: 0.71,
  },
];

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function event() {
  return {
    params: { jobId: "job-1" },
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1", email: "owner@example.com" } }),
    },
  } as never;
}

/** The shape GET /api/jobs/:jobId/solutions returns for a verified pool. `niche_context`
 *  is a niche-scoped preview field (backend routes/schemas/sharedDiscoveryPayload.ts), so
 *  the backend serves it whenever it serves a preview report at all. */
function verifiedSolutionsResponse(run: CapturedRun) {
  return {
    solutionIdeas: IDEAS,
    selectedSolution: null,
    selectedSolutions: null,
    selectedSolutionIds: null,
    selectedSolutionRefs: null,
    selectionRationale: null,
    selectionDecisionProfile: null,
    selectionDecisionProfileVersion: null,
    selectionDraft: { version: 1, items: [], selectionFingerprint: null },
    canRegenerate: true,
    ideaBatchCompletedCount: 0,
    maxIdeaBatches: 3,
    activeOperation: null,
    status: "AWAITING_SELECTION",
    candidatePoolVersion: 4,
    artifactVerification: "verified",
    artifactReason: null,
    previewReport: {
      niche: run.niche,
      generated_at: "2026-08-16T17:36:58.808198Z",
      niche_context: run.niche_context,
    },
  };
}

function backendJob(run: CapturedRun) {
  return {
    id: "job-1",
    niche: run.niche,
    status: "AWAITING_SELECTION",
    entryMode: "standard",
    solutionIdeas: IDEAS,
    selectedSolutions: [],
    assets: [],
    stagesCompleted: 5,
    totalStages: 16,
  } as unknown as Job;
}

async function loadPageData(run: CapturedRun) {
  mocks.fetchBackend.mockImplementation((path: string) => {
    if (path === "/api/jobs/job-1") return Promise.resolve(response(backendJob(run)));
    if (path === "/api/jobs/job-1/solutions") {
      return Promise.resolve(response(verifiedSolutionsResponse(run)));
    }
    return Promise.resolve(response({}, 404));
  });
  const data = (await load(event())) as Record<string, unknown>;
  return {
    ...data,
    creditBalance: 100,
    stageCosts: {
      discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3,
    },
  } as Record<string, unknown>;
}

beforeEach(() => {
  vi.clearAllMocks();
  const state = page as unknown as {
    params: Record<string, string>;
    data: Record<string, unknown>;
  };
  state.params = { jobId: "job-1" };
  state.data = {
    ...state.data,
    featureAccess: {},
    creditBalance: 100,
    stageCosts: {
      discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3,
    },
  };
});

afterEach(() => {
  cleanup();
});

describe("job page — a substituted market is disclosed where the reader is", () => {
  it("discloses the submitted input on a run Stage 1 reframed", async () => {
    const data = await loadPageData(REFRAMED_RUN);

    // Guard the input, not the conclusion: the load must have carried the classification
    // through, or the DOM assertion below could pass (or fail) for the wrong reason.
    const carried = (data.previewReport as { niche_context?: { audience_scope?: string } })
      ?.niche_context;
    expect(carried?.audience_scope).toBe(REFRAMED_RUN.niche_context.audience_scope);

    const view = render(PageComponent, { props: { data: data as never } });

    await waitFor(() => expectDiscloses(view.container, REFRAMED_RUN));
  });

  it("says nothing on a run Stage 1 classified as already on-niche", async () => {
    const data = await loadPageData(ON_NICHE_RUN);

    const view = render(PageComponent, { props: { data: data as never } });

    // Wait for the page to settle on real content before asserting an absence.
    await view.findByText("Alpha Idea");
    expectSilent(view.container);
  });
});
