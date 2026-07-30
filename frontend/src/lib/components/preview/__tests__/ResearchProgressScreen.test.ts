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
    expect(view.getByText("RUN STOPS · UNUSED CREDITS REFUNDED")).toBeInTheDocument();

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
        totalStages: 15,
      },
    });

    expect(view.getByText("Stage 2 of 14")).toBeInTheDocument();
    expect(view.getByText(/Stage 2 \/ 14/)).toBeInTheDocument();
    expect(view.queryByText("Build")).toBeNull();
    expect(view.getByText("Pick ideas")).toBeInTheDocument();
  });
});
