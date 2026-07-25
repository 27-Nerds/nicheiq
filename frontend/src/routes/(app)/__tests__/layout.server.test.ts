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

function event() {
  return {
    locals: {
      auth: vi.fn().mockResolvedValue({ user: { id: "user-1" } }),
    },
    url: new URL("https://nicheiq.test/dashboard"),
  } as never;
}

async function loadData() {
  const result = await load(event());
  if (!result) throw new Error("Expected authenticated layout data");
  return result;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("authenticated app layout billing state", () => {
  it("marks validated balance and stage costs as available", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/billing/balance") return Promise.resolve(response({ available: 731 }));
      if (path === "/api/billing/stage-costs") return Promise.resolve(response({ deep_research: 100 }));
      if (path === "/api/saves/counts") return Promise.resolve(response({ ideas: 0, painPoints: 0 }));
      return Promise.resolve(response({ subscription: null }));
    });

    const result = await loadData();

    expect(result.creditBalance).toBe(731);
    expect(result.stageCosts.deep_research).toBe(100);
    expect(result.billingLoadState).toEqual({
      balanceUnavailable: false,
      costsUnavailable: false,
    });
  });

  it("keeps legacy fallback values but marks failed billing data unavailable", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/billing/balance") return Promise.resolve(response({}, 503));
      if (path === "/api/billing/stage-costs") return Promise.resolve(response({}));
      if (path === "/api/saves/counts") return Promise.resolve(response({ ideas: 0, painPoints: 0 }));
      return Promise.resolve(response({ subscription: null }));
    });

    const result = await loadData();

    expect(result.creditBalance).toBe(0);
    expect(result.stageCosts.deep_research).toBe(15);
    expect(result.billingLoadState).toEqual({
      balanceUnavailable: true,
      costsUnavailable: true,
    });
  });

  it("does not let one failed request hide a valid billing response", async () => {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/billing/balance") return Promise.reject(new Error("balance offline"));
      if (path === "/api/billing/stage-costs") return Promise.resolve(response({ deep_research: 100 }));
      if (path === "/api/saves/counts") return Promise.resolve(response({ ideas: 0, painPoints: 0 }));
      return Promise.resolve(response({ subscription: null }));
    });

    const result = await loadData();

    expect(result.billingLoadState).toEqual({
      balanceUnavailable: true,
      costsUnavailable: false,
    });
  });
});
