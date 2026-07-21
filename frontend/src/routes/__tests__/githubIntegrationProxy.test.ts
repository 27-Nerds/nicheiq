import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ fetchBackend: vi.fn() }));
vi.mock("$lib/backend", () => ({ fetchBackend: mocks.fetchBackend }));

import { GET as connectGithub } from "../api/integrations/github/connect/+server";
import { GET as setupGithub } from "../api/integrations/github/setup/+server";
import { GET as callbackGithub } from "../api/integrations/github/callback/+server";
import { POST as previewIssue } from "../api/jobs/[jobId]/decision-handoff/github/preview/+server";
import {
  GET as getDispatch,
  POST as createDispatch,
} from "../api/jobs/[jobId]/decision-handoff/github/dispatch/+server";

const jobId = "550e8400-e29b-41d4-a716-446655440000";
const locals = {
  auth: vi.fn().mockResolvedValue({ user: { id: "owner-1" } }),
};

function backendResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GitHub integration SvelteKit boundary", () => {
  it("starts an owner-bound install and accepts only a github.com redirect", async () => {
    mocks.fetchBackend.mockResolvedValue(backendResponse({
      installUrl: "https://github.com/apps/nicheiq/installations/new?state=opaque",
    }, 201));

    await expect(connectGithub({
      url: new URL(`http://local/api/integrations/github/connect?jobId=${jobId}`),
      locals,
    } as never)).rejects.toMatchObject({
      status: 303,
      location: "https://github.com/apps/nicheiq/installations/new?state=opaque",
    });
    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      "/api/integrations/github/install-session",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-User-ID": "owner-1" }),
        body: JSON.stringify({ jobId }),
      }),
    );

    mocks.fetchBackend.mockResolvedValue(backendResponse({
      installUrl: "https://attacker.example/install",
    }, 201));
    await expect(connectGithub({
      url: new URL(`http://local/api/integrations/github/connect?jobId=${jobId}`),
      locals,
    } as never)).rejects.toMatchObject({ status: 502 });
  });

  it("forwards setup and OAuth callbacks with the authenticated owner", async () => {
    mocks.fetchBackend
      .mockResolvedValueOnce(backendResponse({
        authorizeUrl: "https://github.com/login/oauth/authorize?state=oauth-state",
      }))
      .mockResolvedValueOnce(backendResponse({
        returnPath: `/jobs/${jobId}/report?github=connected`,
      }));

    await expect(setupGithub({
      url: new URL("http://local/api/integrations/github/setup?state=install-state&installation_id=12345"),
      locals,
    } as never)).rejects.toMatchObject({ status: 303 });
    await expect(callbackGithub({
      url: new URL("http://local/api/integrations/github/callback?state=oauth-state&code=code-1"),
      locals,
    } as never)).rejects.toMatchObject({
      status: 303,
      location: `/jobs/${jobId}/report?github=connected`,
    });

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      1,
      "/api/integrations/github/setup",
      expect.objectContaining({
        body: JSON.stringify({
          state: "install-state",
          installationId: "12345",
        }),
      }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      2,
      "/api/integrations/github/callback",
      expect.objectContaining({
        body: JSON.stringify({ state: "oauth-state", code: "code-1" }),
      }),
    );
  });

  it("forwards preview and receipt operations through the owner identity", async () => {
    mocks.fetchBackend.mockImplementation(async () => backendResponse({ dispatch: null }));
    const body = JSON.stringify({
      connectionId: "123e4567-e89b-42d3-a456-426614174000",
      repositoryId: "987654",
      payloadFingerprint: "a".repeat(64),
    });

    await previewIssue({
      params: { jobId },
      locals,
      request: new Request("http://local", { method: "POST", body }),
    } as never);
    await getDispatch({ params: { jobId }, locals } as never);
    await createDispatch({
      params: { jobId },
      locals,
      request: new Request("http://local", { method: "POST", body }),
    } as never);

    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      1,
      `/api/jobs/${jobId}/decision-handoff/github/preview`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-User-ID": "owner-1" }),
        body,
      }),
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      2,
      `/api/jobs/${jobId}/decision-handoff/github/dispatch`,
      { headers: { "X-User-ID": "owner-1" } },
    );
    expect(mocks.fetchBackend).toHaveBeenNthCalledWith(
      3,
      `/api/jobs/${jobId}/decision-handoff/github/dispatch`,
      expect.objectContaining({ method: "POST", body }),
    );
  });
});
