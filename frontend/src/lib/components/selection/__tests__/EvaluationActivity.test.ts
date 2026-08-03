import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import EvaluationActivity from "../EvaluationActivity.svelte";

const PENDING = {
  sourceMessageId: "message-1",
  evaluationId: "dispatch-1",
  kind: "idea_synthesis" as const,
  proposedTitle: "GLP-1 Off-Ramp + Peptide Maintenance Hub",
  outcome: "pending" as const,
};

describe("EvaluationActivity — live view", () => {
  afterEach(cleanup);

  it("keeps a pending evaluation distinct from Deep Research and leaves comparison available", () => {
    const view = render(EvaluationActivity, {
      props: { jobId: "job-1", activities: [PENDING], view: "live" },
    });

    // With no operation on the wire yet, the wait defaults to queued rather than
    // implying a worker is already on it.
    expect(view.getByText(/Waiting for a free worker — GLP-1 Off-Ramp/)).toBeInTheDocument();
    expect(view.getByText(/Your request is in the queue/)).toBeInTheDocument();
    expect(view.queryByText(/Deep Research/i)).not.toBeInTheDocument();
    expect(view.queryByText(/read-only/i)).not.toBeInTheDocument();
  });

  it("distinguishes a queued wait from a running one", () => {
    const queued = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [PENDING],
        view: "live",
        operation: { createdAt: new Date().toISOString(), claimedAt: null },
      },
    });
    expect(queued.getByText(/Waiting for a free worker/)).toBeInTheDocument();
    cleanup();

    const running = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [PENDING],
        view: "live",
        operation: { createdAt: new Date().toISOString(), claimedAt: new Date().toISOString() },
      },
    });
    expect(running.getByText(/^Scoring /)).toBeInTheDocument();
  });

  it("presents recovery as restoration and never offers scoring or cancellation", () => {
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [PENDING],
        view: "live",
        operation: {
          state: "RECOVERING",
          createdAt: new Date().toISOString(),
          claimedAt: null,
        },
        onCancel: () => undefined,
      },
    });

    expect(view.getByText(/Restoring your previous candidate set/)).toBeInTheDocument();
    expect(view.getByText(/any refundable credits are returned; if no refund applies/)).toBeInTheDocument();
    expect(view.queryByText(/^Scoring /)).not.toBeInTheDocument();
    expect(view.queryByText(/Waiting for a free worker/)).not.toBeInTheDocument();
    expect(view.queryByRole("button", { name: "Cancel evaluation" })).not.toBeInTheDocument();
  });

  it("offers a re-check instead of freezing when the poll gives up", () => {
    const rechecked: string[] = [];
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [PENDING],
        view: "live",
        stalled: true,
        onRecheck: () => rechecked.push("recheck"),
      },
    });

    expect(view.getByText(/We stopped checking automatically/)).toBeInTheDocument();
    view.getByRole("button", { name: "Check for the result" }).click();
    expect(rechecked).toEqual(["recheck"]);
  });

  it("offers operation-scoped cancellation while an evaluation is pending", () => {
    const cancelled: string[] = [];
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [PENDING],
        view: "live",
        onCancel: () => cancelled.push("cancel"),
      },
    });

    view.getByRole("button", { name: "Cancel evaluation" }).click();
    expect(cancelled).toEqual(["cancel"]);
  });

  it("renders nothing once every evaluation has settled", () => {
    // The whole point of the split: a settled result must not hold space above the
    // candidate pool on the page whose job is choosing between candidates.
    const { container } = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        activities: [{ ...PENDING, outcome: "demoted" as const }],
        view: "live",
      },
    });

    expect(container.querySelector("section")).toBeNull();
  });
});

describe("EvaluationActivity — record view", () => {
  afterEach(cleanup);

  it("omits still-running evaluations, which belong to the live view", () => {
    const { container } = render(EvaluationActivity, {
      props: { jobId: "job-1", activities: [PENDING], view: "record" },
    });

    expect(container.querySelector("section")).toBeNull();
  });

  it("shows proposed versus evaluated identity, the reason, and where the result went", () => {
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        view: "record",
        activities: [{
          ...PENDING,
          outcome: "demoted" as const,
          result: {
            solution_name: "GLP-1 Regain Speedometer",
            market_fit_score: 0.4,
            reason: "Personal-wallet payability was too weak.",
          },
        }],
      },
    });

    expect(view.getByText("Did not qualify")).toBeInTheDocument();
    expect(view.getByText("GLP-1 Off-Ramp + Peptide Maintenance Hub")).toBeInTheDocument();
    expect(view.getByText("GLP-1 Regain Speedometer")).toBeInTheDocument();
    expect(view.getByText("40 market fit")).toBeInTheDocument();
    expect(view.getByText("Review evaluation")).toBeInTheDocument();
    // Points at the row's real home instead of restating it here.
    expect(
      view.getByText("The full analysis is kept with the ideas you screened out."),
    ).toBeInTheDocument();
  });

  it("gives a demoted row an exact durable-result destination", () => {
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        view: "record",
        activities: [{ ...PENDING, outcome: "demoted" as const }],
      },
    });

    expect(view.getByRole("link", { name: /Review screened-out result/ })).toHaveAttribute(
      "href",
      "/jobs/job-1?evaluationId=dispatch-1#examined-ruled-out",
    );
  });

  it("links an accepted result to the appended candidate pool", () => {
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        view: "record",
        activities: [{
          sourceMessageId: "message-2",
          evaluationId: "dispatch-2",
          kind: "idea_synthesis" as const,
          proposedTitle: "Maintenance Hub",
          outcome: "accepted" as const,
          result: { solution_name: "Maintenance Hub", market_fit_score: 0.72 },
        }],
      },
    });

    expect(view.getByText("Added to candidates")).toBeInTheDocument();
    expect(view.getByText("It is in the ranked candidates above.")).toBeInTheDocument();
    expect(view.getByRole("link", { name: /View candidate/ })).toHaveAttribute(
      "href",
      "/jobs/job-1#opportunities",
    );
  });

  it.each([
    ["failed" as const, "Evaluation failed", "The evaluation failed before producing a candidate."],
    ["refunded" as const, "Refunded", "The evaluation did not produce a candidate. Eligible credits were returned."],
    ["cancelled" as const, "Cancelled", "The evaluation was cancelled before work started, so no candidate was produced."],
  ])("makes the %s terminal outcome explicit", (outcome, label, detail) => {
    // These two produce no candidate and no ruled-out finding, so the record is the
    // ONLY durable place they exist — it must never drop them.
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        view: "record",
        activities: [{
          sourceMessageId: `message-${outcome}`,
          evaluationId: `dispatch-${outcome}`,
          kind: "idea_synthesis" as const,
          proposedTitle: "Maintenance Hub",
          outcome,
        }],
      },
    });

    expect(view.getByText(label)).toBeInTheDocument();
    expect(view.getByText(detail)).toBeInTheDocument();
    expect(view.getByText("Review evaluation")).toBeInTheDocument();
    if (outcome !== "refunded") {
      expect(view.queryByText(/credits were returned/i)).not.toBeInTheDocument();
    }
  });

  it("shows only the latest settled receipt in the post-run handoff", () => {
    const proposed: string[] = [];
    const latest = {
      ...PENDING,
      sourceMessageId: "latest",
      evaluationId: "dispatch-latest",
      outcome: "accepted" as const,
      result: {
        solution_name: "Latest candidate",
        idea_id: "idea-latest",
        idea_revision: 4,
      },
    };
    const view = render(EvaluationActivity, {
      props: {
        jobId: "job-1",
        view: "handoff",
        activities: [latest, {
          ...PENDING,
          sourceMessageId: "older",
          evaluationId: "dispatch-older",
          proposedTitle: "Older direction",
          outcome: "demoted" as const,
        }],
        onProposeCandidate: (activity) => proposed.push(activity.sourceMessageId),
      },
    });

    expect(view.getByText("Your direction has a result")).toBeInTheDocument();
    expect(view.queryByText("Older direction")).not.toBeInTheDocument();
    view.getByRole("button", { name: /Review for shortlist/ }).click();
    expect(proposed).toEqual(["latest"]);
  });
});
