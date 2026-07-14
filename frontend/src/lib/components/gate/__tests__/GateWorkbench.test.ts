import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/svelte";
import GateWorkbench from "../GateWorkbench.svelte";
import { gateAction, ApiError } from "$lib/api";
import type { GateG2Artifact } from "$lib/types/job";
import { chatLedger } from "$lib/stores/chatLedger.svelte";

// GateWorkbench embeds the same focused rail ChatThread used by the analyst overlay,
// which loads history on mount —
// stub the network-touching bits of $lib/api so mounting never fires a real fetch.
// ApiError is kept as the real class so `instanceof` checks in the component work.
vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    gateAction: vi.fn(),
    getChatHistory: vi.fn(() => Promise.resolve({ messages: [] })),
    streamChat: vi.fn(),
  };
});

// A SINGLE pain, deliberately — the pain-toggle "Exclude" label repeats per row,
// so keeping the fixture to one row keeps getByText unambiguous in these tests.
const g2Artifact: GateG2Artifact = {
  type: "audience_mapping_gate",
  primary_target: "Solo bookkeepers",
  segments: [],
  pains: [{ title: "Manual reconciliation", severity: 0.8, opportunity: null }],
};

const baseProps = {
  jobId: "job-1",
  gateStage: 4 as const,
  gateArtifact: g2Artifact,
  gateApplyCount: 0,
};

async function excludeAndApply(getByText: (t: string) => HTMLElement) {
  await fireEvent.click(getByText("Exclude"));
  await fireEvent.click(getByText("Apply changes"));
}

describe("GateWorkbench — apply_stay failure/re-arrival state flow (findings 12/13)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ledger store is a page-scoped singleton caching per jobId — reset between tests.
    chatLedger.reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("finding 13(b): clears local `applying` on an API-level rejection (409/400/402) without any SSE", async () => {
    vi.mocked(gateAction).mockRejectedValueOnce(new ApiError("Change limit reached", 409));

    const { getByText, findByText } = render(GateWorkbench, {
      props: { ...baseProps, gateReachedAt: "2026-07-10T10:00:00.000Z" },
    });

    await excludeAndApply(getByText);

    // The rejection surfaces its error message and the Apply button becomes
    // clickable again — `applying` must have cleared synchronously in the
    // catch block, not by waiting on a gateReachedAt change that will never come.
    await findByText("Change limit reached");
    const applyBtn = getByText("Apply changes").closest("button") as HTMLButtonElement;
    expect(applyBtn.disabled).toBe(false);
  });

  it("finding 12: fires onApplyStayError on rejection so the parent can clear its own pending flag", async () => {
    vi.mocked(gateAction).mockRejectedValueOnce(new ApiError("Concurrency conflict", 409));
    const onApplyStayStart = vi.fn();
    const onApplyStayError = vi.fn();

    const { getByText, findByText } = render(GateWorkbench, {
      props: {
        ...baseProps,
        gateReachedAt: "2026-07-10T10:00:00.000Z",
        onApplyStayStart,
        onApplyStayError,
      },
    });

    await excludeAndApply(getByText);
    await findByText("Concurrency conflict");

    expect(onApplyStayStart).toHaveBeenCalledTimes(1);
    expect(onApplyStayError).toHaveBeenCalledTimes(1);
  });

  it("finding 12: does NOT fire onApplyStayError when apply_stay succeeds", async () => {
    vi.mocked(gateAction).mockResolvedValueOnce({ status: "ok", message: "applied" });
    const onApplyStayError = vi.fn();

    const { getByText } = render(GateWorkbench, {
      props: { ...baseProps, gateReachedAt: "2026-07-10T10:00:00.000Z", onApplyStayError },
    });

    await excludeAndApply(getByText);

    expect(onApplyStayError).not.toHaveBeenCalled();
  });

  it("shows queue confirmation, then the live worker state during apply_stay", async () => {
    vi.mocked(gateAction).mockResolvedValueOnce({ status: "queued", message: "applied" });

    const { getByText, findByText, rerender } = render(GateWorkbench, {
      props: {
        ...baseProps,
        gateReachedAt: "2026-07-10T10:00:00.000Z",
        jobStatus: "AWAITING_GATE",
      },
    });

    await excludeAndApply(getByText);
    await findByText("Change queued for a worker");

    await rerender({
      ...baseProps,
      gateReachedAt: "2026-07-10T10:00:00.000Z",
      jobStatus: "RUNNING",
    });
    await findByText("Worker is rebuilding this checkpoint");
  });

  it("finding 13(a): a re-stamped gateReachedAt at the SAME gateStage clears `applying` (gate-failed revert self-heals)", async () => {
    vi.mocked(gateAction).mockResolvedValueOnce({ status: "ok", message: "applied" });

    const { getByText, queryByText, rerender } = render(GateWorkbench, {
      props: { ...baseProps, gateReachedAt: "2026-07-10T10:00:00.000Z" },
    });

    await excludeAndApply(getByText);

    // Mid-flight: the pending-patch panel is still up and the Apply button is disabled.
    const applyBtn = getByText("Apply changes").closest("button") as HTMLButtonElement;
    expect(applyBtn.disabled).toBe(true);

    // Backend re-stamps gateReachedAt to a NEW timestamp on re-arrival at the SAME
    // gateStage (workers.ts /gate-reached and /gate-failed both do `new Date()`), even
    // though gateStage itself hasn't changed — the effect's `!==` string comparison
    // must key off the timestamp changing, not the stage.
    await rerender({ ...baseProps, gateReachedAt: "2026-07-10T10:05:00.000Z" });

    // `applying` clearing resets the whole in-flight patch (the SAME behavior a
    // successful round-trip triggers): the pending-patch panel is gone and the pain
    // row's toggle reverts from "Excluded" back to its idle "Exclude" label.
    expect(queryByText("Apply changes")).toBeNull();
    expect(getByText("Exclude")).toBeTruthy();
  });
});

describe("GateWorkbench — conversation presentation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatLedger.reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("uses the expanded analyst overlay presentation in the workflow", () => {
    const { container, getByText } = render(GateWorkbench, {
      props: { ...baseProps, gateReachedAt: null },
    });

    const thread = container.querySelector(".chat-thread");
    expect(thread).toHaveClass("chat-thread--rail", "chat-thread--focus");
    expect(getByText("Analyst")).toBeTruthy();
  });
});
