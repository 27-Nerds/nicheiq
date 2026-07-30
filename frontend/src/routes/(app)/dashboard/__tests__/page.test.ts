import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/svelte";
import type { Job } from "$lib/types/job";

vi.mock("$lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("$lib/api")>();
  return {
    ...actual,
    subscribeToProgress: vi.fn(() => () => {}),
  };
});

import DashboardPage from "../+page.svelte";

afterEach(() => cleanup());

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
        selectedSolutionIds: ["idea-alpha"],
        selectedSolutions: ["Alpha Idea"],
      }),
    ]);

    expect(view.getByText("Deep Research is waiting for a worker…")).toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Cancel" })).toBeNull();
    expect(view.getByRole("link", { name: "View" })).toHaveAttribute("href", "/jobs/job-1");
  });
});
