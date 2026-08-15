/**
 * The guided-research shell is the SECOND mount site of `ResearchProgressScreen`, and the
 * only other place the idea-check phase track can render. It is also the one that cannot
 * be handed the outcome: it has no server load, and `getJob` carries no `idea_validation`.
 *
 * That is safe only because the state where an outcome EXISTS never renders here —
 * `belongsOnCanonicalJobPage` redirects it away before `job` is assigned, so this shell
 * only ever shows the Phase-1 leg, where the idea check has not run yet. This file pins
 * that structural fact; if the redirect ever narrows, the screen starts claiming a
 * completed verdict again and these tests are the alarm.
 *
 * WHAT THIS FILE DOES NOT PIN — a cross-layer coupling, recorded because the argument for
 * completeness rests on it. Sweeping all 120 status × dispatch-kind combinations leaves
 * exactly two that neither redirect nor render correctly: `PENDING` + `DEEP_RESEARCH`.
 * Those are unreachable, but for a BACKEND reason this frontend suite cannot see: every
 * write of `JobStatus.PENDING` is a `prisma.job.create` — `jobService.ts:41` and
 * `creditService.ts:882`, verified 2026-08-14, no `update` writes it anywhere — so PENDING
 * exists only at creation, where no DEEP_RESEARCH dispatch has been authorized yet.
 * The assertions below are all frontend redirects. If PENDING ever becomes writable later
 * in the lifecycle, nothing here goes red — add `PENDING` to the redirect list at that
 * moment rather than trusting this comment to be re-read.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/svelte";
import { page } from "$app/state";

const mocks = vi.hoisted(() => ({
  getJob: vi.fn(),
  goto: vi.fn(() => Promise.resolve()),
}));

vi.mock("$app/navigation", () => ({
  goto: mocks.goto,
  invalidateAll: vi.fn(() => Promise.resolve()),
}));

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    getJob: mocks.getJob,
    subscribeToProgress: vi.fn(() => () => {}),
  };
});

// The ledger rail is not under test and its store is network-backed; stub the exact
// surface the shell and SegmentedLedger read.
vi.mock("$lib/stores/chatLedger.svelte", () => ({
  chatLedger: {
    init: vi.fn(() => Promise.resolve()),
    reload: vi.fn(() => Promise.resolve()),
    segmentMessages: vi.fn(() => []),
    segments: [],
    appliedPatchIds: new Set<string>(),
    historyLoaded: true,
    loadFailed: false,
    usedTurns: 0,
    maxTurns: 10,
  },
}));

import PageComponent from "../+page.svelte";

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    niche: "vet clinics",
    status: "RUNNING",
    entryMode: "validate_idea",
    stagesCompleted: 2,
    totalStages: 16,
    currentStage: 3,
    progress: [],
    ...overrides,
  };
}

const squash = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, " ");

beforeEach(() => {
  vi.clearAllMocks();
  const state = page as unknown as { params: Record<string, string>; data: Record<string, unknown> };
  state.params = { jobId: "job-1" };
  state.data = { ...state.data, stageCosts: { guided: null } };
});

afterEach(() => cleanup());

describe("guided-research shell — the idea-check progress track", () => {
  it("never renders the progress screen for a run that has an idea-check outcome", async () => {
    // RUNNING_PHASE2 is the exact state the job page renders the refused chrome in. Here
    // it is redirected before `job` is set, so no progress screen exists to lie.
    mocks.getJob.mockResolvedValue(job({ status: "RUNNING_PHASE2" }));
    const view = render(PageComponent);
    await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1", { replaceState: true }));
    expect(view.container.querySelector(".research-progress")).toBeNull();
    expect(squash(view.container.textContent)).not.toContain("Your verdict");
  });

  it("redirects a queued Deep Research run away too", async () => {
    mocks.getJob.mockResolvedValue(job({ status: "QUEUED", activeDispatchKind: "DEEP_RESEARCH" }));
    const view = render(PageComponent);
    await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith("/jobs/job-1", { replaceState: true }));
    expect(view.container.querySelector(".research-progress")).toBeNull();
  });

  it("shows the Phase-1 leg, where no idea-check outcome exists yet", async () => {
    mocks.getJob.mockResolvedValue(job());
    const view = render(PageComponent);
    await waitFor(() => expect(view.container.querySelector(".research-progress")).toBeTruthy());
    expect(mocks.goto).not.toHaveBeenCalled();

    // Phase 1 is segment 1 of 3 and phase 2 is still ahead of it — the "done" marking
    // that made "Your verdict" a lie is reachable only from the Deep Research leg.
    const segments = Array.from(view.container.querySelectorAll(".rp-seg")).map((seg) => ({
      label: squash(seg.querySelector(".rp-seg-label")?.textContent),
      state: seg.getAttribute("data-state"),
    }));
    expect(segments).toEqual([
      { label: "Research", state: "active" },
      { label: "Your verdict", state: "pending" },
      { label: "Deep Research", state: "pending" },
    ]);
  });
});
