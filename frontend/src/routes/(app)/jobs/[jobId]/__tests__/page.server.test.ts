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

  it("keeps valid candidates from the job as the fallback on a solutions failure", async () => {
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

    expect(result.solutionsFetchFailed).toBe(false);
    expect(result.job.solutionIdeas).toHaveLength(1);
    expect(result.job.solutionIdeas[0].solution_name).toBe("Fallback candidate");
  });

  it("treats a successful empty response as a legitimate empty candidate set", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job([])));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response({}, 404));
    });

    const result = await load(event()) as Record<string, unknown>;

    expect(result.solutions).toEqual([]);
    expect(result.solutionsFetchFailed).toBe(false);
  });

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
          return Promise.resolve(response({ solutionIdeas: [] }));
        }
        if (path === "/api/jobs/job-1/preview-report") {
          return Promise.resolve(response(previewReport));
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
      expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
        "/api/public/catalog/top-pain-points?limit=8&freePreview=true",
        expect.anything(),
      );
    },
  );

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
});
