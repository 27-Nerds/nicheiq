/**
 * Finding D2, primary defect: the analyst portfolio summary was DEAD in production.
 *
 * SelectionWorkbench gates its "Discovery take" on
 * `ideaPortfolioSummaryFingerprint === livePortfolioFingerprint`, but no call site
 * passed that prop, so the gate could only ever fail. Every job with a summary rendered
 * "Discovery take unavailable", and the analyst "Recommended" badge never appeared.
 *
 * The component's own suite was green throughout, because its `baseProps` INJECTED a
 * fingerprint no caller supplied. A component test structurally cannot catch a prop the
 * page never passes, so this test starts one level up: it runs the real `+page.server.ts`
 * load against a realistic verified `/solutions` response, feeds the result to the real
 * page component, and asserts on rendered DOM. Nothing here is hand-fed to the workbench.
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
// The banner sentence is asserted through the shared constant, never a copy: three
// surfaces render it and a literal here would let one of them drift.
import { EVIDENCE_WITHHELD_DETAIL, EVIDENCE_WITHHELD_TITLE } from "$lib/selection/labels";

/**
 * The literal the pipeline writes into `idea_portfolio_summary_fingerprint` for a pool of
 * exactly these two ideas. Deliberately a hand-written constant rather than a re-implemented
 * hash: a mirrored helper would silently follow a contract change on either side, which is
 * how the dead prop survived review in the first place. `ideaPortfolioFingerprint` is pinned
 * to this same string in backend/src/routes/__tests__/discoveryShares.portfolioSummary.test.ts.
 */
const POOL_FINGERPRINT = '{"version":1,"ideas":[["idea-alpha",1],["idea-beta",1]]}';

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
  {
    solution_name: "Beta Idea",
    idea_id: "idea-beta",
    idea_revision: 1,
    description: "Tracks warranty claims through their approval chain",
    value_proposition: "Shows where a claim stalled without opening the portal",
    market_fit_score: 0.61,
    technical_feasibility_score: 0.64,
    adjusted_composite_score: 0.62,
  },
];

const SUMMARY = [
  "Both ideas serve the same operator but at different points in the job.",
  "Alpha Idea most deserves deeper validation because its buyer is named directly in the evidence.",
].join("\n\n");

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

/** The exact shape GET /api/jobs/:jobId/solutions returns for a verified pool
 *  (backend/src/routes/jobs.ts). `previewReport` is present only when
 *  `artifactVerification === 'verified'`, and it carries the fingerprint. */
function verifiedSolutionsResponse(overrides: Record<string, unknown> = {}) {
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
      niche: "appliance repair shops",
      generated_at: "2026-08-01T00:00:00.000Z",
      idea_portfolio_summary: SUMMARY,
      idea_portfolio_summary_fingerprint: POOL_FINGERPRINT,
    },
    ...overrides,
  };
}

function backendJob(entryMode = "standard") {
  return {
    id: "job-1",
    niche: "appliance repair shops",
    status: "AWAITING_SELECTION",
    entryMode,
    solutionIdeas: IDEAS,
    selectedSolutions: [],
    assets: [],
    stagesCompleted: 5,
    totalStages: 16,
  } as unknown as Job;
}

async function loadPageData(solutionsBody: unknown, entryMode = "standard") {
  mocks.fetchBackend.mockImplementation((path: string) => {
    if (path === "/api/jobs/job-1") return Promise.resolve(response(backendJob(entryMode)));
    if (path === "/api/jobs/job-1/solutions") return Promise.resolve(response(solutionsBody));
    return Promise.resolve(response({}, 404));
  });
  const data = await load(event()) as Record<string, unknown>;
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
  // The Discovery take lives in the workbench's decision-guide block, which the job page
  // renders only for a decision-tools grant (SelectionWorkbench.svelte: `interactive &&
  // decisionTools`). That grant reaches the page through `page.data.featureAccess`.
  state.data = {
    ...state.data,
    featureAccess: { decisionTools: true },
    creditBalance: 100,
    stageCosts: {
      discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3,
    },
  };
});

afterEach(() => {
  cleanup();
});

describe("job page — stored portfolio prose cannot become recommendation authority", () => {
  it("shows neutral guidance and no recommendation badge even for a matching pool", async () => {
    const data = await loadPageData(verifiedSolutionsResponse());

    // Guard the input, not the conclusion: the load must have carried the fingerprint
    // through. Without this the DOM assertions below could pass for the wrong reason.
    expect((data.previewReport as Record<string, unknown>).idea_portfolio_summary_fingerprint)
      .toBe(POOL_FINGERPRINT);

    const view = render(PageComponent, { props: { data: data as never } });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("Discovery take unavailable");
    expect(take).not.toHaveTextContent(
      "most deserves deeper validation because its buyer is named directly in the evidence",
    );

    const table = await view.findByRole("table", { name: "Ranked ideas" });
    await waitFor(() =>
      expect(table.querySelectorAll("[data-solution-name]")).toHaveLength(2));
    expect(table.querySelector('[data-solution-name="Alpha Idea"]'))
      .not.toHaveTextContent("Recommended");
    expect(table.querySelector('[data-solution-name="Beta Idea"]'))
      .not.toHaveTextContent("Recommended");
  });

  it("says the guidance is unavailable when the pool grew past the summary's fingerprint", async () => {
    // The D2 scenario itself: a summary written against these two ideas, beside a pool
    // that has since gained a third. The candidate list stays current; only the guidance
    // about it is withheld.
    const grownPool = [
      ...IDEAS,
      {
        solution_name: "Gamma Idea",
        idea_id: "idea-gamma",
        idea_revision: 1,
        description: "Schedules recall work against technician availability",
        value_proposition: "Keeps recall jobs from colliding with booked calls",
        market_fit_score: 0.58,
        technical_feasibility_score: 0.6,
        adjusted_composite_score: 0.59,
      },
    ];
    const data = await loadPageData(verifiedSolutionsResponse({ solutionIdeas: grownPool }));

    const view = render(PageComponent, { props: { data: data as never } });

    const take = await view.findByLabelText("Discovery take");
    expect(take).toHaveTextContent("Discovery take unavailable");
    expect(take).not.toHaveTextContent("most deserves deeper validation");
    expect(view.queryByText("Recommended")).toBeNull();
  });

  it("withholds evidence framing, in the shared words, when the artifacts are untrusted", async () => {
    const data = await loadPageData(verifiedSolutionsResponse({
      artifactVerification: "untrusted",
      artifactReason: "version_mismatch",
      previewReport: null,
    }));

    const view = render(PageComponent, { props: { data: data as never } });

    const banner = await view.findByText(EVIDENCE_WITHHELD_TITLE);
    expect(banner.parentElement).toHaveTextContent(
      EVIDENCE_WITHHELD_DETAIL,
    );
  });

  it("leaves the withheld banner off the idea-check view, which has its own card", async () => {
    // `validate_idea` never mounts the ranked list on first paint, so the shared banner
    // would assert that "the ideas themselves are current" about ideas nobody can see, and
    // would sit directly above the purpose-built card for the same state. One state, one
    // message: the idea-check card wins here because it is the only one with a retry.
    const data = await loadPageData(verifiedSolutionsResponse({
      artifactVerification: "untrusted",
      artifactReason: "version_mismatch",
      previewReport: null,
    }), "validate_idea");

    const view = render(PageComponent, { props: { data: data as never } });

    expect(await view.findByText("Idea check snapshot unavailable")).toBeInTheDocument();
    expect(view.queryByText(EVIDENCE_WITHHELD_TITLE)).toBeNull();
  });
});
