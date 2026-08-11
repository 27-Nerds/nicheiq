import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { Job } from "$lib/types/job";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
  };
});

import DashboardPage from "../+page.svelte";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    niche: "Indie nail technicians",
    status: "AWAITING_SELECTION",
    createdAt: new Date().toISOString(),
    ...overrides,
  } as Job;
}

function renderDashboard(jobs: Job[]) {
  const data = {
    jobs,
    summariesByJobId: {},
    loadError: false,
    savedIdeas: [],
    savedPainPoints: [],
    savedCounts: { ideas: 0, painPoints: 0 },
  } as unknown as import("../$types").PageData;
  return render(DashboardPage, { props: { data } });
}

describe("dashboard awaiting-decision visibility", () => {
  it("shows AWAITING_SELECTION jobs in the default view with a Choose ideas CTA", () => {
    const view = renderDashboard([job({ solutionIdeasCount: 12 })]);

    expect(view.getByRole("heading", { name: "Ready to review" })).toBeInTheDocument();
    const row = view.getByRole("link", { name: /Choose ideas/ });
    expect(row).toHaveAttribute("href", "/jobs/job-1");
    expect(row).toHaveTextContent("Indie nail technicians");
    expect(row).toHaveTextContent(/12 ideas/);
  });

  it("shows AWAITING_GATE jobs in the default view with a checkpoint CTA", () => {
    const view = renderDashboard([
      job(),
      job({ id: "job-2", niche: "Freight brokers", status: "AWAITING_GATE" }),
    ]);

    // Both decision-pending jobs are visible without touching any filter.
    expect(view.getByText(/2 studies are ready to review/)).toBeInTheDocument();
    const gateRow = view.getByRole("link", { name: /Review checkpoint/ });
    expect(gateRow).toHaveAttribute("href", "/jobs/job-2");
    expect(gateRow).toHaveTextContent(/Checkpoint reached/);
    expect(view.getByRole("link", { name: /Choose ideas/ })).toHaveAttribute(
      "href",
      "/jobs/job-1",
    );
  });

  it("labels queued Phase 2 as Deep Research and does not offer the rejected generic cancel", () => {
    const view = renderDashboard([
      job({
        status: "QUEUED",
        jobMode: "interactive",
        activeDispatchKind: "DEEP_RESEARCH",
        selectedSolutionIds: ["idea-alpha"],
        selectedSolutions: ["Alpha Idea"],
      }),
    ]);

    expect(view.getByText("Deep Research is waiting for a worker…")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(view.getByRole("link", { name: "View progress" })).toHaveAttribute("href", "/jobs/job-1");
  });

  it("uses exact operation identity for queued idea work and preserves a progress re-entry link", () => {
    const view = renderDashboard([
      job({
        status: "QUEUED",
        jobMode: "interactive",
        activeDispatchKind: "REGENERATE",
        selectedSolutionIds: ["idea-alpha"],
      }),
    ]);

    expect(view.getByText("Another idea batch is waiting for a worker…")).toBeInTheDocument();
    expect(view.queryByText("Deep Research is waiting for a worker…")).toBeNull();
    expect(view.getByRole("link", { name: "View progress" })).toHaveAttribute("href", "/jobs/job-1");
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("always lets a running Discovery job be reopened and leaves the app layout as main owner", () => {
    const view = renderDashboard([
      job({
        status: "RUNNING",
        activeDispatchKind: "CONTINUE",
        currentStage: 2,
        currentStageName: "Search & Discovery",
        stagesCompleted: 1,
        totalStages: 16,
      }),
    ]);

    expect(view.getByRole("link", { name: "View progress" })).toHaveAttribute("href", "/jobs/job-1");
    expect(view.getByRole("progressbar").parentElement).toHaveTextContent(
      /Search & Discovery\s*· 2\/14/,
    );
    expect(view.queryByRole("main")).toBeNull();
  });

  it("shows completed callbacks as completed progress instead of the next active stage", () => {
    const view = renderDashboard([
      job({
        status: "RUNNING",
        activeDispatchKind: "CONTINUE",
        currentStage: 4,
        currentStageName: "Audience Mapping",
        stagesCompleted: 4,
        totalStages: 16,
      }),
    ]);

    expect(view.getByRole("progressbar").parentElement).toHaveTextContent(
      /Research worker active\s*· 3\/14/,
    );
    expect(view.queryByText(/Audience Mapping/)).toBeNull();
  });

  it("routes failed runs to recovery context instead of resuming from the dashboard", () => {
    const view = renderDashboard([job({ status: "FAILED", creditRefunded: true })]);

    const recovery = view.getByRole("link", { name: "Review recovery" });
    expect(recovery).toHaveAttribute("href", "/jobs/job-1#recover-run");
    expect(view.queryByRole("button", { name: "Resume" })).toBeNull();
  });

  it("surfaces the authoritative refund receipt after cancellation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: "cancelled",
      creditRefunded: 5,
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
    const view = renderDashboard([
      job({
        status: "QUEUED",
        activeDispatchKind: "CONTINUE",
      }),
    ]);

    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));
    expect(fetch).not.toHaveBeenCalled();
    expect(view.getByText("Stop this run?")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Confirm" }));

    expect(await view.findByRole("status")).toHaveTextContent(
      "Research cancelled. 5 credits were refunded.",
    );
  });

  it("cancels a seed evaluation without presenting the parent research as cancelled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: "cancelled",
      creditRefunded: 3,
    }), { status: 200, headers: { "Content-Type": "application/json" } })));
    const view = renderDashboard([
      job({
        status: "QUEUED",
        activeDispatchKind: "SEED_IDEA",
        activeOperation: {
          id: "seed-operation-1",
          kind: "SEED_IDEA",
          state: "AUTHORIZED",
        },
      }),
    ]);

    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));
    expect(view.getByText("Cancel evaluation?")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Confirm" }));

    expect(await view.findByRole("status")).toHaveTextContent(
      "Evaluation cancelled. 3 credits were refunded; the candidate pool is unchanged.",
    );
    expect(view.queryByText("Research cancelled.")).toBeNull();
  });

  it("does not offer cancellation after a seed evaluation has been claimed", () => {
    const view = renderDashboard([
      job({
        status: "RUNNING",
        activeDispatchKind: "SEED_IDEA",
        activeOperation: {
          id: "seed-operation-1",
          kind: "SEED_IDEA",
          state: "CLAIMED",
        },
      }),
    ]);

    expect(view.getByText("Evaluating your new direction…")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
  });
});
