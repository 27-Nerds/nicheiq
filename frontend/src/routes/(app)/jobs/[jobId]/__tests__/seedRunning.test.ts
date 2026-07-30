/**
 * Blocker 2 (outcome-delivery review): a SEED_IDEA claim flips job.status to
 * QUEUED/RUNNING for the duration of the birth pipeline — exactly like a
 * regen/gate round-trip. Before the fix, `isSelectionPhase` only looked at
 * job.status, so this transition unmounted SelectionWorkbench in favor of
 * ResearchProgressScreen, destroying the settlement poll (`beginSeedSettlementPoll`)
 * and the "Evaluating…" banner along with it. `seedRunning` (derived from
 * `chatLedger.hasPendingSeed` + job.status) now keeps the workbench mounted through
 * that round-trip, mirroring the pre-existing `gateApplyPending` idiom.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { getChatHistory, getSolutions } from "$lib/api";
import type { Job } from "$lib/types/job";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
    shouldKeepSSEOpen: vi.fn(() => false),
    getReportSummary: vi.fn(() => Promise.resolve(null)),
    getDiscoveryShareStatus: vi.fn(() => Promise.resolve({ isShared: false, solutionVotes: {} })),
    regenerateIdeas: vi.fn(),
    getSolutions: vi.fn(() => Promise.resolve({ solutions: [] })),
    getDiscoveryData: vi.fn(() => Promise.resolve(null)),
    getPreviewReport: vi.fn(() => Promise.resolve(null)),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [], weakPool: false })),
  };
});

import PageComponent from "../+page.svelte";

const PENDING_SEED_HISTORY = {
  messages: [
    {
      id: "seed-receipt-1",
      gateStage: 5,
      role: "receipt" as const,
      content: "",
      patchJson: {
        kind: "ledger_event" as const,
        version: 1,
        event: "seed_submitted" as const,
        patch: {},
        rows: [],
        sourceMessageId: "asst-seed-1",
      },
      truncated: false,
      createdAt: "2026-07-13T00:00:00.000Z",
    },
  ],
  weakPool: false,
};

function baseJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    niche: "test niche",
    status: "AWAITING_SELECTION",
    entryMode: "standard",
    solutionIdeas: [
      { solution_name: "Alpha Idea", description: "d", value_proposition: "v" } as never,
    ],
    selectedSolutions: [],
    assets: [],
    stagesCompleted: 5,
    totalStages: 16,
    ...overrides,
  } as unknown as Job;
}

function baseData(job: Job) {
  return {
    job,
    solutions: job.solutionIdeas ?? [],
    reportSummary: null,
    discoveryData: null,
    solutionVotes: {},
    previewReport: null,
    userEmail: "test@example.com",
    catalogPainPoints: [],
    creditBalance: 100,
    stageCosts: { discovery: 5, deep_research: 15, landing_page: 5, regenerate_ideas: 2, seed_idea: 3 },
  };
}

describe("+page.svelte — workbench stays mounted through a seed's QUEUED/RUNNING round-trip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    (page as any).params = { jobId: "job-1" };
    // `clearAllMocks` clears call history but NOT a prior test's `mockResolvedValue`
    // implementation — pin the default here so each test starts from the same base.
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false } as never);
    vi.mocked(getSolutions).mockResolvedValue({
      solutionIdeas: [],
      selectionDraft: { version: 0, items: [] },
      canRegenerate: true,
    } as never);
  });

  afterEach(() => {
    cleanup();
  });

  it("uses the research subject as the selection title and keeps guidance separate", async () => {
    const job = baseJob({ niche: "Competitive Dota 2 And Cs2 Fans." });
    const { findByRole, findByText, queryByRole } = render(PageComponent, {
      props: { data: baseData(job) as never },
    });

    await findByRole("heading", { level: 1, name: "Competitive Dota 2 And Cs2 Fans." });
    await findByText("Discovery is complete. Review the strongest opportunities before moving to Deep Research.");
    expect(queryByRole("heading", { name: "Select candidates for Deep Research" })).toBeNull();
  });

  it("hydrates the authoritative shortlist draft instead of legacy selected solution IDs", async () => {
    const job = baseJob({
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        } as never,
        {
          idea_id: "idea-beta",
          idea_revision: 1,
          solution_name: "Beta Idea",
          description: "d",
          value_proposition: "v",
        } as never,
      ],
      selectedSolutionIds: ["idea-alpha"],
      selectionDraft: {
        version: 4,
        items: [{ ideaId: "idea-beta", ideaRevision: 1 }],
      },
    });

    render(PageComponent, { props: { data: baseData(job) as never } });

    await waitFor(() => {
      expect(document.querySelector<HTMLInputElement>('input[aria-label="Select Alpha Idea"]')).not.toBeNull();
      expect(document.querySelector<HTMLInputElement>('input[aria-label="Deselect Beta Idea"]')).not.toBeNull();
    });
    expect(document.body).not.toHaveTextContent("selectionDraft=");
  });

  it("preserves long research subjects while applying the compact title treatment", async () => {
    const topic =
      "Employees trying to figure out which AI skills to learn and where to expand their professional knowledge to stay employable, overwhelmed by scattered courses and conflicting advice about what their role will actually require";
    const job = baseJob({ niche: topic });
    const { findByRole } = render(PageComponent, { props: { data: baseData(job) as never } });

    const heading = await findByRole("heading", { level: 1, name: topic });
    expect(heading).toHaveAttribute("title", topic);
    expect(heading).toHaveClass("page-header-title--research-topic", "page-header-title--long");
  });

  it("renders SelectionWorkbench (not the progress screen) when a seed dispatch flips status to RUNNING", async () => {
    vi.mocked(getChatHistory).mockResolvedValue(PENDING_SEED_HISTORY as never);
    const job = baseJob({ status: "RUNNING" });

    render(PageComponent, { props: { data: baseData(job) as never } });

    // chatLedger.init(job.id) fires in the mount effect — hasPendingSeed becomes true once
    // the mocked seed_submitted receipt resolves, which is what `seedRunning` depends on.
    await waitFor(() => expect(chatLedger.hasPendingSeed).toBe(true));

    // SelectionWorkbench's shortlist checkbox — proof the workbench (not
    // ResearchProgressScreen, which has no such control) is mounted.
    await waitFor(() =>
      expect(document.querySelector('input[aria-label="Select Alpha Idea"]')).not.toBeNull(),
    );
  });

  it("keeps a queued seed with a saved shortlist in the workbench and shows its progress", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      ...PENDING_SEED_HISTORY,
      messages: [
        {
          id: "asst-seed-1",
          gateStage: 5,
          role: "assistant",
          content: "A proposed direction",
          patchJson: {
            kind: "idea_synthesis",
            operation: "adjacent",
            proposedTitle: "A focused adjacent direction",
            proposedBrief: "A deliberately different workflow for the same buyer.",
            changeSummary: "Changes the workflow while keeping the buyer.",
            rationale: "The current shortlist leaves this adjacent job untested.",
            parents: [{
              ideaId: "idea-alpha",
              ideaRevision: 1,
              solutionName: "Alpha Idea",
              contribution: "Keep the validated buyer.",
            }],
            evidence: {
              sourceAnchors: [{
                ideaId: "idea-alpha",
                ideaRevision: 1,
                candidateSnapshotSha256: "a".repeat(64),
              }],
              requiresValidation: ["Validate demand for the adjacent workflow."],
            },
            newAssumptions: ["The same buyer owns the adjacent workflow."],
          },
          truncated: false,
          createdAt: "2026-07-12T23:59:59.000Z",
        },
        ...PENDING_SEED_HISTORY.messages,
      ],
      activeOperation: {
        id: "dispatch-seed-1",
        kind: "SEED_IDEA",
        state: "AUTHORIZED",
        createdAt: "2026-07-13T00:00:00.000Z",
      },
    } as never);
    const job = baseJob({
      status: "QUEUED",
      jobMode: "interactive",
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        } as never,
      ],
      selectedSolutionIds: ["idea-alpha"],
      selectedSolutions: ["Alpha Idea"],
      selectionDraft: {
        version: 2,
        items: [{ ideaId: "idea-alpha", ideaRevision: 1 }],
      },
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    await waitFor(() =>
      expect(chatLedger.activeOperation?.kind).toBe("SEED_IDEA"),
    );
    await view.findByRole("region", { name: "Evaluation in progress" });
    expect(document.querySelector('input[aria-label="Deselect Alpha Idea"]')).not.toBeNull();
    expect(view.queryByText(/We're validating your top picks/)).toBeNull();
  });

  it("keeps a queued seed in the locked workbench when chat history cannot load", async () => {
    vi.mocked(getChatHistory).mockRejectedValue(new Error("history unavailable"));
    const job = baseJob({
      status: "QUEUED",
      jobMode: "interactive",
      activeDispatchKind: "SEED_IDEA",
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        } as never,
      ],
      selectedSolutionIds: ["idea-alpha"],
      selectedSolutions: ["Alpha Idea"],
      selectionDraft: {
        version: 2,
        items: [{ ideaId: "idea-alpha", ideaRevision: 1 }],
      },
    });

    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    await waitFor(() => expect(chatLedger.loadFailed).toBe(true));
    const checkbox = await view.findByRole("checkbox", { name: "Deselect Alpha Idea" });
    expect(checkbox).toBeDisabled();
    expect(view.queryByText(/We're validating your top picks/)).toBeNull();
  });

  it("uses the client solutions response as the current completed-batch limit", async () => {
    vi.mocked(getSolutions).mockResolvedValue({
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        },
      ],
      selectionDraft: { version: 3, items: [] },
      canRegenerate: false,
    } as never);
    const job = baseJob({
      solutionIdeas: [],
      canRegenerate: true,
    });
    const view = render(PageComponent, {
      props: { data: { ...baseData(job), solutions: null } as never },
    });

    await waitFor(() =>
      expect(document.querySelector('input[aria-label="Select Alpha Idea"]')).not.toBeNull(),
    );
    expect(view.queryByRole("button", { name: "Add another batch" })).toBeNull();
  });

  it("renders the progress screen (not the workbench) when RUNNING with no pending seed", async () => {
    const job = baseJob({ status: "RUNNING", solutionIdeas: [] });

    render(PageComponent, { props: { data: baseData(job) as never } });

    // No seed_submitted receipt this time (default empty history from the mock override below).
    await waitFor(() => expect(chatLedger.jobId).toBe("job-1"));
    expect(chatLedger.hasPendingSeed).toBe(false);

    expect(document.querySelector('input[aria-label="Select Alpha Idea"]')).toBeNull();
  });

  it("renders queued interactive Phase 2 as Deep Research without a dead cancel action", async () => {
    const job = baseJob({
      status: "QUEUED",
      jobMode: "interactive",
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        } as never,
      ],
      selectedSolutionIds: ["idea-alpha"],
      selectedSolutions: ["Alpha Idea"],
      selectionDraft: {
        version: 2,
        items: [{ ideaId: "idea-alpha", ideaRevision: 1 }],
      },
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    await view.findByText(/We're validating your top picks/);
    await view.findByText("Alpha Idea");
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(document.querySelector('input[aria-label="Select Alpha Idea"]')).toBeNull();
  });
});
