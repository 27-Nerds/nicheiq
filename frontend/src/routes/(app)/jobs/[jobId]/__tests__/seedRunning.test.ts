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
import { render, cleanup, fireEvent, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";
import { chatLedger } from "$lib/stores/chatLedger.svelte";
import { getChatHistory, getSolutions } from "$lib/api";
import type { Job } from "$lib/types/job";
import { buyerFacingVerdictNarrative } from "$lib/selection/buyerFacingResearchProse";
import { EVIDENCE_WITHHELD_TITLE } from "$lib/selection/labels";

const apiMocks = vi.hoisted(() => ({
  progressListener: null as ((job: Partial<Job>) => void) | null,
}));

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn((_jobId, onProgress) => {
      apiMocks.progressListener = onProgress;
      return () => {};
    }),
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
    apiMocks.progressListener = null;
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

  it("keeps the full software fit reasoning once in a collapsed inert disclosure", async () => {
    const job = baseJob();
    const narrative = "The workflow is addressable, but adoption depends on a focused buyer wedge.";
    // NicheRealityCheck rewrites pipeline vocabulary ("wedge") before rendering, so look the
    // reasoning up by what the buyer actually reads, not by the raw input.
    const shownNarrative = buyerFacingVerdictNarrative(narrative);
    const view = render(PageComponent, {
      props: {
        data: {
          ...baseData(job),
          previewReport: {
            niche_context: { niche_input: "test niche" },
            niche_difficulty_verdict: {
              difficulty_level: "medium",
              software_addressability: 0.72,
              headline: "Software Fit: Strong - the workflow can be automated",
              narrative_summary: narrative,
              key_strengths: ["The core pain is a repeatable workflow."],
              key_challenges: ["The initial buyer segment is still broad."],
              low_confidence: false,
            },
          },
        } as never,
      },
    });

    const trigger = await view.findByText("Read full software fit analysis");
    const disclosure = trigger.closest("details");
    const reasoning = view.getByText(shownNarrative).closest(".selection-market-read__reasoning");
    expect(trigger.closest("#market-read")).not.toBeNull();
    expect(view.getAllByRole("button", { name: "Market Read" }).length).toBeGreaterThan(0);
    const overviewTrigger = view.container.querySelector<HTMLButtonElement>(
      'button[aria-controls="overview-content"]',
    );
    expect(overviewTrigger).not.toBeNull();
    await fireEvent.click(overviewTrigger!);
    expect(await view.findByRole("link", { name: "Market read" })).toHaveAttribute("href", "#market-read");
    expect(disclosure).not.toHaveAttribute("open");
    expect((reasoning as HTMLElement & { inert?: boolean }).inert).toBe(true);
    expect(view.getAllByText(shownNarrative)).toHaveLength(1);

    await fireEvent.click(trigger);
    await waitFor(() => expect(disclosure).toHaveAttribute("open"));
    await waitFor(() =>
      expect((reasoning as HTMLElement & { inert?: boolean }).inert).toBeUndefined(),
    );
  });

  it("sanitizes software fit prose on the job-page route, not only inside the workbench", async () => {
    const job = baseJob();
    const view = render(PageComponent, {
      props: {
        data: {
          ...baseData(job),
          previewReport: {
            niche_context: { niche_input: "test niche" },
            niche_difficulty_verdict: {
              difficulty_level: "medium",
              software_addressability: 0.72,
              headline: "Software Fit: Strong - the workflow can be automated",
              // ONE VALUE PER FIELD IT ACTUALLY COMES FROM. "The corpus drifts from the stated
              // audience" is a `key_challenges` value, and sitting in the narrative slot it
              // certified the wrong gloss for this field: the narrative's "corpus" is the
              // dataset a product would have to build (21 of the 28 distinct narratives under
              // `output/`, all of them), not the run's own evidence.
              narrative_summary:
                "Focus your efforts on ideas that utilize existing reachable data rather than those requiring a new corpus.",
              key_strengths: [
                "The niche has 10 tools web-verified, with published prices.",
              ],
              key_challenges: [
                "The corpus drifts from the stated audience — tighten the wedge or the product will end up serving the wrong user.",
                "Most ideas need a data corpus that doesn't exist yet: plan a cold-start play (seed it, scrape it, or partner) before the product is useful.",
                "Treat this as a corpus evidence gap: web-verified prices support a paid wedge. Thin early signal; Deep Research validates.",
              ],
              low_confidence: false,
            },
          },
        } as never,
      },
    });

    await view.findByText("Read full software fit analysis");
    // The narrative takes the dataset reading, and the count head is owed even though the
    // article is not adjacent to the noun: "a new collected evidence" is what shipped before.
    expect(view.getByText(
      "Focus your efforts on ideas that utilize existing reachable data rather than those requiring a new dataset.",
    )).toBeInTheDocument();
    expect(view.container.textContent).not.toContain("a new collected evidence");
    // …and `key_challenges`, on the same verdict, keeps the evidence reading.
    expect(view.getByText(/The collected evidence drifts from the stated audience/)).toHaveTextContent(
      "Tighten the entry point or the product will end up serving the wrong user.",
    );
    expect(view.getByText(/Most ideas need a body of data that does not exist yet/)).toHaveTextContent(
      "Plan how to collect, create, or obtain access to it before the product is useful.",
    );
    expect(view.getByText(/10 tools checked on the web/)).toBeInTheDocument();
    expect(view.getByText(/gap in the collected evidence/)).toHaveTextContent(
      "published prices checked on the web support a paid offer. Early evidence is limited. Deep Research can validate it.",
    );
    expect(view.container.textContent).not.toMatch(
      /\bcorpus\b|cold-start|web-verified|paid wedge|Thin early signal|seed it|scrape it/i,
    );
  });

  it("renders only context candidates and withholds preview framing when the snapshot is untrusted", async () => {
    const rawJob = baseJob({
      solutionIdeas: [{
        idea_id: "idea-stale",
        idea_revision: 1,
        solution_name: "Stale raw candidate",
        description: "stale",
        value_proposition: "stale",
      } as never],
    });
    const currentCandidate = {
      idea_id: "idea-current",
      idea_revision: 2,
      solution_name: "Current context candidate",
      description: "current",
      value_proposition: "current",
    };
    const view = render(PageComponent, {
      props: {
        data: {
          ...baseData(rawJob),
          solutions: [currentCandidate],
          selectionArtifactVerification: "untrusted",
          selectionArtifactReason: "version_mismatch",
          previewReport: {
            niche_difficulty_verdict: {
              headline: "Stale preview framing",
              narrative_summary: "This must never render.",
            },
          },
        } as never,
      },
    });

    await view.findByText("Current context candidate");
    expect(view.queryByText("Stale raw candidate")).toBeNull();
    expect(view.queryByText("This must never render.")).toBeNull();
    expect(view.queryByText("Read full software fit analysis")).toBeNull();
    expect(await view.findByText(EVIDENCE_WITHHELD_TITLE)).toBeInTheDocument();
  });

  it("does not mislabel the latest idea-update timestamp as the Discovery run", async () => {
    const startedAt = "2026-07-30T11:16:27.000Z";
    const job = baseJob({ startedAt });
    const view = render(PageComponent, {
      props: { data: baseData(job) as never },
    });

    await view.findByText(/Latest research activity · started/);
    expect(view.queryByText(/Discovery run · started/)).toBeNull();
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

  it("preserves the authoritative shortlist when a partial seed SSE update arrives", async () => {
    const api = await import("$lib/api");
    vi.mocked(api.shouldKeepSSEOpen).mockReturnValue(true);
    const job = baseJob({
      solutionIdeas: [
        {
          idea_id: "idea-alpha",
          idea_revision: 1,
          solution_name: "Alpha Idea",
          description: "d",
          value_proposition: "v",
        } as never,
      ],
      selectionDraft: {
        version: 2,
        items: [{ ideaId: "idea-alpha", ideaRevision: 1 }],
      },
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    await view.findByRole("checkbox", { name: "Deselect Alpha Idea" });
    expect(apiMocks.progressListener).not.toBeNull();
    apiMocks.progressListener?.({
      id: job.id,
      status: "RUNNING",
      activeDispatchKind: "SEED_IDEA",
    });

    await waitFor(() =>
      expect(view.getByRole("checkbox", { name: "Deselect Alpha Idea" })).toBeDisabled(),
    );
  });

  it("lets an exact regeneration dispatch override stale committed selections", async () => {
    const job = baseJob({
      status: "QUEUED",
      jobMode: "interactive",
      activeDispatchKind: "REGENERATE",
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

  it("keeps the checkpoint workspace mounted after reloading a queued apply-stay", async () => {
    const job = baseJob({
      status: "QUEUED",
      activeDispatchKind: "APPLY_STAY",
      chatMode: true,
      gateStage: 1,
      gateArtifact: null,
      solutionIdeas: [],
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    expect(await view.findByRole("heading", { name: "Niche validated" })).toBeInTheDocument();
    expect(view.queryByText("Waiting for a worker")).toBeNull();
  });

  it("owns a completed-without-report state without linking to a missing report", async () => {
    const job = baseJob({
      status: "COMPLETED",
      assets: [],
      solutionIdeas: [],
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    expect(await view.findByRole("heading", { name: "The report file has not arrived" })).toBeInTheDocument();
    expect(view.queryByRole("link", { name: "Open report" })).toBeNull();
    expect(view.getByRole("button", { name: "Check again" })).toBeInTheDocument();
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
        {
          idea_id: "idea-alpha",
          idea_revision: 2,
          solution_name: "Alpha Idea",
          description: "newer draft",
          value_proposition: "newer draft",
        } as never,
      ],
      selectedSolutionIds: ["idea-alpha"],
      selectedSolutions: ["Alpha Idea"],
      selectedSolutionRefs: [{
        ideaId: "idea-alpha",
        ideaRevision: 1,
        snapshotSha256: "a".repeat(64),
      }],
      selectionDraft: {
        version: 2,
        items: [{ ideaId: "idea-alpha", ideaRevision: 2 }],
      },
    });
    const view = render(PageComponent, { props: { data: baseData(job) as never } });

    await view.findByText(/We're validating your top picks/);
    expect((await view.findAllByText("Alpha Idea")).length).toBeGreaterThan(0);
    const receipt = view.getByLabelText("Exact Deep Research selection");
    expect(receipt).toHaveTextContent("Idea idea-alpha · rev 1");
    expect(receipt).not.toHaveTextContent("rev 2");
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(document.querySelector('input[aria-label="Select Alpha Idea"]')).toBeNull();
  });
});
