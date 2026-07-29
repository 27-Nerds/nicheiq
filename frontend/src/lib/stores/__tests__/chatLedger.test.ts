import { describe, it, expect, vi, beforeEach } from "vitest";
import { getChatHistory } from "$lib/api";
import { chatLedger } from "../chatLedger.svelte";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return { ...actual, getChatHistory: vi.fn() };
});

const APPLIED_RECEIPT = {
  id: "r1",
  gateStage: 1,
  role: "receipt" as const,
  content: "Applied changes to Niche description",
  patchJson: {
    kind: "ledger_event" as const,
    version: 1,
    event: "gate_patch_applied" as const,
    patch: { niche_description: "Solo consultants" },
    rows: [{ label: "Niche description", value: "Solo consultants" }],
    sourceMessageId: "asst-9",
  },
  truncated: false,
  createdAt: "2026-07-12T00:00:02.000Z",
};

describe("chatLedger — one thread per job, segmented by checkpoint", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  it("groups the whole job's history into checkpoint segments in pipeline order", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        { id: "m1", gateStage: 5, role: "user", content: "g3 q", patchJson: null, truncated: false, createdAt: "3" },
        { id: "m2", gateStage: 1, role: "user", content: "g1 q", patchJson: null, truncated: false, createdAt: "1" },
        { id: "m3", gateStage: 4, role: "user", content: "g2 q", patchJson: null, truncated: false, createdAt: "2" },
      ],
    });

    await chatLedger.init("job-1");

    // Niche (1) → Audience (4) → Selection (5), regardless of arrival order.
    expect(chatLedger.segments.map((s) => s.gateStage)).toEqual([1, 4, 5]);
    expect(chatLedger.segmentMessages(4).map((m) => m.content)).toEqual(["g2 q"]);
  });

  it("counts user turns GLOBALLY — the backend cap is per job, not per gate", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        { id: "m1", gateStage: 1, role: "user", content: "a", patchJson: null, truncated: false, createdAt: "1" },
        { id: "m2", gateStage: 1, role: "assistant", content: "b", patchJson: null, truncated: false, createdAt: "2" },
        { id: "m3", gateStage: 4, role: "user", content: "c", patchJson: null, truncated: false, createdAt: "3" },
      ],
    });

    await chatLedger.init("job-1");

    expect(chatLedger.usedTurns).toBe(2);
  });

  it("prefers the server's usedTurns when the history response reports it", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        { id: "m1", gateStage: 1, role: "user", content: "a", patchJson: null, truncated: false, createdAt: "1" },
      ],
      usedTurns: 7,
      maxTurns: 30,
    } as never);

    await chatLedger.init("job-1");

    expect(chatLedger.usedTurns).toBe(7);
  });

  it("renders an APPLIED receipt and marks its proposing message applied", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [APPLIED_RECEIPT] } as never);

    await chatLedger.init("job-1");

    const receipt = chatLedger.segmentMessages(1)[0];
    expect(receipt.role).toBe("receipt");
    // Persisted receipts render through the same rows/note shape as session ones.
    expect(receipt.receipt?.rows).toEqual([{ label: "Niche description", value: "Solo consultants" }]);
    // …and the proposal card that produced it stays terminal across reloads.
    expect(chatLedger.appliedPatchIds.has("asst-9")).toBe(true);
  });

  it("hides a SUBMITTED receipt — an apply in flight is not an applied change", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [{ ...APPLIED_RECEIPT, patchJson: { ...APPLIED_RECEIPT.patchJson, event: "gate_patch_submitted" } }],
    } as never);

    await chatLedger.init("job-1");

    expect(chatLedger.segmentMessages(1)).toHaveLength(0);
    expect(chatLedger.appliedPatchIds.has("asst-9")).toBe(false);
  });

  it("swaps the optimistic local receipt for the durable one on reload (no double-count)", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] });
    await chatLedger.init("job-1");

    chatLedger.appendLocal("job-1", {
      id: "local-receipt-1",
      gateStage: 1,
      role: "receipt",
      content: "",
      receipt: { rows: [{ label: "Niche description", value: "Solo consultants" }], note: "Framing re-derived" },
    });
    expect(chatLedger.segmentMessages(1)).toHaveLength(1);

    vi.mocked(getChatHistory).mockResolvedValue({ messages: [APPLIED_RECEIPT] } as never);
    await chatLedger.reload();

    const rows = chatLedger.segmentMessages(1);
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("r1");
  });

  it("keeps cached messages and flags the failure when history can't be loaded", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        { id: "m1", gateStage: 1, role: "user", content: "kept", patchJson: null, truncated: false, createdAt: "1" },
      ],
    });
    await chatLedger.init("job-1");

    vi.mocked(getChatHistory).mockRejectedValue(new Error("network"));
    await chatLedger.reload();

    // A failed refresh must not blank the ledger — the panel shows a retry instead.
    expect(chatLedger.loadFailed).toBe(true);
    expect(chatLedger.segmentMessages(1)).toHaveLength(1);
  });
});

const SEED_SUBMITTED_RECEIPT = {
  id: "seed-r1",
  gateStage: 5,
  role: "receipt" as const,
  content: "Evaluating your idea",
  patchJson: {
    kind: "ledger_event" as const,
    version: 1,
    event: "seed_submitted" as const,
    patch: {},
    rows: [],
    sourceMessageId: "asst-seed-1",
    evaluationId: "dispatch-1",
  },
  truncated: false,
  createdAt: "2026-07-13T00:00:01.000Z",
};

const SEED_SETTLED_RECEIPT = {
  id: "seed-r2",
  gateStage: 5,
  role: "receipt" as const,
  content: "Your idea cleared evaluation",
  patchJson: {
    kind: "ledger_event" as const,
    version: 1,
    event: "seed_settled" as const,
    outcome: "accepted" as const,
    patch: {},
    rows: [],
    sourceMessageId: "asst-seed-1",
    evaluationId: "dispatch-1",
    idea: {
      solution_name: "PatchZero",
      short_description: "Finds missed esports reporting leads.",
      market_fit_score: 0.45,
    },
  },
  truncated: false,
  createdAt: "2026-07-13T00:00:02.000Z",
};

describe("chatLedger — seed outcome derivation (durable receipts, not a parallel store)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  it("has no outcome for a seed that was never submitted", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] } as never);
    await chatLedger.init("job-1");

    expect(chatLedger.seedOutcome("asst-seed-1")).toBeUndefined();
    expect(chatLedger.hasPendingSeed).toBe(false);
  });

  it("marks a seed pending from a durable seed_submitted receipt — survives a reload", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [SEED_SUBMITTED_RECEIPT] } as never);
    await chatLedger.init("job-1");

    expect(chatLedger.seedOutcome("asst-seed-1")).toBe("pending");
    expect(chatLedger.hasPendingSeed).toBe(true);
    // The submitted receipt itself is chrome, not a visible row — the original
    // new_idea_seed proposal message is the one card whose state changes.
    expect(chatLedger.segmentMessages(5)).toHaveLength(0);
  });

  it("settled outcome overrides pending, and hasPendingSeed clears once settled", async () => {
    const proposal = {
      id: "asst-seed-1",
      gateStage: 5,
      role: "assistant" as const,
      content: "A proposed direction",
      patchJson: {
        kind: "idea_synthesis" as const,
        proposedTitle: "GLP-1 Off-Ramp + Peptide Maintenance Hub",
      },
      truncated: false,
      createdAt: "2026-07-13T00:00:00.000Z",
    };
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [proposal, SEED_SUBMITTED_RECEIPT, SEED_SETTLED_RECEIPT],
    } as never);
    await chatLedger.init("job-1");

    expect(chatLedger.seedOutcome("asst-seed-1")).toBe("accepted");
    expect(chatLedger.seedResult("asst-seed-1")).toEqual({
      solution_name: "PatchZero",
      short_description: "Finds missed esports reporting leads.",
      market_fit_score: 0.45,
    });
    expect(chatLedger.hasPendingSeed).toBe(false);
    expect(chatLedger.seedActivities).toEqual([
      expect.objectContaining({
        sourceMessageId: "asst-seed-1",
        evaluationId: "dispatch-1",
        kind: "idea_synthesis",
        proposedTitle: "GLP-1 Off-Ramp + Peptide Maintenance Hub",
        outcome: "accepted",
      }),
    ]);
  });

  it("markSeedPending is optimistic — flips the card before any server round-trip", () => {
    chatLedger.reset();
    expect(chatLedger.seedOutcome("asst-seed-2")).toBeUndefined();
    chatLedger.markSeedPending("asst-seed-2", {
      evaluationId: "dispatch-2",
      kind: "idea_synthesis",
      proposedTitle: "Off-ramp hub",
    });
    expect(chatLedger.seedOutcome("asst-seed-2")).toBe("pending");
    expect(chatLedger.hasPendingSeed).toBe(true);
    expect(chatLedger.seedActivities[0]).toEqual(expect.objectContaining({
      evaluationId: "dispatch-2",
      proposedTitle: "Off-ramp hub",
      outcome: "pending",
    }));
  });

  it("a later reload's server truth overwrites (but never erases) the optimistic mark", async () => {
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] } as never);
    await chatLedger.init("job-1");

    chatLedger.markSeedPending("asst-seed-1");
    expect(chatLedger.seedOutcome("asst-seed-1")).toBe("pending");

    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [SEED_SUBMITTED_RECEIPT, SEED_SETTLED_RECEIPT],
    } as never);
    await chatLedger.reload();

    expect(chatLedger.seedOutcome("asst-seed-1")).toBe("accepted");
  });
});

describe("chatLedger — durable additional-batch activity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  it("reconstructs a settled batch by operation id and lets settlement override submitted", async () => {
    const submitted = {
      id: "batch-r1",
      gateStage: 5,
      role: "receipt" as const,
      content: "Additional batch queued",
      patchJson: {
        kind: "ledger_event" as const,
        version: 1,
        event: "regeneration_submitted" as const,
        patch: {},
        rows: [],
        operationId: "batch-operation-1",
        batch: { ordinal: 2, focus: "novelty" as const },
      },
      createdAt: "2026-07-27T00:00:01.000Z",
    };
    const settled = {
      ...submitted,
      id: "batch-r2",
      patchJson: {
        ...submitted.patchJson,
        event: "regeneration_settled" as const,
        batch: {
          ordinal: 2,
          outcome: "completed" as const,
          generatedCount: 4,
          addedCount: 2,
          addedIdeaIds: ["idea-new-1", "idea-new-2"],
          ruledOutCount: 2,
        },
      },
      createdAt: "2026-07-27T00:00:02.000Z",
    };
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [submitted, settled] } as never);

    await chatLedger.init("job-1");

    expect(chatLedger.hasPendingBatch).toBe(false);
    expect(chatLedger.batchActivities).toEqual([
      expect.objectContaining({
        operationId: "batch-operation-1",
        ordinal: 2,
        focus: "novelty",
        outcome: "completed",
        addedCount: 2,
        addedIdeaIds: ["idea-new-1", "idea-new-2"],
      }),
    ]);
  });

  it("adds an optimistic pending activity from the regenerate response", () => {
    chatLedger.markBatchPending("batch-operation-2", {
      ordinal: 3,
      focus: "distribution",
    });

    expect(chatLedger.hasPendingBatch).toBe(true);
    expect(chatLedger.batchActivities[0]).toEqual(expect.objectContaining({
      operationId: "batch-operation-2",
      ordinal: 3,
      focus: "distribution",
      outcome: "pending",
    }));
  });
});

describe("promoteUserMessage — the duplicate-turn bug", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  it("a reload after a successful send does NOT render the question twice", async () => {
    // The optimistic row is written under a temporary `local-…` id. The server persists it under a
    // UUID. Reconciliation keeps every `local-` row the server doesn't know about — so without
    // promoting the id, BOTH copies survive a reload and the user sees their own question twice.
    // This is why `userMessageId` has to ride back on the `done` event before any reload can fire.
    const SERVER_ID = "11111111-2222-3333-4444-555555555555";

    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [],
      weakPool: false,
    } as never);
    await chatLedger.init("job-1");

    chatLedger.appendLocal("job-1", {
      id: "local-123",
      gateStage: 5,
      role: "user",
      content: "Should I proceed?",
    } as never);

    // `done` arrives with the persisted id.
    chatLedger.promoteUserMessage("job-1", "local-123", SERVER_ID);

    // Now the server replays that turn on the next history load.
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        {
          id: SERVER_ID,
          gateStage: 5,
          role: "user",
          content: "Should I proceed?",
          patchJson: null,
          createdAt: new Date().toISOString(),
        },
      ],
      weakPool: false,
    } as never);
    await chatLedger.reload();

    const asked = chatLedger.messages.filter((m) => m.content === "Should I proceed?");
    expect(asked).toHaveLength(1);
    expect(asked[0].id).toBe(SERVER_ID);
  });

  it("trusts the server's turn count instead of pinning the one from the last history GET", async () => {
    // usedTurns was only ever computed in the history response, and once set it PINNED the
    // display — so locally-sent turns never moved it and the user could hit the wall while the
    // counter still read 24/30.
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] } as never);
    await chatLedger.init("job-1");

    chatLedger.setUsedTurns("job-1", 24);
    expect(chatLedger.usedTurns).toBe(24);
    chatLedger.setUsedTurns("job-1", 25);
    expect(chatLedger.usedTurns).toBe(25);
    // A missing count must not clobber a known one.
    chatLedger.setUsedTurns("job-1", undefined);
    expect(chatLedger.usedTurns).toBe(25);
  });

  it("drops a late mutation from a job the store has since navigated away from", async () => {
    // The exact race the wrong-job ledger contamination bug came from: a `send()` in
    // flight for job A resolves AFTER the user has already navigated to job B (and the
    // page has called chatLedger.init("job-B")). Every mutation captured `jobId` at
    // send-time — if it were the live `jobId` prop instead, it would read "job-B" here
    // and pass this exact guard, defeating it.
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] } as never);
    await chatLedger.init("job-A");

    vi.mocked(getChatHistory).mockResolvedValue({ messages: [] } as never);
    await chatLedger.init("job-B"); // navigated away — resets the store to job B

    chatLedger.appendLocal("job-A", { id: "late-1", gateStage: 5, role: "assistant", content: "stale reply" });
    chatLedger.setUsedTurns("job-A", 99);

    expect(chatLedger.messages.some((m) => m.id === "late-1")).toBe(false);
    expect(chatLedger.usedTurns).not.toBe(99);
  });
});
