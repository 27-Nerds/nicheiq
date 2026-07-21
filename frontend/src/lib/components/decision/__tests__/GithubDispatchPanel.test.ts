import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GithubDispatchPanel from "../GithubDispatchPanel.svelte";
import type {
  GithubConnection,
  GithubHandoffDispatch,
  GithubIssuePreview,
  GithubRepository,
} from "$lib/types/githubIntegration";

const mocks = vi.hoisted(() => ({
  getGithubConnections: vi.fn(),
  getGithubRepositories: vi.fn(),
  getGithubHandoffDispatch: vi.fn(),
  previewGithubHandoffIssue: vi.fn(),
  dispatchGithubHandoffIssue: vi.fn(),
  reconcileGithubHandoffDispatch: vi.fn(),
}));

vi.mock("$lib/api", () => mocks);

const connection: GithubConnection = {
  id: "connection-1",
  provider: "GITHUB",
  accountLogin: "nicheiq",
  accountType: "Organization",
  repositorySelection: "selected",
  status: "ACTIVE",
  lastVerifiedAt: "2026-07-16T12:00:00.000Z",
  createdAt: "2026-07-16T12:00:00.000Z",
};

const repository: GithubRepository = {
  id: "987654",
  name: "signal-desk",
  fullName: "nicheiq/signal-desk",
  htmlUrl: "https://github.com/nicheiq/signal-desk",
  private: true,
  hasIssues: true,
};

const preview: GithubIssuePreview = {
  provider: "GITHUB",
  adapterVersion: 1,
  connectionId: connection.id,
  payloadFingerprint: "a".repeat(64),
  payload: {
    version: 1,
    destination: {
      repositoryId: repository.id,
      owner: "nicheiq",
      name: repository.name,
      fullName: repository.fullName,
    },
    request: {
      title: "Build: Signal Desk",
      body: "# Implementation brief\n\nFrozen owner decision.",
    },
  },
};

function receipt(
  status: GithubHandoffDispatch["status"],
  overrides: Partial<GithubHandoffDispatch> = {},
): GithubHandoffDispatch {
  return {
    id: "dispatch-1",
    handoffId: "handoff-1",
    provider: "GITHUB",
    adapterVersion: 1,
    destinationContainerId: repository.id,
    destination: preview.payload.destination,
    payload: preview.payload,
    payloadFingerprint: preview.payloadFingerprint,
    status,
    retryable: false,
    attemptCount: 1,
    connectionId: connection.id,
    providerResourceId: status === "SUCCEEDED" ? "7001" : null,
    providerResourceNodeId: status === "SUCCEEDED" ? "I_kwDOExample" : null,
    providerResourceNumber: status === "SUCCEEDED" ? 42 : null,
    providerResourceUrl: status === "SUCCEEDED"
      ? "https://github.com/nicheiq/signal-desk/issues/42"
      : null,
    errorClass: status === "UNKNOWN" ? "AMBIGUOUS" : null,
    errorCode: status === "UNKNOWN" ? "GITHUB_CREATE_OUTCOME_UNKNOWN" : null,
    providerRequestStartedAt: "2026-07-16T12:05:00.000Z",
    settledAt: status === "PENDING" ? null : "2026-07-16T12:05:02.000Z",
    reconciledAt: null,
    createdAt: "2026-07-16T12:05:00.000Z",
    updatedAt: "2026-07-16T12:05:02.000Z",
    ...overrides,
  };
}

beforeEach(() => {
  mocks.getGithubConnections.mockResolvedValue({ enabled: true, connections: [] });
  mocks.getGithubRepositories.mockResolvedValue([]);
  mocks.getGithubHandoffDispatch.mockResolvedValue(null);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("GithubDispatchPanel", () => {
  it("starts with an owner-bound GitHub App connection link", async () => {
    const view = render(GithubDispatchPanel, { props: { jobId: "job-1" } });

    const connect = await view.findByRole("link", { name: /Connect GitHub/i });
    expect(connect).toHaveAttribute(
      "href",
      "/api/integrations/github/connect?jobId=job-1",
    );
    expect(mocks.previewGithubHandoffIssue).not.toHaveBeenCalled();
  });

  it("requires an exact preview before creating one issue and shows the receipt", async () => {
    mocks.getGithubConnections.mockResolvedValue({
      enabled: true,
      connections: [connection],
    });
    mocks.getGithubRepositories.mockResolvedValue([repository]);
    mocks.previewGithubHandoffIssue.mockResolvedValue(preview);
    mocks.dispatchGithubHandoffIssue.mockResolvedValue(receipt("SUCCEEDED"));
    const view = render(GithubDispatchPanel, { props: { jobId: "job-1" } });

    await view.findByLabelText("Repository");
    await waitFor(() => expect(mocks.getGithubRepositories).toHaveBeenCalledWith(connection.id));
    await fireEvent.click(view.getByRole("button", { name: "Review exact issue" }));

    expect(await view.findByText("Build: Signal Desk")).toBeInTheDocument();
    expect(view.getByRole("region", { name: "GitHub issue Markdown body" }).textContent)
      .toBe(preview.payload.request.body);
    expect(mocks.dispatchGithubHandoffIssue).not.toHaveBeenCalled();

    await fireEvent.click(view.getByRole("button", { name: "Create issue in GitHub" }));
    await waitFor(() => expect(mocks.dispatchGithubHandoffIssue).toHaveBeenCalledWith(
      "job-1",
      {
        connectionId: connection.id,
        repositoryId: repository.id,
        payloadFingerprint: preview.payloadFingerprint,
      },
    ));
    expect(await view.findByRole("link", { name: /Open GitHub issue/i }))
      .toHaveAttribute("href", "https://github.com/nicheiq/signal-desk/issues/42");
  });

  it("never retries an unknown write and reconciles the durable receipt", async () => {
    mocks.getGithubHandoffDispatch.mockResolvedValue(receipt("UNKNOWN"));
    mocks.reconcileGithubHandoffDispatch.mockResolvedValue({
      dispatch: receipt("SUCCEEDED", {
        reconciledAt: "2026-07-16T12:06:00.000Z",
      }),
      reconciliation: "matched",
    });
    const view = render(GithubDispatchPanel, { props: { jobId: "job-1" } });

    expect(await view.findByText("Creation outcome unknown")).toBeInTheDocument();
    expect(view.getByText(/Do not submit it again|will not retry automatically/i))
      .toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Reconcile status" }));

    await waitFor(() => expect(mocks.reconcileGithubHandoffDispatch)
      .toHaveBeenCalledWith("job-1", "dispatch-1"));
    expect(mocks.dispatchGithubHandoffIssue).not.toHaveBeenCalled();
    expect(await view.findByRole("link", { name: /Open GitHub issue/i })).toBeInTheDocument();
  });

  it("offers an explicit retry only for a retryable failed receipt", async () => {
    const failed = receipt("FAILED", {
      retryable: true,
      errorClass: "PROVIDER_REJECTED",
      errorCode: "GITHUB_RATE_LIMITED",
    });
    mocks.getGithubHandoffDispatch.mockResolvedValue(failed);
    mocks.dispatchGithubHandoffIssue.mockResolvedValue(receipt("SUCCEEDED", {
      attemptCount: 2,
    }));
    const view = render(GithubDispatchPanel, { props: { jobId: "job-1" } });

    await fireEvent.click(await view.findByRole("button", { name: "Retry issue creation" }));

    await waitFor(() => expect(mocks.dispatchGithubHandoffIssue).toHaveBeenCalledWith(
      "job-1",
      {
        connectionId: connection.id,
        repositoryId: repository.id,
        payloadFingerprint: preview.payloadFingerprint,
      },
    ));
    expect(await view.findByRole("link", { name: /Open GitHub issue/i })).toBeInTheDocument();
  });
});
