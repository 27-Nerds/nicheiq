import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import ResearchProgressScreen from "../ResearchProgressScreen.svelte";

describe("ResearchProgressScreen cancel confirm gate", () => {
  afterEach(cleanup);

  it("arms on the first click without cancelling, then cancels on confirm", async () => {
    const onCancel = vi.fn();
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        niche: "Freight brokers",
        onCancel,
      },
    });

    // First click only arms the gate — nothing is posted.
    await fireEvent.click(view.getByRole("button", { name: "Cancel research" }));
    expect(onCancel).not.toHaveBeenCalled();

    // Armed state shows the truthful consequence line and the confirm action.
    expect(view.getByText("RUN STOPS · ELIGIBLE CREDITS REFUNDED")).toBeInTheDocument();

    await fireEvent.click(view.getByRole("button", { name: "Stop this run" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("keeps an in-gate Cancel that disarms without cancelling the run", async () => {
    const onCancel = vi.fn();
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        niche: "Freight brokers",
        onCancel,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Cancel research" }));
    await fireEvent.click(view.getByRole("button", { name: "Cancel" }));

    expect(onCancel).not.toHaveBeenCalled();
    expect(view.getByRole("button", { name: "Cancel research" })).toBeInTheDocument();
  });

  it("renders no cancel affordance when onCancel is absent", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "deep_research" as const,
        jobStatus: "RUNNING_PHASE2",
        niche: "Freight brokers",
      },
    });

    expect(view.queryByRole("button", { name: "Cancel research" })).not.toBeInTheDocument();
    expect(view.getByText(/Research has started and can no longer be cancelled/)).toBeInTheDocument();
  });

  it("keeps Deep Research actions in the saved decision context", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "deep_research" as const,
        jobStatus: "RUNNING_PHASE2",
        jobId: "job-1",
        catalogPainPoints: [{ id: "pain-1", slug: "pain", title: "Other pain", severityScore: 8, mentionCount: 5 } as any],
      },
    });

    expect(view.getByRole("link", { name: "Review research scope" }))
      .toHaveAttribute("href", "/jobs/job-1/selection/compare");
    expect(view.queryByRole("link", { name: "Browse Ideas Catalog" })).not.toBeInTheDocument();
    expect(view.queryByText("Validated problems from other research")).not.toBeInTheDocument();
  });

  it("explains a lost live connection and offers a manual refresh", async () => {
    const onRefresh = vi.fn();
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "deep_research" as const,
        jobStatus: "RUNNING_PHASE2",
        connectionState: "paused" as const,
        onRefresh,
      },
    });

    expect(view.getByText(/Live updates paused/)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Refresh status" }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("renders the exact queued Deep Research cancellation consequence", async () => {
    const onCancel = vi.fn();
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "deep_research" as const,
        jobStatus: "QUEUED",
        niche: "Freight brokers",
        onCancel,
        cancelLabel: "Cancel queued Deep Research",
        cancelConfirmLabel: "Return to selection",
        cancelConsequence: "RETURN TO SELECTION · CHARGED CREDITS REFUNDED",
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Cancel queued Deep Research" }));
    expect(view.getByText("RETURN TO SELECTION · CHARGED CREDITS REFUNDED")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Return to selection" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows the active visible stage, not the number of stages already completed", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        niche: "Freelance bookkeepers",
        currentStage: 2,
        currentStageName: "Search & Discovery",
        stagesCompleted: 1,
        totalStages: 16,
      },
    });

    // ONE reading of the stage, in the live block. A second line under the progress bar
    // used to restate it as "Stage 2 / 14 · N%" — the same fact twice, ~12rem apart.
    expect(view.getByText("Stage 2 of 14")).toBeInTheDocument();
    expect(view.queryByText(/Stage 2 \/ 14/)).toBeNull();
    expect(view.queryByText("Build")).toBeNull();
    expect(view.getByText("Pick ideas")).toBeInTheDocument();
  });

  it("does not present a just-completed callback as the work still running", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        currentStage: 3,
        currentStageName: "Pain Point Analysis",
        stagesCompleted: 3,
        totalStages: 16,
      },
    });

    expect(view.queryByText("Pain Point Analysis")).toBeNull();
    expect(view.getByText("Research worker active")).toBeInTheDocument();
    expect(view.getByText("2 of 14 stages complete")).toBeInTheDocument();
  });

  it("folds the hidden audience stage into the combined public stage", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        currentStage: 4,
        currentStageName: "Audience Mapping",
        stagesCompleted: 2,
        totalStages: 16,
      },
    });

    expect(view.queryByText("Audience Mapping")).toBeNull();
    expect(view.getByText("Pain Point & Audience Analysis")).toBeInTheDocument();
    expect(view.getByText("Stage 3 of 14")).toBeInTheDocument();
  });

  it("uses neutral progress when a callback has no coherent stage number", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        currentStageName: "Pain Point Analysis",
        stagesCompleted: 3,
        totalStages: 16,
      },
    });

    expect(view.queryByText("Pain Point Analysis")).toBeNull();
    expect(view.getByText("Research worker active")).toBeInTheDocument();
    expect(view.getByText("3 of 14 stages complete")).toBeInTheDocument();
  });

  it("shows a persisted Stage 5 substep without changing the public stage count", () => {
    const view = render(ResearchProgressScreen, {
      props: {
        phase: "discovery" as const,
        jobStatus: "RUNNING",
        currentStage: 5,
        currentStageName: "Solution Ideation",
        stagesCompleted: 4,
        totalStages: 16,
        stageArtifact: {
          type: "stage_subprogress",
          stage: 5,
          code: "candidate_refinement",
          label: "Refining candidate solutions",
        },
      },
    });

    expect(view.getByText("Refining candidate solutions")).toBeInTheDocument();
    expect(view.getByText("Stage 4 of 14")).toBeInTheDocument();
  });
});
