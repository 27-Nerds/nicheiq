import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup, waitFor } from "@testing-library/svelte";
import SegmentedLedger from "../SegmentedLedger.svelte";
import { getChatHistory } from "$lib/api";
import { chatLedger } from "$lib/stores/chatLedger.svelte";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return { ...actual, getChatHistory: vi.fn(), streamChat: vi.fn() };
});

const G1_HISTORY = [
  { id: "m1", gateStage: 1, role: "user" as const, content: "narrow the niche", patchJson: null, truncated: false, createdAt: "1" },
  { id: "m2", gateStage: 1, role: "assistant" as const, content: "Here is a narrower framing.", patchJson: null, truncated: false, createdAt: "2" },
];

describe("SegmentedLedger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
    vi.mocked(getChatHistory).mockResolvedValue({ messages: [], weakPool: false });
  });

  afterEach(() => cleanup());

  it("adds no segment chrome on a first checkpoint — there is no history to file yet", async () => {
    const { queryByText, container } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "composing", activeGateStage: 1 },
    });

    await waitFor(() => expect(chatLedger.historyLoaded).toBe(true));
    // No collapsed rows, and no "Research ledger" head — this reads exactly like the
    // plain conversation it replaces.
    expect(container.querySelector(".segment-row")).toBeNull();
    expect(queryByText("Research ledger")).toBeNull();
  });

  it("files a past checkpoint as a collapsed read-only row once a later gate is active", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: G1_HISTORY, weakPool: false });

    const { findByText, queryByText } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "composing", activeGateStage: 4 },
    });

    await findByText("Niche checkpoint");
    // Collapsed: the earlier conversation is summarized, not rendered.
    expect(queryByText("narrow the niche")).toBeNull();
  });

  it("expands a past checkpoint inline, read-only", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: G1_HISTORY, weakPool: false });

    const { findByText, getByRole } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "composing", activeGateStage: 4 },
    });

    const row = await findByText("Niche checkpoint");
    const button = row.closest("button")!;
    expect(button.getAttribute("aria-expanded")).toBe("false");

    await fireEvent.click(button);

    expect(button.getAttribute("aria-expanded")).toBe("true");
    await findByText("narrow the niche");
    await findByText("Checkpoint passed");
    // Exactly ONE composer on the page — the active checkpoint's. History is read-only.
    expect(getByRole("textbox", { name: "Message the analyst" })).toBeTruthy();
  });

  it("shows the applied-change count on a checkpoint that changed the framing", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({
      messages: [
        ...G1_HISTORY,
        {
          id: "r1",
          gateStage: 1,
          role: "receipt",
          content: "Applied changes to Niche description",
          patchJson: {
            kind: "ledger_event",
            version: 1,
            event: "gate_patch_applied",
            patch: { niche_description: "x" },
            rows: [{ label: "Niche description", value: "x" }],
          },
          truncated: false,
          createdAt: "3",
        },
      ],
      weakPool: false,
    } as never);

    const { findByText } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "composing", activeGateStage: 4 },
    });

    await findByText(/1 change applied/);
  });

  it("keeps the ledger on screen while a stage runs — status instead of a composer", async () => {
    const { findByText, queryByRole } = render(SegmentedLedger, {
      props: {
        jobId: "job-1",
        interactionState: "working",
        jobStatus: "RUNNING",
        stagesCompleted: 3,
        totalStages: 16,
        progressPercent: 38,
      },
    });

    await findByText("ANALYST OPENS AT THE NEXT CHECKPOINT");
    await findByText(/Working on stage 3 of 16/);
    // A live SYSTEM row reports the machine's progress…
    await findByText(/38%/);
    // …and the composer is REPLACED, not disabled — a dead input reads as breakage.
    expect(queryByRole("textbox", { name: "Message the analyst" })).toBeNull();
  });

  it("speaks the final leg's language during deep research", async () => {
    const { findByText } = render(SegmentedLedger, {
      props: {
        jobId: "job-1",
        interactionState: "working",
        jobStatus: "RUNNING_PHASE2",
        stagesCompleted: 12,
        totalStages: 16,
        progressPercent: 70,
      },
    });

    await findByText("REPORT GENERATING");
    await findByText(/This is the final leg/);
  });

  it("closes the transcript when the run is terminal", async () => {
    vi.mocked(getChatHistory).mockResolvedValue({ messages: G1_HISTORY, weakPool: false });

    const { findByText, queryByRole } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "readonly" },
    });

    await findByText(/conversation closed/);
    expect(queryByRole("textbox", { name: "Message the analyst" })).toBeNull();
  });

  it("offers a retry instead of blanking when history fails to load", async () => {
    vi.mocked(getChatHistory).mockRejectedValue(new Error("network"));

    const { findByText, findAllByText } = render(SegmentedLedger, {
      props: { jobId: "job-1", interactionState: "composing", activeGateStage: 1 },
    });

    await findByText("Earlier conversation didn't load.");
    // EXACTLY ONE retry, and the count is the assertion. SegmentedLedger mounts a live thread
    // plus a read-only thread per past segment, and every ChatThread gates on the same
    // `loadFailed` flag — so without `showHistoryRetry={false}` a single failed fetch paints an
    // identical Retry button once per mounted thread, on top of the ledger's own banner. The host
    // that shows the failure message owns the retry.
    const retryButtons = await findAllByText("Retry");
    expect(retryButtons).toHaveLength(1);
  });
});
