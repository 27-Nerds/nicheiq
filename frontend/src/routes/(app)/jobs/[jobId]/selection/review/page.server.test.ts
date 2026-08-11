import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ fetchBackend: vi.fn() }));

vi.mock("$lib/backend", () => ({ fetchBackend: mocks.fetchBackend }));

const { load } = await import("./+page.server");

function event() {
  return {
    params: { jobId: "job-1" },
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1" } }),
    },
  } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("selection review server load", () => {
  it("loads collaborator signals even after sharing closes", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      isShared: false,
      solutionVotes: { "Signal desk": 2 },
      solutionVotesById: { "idea-a": 2 },
      voteRationales: [{
        solutionId: "idea-a",
        solutionName: "Signal desk",
        comment: "Clear workflow fit.",
      }],
    }), { status: 200 }));

    const result = await load(event()) as Record<string, unknown>;

    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      "/api/jobs/job-1/discovery-share",
      { headers: { "X-User-ID": "user-1" } },
    );
    expect(result).toEqual({
      collaboratorSignalsStatus: "loaded",
      solutionVotes: { "Signal desk": 2 },
      solutionVotesById: { "idea-a": 2 },
      voteRationales: [{
        solutionId: "idea-a",
        solutionName: "Signal desk",
        comment: "Clear workflow fit.",
      }],
    });
  });

  it("returns an empty signal set when no share record is available", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(null, { status: 404 }));

    await expect(load(event())).resolves.toEqual({
      collaboratorSignalsStatus: "absent",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });

  it("omits a partial rationale whose comment field is missing", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      voteRationales: [{ solutionId: "idea-a", solutionName: "Signal desk" }],
    }), { status: 200 }));

    const result = await load(event());

    expect(result, "missing comment must omit the collaborator note").toEqual({
      collaboratorSignalsStatus: "loaded",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });

  it("omits a partial rationale whose comment field is null", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      voteRationales: [{
        solutionId: "idea-a",
        solutionName: "Signal desk",
        comment: null,
      }],
    }), { status: 200 }));

    const result = await load(event());

    expect(result, "null comment must omit the collaborator note").toEqual({
      collaboratorSignalsStatus: "loaded",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });

  it("omits a wrong-typed vote count instead of passing it to the receipt", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      solutionVotesById: { "idea-a": "two" },
    }), { status: 200 }));

    const result = await load(event());

    expect(result, "non-numeric count must omit the vote fact").toEqual({
      collaboratorSignalsStatus: "loaded",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });

  it("treats an empty-array vote map as no receipt fact", async () => {
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      solutionVotes: [],
    }), { status: 200 }));

    const result = await load(event());

    expect(result, "array-shaped vote map must omit all vote facts").toEqual({
      collaboratorSignalsStatus: "loaded",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });

  it.each([
    ["a network failure", () => Promise.reject(new Error("offline"))],
    ["a non-OK response", () => Promise.resolve(new Response(null, { status: 503 }))],
    ["an invalid JSON response", () => Promise.resolve(new Response("not-json", { status: 200 }))],
  ])("marks collaborator signals unavailable after %s", async (_label, response) => {
    mocks.fetchBackend.mockImplementation(response);

    await expect(load(event())).resolves.toEqual({
      collaboratorSignalsStatus: "unavailable",
      solutionVotes: {},
      solutionVotesById: {},
      voteRationales: [],
    });
  });
});
