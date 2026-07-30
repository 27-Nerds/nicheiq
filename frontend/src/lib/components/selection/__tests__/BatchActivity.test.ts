import { cleanup, fireEvent, render, within } from "@testing-library/svelte";
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
          focus: "novelty",
          addedIdeas: [],
          refPrecision: "exact",
          addedIdeaIds: [],
        }],
        onRetry,
      },
    });

    expect(view.getByText(label)).toBeInTheDocument();
    await fireEvent.click(view.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledWith(expect.objectContaining({
      operationId: `batch-${outcome}`,
      focus: "novelty",
    }));
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

  it("shows only compact in-flight status in a nested selection workspace", () => {
    const view = render(BatchActivity, {
      props: {
        view: "live",
        activities: [
          {
            operationId: "pending-3",
            ordinal: 3,
            focus: "distribution",
            outcome: "pending",
            addedIdeas: [],
            refPrecision: "exact",
            addedIdeaIds: [],
          },
          {
            operationId: "settled-2",
            ordinal: 2,
            focus: "novelty",
            outcome: "completed",
            addedCount: 2,
            addedIdeas: [],
            refPrecision: "exact",
            addedIdeaIds: ["idea-1", "idea-2"],
          },
        ],
      },
    });

    expect(view.getByLabelText("Idea batch in progress")).toHaveTextContent(
      "Batch 3 · Distribution focus",
    );
    expect(view.queryByText("Batch added")).not.toBeInTheDocument();
    expect(view.queryByText("Additional batches")).not.toBeInTheDocument();
    expect(view.queryByText(/Batch history/)).not.toBeInTheDocument();
  });

  it("replaces an indefinite spinner with a non-destructive status check after polling stalls", async () => {
    const onRecheck = vi.fn();
    const view = render(BatchActivity, {
      props: {
        view: "live",
        stalledOperationId: "pending-4",
        activities: [{
          operationId: "pending-4",
          ordinal: 4,
          focus: "auto",
          outcome: "pending",
          addedIdeas: [],
          refPrecision: "exact",
          addedIdeaIds: [],
        }],
        onRecheck,
      },
    });

    expect(view.getByText(/Automatic checks paused/)).toBeInTheDocument();
    expect(view.container.querySelector(".spin")).toBeNull();
    await fireEvent.click(view.getByRole("button", { name: "Check status" }));
    expect(onRecheck).toHaveBeenCalledWith(expect.objectContaining({
      operationId: "pending-4",
    }));
  });

  it("keeps older outcomes, counts, and recovery actions inside batch history", async () => {
    const onReviewCandidates = vi.fn();
    const onReviewRuledOut = vi.fn();
    const onRetry = vi.fn();
    const view = render(BatchActivity, {
      props: {
        activities: [
          {
            operationId: "latest-4",
            ordinal: 4,
            focus: "auto",
            outcome: "completed",
            generatedCount: 1,
            addedCount: 1,
            addedIdeas: [{ ideaId: "idea-latest", ideaRevision: 1 }],
            refPrecision: "exact",
            addedIdeaIds: ["idea-latest"],
          },
          {
            operationId: "older-added-3",
            ordinal: 3,
            focus: "novelty",
            outcome: "completed",
            generatedCount: 3,
            addedCount: 2,
            addedIdeas: [
              { ideaId: "idea-1", ideaRevision: 1 },
              { ideaId: "idea-2", ideaRevision: 1 },
            ],
            refPrecision: "exact",
            addedIdeaIds: ["idea-1", "idea-2"],
          },
          {
            operationId: "older-empty-2",
            ordinal: 2,
            focus: "distribution",
            outcome: "no_candidates_added",
            generatedCount: 3,
            addedCount: 0,
            ruledOutCount: 3,
            addedIdeas: [],
            refPrecision: "exact",
            addedIdeaIds: [],
          },
          {
            operationId: "older-failed-1",
            ordinal: 1,
            focus: "auto",
            outcome: "failed",
            generatedCount: 1,
            addedCount: 0,
            addedIdeas: [],
            refPrecision: "exact",
            addedIdeaIds: [],
          },
        ],
        onReviewCandidates,
        onReviewRuledOut,
        onRetry,
      },
    });

    const summary = view.getByText("Batch history (3)");
    await fireEvent.click(summary);
    const history = summary.closest("details");
    if (!history) throw new Error("Expected batch history disclosure");
    const scoped = within(history);

    expect(scoped.getByText("Batch 3 · Differentiation focus")).toBeInTheDocument();
    expect(scoped.getByText(/Added 2 of 3 generated candidates/)).toBeInTheDocument();
    expect(scoped.getByText(/0 of 3 generated candidates were added.*3 ideas were retained/)).toBeInTheDocument();
    expect(scoped.getByText(/could not complete after generating 1 candidate/)).toBeInTheDocument();

    await fireEvent.click(scoped.getByRole("button", { name: "Review new candidates" }));
    expect(onReviewCandidates).toHaveBeenCalledWith(["idea-1", "idea-2"]);

    await fireEvent.click(scoped.getByRole("button", { name: "Review ruled-out ideas" }));
    expect(onReviewRuledOut).toHaveBeenCalledWith("older-empty-2");

    await fireEvent.click(scoped.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledWith(expect.objectContaining({
      operationId: "older-failed-1",
      focus: "auto",
    }));
  });
});
