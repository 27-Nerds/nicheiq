import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { page } from "$app/state";

const mocks = vi.hoisted(() => ({
  fetchBackend: vi.fn(),
  selectSolution: vi.fn(),
}));

vi.mock("$lib/backend", () => ({ fetchBackend: mocks.fetchBackend }));
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
  getStageCosts: vi.fn(),
  seedIdea: vi.fn(),
  selectSolution: mocks.selectSolution,
  shouldKeepSSEOpen: vi.fn(() => false),
  subscribeToProgress: vi.fn(() => () => undefined),
}));

vi.mock("$lib/components/annotations/AnnotationProvider.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/chat/ChatThread.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/ui/WorkspaceOverlay.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/nav/PhaseNav.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/tour/TourHost.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/tour/TourRestartButton.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/ui/PageHeader.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/selection/ConceptForge.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/selection/BatchActivity.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/selection/EvaluationActivity.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/selection/DecisionBrief.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/selection/ExperimentWorkspace.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));
vi.mock("$lib/components/SolutionDetail.svelte", async () => ({
  default: (await import("./SurfaceStub.svelte")).default,
}));

const { load } = await import("../+layout.server");
const { default: MalformedDecisionStateSurface } = await import("./MalformedDecisionStateSurface.svelte");

const idea = {
  idea_id: "idea-a",
  idea_revision: 3,
  solution_name: "Signal desk",
  short_description: "Turns recurring market signals into a focused briefing.",
};

function response(body: unknown, status = 200): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deeplyMalformedDecisionState() {
  return {
    schemaVersion: 1,
    jobId: "job-1",
    status: "AWAITING_SELECTION",
    shortlist: {
      version: 7,
      fingerprint: "opaque-shortlist-fingerprint",
      items: [{ ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" }],
      staleItems: [],
    },
    profile: null,
    founderFit: null,
    challenges: [],
    ownerEvidence: [],
    assumptions: [],
    experiments: [],
    conclusions: [],
    staleCounts: {
      shortlist: 0,
      profile: 0,
      founderFit: 0,
      challenges: 0,
      ownerEvidence: 0,
      assumptions: 0,
      experiments: 0,
      conclusions: 0,
      total: 0,
    },
    deepResearch: {
      eligible: true,
      optionalWorkRequired: false,
      blockers: [],
    },
    nextAction: {
      kind: "start_deep_research",
      target: "deep_research",
      reason: "The saved shortlist is ready.",
      required: false,
      ideas: [],
      lens: null,
      records: [{ kind: "challenge", id: "challenge-1", version: "one" }],
    },
  };
}

function event() {
  return {
    params: { jobId: "job-1" },
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1" } }),
    },
    url: new URL("https://nicheiq.test/jobs/job-1/selection/review"),
    parent: vi.fn().mockResolvedValue({ featureAccess: { analyst: true, decisionTools: true } }),
  } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  page.url = new URL("https://nicheiq.test/jobs/job-1/selection/review") as typeof page.url;
  mocks.fetchBackend.mockImplementation((path: string) => {
    if (path === "/api/jobs/job-1") {
      return Promise.resolve(response({
        id: "job-1",
        niche: "market signals",
        status: "AWAITING_SELECTION",
        stagesCompleted: 5,
        assets: [],
        solutionIdeas: [idea],
        selectionDraft: {
          version: 7,
          fingerprint: "opaque-shortlist-fingerprint",
          items: [{ ideaId: "idea-a", ideaRevision: 3, title: "Signal desk" }],
        },
      }));
    }
    if (path === "/api/jobs/job-1/solutions") {
      return Promise.resolve(response({ solutionIdeas: [idea] }));
    }
    if (path === "/api/jobs/job-1/selection-decision-state") {
      return Promise.resolve(response(deeplyMalformedDecisionState()));
    }
    return Promise.resolve(response(null, 404));
  });
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe("malformed decision-state buyer surface", () => {
  it("shows the load-failure alert and removes purchase; a boundary cast would hide the alert and enable it", async () => {
    const loaded = await load(event());
    if (!loaded) throw new Error("Expected selection layout data");

    const data = {
      ...loaded,
      collaboratorSignalsStatus: "absent",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
      creditBalance: 731,
      stageCosts: { deep_research: 100 },
      billingLoadState: { balanceUnavailable: false, costsUnavailable: false },
    } as never;
    const view = render(MalformedDecisionStateSurface, { props: { data } });

    const alert = view.getByRole("alert");
    expect(alert).toHaveTextContent("Some selection data is unavailable");
    expect(alert).toHaveTextContent("Your saved shortlist and decision state could not be loaded.");
    expect(view.queryByText("No saved idea scope is available in this selection record."))
      .not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Start Deep Research" })).not.toBeInTheDocument();
    expect(mocks.selectSolution).not.toHaveBeenCalled();
  });
});
