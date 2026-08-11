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
      if (path === "/api/billing/stage-costs") {
        return Promise.resolve(response({
          discovery: 99,
          deep_research: 100,
          guided: { s1: 19, s2_4: 59, s5: 21, total: 99 },
        }));
      }
      if (path === "/api/saves/counts") return Promise.resolve(response({ ideas: 0, painPoints: 0 }));
      return Promise.resolve(response({ subscription: null }));
    });

    const result = await loadData();

    expect(result.creditBalance).toBe(731);
    expect(result.stageCosts.deep_research).toBe(100);
    expect(result.billingLoadState).toEqual({
      balanceUnavailable: false,
      costsUnavailable: false,
      discoveryCostUnavailable: false,
      guidedCostsUnavailable: false,
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
      discoveryCostUnavailable: true,
      guidedCostsUnavailable: true,
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
      discoveryCostUnavailable: true,
      guidedCostsUnavailable: true,
    });
  });
});

// Feature access is fetched with the same `.catch(() => null)` as the billing
// calls, so without a load-state flag a transient failure is indistinguishable
// from a revoked grant — and the analyst surfaces, which fail closed on it,
// would tell a paying subscriber to subscribe.
describe("authenticated app layout feature access", () => {
  function backend(accessResponse: () => Promise<Response>) {
    mocks.fetchBackend.mockImplementation((path: string) => {
      if (path === "/api/users/user-1/feature-access") return accessResponse();
      if (path === "/api/saves/counts") return Promise.resolve(response({ ideas: 0, painPoints: 0 }));
      return Promise.resolve(response({ subscription: null }));
    });
  }

  it("reports a read grant as available", async () => {
    backend(() => Promise.resolve(response({ analyst: true, decisionTools: false })));

    const result = await loadData();

    expect(result.featureAccess).toEqual({ analyst: true, decisionTools: false });
    expect(result.featureAccessUnavailable).toBe(false);
  });

  it("distinguishes a read denial from an unread grant", async () => {
    backend(() => Promise.resolve(response({ analyst: false, decisionTools: false })));

    const denied = await loadData();
    expect(denied.featureAccess.analyst).toBe(false);
    expect(denied.featureAccessUnavailable).toBe(false);

    backend(() => Promise.reject(new Error("feature-access offline")));

    const unavailable = await loadData();
    expect(unavailable.featureAccess.analyst).toBe(false);
    expect(unavailable.featureAccessUnavailable).toBe(true);
  });

  it("marks a non-ok feature-access response unavailable", async () => {
    backend(() => Promise.resolve(response({}, 503)));

    const result = await loadData();

    expect(result.featureAccessUnavailable).toBe(true);
  });
});
