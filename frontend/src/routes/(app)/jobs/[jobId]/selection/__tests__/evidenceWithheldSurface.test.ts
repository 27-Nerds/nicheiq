/**
 * Finding D2, tertiary defect, at the surface the critic named as the worst instance.
 *
 * /selection/review's duplicate-idea gate charges on `data.overlapGroups`, which the
 * layout loader can only populate from a VERIFIED /solutions snapshot. All six
 * `UntrustedRunArtifactReason` states (legacy_missing_version on every pre-migration job,
 * legacy_missing_fingerprint, unresolvable_candidate_pool, version_mismatch,
 * content_mismatch, and preview_unavailable during regeneration) emptied it with no
 * user-visible signal, while the job page showed a banner for the same job. This renders the real layout +
 * review page from the real loader output and asserts the banner is there, in the same
 * words the job page uses.
 *
 * The harness component is shared with malformedDecisionStateSurface.test.ts: it is a
 * plain `<SelectionLayout><ReviewPage/></SelectionLayout>` mount, not specific to that
 * finding.
 */
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { page } from "$app/state";
// Asserted through the shared constants, never a copy of the sentence. Both banners are
// imported: literal copies of the load-failure wording here once blocked its own fix, the
// same trap this file's sibling copy test exists to prevent.
import {
  CANDIDATES_UNAVAILABLE_DETAIL,
  CANDIDATES_UNAVAILABLE_TITLE,
  EVIDENCE_WITHHELD_DETAIL,
  EVIDENCE_WITHHELD_TITLE,
} from "$lib/selection/labels";

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
const { default: SelectionReviewSurface } = await import("./MalformedDecisionStateSurface.svelte");

const idea = {
  idea_id: "idea-a",
  idea_revision: 3,
  solution_name: "Signal desk",
  description: "Turns recurring market signals into a focused briefing.",
  value_proposition: "One briefing instead of five dashboards.",
  short_description: "Turns recurring market signals into a focused briefing.",
};

function response(body: unknown, status = 200): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
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

function backendJob() {
  return {
    id: "job-1",
    niche: "market signals",
    status: "AWAITING_SELECTION",
    stagesCompleted: 5,
    assets: [],
    solutionIdeas: [idea],
    selectionDraft: { version: 1, items: [] },
  };
}

/** Mount the real layout + review page on whatever the real loader produced. */
async function renderSurface() {
  const loaded = await load(event());
  if (!loaded) throw new Error("Expected selection layout data");
  return render(SelectionReviewSurface, {
    props: {
      data: {
        ...loaded,
        collaboratorSignalsStatus: "absent",
        solutionVotes: {},
        solutionVotesById: {},
        voteRationales: [],
        creditBalance: 731,
        stageCosts: { deep_research: 100 },
        billingLoadState: { balanceUnavailable: false, costsUnavailable: false },
      } as never,
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  page.url = new URL("https://nicheiq.test/jobs/job-1/selection/review") as typeof page.url;
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe("/selection/review — degraded run artifacts are stated, not absorbed", () => {
  it("shows the job page's withheld banner for a legacy job with no pool version", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(backendJob()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [idea],
          artifactVerification: "untrusted",
          artifactReason: "legacy_missing_version",
          previewReport: null,
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const view = await renderSurface();

    const banner = view.getByText(EVIDENCE_WITHHELD_TITLE);
    const region = banner.closest("aside");
    expect(region).toHaveTextContent(
      EVIDENCE_WITHHELD_DETAIL,
    );
    expect(region).toHaveAttribute("data-artifact-reason", "legacy_missing_version");
  });

  it("says the ranked pool failed to load rather than showing an empty pool", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(backendJob()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.reject(new Error("network unavailable"));
      }
      return Promise.resolve(response(null, 404));
    });

    const view = await renderSurface();

    const banner = view.getByText(CANDIDATES_UNAVAILABLE_TITLE);
    expect(banner.closest("aside")).toHaveTextContent(
      CANDIDATES_UNAVAILABLE_DETAIL,
    );
    // One boundary message at a time: a pool that never arrived is not an unconfirmed one.
    expect(view.queryByText(EVIDENCE_WITHHELD_TITLE)).toBeNull();
  });

  it("stays quiet on a verified snapshot", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(backendJob()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({
          solutionIdeas: [idea],
          artifactVerification: "verified",
          artifactReason: null,
          previewReport: { overlap_groups: [] },
        }));
      }
      return Promise.resolve(response(null, 404));
    });

    const view = await renderSurface();

    expect(view.queryByText(EVIDENCE_WITHHELD_TITLE)).toBeNull();
    expect(view.queryByText(CANDIDATES_UNAVAILABLE_TITLE)).toBeNull();
  });
});
