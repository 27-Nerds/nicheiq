import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import BatchActivity from "../BatchActivity.svelte";

describe("BatchActivity", () => {
  afterEach(cleanup);

  it("shows an append-only pending state", () => {
    const view = render(BatchActivity, {
      props: {
        activities: [{
          operationId: "batch-1",
          ordinal: 2,
          focus: "auto",
          outcome: "pending",
          addedIdeas: [],
          refPrecision: "exact",
          addedIdeaIds: [],
        }],
      },
    });

    expect(view.getByText("Adding another batch")).toBeInTheDocument();
    expect(view.getByText(/Existing candidate scores and your shortlist stay unchanged/)).toBeInTheDocument();
  });

  it("reviews exactly the durable IDs added by a completed batch", async () => {
    const onReviewCandidates = vi.fn();
    const view = render(BatchActivity, {
      props: {
        activities: [{
          operationId: "batch-2",
          ordinal: 2,
          outcome: "completed",
          addedCount: 2,
          addedIdeas: [],
          refPrecision: "legacy_id_only",
          addedIdeaIds: ["idea-1", "idea-2"],
        }],
        onReviewCandidates,
      },
    });

    await fireEvent.click(view.getByRole("button", { name: "Review new candidates" }));
    expect(onReviewCandidates).toHaveBeenCalledWith(["idea-1", "idea-2"]);
  });

  it("routes a zero-add batch to its ruled-out analysis", async () => {
    const onReviewRuledOut = vi.fn();
    const view = render(BatchActivity, {
      props: {
        activities: [{
          operationId: "batch-3",
          ordinal: 3,
          outcome: "no_candidates_added",
          ruledOutCount: 3,
          addedIdeas: [],
          refPrecision: "exact",
          addedIdeaIds: [],
        }],
        onReviewRuledOut,
      },
    });

    expect(view.getByText("No candidates added")).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Review ruled-out ideas" }));
    expect(onReviewRuledOut).toHaveBeenCalledWith("batch-3");
  });

  it.each([
    ["failed" as const, "Batch failed"],
    ["refunded" as const, "Batch refunded"],
  ])("offers a retry after a %s batch", async (outcome, label) => {
    const onRetry = vi.fn();
    const view = render(BatchActivity, {
      props: {
        activities: [{
          operationId: `batch-${outcome}`,
          ordinal: 4,
          outcome,
          refunded: outcome === "refunded",
          addedIdeas: [],
          refPrecision: "exact",
          addedIdeaIds: [],
        }],
        onRetry,
      },
    });

    expect(view.getByText(label)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("keeps all pending runs and only the latest settled run above history", () => {
    const activity = (
      operationId: string,
      ordinal: number,
      outcome: "pending" | "completed",
    ) => ({
      operationId,
      ordinal,
      outcome,
      addedIdeas: [],
      refPrecision: "exact" as const,
      addedIdeaIds: [],
    });
    const view = render(BatchActivity, {
      props: {
        activities: [
          activity("pending-4", 4, "pending"),
          activity("settled-3", 3, "completed"),
          activity("pending-2", 2, "pending"),
          activity("settled-1", 1, "completed"),
        ],
      },
    });

    expect(view.getByText("Batch 4 · Automatic focus")).toBeInTheDocument();
    expect(view.getByText("Batch 3 · Automatic focus")).toBeInTheDocument();
    expect(view.getByText("Batch 2 · Automatic focus")).toBeInTheDocument();
    expect(view.getByText("Batch history (1)")).toBeInTheDocument();
  });
});
