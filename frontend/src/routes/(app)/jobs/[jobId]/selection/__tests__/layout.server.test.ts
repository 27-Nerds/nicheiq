import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchBackend: vi.fn(),
}));

vi.mock("$lib/backend", () => ({
  fetchBackend: mocks.fetchBackend,
}));

import { load } from "../+layout.server";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function event(route = "compare", decisionTools = true) {
  return {
    params: { jobId: "job-1" },
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1" } }),
    },
    url: new URL(`https://nicheiq.test/jobs/job-1/selection/${route}`),
    // The (app) layout resolves the admin-granted feature flags.
    parent: vi.fn().mockResolvedValue({ featureAccess: { analyst: true, decisionTools } }),
  } as never;
}

function job() {
  return {
    id: "job-1",
    status: "AWAITING_SELECTION",
    solutionIdeas: [],
    assets: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("selection layout Discovery navigation", () => {
  it("prefetches saved directions with the Compare route's parallel data", async () => {
    const sets = [{ id: "set-1" }];
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/selection-concept-sets") {
        return Promise.resolve(response({ sets }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.conceptSets).toEqual(sets);
  });

  it("does not fetch saved directions for unrelated selection routes", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("risks"));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.conceptSets).toBeNull();
    expect(mocks.fetchBackend).not.toHaveBeenCalledWith(
      "/api/jobs/job-1/selection-concept-sets",
      expect.anything(),
    );
  });

  it("returns the sections actually present when both artifact outcomes are known", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/preview-report") {
        return Promise.resolve(response({
          detailed_pain_points: [{ title: "Pain", severity_score: 0.8 }],
        }));
      }
      if (path === "/api/jobs/job-1/discovery-data") {
        return Promise.resolve(response(null, 404));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.availableSectionIds).toEqual(["overview", "pain-points"]);
  });

  it("does not treat a failed artifact request as an empty dossier", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      if (path === "/api/jobs/job-1/preview-report") {
        return Promise.reject(new Error("network unavailable"));
      }
      if (path === "/api/jobs/job-1/discovery-data") {
        return Promise.resolve(response(null, 404));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event());
    if (!result) throw new Error("Expected selection layout data");

    expect(result.availableSectionIds).toBeUndefined();
  });
});

describe("selection layout decision-tools gate", () => {
  it("redirects /risks to /compare without the grant", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      return Promise.resolve(response(null, 404));
    });

    await expect(load(event("risks", false))).rejects.toMatchObject({
      status: 307,
      location: "/jobs/job-1/selection/compare",
    });
  });

  it("serves /compare without the grant, skipping the gated fetches", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("compare", false));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionTools).toBe(false);
    expect(result.founderFit).toBeNull();
    expect(result.conceptSets).toBeNull();
    // Not fetched means not failed: the banner must stay down.
    expect(result.selectionLoadState.founderFitUnavailable).toBe(false);
    for (const gated of [
      "/api/jobs/job-1/founder-fit",
      "/api/jobs/job-1/selection-concept-sets",
    ]) {
      expect(mocks.fetchBackend).not.toHaveBeenCalledWith(gated, expect.anything());
    }
  });

  it("still fetches the gated data for a granted owner", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/jobs/job-1") return Promise.resolve(response(job()));
      if (path === "/api/jobs/job-1/solutions") {
        return Promise.resolve(response({ solutionIdeas: [] }));
      }
      return Promise.resolve(response(null, 404));
    });

    const result = await load(event("compare", true));
    if (!result) throw new Error("Expected selection layout data");

    expect(result.decisionTools).toBe(true);
    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      "/api/jobs/job-1/founder-fit",
      expect.anything(),
    );
  });
});
