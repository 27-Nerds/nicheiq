import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchBackend: vi.fn(),
}));

vi.mock("$lib/backend", () => ({
  fetchBackend: mocks.fetchBackend,
}));

import { load } from "../+page.server";

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

function job(solutionIdeas: unknown[]) {
  return {
    id: "job-1",
    status: "AWAITING_SELECTION",
    solutionIdeas,
    assets: [],
  };
}

function selectionContext(
  solutionIdeas: unknown[],
  previewReport: unknown = null,
  artifactVerification: "verified" | "untrusted" = "verified",
) {
  return {
    solutionIdeas,
    previewReport: artifactVerification === "verified" ? previewReport : null,
    artifactVerification,
    artifactReason: artifactVerification === "untrusted" ? "version_mismatch" : null,
    selectedSolution: null,
    selectedSolutions: null,
    selectedSolutionIds: null,
    selectedSolutionRefs: null,
    selectionRationale: null,
    selectionDecisionProfile: null,
    selectionDraft: { version: 1, items: [] },
    canRegenerate: true,
    ideaBatchCompletedCount: 0,
    maxIdeaBatches: 3,
    activeOperation: null,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("job selection candidate load state", () => {
  it("surfaces a failed solutions request when the job has no valid fallback", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job([])));
      if (path === "/api/jobs/job-1/solutions") return Promise.resolve(response({}, 503));
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, unknown>;

    expect(result.solutions).toBeNull();
    expect(result.solutionsFetchFailed).toBe(true);
  });

  it("does not render raw job candidates when the verified context request fails", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response(job([{
          solution_name: "Fallback candidate",
          description: "Valid job candidate",
          value_proposition: "Still visible",
        }])));
      }
      if (path === "/api/jobs/job-1/solutions") return Promise.resolve(response({}, 503));
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, any>;

    expect(result.solutionsFetchFailed).toBe(true);
    expect(result.solutions).toBeNull();
    expect(result.job.solutionIdeas).toEqual([]);
  });

  it("treats a successful empty response as a legitimate empty candidate set", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job([])));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response(selectionContext([], {})));
      }
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, unknown>;

    expect(result.solutions).toEqual([]);
    expect(result.solutionsFetchFailed).toBe(false);
  });

  it("loads historical collaborator feedback when the public share is inactive", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job([{
        idea_id: "idea-chosen",
        idea_revision: 1,
        solution_name: "Chosen idea",
        description: "Valid candidate",
        value_proposition: "Chosen value",
      }])));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response(selectionContext([], {})));
      }
      if (path === "/api/jobs/job-1/discovery-share") {
        return Promise.resolve(response({
          isShared: false,
          solutionVotes: { "Chosen idea": 2 },
          solutionVotesById: { "idea-chosen": 2 },
          voteRationales: [{
            solutionId: "idea-chosen",
            solutionName: "Chosen idea",
            comment: "This fits the workflow.",
          }],
        }));
      }
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, any>;

    expect(result.solutionVotes).toEqual({ "Chosen idea": 2 });
    expect(result.solutionVotesById).toEqual({ "idea-chosen": 2 });
    expect(result.voteRationales).toEqual([{
      solutionId: "idea-chosen",
      solutionName: "Chosen idea",
      comment: "This fits the workflow.",
    }]);
  });

  it.each(["RUNNING_PHASE2", "COMPLETED"])(
    "retains collaborator feedback after selection while the job is %s",
    async (status) => {
      const selectedJob = {
        ...job([{
          idea_id: "idea-chosen",
          idea_revision: 1,
          solution_name: "Chosen idea",
          description: "Valid candidate",
          value_proposition: "Chosen value",
        }]),
        status,
        selectedSolutions: ["Chosen idea"],
      };
      mocks.fetchBackend.mockImplementation((path: string) => {
        if (path === "/api/jobs/job-1") return Promise.resolve(response(selectedJob));
        if (path === "/api/jobs/job-1/discovery-share") {
          return Promise.resolve(response({
            isShared: false,
            solutionVotes: { "Chosen idea": 1 },
            solutionVotesById: { "idea-chosen": 1 },
            voteRationales: [{
              solutionId: "idea-chosen",
              solutionName: "Chosen idea",
              comment: "Keep this one.",
            }],
          }));
        }
        return Promise.resolve(response({}, 404));
      });

      const result = await load(event()) as Record<string, any>;

      expect(result.solutionVotesById).toEqual({ "idea-chosen": 1 });
      expect(result.voteRationales).toHaveLength(1);
      expect(mocks.fetchBackend).toHaveBeenCalledWith(
        "/api/jobs/job-1/discovery-share",
        expect.anything(),
      );
    },
  );

  it.each(["RUNNING_PHASE2", "COMPLETED"])(
    "hydrates saved annotations as a read-only record while the job is %s",
    async (status) => {
      const selectedJob = {
        ...job([]),
        status,
        selectedSolutions: ["Chosen idea"],
      };
      const savedAnnotations = {
        revision: 3,
        document: {
          version: 1,
          surfaces: {
            "research:page": {
              strokes: [{
                id: "stroke-1",
                color: "#dc2626",
                width: 4,
                createdAt: 1,
                points: [[0, 0], [10, 10]],
              }],
            },
          },
        },
        updatedAt: "2026-08-02T09:00:00.000Z",
      };
      mocks.fetchBackend.mockImplementation((path: string) => {
        if (path === "/api/jobs/job-1") return Promise.resolve(response(selectedJob));
        if (path === "/api/jobs/job-1/discovery-annotations") {
          return Promise.resolve(response(savedAnnotations));
        }
        return Promise.resolve(response({}, 404));
      });

      const result = await load(event()) as Record<string, any>;

      expect(result.annotationDocument).toEqual(savedAnnotations);
      expect(mocks.fetchBackend).toHaveBeenCalledWith(
        "/api/jobs/job-1/discovery-annotations",
        expect.anything(),
      );
    },
  );

  it.each([
    ["QUEUED", "SEED_IDEA"],
    ["RUNNING", "SEED_IDEA"],
    ["QUEUED", "REGENERATE"],
    ["REGENERATING", "REGENERATE"],
  ])(
    "keeps the complete selection workspace loaded while %s %s work is active",
    async (status, activeDispatchKind) => {
      const selectionMutationJob = {
        ...job([]),
        status,
        activeDispatchKind,
      };
      const previewReport = { user_segments: [{ name: "Freelance bookkeepers" }] };
      const discoveryData = { metadata: { source_count: 12 } };

      mocks.fetchBackend.mockImplementation((path: string) => {
        if (path === "/api/jobs/job-1") return Promise.resolve(response(selectionMutationJob));
        if (path === "/api/jobs/job-1/solutions") {
          return Promise.resolve(response(selectionContext([], previewReport)));
        }
        if (path === "/api/jobs/job-1/discovery-data") {
          return Promise.resolve(response(discoveryData));
        }
        if (path === "/api/selection/metric-explanations") {
          return Promise.resolve(response({ metrics: {} }));
        }
        return Promise.resolve(response({}, 404));
      });

      const result = await load(event()) as Record<string, any>;

      expect(result.solutions).toEqual([]);
      expect(result.previewReport).toEqual(previewReport);
      expect(result.discoveryData).toEqual(discoveryData);
      expect(result.metricExplanations).toEqual({ metrics: {} });
      expect(result.selectionArtifactVerification).toBe("verified");
      expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
        "/api/public/catalog/top-pain-points?limit=8&freePreview=true",
        expect.anything(),
      );
      expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
        "/api/jobs/job-1/preview-report",
        expect.anything(),
      );
    },
  );

  it("keeps canonical candidates but withholds preview framing when the context is untrusted", async () => {
    const candidate = {
      idea_id: "idea-current",
      idea_revision: 2,
      solution_name: "Current candidate",
      description: "Current pool row",
      value_proposition: "Current value",
    };
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job([candidate])));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response(selectionContext([candidate], { stale: true }, "untrusted")));
      }
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, any>;

    expect(result.solutions).toEqual([expect.objectContaining({ idea_id: "idea-current" })]);
    expect(result.job.solutionIdeas).toEqual(result.solutions);
    expect(result.previewReport).toBeNull();
    expect(result.selectionArtifactVerification).toBe("untrusted");
    expect(result.selectionArtifactReason).toBe("version_mismatch");
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/preview-report",
      expect.anything(),
    );
  });

  it("skips the Discovery-dossier fetches at AWAITING_GATE without tripping failure flags", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({
          ...job([]),
          status: "AWAITING_GATE",
          activeDispatchKind: null,
        }));
      }
      // The backend's gate-status guard 400s the artifact endpoints mid-gate.
      return Promise.resolve(response({}, 400));
    });

    const result = await load(event()) as Record<string, unknown>;

    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/discovery-data",
      expect.anything(),
    );
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/preview-report",
      expect.anything(),
    );
    expect(result.discoveryDataFetchFailed).toBe(false);
    expect(result.previewReportFetchFailed).toBe(false);
  });

  it("keeps initial queued discovery on the lightweight progress data contract", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({
          ...job([]),
          status: "QUEUED",
          activeDispatchKind: null,
        }));
      }
      if (path === "/api/public/catalog/top-pain-points?limit=8&freePreview=true") {
        return Promise.resolve(response({ painPoints: [] }));
      }
      return Promise.resolve(response({}, 404));
    });

    await load(event());

    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      "/api/public/catalog/top-pain-points?limit=8&freePreview=true",
      expect.anything(),
    );
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/preview-report",
      expect.anything(),
    );
  });

  it("does not fetch Discovery catalog detours for queued Deep Research", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") {
        return Promise.resolve(response({
          ...job([]),
          status: "QUEUED",
          activeDispatchKind: "DEEP_RESEARCH",
          selectedSolutions: ["Chosen idea"],
        }));
      }
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, unknown>;

    expect(result.catalogPainPoints).toEqual([]);
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/public/catalog/top-pain-points?limit=8&freePreview=true",
      expect.anything(),
    );
  });
});
