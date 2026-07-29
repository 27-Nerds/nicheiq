import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import JobHeroAside from "../JobHeroAside.svelte";

afterEach(cleanup);

describe("JobHeroAside", () => {
  it("shows the selection decision instead of research telemetry while awaiting a choice", () => {
    render(JobHeroAside, {
      props: {
        state: "awaiting",
        selectionCount: 2,
        stagesCompleted: 5,
        totalStages: 16,
      },
    });

    expect(screen.getByText("Action needed")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("ideas ready to review")).toBeInTheDocument();
    expect(screen.getByText("Select")).toBeInTheDocument();
    expect(screen.queryByText("Progress")).not.toBeInTheDocument();
    expect(screen.queryByText("Elapsed")).not.toBeInTheDocument();
  });

  it("keeps live progress telemetry for an active research run", () => {
    render(JobHeroAside, {
      props: {
        state: "running",
        progressPercent: 42,
        stagesCompleted: 6,
        totalStages: 16,
        startedAt: null,
      },
    });

    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("16")).toBeInTheDocument();
    expect(screen.getByText("Elapsed")).toBeInTheDocument();
  });
});
